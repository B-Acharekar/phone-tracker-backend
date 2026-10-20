from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO

from .config import Config
from .services.firebase_service import FirebaseService
from .routes.installations import bp as installations_bp
from .routes.friends import bp as friends_bp
from .routes.groups import bp as groups_bp
from .routes.profile import bp as profile_bp
from .routes.groups import bp as groups_bp
from .routes.sharing import bp as sharing_bp
from .routes.feedback import bp as feedback_bp
from .realtime import register_realtime

socketio = SocketIO(cors_allowed_origins="*", async_mode="threading")

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    CORS(app)
    socketio.init_app(app, cors_allowed_origins="*")
    app.extensions["firebase_service"] = FirebaseService()
    app.extensions["socketio"] = socketio
    app.register_blueprint(installations_bp, url_prefix="/api/v1")
    app.register_blueprint(friends_bp, url_prefix="/api/v1")
    app.register_blueprint(profile_bp, url_prefix="/api/v1")
    app.register_blueprint(groups_bp, url_prefix="/api/v1")
    app.register_blueprint(sharing_bp, url_prefix="/api/v1")
    app.register_blueprint(feedback_bp, url_prefix="/api/v1")
    register_realtime(socketio, app)

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "phone-tracker-backend"}

    return app
