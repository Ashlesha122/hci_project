"""
emotion.py
----------
Real-time facial expression and mood recognition engine.
Uses OpenCV Haar face detection, CLAHE contrast equalization,
DeepFace neural emotion analysis, and active online learning calibrations.
"""

from __future__ import annotations

from collections import deque
import cv2
import numpy as np
from deepface import DeepFace

import db

# Pre-load cascades for face detection
_frontal_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
_alt2_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_alt2.xml")
_profile_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")

# CLAHE for contrast normalization
_clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))


def _find_face(gray: np.ndarray) -> tuple[int, int, int, int] | None:
    """Detect face using multiple cascades for robustness."""
    for cascade in [_alt2_cascade, _frontal_cascade, _profile_cascade]:
        if not cascade.empty():
            faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(60, 60))
            if len(faces) > 0:
                return max(faces, key=lambda f: f[2] * f[3])
    return None


def _calculate_nuanced_moods(raw: dict, user_id: int = None) -> tuple[str, dict[str, float], float]:
    """
    Map raw FER-2013 neural scores into 9 human affective states.
    Applies user calibration weights from feedback.
    """
    h = float(raw.get("happy", 0.0))
    n = float(raw.get("neutral", 0.0))
    sur = float(raw.get("surprise", 0.0))
    sad = float(raw.get("sad", 0.0))
    ang = float(raw.get("angry", 0.0))
    fea = float(raw.get("fear", 0.0))

    # Adjust for monitor illumination shadows
    fea_adj = fea * 0.35
    sad_adj = sad * 0.60
    ang_adj = ang * 0.70
    h_adj = h * 1.35
    n_adj = n * 1.25
    sur_adj = sur * 1.05

    base_scores: dict[str, float] = {
        "happy": h_adj + (0.25 * sur_adj if h_adj > 10 else 0.0),
        "calm": n_adj if (sad_adj < 20 and ang_adj < 18) else n_adj * 0.65,
        "focused": (n_adj * 0.85 + ang_adj * 0.9) if (n > 25 and ang_adj > 6) else n_adj * 0.45,
        "excited": (h_adj + sur_adj) * 0.95 if (h_adj > 12 and sur_adj > 12) else 0.0,
        "surprise": sur_adj,
        "tired": (sad_adj * 0.85 + n_adj * 0.5) if (sad_adj > 14 and n > 20) else sad_adj * 0.35,
        "stressed": ang_adj * 0.95 + fea_adj * 0.65,
        "sad": sad_adj,
        "frustrated": (ang_adj * 0.75 + sad_adj * 0.75) if (ang_adj > 10 and sad_adj > 10) else 0.0,
    }

    # Apply personalized learning weights
    if user_id:
        learned_weights = db.get_calibration_weights(user_id)
    else:
        learned_weights = {m: 1.0 for m in db.SUPPORTED_MOODS}
    calibrated_scores = {k: v * learned_weights.get(k, 1.0) for k, v in base_scores.items()}

    # Normalize to 100%
    total = sum(calibrated_scores.values()) or 1.0
    normalized = {k: round(v / total * 100.0, 1) for k, v in calibrated_scores.items() if v > 0.5}
    if not normalized:
        normalized = {"calm": 100.0}

    dominant = max(normalized, key=normalized.get)
    top_score = normalized[dominant]

    # Confidence from separation margin
    vals_sorted = sorted(normalized.values(), reverse=True)
    margin = (vals_sorted[0] - vals_sorted[1]) if len(vals_sorted) > 1 else vals_sorted[0]
    confidence = round(min(98.5, max(52.0, (top_score * 0.65) + (margin * 0.45) + 18.0)), 1)

    return dominant, normalized, confidence


class TemporalSmoother:
    """Smoothes scores over consecutive frames to eliminate blink noise."""

    def __init__(self, window: int = 3) -> None:
        self.history: deque[dict[str, float]] = deque(maxlen=window)

    def smooth(self, moods: dict[str, float]) -> dict[str, float]:
        self.history.append(moods)
        accum: dict[str, float] = {}
        total_w = 0.0
        for i, h in enumerate(self.history):
            w = 1.0 + (i * 0.5)
            total_w += w
            for k, v in h.items():
                accum[k] = accum.get(k, 0.0) + (v * w)
        return {k: round(v / total_w, 1) for k, v in accum.items()}


_smoother = TemporalSmoother(window=3)


def analyze_bgr(frame_bgr: np.ndarray, user_id: int = None) -> dict:
    """Analyzes camera frame for facial emotion detection."""
    if frame_bgr is None or frame_bgr.size == 0:
        return {"success": False, "error": "Camera frame was empty."}

    try:
        ih, iw = frame_bgr.shape[:2]
        if iw > 640:
            scale = 640.0 / iw
            frame_bgr = cv2.resize(frame_bgr, (int(iw * scale), int(ih * scale)), interpolation=cv2.INTER_AREA)
            ih, iw = frame_bgr.shape[:2]

        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        face_rect = _find_face(gray)

        if face_rect is None:
            return {"success": False, "error": "Looking for face... Please look directly at the camera."}

        x, y, w, h = face_rect

        # 15% padded crop for complete facial geometry
        pad_x, pad_y = int(w * 0.15), int(h * 0.15)
        x1, y1 = max(0, x - pad_x), max(0, y - pad_y)
        x2, y2 = min(iw, x + w + pad_x), min(ih, y + h + pad_y)
        face_crop = frame_bgr[y1:y2, x1:x2]

        if face_crop.size == 0:
            return {"success": False, "error": "Invalid face crop."}

        # CLAHE contrast adjustment
        ycrcb = cv2.cvtColor(face_crop, cv2.COLOR_BGR2YCrCb)
        ycrcb[:, :, 0] = _clahe.apply(ycrcb[:, :, 0])
        enhanced_face = cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2BGR)

        # DeepFace inference
        result = DeepFace.analyze(
            img_path=enhanced_face,
            actions=["emotion"],
            enforce_detection=False,
            silent=True,
        )

        face_res = result[0] if isinstance(result, list) else result
        raw_emotions = face_res.get("emotion") or {}

        dominant, normalized_moods, conf = _calculate_nuanced_moods(raw_emotions, user_id)
        smoothed_moods = _smoother.smooth(normalized_moods)
        final_dominant = max(smoothed_moods, key=smoothed_moods.get)

        return {
            "success": True,
            "dominant_emotion": final_dominant,
            "confidence": conf,
            "emotions": smoothed_moods,
            "region": {"x": int(x), "y": int(y), "w": int(w), "h": int(h)},
        }
    except Exception as exc:
        return {"success": False, "error": f"Detection paused: {exc}"}


def warm_up() -> None:
    """Pre-loads neural weights into memory."""
    try:
        DeepFace.build_model("Emotion", task="facial_attribute")
    except Exception:
        pass
