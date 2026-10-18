from flask import Blueprint, request, current_app
bp = Blueprint("installations", __name__)
@bp.post("/installations")
def register():
    data = request.get_json(silent=True) or {}; device_id, app_id = data.get("device_id"), data.get("app_id")
    if not device_id or app_id != current_app.config["SERVICE_APP_ID"]: return {"error":"device_id and valid app_id are required"}, 400
    try:
        token = current_app.extensions["firebase_service"].register(device_id, app_id)
        profile = {key: data[key] for key in ("name", "avatar", "device_model") if data.get(key)}
        if profile:
            current_app.extensions["firebase_service"].ref("users", device_id).set(profile, merge=True)
    except ValueError as exc: return {"error": str(exc)}, 409
    return {"device_id": device_id, "app_id": app_id, "session_token": token}, 201
