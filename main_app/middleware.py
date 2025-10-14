from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin


class LoginCheckMiddleWare(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        modulename = view_func.__module__
        user = request.user  # Who is the current user ?

        if user.is_authenticated:
            if user.user_type == '1':  # Admin
                if modulename == 'main_app.student_views':
                    return redirect(reverse('admin_home'))
            elif user.user_type == '2':  # Coordinator
                if modulename in ('main_app.student_views', 'main_app.hod_views'):
                    return redirect(reverse('coordinator_home'))
            elif user.user_type == '3':  # Alumni
                if modulename in ('main_app.hod_views', 'main_app.staff_views'):
                    return redirect(reverse('alumni_home'))
            else:  # Unknown user type
                return redirect(reverse('login_page'))
        else:
            public_urls = {
                'home',
                'login_page',
                'user_login',
                'alumni_registration',
                'register',
                'public_alumni_directory',
                'public_job_board',
                'public_events',
                'public_news',
                'about_cosa',
                'contact_us',
                'job_detail',
                'event_detail',
                'news_detail',
                'showFirebaseJS',
                'check_email_availability',
            }

            resolver_match = getattr(request, 'resolver_match', None)
            current_url = resolver_match.url_name if resolver_match else None

            if (current_url in public_urls or
                    modulename == 'django.contrib.auth.views' or
                    request.path.startswith(settings.STATIC_URL) or
                    request.path.startswith(settings.MEDIA_URL)):
                return None

            return redirect(reverse('login_page'))
