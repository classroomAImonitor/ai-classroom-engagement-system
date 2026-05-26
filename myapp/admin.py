from django.contrib import admin
from .models import Classroom, VideoUpload, WebcamSession, AnalysisReport

@admin.register(Classroom)
class ClassroomAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'created_at')
    search_fields = ('name', 'user__username')

@admin.register(VideoUpload)
class VideoUploadAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'classroom', 'uploaded_at', 'processed')
    list_filter = ('processed', 'classroom')
    search_fields = ('title', 'user__username')

@admin.register(WebcamSession)
class WebcamSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'classroom', 'engagement_score', 'created_at')
    list_filter = ('classroom',)

@admin.register(AnalysisReport)
class AnalysisReportAdmin(admin.ModelAdmin):
    list_display = ('title', 'classroom', 'overall_engagement', 'generated_at')
    list_filter = ('classroom',)
