"""
URL configuration for myapp
AI-Driven Classroom Engagement Monitoring System
"""

from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Home
    path('', views.home, name='home'),

    # Authentication
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),

    # Password Reset
    path(
        'password-reset/',
        auth_views.PasswordResetView.as_view(
            template_name='auth/password_reset.html',
            email_template_name='auth/password_reset_email.html',
            subject_template_name='auth/password_reset_subject.txt'
        ),
        name='password_reset'
    ),

    path(
        'password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='auth/password_reset_done.html'
        ),
        name='password_reset_done'
    ),

    path(
        'password-reset-confirm/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='auth/password_reset_confirm.html'
        ),
        name='password_reset_confirm'
    ),

    path(
        'password-reset-complete/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='auth/password_reset_complete.html'
        ),
        name='password_reset_complete'
    ),

    # Video CRUD
    path('videos/', include(('myapp.video_urls', 'videos'), namespace='videos')),

    # Analytics
    path('analytics/', views.analytics, name='analytics'),
    path('analytics/<int:pk>/', views.analytics, name='analytics_detail'),
    path('reports/', views.reports, name='reports'),
    path('about/', views.about, name='about'),
    path('webcam-demo/', views.webcam_demo, name='webcam_demo'),

    path('reports/export/', views.reports_export_csv, name='reports_export_csv'),
]