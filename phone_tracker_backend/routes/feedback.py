from flask import Blueprint, request, current_app, g
from ..auth import current_service, require_device

bp = Blueprint("feedback", __name__)

@bp.post("/feedback")
@require_device
def submit_feedback():
    data = request.get_json(silent=True) or {}
    rating = data.get("rating")
    feedback = str(data.get("feedback", "")).strip()
    if not isinstance(rating, int) or rating < 1 or rating > 5:
        return {"error": "rating must be between 1 and 5"}, 400
    if not feedback or len(feedback) > 500:
        return {"error": "feedback must contain 1 to 500 characters"}, 400
    service = current_service()
    ref = service.ref("feedback", f"{g.device_id}_{int(service.now().timestamp())}")
    ref.set({"device_id": g.device_id, "rating": rating, "feedback": feedback, "created_at": service.now()})
    return {"saved": True}, 201
