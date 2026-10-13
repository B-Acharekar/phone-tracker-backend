import os

from phone_tracker_backend import create_app, socketio

app = create_app()

if __name__ == "__main__":
    # Render supplies PORT at runtime. Werkzeug is kept as the Socket.IO
    # development fallback because this service is started with `python app.py`.
    # Flask-SocketIO requires the explicit opt-in when that fallback is used
    # outside development mode.
    socketio.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000")),
        debug=False,
        allow_unsafe_werkzeug=True,
    )
