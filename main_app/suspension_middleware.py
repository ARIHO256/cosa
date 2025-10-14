from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from django.utils.deprecation import MiddlewareMixin


class SuspensionMiddleware(MiddlewareMixin):
    """
    Middleware to check if a user's account is suspended and redirect them
    to a suspension notice page if they try to access restricted content.
    """
    
    # URLs that suspended users are allowed to access
    ALLOWED_URLS = [
        'suspension_notice',
        'logout',
        'login_page',
        'user_login',
        'alumni_registration',
    ]
    
    # URLs that require authentication but suspended users can't access
    RESTRICTED_URLS = [
        'admin_home',
        'coordinator_home', 
        'alumni_home',
        'admin_manage_alumni',
        'coordinator_manage_alumni',
        'admin_register_alumni',
        'coordinator_register_alumni',
        'admin_delete_alumni',
        'coordinator_delete_alumni',
        'admin_messages_inbox',
        'coordinator_messages_inbox',
        'admin_send_message',
        'coordinator_send_message',
        'admin_view_message',
        'coordinator_view_message',
        'admin_suspend_user',
        'admin_unsuspend_user',
        'admin_user_suspension_history',
        'admin_export_alumni_excel',
        'admin_export_alumni_by_year_excel',
        'admin_export_alumni_statistics_excel',
        'coordinator_export_alumni_excel',
        'coordinator_export_alumni_by_year_excel',
        'coordinator_export_alumni_statistics_excel',
        'alumni_profile',
        'alumni_edit_profile',
        'alumni_messages_inbox',
        'alumni_send_message',
        'alumni_view_message',
        'alumni_post_job',
        'alumni_jobs',
        'alumni_news',
        'alumni_events',
        'alumni_directory',
        'alumni_notifications',
        'news_detail',
        'job_detail',
        'event_detail',
        'add_comment',
        'add_reply',
        'like_comment',
        'unlike_comment',
    ]
    
    def process_request(self, request):
        # Skip if user is not authenticated
        if not request.user.is_authenticated:
            return None
            
        # Skip if user is not suspended
        if not hasattr(request.user, 'is_suspended') or not request.user.is_suspended:
            return None
            
        # Skip if user is accessing allowed URLs
        current_url_name = request.resolver_match.url_name if request.resolver_match else None
        if current_url_name in self.ALLOWED_URLS:
            return None
            
        # Check if user is trying to access restricted content
        if current_url_name in self.RESTRICTED_URLS or self._is_restricted_path(request.path):
            # Redirect to suspension notice
            return redirect('suspension_notice')
            
        return None
    
    def _is_restricted_path(self, path):
        """
        Check if the current path should be restricted for suspended users.
        """
        restricted_paths = [
            '/admin/',
            '/coordinator/',
            '/alumni/',
            '/news/',
            '/jobs/',
            '/events/',
            '/directory/',
            '/notifications/',
            '/profile/',
            '/messages/',
        ]
        
        return any(path.startswith(restricted) for restricted in restricted_paths)
