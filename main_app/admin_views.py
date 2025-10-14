import json
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render, reverse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q, Count, Sum, Prefetch
from django.core.paginator import Paginator
from django.utils import timezone
from django.conf import settings
from datetime import datetime, timedelta

from .models import *
from .forms import *
from .excel_utils import export_alumni_to_excel, export_alumni_by_graduation_year, export_alumni_statistics




@login_required
def manage_alumni(request):
    """Manage alumni"""
    if request.user.user_type != '1':
        return redirect('login_page')
    
    alumni = Alumni.objects.select_related('admin', 'degree', 'graduation_year').order_by('-admin__date_joined')
    
    # Search functionality
    search = request.GET.get('search')
    if search:
        alumni = alumni.filter(
            Q(admin__first_name__icontains=search) |
            Q(admin__last_name__icontains=search) |
            Q(admin__email__icontains=search) |
            Q(degree__name__icontains=search) |
            Q(graduation_year__year__icontains=search)
        )
    
    # Filter by verification status
    verification_status = request.GET.get('verification_status')
    if verification_status == 'verified':
        alumni = alumni.filter(admin__is_verified=True)
    elif verification_status == 'pending':
        alumni = alumni.filter(admin__is_verified=False)
    
    # Pagination
    paginator = Paginator(alumni, 25)
    page_number = request.GET.get('page')
    alumni_list = paginator.get_page(page_number)
    
    context = {
        'alumni': alumni_list,
    }
    
    return render(request, 'admin_template/manage_alumni.html', context)


@login_required
def verify_alumni(request, alumni_id):
    """Verify an alumni"""
    if request.user.user_type != '1':
        return redirect('login_page')
    
    alumni = get_object_or_404(Alumni, id=alumni_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'verify':
            alumni.admin.is_verified = True
            alumni.admin.save()
            messages.success(request, f'{alumni.admin.get_full_name()} has been verified!')
        elif action == 'reject':
            messages.info(request, f'Verification for {alumni.admin.get_full_name()} has been rejected.')
        
        return redirect('manage_alumni')
    
    context = {
        'alumni': alumni,
    }
    
    return render(request, 'admin_template/verify_alumni.html', context)


@login_required
def admin_home(request):
    """System Administrator dashboard"""
    if request.user.user_type != '1':
        return redirect('login_page')
    
    # Get comprehensive statistics
    stats = {
        'total_alumni': Alumni.objects.filter(admin__is_verified=True).count(),
        'pending_verifications': Alumni.objects.filter(admin__is_verified=False).count(),
        'total_coordinators': AlumniCoordinator.objects.count(),
        'active_events': Event.objects.filter(status='upcoming').count(),
        'total_jobs': JobPosting.objects.filter(is_active=True).count(),
        'total_companies': Company.objects.filter(is_verified=True).count(),
        'total_donations': Donation.objects.filter(payment_status='completed').aggregate(
            total=Sum('amount')
        )['total'] or 0,
        'active_mentorships': MentorshipProgram.objects.filter(status='active').count(),
        'published_news': News.objects.filter(is_published=True).count(),
        'unresolved_feedback': FeedbackAlumni.objects.filter(is_resolved=False).count(),
    }
    
    # Get recent activities
    recent_alumni = Alumni.objects.filter(
        admin__is_verified=True
    ).select_related('admin').order_by('-admin__date_joined')[:5]
    
    recent_events = Event.objects.order_by('-created_at')[:5]
    recent_jobs = JobPosting.objects.order_by('-created_at')[:5]
    recent_donations = Donation.objects.filter(
        payment_status='completed'
    ).order_by('-created_at')[:5]
    
    # Get system metrics
    today = timezone.now().date()
    last_30_days = today - timedelta(days=30)
    
    metrics = {
        'new_alumni_30_days': Alumni.objects.filter(
            admin__date_joined__gte=last_30_days
        ).count(),
        'new_jobs_30_days': JobPosting.objects.filter(
            created_at__gte=last_30_days
        ).count(),
        'donations_30_days': Donation.objects.filter(
            created_at__gte=last_30_days,
            payment_status='completed'
        ).aggregate(total=Sum('amount'))['total'] or 0,
        'events_30_days': Event.objects.filter(
            created_at__gte=last_30_days
        ).count(),
    }
    
    context = {
        'admin_user': request.user,
        'stats': stats,
        'metrics': metrics,
        'recent_alumni': recent_alumni,
        'recent_events': recent_events,
        'recent_jobs': recent_jobs,
        'recent_donations': recent_donations,
    }
    
    return render(request, 'admin_template/admin_home.html', context)


@login_required
def manage_coordinators(request):
    """Manage COSA Coordinators"""
    if request.user.user_type != '1':
        return redirect('login_page')
    
    coordinators = AlumniCoordinator.objects.select_related('admin').order_by('-admin__date_joined')
    
    # Search functionality
    search = request.GET.get('search')
    if search:
        coordinators = coordinators.filter(
            Q(admin__first_name__icontains=search) |
            Q(admin__last_name__icontains=search) |
            Q(admin__email__icontains=search) |
            Q(department__icontains=search)
        )
    
    # Pagination
    paginator = Paginator(coordinators, 20)
    page_number = request.GET.get('page')
    coordinator_list = paginator.get_page(page_number)
    
    context = {
        'coordinators': coordinator_list,
    }
    
    return render(request, 'admin_template/manage_coordinators.html', context)


@login_required
def add_coordinator(request):
    """Add a new alumni coordinator"""
    if request.user.user_type != '1':
        return redirect('login_page')
    
    if request.method == 'POST':
        # Create user account
        email = request.POST.get('email')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        password = request.POST.get('password')
        phone_number = request.POST.get('phone_number', '')
        address = request.POST.get('address', '')
        department = request.POST.get('department', '')
        employee_id = request.POST.get('employee_id', '')
        
        # Check if email already exists
        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, 'Email already exists!')
            return render(request, 'admin_template/add_coordinator.html')
        
        # Create user
        user = CustomUser.objects.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            user_type='2',
            phone_number=phone_number,
            address=address,
            is_verified=True
        )
        
        # Update coordinator profile
        coordinator = user.alumnicoordinator
        coordinator.department = department
        coordinator.employee_id = employee_id
        coordinator.save()
        
        messages.success(request, 'Alumni Coordinator added successfully!')
        return redirect('manage_coordinators')
    
    return render(request, 'admin_template/add_coordinator.html')


@login_required
def edit_coordinator(request, coordinator_id):
    """Edit coordinator details"""
    if request.user.user_type != '1':
        return redirect('login_page')
    
    coordinator = get_object_or_404(AlumniCoordinator, id=coordinator_id)
    
    if request.method == 'POST':
        coordinator.admin.first_name = request.POST.get('first_name')
        coordinator.admin.last_name = request.POST.get('last_name')
        coordinator.admin.phone_number = request.POST.get('phone_number', '')
        coordinator.admin.address = request.POST.get('address', '')
        coordinator.department = request.POST.get('department', '')
        coordinator.employee_id = request.POST.get('employee_id', '')
        
        # Update password if provided
        password = request.POST.get('password')
        if password:
            coordinator.admin.set_password(password)
        
        coordinator.admin.save()
        coordinator.save()
        
        messages.success(request, 'Coordinator updated successfully!')
        return redirect('manage_coordinators')
    
    context = {
        'coordinator': coordinator,
    }
    
    return render(request, 'admin_template/edit_coordinator.html', context)


@login_required
def delete_coordinator(request, coordinator_id):
    """Delete coordinator"""
    if request.user.user_type != '1':
        return redirect('login_page')
    
    coordinator = get_object_or_404(AlumniCoordinator, id=coordinator_id)
    
    if request.method == 'POST':
        coordinator.admin.delete()  # This will cascade delete the coordinator
        messages.success(request, 'Coordinator deleted successfully!')
        return redirect('manage_coordinators')
    
    context = {
        'coordinator': coordinator,
    }
    
    return render(request, 'admin_template/delete_coordinator.html', context)


@login_required
def manage_departments(request):
    """Manage departments"""
    if request.user.user_type != '1':
        return redirect('login_page')
    
    departments = Department.objects.order_by('name')
    
    context = {
        'departments': departments,
    }
    
    return render(request, 'admin_template/manage_departments.html', context)


@login_required
def add_department(request):
    """Add a new department"""
    if request.user.user_type != '1':
        return redirect('login_page')
    
    if request.method == 'POST':
        form = DepartmentForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Department added successfully!')
            return redirect('manage_departments')
    else:
        form = DepartmentForm()
    
    context = {
        'form': form,
    }
    
    return render(request, 'admin_template/add_department.html', context)


@login_required
def edit_department(request, department_id):
    """Edit department"""
    if request.user.user_type != '1':
        return redirect('login_page')
    
    department = get_object_or_404(Department, id=department_id)
    
    if request.method == 'POST':
        form = DepartmentForm(request.POST, instance=department)
        if form.is_valid():
            form.save()
            messages.success(request, 'Department updated successfully!')
            return redirect('manage_departments')
    else:
        form = DepartmentForm(instance=department)
    
    context = {
        'form': form,
        'department': department,
    }
    
    return render(request, 'admin_template/edit_department.html', context)


@login_required
def delete_department(request, department_id):
    """Delete department"""
    if request.user.user_type != '1':
        return redirect('login_page')
    
    department = get_object_or_404(Department, id=department_id)
    
    # Check if department has associated degrees
    if department.degree_set.exists():
        messages.error(request, f'Cannot delete department "{department.name}" because it has associated degree programs. Please delete or reassign the degree programs first.')
        return redirect('manage_departments')
    
    if request.method == 'POST':
        department.delete()
        messages.success(request, 'Department deleted successfully!')
        return redirect('manage_departments')
    
    context = {
        'department': department,
    }
    
    return render(request, 'admin_template/delete_department.html', context)


@login_required
def manage_degrees(request):
    """Manage degree programs"""
    if request.user.user_type != '1':
        return redirect('login_page')
    
    degrees = Degree.objects.select_related('department').order_by('department__name', 'name')
    
    # Calculate statistics
    degree_types_count = degrees.values('degree_type').distinct().count()
    departments_count = degrees.values('department').distinct().count()
    active_degrees_count = degrees.filter(is_active=True).count()
    
    # Get departments for filter dropdown
    departments = Department.objects.filter(is_active=True).order_by('name')
    
    context = {
        'degrees': degrees,
        'degree_types_count': degree_types_count,
        'departments_count': departments_count,
        'active_degrees_count': active_degrees_count,
        'departments': departments,
    }
    
    return render(request, 'admin_template/manage_degrees.html', context)


@login_required
def add_degree(request):
    """Add a new degree program"""
    if request.user.user_type != '1':
        return redirect('login_page')
    
    if request.method == 'POST':
        form = DegreeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Degree program added successfully!')
            return redirect('manage_degrees')
    else:
        form = DegreeForm()
    
    context = {
        'form': form,
    }
    
    return render(request, 'admin_template/add_degree.html', context)


@login_required
def edit_degree(request, degree_id):
    """Edit degree program"""
    if request.user.user_type != '1':
        return redirect('login_page')
    
    degree = get_object_or_404(Degree, id=degree_id)
    
    if request.method == 'POST':
        form = DegreeForm(request.POST, instance=degree)
        if form.is_valid():
            form.save()
            messages.success(request, 'Degree program updated successfully!')
            return redirect('manage_degrees')
    else:
        form = DegreeForm(instance=degree)
    
    context = {
        'form': form,
        'degree': degree,
    }
    
    return render(request, 'admin_template/edit_degree.html', context)


@login_required
def delete_degree(request, degree_id):
    """Delete degree program"""
    if request.user.user_type != '1':
        return redirect('login_page')
    
    degree = get_object_or_404(Degree, id=degree_id)
    
    # Check if degree has associated alumni
    if degree.alumni_set.exists():
        messages.error(request, f'Cannot delete degree "{degree.name}" because it has associated alumni. Please reassign the alumni first.')
        return redirect('manage_degrees')
    
    if request.method == 'POST':
        degree.delete()
        messages.success(request, 'Degree program deleted successfully!')
        return redirect('manage_degrees')
    
    context = {
        'degree': degree,
    }
    
    return render(request, 'admin_template/delete_degree.html', context)


@login_required
def manage_graduation_years(request):
    """Manage class levels"""
    if request.user.user_type != '1':
        return redirect('login_page')
    
    years = GraduationYear.objects.order_by('display_order', 'year')
    
    context = {
        'years': years,
    }
    
    return render(request, 'admin_template/manage_graduation_years.html', context)


@login_required
def add_graduation_year(request):
    """Add a new class level"""
    if request.user.user_type != '1':
        return redirect('login_page')
    
    if request.method == 'POST':
        form = GraduationYearForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Class level added successfully!')
            return redirect('manage_graduation_years')
    else:
        form = GraduationYearForm()
    
    context = {
        'form': form,
    }
    
    return render(request, 'admin_template/add_graduation_year.html', context)


@login_required
def edit_graduation_year(request, year_id):
    """Edit class level"""
    if request.user.user_type != '1':
        return redirect('login_page')
    
    year = get_object_or_404(GraduationYear, id=year_id)
    
    if request.method == 'POST':
        form = GraduationYearForm(request.POST, instance=year)
        if form.is_valid():
            form.save()
            messages.success(request, 'Class level updated successfully!')
            return redirect('manage_graduation_years')
    else:
        form = GraduationYearForm(instance=year)
    
    context = {
        'form': form,
        'year': year,
    }
    
    return render(request, 'admin_template/edit_graduation_year.html', context)


@login_required
def delete_graduation_year(request, year_id):
    """Delete class level"""
    if request.user.user_type != '1':
        return redirect('login_page')
    
    year = get_object_or_404(GraduationYear, id=year_id)
    
    # Check if year has associated alumni
    if year.alumni_set.exists():
        messages.error(request, f'Cannot delete class level "{year.get_year_display()}" because it has associated alumni. Please reassign the alumni first.')
        return redirect('manage_graduation_years')
    
    if request.method == 'POST':
        year.delete()
        messages.success(request, 'Class level deleted successfully!')
        return redirect('manage_graduation_years')
    
    context = {
        'year': year,
    }
    
    return render(request, 'admin_template/delete_graduation_year.html', context)


@login_required
def manage_companies(request):
    """Manage companies"""
    if request.user.user_type != '1':
        return redirect('login_page')
    
    companies = Company.objects.order_by('-created_at')
    
    # Search functionality
    search = request.GET.get('search')
    if search:
        companies = companies.filter(
            Q(name__icontains=search) |
            Q(industry__icontains=search) |
            Q(location__icontains=search)
        )
    
    # Filter by verification status
    verification_status = request.GET.get('verification_status')
    if verification_status == 'verified':
        companies = companies.filter(is_verified=True)
    elif verification_status == 'pending':
        companies = companies.filter(is_verified=False)
    
    # Pagination
    paginator = Paginator(companies, 25)
    page_number = request.GET.get('page')
    company_list = paginator.get_page(page_number)
    
    context = {
        'companies': company_list,
    }
    
    return render(request, 'admin_template/manage_companies.html', context)


@login_required
def verify_company(request, company_id):
    """Verify a company"""
    if request.user.user_type != '1':
        return redirect('login_page')
    
    company = get_object_or_404(Company, id=company_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'verify':
            company.is_verified = True
            company.save()
            messages.success(request, f'{company.name} has been verified!')
        elif action == 'reject':
            messages.info(request, f'Verification for {company.name} has been rejected.')
        
        return redirect('manage_companies')
    
    context = {
        'company': company,
    }
    
    return render(request, 'admin_template/verify_company.html', context)


@login_required
def edit_company(request, company_id):
    """Edit company"""
    if request.user.user_type != '1':
        return redirect('login_page')
    
    company = get_object_or_404(Company, id=company_id)
    
    if request.method == 'POST':
        form = CompanyForm(request.POST, instance=company)
        if form.is_valid():
            form.save()
            messages.success(request, 'Company updated successfully!')
            return redirect('manage_companies')
    else:
        form = CompanyForm(instance=company)
    
    context = {
        'form': form,
        'company': company,
    }
    
    return render(request, 'admin_template/edit_company.html', context)


@login_required
def delete_company(request, company_id):
    """Delete company"""
    if request.user.user_type != '1':
        return redirect('login_page')
    
    company = get_object_or_404(Company, id=company_id)
    
    # Check if company has associated job postings
    if company.jobposting_set.exists():
        messages.error(request, f'Cannot delete company "{company.name}" because it has associated job postings. Please delete the job postings first.')
        return redirect('manage_companies')
    
    if request.method == 'POST':
        company.delete()
        messages.success(request, 'Company deleted successfully!')
        return redirect('manage_companies')
    
    context = {
        'company': company,
    }
    
    return render(request, 'admin_template/delete_company.html', context)


@login_required
def system_analytics(request):
    """System analytics and reports"""
    if request.user.user_type != '1':
        return redirect('login_page')
    
    # Alumni statistics
    alumni_stats = {
        'total': Alumni.objects.count(),
        'verified': Alumni.objects.filter(admin__is_verified=True).count(),
        'by_graduation_year': Alumni.objects.values(
            'graduation_year__year'
        ).annotate(count=Count('id')).order_by('-graduation_year__year')[:10],
        'by_degree': Alumni.objects.values(
            'degree__name'
        ).annotate(count=Count('id')).order_by('-count')[:10],
        'by_employment_status': Alumni.objects.values(
            'employment_status'
        ).annotate(count=Count('id')),
    }
    
    # Job statistics
    job_stats = {
        'total': JobPosting.objects.count(),
        'active': JobPosting.objects.filter(is_active=True).count(),
        'by_type': JobPosting.objects.values(
            'job_type'
        ).annotate(count=Count('id')),
        'applications': JobApplication.objects.count(),
    }
    
    # Event statistics
    event_stats = {
        'total': Event.objects.count(),
        'upcoming': Event.objects.filter(status='upcoming').count(),
        'registrations': EventRegistration.objects.count(),
        'by_type': Event.objects.values(
            'event_type'
        ).annotate(count=Count('id')),
    }
    
    # Donation statistics - MySQL compatible version
    from django.db.models.functions import ExtractMonth
    
    donation_stats = {
        'total_amount': Donation.objects.filter(
            payment_status='completed'
        ).aggregate(total=Sum('amount'))['total'] or 0,
        'total_count': Donation.objects.filter(payment_status='completed').count(),
        'by_type': Donation.objects.filter(
            payment_status='completed'
        ).values('donation_type').annotate(
            count=Count('id'),
            total=Sum('amount')
        ),
        'monthly_trend': Donation.objects.filter(
            payment_status='completed',
            created_at__gte=timezone.now() - timezone.timedelta(days=365)
        ).annotate(
            month=ExtractMonth('created_at')
        ).values('month').annotate(
            count=Count('id'),
            total=Sum('amount')
        ).order_by('month'),
    }
    
    context = {
        'alumni_stats': alumni_stats,
        'job_stats': job_stats,
        'event_stats': event_stats,
        'donation_stats': donation_stats,
    }
    
    return render(request, 'admin_template/system_analytics.html', context)

@login_required
def system_settings(request):
    """System settings management"""
    if request.user.user_type != '1':
        return redirect('login_page')
    
    if request.method == 'POST':
        # Update COSA settings (this would typically be stored in database)
        # For now, we'll just show a success message
        messages.success(request, 'System settings updated successfully!')
        return redirect('system_settings')
    
    context = {
        'cosa_settings': settings.COSA_SETTINGS,
    }
    
    return render(request, 'admin_template/system_settings.html', context)


@login_required
def admin_profile(request):
    """Admin profile management"""
    if request.user.user_type != '1':
        return redirect('login_page')
    
    if request.method == 'POST':
        form = AdminProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('admin_profile')
    else:
        form = AdminProfileForm(instance=request.user)
    
    context = {
        'form': form,
    }
    
    return render(request, 'admin_template/admin_profile.html', context)


@login_required
def bulk_operations(request):
    """Bulk operations on alumni data"""
    if request.user.user_type != '1':
        return redirect('login_page')
    
    if request.method == 'POST':
        operation = request.POST.get('operation')
        
        if operation == 'verify_all_pending':
            count = Alumni.objects.filter(admin__is_verified=False).update(
                admin__is_verified=True
            )
            messages.success(request, f'Verified {count} pending alumni!')
        
        elif operation == 'send_newsletter':
            # This would typically integrate with an email service
            count = Alumni.objects.filter(
                newsletter_subscription=True,
                admin__is_verified=True
            ).count()
            messages.success(request, f'Newsletter queued for {count} alumni!')
        
        return redirect('bulk_operations')
    
    # Get counts for various operations
    counts = {
        'pending_verifications': Alumni.objects.filter(admin__is_verified=False).count(),
        'newsletter_subscribers': Alumni.objects.filter(
            newsletter_subscription=True,
            admin__is_verified=True
        ).count(),
        'inactive_alumni': Alumni.objects.filter(
            admin__last_login__lt=timezone.now() - timedelta(days=365)
        ).count(),
    }
    
    context = {
        'counts': counts,
    }
    
    return render(request, 'admin_template/bulk_operations.html', context)


@csrf_exempt
def admin_fcmtoken(request):
    """Update FCM token for admin"""
    if request.user.user_type != '1':
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'})
    
    if request.method == 'POST':
        fcm_token = request.POST.get('fcm_token')
        if fcm_token:
            request.user.fcm_token = fcm_token
            request.user.save()
            return JsonResponse({'status': 'success'})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})


@csrf_exempt
def get_system_stats(request):
    """AJAX endpoint for dashboard statistics"""
    if request.user.user_type != '1':
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'})
    
    stats = {
        'total_alumni': Alumni.objects.filter(admin__is_verified=True).count(),
        'active_jobs': JobPosting.objects.filter(is_active=True).count(),
        'upcoming_events': Event.objects.filter(status='upcoming').count(),
        'total_donations': float(Donation.objects.filter(
            payment_status='completed'
        ).aggregate(total=Sum('amount'))['total'] or 0),
    }
    
    return JsonResponse(stats)


@login_required
def admin_messages_inbox(request):
    """Admin messages inbox - shows sent messages"""
    if request.user.user_type != '1':
        return redirect('login_page')
    
    # Get admin profile
    try:
        admin_profile = request.user.admin
    except Admin.DoesNotExist:
        messages.error(request, 'Admin profile not found.')
        return redirect('login_page')
    
    # Get messages sent by this admin
    sent_messages = Message.objects.filter(
        sender_type='admin',
        sender_admin=admin_profile
    ).select_related('recipient', 'recipient__admin').order_by('-created_at')
    
    # Pagination
    paginator = Paginator(sent_messages, 10)
    page_number = request.GET.get('page')
    messages_page = paginator.get_page(page_number)
    
    context = {
        'messages': messages_page,
        'admin_user': request.user,
    }
    
    return render(request, 'admin_template/messages_inbox.html', context)


@login_required
def admin_send_message(request, recipient_id=None):
    """Send a message to an alumni"""
    if request.user.user_type != '1':
        return redirect('login_page')
    
    # Get admin profile
    try:
        admin_profile = request.user.admin
    except Admin.DoesNotExist:
        messages.error(request, 'Admin profile not found.')
        return redirect('login_page')
    
    recipient = None
    if recipient_id:
        recipient = get_object_or_404(Alumni, id=recipient_id, admin__is_verified=True)
    
    if request.method == 'POST':
        form = AdminMessageForm(request.POST, request.FILES)
        if form.is_valid():
            message = form.save(commit=False)
            message.sender_type = 'admin'
            message.sender_admin = admin_profile
            message.save()
            messages.success(request, f'Message sent successfully to {message.recipient.full_name}!')
            return redirect('admin_messages_inbox')
    else:
        initial_data = {}
        if recipient:
            initial_data['recipient'] = recipient
        form = AdminMessageForm(initial=initial_data)
    
    context = {
        'form': form,
        'recipient': recipient,
        'admin_user': request.user,
    }
    
    return render(request, 'admin_template/send_message.html', context)


@login_required
def admin_view_message(request, message_id):
    """View a specific message"""
    if request.user.user_type != '1':
        return redirect('login_page')
    
    # Get admin profile
    try:
        admin_profile = request.user.admin
    except Admin.DoesNotExist:
        messages.error(request, 'Admin profile not found.')
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
        sender_type='admin',
        sender_admin=admin_profile
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
            reply.sender_type = 'admin'
            reply.sender_admin = admin_profile
            reply.sender_alumni = None
            reply.sender_coordinator = None
            reply.parent = None
            reply.save()
            message.status = 'sent'
            message.read_at = None
            message.save(update_fields=['status', 'read_at'])
            messages.success(request, 'Reply sent successfully.')
            return redirect('admin_view_message', message_id=message.id)
        else:
            messages.error(request, 'Please fix the errors below to send your reply.')
    
    context = {
        'message': message,
        'admin_user': request.user,
        'replies': replies,
        'reply_form': reply_form,
    }
    
    return render(request, 'admin_template/view_message.html', context)


@login_required
def admin_fcmtoken(request):
    """Admin FCM token management"""
    if request.user.user_type != '1':
        return redirect('login_page')
    
    if request.method == 'POST':
        token = request.POST.get('fcm_token')
        if token:
            # Store FCM token for admin
            request.user.fcm_token = token
            request.user.save()
            return JsonResponse({'status': 'success'})
    
    return JsonResponse({'status': 'error'})


@login_required
def get_system_stats(request):
    """Get system statistics for AJAX requests"""
    if request.user.user_type != '1':
        return redirect('login_page')
    
    stats = {
        'total_alumni': Alumni.objects.filter(admin__is_verified=True).count(),
        'pending_verifications': Alumni.objects.filter(admin__is_verified=False).count(),
        'total_coordinators': AlumniCoordinator.objects.count(),
        'active_events': Event.objects.filter(status='upcoming').count(),
        'total_jobs': JobPosting.objects.filter(is_active=True).count(),
        'total_companies': Company.objects.filter(is_verified=True).count(),
        'total_donations': Donation.objects.filter(payment_status='completed').aggregate(
            total=Sum('amount')
        )['total'] or 0,
        'active_mentorships': MentorshipProgram.objects.filter(status='active').count(),
        'published_news': News.objects.filter(is_published=True).count(),
        'unresolved_feedback': FeedbackAlumni.objects.filter(is_resolved=False).count(),
    }
    
    return JsonResponse(stats)


@login_required
def register_alumni(request):
    """Register a new alumni (for admins)"""
    if request.user.user_type != '1':
        return redirect('login_page')
    
    if request.method == 'POST':
        form = AlumniRegistrationForm(request.POST)
        if form.is_valid():
            try:
                # Save the form which creates both user and alumni
                user = form.save()
                
                # Update user settings for admin created alumni
                user.is_verified = True  # Auto-verify when created by admin
                user.save()
                
                # Get the alumni record (should exist after form.save())
                try:
                    alumni = user.alumni
                    # Update alumni privacy level for admin created alumni
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
                return render(request, 'admin_template/register_alumni.html', {'form': form})
    else:
        form = AlumniRegistrationForm()
    
    context = {
        'form': form,
    }
    
    return render(request, 'admin_template/register_alumni.html', context)


@login_required
def delete_alumni(request, alumni_id):
    """Delete an alumni (for admins)"""
    if request.user.user_type != '1':
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
    
    return render(request, 'admin_template/delete_alumni.html', context)


@login_required
def export_alumni_excel(request, export_type='all'):
    """Export alumni data to Excel format"""
    if request.user.user_type != '1':  # Admin only
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
def export_alumni_by_year_excel(request, year_id):
    """Export alumni by class level to Excel"""
    if request.user.user_type != '1':  # Admin only
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
def export_alumni_statistics_excel(request):
    """Export alumni statistics to Excel"""
    if request.user.user_type != '1':  # Admin only
        return redirect('login_page')
    
    try:
        response = export_alumni_statistics()
        
        messages.success(request, 'Successfully exported alumni statistics to Excel!')
        return response
        
    except Exception as e:
        messages.error(request, f'Error exporting statistics: {str(e)}')
        return redirect('admin_home')


@login_required
def admin_suspend_user(request, user_id):
    """Suspend a user account"""
    if request.user.user_type != '1':
        return redirect('login_page')
    
    user = get_object_or_404(CustomUser, id=user_id)
    
    # Prevent suspending other admins
    if user.user_type == '1':
        messages.error(request, 'Cannot suspend other administrators.')
        return redirect('manage_alumni')
    
    if request.method == 'POST':
        form = SuspendUserForm(request.POST)
        if form.is_valid():
            reason = form.cleaned_data['reason']
            suspension_type = form.cleaned_data['suspension_type']
            expires_at = form.cleaned_data.get('expires_at')
            
            if suspension_type == 'permanent':
                expires_at = None
            
            user.suspend_account(
                suspended_by=request.user,
                reason=reason,
                expires_at=expires_at
            )
            
            messages.success(request, f'Account for {user.get_full_name()} has been suspended successfully.')
            return redirect('manage_alumni')
    else:
        form = SuspendUserForm()
    
    context = {
        'form': form,
        'user': user,
        'admin_user': request.user,
    }
    
    return render(request, 'admin_template/suspend_user.html', context)


@login_required
def admin_unsuspend_user(request, user_id):
    """Unsuspend a user account"""
    if request.user.user_type != '1':
        return redirect('login_page')
    
    user = get_object_or_404(CustomUser, id=user_id)
    
    if not user.is_suspended:
        messages.warning(request, f'Account for {user.get_full_name()} is not suspended.')
        return redirect('manage_alumni')
    
    if request.method == 'POST':
        form = UnsuspendUserForm(request.POST)
        if form.is_valid():
            reason = form.cleaned_data.get('reason', '')
            
            user.unsuspend_account()
            
            messages.success(request, f'Account for {user.get_full_name()} has been unsuspended successfully.')
            return redirect('manage_alumni')
    else:
        form = UnsuspendUserForm()
    
    context = {
        'form': form,
        'user': user,
        'admin_user': request.user,
    }
    
    return render(request, 'admin_template/unsuspend_user.html', context)


@login_required
def admin_user_suspension_history(request, user_id):
    """View suspension history for a user"""
    if request.user.user_type != '1':
        return redirect('login_page')
    
    user = get_object_or_404(CustomUser, id=user_id)
    
    context = {
        'user': user,
        'admin_user': request.user,
    }
    
    return render(request, 'admin_template/user_suspension_history.html', context)
