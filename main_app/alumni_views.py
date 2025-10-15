import json
from datetime import timedelta

from functools import wraps

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render, reverse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q, Count, Prefetch
from django.core.paginator import Paginator
from django.utils import timezone
from django.core.files.storage import default_storage
from django.conf import settings
from django.template.loader import render_to_string

from .models import *
from .models import Follow, FriendRequest, Friendship, Notification, CustomUser
from .forms import *


def alumni_profile_required(view_func):
    """Ensure the logged-in user has an associated alumni profile."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if request.user.user_type != '3':
            return redirect('login_page')

        try:
            request.alumni = request.user.alumni
        except Alumni.DoesNotExist:
            logout(request)
            messages.error(
                request,
                'Alumni profile not found. Please contact the alumni office to complete your registration.'
            )
            return redirect('login_page')

        return view_func(request, *args, **kwargs)

    return _wrapped


@login_required
@alumni_profile_required
def alumni_home(request):
    """COSA DASHBOARD"""
    alumni = request.alumni
    
    # Get dashboard statistics
    stats = {
        'total_alumni': Alumni.objects.filter(admin__is_verified=True).count(),
        'my_connections': Alumni.objects.filter(
            privacy_level__in=['public', 'limited'],
            admin__is_verified=True
        ).exclude(id=alumni.id).count(),
        'available_jobs': JobPosting.objects.filter(is_active=True).count(),
        'upcoming_events': Event.objects.filter(status='upcoming').count(),
        'my_applications': JobApplication.objects.filter(applicant=alumni).count(),
        'my_registrations': EventRegistration.objects.filter(alumni=alumni).count(),
    }
    
    # Get recent activities
    recent_jobs = JobPosting.objects.filter(is_active=True).order_by('-created_at')[:5]
    upcoming_events = Event.objects.filter(
        status='upcoming',
        start_date__gt=timezone.now()
    ).order_by('start_date')[:5]
    recent_news = News.objects.filter(
        is_published=True,
        publish_date__lte=timezone.now()
    ).order_by('-publish_date')[:3]
    
    # Get notifications
    notifications = NotificationAlumni.objects.filter(
        alumni=alumni,
        is_read=False
    ).order_by('-created_at')[:5]
    
    context = {
        'alumni': alumni,
        'stats': stats,
        'recent_jobs': recent_jobs,
        'upcoming_events': upcoming_events,
        'recent_news': recent_news,
        'notifications': notifications,
    }
    
    return render(request, 'alumni_template/alumni_home.html', context)


@login_required
@alumni_profile_required
def alumni_profile(request):
    """Alumni profile management"""
    alumni = request.alumni
    
    if request.method == 'POST':
        # Handle profile picture upload separately
        if 'profile_pic' in request.FILES:
            alumni.admin.profile_pic = request.FILES['profile_pic']
            alumni.admin.save()
            messages.success(request, 'Profile picture updated successfully!')
            return redirect('alumni_profile')
        
        # Handle profile form
        form = AlumniProfileForm(request.POST, instance=alumni)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('alumni_profile')
    else:
        form = AlumniProfileForm(instance=alumni)
    
    context = {
        'form': form,
        'alumni': alumni,
    }
    
    return render(request, 'alumni_template/alumni_profile.html', context)


@login_required
@alumni_profile_required
def alumni_directory(request):
    """COSA Directory for logged-in users"""
    context = _build_alumni_directory_context(request)
    return render(request, 'alumni_template/alumni_directory.html', context)


def _build_alumni_directory_context(request):
    """Helper to build context for alumni directory listings."""
    form = AlumniSearchForm(request.GET or None)
    alumni_list = Alumni.objects.filter(
        admin__is_verified=True
    ).select_related(
        'admin', 'degree', 'graduation_year', 'current_company'
    )
    
    # Exclude the logged-in alumni if available
    if hasattr(request, 'alumni'):
        alumni_list = alumni_list.exclude(id=request.alumni.id)
    
    # Apply privacy filters based on user's access level
    alumni_list = alumni_list.filter(
        Q(privacy_level='public') |
        Q(privacy_level='limited', admin__is_verified=True)
    )
    
    # Apply search filters
    if form.is_valid():
        search = form.cleaned_data.get('search')
        if search:
            alumni_list = alumni_list.filter(
                Q(admin__first_name__icontains=search) |
                Q(admin__last_name__icontains=search) |
                Q(current_company__name__icontains=search) |
                Q(skills__icontains=search) |
                Q(industry__icontains=search)
            )
        
        graduation_year = form.cleaned_data.get('graduation_year')
        if graduation_year:
            alumni_list = alumni_list.filter(graduation_year__year=graduation_year)
        
        degree = form.cleaned_data.get('degree')
        if degree:
            alumni_list = alumni_list.filter(degree__degree_type=degree)
        
        if form.cleaned_data.get('is_mentor'):
            alumni_list = alumni_list.filter(is_mentor=True)
        
        if form.cleaned_data.get('willing_to_hire'):
            alumni_list = alumni_list.filter(willing_to_hire=True)
    
    # Pagination
    paginator = Paginator(alumni_list, settings.ALUMNI_PER_PAGE)
    page_number = request.GET.get('page')
    alumni = paginator.get_page(page_number)
    
    return {
        'alumni': alumni,
        'form': form,
        'total_count': alumni_list.count(),
    }


@login_required
@alumni_profile_required
def alumni_directory_data(request):
    """AJAX endpoint for alumni directory filters."""
    context = _build_alumni_directory_context(request)
    html = render_to_string(
        'alumni_template/partials/alumni_directory_results.html',
        context,
        request=request
    )
    
    alumni_page = context['alumni']
    
    return JsonResponse({
        'html': html,
        'total_count': context['total_count'],
        'page_count': alumni_page.paginator.num_pages if alumni_page.paginator else 1,
        'page_number': alumni_page.number,
    })


@login_required
@alumni_profile_required
def alumni_detail(request, alumni_id):
    """View individual alumni profile"""
    alumni = get_object_or_404(Alumni, id=alumni_id, admin__is_verified=True)

    # Check privacy permissions
    if alumni.privacy_level == 'private' and alumni != request.alumni:
        messages.error(request, 'This profile is private.')
        return redirect('alumni_directory')

    context = {
        'profile_alumni': alumni,
        'can_contact': alumni.allow_contact and alumni != request.alumni,
    }
    
    return render(request, 'alumni_template/alumni_detail.html', context)


# =========================
# Social: Follow & Friends
# =========================

@login_required
def follow_toggle(request, user_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)
    actor = request.user
    try:
        target = CustomUser.objects.get(id=user_id)
    except CustomUser.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'User not found'}, status=404)
    if actor.id == target.id:
        return JsonResponse({'status': 'error', 'message': 'Cannot follow yourself'}, status=400)

    existing = Follow.objects.filter(follower=actor, following=target).first()
    if existing:
        existing.delete()
        return JsonResponse({'status': 'success', 'action': 'unfollowed'})

    Follow.objects.create(follower=actor, following=target)
    Notification.objects.create(
        recipient=target,
        sender=actor,
        notification_type='follow',
        message=f"{actor.first_name or actor.email} started following you."
    )
    return JsonResponse({'status': 'success', 'action': 'followed'})


@login_required
def send_friend_request(request, user_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)
    actor = request.user
    try:
        target = CustomUser.objects.get(id=user_id)
    except CustomUser.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'User not found'}, status=404)
    if actor.id == target.id:
        return JsonResponse({'status': 'error', 'message': 'Cannot add yourself'}, status=400)

    # Already friends?
    if _are_friends(actor, target):
        return JsonResponse({'status': 'error', 'message': 'Already friends'}, status=400)

    fr, created = FriendRequest.objects.get_or_create(sender=actor, receiver=target, defaults={'status': 'pending'})
    if not created and fr.status == 'pending':
        return JsonResponse({'status': 'success', 'action': 'already_pending'})
    if not created and fr.status in ('rejected', 'cancelled'):
        fr.status = 'pending'
        fr.save(update_fields=['status', 'updated_at'])

    Notification.objects.create(
        recipient=target,
        sender=actor,
        notification_type='friend_request',
        message=f"{actor.first_name or actor.email} sent you a friend request."
    )
    return JsonResponse({'status': 'success', 'action': 'requested'})


@login_required
def respond_friend_request(request, request_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)
    action = request.POST.get('action')  # 'accept' or 'reject'
    try:
        fr = FriendRequest.objects.select_related('sender', 'receiver').get(id=request_id, receiver=request.user)
    except FriendRequest.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Request not found'}, status=404)

    if fr.status != 'pending':
        return JsonResponse({'status': 'error', 'message': 'Request already processed'}, status=400)

    if action == 'accept':
        fr.status = 'accepted'
        fr.save(update_fields=['status', 'updated_at'])

        # Create friendship (ordered pair)
        _ensure_friendship(fr.sender, fr.receiver)

        Notification.objects.create(
            recipient=fr.sender,
            sender=fr.receiver,
            notification_type='friend_acceptance',
            message=f"{fr.receiver.first_name or fr.receiver.email} accepted your friend request."
        )
        return JsonResponse({'status': 'success', 'action': 'accepted'})

    if action == 'reject':
        fr.status = 'rejected'
        fr.save(update_fields=['status', 'updated_at'])
        return JsonResponse({'status': 'success', 'action': 'rejected'})

    return JsonResponse({'status': 'error', 'message': 'Invalid action'}, status=400)


def _ensure_friendship(u1, u2):
    # Order users by id to maintain uniqueness
    if u1.id > u2.id:
        u1, u2 = u2, u1
    Friendship.objects.get_or_create(user1=u1, user2=u2)


def _are_friends(u1, u2):
    a, b = (u1, u2) if u1.id < u2.id else (u2, u1)
    return Friendship.objects.filter(user1=a, user2=b).exists()


@login_required
def list_followers(request, user_id=None):
    user = request.user if not user_id else get_object_or_404(CustomUser, id=user_id)
    followers = Follow.objects.filter(following=user).select_related('follower')
    data = [{
        'id': f.follower.id,
        'name': f.follower.get_full_name() or f.follower.email,
        'email': f.follower.email,
    } for f in followers]
    return JsonResponse({'results': data})


@login_required
def list_following(request, user_id=None):
    user = request.user if not user_id else get_object_or_404(CustomUser, id=user_id)
    following = Follow.objects.filter(follower=user).select_related('following')
    data = [{
        'id': f.following.id,
        'name': f.following.get_full_name() or f.following.email,
        'email': f.following.email,
    } for f in following]
    return JsonResponse({'results': data})


@login_required
def list_friends(request, user_id=None):
    user = request.user if not user_id else get_object_or_404(CustomUser, id=user_id)
    friendships = Friendship.objects.filter(models.Q(user1=user) | models.Q(user2=user)).select_related('user1', 'user2')
    results = []
    for fs in friendships:
        friend = fs.user2 if fs.user1_id == user.id else fs.user1
        results.append({
            'id': friend.id,
            'name': friend.get_full_name() or friend.email,
            'email': friend.email,
        })
    return JsonResponse({'results': results})


@login_required
def notifications_feed(request):
    """Return unread and all notifications for the authenticated user."""
    unread_only = request.GET.get('unread') == '1'
    qs = Notification.objects.filter(recipient=request.user).select_related('sender')
    if unread_only:
        qs = qs.filter(is_read=False)
    qs = qs.order_by('-created_at')[:100]
    data = [{
        'id': n.id,
        'type': n.notification_type,
        'message': n.message,
        'sender': {
            'id': n.sender.id,
            'name': n.sender.get_full_name() or n.sender.email,
            'email': n.sender.email,
        },
        'is_read': n.is_read,
        'created_at': n.created_at.isoformat(),
    } for n in qs]
    return JsonResponse({'results': data})


@login_required
def mark_notification_read(request, notification_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)
    try:
        n = Notification.objects.get(id=notification_id, recipient=request.user)
    except Notification.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Not found'}, status=404)
    if not n.is_read:
        n.is_read = True
        n.save(update_fields=['is_read', 'updated_at'])
    return JsonResponse({'status': 'success'})


# -------------------------
# Simple pages consuming AJAX
# -------------------------

@login_required
@alumni_profile_required
def friends_page(request):
    return render(request, 'alumni_template/friends.html')


@login_required
@alumni_profile_required
def followers_page(request):
    return render(request, 'alumni_template/followers.html')


@login_required
@alumni_profile_required
def following_page(request):
    return render(request, 'alumni_template/following.html')


@login_required
@alumni_profile_required
def job_board(request):
    """Job board for alumni"""
    jobs = JobPosting.objects.filter(is_active=True).select_related(
        'company', 'posted_by'
    ).order_by('-created_at')
    
    # Filter options
    job_type = request.GET.get('job_type')
    if job_type:
        jobs = jobs.filter(job_type=job_type)
    
    location = request.GET.get('location')
    if location:
        jobs = jobs.filter(location__icontains=location)
    
    experience_level = request.GET.get('experience_level')
    if experience_level:
        jobs = jobs.filter(experience_level=experience_level)
    
    search = request.GET.get('search')
    if search:
        jobs = jobs.filter(
            Q(title__icontains=search) |
            Q(company__name__icontains=search) |
            Q(description__icontains=search)
        )
    
    # Pagination
    paginator = Paginator(jobs, settings.JOBS_PER_PAGE)
    page_number = request.GET.get('page')
    job_list = paginator.get_page(page_number)
    
    # Get user's applications
    user_applications = JobApplication.objects.filter(
        applicant=request.alumni
    ).values_list('job_id', flat=True)
    
    context = {
        'jobs': job_list,
        'job_types': JobPosting.JOB_TYPES,
        'experience_levels': JobPosting.EXPERIENCE_LEVELS,
        'user_applications': list(user_applications),
    }
    
    return render(request, 'alumni_template/job_board.html', context)


@login_required
@alumni_profile_required
def post_job(request):
    """Post a new job opportunity - Simplified version"""
    companies = Company.objects.all()
    
    # If no companies exist, create a default one
    if not companies.exists():
        default_company = Company.objects.create(
            name="General Company",
            description="Default company for job postings",
            industry="Various",
            size="Unknown",
            founded_year=2000,
            website="",
            email="",
            phone="",
            address="",
            created_by=None
        )
        companies = Company.objects.all()
    
    if request.method == 'POST':
        form = JobPostingForm(request.POST)
        if form.is_valid():
            try:
                job = form.save(commit=False)
                
                # Set defaults for simplified form
                job.posted_by = request.alumni
                job.requirements = "Requirements will be discussed during interview process."
                job.experience_level = 'mid'  # Default to mid-level
                job.currency = 'USD'
                
                job.save()
                messages.success(request, '🎉 Job posted successfully! Alumni can now see and apply for this opportunity.')
                return redirect('job_board')
            except Exception as e:
                messages.error(request, f'Error saving job: {str(e)}')
                print(f"Error saving job: {str(e)}")
        else:
            # Show simplified error messages
            if 'title' in form.errors:
                messages.error(request, 'Please provide a clear job title')
            if 'company' in form.errors:
                messages.error(request, 'Please select a company')
            if 'description' in form.errors:
                messages.error(request, 'Please describe the job role')
            if 'job_type' in form.errors:
                messages.error(request, 'Please select a job type')
            if 'location' in form.errors:
                messages.error(request, 'Please specify the job location')
    else:
        form = JobPostingForm()
    
    context = {
        'form': form,
        'companies': companies,
        'total_companies': companies.count(),
    }
    
    return render(request, 'alumni_template/post_job_simple.html', context)


@login_required
@alumni_profile_required
def apply_job(request, job_id):
    """Apply for a job"""
    job = get_object_or_404(JobPosting, id=job_id, is_active=True)
    alumni = request.alumni
    
    # Check if already applied
    if JobApplication.objects.filter(job=job, applicant=alumni).exists():
        messages.warning(request, 'You have already applied for this job.')
        return redirect('job_detail', job_id=job.id)
    
    if request.method == 'POST':
        cover_letter = request.POST.get('cover_letter', '')
        resume = request.FILES.get('resume')
        
        JobApplication.objects.create(
            job=job,
            applicant=alumni,
            cover_letter=cover_letter,
            resume=resume
        )
        
        messages.success(request, 'Application submitted successfully!')
        return redirect('job_detail', job_id=job.id)
    
    context = {
        'job': job,
    }
    
    return render(request, 'alumni_template/apply_job.html', context)


@login_required
@alumni_profile_required
def my_applications(request):
    """View user's job applications"""
    applications = JobApplication.objects.filter(
        applicant=request.alumni
    ).select_related('job', 'job__company').order_by('-application_date')
    
    # Pagination
    paginator = Paginator(applications, 20)
    page_number = request.GET.get('page')
    application_list = paginator.get_page(page_number)
    
    context = {
        'applications': application_list,
    }
    
    return render(request, 'alumni_template/my_applications.html', context)


@login_required
@alumni_profile_required
def events(request):
    """View events"""
    events = Event.objects.filter(
        status='upcoming'
    ).select_related('organizer').order_by('start_date')
    
    # Filter by event type
    event_type = request.GET.get('event_type')
    if event_type:
        events = events.filter(event_type=event_type)
    
    # Pagination
    paginator = Paginator(events, settings.EVENTS_PER_PAGE)
    page_number = request.GET.get('page')
    event_list = paginator.get_page(page_number)
    
    # Get user's registrations
    user_registrations = EventRegistration.objects.filter(
        alumni=request.alumni
    ).values_list('event_id', flat=True)
    
    context = {
        'events': event_list,
        'event_types': Event.EVENT_TYPES,
        'user_registrations': list(user_registrations),
    }
    
    return render(request, 'alumni_template/events.html', context)


@login_required
@alumni_profile_required
def register_event(request, event_id):
    """Register for an event"""
    event = get_object_or_404(Event, id=event_id)
    alumni = request.alumni
    
    # Check if already registered
    if EventRegistration.objects.filter(event=event, alumni=alumni).exists():
        messages.warning(request, 'You are already registered for this event.')
        return redirect('event_detail', event_id=event.id)
    
    # Check if registration is open
    if not event.is_registration_open:
        messages.error(request, 'Registration for this event is closed.')
        return redirect('event_detail', event_id=event.id)
    
    if request.method == 'POST':
        form = EventRegistrationForm(request.POST)
        if form.is_valid():
            registration = EventRegistration.objects.create(
                event=event,
                alumni=alumni,
                special_requirements=form.cleaned_data['special_requirements'],
                status='pending' if event.requires_approval else 'confirmed'
            )
            
            if event.requires_approval:
                messages.success(request, 'Registration submitted! Awaiting approval.')
            else:
                messages.success(request, 'Successfully registered for the event!')
            
            return redirect('event_detail', event_id=event.id)
    else:
        form = EventRegistrationForm()
    
    context = {
        'event': event,
        'form': form,
    }
    
    return render(request, 'alumni_template/register_event.html', context)


@login_required
@alumni_profile_required
def my_events(request):
    """View user's event registrations"""
    registrations = EventRegistration.objects.filter(
        alumni=request.alumni
    ).select_related('event').order_by('-registration_date')
    
    context = {
        'registrations': registrations,
        'today': timezone.now().date(),
        'cancel_statuses': ('confirmed', 'pending'),
    }
    
    return render(request, 'alumni_template/my_events.html', context)


@login_required
@alumni_profile_required
def messages_inbox(request):
    """View messages inbox"""
    alumni = request.alumni

    # Mark freshly received messages as delivered once inbox is opened
    Message.objects.filter(
        recipient=alumni,
        status='sent'
    ).update(status='delivered')

    # Get all messages sent to this alumni (from any sender type)
    messages_list = Message.objects.filter(
        recipient=alumni
    ).select_related(
        'sender_alumni', 'sender_alumni__admin',
        'sender_admin', 'sender_admin__admin',
        'sender_coordinator', 'sender_coordinator__admin'
    ).order_by('-created_at')
    
    # Pagination
    paginator = Paginator(messages_list, 20)
    page_number = request.GET.get('page')
    message_list = paginator.get_page(page_number)
    
    context = {
        'messages': message_list,
    }

    return render(request, 'alumni_template/messages_inbox.html', context)


@login_required
@alumni_profile_required
def messages_sent(request):
    """List messages the alumni has sent."""
    sent_messages = Message.objects.filter(
        sender_type='alumni',
        sender_alumni=request.alumni
    ).select_related(
        'recipient', 'recipient__admin'
    ).order_by('-created_at')

    paginator = Paginator(sent_messages, 20)
    page_number = request.GET.get('page')
    message_list = paginator.get_page(page_number)

    edit_window_minutes = 10
    edit_window = timedelta(minutes=edit_window_minutes)
    now = timezone.now()
    for msg in message_list:
        msg.can_edit = (now - msg.created_at) <= edit_window
        msg.edit_deadline = msg.created_at + edit_window

    context = {
        'messages': message_list,
        'edit_window_minutes': edit_window_minutes,
    }

    return render(request, 'alumni_template/messages_sent.html', context)


@login_required
@alumni_profile_required
def delete_message(request, message_id):
    if request.method != 'POST':
        return redirect('messages_inbox')

    message_obj = get_object_or_404(
        Message,
        id=message_id,
        recipient=request.alumni
    )
    message_obj.delete()
    messages.success(request, 'Message deleted.')
    return redirect('messages_inbox')


@login_required
@alumni_profile_required
def bulk_delete_messages(request):
    if request.method != 'POST':
        return redirect('messages_inbox')

    ids = request.POST.getlist('message_ids')
    if ids:
        Message.objects.filter(
            id__in=ids,
            recipient=request.alumni
        ).delete()
        messages.success(request, 'Selected messages deleted.')
    else:
        messages.info(request, 'No messages selected.')
    return redirect('messages_inbox')


@login_required
@alumni_profile_required
def edit_message(request, message_id):

    message_obj = get_object_or_404(
        Message,
        id=message_id,
        sender_type='alumni',
        sender_alumni=request.alumni
    )

    edit_window = timedelta(minutes=10)
    if timezone.now() - message_obj.created_at > edit_window:
        messages.error(request, 'You can only edit a message within 10 minutes of sending.')
        return redirect('messages_sent')

    if request.method == 'POST':
        form = MessageEditForm(request.POST, request.FILES, instance=message_obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'Message updated successfully.')
            return redirect('messages_sent')
    else:
        form = MessageEditForm(instance=message_obj)

    context = {
        'form': form,
        'message_obj': message_obj,
        'deadline': message_obj.created_at + edit_window,
    }
    return render(request, 'alumni_template/edit_message.html', context)


@login_required
@alumni_profile_required
def send_message(request, recipient_id=None):
    """Send a message to another alumni"""
    recipient = None
    if recipient_id:
        recipient = get_object_or_404(Alumni, id=recipient_id, allow_contact=True)
    
    if request.method == 'POST':
        form = MessageForm(request.POST, request.FILES)
        if form.is_valid():
            message = form.save(commit=False)
            message.sender_type = 'alumni'
            message.sender_alumni = request.alumni
            message.save()
            messages.success(request, 'Message sent successfully!')
            return redirect('messages_inbox')
    else:
        initial_data = {}
        if recipient:
            initial_data['recipient'] = recipient
        form = MessageForm(initial=initial_data)
    
    context = {
        'form': form,
        'recipient': recipient,
    }
    
    return render(request, 'alumni_template/send_message.html', context)


@login_required
@alumni_profile_required
def view_message(request, message_id):
    """View a specific message"""
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
        recipient=request.alumni
    )
    
    # Mark as read
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
            reply.sender_type = 'alumni'
            reply.sender_alumni = request.alumni
            reply.sender_admin = None
            reply.sender_coordinator = None
            reply.parent = None  # reserved for future threaded replies
            reply.save()
            message.status = 'delivered'
            message.read_at = None
            message.save(update_fields=['status', 'read_at'])
            messages.success(request, 'Reply sent successfully.')
            return redirect('view_message', message_id=message.id)
        else:
            messages.error(request, 'Please correct the errors below to send your reply.')
    
    context = {
        'message': message,
        'replies': replies,
        'reply_form': reply_form,
    }
    
    return render(request, 'alumni_template/view_message.html', context)


@login_required
@alumni_profile_required
def alumni_feedback(request):
    """Submit feedback"""
    if request.method == 'POST':
        form = FeedbackAlumniForm(request.POST)
        if form.is_valid():
            feedback = form.save(commit=False)
            feedback.alumni = request.alumni
            feedback.save()
            messages.success(request, 'Feedback submitted successfully!')
            return redirect('alumni_home')
    else:
        form = FeedbackAlumniForm()
    
    context = {
        'form': form,
    }
    
    return render(request, 'alumni_template/feedback.html', context)


@login_required
@alumni_profile_required
def notifications(request):
    """View notifications"""
    notifications_list = NotificationAlumni.objects.filter(
        alumni=request.alumni
    ).order_by('-created_at')
    
    # Mark all as read
    notifications_list.filter(is_read=False).update(
        is_read=True,
        read_at=timezone.now()
    )
    
    # Pagination
    paginator = Paginator(notifications_list, 20)
    page_number = request.GET.get('page')
    notification_list = paginator.get_page(page_number)
    
    context = {
        'notifications': notification_list,
    }
    
    return render(request, 'alumni_template/notifications.html', context)


@login_required
@alumni_profile_required
def delete_notification(request, notification_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

    notification = get_object_or_404(
        NotificationAlumni,
        id=notification_id,
        alumni=request.alumni
    )
    notification.delete()
    return JsonResponse({'status': 'success'})


@csrf_exempt
def alumni_fcmtoken(request):
    """Update FCM token for push notifications"""
    user = request.user
    if not user.is_authenticated or getattr(user, 'user_type', None) != '3':
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'})

    try:
        user.alumni
    except Alumni.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Alumni profile missing'}, status=400)

    if request.method == 'POST':
        fcm_token = request.POST.get('fcm_token')
        if fcm_token:
            request.user.fcm_token = fcm_token
            request.user.save()
            return JsonResponse({'status': 'success'})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})
