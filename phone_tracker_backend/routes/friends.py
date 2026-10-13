from datetime import timedelta
from flask import Blueprint, request, current_app, g
from ..auth import require_device
bp = Blueprint("friends", __name__)
def svc(): return current_app.extensions["firebase_service"]
@bp.post("/friends/invite")
@require_device
def create_invite():
    user_ref = svc().ref("users", g.device_id)
    user_snap = user_ref.get()
    existing_code = (user_snap.to_dict() or {}).get("invite_code") if user_snap.exists else None
    if existing_code:
        return {"code": existing_code, "permanent": True}, 200

    code = svc().invite_code()
    user_ref.set({"invite_code": code}, merge=True)
    svc().ref("friendInvitations", code).set({
        "code": code,
        "owner_id": g.device_id,
        "status": "active",
        "permanent": True,
    })
    return {"code": code, "permanent": True}, 201
@bp.post("/friends/requests")
@require_device
def request_friend():
    code=(request.get_json(silent=True) or {}).get("code","").strip().upper(); ref=svc().ref("friendInvitations",code); snap=ref.get()
    invite = snap.to_dict() if snap.exists else {}
    expires_at = invite.get("expires_at")
    if not snap.exists or invite.get("status") != "active" or (expires_at and expires_at <= svc().now()): return {"error":"invalid or expired invite"},400
    owner=invite["owner_id"]
    if owner==g.device_id: return {"error":"cannot connect to yourself"},400
    request_id=f"{owner}_{g.device_id}"; svc().ref("friendRequests",request_id).set({"from_id":g.device_id,"to_id":owner,"status":"pending","created_at":svc().now()})
    return {"request_id":request_id,"status":"pending"},201
@bp.get("/friends/requests")
@require_device
def list_requests():
    rows=[]
    for snap in svc().db.collection("friendRequests").where(filter=__import__('google.cloud.firestore_v1.base_query',fromlist=['FieldFilter']).FieldFilter("to_id","==",g.device_id)).stream():
        row = {"id": snap.id, **snap.to_dict()}
        sender = svc().ref("users", row["from_id"]).get()
        profile = sender.to_dict() if sender.exists else {}
        row["from_name"] = profile.get("name") or row["from_id"]
        row["from_avatar"] = profile.get("avatar", "🙂")
        rows.append(row)
    return {"requests":rows}

@bp.get("/friends/requests/sent")
@require_device
def list_sent_requests():
    rows=[]
    field_filter=__import__('google.cloud.firestore_v1.base_query',fromlist=['FieldFilter']).FieldFilter("from_id","==",g.device_id)
    for snap in svc().db.collection("friendRequests").where(filter=field_filter).stream():
        row={"id":snap.id,**snap.to_dict()}
        recipient=svc().ref("users", row["to_id"]).get()
        profile=recipient.to_dict() if recipient.exists else {}
        row["to_name"]=profile.get("name") or row["to_id"]
        rows.append(row)
    return {"requests":rows}
@bp.post("/friends/requests/<request_id>")
@require_device
def decide(request_id):
    action=(request.get_json(silent=True) or {}).get("action")
    if action not in {"accept","reject"}: return {"error":"action must be accept or reject"},400
    ref=svc().ref("friendRequests",request_id); snap=ref.get()
    if not snap.exists or snap.to_dict().get("to_id")!=g.device_id: return {"error":"request not found"},404
    data=snap.to_dict(); current=data.get("status")
    if action == "accept" and current != "pending": return {"error":"request already decided"},409
    if action == "reject" and current == "rejected": return {"error":"request already rejected"},409
    status="accepted" if action=="accept" else "rejected"; ref.update({"status":status,"decided_at":svc().now()})
    if action=="accept": svc().ref("friendships", "_".join(sorted([data["from_id"],data["to_id"]]))).set({"members":[data["from_id"],data["to_id"]],"created_at":svc().now()})
    elif current == "accepted": svc().ref("friendships", "_".join(sorted([data["from_id"],data["to_id"]]))).delete()
    return {"request_id":request_id,"status":status}
