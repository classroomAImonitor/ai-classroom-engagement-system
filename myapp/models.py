# Migration hint: After editing this file, run:
#   python manage.py makemigrations && python manage.py migrate
#
# New field added:
#   VideoUpload.engagement_timeline — JSONField storing per-sample engagement scores
#     for the real timeline chart (replaces random data in the analytics view).

from django.db import models
from django.contrib.auth.models import User


class Classroom(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class VideoUpload(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    classroom = models.ForeignKey(
        Classroom, on_delete=models.SET_NULL, null=True, blank=True, related_name='videos'
    )
    title = models.CharField(max_length=200, blank=True)
    video_file = models.FileField(upload_to='videos/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)

    # ── Engagement Metrics ──
    engagement_score = models.FloatField(null=True, blank=True)
    student_count = models.IntegerField(default=0)
    attentive_pct = models.FloatField(default=0.0)
    sleepy_pct = models.FloatField(default=0.0)
    distracted_pct = models.FloatField(default=0.0)
    neutral_pct = models.FloatField(default=0.0)
    talking_pct = models.FloatField(default=0.0)
    hand_raises_count = models.IntegerField(default=0)
    phone_usage_pct = models.FloatField(default=0.0)

    # Real per-sample engagement timeline for charts (replaces random data)
    engagement_timeline = models.JSONField(default=list, blank=True)

    # ── Processing State ──
    processing_status = models.CharField(max_length=50, default='Pending', choices=[
        ('Pending', 'Pending'),
        ('Processing', 'Processing'),
        ('Completed', 'Completed'),
        ('Failed', 'Failed'),
    ])
    estimated_time = models.CharField(max_length=100, blank=True, null=True)
    heatmap_image = models.ImageField(upload_to='heatmaps/', null=True, blank=True)
    camera_angle = models.IntegerField(default=0, choices=[
        (0,   '0° (Horizontal)'),
        (90,  '90° (Clockwise)'),
        (180, '180° (Inverted)'),
        (270, '270° (Counter-Clockwise)'),
    ])

    def __str__(self):
        return f"{self.title} ({self.uploaded_at})"


class WebcamSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    classroom = models.ForeignKey(
        Classroom, on_delete=models.SET_NULL, null=True, blank=True, related_name='sessions'
    )
    engagement_score = models.FloatField()
    attentive = models.IntegerField()
    sleepy = models.IntegerField()
    distracted = models.IntegerField()
    neutral = models.IntegerField()
    talking = models.IntegerField(default=0)
    hand_raises = models.IntegerField(default=0)
    phone_usage = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Webcam Session {self.id} ({self.created_at})"


class AnalysisReport(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    classroom = models.ForeignKey(Classroom, on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=200)
    summary = models.TextField(blank=True)
    overall_engagement = models.FloatField(null=True, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)

    # Links to the source data
    video = models.OneToOneField(
        VideoUpload, on_delete=models.SET_NULL, null=True, blank=True, related_name='report'
    )
    session = models.OneToOneField(
        WebcamSession, on_delete=models.SET_NULL, null=True, blank=True, related_name='report'
    )

    def __str__(self):
        return f"Report: {self.title} ({self.generated_at})"
