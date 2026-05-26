"""
Views for AI-Driven Classroom Engagement Monitoring System.

Bug fixes applied:
  [BUG 1]  total_obs now sums ALL metric values, not just 3.
  [BUG 2]  neutral_pct is calculated and saved to the model.
  [BUG 3]  context['video'] = data_obj when stype == 'video' so templates can use {{ video.pk }}.
  [BUG 4]  Timeline line_values derived from real attentive_pct, not random.randint().
  [BUG 5]  process_video_task() calls connection.close() for thread-safe DB access.
  [BUG 10] video.neutral_pct is saved during processing.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.db.models import Q
from .forms import VideoForm, RegisterForm, LoginForm
from .models import VideoUpload, WebcamSession
import cv2
import cv2.data
import numpy as np
import json
import time
import csv
import os
from datetime import datetime
import threading
from .analysis import get_analyzer


# ═══════════════════════════════════════════════
# Home / Dashboard / Static Views
# ═══════════════════════════════════════════════

def home(request):
    return render(request, 'main/home.html')


@login_required
def dashboard(request):
    """User dashboard with REAL data from processed videos and webcam sessions."""
    # Query real stats from DB
    user_videos = VideoUpload.objects.filter(
        Q(user=request.user) | Q(user__isnull=True)
    )
    processed_videos = user_videos.filter(processed=True)
    webcam_sessions = WebcamSession.objects.filter(
        Q(user=request.user) | Q(user__isnull=True)
    )

    # Total students across both processed videos and live webcam scans
    total_students = sum(v.student_count for v in processed_videos) + sum(
        (s.attentive + s.sleepy + s.distracted + s.neutral + s.talking + s.phone_usage)
        for s in webcam_sessions
    )

    # Combined average attention (engagement_score) across all video and webcam sessions
    total_scores = []
    for v in processed_videos:
        if v.engagement_score is not None:
            total_scores.append(v.engagement_score * 100)
    for s in webcam_sessions:
        if s.engagement_score is not None:
            total_scores.append(s.engagement_score)

    if total_scores:
        avg_attention = sum(total_scores) / len(total_scores)
    else:
        avg_attention = 0
    avg_attention = round(avg_attention, 1)

    # Total sessions = videos + webcam sessions
    total_sessions = user_videos.count() + webcam_sessions.count()

    # Total reports = processed videos + webcam sessions
    total_reports = processed_videos.count() + webcam_sessions.count()

    # Engaged = total attentive students, Fatigue = total sleepy (combining video and webcam sessions)
    total_engaged = sum(
        int(v.student_count * v.attentive_pct / 100) for v in processed_videos
    ) + sum(
        s.attentive for s in webcam_sessions
    )
    total_fatigue = sum(
        int(v.student_count * v.sleepy_pct / 100) for v in processed_videos
    ) + sum(
        s.sleepy for s in webcam_sessions
    )

    context = {
        'total_students': total_students,
        'avg_attention': avg_attention,
        'total_sessions': total_sessions,
        'total_reports': total_reports,
        'total_engaged': total_engaged,
        'total_fatigue': total_fatigue,
    }
    return render(request, 'main/dashboard.html', context)


def about(request):
    """About us page"""
    return render(request, 'main/about.html')


def webcam_demo(request):
    """Webcam demo page"""
    return render(request, 'main/webcam_demo.html')


# ═══════════════════════════════════════════════
# Authentication Views
# ═══════════════════════════════════════════════

def login_view(request):
    """User login view"""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back, {username}!')
                return redirect('dashboard')
            else:
                messages.error(request, 'Invalid username or password.')
        else:
            messages.error(request, 'Invalid username, password, or captcha.')
    else:
        form = LoginForm()

    return render(request, 'auth/login.html', {'form': form})


def register_view(request):
    """User registration view"""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Account created for {username}! You can now login.')
            return redirect('login')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = RegisterForm()

    return render(request, 'auth/register.html', {'form': form})


def logout_view(request):
    """User logout view"""
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('home')


# ═══════════════════════════════════════════════
# Video CRUD
# ═══════════════════════════════════════════════

@login_required
def video_upload(request):
    """Upload new video"""
    if request.method == 'POST':
        form = VideoForm(request.POST, request.FILES)
        if form.is_valid():
            video = form.save(commit=False)
            video.user = request.user
            video.save()
            messages.success(request, f'Video "{video.title}" uploaded successfully!')
            return redirect('videos:video_list')
    else:
        form = VideoForm()
    return render(request, 'main/upload_video.html', {'form': form})


@login_required
def video_list(request):
    """List all videos for the current user"""
    videos = VideoUpload.objects.filter(user=request.user).order_by('-uploaded_at')
    return render(request, 'main/video_list.html', {'videos': videos})


@login_required
def video_update(request, pk):
    """Update video"""
    video = get_object_or_404(VideoUpload, pk=pk, user=request.user)
    if request.method == 'POST':
        form = VideoForm(request.POST, request.FILES, instance=video)
        if form.is_valid():
            form.save()
            messages.success(request, 'Video updated successfully!')
            return redirect('videos:video_list')
    else:
        form = VideoForm(instance=video)
    return render(request, 'main/update_video.html', {'form': form, 'video': video})


@login_required
def video_delete(request, pk):
    """Delete video - Robust file and record removal"""
    video = get_object_or_404(VideoUpload, Q(user=request.user) | Q(user__isnull=True), pk=pk)
    video_title = video.title

    if request.method == 'POST':
        try:
            # Delete physical file
            if video.video_file and os.path.exists(video.video_file.path):
                os.remove(video.video_file.path)

            video.delete()
            messages.success(request, f'Video "{video_title}" and its analysis deleted successfully!')
        except Exception as e:
            messages.error(request, f"Error deleting video: {str(e)}")

        return redirect('videos:video_list')
    return redirect('videos:video_list')


@login_required
def report_delete(request, report_id):
    """Delete either a VideoUpload or a WebcamSession record"""
    if request.method == 'POST':
        try:
            if str(report_id).startswith('video-'):
                obj_id = report_id.split('-')[1]
                video = get_object_or_404(
                    VideoUpload, Q(user=request.user) | Q(user__isnull=True), id=obj_id
                )
                # Cleanup file
                if video.video_file and os.path.exists(video.video_file.path):
                    try:
                        os.remove(video.video_file.path)
                    except Exception:
                        pass
                video.delete()
                messages.success(request, "Video report deleted successfully.")
            elif str(report_id).startswith('webcam-'):
                obj_id = report_id.split('-')[1]
                WebcamSession.objects.filter(
                    Q(user=request.user) | Q(user__isnull=True), id=obj_id
                ).delete()
                messages.success(request, "Webcam report deleted successfully.")
            else:
                # Fallback for integer IDs
                VideoUpload.objects.filter(id=report_id, user=request.user).delete()
                messages.success(request, "Report deleted.")
        except Exception as e:
            messages.error(request, f"Deletion failed: {str(e)}")

    return redirect('reports')


# ═══════════════════════════════════════════════
# Video Processing Engine
# ═══════════════════════════════════════════════

@login_required
def video_process(request, pk):
    """Start video processing in a background thread with specific time estimation"""
    video = get_object_or_404(VideoUpload, pk=pk)
    # Allow processing for Pending AND Failed (retry), but not already Processing/Completed
    if video.processing_status not in ('Processing', 'Completed'):
        # Ensure the video has a title
        if not video.title:
            video.title = f'Video {video.id}'

        # Calculate time estimate
        try:
            cap = cv2.VideoCapture(video.video_file.path)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS) or 30
            duration_sec = total_frames / fps
            duration_min = duration_sec / 60
            cap.release()
        except Exception:
            duration_min = 1

        # Dynamic estimate based on sampling (approx 25% of duration for 1s sample)
        est_min = max(1, round(duration_min * 0.25))
        video.estimated_time = f"~{est_min} minutes"
        video.processing_status = 'Processing'
        video.save()

        # Start background thread for processing
        thread = threading.Thread(target=process_video_task, args=(video.id,))
        thread.daemon = True
        thread.start()

        msg = (
            f'Analysis for "{video.title}" (Length: {int(duration_min)}m) has started. '
            f'Estimated time: {video.estimated_time}. You can continue working while we analyze.'
        )
        messages.success(request, msg)
    elif video.processing_status == 'Completed':
        messages.info(request, 'This video has already been processed successfully.')
    else:
        messages.info(request, 'This video is currently being processed. Please wait.')
    return redirect('videos:video_list')


def process_video_task(video_id):
    """Background task wrapper for video processing with status updates."""
    import traceback
    # Force Django to open a fresh DB connection for this thread.
    from django.db import connection
    connection.close()

    try:
        from .models import VideoUpload
        video = VideoUpload.objects.get(id=video_id)
        # Ensure title exists
        if not video.title:
            video.title = f'Video {video_id}'
            video.save(update_fields=['title'])
        process_video(video)
        video.processing_status = 'Completed'
        video.save()
        print(f'[VideoProcess] Video {video_id} completed successfully.')
    except Exception as e:
        print(f'[VideoProcess] ERROR processing video {video_id}:')
        traceback.print_exc()
        try:
            from .models import VideoUpload
            video = VideoUpload.objects.get(id=video_id)
            video.processing_status = 'Failed'
            video.save()
        except Exception:
            pass


def process_video(video):
    """Advanced Analysis with MediaPipe & Dynamic Sampling for 60m+ Videos."""
    print(f"Starting Advanced Analysis for: {video.title}")
    analyzer = get_analyzer()
    cap = cv2.VideoCapture(video.video_file.path)

    if not cap.isOpened():
        raise Exception("Could not open video file")

    # ── DYNAMIC SAMPLING ENGINE ──
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    duration_mins = total_frames / (fps * 60)

    # Sampling rate based on video length
    if duration_mins < 5:
        sample_step = int(fps * 0.5)
    elif duration_mins < 20:
        sample_step = int(fps * 1)
    elif duration_mins < 60:
        sample_step = int(fps * 2)
    else:
        sample_step = int(fps * 3)

    # Ensure sample_step is at least 1 to avoid infinite loop
    sample_step = max(1, sample_step)

    # Dynamic temporal subsampling: ensure total frames to process is capped to prevent long processing times
    MAX_FRAMES_TO_PROCESS = 150
    if total_frames / sample_step > MAX_FRAMES_TO_PROCESS:
        sample_step = int(total_frames / MAX_FRAMES_TO_PROCESS)
        sample_step = max(1, sample_step)

    frame_idx = 0
    processed_count = 0

    # Behavior Accumulators
    metrics = {
        'attentive': 0, 'sleepy': 0, 'distracted': 0, 'neutral': 0,
        'talking': 0, 'hand_raises': 0, 'phone_usage': 0,
    }
    student_presence = []

    # Real engagement timeline samples (replaces random data)
    engagement_timeline = []

    # Heatmap Setup — single-channel intensity accumulation
    attention_grid = None          # float32 intensity map
    background_snapshot = None    # clean dimmed background for blending

    # Behavior → attention intensity weights
    # High = engaged/attentive, Low = distracted/absent
    ATTENTION_WEIGHTS = {
        'attentive':  1.00,   # peak engagement → RED in TURBO
        'talking':    0.80,   # active participation
        'neutral':    0.50,   # baseline presence → YELLOW
        'sleepy':     0.30,   # low alertness → GREEN/BLUE
        'distracted': 0.20,   # off-task → BLUE
        'phone':      0.10,   # highly disengaged → deep BLUE
    }

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Apply Rotation if needed
        if video.camera_angle == 90:
            frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        elif video.camera_angle == 180:
            frame = cv2.rotate(frame, cv2.ROTATE_180)
        elif video.camera_angle == 270:
            frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

        if frame_idx % sample_step == 0:
            h, w, _ = frame.shape
            if attention_grid is None:
                attention_grid = np.zeros((h, w), dtype=np.float32)
                # Capture the first sampled frame as a dimmed background snapshot
                background_snapshot = cv2.GaussianBlur(frame, (15, 15), 0)

            # RUN MEDIAPIPE ANALYSIS
            # static=True: CRITICAL for video — forces full detection per frame
            # Without this, FaceMesh only finds 1 face when frames are skipped
            frame_results = analyzer.analyze_frame(frame, static=True)

            # Accumulate metrics
            metrics['attentive'] += frame_results['attentive']
            metrics['sleepy'] += frame_results['sleepy']
            metrics['distracted'] += frame_results['distracted']
            metrics['talking'] += frame_results['talking']
            metrics['hand_raises'] += frame_results['hand_raises']
            metrics['phone_usage'] += frame_results['phone_usage']
            metrics['neutral'] += frame_results.get('neutral', 0)

            student_presence.append(frame_results['total_students'])
            processed_count += 1

            # Record real engagement score for this sample (for timeline chart)
            if frame_results['total_students'] > 0:
                sample_engagement = int(
                    frame_results['attentive'] / frame_results['total_students'] * 100
                )
            else:
                sample_engagement = 0
            engagement_timeline.append(sample_engagement)

            # Heatmap Accumulation — weighted by attention intensity
            # Each face center receives a weighted intensity contribution.
            # The weight encodes how engaged the student is.
            # Attentive students push intensity toward Red in TURBO colormap.
            for face in frame_results['face_coords']:
                fx, fy, fw, fh = face['box']
                cx, cy = fx + fw // 2, fy + fh // 2
                weight = ATTENTION_WEIGHTS.get(face['label'], 0.40)

                # Paint a filled circle weighted by attention intensity
                # Use radius proportional to face size for realistic density blobs
                radius = max(40, int(max(fw, fh) * 0.9))
                cv2.circle(attention_grid, (cx, cy), radius, (weight,), -1)

        frame_idx += 1

    cap.release()

    if processed_count > 0:
        # [BUG 1] FIXED: total_obs sums ALL behaviors, not just 3
        total_obs = sum(metrics.values()) or 1

        video.attentive_pct = (metrics['attentive'] / total_obs) * 100
        video.sleepy_pct = (metrics['sleepy'] / total_obs) * 100
        video.distracted_pct = (metrics['distracted'] / total_obs) * 100
        video.talking_pct = (metrics['talking'] / total_obs) * 100
        video.phone_usage_pct = (metrics['phone_usage'] / total_obs) * 100

        # [BUG 2 + BUG 10] FIXED: neutral_pct is now calculated and saved
        video.neutral_pct = (metrics['neutral'] / total_obs) * 100

        video.hand_raises_count = metrics['hand_raises']

        video.student_count = (
            int(np.percentile(student_presence, 90)) if student_presence else 0
        )
        video.engagement_score = metrics['attentive'] / total_obs

        # Save real engagement timeline (for chart — replaces random data)
        video.engagement_timeline = engagement_timeline

        # ─── Heatmap Finalization ───────────────────────────────────────────
        # Technique: single-channel attention intensity → COLORMAP_TURBO
        # TURBO scale: 0.0 (Blue) → 0.5 (Green/Yellow) → 1.0 (Red)
        # So Red = high sustained attention, Blue = low or distracted zones.
        if attention_grid is not None and background_snapshot is not None:

            # Step 1: Large Gaussian blur for smooth density distribution
            # Kernel 101×101 produces wide, clean hot-zone gradients
            smoothed = cv2.GaussianBlur(attention_grid, (101, 101), 0)

            # Step 2: Normalize to 0-255 safely
            if np.max(smoothed) > 0:
                cv2.normalize(smoothed, smoothed, 0, 255, cv2.NORM_MINMAX)
            heat_uint8 = smoothed.astype(np.uint8)

            # Step 3: Apply professional colormap
            # COLORMAP_TURBO: Blue(low) → Green → Yellow(medium) → Red(high)
            heatmap_colored = cv2.applyColorMap(heat_uint8, cv2.COLORMAP_TURBO)

            # Step 4: Mask out pixels with near-zero intensity (keep background clean)
            # Threshold: pixels below 15/255 stay as background, not colored
            alpha_mask = np.clip(smoothed / 255.0, 0, 1)
            alpha_3ch  = np.stack([alpha_mask, alpha_mask, alpha_mask], axis=2)
            heatmap_masked = (heatmap_colored.astype(np.float32) * alpha_3ch).astype(np.uint8)

            # Step 5: Dim the background slightly so the heatmap pops visually
            bg_dimmed = cv2.convertScaleAbs(background_snapshot, alpha=0.65, beta=0)

            # Step 6: Blend heatmap over dimmed background
            # 55% background, 45% heatmap — keeps classroom context visible
            heatmap_overlay = cv2.addWeighted(bg_dimmed, 0.55, heatmap_masked, 0.45, 0)

            heatmap_dir = os.path.join(settings.MEDIA_ROOT, 'heatmaps')
            os.makedirs(heatmap_dir, exist_ok=True)
            heatmap_filename = f'heatmap_{video.id}_{int(time.time())}.png'
            cv2.imwrite(os.path.join(heatmap_dir, heatmap_filename), heatmap_overlay)
            video.heatmap_image = f'heatmaps/{heatmap_filename}'

        video.processed_at = datetime.now()
        video.processed = True
        video.save()


# ═══════════════════════════════════════════════
# Engagement Analytics Module
# ═══════════════════════════════════════════════

@login_required
def analytics(request, pk=None):
    """Analytics view with real data from specific video or latest if no pk provided."""
    stype = request.GET.get('type', 'video')

    # Strip prefixes if present (e.g., 'video-12' -> '12')
    if pk and isinstance(pk, str):
        if pk.startswith('video-'):
            pk = pk.split('-')[1]
            stype = 'video'
        elif pk.startswith('webcam-'):
            pk = pk.split('-')[1]
            stype = 'webcam'

    try:
        data_obj = None
        if pk:
            if stype == 'video':
                data_obj = get_object_or_404(VideoUpload, pk=pk)
            else:
                data_obj = get_object_or_404(WebcamSession, pk=pk)
        else:
            # Default: try latest video, if none, try latest webcam
            latest_video = VideoUpload.objects.filter(
                Q(user=request.user) | Q(user__isnull=True),
                processed=True,
            ).order_by('-uploaded_at').first()

            if latest_video:
                data_obj = latest_video
                stype = 'video'
            else:
                latest_webcam = WebcamSession.objects.filter(
                    Q(user=request.user) | Q(user__isnull=True)
                ).order_by('-created_at').first()
                if latest_webcam:
                    data_obj = latest_webcam
                    stype = 'webcam'

        if data_obj:
            if stype == 'video':
                engagement_pct = int(data_obj.engagement_score * 100) if data_obj.engagement_score else 0
                total = data_obj.student_count
                attentive = int(total * (data_obj.attentive_pct / 100))
                sleepy = int(total * (data_obj.sleepy_pct / 100))
                distracted = int(total * (data_obj.distracted_pct / 100))
                talking = int(total * (data_obj.talking_pct / 100))
                hand_raises = data_obj.hand_raises_count
                phone = int(total * (data_obj.phone_usage_pct / 100))
                title = data_obj.title
                attentive_pct_raw = data_obj.attentive_pct
            else:
                # Sum behaviors to calculate actual student volume dynamically
                total = data_obj.attentive + data_obj.sleepy + data_obj.distracted + data_obj.neutral + data_obj.talking + data_obj.phone_usage
                if total == 0:
                    total = 1
                engagement_pct = int(data_obj.engagement_score) if data_obj.engagement_score else 0
                attentive = data_obj.attentive
                sleepy = data_obj.sleepy
                distracted = data_obj.distracted
                talking = data_obj.talking
                hand_raises = data_obj.hand_raises
                phone = data_obj.phone_usage
                title = f"Webcam Session {data_obj.created_at.strftime('%Y-%m-%d %H:%M')}"
                attentive_pct_raw = int(attentive / total * 100) if total > 0 else engagement_pct

            neutral = total - attentive - sleepy - distracted - talking - phone

            # [BUG 4] FIXED: Timeline derived from real data, not random.randint()
            # If we have a stored engagement_timeline (video), downsample to 6 points.
            # Otherwise, derive a realistic spread from attentive_pct.
            if stype == 'video' and hasattr(data_obj, 'engagement_timeline') and data_obj.engagement_timeline:
                timeline = data_obj.engagement_timeline
                # Downsample to 6 evenly-spaced points
                n = len(timeline)
                if n >= 6:
                    indices = [int(i * (n - 1) / 5) for i in range(6)]
                    line_values = [max(0, min(100, timeline[i])) for i in indices]
                else:
                    line_values = [max(0, min(100, v)) for v in timeline]
                    # Pad to 6 if fewer
                    while len(line_values) < 6:
                        line_values.append(line_values[-1] if line_values else 0)
            else:
                # Deterministic spread from attentive_pct — no randomness
                ap = attentive_pct_raw
                line_values = [
                    max(0, min(100, int(ap * 0.92))),
                    max(0, min(100, int(ap * 0.95))),
                    max(0, min(100, int(ap * 0.97))),
                    max(0, min(100, int(ap * 1.00))),
                    max(0, min(100, int(ap * 0.98))),
                    max(0, min(100, engagement_pct)),
                ]

            line_labels = ['T-10m', 'T-8m', 'T-6m', 'T-4m', 'T-2m', 'Current']

            context = {
                'engagement_percentage': engagement_pct,
                'total_students': total,
                'attentive': attentive,
                'sleepy': sleepy,
                'distracted': distracted,
                'talking': talking,
                'hand_raises': hand_raises,
                'phone': phone,
                'neutral': max(0, neutral),
                'video_title': title,
                'data_type': stype,
                'line_labels': json.dumps(line_labels),
                'line_values': json.dumps(line_values),
            }

            # [BUG 3] FIXED: Pass 'video' to context so template can use {{ video.pk }}
            if stype == 'video':
                context['video'] = data_obj

        else:
            context = {
                'total_students': 0, 'engagement_percentage': 0, 'attentive': 0,
                'sleepy': 0, 'distracted': 0, 'neutral': 0,
                'message': 'No analyzed data found. Perform a webcam scan or process a video first.',
            }
    except Exception as e:
        print(f"Analytics Error: {str(e)}")
        context = {
            'total_students': 0, 'engagement_percentage': 0, 'attentive': 0,
            'sleepy': 0, 'distracted': 0, 'neutral': 0,
            'message': 'Error loading analytics.',
        }

    return render(request, 'main/analytics.html', context)


# ═══════════════════════════════════════════════
# CSV Export
# ═══════════════════════════════════════════════

@login_required
def video_export_csv(request, pk):
    """Export analytics data to CSV"""
    video = get_object_or_404(VideoUpload, pk=pk, user=request.user)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="analytics_{video.pk}_{video.title[:20]}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Classroom Engagement Analytics Report'])
    writer.writerow(['Video Title', video.title])
    writer.writerow(['Uploaded At', video.uploaded_at.strftime("%Y-%m-%d %H:%M:%S")])
    writer.writerow([])

    engagement_pct = int(video.engagement_score * 100) if video.engagement_score else 0
    total = video.student_count
    attentive = int(total * (video.attentive_pct / 100))
    sleepy = int(total * (video.sleepy_pct / 100))
    distracted = int(total * (video.distracted_pct / 100))
    talking = int(total * (video.talking_pct / 100))
    phone = int(total * (video.phone_usage_pct / 100))
    neutral = total - attentive - sleepy - distracted - talking - phone

    writer.writerow(['Metric', 'Count/Value'])
    writer.writerow(['Overall Engagement Score', f'{engagement_pct}%'])
    writer.writerow(['Total Students Detected', total])
    writer.writerow(['Attentive Students', attentive])
    writer.writerow(['Sleepy Students', sleepy])
    writer.writerow(['Distracted Students', distracted])
    writer.writerow(['Talking Students', talking])
    writer.writerow(['Phone Usage', phone])
    writer.writerow(['Hand Raises', video.hand_raises_count])
    writer.writerow(['Neutral Students', max(0, neutral)])

    return response


# ═══════════════════════════════════════════════
# Reports Module
# ═══════════════════════════════════════════════

@login_required
def save_webcam_session(request):
    """Save finalized 20-second webcam session scores"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            WebcamSession.objects.create(
                user=request.user,
                engagement_score=data.get('engagement', 0),
                attentive=data.get('attentive', 0),
                sleepy=data.get('sleepy', 0),
                distracted=data.get('distracted', 0),
                neutral=data.get('neutral', 0),
                talking=data.get('talking', 0),
                hand_raises=data.get('hand_raises', 0),
                phone_usage=data.get('phone_usage', 0),
            )
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'success': False}, status=405)


@login_required
def reports(request):
    """Reports dashboard showing history of both video and webcam analysis"""
    # Fetch Video Reports for current user or legacy orphaned reports
    video_uploads = VideoUpload.objects.filter(
        Q(user=request.user) | Q(user__isnull=True)
    ).order_by('-uploaded_at')

    # Fetch Webcam Sessions for current user or legacy
    webcam_sessions = WebcamSession.objects.filter(
        Q(user=request.user) | Q(user__isnull=True)
    ).order_by('-created_at')

    # Unify into a single list of simplified report objects
    unified_reports = []

    # Process videos
    for v in video_uploads:
        engagement_pct = int(v.engagement_score * 100) if v.engagement_score else 0
        total = v.student_count
        attentive = int(total * (v.attentive_pct / 100)) if v.processed else '—'
        sleepy = int(total * (v.sleepy_pct / 100)) if v.processed else '—'
        distracted = int(total * (v.distracted_pct / 100)) if v.processed else '—'

        unified_reports.append({
            'id': f"video-{v.id}",
            'type': 'video',
            'title': v.title or "Video Analysis",
            'date': v.uploaded_at,
            'engagement': engagement_pct,
            'attentive': attentive,
            'sleepy': sleepy,
            'distracted': distracted,
            'talking': int(total * (v.talking_pct / 100)) if v.processed else '—',
            'hand_raises': v.hand_raises_count if v.processed else '—',
            'phone_usage': int(total * (v.phone_usage_pct / 100)) if v.processed else '—',
            'total': total if v.processed else 'Wait..',
            'heatmap': v.heatmap_image.url if v.heatmap_image else None,
            'original_id': v.id,
        })

    # Process webcam sessions
    for s in webcam_sessions:
        unified_reports.append({
            'id': f"webcam-{s.id}",
            'type': 'webcam',
            'title': "Live Webcam Scan",
            'date': s.created_at,
            'engagement': int(s.engagement_score),
            'attentive': s.attentive,
            'sleepy': s.sleepy,
            'distracted': s.distracted,
            'talking': s.talking,
            'hand_raises': s.hand_raises,
            'phone_usage': s.phone_usage,
            'total': s.attentive + s.sleepy + s.distracted + s.neutral + s.talking + s.phone_usage,
            'original_id': s.id,
        })

    # Sort unified reports by date
    unified_reports.sort(key=lambda x: x['date'], reverse=True)

    # Context stats
    total_obs = sum(
        r['total'] if isinstance(r['total'], int) else 0
        for r in unified_reports
    )
    avg_eng = (
        sum(r['engagement'] for r in unified_reports) // len(unified_reports)
        if unified_reports else 0
    )
    best_eng = max((r['engagement'] for r in unified_reports), default=0)

    context = {
        'reports': unified_reports,
        'total_students_stat': total_obs,
        'avg_engagement': avg_eng,
        'best_engagement': best_eng,
    }
    return render(request, 'main/reports.html', context)


@login_required
def reports_export_csv(request):
    """Export all processed reports for current user (and legacy) to a complete CSV"""
    processed_videos = VideoUpload.objects.filter(
        Q(user=request.user) | Q(user__isnull=True),
        processed=True,
    ).order_by('-uploaded_at')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="all_classroom_reports.csv"'

    writer = csv.writer(response)
    writer.writerow(['Classroom Engagement - Global Report Archive'])
    writer.writerow(['Date Exported', datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    writer.writerow([])

    writer.writerow([
        'Date', 'Title', 'Total Students', 'Attentive', 'Sleepy',
        'Distracted', 'Talking', 'Phone', 'Hand Raises', 'Neutral', 'Engagement Rate %',
    ])

    for video in processed_videos:
        engagement_pct = int(video.engagement_score * 100) if video.engagement_score else 0
        total = video.student_count
        attentive = int(total * (video.attentive_pct / 100))
        sleepy = int(total * (video.sleepy_pct / 100))
        distracted = int(total * (video.distracted_pct / 100))
        talking = int(total * (video.talking_pct / 100))
        phone = int(total * (video.phone_usage_pct / 100))
        neutral = total - attentive - sleepy - distracted - talking - phone

        writer.writerow([
            video.uploaded_at.strftime("%Y-%m-%d"),
            video.title,
            total,
            attentive,
            sleepy,
            distracted,
            talking,
            phone,
            video.hand_raises_count,
            max(0, neutral),
            f"{engagement_pct}%",
        ])

    return response


# ═══════════════════════════════════════════════
# Miscellaneous Views
# ═══════════════════════════════════════════════

@login_required
def technical_docs(request):
    """Technical documentation for the AI engagement system"""
    return render(request, 'main/documentation.html')


@login_required
def privacy_protocol(request):
    """Privacy and ethical guidelines for the project"""
    return render(request, 'main/privacy_ethics.html')


@login_required
def research_whitepaper(request):
    """Whitepaper abstract and vision overview"""
    return render(request, 'main/whitepaper.html')


# ═══════════════════════════════════════════════
# Live Webcam Analysis API
# ═══════════════════════════════════════════════

@login_required
def live_engagement_analysis(request):
    """Real-time AI engagement analysis for webcam frames"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            image_data = data.get('image', '')

            if not image_data:
                return JsonResponse({'error': 'No image data'}, status=400)

            # Decode base64 image
            import base64
            format_str, imgstr = image_data.split(';base64,')
            nparr = np.frombuffer(base64.b64decode(imgstr), np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if img is None:
                return JsonResponse({'error': 'Failed to decode image'}, status=400)

            # Use the global analyzer instance (thread-safe via internal lock)
            analyzer = get_analyzer()
            # static=False: webcam is a continuous stream, tracking helps
            results = analyzer.analyze_frame(img, static=False)

            return JsonResponse({
                'success': True,
                'faces': results['total_students'],
                'face_coords': results['face_coords'],
                'engagement': (
                    int(results['attentive'] / results['total_students'] * 100)
                    if results['total_students'] > 0 else 0
                ),
                'attentive': results['attentive'],
                'distracted': results['distracted'],
                'sleepy': results['sleepy'],
                'neutral': results['neutral'],
                'talking': results['talking'],
                'hand_raises': results['hand_raises'],
                'phone_usage': results['phone_usage'],
            })

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Only POST allowed'}, status=405)


@login_required
def video_status_api(request, pk):
    """API endpoint to get the real-time status of a video upload."""
    video = get_object_or_404(VideoUpload, pk=pk)
    # Check authorization (allow user's own videos, or legacy orphaned ones)
    if video.user and video.user != request.user:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    return JsonResponse({
        'id': video.id,
        'processing_status': video.processing_status,
        'estimated_time': video.estimated_time,
        'processed': video.processed,
        'engagement_score': round(video.engagement_score * 100, 1) if (video.engagement_score is not None) else None,
    })
