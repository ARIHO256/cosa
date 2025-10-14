from django import forms
from django.db import transaction
from django.forms.widgets import DateInput, DateTimeInput, TextInput, Select, CheckboxInput
from django.contrib.auth.forms import UserCreationForm
from django.utils import timezone
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Field, Div, HTML
from crispy_forms.bootstrap import FormActions
from .models import *


def format_alumni_recipient_label(alumni):
    """Consistent label for recipient dropdowns."""
    year_display = alumni.graduation_year.get_year_display() if alumni.graduation_year else 'Year not set'
    student_id = alumni.student_id or 'No COSA ID'
    return f"{alumni.full_name} — {year_display} • {student_id}"


class FormSettings(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(FormSettings, self).__init__(*args, **kwargs)
        # Add Bootstrap classes to all form fields
        for field in self.visible_fields():
            field.field.widget.attrs['class'] = 'form-control'


class CustomUserForm(FormSettings):
    email = forms.EmailField(required=True)
    gender = forms.ChoiceField(choices=CustomUser.GENDER, required=False)
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    phone_number = forms.CharField(required=False, max_length=20)
    address = forms.CharField(widget=forms.Textarea, required=False)
    password = forms.CharField(widget=forms.PasswordInput)
    profile_pic = forms.ImageField(required=False)

    def __init__(self, *args, **kwargs):
        super(CustomUserForm, self).__init__(*args, **kwargs)
        
        if kwargs.get('instance'):
            instance = kwargs.get('instance').admin.__dict__
            self.fields['password'].required = False
            for field in CustomUserForm.Meta.fields:
                self.fields[field].initial = instance.get(field)
            if self.instance.pk is not None:
                self.fields['password'].widget.attrs['placeholder'] = "Fill this only if you wish to update password"

    def clean_email(self, *args, **kwargs):
        formEmail = self.cleaned_data['email'].lower()
        if self.instance.pk is None:  # Insert
            if CustomUser.objects.filter(email=formEmail).exists():
                raise forms.ValidationError("The given email is already registered")
        else:  # Update
            dbEmail = self.Meta.model.objects.get(id=self.instance.pk).admin.email.lower()
            if dbEmail != formEmail:  # There has been changes
                if CustomUser.objects.filter(email=formEmail).exists():
                    raise forms.ValidationError("The given email is already registered")
        return formEmail

    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'gender', 'phone_number', 'password', 'profile_pic', 'address']


class AlumniRegistrationForm(UserCreationForm):
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    email = forms.EmailField(required=True)
    graduation_year = forms.ModelChoiceField(queryset=GraduationYear.objects.filter(is_active=True), required=True)
    degree = forms.ModelChoiceField(queryset=Degree.objects.filter(is_active=True), required=True)
    
    class Meta:
        model = CustomUser
        fields = ('first_name', 'last_name', 'email', 'password1', 'password2')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault('class', 'form-check-input')
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault('class', 'form-select')
            else:
                widget.attrs.setdefault('class', 'form-control')
                widget.attrs.setdefault('placeholder', field.label)
        
        self.fields['password1'].widget.attrs.update({'autocomplete': 'new-password'})
        self.fields['password2'].widget.attrs.update({'autocomplete': 'new-password'})
        self.fields['email'].widget.attrs.update({'autocomplete': 'email'})
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('first_name', css_class='form-group col-md-6 mb-0'),
                Column('last_name', css_class='form-group col-md-6 mb-0'),
                css_class='form-row'
            ),
            'email',
            Row(
                Column('graduation_year', css_class='form-group col-md-6 mb-0'),
                Column('degree', css_class='form-group col-md-6 mb-0'),
                css_class='form-row'
            ),
            'password1',
            'password2',
            FormActions(
                Submit('submit', 'Register as Alumni', css_class='btn btn-primary btn-lg')
            )
        )

    def save(self, commit=True):
        user = super().save(commit=False)
        user.user_type = '3'  # Alumni
        user.email = self.cleaned_data['email']
        user.is_verified = False  # Requires admin approval
        user.is_active = True     # Can login but with limited access

        if not commit:
            return user

        with transaction.atomic():
            user.save()
            # Ensure a single Alumni profile (signals may create one already)
            alumni, _ = Alumni.objects.get_or_create(admin=user)
            alumni.graduation_year = self.cleaned_data['graduation_year']
            alumni.degree = self.cleaned_data['degree']
            if not getattr(alumni, 'privacy_level', None):
                alumni.privacy_level = 'private'
            alumni.save()
        return user


class AlumniProfileForm(FormSettings):
    class Meta:
        model = Alumni
        fields = [
            'degree', 'graduation_year', 'current_company', 'job_title',
            'employment_status', 'industry', 'linkedin_profile', 'date_of_birth',
            'current_city', 'current_country', 'bio', 'achievements', 'skills',
            'privacy_level', 'allow_contact', 'newsletter_subscription',
            'is_mentor', 'is_job_seeker', 'willing_to_hire'
        ]
        widgets = {
            'date_of_birth': DateInput(attrs={'type': 'date'}),
            'bio': forms.Textarea(attrs={'rows': 4}),
            'achievements': forms.Textarea(attrs={'rows': 3}),
            'skills': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Enter skills separated by commas'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Div(
                HTML('<h4>Academic Information</h4>'),
                Row(
                    Column('degree', css_class='form-group col-md-6 mb-0'),
                    Column('graduation_year', css_class='form-group col-md-6 mb-0'),
                ),
                css_class='card-body'
            ),
            Div(
                HTML('<h4>Professional Information</h4>'),
                Row(
                    Column('current_company', css_class='form-group col-md-6 mb-0'),
                    Column('job_title', css_class='form-group col-md-6 mb-0'),
                ),
                Row(
                    Column('employment_status', css_class='form-group col-md-6 mb-0'),
                    Column('industry', css_class='form-group col-md-6 mb-0'),
                ),
                'linkedin_profile',
                css_class='card-body'
            ),
            Div(
                HTML('<h4>Personal Information</h4>'),
                Row(
                    Column('date_of_birth', css_class='form-group col-md-4 mb-0'),
                    Column('current_city', css_class='form-group col-md-4 mb-0'),
                    Column('current_country', css_class='form-group col-md-4 mb-0'),
                ),
                'bio',
                'achievements',
                'skills',
                css_class='card-body'
            ),
            Div(
                HTML('<h4>Privacy & Engagement</h4>'),
                'privacy_level',
                Row(
                    Column(Field('allow_contact', css_class='form-check-input'), css_class='form-group col-md-4 mb-0'),
                    Column(Field('newsletter_subscription', css_class='form-check-input'), css_class='form-group col-md-4 mb-0'),
                    Column(Field('is_mentor', css_class='form-check-input'), css_class='form-group col-md-4 mb-0'),
                ),
                Row(
                    Column(Field('is_job_seeker', css_class='form-check-input'), css_class='form-group col-md-6 mb-0'),
                    Column(Field('willing_to_hire', css_class='form-check-input'), css_class='form-group col-md-6 mb-0'),
                ),
                css_class='card-body'
            ),
            FormActions(
                Submit('submit', 'Update Profile', css_class='btn btn-primary')
            )
        )


class JobPostingForm(FormSettings):
    class Meta:
        model = JobPosting
        fields = [
            'title', 'company', 'description', 'job_type', 'location', 'is_remote'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Only require the absolutely essential fields
        self.fields['title'].required = True
        self.fields['company'].required = True
        self.fields['description'].required = True
        self.fields['job_type'].required = True
        self.fields['location'].required = True
        
        # Set widget attributes
        self.fields['job_type'].widget.attrs['class'] = 'form-select'
        self.fields['location'].widget.attrs['placeholder'] = 'e.g., Kampala Uganda, NY or Remote'
        
        # Add simple help text
        self.fields['title'].help_text = 'Clear and descriptive job title'
        self.fields['description'].help_text = 'Brief description of the role and what you\'re looking for'
        self.fields['location'].help_text = 'Where the job is located'
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'title',
            'company',
            'description',
            Row(
                Column('job_type', css_class='form-group col-md-6 mb-0'),
                Column('location', css_class='form-group col-md-6 mb-0'),
            ),
            Field('is_remote', css_class='form-check-input'),
            FormActions(
                Submit('submit', 'Post Job', css_class='btn btn-success btn-lg')
            )
        )
    
    def clean(self):
        cleaned_data = super().clean()
        return cleaned_data


class EventForm(FormSettings):
    class Meta:
        model = Event
        fields = [
            'title', 'description', 'event_type', 'start_date', 'end_date',
            'registration_deadline', 'is_virtual', 'venue', 'address', 'virtual_link',
            'max_attendees', 'registration_fee', 'requires_approval', 'featured_image',
            'target_graduation_years'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'start_date': DateInput(attrs={'type': 'datetime-local'}),
            'end_date': DateInput(attrs={'type': 'datetime-local'}),
            'registration_deadline': DateInput(attrs={'type': 'datetime-local'}),
            'address': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'title',
            'description',
            'event_type',
            Row(
                Column('start_date', css_class='form-group col-md-6 mb-0'),
                Column('end_date', css_class='form-group col-md-6 mb-0'),
            ),
            'registration_deadline',
            Field('is_virtual', css_class='form-check-input'),
            'venue',
            'address',
            'virtual_link',
            Row(
                Column('max_attendees', css_class='form-group col-md-4 mb-0'),
                Column('registration_fee', css_class='form-group col-md-4 mb-0'),
                Column(Field('requires_approval', css_class='form-check-input'), css_class='form-group col-md-4 mb-0'),
            ),
            'featured_image',
            'target_graduation_years',
            FormActions(
                Submit('submit', 'Create Event', css_class='btn btn-primary')
            )
        )


class EventRegistrationForm(forms.Form):
    special_requirements = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False,
        help_text="Any special dietary requirements, accessibility needs, etc."
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'special_requirements',
            FormActions(
                Submit('submit', 'Register for Event', css_class='btn btn-success')
            )
        )


class DonationForm(FormSettings):
    class Meta:
        model = Donation
        fields = ['amount', 'currency', 'donation_type', 'is_anonymous', 'public_message', 'campaign']
        widgets = {
            'public_message': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('amount', css_class='form-group col-md-6 mb-0'),
                Column('currency', css_class='form-group col-md-6 mb-0'),
            ),
            'donation_type',
            'campaign',
            Field('is_anonymous', css_class='form-check-input'),
            'public_message',
            FormActions(
                Submit('submit', 'Donate Now', css_class='btn btn-success')
            )
        )


class MessageForm(FormSettings):
    class Meta:
        model = Message
        fields = ['recipient', 'subject', 'content', 'attachment']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter recipients to only show alumni with contact permission
        self.fields['recipient'].queryset = Alumni.objects.filter(allow_contact=True)
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'recipient',
            'subject',
            'content',
            'attachment',
            FormActions(
                Submit('submit', 'Send Message', css_class='btn btn-primary')
            )
        )


class MessageEditForm(FormSettings):
    class Meta:
        model = Message
        fields = ['subject', 'content', 'attachment']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['subject'].required = False
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'subject',
            'content',
            'attachment',
            FormActions(
                Submit('submit', 'Save Changes', css_class='btn btn-primary')
            )
        )


class AdminMessageForm(FormSettings):
    class Meta:
        model = Message
        fields = ['recipient', 'subject', 'content', 'attachment']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Show all verified alumni as potential recipients
        recipient_field = self.fields['recipient']
        recipient_field.queryset = Alumni.objects.filter(admin__is_verified=True).select_related('admin', 'graduation_year', 'degree')
        recipient_field.label = "Send to Alumni"
        recipient_field.empty_label = "Select an alumni recipient"
        recipient_field.widget.attrs['class'] = 'form-select'
        recipient_field.label_from_instance = format_alumni_recipient_label
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h5 class="mb-3"><i class="fas fa-envelope me-2"></i>Send Message to Alumni</h5>'),
            'recipient',
            'subject',
            'content',
            'attachment',
            FormActions(
                Submit('submit', 'Send Message', css_class='btn btn-success btn-lg')
            )
        )


class CoordinatorMessageForm(FormSettings):
    class Meta:
        model = Message
        fields = ['recipient', 'subject', 'content', 'attachment']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Show all verified alumni as potential recipients
        recipient_field = self.fields['recipient']
        recipient_field.queryset = Alumni.objects.filter(admin__is_verified=True).select_related('admin', 'graduation_year', 'degree')
        recipient_field.label = "Send to Alumni"
        recipient_field.empty_label = "Select an alumni recipient"
        recipient_field.widget.attrs['class'] = 'form-select'
        recipient_field.label_from_instance = format_alumni_recipient_label
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h5 class="mb-3"><i class="fas fa-envelope me-2"></i>Send Message to Alumni</h5>'),
            'recipient',
            'subject',
            'content',
            'attachment',
            FormActions(
                Submit('submit', 'Send Message', css_class='btn btn-primary btn-lg')
            )
        )


class MessageReplyForm(FormSettings):
    class Meta:
        model = MessageReply
        fields = ['content', 'attachment']
        widgets = {
            'content': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Write your reply...',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['content'].label = "Reply"
        self.fields['attachment'].label = "Attachment (optional)"


class AlumniSearchForm(forms.Form):
    YEAR_CHOICES = [('','All Years')] + [(str(year), str(year)) for year in range(2004, 2026)]
    LEVEL_CHOICES = [
        ('', 'All Levels'),
        ('O_level', 'O Level'),
        ('A_level', 'A Level'),
    ]

    search = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Search by name, company, or skills...'})
    )
    graduation_year = forms.ChoiceField(
        choices=YEAR_CHOICES,
        required=False
    )
    degree = forms.ChoiceField(
        choices=LEVEL_CHOICES,
        required=False
    )
    is_mentor = forms.BooleanField(required=False, label="Available as Mentor")
    willing_to_hire = forms.BooleanField(required=False, label="Willing to Hire")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['search'].label = 'Search Alumni'
        self.fields['graduation_year'].label = 'Completion Year'
        self.fields['degree'].label = 'Level'

        select_fields = ['graduation_year', 'degree']
        for name in select_fields:
            self.fields[name].widget.attrs.setdefault('class', 'form-select')

        for name in ['search']:
            self.fields[name].widget.attrs.setdefault('class', 'form-control')

        for name in ['is_mentor', 'willing_to_hire']:
            self.fields[name].widget.attrs.setdefault('class', 'form-check-input')


class SuspendUserForm(FormSettings):
    reason = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4, 'placeholder': 'Enter reason for suspension...'}),
        required=True,
        help_text="Please provide a clear reason for suspending this account"
    )
    suspension_type = forms.ChoiceField(
        choices=[
            ('permanent', 'Permanent Suspension'),
            ('temporary', 'Temporary Suspension'),
        ],
        widget=forms.RadioSelect,
        initial='temporary'
    )
    expires_at = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        help_text="Leave empty for permanent suspension"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h5 class="mb-3"><i class="fas fa-ban me-2"></i>Suspend User Account</h5>'),
            'reason',
            'suspension_type',
            'expires_at',
            FormActions(
                Submit('submit', 'Suspend Account', css_class='btn btn-danger btn-lg')
            )
        )
    
    def clean(self):
        cleaned_data = super().clean()
        suspension_type = cleaned_data.get('suspension_type')
        expires_at = cleaned_data.get('expires_at')
        
        if suspension_type == 'temporary' and not expires_at:
            raise forms.ValidationError("Please specify an expiration date for temporary suspension.")
        
        if suspension_type == 'permanent' and expires_at:
            raise forms.ValidationError("Permanent suspension should not have an expiration date.")
        
        if expires_at and expires_at <= timezone.now():
            raise forms.ValidationError("Expiration date must be in the future.")
        
        return cleaned_data


class UnsuspendUserForm(FormSettings):
    reason = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Enter reason for unsuspending...'}),
        required=False,
        help_text="Optional: Reason for unsuspending this account"
    )
    graduation_year = forms.ChoiceField(
        choices=AlumniSearchForm.YEAR_CHOICES,
        required=False,
        label="Year"
    )
    degree = forms.ChoiceField(
        choices=AlumniSearchForm.LEVEL_CHOICES,
        required=False,
        label="Level"
    )
    employment_status = forms.ChoiceField(
        choices=[('', 'All Status')] + Alumni.EMPLOYMENT_STATUS,
        required=False
    )
    current_city = forms.ChoiceField(
        choices=[('', 'All Cities')],
        required=False,
        label="Current City"
    )
    industry = forms.CharField(max_length=100, required=False)
    is_mentor = forms.BooleanField(required=False, label="Available as Mentor")
    willing_to_hire = forms.BooleanField(required=False, label="Willing to Hire")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'GET'
        self.helper.layout = Layout(
            'search',
            Row(
                Column('graduation_year', css_class='form-group col-md-6 mb-0'),
                Column('degree', css_class='form-group col-md-6 mb-0'),
            ),
            Row(
                Column('employment_status', css_class='form-group col-md-6 mb-0'),
                Column('current_city', css_class='form-group col-md-6 mb-0'),
            ),
            'industry',
            Row(
                Column(Field('is_mentor', css_class='form-check-input'), css_class='form-group col-md-6 mb-0'),
                Column(Field('willing_to_hire', css_class='form-check-input'), css_class='form-group col-md-6 mb-0'),
            ),
            FormActions(
                Submit('submit', 'Search Alumni', css_class='btn btn-primary')
            )
        )
        self.fields['current_city'].choices = AlumniSearchForm.get_city_choices()
        select_fields = ['graduation_year', 'degree', 'employment_status', 'current_city']
        for name in select_fields:
            self.fields[name].widget.attrs.setdefault('class', 'form-select')
        for name in ['industry', 'reason']:
            self.fields[name].widget.attrs.setdefault('class', 'form-control')
        for name in ['is_mentor', 'willing_to_hire']:
            self.fields[name].widget.attrs.setdefault('class', 'form-check-input')


class CompanyForm(FormSettings):
    class Meta:
        model = Company
        fields = ['name', 'website', 'industry', 'size', 'location', 'description', 'logo']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'name',
            Row(
                Column('website', css_class='form-group col-md-6 mb-0'),
                Column('industry', css_class='form-group col-md-6 mb-0'),
            ),
            Row(
                Column('size', css_class='form-group col-md-6 mb-0'),
                Column('location', css_class='form-group col-md-6 mb-0'),
            ),
            'description',
            'logo',
            FormActions(
                Submit('submit', 'Save Company', css_class='btn btn-primary')
            )
        )


class FeedbackAlumniForm(FormSettings):
    class Meta:
        model = FeedbackAlumni
        fields = ['feedback_type', 'subject', 'rating', 'feedback']
        widgets = {
            'feedback': forms.Textarea(attrs={'rows': 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        rating_field = self.fields['rating']
        rating_field.required = False
        rating_field.widget = forms.RadioSelect(choices=rating_field.choices)
        rating_field.widget.attrs['class'] = 'rating-star-inputs'
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'feedback_type',
            'subject',
            'rating',
            'feedback',
            FormActions(
                Submit('submit', 'Submit Feedback', css_class='btn btn-primary')
            )
        )


# Legacy forms for backward compatibility (can be removed later)
class AdminForm(CustomUserForm):
    def __init__(self, *args, **kwargs):
        super(AdminForm, self).__init__(*args, **kwargs)

    class Meta(CustomUserForm.Meta):
        model = Admin
        fields = CustomUserForm.Meta.fields


class DepartmentForm(FormSettings):
    class Meta:
        model = Department
        fields = ['name', 'code', 'description']


class DegreeForm(FormSettings):
    class Meta:
        model = Degree
        fields = ['name', 'degree_type', 'department', 'duration_years']


class GraduationYearForm(FormSettings):
    class Meta:
        model = GraduationYear
        fields = ['year']
        widgets = {
            'year': forms.NumberInput(attrs={'min': 1900, 'max': 2100}),
        }


class AdminProfileForm(FormSettings):
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'address', 'profile_pic']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('first_name', css_class='form-group col-md-6 mb-0'),
                Column('last_name', css_class='form-group col-md-6 mb-0'),
            ),
            'email',
            'phone_number',
            'address',
            'profile_pic',
            FormActions(
                Submit('submit', 'Update Profile', css_class='btn btn-primary')
            )
        )


class CommentForm(FormSettings):
    content = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': 'Write your comment...',
            'class': 'form-control'
        }),
        max_length=1000,
        help_text='Maximum 1000 characters'
    )
    
    class Meta:
        model = Comment
        fields = ['content']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'content',
            FormActions(
                Submit('submit', 'Post Comment', css_class='btn btn-primary btn-sm')
            )
        )
