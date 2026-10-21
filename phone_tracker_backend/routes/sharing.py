from flask import Blueprint, request, current_app, g
from ..auth import current_service, require_device
bp = Blueprint("sharing", __name__)
@bp.put("/sharing")
@require_device
def sharing():
    enabled = (request.get_json(silent=True) or {}).get("enabled")
    if not isinstance(enabled, bool): return {"error":"enabled must be boolean"}, 400
    current_service().ref("userPreferences", g.device_id).set({"location_sharing_enabled": enabled}, merge=True)
    return {"enabled": enabled}
