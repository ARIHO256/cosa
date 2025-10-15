from .models import (
    Alumni,
    Company,
    FeedbackAlumni,
    EventRegistration,
    Donation,
    NotificationAlumni,
    NotificationCoordinator,
    Message,
)
from .models import Notification as SocialNotification


def header_counts(request):
    """
    Provide notification/action counts that drive the header badges.
    Numbers are lightweight summaries so the header can highlight
    outstanding items that need attention.
    """
    data = {
        'admin_badges': {},
        'coordinator_badges': {},
        'alumni_badges': {},
    }

    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return data

    user_type = getattr(user, 'user_type', None)

    if user_type == '1':  # Administrator
        data['admin_badges'] = {
            'alumni': Alumni.objects.filter(admin__is_verified=False).count(),
            'companies': Company.objects.filter(is_verified=False).count(),
            'feedback': FeedbackAlumni.objects.filter(is_resolved=False).count(),
        }
    elif user_type == '2':  # Coordinator
        coordinator = getattr(user, 'alumnicoordinator', None)
        pending_regs = 0
        unread_notices = 0
        if coordinator:
            pending_regs = EventRegistration.objects.filter(
                status='pending',
                event__organizer=coordinator
            ).count()
            unread_notices = NotificationCoordinator.objects.filter(
                coordinator=coordinator,
                is_read=False
            ).count()

        data['coordinator_badges'] = {
            'alumni': Alumni.objects.filter(admin__is_verified=False).count(),
            'events': pending_regs,
            'donations': Donation.objects.filter(payment_status='pending').count(),
            'messages': unread_notices,
            'feedback': FeedbackAlumni.objects.filter(is_resolved=False).count(),
        }
    elif user_type == '3':  # Alumni
        alumni = getattr(user, 'alumni', None)
        unread_messages = 0
        unread_notifications = 0
        social_unread = 0
        if alumni:
            unread_messages = Message.objects.filter(
                recipient=alumni,
                status='sent'
            ).count()
            unread_notifications = NotificationAlumni.objects.filter(
                alumni=alumni,
                is_read=False
            ).count()
        # Count social notifications for any authenticated user
        social_unread = SocialNotification.objects.filter(recipient=user, is_read=False).count()

        data['alumni_badges'] = {
            'messages': unread_messages,
            'alerts': unread_notifications + social_unread,
            'notifications': unread_notifications + social_unread,
            'feedback': 0,
            'home': unread_messages + unread_notifications + social_unread,
        }

    return data
