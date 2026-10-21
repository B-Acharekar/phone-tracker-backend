from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO
from google.api_core.exceptions import GoogleAPICallError
from google.auth.exceptions import GoogleAuthError

from .config import Config
from .services.firebase_service import FirebaseServiceRegistry
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
    app.extensions["firebase_service"] = FirebaseServiceRegistry(app.config)
    app.extensions["socketio"] = socketio

    @app.errorhandler(GoogleAPICallError)
    def firestore_api_error(error):
        app.logger.exception("Firebase API request failed")
        return {"error": "backend data service temporarily unavailable"}, 503

    @app.errorhandler(GoogleAuthError)
    def firebase_auth_error(error):
        app.logger.exception("Firebase authentication failed")
        return {"error": "backend data service temporarily unavailable"}, 503

    @app.errorhandler(OSError)
    def firebase_configuration_error(error):
        app.logger.exception("Firebase configuration failed")
        return {"error": "backend data service temporarily unavailable"}, 503

    @app.errorhandler(ValueError)
    def firebase_value_error(error):
        app.logger.exception("Firebase configuration failed")
        return {"error": "backend data service temporarily unavailable"}, 503
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
