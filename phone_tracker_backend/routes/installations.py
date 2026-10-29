from flask import Blueprint, request, current_app
from ..profile_utils import UNKNOWN_USER, display_name
bp = Blueprint("installations", __name__)
@bp.post("/installations")
def register():
    data = request.get_json(silent=True) or {}; device_id, app_id = data.get("device_id"), data.get("app_id")
    if not device_id or app_id not in current_app.config["SUPPORTED_APP_IDS"]: return {"error":"device_id and valid app_id are required"}, 400
    try:
        service = current_app.extensions["firebase_service"].for_app(app_id)
        token = service.register(device_id, app_id)
        if app_id != "phone-tracker-0011":
            profile = {key: data[key] for key in ("name", "avatar", "device_model") if data.get(key)}
            if profile:
                service.ref("users", device_id).set(profile, merge=True)
            return {"device_id": device_id, "app_id": app_id, "session_token": token}, 201

        existing = service.ref("users", device_id).get()
        existing_data = existing.to_dict() if existing.exists else {}
        # A repeat installation often sends only device_id/app_id. Reuse the
        # already saved profile name instead of returning the device ID as the
        # display name.
        supplied_name = display_name(existing_data) or display_name(data)
        profile = {key: data[key] for key in ("avatar", "device_model") if data.get(key)}
        if supplied_name:
            # Store the canonical field and the legacy 0011 field so all app
            # versions can read the same public display name.
            profile.update({"name": supplied_name, "profile_name": supplied_name})
        if profile:
            service.ref("users", device_id).set(profile, merge=True)
    except ValueError as exc: return {"error": str(exc)}, 409
    return {
        "device_id": device_id,
        "app_id": app_id,
        "name": supplied_name or UNKNOWN_USER,
        "profile_name": supplied_name or UNKNOWN_USER,
        "session_token": token,
    }, 201
