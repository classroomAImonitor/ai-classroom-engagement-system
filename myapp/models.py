from django.db import models
from django.contrib.auth.models import User

class VideoUpload(models.Model):
    title = models.CharField(max_length=200, blank=True)
    video_file = models.FileField(upload_to='videos/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    engagement_score = models.FloatField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.title} ({self.uploaded_at})"
