"""
app.py
------
MoodPulse • Real-Time Face Mood Reader & Adaptive Workspace.
Secure web app with login/signup, emotion detection, training & testing.
"""

from __future__ import annotations

import base64
import os
import random
import secrets
import sys
from functools import wraps

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import cv2
import numpy as np
from flask import (Flask, jsonify, redirect, render_template,
                   request, session, url_for, flash, send_file)
from flask_cors import CORS

import db
import emotion as emotion_engine

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
CORS(app, supports_credentials=True)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB max upload

_model_ready = False

# ---------------------------------------------------------------------------
# Desk Tips
# ---------------------------------------------------------------------------
DESK_TIPS = [
    "<strong>Desk Tip:</strong> Unclench your jaw and gently drop your shoulders away from your ears.",
    "<strong>Desk Tip:</strong> Follow the 20-20-20 rule: every 20 minutes, gaze at an object 20 feet away for 20 seconds.",
    "<strong>Desk Tip:</strong> Keep your screen at eye level to prevent neck stiffness during long work sessions.",
    "<strong>Desk Tip:</strong> Take a slow, deep belly breath to instantly reset your nervous system.",
    "<strong>Desk Tip:</strong> A quick 2-minute standing stretch boosts mental clarity and blood flow.",
    "<strong>Desk Tip:</strong> Rest your palms over your eyes for 15 seconds to ease screen glare fatigue.",
    "<strong>Desk Tip:</strong> Keep both feet flat on the floor and support your lower back.",
    "<strong>Desk Tip:</strong> Drink a glass of water—mild dehydration is often mistaken for mental fatigue.",
    "<strong>Desk Tip:</strong> Roll your wrists and stretch your fingers to relieve typing strain.",
    "<strong>Desk Tip:</strong> Step away from the monitor during breaks to give your eyes a true reset.",
]

MOOD_PROFILES = {
    "happy":     {"theme": "joy",        "badge": "Joyful & Smiling",    "guidance": "Savor this positive momentum! Great energy for creative problem-solving.", "pacer_suggested": False},
    "calm":      {"theme": "calm",       "badge": "Calm & Centered",     "guidance": "Relaxed and balanced. An optimal state for steady, continuous work.",       "pacer_suggested": False},
    "focused":   {"theme": "focus",      "badge": "Deep Focus",          "guidance": "High concentration detected. You are in the flow zone.",                   "pacer_suggested": False},
    "excited":   {"theme": "excited",    "badge": "Excited & Energized", "guidance": "High positive arousal! Channel this vibrant energy into your projects.",    "pacer_suggested": False},
    "surprise":  {"theme": "wonder",     "badge": "Surprised & Alert",   "guidance": "Curiosity detected! Stay open to unexpected solutions.",                   "pacer_suggested": False},
    "tired":     {"theme": "tired",      "badge": "Screen Fatigue",      "guidance": "Your eyes look fatigued. A 20-second eye rest can recharge your focus.",    "pacer_suggested": True},
    "stressed":  {"theme": "stressed",   "badge": "Tension Detected",    "guidance": "Facial tension detected. Unclench your jaw and breathe out slowly.",        "pacer_suggested": True},
    "sad":       {"theme": "sad",        "badge": "Gentle Pause",        "guidance": "Notice any cognitive heaviness. Give yourself permission to pause.",         "pacer_suggested": True},
    "frustrated":{"theme": "frustrated", "badge": "Frustration Detected","guidance": "Take a 60-second breathing pause to decompress and reset.",                 "pacer_suggested": True},
}


# ---------------------------------------------------------------------------
# Auth Decorator
# ---------------------------------------------------------------------------

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # For API requests, always synchronize to the currently active logged-in user
        if request.is_json or request.path.startswith("/api/"):
            active_user = db.get_active_user()
            if active_user:
                session["user_id"] = active_user["id"]
                session["username"] = active_user["username"]
                return f(*args, **kwargs)
            if "user_id" in session:
                return f(*args, **kwargs)
            return jsonify({"success": False, "error": "Login required"}), 401

        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def _ensure_model():
    global _model_ready
    if not _model_ready:
        emotion_engine.warm_up()
        _model_ready = True


# ---------------------------------------------------------------------------
# Auth Routes
# ---------------------------------------------------------------------------

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""

        if not username or len(username) < 3:
            flash("Username must be at least 3 characters.", "error")
            return render_template("signup.html")
        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return render_template("signup.html")
        if password != confirm:
            flash("Passwords do not match.", "error")
            return render_template("signup.html")

        user_id = db.create_user(username, password)
        if user_id is None:
            flash("Username already taken. Please choose another.", "error")
            return render_template("signup.html")

        db.set_active_user(user_id)
        session["user_id"] = user_id
        session["username"] = username
        flash("Account created successfully! Welcome to MoodPulse.", "success")
        return redirect(url_for("index"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        user = db.verify_user(username, password)
        if user is None:
            flash("Invalid username or password.", "error")
            return render_template("login.html")

        db.set_active_user(user["id"])
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        flash(f"Welcome back, {user['username']}!", "success")
        return redirect(url_for("index"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Page Routes
# ---------------------------------------------------------------------------

@app.route("/")
@login_required
def index():
    initial_tip = random.choice(DESK_TIPS)
    return render_template(
        "index.html",
        initial_tip=initial_tip,
        username=session.get("username"),
    )


@app.route("/train")
@login_required
def train_page():
    return render_template("train.html", username=session.get("username"))


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------

@app.route("/health")
def health():
    return jsonify({"status": "ok", "app": "MoodPulse Face ML"})


@app.route("/api/analyze", methods=["POST"])
@login_required
def analyze_frame():
    data = request.get_json(force=True) or {}
    image_data = data.get("image", "")
    save_mood = data.get("save_mood", False)
    corrected_mood = data.get("corrected_mood")
    user_id = session["user_id"]

    if not image_data:
        return jsonify({"success": False, "error": "No camera frame received."})

    try:
        _ensure_model()
        if "," in image_data:
            image_data = image_data.split(",", 1)[1]
        raw = base64.b64decode(image_data)
        arr = np.frombuffer(raw, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            return jsonify({"success": False, "error": "Could not decode camera frame."})
    except Exception as exc:
        return jsonify({"success": False, "error": f"Frame error: {exc}"})

    result = emotion_engine.analyze_bgr(frame, user_id=user_id)
    if not result.get("success"):
        return jsonify(result)

    dominant = result["dominant_emotion"]
    confidence = result.get("confidence", 85.0)

    if save_mood or corrected_mood:
        final_mood = corrected_mood or dominant
        db.log_mood(
            user_id=user_id,
            emotion=final_mood,
            confidence=confidence,
            confirmed=1 if not corrected_mood else 0,
            corrected_to=corrected_mood,
        )

    profile = MOOD_PROFILES.get(dominant, MOOD_PROFILES["calm"])
    result["hci"] = profile
    result["stats"] = db.get_stats(user_id)
    if save_mood or corrected_mood:
        result["history"] = db.get_history(user_id, 20)
    return jsonify(result)


@app.route("/api/save-checkin", methods=["POST"])
@login_required
def save_checkin():
    data = request.get_json(force=True) or {}
    emotion = data.get("emotion", "calm")
    confidence = float(data.get("confidence", 85.0))
    user_id = session["user_id"]

    db.log_mood(
        user_id=user_id,
        emotion=emotion,
        confidence=confidence,
        confirmed=1,
    )
    return jsonify({
        "success": True,
        "stats": db.get_stats(user_id),
        "history": db.get_history(user_id, 20),
    })


@app.route("/api/feedback", methods=["POST"])
@login_required
def user_feedback():
    data = request.get_json(force=True) or {}
    is_correct = bool(data.get("is_correct", True))
    predicted_mood = data.get("predicted_mood")
    corrected_to = data.get("corrected_mood")
    user_id = session["user_id"]

    stats = db.record_feedback(
        user_id=user_id,
        is_correct=is_correct,
        predicted_mood=predicted_mood,
        corrected_to=corrected_to,
    )
    return jsonify({
        "success": True,
        "stats": stats,
        "learned_weights": db.get_calibration_weights(user_id),
        "history": db.get_history(user_id, 20),
    })


@app.route("/api/user-profile")
@login_required
def user_profile():
    user_id = session["user_id"]
    user = db.get_user_by_id(user_id)
    stats = db.get_stats(user_id)
    return jsonify({
        "success": True,
        "user_id": user_id,
        "username": user["username"] if user else session.get("username", "User"),
        "stats": stats,
    })


@app.route("/api/clear-history", methods=["POST"])
@login_required
def clear_history():
    user_id = session["user_id"]
    db.clear_user_history(user_id)
    return jsonify({
        "success": True,
        "stats": db.get_stats(user_id),
        "history": [],
    })


@app.route("/api/download-extension")
def download_extension():
    """Package the browser extension into a zip for users to install in Chrome/Edge."""
    import io
    import zipfile
    ext_dir = os.path.join(BASE_DIR, "extension")
    server_origin = request.host_url.rstrip("/")

    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(ext_dir):
            for file in files:
                if file.endswith(".py") or file.endswith(".pyc"):
                    continue
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, ext_dir)

                if file == "panel.js":
                    with open(full_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    content = content.replace('let API = "http://127.0.0.1:5000";', f'let API = "{server_origin}";')
                    zf.writestr(rel_path, content)
                else:
                    zf.write(full_path, rel_path)

    memory_file.seek(0)
    return send_file(
        memory_file,
        mimetype="application/zip",
        as_attachment=True,
        download_name="moodpulse-extension.zip",
    )


@app.route("/api/history", methods=["GET"])
@login_required
def mood_history():
    user_id = session["user_id"]
    limit = min(int(request.args.get("limit", 20)), 100)
    return jsonify({
        "success": True,
        "history": db.get_history(user_id, limit),
        "stats": db.get_stats(user_id),
    })


# ---------------------------------------------------------------------------
# Training & Testing API
# ---------------------------------------------------------------------------

@app.route("/api/train", methods=["POST"])
@login_required
def api_train():
    data = request.get_json(force=True) or {}
    epochs = min(int(data.get("epochs", 10)), 50)  # cap at 50
    user_id = session["user_id"]

    try:
        import train_test
        result = train_test.train_model(epochs=epochs, use_demo=True)

        if result["success"]:
            db.save_training_result(
                user_id=user_id,
                epochs=epochs,
                train_acc=result["train_accuracy"],
                val_acc=result["val_accuracy"],
                train_loss=result["train_loss"],
                val_loss=result["val_loss"],
            )

        return jsonify(result)
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)})


@app.route("/api/test", methods=["POST"])
@login_required
def api_test():
    user_id = session["user_id"]
    try:
        import train_test
        result = train_test.test_model(use_demo=True)

        if result["success"]:
            db.save_testing_result(
                user_id=user_id,
                test_acc=result["test_accuracy"],
                total=result["total_samples"],
                correct=result["correct_predictions"],
                per_class=result["per_class_accuracy"],
            )

        return jsonify(result)
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)})


@app.route("/api/model-info", methods=["GET"])
@login_required
def api_model_info():
    try:
        import train_test
        info = train_test.get_model_info()
        user_id = session["user_id"]
        info["training_history"] = db.get_training_history(user_id)
        info["testing_history"] = db.get_testing_history(user_id)
        return jsonify(info)
    except Exception as exc:
        return jsonify({"error": str(exc)})


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    db.init_db()
    print("=" * 60)
    print("  MoodPulse • Web Application Started")
    print("  Open in your browser: http://localhost:5000")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5000, debug=False)
