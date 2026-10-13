from flask import Blueprint, request, current_app, g
from firebase_admin import firestore
from ..auth import require_device
bp = Blueprint("profile", __name__)
@bp.put("/profile")
@require_device
def update_profile():
    name = (request.get_json(silent=True) or {}).get("name", "").strip()
    if not name or len(name) > 80: return {"error":"name is required and must be <= 80 characters"}, 400
    current_app.extensions["firebase_service"].ref("users", g.device_id).set({"profile_name": name, "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)
    return {"device_id": g.device_id, "name": name}
