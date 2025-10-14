from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from .models import *


class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ('email', 'first_name', 'last_name', 'user_type', 'is_verified', 'is_active', 'created_at')
    list_filter = ('user_type', 'is_verified', 'is_active', 'created_at')
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'gender', 'phone_number', 'address', 'profile_pic')}),
        ('Permissions', {'fields': ('user_type', 'is_verified', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'user_type'),
        }),
    )
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)


@admin.register(Admin)
class AdminModelAdmin(admin.ModelAdmin):
    list_display = ('admin', 'employee_id')
    search_fields = ('admin__email', 'admin__first_name', 'admin__last_name', 'employee_id')


@admin.register(AlumniCoordinator)
class AlumniCoordinatorAdmin(admin.ModelAdmin):
    list_display = ('admin', 'employee_id', 'department')
    list_filter = ('department',)
    search_fields = ('admin__email', 'admin__first_name', 'admin__last_name', 'employee_id', 'department')


@admin.register(GraduationYear)
class GraduationYearAdmin(admin.ModelAdmin):
    list_display = ('year', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('year',)
    ordering = ('-year',)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'code')
    prepopulated_fields = {'code': ('name',)}


@admin.register(Degree)
class DegreeAdmin(admin.ModelAdmin):
    list_display = ('name', 'degree_type', 'department', 'duration_years', 'is_active')
    list_filter = ('degree_type', 'department', 'is_active')
    search_fields = ('name', 'department__name')


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'industry', 'size', 'location', 'is_verified', 'created_at')
    list_filter = ('industry', 'size', 'is_verified')
    search_fields = ('name', 'industry', 'location')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Alumni)
class AlumniAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'student_id', 'degree', 'graduation_year', 'current_company', 'employment_status', 'privacy_level')
    list_filter = ('graduation_year', 'degree', 'employment_status', 'privacy_level', 'is_mentor', 'willing_to_hire')
    search_fields = ('admin__first_name', 'admin__last_name', 'admin__email', 'student_id', 'current_company__name')
    raw_id_fields = ('admin', 'current_company', 'degree', 'graduation_year')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('admin', 'student_id', 'degree', 'graduation_year')
        }),
        ('Professional Information', {
            'fields': ('current_company', 'job_title', 'employment_status', 'industry', 'linkedin_profile')
        }),
        ('Personal Information', {
            'fields': ('date_of_birth', 'current_city', 'current_country', 'bio', 'achievements', 'skills')
        }),
        ('Privacy & Communication', {
            'fields': ('privacy_level', 'allow_contact', 'newsletter_subscription')
        }),
        ('Engagement', {
            'fields': ('is_mentor', 'is_job_seeker', 'willing_to_hire')
        }),
    )


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'event_type', 'status', 'start_date', 'is_virtual', 'attendee_count', 'organizer')
    list_filter = ('event_type', 'status', 'is_virtual', 'start_date')
    search_fields = ('title', 'description', 'organizer__admin__first_name', 'organizer__admin__last_name')
    date_hierarchy = 'start_date'
    raw_id_fields = ('organizer',)
    filter_horizontal = ('target_graduation_years',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'event_type', 'status', 'organizer')
        }),
        ('Date & Time', {
            'fields': ('start_date', 'end_date', 'registration_deadline')
        }),
        ('Location', {
            'fields': ('is_virtual', 'venue', 'address', 'virtual_link')
        }),
        ('Registration', {
            'fields': ('max_attendees', 'registration_fee', 'requires_approval')
        }),
        ('Targeting', {
            'fields': ('target_graduation_years',)
        }),
        ('Media', {
            'fields': ('featured_image',)
        }),
    )


@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    list_display = ('alumni', 'event', 'status', 'registration_date', 'payment_status')
    list_filter = ('status', 'payment_status', 'registration_date')
    search_fields = ('alumni__admin__first_name', 'alumni__admin__last_name', 'event__title')
    raw_id_fields = ('event', 'alumni')


@admin.register(JobPosting)
class JobPostingAdmin(admin.ModelAdmin):
    list_display = ('title', 'company', 'job_type', 'location', 'is_active', 'posted_by', 'created_at')
    list_filter = ('job_type', 'experience_level', 'is_active', 'is_featured', 'is_remote')
    search_fields = ('title', 'company__name', 'location', 'posted_by__admin__first_name')
    date_hierarchy = 'created_at'
    raw_id_fields = ('company', 'posted_by')
    
    fieldsets = (
        ('Job Information', {
            'fields': ('title', 'company', 'description', 'requirements')
        }),
        ('Job Details', {
            'fields': ('job_type', 'experience_level', 'location', 'is_remote')
        }),
        ('Compensation', {
            'fields': ('salary_min', 'salary_max', 'currency')
        }),
        ('Application', {
            'fields': ('application_deadline', 'application_email', 'application_url')
        }),
        ('Posting Details', {
            'fields': ('posted_by', 'is_active', 'is_featured')
        }),
    )


@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = ('applicant', 'job', 'status', 'application_date')
    list_filter = ('status', 'application_date')
    search_fields = ('applicant__admin__first_name', 'applicant__admin__last_name', 'job__title')
    raw_id_fields = ('job', 'applicant')


@admin.register(Donation)
class DonationAdmin(admin.ModelAdmin):
    list_display = ('donor_display', 'amount', 'currency', 'donation_type', 'payment_status', 'created_at')
    list_filter = ('donation_type', 'payment_status', 'is_anonymous', 'created_at')
    search_fields = ('donor__admin__first_name', 'donor__admin__last_name', 'transaction_id', 'campaign')
    date_hierarchy = 'created_at'
    raw_id_fields = ('donor',)
    
    def donor_display(self, obj):
        return "Anonymous" if obj.is_anonymous else obj.donor.full_name
    donor_display.short_description = 'Donor'


@admin.register(MentorshipProgram)
class MentorshipProgramAdmin(admin.ModelAdmin):
    list_display = ('mentor', 'mentee', 'focus_area', 'status', 'start_date', 'duration_months')
    list_filter = ('status', 'focus_area', 'start_date')
    search_fields = ('mentor__admin__first_name', 'mentee__admin__first_name', 'focus_area')
    raw_id_fields = ('mentor', 'mentee')


@admin.register(News)
class NewsAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'author', 'is_published', 'is_featured', 'publish_date')
    list_filter = ('category', 'is_published', 'is_featured', 'publish_date')
    search_fields = ('title', 'content', 'author__admin__first_name')
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'publish_date'
    raw_id_fields = ('author',)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('get_sender_name', 'recipient', 'subject', 'status', 'created_at')
    list_filter = ('sender_type', 'status', 'created_at')
    search_fields = ('sender_alumni__admin__first_name', 'sender_admin__admin__first_name', 'sender_coordinator__admin__first_name', 'recipient__admin__first_name', 'subject')
    raw_id_fields = ('sender_alumni', 'sender_admin', 'sender_coordinator', 'recipient')
    readonly_fields = ('created_at', 'read_at')
    
    fieldsets = (
        ('Message Info', {
            'fields': ('sender_type', 'subject', 'content', 'status')
        }),
        ('Senders', {
            'fields': ('sender_alumni', 'sender_admin', 'sender_coordinator'),
            'description': 'Only one sender should be selected based on sender_type'
        }),
        ('Recipient', {
            'fields': ('recipient',)
        }),
        ('Attachment', {
            'fields': ('attachment',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'read_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(MessageReply)
class MessageReplyAdmin(admin.ModelAdmin):
    list_display = ('message', 'sender_type', 'created_at')
    list_filter = ('sender_type', 'created_at')
    search_fields = (
        'message__subject',
        'sender_alumni__admin__first_name',
        'sender_admin__admin__first_name',
        'sender_coordinator__admin__first_name',
        'content',
    )
    raw_id_fields = ('message', 'parent', 'sender_alumni', 'sender_admin', 'sender_coordinator')
    readonly_fields = ('created_at',)


@admin.register(AlumniGroup)
class AlumniGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'group_type', 'admin', 'member_count', 'is_public', 'created_at')
    list_filter = ('group_type', 'is_public', 'requires_approval')
    search_fields = ('name', 'description', 'admin__admin__first_name')
    raw_id_fields = ('admin',)
    # Removed filter_horizontal for 'members' since it uses a through model


@admin.register(GroupMembership)
class GroupMembershipAdmin(admin.ModelAdmin):
    list_display = ('member', 'group', 'status', 'joined_date')
    list_filter = ('status', 'joined_date')
    search_fields = ('member__admin__first_name', 'group__name')
    raw_id_fields = ('group', 'member')


@admin.register(NotificationAlumni)
class NotificationAlumniAdmin(admin.ModelAdmin):
    list_display = ('alumni', 'title', 'notification_type', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('alumni__admin__first_name', 'title', 'message')
    raw_id_fields = ('alumni',)


@admin.register(NotificationCoordinator)
class NotificationCoordinatorAdmin(admin.ModelAdmin):
    list_display = ('coordinator', 'title', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('coordinator__admin__first_name', 'title', 'message')
    raw_id_fields = ('coordinator',)


@admin.register(FeedbackAlumni)
class FeedbackAlumniAdmin(admin.ModelAdmin):
    list_display = ('alumni', 'feedback_type', 'subject', 'rating', 'is_resolved', 'created_at')
    list_filter = ('feedback_type', 'rating', 'is_resolved', 'created_at')
    search_fields = ('alumni__admin__first_name', 'subject', 'feedback')
    raw_id_fields = ('alumni',)


# Register the CustomUser with the custom admin
admin.site.register(CustomUser, CustomUserAdmin)
