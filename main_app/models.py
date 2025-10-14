from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import UserManager
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from datetime import datetime, timedelta


class CustomUserManager(UserManager):
    def _create_user(self, email, password, **extra_fields):
        email = self.normalize_email(email)
        user = CustomUser(email=email, **extra_fields)
        user.password = make_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        extra_fields.setdefault("user_type", "3")  # Default to Alumni
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("user_type", "1")  # Force Admin type for superusers

        assert extra_fields["is_staff"]
        assert extra_fields["is_superuser"]
        return self._create_user(email, password, **extra_fields)


class CustomUser(AbstractUser):
    USER_TYPE = ((1, "Admin"), (2, "Alumni Coordinator"), (3, "Alumni"))
    GENDER = [("M", "Male"), ("F", "Female"), ("O", "Other"), ("P", "Prefer not to say")]
    
    username = None  # Removed username, using email instead
    email = models.EmailField(unique=True)
    user_type = models.CharField(default=3, choices=USER_TYPE, max_length=1)
    gender = models.CharField(max_length=1, choices=GENDER, blank=True)
    profile_pic = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    address = models.TextField(blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    fcm_token = models.TextField(default="", blank=True)  # For firebase notifications
    is_verified = models.BooleanField(default=False)
    
    # Account suspension fields - REMOVED self-reference to avoid circular import
    is_suspended = models.BooleanField(default=False, help_text="Whether the account is suspended")
    suspension_reason = models.TextField(blank=True, null=True, help_text="Reason for suspension")
    suspended_at = models.DateTimeField(null=True, blank=True, help_text="When the account was suspended")
    suspension_expires_at = models.DateTimeField(null=True, blank=True, help_text="When the suspension expires (null for permanent)")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = CustomUserManager()

    def __str__(self):
        return f"{self.first_name} {self.last_name}" if self.first_name and self.last_name else self.email
    
    def suspend_account(self, reason="", expires_at=None):
        """Suspend this user account"""
        self.is_suspended = True
        self.suspension_reason = reason
        self.suspended_at = timezone.now()
        self.suspension_expires_at = expires_at
        self.save()
    
    def unsuspend_account(self):
        """Unsuspend this user account"""
        self.is_suspended = False
        self.suspension_reason = None
        self.suspended_at = None
        self.suspension_expires_at = None
        self.save()
    
    def is_suspension_expired(self):
        """Check if suspension has expired"""
        if not self.is_suspended:
            return False
        if not self.suspension_expires_at:
            return False  # Permanent suspension
        return timezone.now() > self.suspension_expires_at
    
    def get_suspension_status(self):
        """Get human-readable suspension status"""
        if not self.is_suspended:
            return "Active"
        if self.is_suspension_expired():
            return "Expired (Auto-unsuspend needed)"
        if self.suspension_expires_at:
            return f"Suspended until {self.suspension_expires_at.strftime('%Y-%m-%d %H:%M')}"
        return "Permanently suspended"
    
    def can_login(self):
        """Check if user can login (not suspended or suspension expired)"""
        if not self.is_suspended:
            return True
        if self.is_suspension_expired():
            # Auto-unsuspend expired suspensions
            self.unsuspend_account()
            return True
        return False

    # ADD THESE NEW PROPERTIES:
    @property
    def is_admin(self):
        """Check if user is an administrator"""
        return self.user_type == '1' or self.is_superuser
    
    @property
    def is_coordinator(self):
        """Check if user is a coordinator"""
        return self.user_type == '2'
    
    @property
    def is_alumni(self):
        """Check if user is an alumni"""
        return self.user_type == '3'
    
    def save(self, *args, **kwargs):
        """Override save to ensure superusers are always admins"""
        # If user is superuser, automatically set as admin
        if self.is_superuser and self.user_type != '1':
            self.user_type = '1'
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"


class Admin(models.Model):
    admin = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    employee_id = models.CharField(max_length=20, unique=True, blank=True)
    
    def __str__(self):
        return f"Admin: {self.admin.first_name} {self.admin.last_name}"

    class Meta:
        verbose_name = "System Administrator"
        verbose_name_plural = "System Administrators"


class AlumniCoordinator(models.Model):
    admin = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    employee_id = models.CharField(max_length=20, unique=True, blank=True)
    department = models.CharField(max_length=100, blank=True)
    
    def __str__(self):
        return f"Coordinator: {self.admin.first_name} {self.admin.last_name}"

    class Meta:
        verbose_name = "Alumni Coordinator"
        verbose_name_plural = "COSA Coordinators"


class GraduationYear(models.Model):
    YEAR_CHOICES = [(str(year), str(year)) for year in range(2003, 2026)]


    year = models.CharField(max_length=20, unique=True, choices=YEAR_CHOICES)
    display_order = models.PositiveIntegerField(default=0, help_text="Controls the ordering of levels in lists")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.get_year_display()

    @property
    def code(self):
        return self.year

    @property
    def short_code(self):
        mapping = {
            'O_LEVEL': 'OL',
            'A_LEVEL': 'AL',
        }
        if self.year in mapping:
            return mapping[self.year]
        return self.year.replace(' ', '').upper()

    class Meta:
        ordering = ['display_order', 'year']
        verbose_name = "Class Level"
        verbose_name_plural = "Class Levels"


class Department(models.Model):
    name = models.CharField(max_length=120, unique=True)
    code = models.CharField(max_length=10, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        verbose_name = "Department"
        verbose_name_plural = "Departments"


class Degree(models.Model):
    CLASS_LEVELS = [
        ('S1', 'Senior One'),
        ('S2', 'Senior Two'),
        ('S3', 'Senior Three'),
        ('S4', 'Senior Four (O\'Level)'),
        ('S5', 'Senior Five'),
        ('S6', 'Senior Six (A\'Level)'),
    ]

    name = models.CharField(max_length=120)
    degree_type = models.CharField(max_length=20, choices=CLASS_LEVELS)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    duration_years = models.IntegerField(default=4)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.degree_type} in {self.name}"

    class Meta:
        ordering = ['degree_type', 'name']
        verbose_name = "Level"
        verbose_name_plural = "Levels"

class Company(models.Model):
    COMPANY_SIZES = [
        ('startup', '1-10 employees'),
        ('small', '11-50 employees'),
        ('medium', '51-200 employees'),
        ('large', '201-1000 employees'),
        ('enterprise', '1000+ employees'),
    ]
    
    name = models.CharField(max_length=200, unique=True)
    website = models.URLField(blank=True)
    industry = models.CharField(max_length=100, blank=True)
    size = models.CharField(max_length=20, choices=COMPANY_SIZES, blank=True)
    location = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to='company_logos/', blank=True, null=True)

    # 🔥 New fields
    founded_year = models.IntegerField(null=True, blank=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,   # 🔥 correct way
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='companies'
    )
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        verbose_name = "Company"
        verbose_name_plural = "Companies"


class Alumni(models.Model):
    EMPLOYMENT_STATUS = [
        ('employed', 'Employed'),
        ('unemployed', 'Unemployed'),
        ('self_employed', 'Self-Employed'),
        ('student', 'Student'),
        ('retired', 'Retired'),
    ]
    
    PRIVACY_LEVELS = [
        ('public', 'Public - Visible to all alumni'),
        ('limited', 'Limited - Visible to verified alumni only'),
        ('private', 'Private - Only basic info visible'),
    ]
    
    admin = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    student_id = models.CharField(max_length=20, unique=True, blank=True, editable=False)
    degree = models.ForeignKey(Degree, on_delete=models.SET_NULL, null=True)
    graduation_year = models.ForeignKey(GraduationYear, on_delete=models.SET_NULL, null=True)
    
    # Professional Information
    current_company = models.ForeignKey(Company, on_delete=models.SET_NULL, null=True, blank=True)
    job_title = models.CharField(max_length=100, blank=True)
    employment_status = models.CharField(max_length=20, choices=EMPLOYMENT_STATUS, default='employed')
    industry = models.CharField(max_length=100, blank=True)
    linkedin_profile = models.URLField(blank=True)
    
    # Personal Information
    date_of_birth = models.DateField(null=True, blank=True)
    current_city = models.CharField(max_length=100, blank=True)
    current_country = models.CharField(max_length=100, blank=True)
    bio = models.TextField(blank=True, help_text="Brief professional/personal bio")
    
    # Achievements and Recognition
    achievements = models.TextField(blank=True, help_text="Notable achievements and awards")
    skills = models.TextField(blank=True, help_text="Professional skills (comma-separated)")
    
    # Privacy and Communication
    privacy_level = models.CharField(max_length=20, choices=PRIVACY_LEVELS, default='limited')
    allow_contact = models.BooleanField(default=True)
    newsletter_subscription = models.BooleanField(default=True)
    
    # Engagement
    is_mentor = models.BooleanField(default=False)
    is_job_seeker = models.BooleanField(default=False)
    willing_to_hire = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.admin.first_name} {self.admin.last_name} ({self.graduation_year.get_year_display() if self.graduation_year else 'Level Not Set'})"

    @property
    def full_name(self):
        return f"{self.admin.first_name} {self.admin.last_name}"

    @property
    def years_since_graduation(self):
        return None
    
    def generate_student_id(self):
        """Generate a unique student ID based on the class level and sequential number"""
        if not self.graduation_year:
            return f"COSAUNK{timezone.now().year}{str(self.pk or '').zfill(3)}"
        
        level_code = self.graduation_year.short_code
        prefix = f"COSA{level_code}"
        
        existing_alumni = Alumni.objects.filter(
            graduation_year=self.graduation_year,
            student_id__startswith=prefix
        ).exclude(student_id='').order_by('-student_id')
        
        if existing_alumni.exists():
            last_student_id = existing_alumni.first().student_id
            try:
                last_sequential = int(last_student_id[-3:])
                next_sequential = last_sequential + 1
            except (ValueError, IndexError):
                next_sequential = existing_alumni.count() + 1
        else:
            next_sequential = 1
        
        sequential_number = str(next_sequential).zfill(3)
        student_id = f"{prefix}{sequential_number}"
        counter = 1
        
        while Alumni.objects.filter(student_id=student_id).exists():
            counter += 1
            sequential_number = str(next_sequential + counter - 1).zfill(3)
            student_id = f"{prefix}{sequential_number}"
        
        return student_id
    
    def save(self, *args, **kwargs):
        """Override save to auto-generate student_id if not provided"""
        if not self.student_id:
            self.student_id = self.generate_student_id()
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['graduation_year__display_order', 'admin__last_name']
        verbose_name = "Alumni"
        verbose_name_plural = "Alumni"


class Event(models.Model):
    EVENT_TYPES = [
        ('reunion', 'Alumni Reunion'),
        ('networking', 'Networking Event'),
        ('seminar', 'Seminar/Workshop'),
        ('social', 'Social Gathering'),
        ('fundraising', 'Fundraising Event'),
        ('career', 'Career Fair'),
        ('webinar', 'Webinar'),
        ('other', 'Other'),
    ]
    
    EVENT_STATUS = [
        ('upcoming', 'Upcoming'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    status = models.CharField(max_length=20, choices=EVENT_STATUS, default='upcoming')
    
    # Date and Time
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    registration_deadline = models.DateTimeField(null=True, blank=True)
    
    # Location
    is_virtual = models.BooleanField(default=False)
    venue = models.CharField(max_length=200, blank=True)
    address = models.TextField(blank=True)
    virtual_link = models.URLField(blank=True)
    
    # Registration
    max_attendees = models.IntegerField(null=True, blank=True)
    registration_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    requires_approval = models.BooleanField(default=False)
    
    # Media
    featured_image = models.ImageField(upload_to='event_images/', blank=True, null=True)
    
    # Organization
    organizer = models.ForeignKey(AlumniCoordinator, on_delete=models.CASCADE)
    target_graduation_years = models.ManyToManyField(GraduationYear, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    @property
    def is_registration_open(self):
        now = timezone.now()
        if self.registration_deadline:
            return now < self.registration_deadline and self.status == 'upcoming'
        return self.status == 'upcoming'

    @property
    def attendee_count(self):
        return self.eventregistration_set.filter(status='confirmed').count()

    class Meta:
        ordering = ['-start_date']
        verbose_name = "Event"
        verbose_name_plural = "Events"


class EventRegistration(models.Model):
    REGISTRATION_STATUS = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('waitlist', 'Waitlist'),
    ]
    
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    alumni = models.ForeignKey(Alumni, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=REGISTRATION_STATUS, default='pending')
    registration_date = models.DateTimeField(auto_now_add=True)
    payment_status = models.BooleanField(default=False)
    special_requirements = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.alumni.full_name} - {self.event.title}"

    class Meta:
        unique_together = ['event', 'alumni']
        ordering = ['-registration_date']
        verbose_name = "Event Registration"
        verbose_name_plural = "Event Registrations"


class JobPosting(models.Model):
    JOB_TYPES = [
        ('full_time', 'Full Time'),
        ('part_time', 'Part Time'),
        ('contract', 'Contract'),
        ('internship', 'Internship'),
        ('freelance', 'Freelance'),
    ]
    
    EXPERIENCE_LEVELS = [
        ('entry', 'Entry Level (0-2 years)'),
        ('mid', 'Mid Level (3-5 years)'),
        ('senior', 'Senior Level (6-10 years)'),
        ('executive', 'Executive Level (10+ years)'),
    ]
    
    title = models.CharField(max_length=200)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    description = models.TextField()
    requirements = models.TextField(null=True, blank=True)
    
    # Job Details
    job_type = models.CharField(max_length=20, choices=JOB_TYPES)
    experience_level = models.CharField(max_length=20, choices=EXPERIENCE_LEVELS, default='mid')
    location = models.CharField(max_length=200)
    is_remote = models.BooleanField(default=False)
    
    # Compensation
    salary_min = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    salary_max = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default='USD')
    
    # Application
    application_deadline = models.DateTimeField(null=True, blank=True)
    application_email = models.EmailField(blank=True)
    application_url = models.URLField(blank=True)
    
    # Posting Details
    posted_by = models.ForeignKey(Alumni, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} at {self.company.name}"

    @property
    def is_application_open(self):
        if self.application_deadline:
            return timezone.now() < self.application_deadline and self.is_active
        return self.is_active

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Job Posting"
        verbose_name_plural = "Job Postings"


class JobApplication(models.Model):
    APPLICATION_STATUS = [
        ('applied', 'Applied'),
        ('reviewed', 'Under Review'),
        ('shortlisted', 'Shortlisted'),
        ('interviewed', 'Interviewed'),
        ('offered', 'Offered'),
        ('hired', 'Hired'),
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn'),
    ]
    
    job = models.ForeignKey(JobPosting, on_delete=models.CASCADE)
    applicant = models.ForeignKey(Alumni, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=APPLICATION_STATUS, default='applied')
    cover_letter = models.TextField(blank=True)
    resume = models.FileField(upload_to='resumes/', blank=True, null=True)
    application_date = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.applicant.full_name} - {self.job.title}"

    class Meta:
        unique_together = ['job', 'applicant']
        ordering = ['-application_date']
        verbose_name = "Job Application"
        verbose_name_plural = "Job Applications"


class Donation(models.Model):
    DONATION_TYPES = [
        ('general', 'General Fund'),
        ('scholarship', 'Scholarship Fund'),
        ('infrastructure', 'Infrastructure'),
        ('research', 'Research Fund'),
        ('emergency', 'Emergency Fund'),
        ('other', 'Other'),
    ]
    
    PAYMENT_STATUS = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    donor = models.ForeignKey(Alumni, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    donation_type = models.CharField(max_length=20, choices=DONATION_TYPES)
    
    # Payment Details
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    payment_method = models.CharField(max_length=50, blank=True)
    transaction_id = models.CharField(max_length=100, blank=True)
    
    # Recognition
    is_anonymous = models.BooleanField(default=False)
    public_message = models.TextField(blank=True)
    
    # Metadata
    campaign = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        donor_name = "Anonymous" if self.is_anonymous else self.donor.full_name
        return f"{donor_name} - {self.currency} {self.amount}"

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Donation"
        verbose_name_plural = "Donations"


class MentorshipProgram(models.Model):
    PROGRAM_STATUS = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('paused', 'Paused'),
        ('cancelled', 'Cancelled'),
    ]
    
    mentor = models.ForeignKey(Alumni, on_delete=models.CASCADE, related_name='mentoring_programs')
    mentee = models.ForeignKey(Alumni, on_delete=models.CASCADE, related_name='mentee_programs')
    
    # Program Details
    focus_area = models.CharField(max_length=100)
    goals = models.TextField()
    duration_months = models.IntegerField(default=6)
    
    # Status and Dates
    status = models.CharField(max_length=20, choices=PROGRAM_STATUS, default='active')
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    
    # Feedback
    mentor_feedback = models.TextField(blank=True)
    mentee_feedback = models.TextField(blank=True)
    coordinator_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.mentor.full_name} mentoring {self.mentee.full_name}"

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Mentorship Program"
        verbose_name_plural = "Mentorship Programs"


class News(models.Model):
    NEWS_CATEGORIES = [
        ('general', 'General News'),
        ('alumni_spotlight', 'Alumni Spotlight'),
        ('achievements', 'Achievements'),
        ('events', 'Events'),
        ('careers', 'Career News'),
        ('institution', 'Institution Updates'),
    ]
    
    title = models.CharField(max_length=200)
    content = models.TextField()
    category = models.CharField(max_length=20, choices=NEWS_CATEGORIES, default='general')
    
    # Media
    featured_image = models.ImageField(upload_to='news_images/', blank=True, null=True)
    
    # Publishing
    author = models.ForeignKey(AlumniCoordinator, on_delete=models.CASCADE)
    is_published = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    publish_date = models.DateTimeField(null=True, blank=True)
    
    # SEO
    slug = models.SlugField(unique=True, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['-created_at']
        verbose_name = "News Article"
        verbose_name_plural = "News Articles"


class Message(models.Model):
    MESSAGE_STATUS = [
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('read', 'Read'),
    ]
    
    SENDER_TYPES = [
        ('alumni', 'Alumni'),
        ('admin', 'Admin'),
        ('coordinator', 'Coordinator'),
    ]
    
    # Sender can be Alumni, Admin, or Coordinator
    sender_type = models.CharField(max_length=20, choices=SENDER_TYPES, default='alumni')
    sender_alumni = models.ForeignKey(Alumni, on_delete=models.CASCADE, related_name='sent_messages', null=True, blank=True)
    sender_admin = models.ForeignKey(Admin, on_delete=models.CASCADE, related_name='sent_messages', null=True, blank=True)
    sender_coordinator = models.ForeignKey(AlumniCoordinator, on_delete=models.CASCADE, related_name='sent_messages', null=True, blank=True)
    
    # Recipient is always an Alumni
    recipient = models.ForeignKey(Alumni, on_delete=models.CASCADE, related_name='received_messages')
    subject = models.CharField(max_length=200)
    content = models.TextField()
    status = models.CharField(max_length=20, choices=MESSAGE_STATUS, default='sent')
    
    # Attachments
    attachment = models.FileField(upload_to='message_attachments/', blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        sender_name = self.get_sender_name()
        return f"From {sender_name} to {self.recipient.full_name}: {self.subject}"
    
    def get_sender_name(self):
        """Get the sender's name based on sender type"""
        if self.sender_type == 'alumni' and self.sender_alumni:
            return self.sender_alumni.full_name
        elif self.sender_type == 'admin' and self.sender_admin:
            return f"{self.sender_admin.admin.first_name} {self.sender_admin.admin.last_name}"
        elif self.sender_type == 'coordinator' and self.sender_coordinator:
            return f"{self.sender_coordinator.admin.first_name} {self.sender_coordinator.admin.last_name}"
        return "Unknown Sender"
    
    def get_sender_role(self):
        """Get the sender's role for display"""
        if self.sender_type == 'alumni':
            return "Alumni"
        elif self.sender_type == 'admin':
            return "Administrator"
        elif self.sender_type == 'coordinator':
            return "Alumni Coordinator"
        return "Unknown"
    
    def get_sender_profile(self):
        """Return the CustomUser profile for the sender if available."""
        if self.sender_type == 'alumni' and self.sender_alumni:
            return self.sender_alumni.admin
        if self.sender_type == 'admin' and self.sender_admin:
            return self.sender_admin.admin
        if self.sender_type == 'coordinator' and self.sender_coordinator:
            return self.sender_coordinator.admin
        return None

    def get_sender_email(self):
        """Return the sender's email address if available."""
        profile = self.get_sender_profile()
        return getattr(profile, 'email', '')

    def is_from_user(self, user):
        """Check if this message was sent by the provided user."""
        if not user or not getattr(user, 'is_authenticated', False):
            return False
        if self.sender_type == 'alumni':
            alumni = getattr(user, 'alumni', None)
            return alumni and self.sender_alumni_id == alumni.id
        if self.sender_type == 'admin':
            admin_profile = getattr(user, 'admin', None)
            return admin_profile and self.sender_admin_id == admin_profile.id
        if self.sender_type == 'coordinator':
            coordinator = getattr(user, 'alumnicoordinator', None)
            return coordinator and self.sender_coordinator_id == coordinator.id
        return False

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Message"
        verbose_name_plural = "Messages"


class MessageReply(models.Model):
    """Threaded replies for messages allowing unlimited depth."""
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='replies')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    sender_type = models.CharField(max_length=20, choices=Message.SENDER_TYPES)
    sender_alumni = models.ForeignKey(Alumni, on_delete=models.CASCADE, related_name='message_replies', null=True, blank=True)
    sender_admin = models.ForeignKey(Admin, on_delete=models.CASCADE, related_name='message_replies', null=True, blank=True)
    sender_coordinator = models.ForeignKey(AlumniCoordinator, on_delete=models.CASCADE, related_name='message_replies', null=True, blank=True)
    content = models.TextField()
    attachment = models.FileField(upload_to='message_attachments/replies/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = "Message Reply"
        verbose_name_plural = "Message Replies"

    def __str__(self):
        return f"Reply by {self.get_sender_name()} on {self.message}"

    def get_sender_name(self):
        if self.sender_type == 'alumni' and self.sender_alumni:
            return self.sender_alumni.full_name
        if self.sender_type == 'admin' and self.sender_admin:
            return f"{self.sender_admin.admin.first_name} {self.sender_admin.admin.last_name}"
        if self.sender_type == 'coordinator' and self.sender_coordinator:
            return f"{self.sender_coordinator.admin.first_name} {self.sender_coordinator.admin.last_name}"
        return "Unknown Sender"

    def get_sender_role(self):
        if self.sender_type == 'alumni':
            return "Alumni"
        if self.sender_type == 'admin':
            return "Administrator"
        if self.sender_type == 'coordinator':
            return "Alumni Coordinator"
        return "Unknown"

    def get_sender_profile(self):
        if self.sender_type == 'alumni' and self.sender_alumni:
            return self.sender_alumni.admin
        if self.sender_type == 'admin' and self.sender_admin:
            return self.sender_admin.admin
        if self.sender_type == 'coordinator' and self.sender_coordinator:
            return self.sender_coordinator.admin
        return None

    def get_sender_email(self):
        profile = self.get_sender_profile()
        return getattr(profile, 'email', '')

    def is_from_user(self, user):
        if not user or not getattr(user, 'is_authenticated', False):
            return False
        if self.sender_type == 'alumni':
            alumni = getattr(user, 'alumni', None)
            return alumni and self.sender_alumni_id == alumni.id
        if self.sender_type == 'admin':
            admin_profile = getattr(user, 'admin', None)
            return admin_profile and self.sender_admin_id == admin_profile.id
        if self.sender_type == 'coordinator':
            coordinator = getattr(user, 'alumnicoordinator', None)
            return coordinator and self.sender_coordinator_id == coordinator.id
        return False


class AlumniGroup(models.Model):
    GROUP_TYPES = [
        ('graduation_year', 'Completion Year'),
        ('department', 'Department'),
        ('location', 'Location-based'),
        ('industry', 'Industry'),
        ('interest', 'Interest-based'),
    ]
    
    name = models.CharField(max_length=100)
    description = models.TextField()
    group_type = models.CharField(max_length=20, choices=GROUP_TYPES)
    
    # Group Settings
    is_public = models.BooleanField(default=True)
    requires_approval = models.BooleanField(default=False)
    
    # Management
    admin = models.ForeignKey(Alumni, on_delete=models.CASCADE, related_name='administered_groups')
    members = models.ManyToManyField(Alumni, through='GroupMembership', related_name='groups')
    
    # Media
    group_image = models.ImageField(upload_to='group_images/', blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    @property
    def member_count(self):
        return self.members.count()

    class Meta:
        ordering = ['name']
        verbose_name = "Alumni Group"
        verbose_name_plural = "Alumni Groups"


class GroupMembership(models.Model):
    MEMBERSHIP_STATUS = [
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]
    
    group = models.ForeignKey(AlumniGroup, on_delete=models.CASCADE)
    member = models.ForeignKey(Alumni, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=MEMBERSHIP_STATUS, default='active')
    joined_date = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.member.full_name} in {self.group.name}"

    class Meta:
        unique_together = ['group', 'member']
        ordering = ['-joined_date']
        verbose_name = "Group Membership"
        verbose_name_plural = "Group Memberships"


# Notification Models
class NotificationAlumni(models.Model):
    NOTIFICATION_TYPES = [
        ('event', 'Event Notification'),
        ('job', 'Job Posting'),
        ('message', 'New Message'),
        ('news', 'News Update'),
        ('system', 'System Notification'),
    ]
    
    alumni = models.ForeignKey(Alumni, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='system')
    is_read = models.BooleanField(default=False)
    
    # Optional links
    link_url = models.URLField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Notification for {self.alumni.full_name}: {self.title}"

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Alumni Notification"
        verbose_name_plural = "Alumni Notifications"


class NotificationCoordinator(models.Model):
    coordinator = models.ForeignKey(AlumniCoordinator, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Notification for {self.coordinator.admin.first_name}: {self.title}"

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Coordinator Notification"
        verbose_name_plural = "Coordinator Notifications"


# Feedback Models
class FeedbackAlumni(models.Model):
    FEEDBACK_TYPES = [
        ('general', 'General Feedback'),
        ('technical', 'Technical Issue'),
        ('feature_request', 'Feature Request'),
        ('complaint', 'Complaint'),
        ('suggestion', 'Suggestion'),
    ]
    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]
    
    alumni = models.ForeignKey(Alumni, on_delete=models.CASCADE)
    feedback_type = models.CharField(max_length=20, choices=FEEDBACK_TYPES, default='general')
    subject = models.CharField(max_length=200)
    feedback = models.TextField()
    reply = models.TextField(blank=True)
    is_resolved = models.BooleanField(default=False)
    rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Feedback from {self.alumni.full_name}: {self.subject}"

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Alumni Feedback"
        verbose_name_plural = "Alumni Feedback"


# Like and Comment Models
class Like(models.Model):
    CONTENT_TYPES = [
        ('news', 'News'),
        ('job', 'Job'),
        ('event', 'Event'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    content_type = models.CharField(max_length=10, choices=CONTENT_TYPES)
    object_id = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'content_type', 'object_id']
        ordering = ['-created_at']
        verbose_name = "Like"
        verbose_name_plural = "Likes"
    
    def __str__(self):
        return f"{self.user.get_full_name()} liked {self.content_type} #{self.object_id}"


class Comment(models.Model):
    CONTENT_TYPES = [
        ('news', 'News'),
        ('job', 'Job'),
        ('event', 'Event'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    content_type = models.CharField(max_length=10, choices=CONTENT_TYPES)
    object_id = models.PositiveIntegerField()
    content = models.TextField()
    is_approved = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # For nested comments (replies)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    depth = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Comment"
        verbose_name_plural = "Comments"
    
    def __str__(self):
        return f"Comment by {self.user.get_full_name()} on {self.content_type} #{self.object_id}"
    
    @property
    def reply_count(self):
        return self.replies.filter(is_approved=True).count()
    
    @property
    def like_count(self):
        return CommentLike.objects.filter(comment=self).count()
    
    def get_replies(self):
        return self.replies.filter(is_approved=True).order_by('created_at')
    
    def get_all_nested_replies(self):
        """Get all nested replies recursively"""
        replies = self.get_replies()
        all_replies = []
        for reply in replies:
            all_replies.append(reply)
            all_replies.extend(reply.get_all_nested_replies())
        return all_replies
    
    def save(self, *args, **kwargs):
        """Override save to automatically calculate depth"""
        if self.parent:
            self.depth = self.parent.depth + 1
        else:
            self.depth = 0
        super().save(*args, **kwargs)


class CommentLike(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name='likes')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'comment']
        ordering = ['-created_at']
        verbose_name = "Comment Like"
        verbose_name_plural = "Comment Likes"
    
    def __str__(self):
        return f"{self.user.get_full_name()} liked comment by {self.comment.user.get_full_name()}"


# UPDATED Signal handlers for user profile creation
@receiver(post_save, sender=CustomUser)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Automatically create the appropriate profile when a user is created.
    Superusers are automatically made Admins.
    """
    if created:
        try:
            # If user is superuser or admin, create Admin profile
            if instance.is_superuser or instance.user_type == '1':
                # Ensure user_type is set to Admin for superusers
                if instance.is_superuser and instance.user_type != '1':
                    instance.user_type = '1'
                    instance.save()
                Admin.objects.get_or_create(admin=instance)
            # For regular users, create profile based on user_type
            elif instance.user_type == '2':
                AlumniCoordinator.objects.get_or_create(admin=instance)
            elif instance.user_type == '3':
                Alumni.objects.get_or_create(admin=instance)
        except Exception as e:
            # Log the error but don't crash
            print(f"Error creating user profile: {e}")


@receiver(post_save, sender=CustomUser)
def save_user_profile(sender, instance, **kwargs):
    """
    Ensure profile is saved when user is saved
    """
    try:
        if instance.is_superuser or instance.user_type == '1':
            # Ensure superusers/admins have Admin profile
            admin_profile, created = Admin.objects.get_or_create(admin=instance)
            if not created:
                admin_profile.save()
        elif instance.user_type == '2':
            instance.alumnicoordinator.save()
        elif instance.user_type == '3':
            instance.alumni.save()
    except Exception as e:
        # Handle case where profile doesn't exist yet
        print(f"Error saving user profile: {e}")
