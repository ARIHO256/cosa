import json
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render, reverse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q, Count, Sum, Avg, Prefetch
from django.db import models
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta
from django.utils.text import slugify
from django.conf import settings

from .models import *
from .forms import *
from .excel_utils import export_alumni_to_excel, export_alumni_by_graduation_year, export_alumni_statistics


@login_required
def coordinator_home(request):
    """COSA Coordinator Dashboard"""
    if request.user.user_type != '2':
        return redirect('login_page')
    
    coordinator = request.user.alumnicoordinator
    
    # Get dashboard statistics
    stats = {
        'total_alumni': Alumni.objects.filter(admin__is_verified=True).count(),
        'pending_verifications': Alumni.objects.filter(admin__is_verified=False).count(),
        'active_events': Event.objects.filter(status='upcoming').count(),
        'pending_registrations': EventRegistration.objects.filter(status='pending').count(),
        'active_jobs': JobPosting.objects.filter(is_active=True).count(),
        'total_donations': Donation.objects.filter(payment_status='completed').count(),
        'active_mentorships': MentorshipProgram.objects.filter(status='active').count(),
        'unread_feedback': FeedbackAlumni.objects.filter(is_resolved=False).count(),
    }
    
    # Get recent activities
    recent_alumni = Alumni.objects.filter(
        admin__is_verified=True
    ).order_by('-admin__date_joined')[:5]
    
    recent_events = Event.objects.filter(
        organizer=coordinator
    ).order_by('-created_at')[:5]
    
    pending_registrations = EventRegistration.objects.filter(
        status='pending',
        event__organizer=coordinator
    ).select_related('alumni', 'event').order_by('-registration_date')[:5]
    
    recent_feedback = FeedbackAlumni.objects.filter(
        is_resolved=False
    ).order_by('-created_at')[:5]
    
    context = {
        'coordinator': coordinator,
        'stats': stats,
        'recent_alumni': recent_alumni,
        'recent_events': recent_events,
        'pending_registrations': pending_registrations,
        'recent_feedback': recent_feedback,
    }
    
    return render(request, 'coordinator_template/coordinator_home.html', context)


@login_required
def manage_alumni(request):
    """Manage alumni profiles"""
    if request.user.user_type not in ['1', '2']:  # Allow both Admin (1) and Coordinator (2)
        return redirect('login_page')
    
    alumni_list = Alumni.objects.select_related(
        'admin', 'degree', 'graduation_year', 'current_company'
    ).order_by('-admin__date_joined')
    
    # Search functionality
    search = request.GET.get('search')
    if search:
        alumni_list = alumni_list.filter(
            Q(admin__first_name__icontains=search) |
            Q(admin__last_name__icontains=search) |
            Q(admin__email__icontains=search) |
            Q(student_id__icontains=search)
        )
    
    # Filter by verification status
    verification_status = request.GET.get('verification_status')
    if verification_status == 'verified':
        alumni_list = alumni_list.filter(admin__is_verified=True)
    elif verification_status == 'pending':
        alumni_list = alumni_list.filter(admin__is_verified=False)
    
    # Pagination
    paginator = Paginator(alumni_list, 25)
    page_number = request.GET.get('page')
    alumni = paginator.get_page(page_number)
    
    context = {
        'alumni': alumni,
        'total_count': alumni_list.count(),
    }
    
    return render(request, 'coordinator_template/manage_alumni.html', context)


@login_required
def verify_alumni(request, alumni_id):
    """Verify an alumni profile"""
    if request.user.user_type not in ['1', '2']:  # Allow both Admin (1) and Coordinator (2)
        return redirect('login_page')
    
    alumni = get_object_or_404(Alumni, id=alumni_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'verify':
            alumni.admin.is_verified = True
            alumni.admin.save()
            messages.success(request, f'{alumni.full_name} has been verified successfully!')
        elif action == 'reject':
            # You might want to send an email notification here
            messages.info(request, f'Verification for {alumni.full_name} has been rejected.')
        
        return redirect('manage_alumni')
    
    context = {
        'alumni': alumni,
    }
    
    return render(request, 'coordinator_template/verify_alumni.html', context)


@login_required
def manage_events(request):
    """Manage events"""
    if request.user.user_type != '2':
        return redirect('login_page')
    
    coordinator = request.user.alumnicoordinator
    events = Event.objects.filter(
        organizer=coordinator
    ).order_by('-created_at')
    
    # Filter by status
    status = request.GET.get('status')
    if status:
        events = events.filter(status=status)
    
    # Pagination
    paginator = Paginator(events, 20)
    page_number = request.GET.get('page')
    event_list = paginator.get_page(page_number)
    
    context = {
        'events': event_list,
        'event_statuses': Event.EVENT_STATUS,
    }
    
    return render(request, 'coordinator_template/manage_events.html', context)


@login_required
def create_event(request):
    """Create a new event"""
    if request.user.user_type != '2':
        return redirect('login_page')
    
    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES)
        if form.is_valid():
            event = form.save(commit=False)
            event.organizer = request.user.alumnicoordinator
            event.save()
            form.save_m2m()  # Save many-to-many relationships
            messages.success(request, 'Event created successfully!')
            return redirect('manage_events')
    else:
        form = EventForm()
    
    context = {
        'form': form,
    }
    
    return render(request, 'coordinator_template/create_event.html', context)


@login_required
def edit_event(request, event_id):
    """Edit an existing event"""
    if request.user.user_type != '2':
        return redirect('login_page')
    
    event = get_object_or_404(Event, id=event_id, organizer=request.user.alumnicoordinator)
    
    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES, instance=event)
        if form.is_valid():
            form.save()
            messages.success(request, 'Event updated successfully!')
            return redirect('manage_events')
    else:
        form = EventForm(instance=event)
    
    context = {
        'form': form,
        'event': event,
    }
    
    return render(request, 'coordinator_template/edit_event.html', context)


@login_required
def event_registrations(request, event_id):
    """Manage event registrations"""
    if request.user.user_type != '2':
        return redirect('login_page')
    
    event = get_object_or_404(Event, id=event_id, organizer=request.user.alumnicoordinator)
    registrations = EventRegistration.objects.filter(
        event=event
    ).select_related('alumni').order_by('-registration_date')
    
    # Filter by status
    status = request.GET.get('status')
    if status:
        registrations = registrations.filter(status=status)
    
    context = {
        'event': event,
        'registrations': registrations,
        'registration_statuses': EventRegistration.REGISTRATION_STATUS,
    }
    
    return render(request, 'coordinator_template/event_registrations.html', context)


@login_required
def approve_registration(request, registration_id):
    """Approve or reject event registration"""
    if request.user.user_type != '2':
        return redirect('login_page')
    
    registration = get_object_or_404(
        EventRegistration,
        id=registration_id,
        event__organizer=request.user.alumnicoordinator
    )
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'approve':
            registration.status = 'confirmed'
            registration.save()
            messages.success(request, 'Registration approved successfully!')
        elif action == 'reject':
            registration.status = 'cancelled'
            registration.save()
            messages.info(request, 'Registration rejected.')
        
        return redirect('event_registrations', event_id=registration.event.id)
    
    context = {
        'registration': registration,
    }
    
    return render(request, 'coordinator_template/approve_registration.html', context)


@login_required
def manage_news(request):
    """Manage news articles"""
    if request.user.user_type != '2':
        return redirect('login_page')
    
    coordinator = request.user.alumnicoordinator
    news_list = News.objects.filter(
        author=coordinator
    ).order_by('-created_at')
    
    # Filter by publication status
    status = request.GET.get('status')
    if status == 'published':
        news_list = news_list.filter(is_published=True)
    elif status == 'draft':
        news_list = news_list.filter(is_published=False)
    
    # Pagination
    paginator = Paginator(news_list, 20)
    page_number = request.GET.get('page')
    news = paginator.get_page(page_number)
    
    context = {
        'news': news,
    }
    
    return render(request, 'coordinator_template/manage_news.html', context)


@login_required
def create_news(request):
    """Create a new news article"""
    if request.user.user_type != '2':
        return redirect('login_page')
    
    if request.method == 'POST':
        title = request.POST.get('title')
        content = request.POST.get('content')
        category = request.POST.get('category')
        is_published = request.POST.get('is_published') == 'on'
        is_featured = request.POST.get('is_featured') == 'on'
        featured_image = request.FILES.get('featured_image')
        meta_description = request.POST.get('meta_description', '')
        
        # Generate slug
        slug = slugify(title)
        original_slug = slug
        counter = 1
        while News.objects.filter(slug=slug).exists():
            slug = f"{original_slug}-{counter}"
            counter += 1
        
        news = News.objects.create(
            title=title,
            content=content,
            category=category,
            author=request.user.alumnicoordinator,
            is_published=is_published,
            is_featured=is_featured,
            featured_image=featured_image,
            slug=slug,
            meta_description=meta_description,
            publish_date=timezone.now() if is_published else None
        )
        
        messages.success(request, 'News article created successfully!')
        return redirect('manage_news')
    
    context = {
        'categories': News.NEWS_CATEGORIES,
    }
    
    return render(request, 'coordinator_template/create_news.html', context)


@login_required
def edit_news(request, news_id):
    """Edit a news article"""
    if request.user.user_type != '2':
        return redirect('login_page')
    
    news = get_object_or_404(News, id=news_id, author=request.user.alumnicoordinator)
    
    if request.method == 'POST':
        news.title = request.POST.get('title')
        news.content = request.POST.get('content')
        news.category = request.POST.get('category')
        news.is_published = request.POST.get('is_published') == 'on'
        news.is_featured = request.POST.get('is_featured') == 'on'
        news.meta_description = request.POST.get('meta_description', '')
        
        if request.FILES.get('featured_image'):
            news.featured_image = request.FILES.get('featured_image')
        
        if news.is_published and not news.publish_date:
            news.publish_date = timezone.now()
        
        news.save()
        messages.success(request, 'News article updated successfully!')
        return redirect('manage_news')
    
    context = {
        'news': news,
        'categories': News.NEWS_CATEGORIES,
    }
    
    return render(request, 'coordinator_template/edit_news.html', context)


@login_required
def publish_news(request, news_id):
    """Publish a news article"""
    if request.user.user_type != '2':
        return redirect('login_page')
    
    if request.method == 'POST':
        news = get_object_or_404(News, id=news_id, author=request.user.alumnicoordinator)
        
        if not news.is_published:
            news.is_published = True
            news.publish_date = timezone.now()
            news.save()
            messages.success(request, f'"{news.title}" has been published successfully!')
        else:
            messages.info(request, f'"{news.title}" is already published.')
    
    return redirect('manage_news')


@login_required
def unpublish_news(request, news_id):
    """Unpublish a news article"""
    if request.user.user_type != '2':
        return redirect('login_page')
    
    if request.method == 'POST':
        news = get_object_or_404(News, id=news_id, author=request.user.alumnicoordinator)
        
        if news.is_published:
            news.is_published = False
            news.publish_date = None
            news.save()
            messages.success(request, f'"{news.title}" has been unpublished and saved as draft.')
        else:
            messages.info(request, f'"{news.title}" is already a draft.')
    
    return redirect('manage_news')


@login_required
def manage_jobs(request):
    """Manage job postings"""
    if request.user.user_type != '2':
        return redirect('login_page')
    
    jobs = JobPosting.objects.select_related(
        'company', 'posted_by'
    ).order_by('-created_at')
    
    # Filter by status
    status = request.GET.get('status')
    if status == 'active':
        jobs = jobs.filter(is_active=True)
    elif status == 'inactive':
        jobs = jobs.filter(is_active=False)
    
    # Search functionality
    search = request.GET.get('search')
    if search:
        jobs = jobs.filter(
            Q(title__icontains=search) |
            Q(company__name__icontains=search)
        )
    
    # Pagination
    paginator = Paginator(jobs, 20)
    page_number = request.GET.get('page')
    job_list = paginator.get_page(page_number)
    
    context = {
        'jobs': job_list,
    }
    
    return render(request, 'coordinator_template/manage_jobs.html', context)


@login_required
def job_applications(request, job_id):
    """View applications for a specific job"""
    if request.user.user_type != '2':
        return redirect('login_page')
    
    job = get_object_or_404(JobPosting, id=job_id)
    applications = JobApplication.objects.filter(
        job=job
    ).select_related('applicant').order_by('-application_date')
    
    context = {
        'job': job,
        'applications': applications,
    }
    
    return render(request, 'coordinator_template/job_applications.html', context)


@login_required
def manage_donations(request):
    """Manage donations"""
    if request.user.user_type != '2':
        return redirect('login_page')
    
    donations = Donation.objects.select_related('donor').order_by('-created_at')
    
    # Filter by status
    status = request.GET.get('status')
    if status:
        donations = donations.filter(payment_status=status)
    
    # Filter by type
    donation_type = request.GET.get('type')
    if donation_type:
        donations = donations.filter(donation_type=donation_type)
    
    # Pagination
    paginator = Paginator(donations, 25)
    page_number = request.GET.get('page')
    donation_list = paginator.get_page(page_number)
    
    # Calculate totals
    total_amount = donations.filter(payment_status='completed').aggregate(
        total=models.Sum('amount')
    )['total'] or 0
    
    context = {
        'donations': donation_list,
        'total_amount': total_amount,
        'payment_statuses': Donation.PAYMENT_STATUS,
        'donation_types': Donation.DONATION_TYPES,
    }
    
    return render(request, 'coordinator_template/manage_donations.html', context)


@login_required
def manage_mentorships(request):
    """Manage mentorship programs"""
    if request.user.user_type != '2':
        return redirect('login_page')
    
    mentorships = MentorshipProgram.objects.select_related(
        'mentor', 'mentee'
    ).order_by('-created_at')
    
    # Filter by status
    status = request.GET.get('status')
    if status:
        mentorships = mentorships.filter(status=status)
    
    # Pagination
    paginator = Paginator(mentorships, 20)
    page_number = request.GET.get('page')
    mentorship_list = paginator.get_page(page_number)
    
    context = {
        'mentorships': mentorship_list,
        'program_statuses': MentorshipProgram.PROGRAM_STATUS,
    }
    
    return render(request, 'coordinator_template/manage_mentorships.html', context)


@login_required
def create_mentorship(request):
    """Create a new mentorship program"""
    if request.user.user_type != '2':
        return redirect('login_page')
    
    if request.method == 'POST':
        mentor_id = request.POST.get('mentor')
        mentee_id = request.POST.get('mentee')
        focus_area = request.POST.get('focus_area')
        goals = request.POST.get('goals')
        duration_months = request.POST.get('duration_months')
        start_date = request.POST.get('start_date')
        
        mentor = get_object_or_404(Alumni, id=mentor_id, is_mentor=True)
        mentee = get_object_or_404(Alumni, id=mentee_id)
        
        MentorshipProgram.objects.create(
            mentor=mentor,
            mentee=mentee,
            focus_area=focus_area,
            goals=goals,
            duration_months=int(duration_months),
            start_date=start_date
        )
        
        messages.success(request, 'Mentorship program created successfully!')
        return redirect('manage_mentorships')
    
    # Get available mentors and mentees
    mentors = Alumni.objects.filter(is_mentor=True, admin__is_verified=True)
    mentees = Alumni.objects.filter(admin__is_verified=True)
    
    context = {
        'mentors': mentors,
        'mentees': mentees,
    }
    
    return render(request, 'coordinator_template/create_mentorship.html', context)


@login_required
def manage_feedback(request):
    """ManageCOSA Feedback"""
    if request.user.user_type != '2':
        return redirect('login_page')
    
    base_queryset = FeedbackAlumni.objects.select_related('alumni').order_by('-created_at')
    feedback_list = base_queryset

    total_feedback_count = base_queryset.count()
    pending_count = base_queryset.filter(is_resolved=False).count()
    resolved_count = base_queryset.filter(is_resolved=True).count()
    seven_days_ago = timezone.now() - timedelta(days=7)
    this_week_count = base_queryset.filter(created_at__gte=seven_days_ago).count()
    
    # Filter by resolution status
    status = request.GET.get('status')
    if status == 'resolved':
        feedback_list = feedback_list.filter(is_resolved=True)
    elif status == 'pending':
        feedback_list = feedback_list.filter(is_resolved=False)
    
    # Filter by type
    feedback_type = request.GET.get('type')
    if feedback_type:
        feedback_list = feedback_list.filter(feedback_type=feedback_type)
    
    rating_summary = feedback_list.aggregate(
        average_rating=Avg('rating'),
        total_rated=Count('rating'),
    )
    avg_rating = rating_summary['average_rating']
    if avg_rating is not None:
        rating_summary['average_rating'] = round(avg_rating, 2)
    
    # Pagination
    paginator = Paginator(feedback_list, 20)
    page_number = request.GET.get('page')
    feedback = paginator.get_page(page_number)
    
    context = {
        'feedback': feedback,
        'feedback_types': FeedbackAlumni.FEEDBACK_TYPES,
        'rating_summary': rating_summary,
        'pending_count': pending_count,
        'resolved_count': resolved_count,
        'this_week_count': this_week_count,
        'total_feedback_count': total_feedback_count,
    }
    
    return render(request, 'coordinator_template/manage_feedback.html', context)


@login_required
def reply_feedback(request, feedback_id):
    """Reply toCOSA Feedback"""
    if request.user.user_type != '2':
        return redirect('login_page')
    
    feedback = get_object_or_404(FeedbackAlumni, id=feedback_id)
    
    if request.method == 'POST':
        reply = request.POST.get('reply')
        feedback.reply = reply
        feedback.is_resolved = True
        feedback.save()
        
        messages.success(request, 'Reply sent successfully!')
        return redirect('manage_feedback')
    
    context = {
        'feedback': feedback,
    }
    
    return render(request, 'coordinator_template/reply_feedback.html', context)


@login_required
def resolve_feedback(request, feedback_id):
    """Mark feedback as resolved"""
    if request.user.user_type != '2':
        return redirect('login_page')
    
    if request.method == 'POST':
        feedback = get_object_or_404(FeedbackAlumni, id=feedback_id)
        
        if not feedback.is_resolved:
            feedback.is_resolved = True
            feedback.save()
            messages.success(request, f'Feedback "{feedback.subject}" has been marked as resolved.')
        else:
            messages.info(request, f'Feedback "{feedback.subject}" is already resolved.')
    
    return redirect('manage_feedback')


@login_required
def pending_feedback(request, feedback_id):
    """Mark feedback as pending"""
    if request.user.user_type != '2':
        return redirect('login_page')
    
    if request.method == 'POST':
        feedback = get_object_or_404(FeedbackAlumni, id=feedback_id)
        
        if feedback.is_resolved:
            feedback.is_resolved = False
            feedback.save()
            messages.success(request, f'Feedback "{feedback.subject}" has been marked as pending.')
        else:
            messages.info(request, f'Feedback "{feedback.subject}" is already pending.')
    
    return redirect('manage_feedback')


@login_required
def coordinator_profile(request):
    """Coordinator profile management"""
    if request.user.user_type != '2':
        return redirect('login_page')
    
    coordinator = request.user.alumnicoordinator
    
    if request.method == 'POST':
        # Update basic info
        coordinator.admin.first_name = request.POST.get('first_name')
        coordinator.admin.last_name = request.POST.get('last_name')
        coordinator.admin.phone_number = request.POST.get('phone_number')
        coordinator.admin.address = request.POST.get('address')
        coordinator.department = request.POST.get('department')
        
        if request.FILES.get('profile_pic'):
            coordinator.admin.profile_pic = request.FILES.get('profile_pic')
        
        coordinator.admin.save()
        coordinator.save()
        
        messages.success(request, 'Profile updated successfully!')
        return redirect('coordinator_profile')
    
    context = {
        'coordinator': coordinator,
    }
    
    return render(request, 'coordinator_template/coordinator_profile.html', context)


@csrf_exempt
def coordinator_fcmtoken(request):
    """Update FCM token for coordinator"""
    if request.user.user_type != '2':
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'})
    
    if request.method == 'POST':
        fcm_token = request.POST.get('fcm_token')
        if fcm_token:
            request.user.fcm_token = fcm_token
            request.user.save()
            return JsonResponse({'status': 'success'})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})


@login_required
def send_notification(request):
    """Send notifications to alumni"""
    if request.user.user_type != '2':
        return redirect('login_page')
    
    if request.method == 'POST':
        title = request.POST.get('title')
        message = request.POST.get('message')
        notification_type = request.POST.get('notification_type', 'system')
        target_audience = request.POST.get('target_audience', 'all')
        
        # Determine recipients
        if target_audience == 'all':
            recipients = Alumni.objects.filter(admin__is_verified=True)
        elif target_audience == 'graduation_year':
            year_id = request.POST.get('graduation_year')
            recipients = Alumni.objects.filter(
                graduation_year_id=year_id,
                admin__is_verified=True
            )
        elif target_audience == 'degree':
            degree_id = request.POST.get('degree')
            recipients = Alumni.objects.filter(
                degree_id=degree_id,
                admin__is_verified=True
            )
        else:
            recipients = Alumni.objects.none()
        
        # Create notifications
        notifications = []
        for recipient in recipients:
            notifications.append(
                NotificationAlumni(
                    alumni=recipient,
                    title=title,
                    message=message,
                    notification_type=notification_type
                )
            )
        
        NotificationAlumni.objects.bulk_create(notifications)
        
        messages.success(request, f'Notification sent to {len(notifications)} Citizens Secondary School alumni!')
        return redirect('coordinator_home')
    
    context = {
        'graduation_years': GraduationYear.objects.filter(is_active=True),
        'degrees': Degree.objects.filter(is_active=True),
        'notification_types': NotificationAlumni.NOTIFICATION_TYPES,
    }
    
    return render(request, 'coordinator_template/send_notification.html', context)


@login_required
def coordinator_messages_inbox(request):
    """Coordinator messages inbox - shows sent messages"""
    if request.user.user_type != '2':
        return redirect('login_page')
    
    # Get coordinator profile
    try:
        coordinator_profile = request.user.alumnicoordinator
    except AlumniCoordinator.DoesNotExist:
        messages.error(request, 'Coordinator profile not found.')
        return redirect('login_page')
    
    # Get messages sent by this coordinator
    sent_messages = Message.objects.filter(
        sender_type='coordinator',
        sender_coordinator=coordinator_profile
    ).select_related('recipient', 'recipient__admin').order_by('-created_at')
    
    # Pagination
    paginator = Paginator(sent_messages, 10)
    page_number = request.GET.get('page')
    messages_page = paginator.get_page(page_number)
    
    context = {
        'messages': messages_page,
        'coordinator_user': request.user,
    }
    
    return render(request, 'coordinator_template/messages_inbox.html', context)


def _build_alumni_recipient_queryset(request):
    """Return filtered alumni queryset for messaging recipients."""
    verified_alumni = Alumni.objects.filter(admin__is_verified=True).select_related('admin', 'graduation_year', 'degree')
    filters = {
        'search': request.GET.get('search', '').strip(),
        'student_id': request.GET.get('student_id', '').strip(),
        'graduation_year': request.GET.get('graduation_year', '').strip(),
        'degree': request.GET.get('degree', '').strip(),
    }
    
    queryset = verified_alumni
    
    if filters['search']:
        queryset = queryset.filter(
            Q(admin__first_name__icontains=filters['search']) |
            Q(admin__last_name__icontains=filters['search']) |
            Q(admin__email__icontains=filters['search'])
        )
    
    if filters['student_id']:
        queryset = queryset.filter(student_id__icontains=filters['student_id'])
    
    if filters['graduation_year']:
        queryset = queryset.filter(graduation_year_id=filters['graduation_year'])
    
    if filters['degree']:
        queryset = queryset.filter(degree_id=filters['degree'])
    
    queryset = queryset.order_by('graduation_year__display_order', 'admin__last_name', 'admin__first_name')
    filtered_count = queryset.count()
    total_count = verified_alumni.count()
    
    return queryset, filters, filtered_count, total_count


@login_required
def coordinator_send_message(request, recipient_id=None):
    """Send a message to an alumni"""
    if request.user.user_type != '2':
        return redirect('login_page')
    
    # Get coordinator profile
    try:
        coordinator_profile = request.user.alumnicoordinator
    except AlumniCoordinator.DoesNotExist:
        messages.error(request, 'Coordinator profile not found.')
        return redirect('login_page')
    
    recipient = None
    if recipient_id:
        recipient = get_object_or_404(Alumni, id=recipient_id, admin__is_verified=True)
    
    recipient_queryset, filters, filtered_recipient_count, total_recipient_count = _build_alumni_recipient_queryset(request)
    
    form_initial = {}
    if recipient:
        form_initial['recipient'] = recipient
    
    if request.method == 'POST':
        form = CoordinatorMessageForm(request.POST, request.FILES, initial=form_initial)
        if form.is_valid():
            message = form.save(commit=False)
            message.sender_type = 'coordinator'
            message.sender_coordinator = coordinator_profile
            message.save()
            messages.success(request, f'Message sent successfully to {message.recipient.full_name}!')
            return redirect('coordinator_messages_inbox')
    else:
        form = CoordinatorMessageForm(initial=form_initial)
    
    # Apply filtered queryset to recipient field
    form.fields['recipient'].queryset = recipient_queryset
    
    context = {
        'form': form,
        'recipient': recipient,
        'coordinator_user': request.user,
        'graduation_years': GraduationYear.objects.filter(is_active=True).order_by('display_order', 'year'),
        'degrees': Degree.objects.filter(is_active=True).order_by('name'),
        'filters': filters,
        'filtered_recipient_count': filtered_recipient_count,
        'total_recipient_count': total_recipient_count,
    }
    
    return render(request, 'coordinator_template/send_message.html', context)


@login_required
def coordinator_alumni_search(request):
    """AJAX endpoint to filter alumni recipients dynamically."""
    if request.user.user_type != '2':
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        request.user.alumnicoordinator
    except AlumniCoordinator.DoesNotExist:
        return JsonResponse({'error': 'Coordinator profile not found'}, status=403)
    
    recipient_queryset, _, filtered_recipient_count, total_recipient_count = _build_alumni_recipient_queryset(request)
    
    recipients = [
        {
            'id': alumni.id,
            'label': format_alumni_recipient_label(alumni),
        }
        for alumni in recipient_queryset
    ]
    
    return JsonResponse({
        'results': recipients,
        'filtered_count': filtered_recipient_count,
        'total_count': total_recipient_count,
    })


@login_required
def coordinator_view_message(request, message_id):
    """View a specific message"""
    if request.user.user_type != '2':
        return redirect('login_page')
    
    # Get coordinator profile
    try:
        coordinator_profile = request.user.alumnicoordinator
    except AlumniCoordinator.DoesNotExist:
        messages.error(request, 'Coordinator profile not found.')
        return redirect('login_page')
    
    message_queryset = Message.objects.select_related(
        'sender_alumni__admin',
        'sender_admin__admin',
        'sender_coordinator__admin',
        'recipient__admin'
    ).prefetch_related(
        Prefetch(
            'replies',
            queryset=MessageReply.objects.select_related(
                'sender_alumni__admin',
                'sender_admin__admin',
                'sender_coordinator__admin'
            ).order_by('created_at')
        )
    )
    message = get_object_or_404(
        message_queryset,
        id=message_id,
        sender_type='coordinator',
        sender_coordinator=coordinator_profile
    )
    
    # Mark as read if not already
    if message.status != 'read':
        message.status = 'read'
        message.read_at = timezone.now()
        message.save()

    replies = list(message.replies.all())
    reply_form = MessageReplyForm()

    if request.method == 'POST':
        reply_form = MessageReplyForm(request.POST, request.FILES)
        if reply_form.is_valid():
            reply = reply_form.save(commit=False)
            reply.message = message
            reply.sender_type = 'coordinator'
            reply.sender_coordinator = coordinator_profile
            reply.sender_admin = None
            reply.sender_alumni = None
            reply.parent = None
            reply.save()
            message.status = 'sent'
            message.read_at = None
            message.save(update_fields=['status', 'read_at'])
            messages.success(request, 'Reply sent successfully.')
            return redirect('coordinator_view_message', message_id=message.id)
        else:
            messages.error(request, 'Please correct the errors below to send your reply.')
    
    context = {
        'message': message,
        'coordinator_user': request.user,
        'replies': replies,
        'reply_form': reply_form,
    }
    
    return render(request, 'coordinator_template/view_message.html', context)


@login_required
def register_alumni(request):
    """Register a new alumni (for coordinators and admins)"""
    if request.user.user_type not in ['1', '2']:  # Allow both Admin (1) and Coordinator (2)
        return redirect('login_page')
    
    if request.method == 'POST':
        form = AlumniRegistrationForm(request.POST)
        if form.is_valid():
            try:
                # Save the form which creates both user and alumni
                user = form.save()
                
                # Update user settings for coordinator/admin created alumni
                user.is_verified = True  # Auto-verify when created by admin/coordinator
                user.save()
                
                # Get the alumni record (should exist after form.save())
                try:
                    alumni = user.alumni
                    # Update alumni privacy level for coordinator/admin created alumni
                    alumni.privacy_level = 'limited'  # Default to limited privacy
                    alumni.save()
                    
                    messages.success(request, f'Citizens Secondary School alumni {user.get_full_name()} has been registered successfully with Student ID: {alumni.student_id}!')
                except Alumni.DoesNotExist:
                    # If alumni record doesn't exist, create it manually
                    alumni = Alumni.objects.create(
                        admin=user,
                        graduation_year=form.cleaned_data['graduation_year'],
                        degree=form.cleaned_data['degree'],
                        privacy_level='limited'
                    )
                    messages.success(request, f'Citizens Secondary School alumni {user.get_full_name()} has been registered successfully with Student ID: {alumni.student_id}!')
                
                return redirect('manage_alumni')
                
            except Exception as e:
                messages.error(request, f'Error creating alumni: {str(e)}')
                return render(request, 'coordinator_template/register_alumni.html', {'form': form})
    else:
        form = AlumniRegistrationForm()
    
    context = {
        'form': form,
    }
    
    return render(request, 'coordinator_template/register_alumni.html', context)


@login_required
def delete_alumni(request, alumni_id):
    """Delete an alumni (for coordinators and admins)"""
    if request.user.user_type not in ['1', '2']:  # Allow both Admin (1) and Coordinator (2)
        return redirect('login_page')
    
    alumni = get_object_or_404(Alumni, id=alumni_id)
    
    if request.method == 'POST':
        alumni_name = alumni.full_name
        # Delete the user account (this will cascade delete the alumni profile)
        alumni.admin.delete()
        messages.success(request, f'Citizens Secondary School alumni {alumni_name} has been deleted successfully!')
        return redirect('manage_alumni')
    
    context = {
        'alumni': alumni,
    }
    
    return render(request, 'coordinator_template/delete_alumni.html', context)


@login_required
def coordinator_export_alumni_excel(request, export_type='all'):
    """Export alumni data to Excel format - Coordinator access"""
    if request.user.user_type not in ['1', '2']:  # Admin or Coordinator
        return redirect('login_page')
    
    try:
        # Get all alumni with related data
        alumni_queryset = Alumni.objects.select_related(
            'admin', 'graduation_year', 'degree', 'current_company'
        ).all()
        
        # Apply filters if provided
        search_query = request.GET.get('search', '')
        graduation_year = request.GET.get('graduation_year', '')
        degree = request.GET.get('degree', '')
        
        if search_query:
            alumni_queryset = alumni_queryset.filter(
                Q(admin__first_name__icontains=search_query) |
                Q(admin__last_name__icontains=search_query) |
                Q(admin__email__icontains=search_query) |
                Q(student_id__icontains=search_query)
            )
        
        if graduation_year:
            alumni_queryset = alumni_queryset.filter(graduation_year_id=graduation_year)
        
        if degree:
            alumni_queryset = alumni_queryset.filter(degree_id=degree)
        
        # Export to Excel
        response = export_alumni_to_excel(alumni_queryset, export_type)
        
        # Log the export action
        messages.success(request, f'Successfully exported {alumni_queryset.count()} alumni records to Excel!')
        
        return response
        
    except Exception as e:
        messages.error(request, f'Error exporting alumni data: {str(e)}')
        return redirect('manage_alumni')


@login_required
def coordinator_export_alumni_by_year_excel(request, year_id):
    """Export alumni by graduation year to Excel - Coordinator access"""
    if request.user.user_type not in ['1', '2']:  # Admin or Coordinator
        return redirect('login_page')
    
    try:
        graduation_year = get_object_or_404(GraduationYear, id=year_id)
        response = export_alumni_by_graduation_year(graduation_year)
        
        messages.success(request, f'Successfully exported Class of {graduation_year.year} alumni to Excel!')
        return response
        
    except Exception as e:
        messages.error(request, f'Error exporting alumni data: {str(e)}')
        return redirect('manage_alumni')


@login_required
def coordinator_export_alumni_statistics_excel(request):
    """Export alumni statistics to Excel - Coordinator access"""
    if request.user.user_type not in ['1', '2']:  # Admin or Coordinator
        return redirect('login_page')
    
    try:
        response = export_alumni_statistics()
        
        messages.success(request, 'Successfully exported alumni statistics to Excel!')
        return response
        
    except Exception as e:
        messages.error(request, f'Error exporting statistics: {str(e)}')
        return redirect('coordinator_home')
