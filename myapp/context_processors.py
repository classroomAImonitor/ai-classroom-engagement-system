from .models import VideoUpload

def footer_stats(request):
    """
    Provides global statistics for the Neural HUD footer.
    """
    try:
        total = VideoUpload.objects.count()
        processed = VideoUpload.objects.filter(processed=True).count()
        avg_score = 0
        if processed > 0:
            videos = VideoUpload.objects.filter(processed=True)
            avg_score = sum(v.engagement_score for v in videos) / processed * 100
        
        return {
            'hud_total_videos': total,
            'hud_processed_videos': processed,
            'hud_avg_engagement': int(avg_score)
        }
    except:
        return {
            'hud_total_videos': 0,
            'hud_processed_videos': 0,
            'hud_avg_engagement': 0
        }
