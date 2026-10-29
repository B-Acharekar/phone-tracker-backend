from flask import Blueprint, request, current_app, g
from firebase_admin import firestore
from ..auth import current_service, require_device
from ..profile_utils import display_name, legacy_display_name, public_profile
bp = Blueprint("profile", __name__)

MAX_AVATAR_BYTES = 5 * 1024 * 1024
ALLOWED_AVATAR_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}

@bp.get("/profile")
@require_device
def get_profile():
    if g.app_id != "phone-tracker-0011":
        return {"error": "profile endpoint not found"}, 404
    snap = current_service().ref("users", g.device_id).get()
    return public_profile(g.device_id, snap.to_dict() if snap.exists else {})

@bp.post("/profile/avatar")
@require_device
def upload_avatar():
    if g.app_id != "phone-tracker-0011":
        return {"error": "avatar upload endpoint not found"}, 404

    upload = request.files.get("avatar") or request.files.get("profile_picture")
    if upload is None or not upload.filename:
        return {"error": "an avatar image is required"}, 400
    content_type = (upload.mimetype or "").lower()
    if content_type not in ALLOWED_AVATAR_TYPES:
        return {"error": "avatar must be a JPEG, PNG, WebP, or GIF image"}, 415

    content = upload.read(MAX_AVATAR_BYTES + 1)
    if len(content) > MAX_AVATAR_BYTES:
        return {"error": "avatar must be 5 MB or smaller"}, 413
    if not content:
        return {"error": "avatar image is empty"}, 400

    avatar_url = current_service().upload_avatar(g.device_id, content, content_type)
    current_service().ref("users", g.device_id).set({
        "avatar": avatar_url,
        "profile_picture": avatar_url,
        "profilePicture": avatar_url,
        "updated_at": firestore.SERVER_TIMESTAMP,
    }, merge=True)
    return {
        "avatar": avatar_url,
        "profile_picture": avatar_url,
        "profilePicture": avatar_url,
    }, 201

@bp.put("/profile")
@require_device
def update_profile():
    payload = request.get_json(silent=True) or {}
    if g.app_id != "phone-tracker-0011":
        name = str(payload.get("name", "")).strip()
        if not name or len(name) > 80: return {"error":"name is required and must be <= 80 characters"}, 400
        current_service().ref("users", g.device_id).set({"profile_name": name, "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)
        return {"device_id": g.device_id, "name": name}

    name = display_name(payload)
    if not name or len(name) > 80: return {"error":"name is required and must be <= 80 characters"}, 400
    # Keep both field names while older clients and records are migrated. The
    # friend and realtime APIs expose the public profile name from `name`,
    # while older 0011 clients wrote `profile_name`.
    current_service().ref("users", g.device_id).set({
        "name": name,
        "profile_name": name,
        "updated_at": firestore.SERVER_TIMESTAMP,
    }, merge=True)
    return {"device_id": g.device_id, "name": name}
