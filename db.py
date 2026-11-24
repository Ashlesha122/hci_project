"""
db.py
-----
SQLite storage for users, mood logs, and human-in-the-loop calibrations.
Includes secure user authentication with bcrypt password hashing.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime

import bcrypt

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "moods.db")

SUPPORTED_MOODS = [
    "happy", "calm", "focused", "excited",
    "surprise", "tired", "stressed", "sad", "frustrated",
]


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def init_db() -> None:
    with _connect() as conn:
        # Users table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        # Mood logs
        conn.execute("""
            CREATE TABLE IF NOT EXISTS mood_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                emotion TEXT NOT NULL DEFAULT 'calm',
                confidence REAL NOT NULL DEFAULT 0.0,
                confirmed INTEGER DEFAULT 1,
                corrected_to TEXT DEFAULT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        # Calibrations
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_calibrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                predicted_mood TEXT NOT NULL,
                actual_mood TEXT NOT NULL,
                is_correct INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        # Training results
        conn.execute("""
            CREATE TABLE IF NOT EXISTS training_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                epochs INTEGER NOT NULL,
                train_accuracy REAL,
                val_accuracy REAL,
                train_loss REAL,
                val_loss REAL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        # Testing results
        conn.execute("""
            CREATE TABLE IF NOT EXISTS testing_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                test_accuracy REAL,
                total_samples INTEGER,
                correct_predictions INTEGER,
                per_class_accuracy TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        # App state (for multi-user session & extension sync)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS app_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        # Database tables initialized cleanly without demo users


def reset_database() -> None:
    """Completely wipe all tables and re-initialize clean schema."""
    with _connect() as conn:
        conn.execute("DROP TABLE IF EXISTS testing_results")
        conn.execute("DROP TABLE IF EXISTS training_results")
        conn.execute("DROP TABLE IF EXISTS user_calibrations")
        conn.execute("DROP TABLE IF EXISTS mood_logs")
        conn.execute("DROP TABLE IF EXISTS users")
    init_db()


# ---------------------------------------------------------------------------
# User Authentication
# ---------------------------------------------------------------------------

def create_user(username: str, password: str) -> int | None:
    """Create a new user. Returns user id or None if username exists."""
    raw_name = username.strip()
    if not raw_name:
        return None
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    try:
        with _connect() as conn:
            existing = conn.execute("SELECT id FROM users WHERE LOWER(username) = LOWER(?)", (raw_name,)).fetchone()
            if existing:
                return None
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cur = conn.execute(
                "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                (raw_name, hashed.decode("utf-8"), now),
            )
            return cur.lastrowid
    except sqlite3.IntegrityError:
        return None


def verify_user(username: str, password: str) -> dict | None:
    """Verify credentials case-insensitively. Returns user dict or None."""
    raw_name = username.strip()
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE LOWER(username) = LOWER(?)",
            (raw_name,),
        ).fetchone()
        if row and bcrypt.checkpw(password.encode("utf-8"), row["password_hash"].encode("utf-8")):
            return {"id": row["id"], "username": row["username"]}
    return None


def get_user_by_id(user_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT id, username FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def set_active_user(user_id: int) -> None:
    """Record which user currently signed in, so background extension syncs to them."""
    with _connect() as conn:
        conn.execute(
            "INSERT INTO app_state (key, value) VALUES ('active_user_id', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (str(user_id),),
        )


def get_active_user() -> dict | None:
    """Get currently active user for extension synchronization."""
    with _connect() as conn:
        row = conn.execute("SELECT value FROM app_state WHERE key = 'active_user_id'").fetchone()
        if row:
            uid = int(row["value"])
            user_row = conn.execute("SELECT id, username FROM users WHERE id = ?", (uid,)).fetchone()
            if user_row:
                return dict(user_row)
        latest = conn.execute("SELECT id, username FROM users ORDER BY id DESC LIMIT 1").fetchone()
        return dict(latest) if latest else None


# ---------------------------------------------------------------------------
# Mood Logging
# ---------------------------------------------------------------------------

def log_mood(
    user_id: int,
    emotion: str,
    confidence: float = 0.0,
    confirmed: int = 1,
    corrected_to: str | None = None,
) -> int:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO mood_logs (user_id, emotion, confidence, confirmed, corrected_to, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, emotion, float(confidence), int(confirmed), corrected_to, now),
        )
        return cur.lastrowid


def record_feedback(
    user_id: int,
    is_correct: bool,
    predicted_mood: str | None = None,
    corrected_to: str | None = None,
) -> dict:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    last_pred = (predicted_mood or "calm").lower()
    final_mood = ((corrected_to if not is_correct else last_pred) or "calm").lower()

    with _connect() as conn:
        # Always insert a permanent new check-in record for this user action
        conn.execute(
            "INSERT INTO mood_logs (user_id, emotion, confidence, confirmed, corrected_to, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, final_mood, 85.0, 1 if is_correct else 0, corrected_to, now),
        )

        actual = final_mood
        conn.execute(
            "INSERT INTO user_calibrations (user_id, predicted_mood, actual_mood, is_correct, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, last_pred, actual, 1 if is_correct else 0, now),
        )

    return get_stats(user_id)


def get_calibration_weights(user_id: int) -> dict[str, float]:
    weights = {m: 1.0 for m in SUPPORTED_MOODS}
    with _connect() as conn:
        events = conn.execute(
            "SELECT predicted_mood, actual_mood, is_correct FROM user_calibrations "
            "WHERE user_id = ? ORDER BY id ASC",
            (user_id,),
        ).fetchall()

        for ev in events:
            pred = ev["predicted_mood"].lower()
            actual = ev["actual_mood"].lower()
            is_correct = bool(ev["is_correct"])

            if is_correct:
                if pred in weights:
                    weights[pred] = min(2.5, weights[pred] + 0.08)
            else:
                if actual in weights:
                    weights[actual] = min(2.5, weights[actual] + 0.18)
                if pred in weights:
                    weights[pred] = max(0.35, weights[pred] - 0.12)

    return {k: round(v, 3) for k, v in weights.items()}


def clear_user_history(user_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM mood_logs WHERE user_id = ?", (user_id,))


def get_history(user_id: int, limit: int = 20) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, COALESCE(corrected_to, emotion) AS emotion, confidence, confirmed, corrected_to, created_at "
            "FROM mood_logs WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def get_stats(user_id: int) -> dict:
    with _connect() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM mood_logs WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        confirmed = conn.execute(
            "SELECT COUNT(*) FROM mood_logs WHERE user_id = ? AND confirmed = 1", (user_id,)
        ).fetchone()[0]
        calibrations = conn.execute(
            "SELECT COUNT(*) FROM user_calibrations WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        rate = round((confirmed / total * 100.0), 1) if total > 0 else None
        return {
            "total_checkins": total,
            "confirmed_count": confirmed,
            "accuracy_rate": rate,
            "learning_count": calibrations,
        }


# ---------------------------------------------------------------------------
# Training & Testing Results
# ---------------------------------------------------------------------------

def save_training_result(user_id: int, epochs: int, train_acc: float,
                         val_acc: float, train_loss: float, val_loss: float) -> int:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO training_results (user_id, epochs, train_accuracy, val_accuracy, "
            "train_loss, val_loss, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, epochs, train_acc, val_acc, train_loss, val_loss, now),
        )
        return cur.lastrowid


def save_testing_result(user_id: int, test_acc: float, total: int,
                        correct: int, per_class: dict) -> int:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO testing_results (user_id, test_accuracy, total_samples, "
            "correct_predictions, per_class_accuracy, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, test_acc, total, correct, json.dumps(per_class), now),
        )
        return cur.lastrowid


def get_training_history(user_id: int, limit: int = 5) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM training_results WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def get_testing_history(user_id: int, limit: int = 5) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM testing_results WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            if d.get("per_class_accuracy"):
                d["per_class_accuracy"] = json.loads(d["per_class_accuracy"])
            results.append(d)
        return results
