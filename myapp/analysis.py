"""
Engagement Analyzer — Hybrid Detection Engine.

Uses Haar Cascade for FACE DETECTION (works reliably on classroom wide-shots)
then applies MediaPipe FaceMesh on each CROPPED FACE for behavioral analysis
(EAR, MAR, head pose).

This solves the core problem: MediaPipe FaceMesh in multi-face mode only
detects close-up/selfie faces. Haar Cascade detects faces at any scale.
"""

import cv2
import numpy as np
import threading

try:
    import mediapipe.solutions.face_mesh as mp_face_mesh
except ImportError:
    from mediapipe.python.solutions import face_mesh as mp_face_mesh


class EngagementAnalyzer:
    """
    Hybrid engagement analyzer:
      Step 1: Haar Cascade finds ALL faces in the classroom frame
      Step 2: MediaPipe FaceMesh analyzes each face crop for behavior
    """
    _instance = None
    _init_lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    print("Initializing Hybrid EngagementAnalyzer (Haar + FaceMesh)...")
                    cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._lock = threading.Lock()

        # ── Step 1: Haar Cascade for robust multi-face detection ──
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )

        # ── Step 2: FaceMesh for per-face behavioral analysis ──
        # Single-face, static mode — applied to each cropped face individually
        self.face_mesh = mp_face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.3,
            min_tracking_confidence=0.3,
        )

        # Live webcam mesh — multi-face tracking for continuous streams
        self.face_mesh_live = mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=40,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

        # ── Behavioral Thresholds ──
        self.EAR_THRESHOLD = 0.22
        self.MAR_THRESHOLD = 0.35
        self.YAW_THRESHOLD = 25
        self.PITCH_THRESHOLD = 20
        self.HAND_RAISE_PITCH = -15
        self.PHONE_PITCH = 13.0
        self.PHONE_YAW_MAX = 18.0

    def calculate_ear(self, landmarks, eye_indices):
        """Eye Aspect Ratio for sleepiness."""
        try:
            p = lambda i: np.array([landmarks[i].x, landmarks[i].y])
            v1 = np.linalg.norm(p(eye_indices[1]) - p(eye_indices[5]))
            v2 = np.linalg.norm(p(eye_indices[2]) - p(eye_indices[4]))
            h  = np.linalg.norm(p(eye_indices[0]) - p(eye_indices[3]))
            return (v1 + v2) / (2.0 * h) if h > 0 else 0.5
        except Exception:
            return 0.5

    def calculate_mar(self, landmarks):
        """Mouth Aspect Ratio for talking."""
        try:
            v = np.linalg.norm(
                np.array([landmarks[13].x, landmarks[13].y])
                - np.array([landmarks[14].x, landmarks[14].y])
            )
            h = np.linalg.norm(
                np.array([landmarks[61].x, landmarks[61].y])
                - np.array([landmarks[291].x, landmarks[291].y])
            )
            return v / h if h > 0 else 0
        except Exception:
            return 0

    def get_head_pose(self, landmarks):
        """Pitch and yaw from FaceMesh landmarks."""
        nose  = landmarks[1]
        l_eye = landmarks[33]
        r_eye = landmarks[263]
        mid_x = (l_eye.x + r_eye.x) / 2
        mid_y = (l_eye.y + r_eye.y) / 2
        yaw   = (nose.x - mid_x) * 100
        pitch = (nose.y - mid_y) * 100
        return pitch, yaw

    def _classify_face(self, lms):
        """Classify a single face's behavior from its FaceMesh landmarks."""
        pitch, yaw = self.get_head_pose(lms)

        ear_l = self.calculate_ear(lms, [33, 160, 158, 133, 153, 144])
        ear_r = self.calculate_ear(lms, [362, 385, 387, 263, 373, 380])
        is_sleepy = (ear_l + ear_r) / 2 < self.EAR_THRESHOLD

        mar = self.calculate_mar(lms)
        is_talking = mar > self.MAR_THRESHOLD

        is_distracted = abs(yaw) > self.YAW_THRESHOLD or pitch > self.PITCH_THRESHOLD
        is_using_phone = pitch > self.PHONE_PITCH and abs(yaw) < self.PHONE_YAW_MAX
        is_hand_raise = pitch < self.HAND_RAISE_PITCH

        # Priority label
        if is_using_phone:
            label = 'phone'
        elif is_sleepy:
            label = 'sleepy'
        elif is_distracted:
            label = 'distracted'
        elif is_talking:
            label = 'talking'
        else:
            label = 'attentive'

        return label, is_hand_raise

    def analyze_frame(self, frame, static=False):
        """
        Analyze a frame for student behaviors.

        static=True:  VIDEO mode — Haar finds faces, FaceMesh analyzes each crop
        static=False: WEBCAM mode — FaceMesh multi-face tracking on full frame
        """
        results = {
            'total_students': 0,
            'attentive': 0,
            'sleepy': 0,
            'distracted': 0,
            'talking': 0,
            'hand_raises': 0,
            'phone_usage': 0,
            'neutral': 0,
            'face_coords': [],
        }

        h, w, _ = frame.shape

        if static:
            # ═══════════════════════════════════════════════
            # VIDEO MODE: Haar Cascade → FaceMesh per crop
            # ═══════════════════════════════════════════════

            # Downscale for Haar — 1920px preserves small/distant faces
            # in wide-angle classroom shots while keeping processing fast
            max_width = 1920
            if w > max_width:
                scale = max_width / w
                proc_frame = cv2.resize(frame, (max_width, int(h * scale)))
            else:
                scale = 1.0
                proc_frame = frame

            gray = cv2.cvtColor(proc_frame, cv2.COLOR_BGR2GRAY)
            # Histogram equalization improves contrast for distant faces
            gray = cv2.equalizeHist(gray)

            # Haar Cascade detection — tuned for wide-angle classroom footage
            face_rects = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=3,     # Lowered from 4 for better recall
                minSize=(20, 20),   # Smaller min catches distant students
                flags=cv2.CASCADE_SCALE_IMAGE,
            )

            results['total_students'] = len(face_rects)

            # Spatial subsampling to prevent excessive FaceMesh processing times on crowded frames
            MAX_FACES_PER_FRAME = 8
            if len(face_rects) > MAX_FACES_PER_FRAME:
                # Sort faces by X-coordinate to guarantee an even left-to-right spatial sample
                sorted_rects = sorted(face_rects, key=lambda r: r[0])
                # Choose MAX_FACES_PER_FRAME evenly-spaced faces to analyze
                indices = [int(i * (len(sorted_rects) - 1) / (MAX_FACES_PER_FRAME - 1)) for i in range(MAX_FACES_PER_FRAME)]
                indices = sorted(list(set(indices))) # Ensure unique sorted indices
                analyzed_rects = [sorted_rects[i] for i in indices]
                fallback_rects = [r for i, r in enumerate(sorted_rects) if i not in indices]
            else:
                analyzed_rects = face_rects
                fallback_rects = []

            # 1. Process fallback (unsampled) faces: default to 'attentive'
            for (fx, fy, fw, fh) in fallback_rects:
                ox = int(fx / scale)
                oy = int(fy / scale)
                ow = int(fw / scale)
                oh = int(fh / scale)
                results['face_coords'].append({
                    'label': 'attentive',
                    'box': [ox, oy, ow, oh],
                })
                results['attentive'] += 1

            # 2. Process analyzed faces using Hybrid Cascade + FaceMesh
            for (fx, fy, fw, fh) in analyzed_rects:
                # Map coordinates back to original frame if downscaled
                ox = int(fx / scale)
                oy = int(fy / scale)
                ow = int(fw / scale)
                oh = int(fh / scale)

                # Add padding around face for better FaceMesh analysis
                pad = int(oh * 0.35)
                y1 = max(0, oy - pad)
                y2 = min(h, oy + oh + pad)
                x1 = max(0, ox - pad)
                x2 = min(w, ox + ow + pad)
                face_crop = frame[y1:y2, x1:x2]

                if face_crop.size == 0 or face_crop.shape[0] < 20 or face_crop.shape[1] < 20:
                    # Face too small to analyze — count as neutral
                    results['face_coords'].append({
                        'label': 'attentive',
                        'box': [ox, oy, ow, oh],
                    })
                    results['attentive'] += 1
                    continue

                # Resize crop for FaceMesh (works best around 256-512px)
                crop_h, crop_w = face_crop.shape[:2]
                target_size = 256
                if crop_w > 0 and crop_h > 0:
                    face_resized = cv2.resize(face_crop, (target_size, target_size))
                else:
                    results['attentive'] += 1
                    results['face_coords'].append({
                        'label': 'attentive',
                        'box': [ox, oy, ow, oh],
                    })
                    continue

                rgb_crop = cv2.cvtColor(face_resized, cv2.COLOR_BGR2RGB)

                with self._lock:
                    mesh_result = self.face_mesh.process(rgb_crop)

                if mesh_result.multi_face_landmarks:
                    lms = mesh_result.multi_face_landmarks[0].landmark
                    label, is_hand_raise = self._classify_face(lms)

                    if label == 'phone':
                        results['phone_usage'] += 1
                    elif label == 'sleepy':
                        results['sleepy'] += 1
                    elif label == 'distracted':
                        results['distracted'] += 1
                    elif label == 'talking':
                        results['talking'] += 1
                    else:
                        results['attentive'] += 1

                    if is_hand_raise:
                        results['hand_raises'] += 1
                else:
                    # FaceMesh couldn't analyze the crop — default to attentive
                    label = 'attentive'
                    results['attentive'] += 1

                results['face_coords'].append({
                    'label': label,
                    'box': [ox, oy, ow, oh],
                })

        else:
            # ═══════════════════════════════════════════════
            # WEBCAM MODE: FaceMesh multi-face tracking
            # ═══════════════════════════════════════════════
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            with self._lock:
                face_results = self.face_mesh_live.process(rgb_frame)

            if face_results.multi_face_landmarks:
                results['total_students'] = len(face_results.multi_face_landmarks)

                for face_landmarks in face_results.multi_face_landmarks:
                    lms = face_landmarks.landmark
                    label, is_hand_raise = self._classify_face(lms)

                    if label == 'phone':
                        results['phone_usage'] += 1
                    elif label == 'sleepy':
                        results['sleepy'] += 1
                    elif label == 'distracted':
                        results['distracted'] += 1
                    elif label == 'talking':
                        results['talking'] += 1
                    else:
                        results['attentive'] += 1

                    if is_hand_raise:
                        results['hand_raises'] += 1

                    all_x = [lm.x for lm in lms]
                    all_y = [lm.y for lm in lms]
                    results['face_coords'].append({
                        'label': label,
                        'box': [
                            int(min(all_x) * w),
                            int(min(all_y) * h),
                            int((max(all_x) - min(all_x)) * w),
                            int((max(all_y) - min(all_y)) * h),
                        ],
                    })

        # Neutral = everyone not classified
        results['neutral'] = max(0,
            results['total_students']
            - results['attentive']
            - results['sleepy']
            - results['distracted']
            - results['talking']
            - results['phone_usage']
        )

        return results

    def close(self):
        pass


def get_analyzer():
    """Get the global thread-safe singleton analyzer."""
    return EngagementAnalyzer.get_instance()
