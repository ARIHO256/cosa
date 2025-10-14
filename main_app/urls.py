"""COSA Alumni Management System URL Configuration"""

from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

from . import views, admin_views, coordinator_views, alumni_views

urlpatterns = [
    # Public URLs
    path("", views.login_page, name='home'),
    path("about/", views.about_cosa, name='about_cosa'),
    path("contact/", views.contact_us, name='contact_us'),
    path("alumni-directory/", views.public_alumni_directory, name='public_alumni_directory'),
    path("alumni-directory/data/", views.public_alumni_directory_data, name='public_alumni_directory_data'),
    path("jobs/", views.public_job_board, name='public_job_board'),
    path("job/<int:job_id>/", views.job_detail, name='job_detail'),
    path("events/", views.public_events, name='public_events'),
    path("event/<int:event_id>/", views.event_detail, name='event_detail'),
    path("news/", views.public_news, name='public_news'),
    path("news/<slug:slug>/", views.news_detail, name='news_detail'),
    
    # Authentication
    path("login/", views.login_page, name='login_page'),
    path("doLogin/", views.doLogin, name='user_login'),
    path("logout_user/", views.logout_user, name='user_logout'),
    path("register/alumni/", views.alumni_registration, name='alumni_registration'),
    path("register/", views.alumni_registration, name='register'),
    path("pending-approval/", views.pending_approval, name='pending_approval'),
    path("suspension-notice/", views.suspension_notice, name='suspension_notice'),
    
    # AJAX endpoints
    path("check_email_availability/", views.check_email_availability, name='check_email_availability'),
    path("firebase-messaging-sw.js", views.showFirebaseJS, name='showFirebaseJS'),
    
    # Like and Comment functionality
    path("toggle_like/", views.toggle_like, name='toggle_like'),
    path("add_comment/", views.add_comment, name='add_comment'),
    path("add_reply/", views.add_reply, name='add_reply'),
    path("toggle_comment_like/", views.toggle_comment_like, name='toggle_comment_like'),
    
    # System Administrator URLs
    path("admin/home/", admin_views.admin_home, name='admin_home'),
    path("admin/profile/", admin_views.admin_profile, name='admin_profile'),
    path("admin/coordinators/", admin_views.manage_coordinators, name='manage_coordinators'),
    path("admin/coordinators/add/", admin_views.add_coordinator, name='add_coordinator'),
    path("admin/coordinators/edit/<int:coordinator_id>/", admin_views.edit_coordinator, name='edit_coordinator'),
    path("admin/coordinators/delete/<int:coordinator_id>/", admin_views.delete_coordinator, name='delete_coordinator'),
    
    path("admin/alumni/", admin_views.manage_alumni, name='manage_alumni'),
    path("admin/alumni/register/", admin_views.register_alumni, name='admin_register_alumni'),
    path("admin/alumni/verify/<int:alumni_id>/", admin_views.verify_alumni, name='verify_alumni'),
    path("admin/alumni/delete/<int:alumni_id>/", admin_views.delete_alumni, name='admin_delete_alumni'),
    
    path("admin/departments/", admin_views.manage_departments, name='manage_departments'),
    path("admin/departments/add/", admin_views.add_department, name='add_department'),
    path("admin/departments/edit/<int:department_id>/", admin_views.edit_department, name='edit_department'),
    path("admin/departments/delete/<int:department_id>/", admin_views.delete_department, name='delete_department'),
    
    path("admin/degrees/", admin_views.manage_degrees, name='manage_degrees'),
    path("admin/degrees/add/", admin_views.add_degree, name='add_degree'),
    path("admin/degrees/edit/<int:degree_id>/", admin_views.edit_degree, name='edit_degree'),
    path("admin/degrees/delete/<int:degree_id>/", admin_views.delete_degree, name='delete_degree'),
    
    path("admin/graduation-years/", admin_views.manage_graduation_years, name='manage_graduation_years'),
    path("admin/graduation-years/add/", admin_views.add_graduation_year, name='add_graduation_year'),
    path("admin/graduation-years/edit/<int:year_id>/", admin_views.edit_graduation_year, name='edit_graduation_year'),
    path("admin/graduation-years/delete/<int:year_id>/", admin_views.delete_graduation_year, name='delete_graduation_year'),
    
    path("admin/companies/", admin_views.manage_companies, name='manage_companies'),
    path("admin/companies/verify/<int:company_id>/", admin_views.verify_company, name='verify_company'),
    path("admin/companies/edit/<int:company_id>/", admin_views.edit_company, name='edit_company'),
    path("admin/companies/delete/<int:company_id>/", admin_views.delete_company, name='delete_company'),
    
    path("admin/analytics/", admin_views.system_analytics, name='system_analytics'),
    path("admin/settings/", admin_views.system_settings, name='system_settings'),
    path("admin/bulk-operations/", admin_views.bulk_operations, name='bulk_operations'),
    path("admin/fcmtoken/", admin_views.admin_fcmtoken, name='admin_fcmtoken'),
    path("admin/stats/", admin_views.get_system_stats, name='get_system_stats'),
    
    # Admin Messaging
    path("admin/messages/", admin_views.admin_messages_inbox, name='admin_messages_inbox'),
    path("admin/messages/send/", admin_views.admin_send_message, name='admin_send_message'),
    path("admin/messages/send/<int:recipient_id>/", admin_views.admin_send_message, name='admin_send_message_to'),
    path("admin/messages/view/<int:message_id>/", admin_views.admin_view_message, name='admin_view_message'),
    
    # Admin Export URLs
    path("admin/export/alumni/<str:export_type>/", admin_views.export_alumni_excel, name='admin_export_alumni_excel'),
    path("admin/export/alumni/year/<int:year_id>/", admin_views.export_alumni_by_year_excel, name='admin_export_alumni_by_year_excel'),
    path("admin/export/statistics/", admin_views.export_alumni_statistics_excel, name='admin_export_alumni_statistics_excel'),
    
    # Admin User Suspension URLs
    path("admin/suspend-user/<int:user_id>/", admin_views.admin_suspend_user, name='admin_suspend_user'),
    path("admin/unsuspend-user/<int:user_id>/", admin_views.admin_unsuspend_user, name='admin_unsuspend_user'),
    path("admin/user-suspension-history/<int:user_id>/", admin_views.admin_user_suspension_history, name='admin_user_suspension_history'),
    
    # Alumni Coordinator URLs
    path("coordinator/home/", coordinator_views.coordinator_home, name='coordinator_home'),
    path("coordinator/profile/", coordinator_views.coordinator_profile, name='coordinator_profile'),
    
    path("coordinator/alumni/", coordinator_views.manage_alumni, name='manage_alumni'),
    path("coordinator/alumni/register/", coordinator_views.register_alumni, name='coordinator_register_alumni'),
    path("coordinator/alumni/verify/<int:alumni_id>/", coordinator_views.verify_alumni, name='verify_alumni'),
    path("coordinator/alumni/delete/<int:alumni_id>/", coordinator_views.delete_alumni, name='coordinator_delete_alumni'),
    
    path("coordinator/events/", coordinator_views.manage_events, name='manage_events'),
    path("coordinator/events/create/", coordinator_views.create_event, name='create_event'),
    path("coordinator/events/edit/<int:event_id>/", coordinator_views.edit_event, name='edit_event'),
    path("coordinator/events/<int:event_id>/registrations/", coordinator_views.event_registrations, name='event_registrations'),
    path("coordinator/registrations/approve/<int:registration_id>/", coordinator_views.approve_registration, name='approve_registration'),
    
    path("coordinator/news/", coordinator_views.manage_news, name='manage_news'),
    path("coordinator/news/create/", coordinator_views.create_news, name='create_news'),
    path("coordinator/news/edit/<int:news_id>/", coordinator_views.edit_news, name='edit_news'),
    path("coordinator/news/publish/<int:news_id>/", coordinator_views.publish_news, name='publish_news'),
    path("coordinator/news/unpublish/<int:news_id>/", coordinator_views.unpublish_news, name='unpublish_news'),
    
    path("coordinator/jobs/", coordinator_views.manage_jobs, name='manage_jobs'),
    path("coordinator/jobs/<int:job_id>/applications/", coordinator_views.job_applications, name='job_applications'),
    
    path("coordinator/donations/", coordinator_views.manage_donations, name='manage_donations'),
    
    path("coordinator/mentorships/", coordinator_views.manage_mentorships, name='manage_mentorships'),
    path("coordinator/mentorships/create/", coordinator_views.create_mentorship, name='create_mentorship'),
    
    path("coordinator/feedback/", coordinator_views.manage_feedback, name='manage_feedback'),
    path("coordinator/feedback/reply/<int:feedback_id>/", coordinator_views.reply_feedback, name='reply_feedback'),
    path("coordinator/feedback/resolve/<int:feedback_id>/", coordinator_views.resolve_feedback, name='resolve_feedback'),
    path("coordinator/feedback/pending/<int:feedback_id>/", coordinator_views.pending_feedback, name='pending_feedback'),
    
    path("coordinator/notifications/send/", coordinator_views.send_notification, name='send_notification'),
    path("coordinator/fcmtoken/", coordinator_views.coordinator_fcmtoken, name='coordinator_fcmtoken'),
    
    # Coordinator Messaging
    path("coordinator/messages/", coordinator_views.coordinator_messages_inbox, name='coordinator_messages_inbox'),
    path("coordinator/messages/send/", coordinator_views.coordinator_send_message, name='coordinator_send_message'),
    path("coordinator/messages/send/<int:recipient_id>/", coordinator_views.coordinator_send_message, name='coordinator_send_message_to'),
    path("coordinator/messages/alumni-search/", coordinator_views.coordinator_alumni_search, name='coordinator_alumni_search'),
    path("coordinator/messages/view/<int:message_id>/", coordinator_views.coordinator_view_message, name='coordinator_view_message'),
    
    # Coordinator Export URLs
    path("coordinator/export/alumni/<str:export_type>/", coordinator_views.coordinator_export_alumni_excel, name='coordinator_export_alumni_excel'),
    path("coordinator/export/alumni/year/<int:year_id>/", coordinator_views.coordinator_export_alumni_by_year_excel, name='coordinator_export_alumni_by_year_excel'),
    path("coordinator/export/statistics/", coordinator_views.coordinator_export_alumni_statistics_excel, name='coordinator_export_alumni_statistics_excel'),
    
    # Alumni URLs
    path("alumni/home/", alumni_views.alumni_home, name='alumni_home'),
    path("alumni/profile/", alumni_views.alumni_profile, name='alumni_profile'),
    
    path("alumni/directory/", alumni_views.alumni_directory, name='alumni_directory'),
    path("alumni/directory/data/", alumni_views.alumni_directory_data, name='alumni_directory_data'),
    path("alumni/profile/<int:alumni_id>/", alumni_views.alumni_detail, name='alumni_detail'),
    
    path("alumni/jobs/", alumni_views.job_board, name='job_board'),
    path("alumni/jobs/post/", alumni_views.post_job, name='post_job'),
    path("alumni/jobs/apply/<int:job_id>/", alumni_views.apply_job, name='apply_job'),
    path("alumni/jobs/my-applications/", alumni_views.my_applications, name='my_applications'),
    
    path("alumni/events/", alumni_views.events, name='events'),
    path("alumni/events/register/<int:event_id>/", alumni_views.register_event, name='register_event'),
    path("alumni/events/my-events/", alumni_views.my_events, name='my_events'),
    
    path("alumni/messages/", alumni_views.messages_inbox, name='messages_inbox'),
    path("alumni/messages/send/", alumni_views.send_message, name='send_message'),
    path("alumni/messages/send/<int:recipient_id>/", alumni_views.send_message, name='send_message_to'),
    path("alumni/messages/view/<int:message_id>/", alumni_views.view_message, name='view_message'),
    
    path("alumni/feedback/", alumni_views.alumni_feedback, name='alumni_feedback'),
    path("alumni/notifications/", alumni_views.notifications, name='notifications'),
    path("alumni/fcmtoken/", alumni_views.alumni_fcmtoken, name='alumni_fcmtoken'),
    
    # Legacy URLs for backward compatibility (can be removed later)
    path("get_attendance", views.login_page, name='get_attendance'),  # Redirect to login
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
