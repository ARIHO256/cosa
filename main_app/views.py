import json
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render, reverse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
from django.core.paginator import Paginator
from django.utils import timezone
from django.template.loader import render_to_string

from .EmailBackend import EmailBackend
from .models import *
from .forms import AlumniRegistrationForm, AlumniSearchForm, CommentForm


def login_page(request):
    """Main login page forCOSA management System"""
    if request.user.is_authenticated:
        if request.user.user_type == '1':
            return redirect(reverse("admin_home"))
        elif request.user.user_type == '2':
            return redirect(reverse("coordinator_home"))
        else:
            return redirect(reverse("alumni_home"))
    return render(request, 'main_app/login.html')


def doLogin(request, **kwargs):
    """Handle user authentication"""
    if request.method != 'POST':
        return HttpResponse("<h4>Access Denied</h4>")
    else:
        # Authenticate
        user = authenticate(
            request,
            username=request.POST.get('email'),
            password=request.POST.get('password')
        )
        if user is not None:
            # Check if user account is suspended
            if not user.can_login():
                # Log them in but redirect to suspension notice
                login(request, user, backend='main_app.EmailBackend.EmailBackend')
                return redirect('suspension_notice')
            
            # Check if user is verified (for alumni)
            if user.user_type == '3' and not user.is_verified:
                # Log them in but redirect to pending approval page
                login(request, user, backend='main_app.EmailBackend.EmailBackend')
                return redirect('pending_approval')
            
            # Specify the backend when logging in
            login(request, user, backend='main_app.EmailBackend.EmailBackend')
            
            if user.user_type == '1':
                return redirect(reverse("admin_home"))
            elif user.user_type == '2':
                return redirect(reverse("coordinator_home"))
            else:
                return redirect(reverse("alumni_home"))
        else:
            messages.error(request, "Invalid email or password")
            return redirect("/")


def logout_user(request):
    """Handle user logout"""
    if request.user is not None:
        logout(request)
    return redirect("/")


def alumni_registration(request):
    """Alumni self-registration page"""
    if request.user.is_authenticated:
        if request.user.user_type == '1':
            return redirect('admin_home')
        if request.user.user_type == '2':
            return redirect('coordinator_home')
        return redirect('alumni_home')
    
    if request.method == 'POST':
        form = AlumniRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Your registration has been received. Please check your email once an administrator verifies your account."
            )
            return redirect('login_page')
    else:
        form = AlumniRegistrationForm()
    
    setup_needed = not (
        GraduationYear.objects.filter(is_active=True).exists() and
        Degree.objects.filter(is_active=True).exists()
    )
    
    context = {
        'form': form,
        'setup_needed': setup_needed,
    }
    
    return render(request, 'registration/alumni_register.html', context)


def _build_public_directory_context(request):
    """Prepare filtered queryset, pagination, and totals for the public directory."""
    form = AlumniSearchForm(request.GET or None)
    can_view = request.user.is_authenticated

    if can_view:
        alumni_qs = Alumni.objects.filter(
            privacy_level__in=['public', 'limited'],
            admin__is_verified=True
        ).select_related('admin', 'degree', 'graduation_year', 'current_company')
    else:
        alumni_qs = Alumni.objects.none()
    
    if can_view and form.is_valid():
        search = form.cleaned_data.get('search')
        if search:
            alumni_qs = alumni_qs.filter(
                Q(admin__first_name__icontains=search) |
                Q(admin__last_name__icontains=search) |
                Q(current_company__name__icontains=search) |
                Q(skills__icontains=search) |
                Q(industry__icontains=search)
            )
        
        graduation_year = form.cleaned_data.get('graduation_year')
        if graduation_year:
            alumni_qs = alumni_qs.filter(graduation_year__year=graduation_year)
        
        degree = form.cleaned_data.get('degree')
        if degree:
            alumni_qs = alumni_qs.filter(degree__degree_type=degree)
        
        if form.cleaned_data.get('is_mentor'):
            alumni_qs = alumni_qs.filter(is_mentor=True)
        
        if form.cleaned_data.get('willing_to_hire'):
            alumni_qs = alumni_qs.filter(willing_to_hire=True)
    
    total_count = alumni_qs.count()
    paginator = Paginator(alumni_qs, 24)
    page_number = request.GET.get('page')
    alumni_page = paginator.get_page(page_number)
    
    return {
        'form': form,
        'alumni': alumni_page,
        'total_count': total_count,
        'can_view_directory': can_view,
    }


def public_alumni_directory(request):
    """Public COSA Directory with search functionality"""
    context = _build_public_directory_context(request)
    return render(request, 'main_app/public_alumni_directory.html', context)


def public_alumni_directory_data(request):
    """AJAX endpoint for real-time directory filtering."""
    context = _build_public_directory_context(request)
    html = render_to_string(
        'main_app/partials/public_alumni_directory_results.html',
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


def public_job_board(request):
    """Public job board showing active job postings"""
    jobs = JobPosting.objects.filter(
        is_active=True,
        application_deadline__gt=timezone.now()
    ).select_related('company', 'posted_by').order_by('-created_at')
    
    # Filter by job type if specified
    job_type = request.GET.get('job_type')
    if job_type:
        jobs = jobs.filter(job_type=job_type)
    
    # Filter by location if specified
    location = request.GET.get('location')
    if location:
        jobs = jobs.filter(location__icontains=location)
    
    # Filter by experience level if specified
    experience_level = request.GET.get('experience_level')
    if experience_level:
        jobs = jobs.filter(experience_level=experience_level)
    
    # Pagination
    paginator = Paginator(jobs, 20)  # Show 20 jobs per page
    page_number = request.GET.get('page')
    job_list = paginator.get_page(page_number)
    
    context = {
        'jobs': job_list,
        'job_types': JobPosting.JOB_TYPES,
        'experience_levels': JobPosting.EXPERIENCE_LEVELS,
    }
    
    return render(request, 'main_app/public_job_board.html', context)


def public_events(request):
    """Public events listing"""
    if request.user.is_authenticated:
        if request.user.user_type == '3':
            return redirect('events')
        if request.user.user_type == '2':
            return redirect('manage_events')
        if request.user.user_type == '1':
            return redirect('admin_home')

    events = Event.objects.filter(
        status='upcoming',
        start_date__gt=timezone.now()
    ).select_related('organizer').order_by('start_date')
    
    # Filter by event type if specified
    event_type = request.GET.get('event_type')
    if event_type:
        events = events.filter(event_type=event_type)
    
    # Pagination
    paginator = Paginator(events, 12)  # Show 12 events per page
    page_number = request.GET.get('page')
    event_list = paginator.get_page(page_number)
    
    context = {
        'events': event_list,
        'event_types': Event.EVENT_TYPES,
    }
    
    return render(request, 'main_app/public_events.html', context)


def public_news(request):
    """Public news and announcements"""
    news_list = News.objects.filter(
        is_published=True,
        publish_date__lte=timezone.now()
    ).select_related('author').order_by('-publish_date')
    
    # Filter by category if specified
    category = request.GET.get('category')
    if category:
        news_list = news_list.filter(category=category)
    
    # Pagination
    paginator = Paginator(news_list, 10)  # Show 10 news items per page
    page_number = request.GET.get('page')
    news = paginator.get_page(page_number)
    
    # Get featured news
    featured_news = News.objects.filter(
        is_published=True,
        is_featured=True,
        publish_date__lte=timezone.now()
    ).order_by('-publish_date')[:3]
    
    context = {
        'news': news,
        'featured_news': featured_news,
        'categories': News.NEWS_CATEGORIES,
    }
    
    return render(request, 'main_app/public_news.html', context)


def news_detail(request, slug):
    """Individual news article detail"""
    article = get_object_or_404(News, slug=slug, is_published=True)
    
    # Get related news
    related_news = News.objects.filter(
        category=article.category,
        is_published=True
    ).exclude(id=article.id).order_by('-publish_date')[:3]
    
    # Like and comment functionality
    user_liked = False
    total_likes = 0
    comments = []
    total_comments = 0
    
    if request.user.is_authenticated:
        # Check if user liked this article
        user_liked = Like.objects.filter(
            user=request.user,
            content_type='news',
            object_id=article.id
        ).exists()
    
    # Get total likes
    total_likes = Like.objects.filter(
        content_type='news',
        object_id=article.id
    ).count()
    
    # Get comments
    comments = Comment.objects.filter(
        content_type='news',
        object_id=article.id,
        is_approved=True,
        parent__isnull=True  # Only top-level comments
    ).select_related('user').prefetch_related('replies__user').order_by('-created_at')
    
    # Add like status to comments and replies
    for comment in comments:
        if request.user.is_authenticated:
            comment.user_liked = CommentLike.objects.filter(
                user=request.user,
                comment=comment
            ).exists()
            
            # Add like status to replies
            for reply in comment.replies.all():
                reply.user_liked = CommentLike.objects.filter(
                    user=request.user,
                    comment=reply
                ).exists()
        else:
            comment.user_liked = False
            # Add like status to replies
            for reply in comment.replies.all():
                reply.user_liked = False
    
    total_comments = Comment.objects.filter(
        content_type='news',
        object_id=article.id,
        is_approved=True
    ).count()
    
    context = {
        'article': article,
        'related_news': related_news,
        'content_type': 'news',
        'object_id': article.id,
        'user_liked': user_liked,
        'total_likes': total_likes,
        'comments': comments,
        'total_comments': total_comments,
    }
    
    # Debug: Print context data
    print(f"News Detail Context: content_type={context['content_type']}, object_id={context['object_id']}, total_likes={context['total_likes']}, total_comments={context['total_comments']}")
    
    return render(request, 'main_app/news_detail.html', context)


def job_detail(request, job_id):
    """Individual job posting detail"""
    job = get_object_or_404(JobPosting, id=job_id, is_active=True)
    
    # Check if user has already applied
    has_applied = False
    if request.user.is_authenticated and hasattr(request.user, 'alumni'):
        has_applied = JobApplication.objects.filter(
            job=job,
            applicant=request.user.alumni
        ).exists()
    
    # Like and comment functionality
    user_liked = False
    total_likes = 0
    comments = []
    total_comments = 0
    
    if request.user.is_authenticated:
        # Check if user liked this job
        user_liked = Like.objects.filter(
            user=request.user,
            content_type='job',
            object_id=job.id
        ).exists()
    
    # Get total likes
    total_likes = Like.objects.filter(
        content_type='job',
        object_id=job.id
    ).count()
    
    # Get comments
    comments = Comment.objects.filter(
        content_type='job',
        object_id=job.id,
        is_approved=True,
        parent__isnull=True  # Only top-level comments
    ).select_related('user').prefetch_related('replies__user').order_by('-created_at')
    
    # Add like status to comments and replies
    for comment in comments:
        if request.user.is_authenticated:
            comment.user_liked = CommentLike.objects.filter(
                user=request.user,
                comment=comment
            ).exists()
            
            # Add like status to replies
            for reply in comment.replies.all():
                reply.user_liked = CommentLike.objects.filter(
                    user=request.user,
                    comment=reply
                ).exists()
        else:
            comment.user_liked = False
            # Add like status to replies
            for reply in comment.replies.all():
                reply.user_liked = False
    
    total_comments = Comment.objects.filter(
        content_type='job',
        object_id=job.id,
        is_approved=True
    ).count()
    
    context = {
        'job': job,
        'has_applied': has_applied,
        'content_type': 'job',
        'object_id': job.id,
        'user_liked': user_liked,
        'total_likes': total_likes,
        'comments': comments,
        'total_comments': total_comments,
    }
    
    # Debug: Print context data
    print(f"Job Detail Context: content_type={context['content_type']}, object_id={context['object_id']}, total_likes={context['total_likes']}, total_comments={context['total_comments']}")
    
    return render(request, 'main_app/job_detail.html', context)


def event_detail(request, event_id):
    """Individual event detail"""
    event = get_object_or_404(Event, id=event_id)
    
    # Check if user has already registered
    has_registered = False
    if request.user.is_authenticated and hasattr(request.user, 'alumni'):
        has_registered = EventRegistration.objects.filter(
            event=event,
            alumni=request.user.alumni
        ).exists()
    
    # Like and comment functionality
    user_liked = False
    total_likes = 0
    comments = []
    total_comments = 0
    
    if request.user.is_authenticated:
        # Check if user liked this event
        user_liked = Like.objects.filter(
            user=request.user,
            content_type='event',
            object_id=event.id
        ).exists()
    
    # Get total likes
    total_likes = Like.objects.filter(
        content_type='event',
        object_id=event.id
    ).count()
    
    # Get comments
    comments = Comment.objects.filter(
        content_type='event',
        object_id=event.id,
        is_approved=True,
        parent__isnull=True  # Only top-level comments
    ).select_related('user').prefetch_related('replies__user').order_by('-created_at')
    
    # Add like status to comments and replies
    for comment in comments:
        if request.user.is_authenticated:
            comment.user_liked = CommentLike.objects.filter(
                user=request.user,
                comment=comment
            ).exists()
            
            # Add like status to replies
            for reply in comment.replies.all():
                reply.user_liked = CommentLike.objects.filter(
                    user=request.user,
                    comment=reply
                ).exists()
        else:
            comment.user_liked = False
            # Add like status to replies
            for reply in comment.replies.all():
                reply.user_liked = False
    
    total_comments = Comment.objects.filter(
        content_type='event',
        object_id=event.id,
        is_approved=True
    ).count()
    
    context = {
        'event': event,
        'has_registered': has_registered,
        'content_type': 'event',
        'object_id': event.id,
        'user_liked': user_liked,
        'total_likes': total_likes,
        'comments': comments,
        'total_comments': total_comments,
    }
    
    # Debug: Print context data
    print(f"Event Detail Context: content_type={context['content_type']}, object_id={context['object_id']}, total_likes={context['total_likes']}, total_comments={context['total_comments']}")
    
    return render(request, 'main_app/event_detail.html', context)


@csrf_exempt
def check_email_availability(request):
    """AJAX endpoint to check if email is available"""
    if request.method == 'POST':
        email = request.POST.get('email', '').lower()
        if CustomUser.objects.filter(email=email).exists():
            return JsonResponse({'available': False})
        return JsonResponse({'available': True})
    return JsonResponse({'available': False})


def about_cosa(request):
    """AboutCOSA management System page"""
    # Get some statistics
    stats = {
        'total_alumni': Alumni.objects.filter(admin__is_verified=True).count(),
        'total_companies': Company.objects.filter(is_verified=True).count(),
        'active_jobs': JobPosting.objects.filter(is_active=True).count(),
        'upcoming_events': Event.objects.filter(status='upcoming').count(),
    }
    
    context = {
        'stats': stats,
    }
    
    return render(request, 'main_app/about.html', context)


def contact_us(request):
    """Contact us page"""
    return render(request, 'main_app/contact.html')


def pending_approval(request):
    """Pending approval page for unverified users"""
    if not request.user.is_authenticated:
        return redirect('login_page')
    
    if request.user.is_verified:
        # If user is already verified, redirect to appropriate dashboard
        if request.user.user_type == '1':
            return redirect('admin_home')
        elif request.user.user_type == '2':
            return redirect('coordinator_home')
        else:
            return redirect('alumni_home')
    
    return render(request, 'main_app/pending_approval.html')


# Legacy function for backward compatibility
def showFirebaseJS(request):
    """Firebase messaging service worker (legacy)"""
    data = """
    //COSA management System
    // Firebase messaging service worker
    importScripts('https://www.gstatic.com/firebasejs/9.0.0/firebase-app-compat.js');
    importScripts('https://www.gstatic.com/firebasejs/9.0.0/firebase-messaging-compat.js');

    firebase.initializeApp({
        apiKey: "your-api-key",
        authDomain: "cosa-alumni.firebaseapp.com",
        projectId: "cosa-alumni",
        storageBucket: "cosa-alumni.appspot.com",
        messagingSenderId: "123456789",
        appId: "your-app-id"
    });

    const messaging = firebase.messaging();
    messaging.onBackgroundMessage(function(payload) {
        const notificationTitle = payload.notification.title;
        const notificationOptions = {
            body: payload.notification.body,
            icon: '/static/img/cosa-logo.png'
        };
        
        self.registration.showNotification(notificationTitle, notificationOptions);
    });
    """
    return HttpResponse(data, content_type='application/javascript')


@csrf_exempt
@login_required
def toggle_like(request):
    """Toggle like/unlike for news, jobs, and events"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    try:
        content_type = request.POST.get('content_type')
        object_id = int(request.POST.get('object_id'))
        
        if content_type not in ['news', 'job', 'event']:
            return JsonResponse({'error': 'Invalid content type'}, status=400)
        
        # Check if like exists
        like, created = Like.objects.get_or_create(
            user=request.user,
            content_type=content_type,
            object_id=object_id
        )
        
        if not created:
            # Unlike - delete the like
            like.delete()
            liked = False
        else:
            # Like created
            liked = True
        
        # Get total likes count
        total_likes = Like.objects.filter(
            content_type=content_type,
            object_id=object_id
        ).count()
        
        return JsonResponse({
            'liked': liked,
            'total_likes': total_likes
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@login_required
def add_comment(request):
    """Add comment to news, jobs, and events"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    try:
        content_type = request.POST.get('content_type')
        object_id = int(request.POST.get('object_id'))
        content = request.POST.get('content', '').strip()
        parent_id = request.POST.get('parent_id')
        
        if content_type not in ['news', 'job', 'event']:
            return JsonResponse({'error': 'Invalid content type'}, status=400)
        
        if not content:
            return JsonResponse({'error': 'Comment content is required'}, status=400)
        
        # Create comment
        comment = Comment.objects.create(
            user=request.user,
            content_type=content_type,
            object_id=object_id,
            content=content,
            parent_id=parent_id if parent_id else None
        )
        
        # Get total comments count
        total_comments = Comment.objects.filter(
            content_type=content_type,
            object_id=object_id,
            is_approved=True
        ).count()
        
        # Generate comment HTML using the template
        from django.template.loader import render_to_string
        
        # Add like status for the comment
        comment.user_liked = False
        
        comment_html = render_to_string('main_app/comment_item.html', {
            'comment': comment,
            'user': request.user,
        })
        
        return JsonResponse({
            'success': True,
            'comment_id': comment.id,
            'total_comments': total_comments,
            'comment_html': comment_html
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@login_required
def add_reply(request):
    """Add reply to a comment"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    try:
        parent_comment_id = request.POST.get('parent_comment_id')
        content = request.POST.get('content', '').strip()
        
        if not parent_comment_id or not content:
            return JsonResponse({'error': 'Parent comment ID and content are required'}, status=400)
        
        # Get parent comment
        parent_comment = Comment.objects.get(id=parent_comment_id)
        
        # Create reply
        reply = Comment.objects.create(
            user=request.user,
            content_type=parent_comment.content_type,
            object_id=parent_comment.object_id,
            content=content,
            parent=parent_comment
        )
        
        # Generate reply HTML using the template
        from django.template.loader import render_to_string
        
        # Add like status for the reply
        reply.user_liked = False
        
        reply_html = render_to_string('main_app/comment_item.html', {
            'comment': reply,
            'user': request.user,
        })
        
        return JsonResponse({
            'success': True,
            'reply_html': reply_html
        })
        
    except Comment.DoesNotExist:
        return JsonResponse({'error': 'Parent comment not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@login_required
def toggle_comment_like(request):
    """Toggle like/unlike for comments"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    try:
        comment_id = int(request.POST.get('comment_id'))
        
        comment = Comment.objects.get(id=comment_id)
        
        # Check if like exists
        like, created = CommentLike.objects.get_or_create(
            user=request.user,
            comment=comment
        )
        
        if not created:
            # Unlike - delete the like
            like.delete()
            liked = False
        else:
            # Like created
            liked = True
        
        # Get total likes count
        total_likes = CommentLike.objects.filter(comment=comment).count()
        
        return JsonResponse({
            'liked': liked,
            'total_likes': total_likes
        })
        
    except Comment.DoesNotExist:
        return JsonResponse({'error': 'Comment not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def suspension_notice(request):
    """Display suspension notice for suspended users"""
    if not request.user.is_suspended:
        # Redirect non-suspended users to their appropriate home
        if request.user.user_type == '1':
            return redirect('admin_home')
        elif request.user.user_type == '2':
            return redirect('coordinator_home')
        else:
            return redirect('alumni_home')
    
    return render(request, 'main_app/suspension_notice.html')
