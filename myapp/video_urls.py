from django.urls import path
from . import views

urlpatterns = [
    path('', views.video_list, name='video_list'),
    path('upload/', views.video_upload, name='video_upload'),
    path('<int:pk>/update/', views.video_update, name='video_update'),
    path('<int:pk>/delete/', views.video_delete, name='video_delete'),
    path('<int:pk>/process/', views.video_process, name='video_process'),
    path('<int:pk>/export/', views.video_export_csv, name='video_export_csv'),
]
