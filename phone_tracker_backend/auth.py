from functools import wraps
from flask import request, current_app, g

def require_device(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        payload = request.get_json(silent=True, cache=True) or {}
        device_id = request.headers.get("X-Device-ID") or payload.get("device_id")
        app_id = request.headers.get("X-App-ID") or payload.get("app_id")
        token = request.headers.get("X-Session-Token") or payload.get("session_token")
        registry = current_app.extensions["firebase_service"]
        if not device_id or app_id not in current_app.config["SUPPORTED_APP_IDS"] or not token:
            return {"error": "valid device ID, app ID, and session token are required"}, 401
        service = registry.for_app(app_id)
        if not service.valid_session(device_id, app_id, token):
            return {"error": "valid device ID, app ID, and session token are required"}, 401
        g.device_id, g.app_id = device_id, app_id
        return fn(*args, **kwargs)
    return wrapped

def current_service():
    return current_app.extensions["firebase_service"].for_app(g.app_id)
