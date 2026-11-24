"""
server.py
---------
Entry point alias forwarding to app.py.
"""

from app import app, db

if __name__ == "__main__":
    db.init_db()
    print("=" * 60)
    print("  MoodPulse • Web Application Started")
    print("  Open in your browser: http://localhost:5000")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5000, debug=False)
