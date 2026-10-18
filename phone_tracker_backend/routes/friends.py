from datetime import datetime, timezone
from flask import Blueprint, request, current_app, g
from ..auth import require_device
bp = Blueprint("friends", __name__)
def svc(): return current_app.extensions["firebase_service"]

def friendship_id(first_id, second_id):
    return "_".join(sorted([first_id, second_id]))

def profile(device_id):
    snap = svc().ref("users", device_id).get()
    data = snap.to_dict() if snap.exists else {}
    return {
        "name": data.get("name") or data.get("device_model") or device_id,
        "device_model": data.get("device_model") or data.get("name") or "Android device",
        "avatar": data.get("avatar"),
    }

def iso_timestamp(value):
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)

def is_friend(first_id, second_id):
    snap = svc().ref("friendships", friendship_id(first_id, second_id)).get()
    return snap.exists and first_id in (snap.to_dict() or {}).get("members", []) and second_id in (snap.to_dict() or {}).get("members", [])

def location_permission_id(owner_id, viewer_id):
    return f"{owner_id}_{viewer_id}"

def request_location_row(snap):
    row = {"id": snap.id, **(snap.to_dict() or {})}
    sender = profile(row.get("from_id", ""))
    recipient = profile(row.get("to_id", ""))
    row.update({
        "from_name": sender["name"],
        "from_model": sender["device_model"],
        "to_name": recipient["name"],
        "to_model": recipient["device_model"],
        "created_at": iso_timestamp(row.get("created_at")),
        "decided_at": iso_timestamp(row.get("decided_at")),
    })
    return row
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
    if is_friend(g.device_id, owner): return {"error":"you are already friends"},409
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
    if action not in {"accept","reject","cancel"}: return {"error":"action must be accept, reject, or cancel"},400
    ref=svc().ref("friendRequests",request_id); snap=ref.get()
    if not snap.exists: return {"error":"request not found"},404
    data=snap.to_dict(); current=data.get("status")
    if action == "cancel":
        if data.get("from_id") != g.device_id: return {"error":"request not found"},404
        if current != "pending": return {"error":"request already decided"},409
        ref.update({"status":"cancelled","decided_at":svc().now()})
        return {"request_id":request_id,"status":"cancelled"}
    if data.get("to_id")!=g.device_id: return {"error":"request not found"},404
    if action == "accept" and current != "pending": return {"error":"request already decided"},409
    if action == "reject" and current == "rejected": return {"error":"request already rejected"},409
    status="accepted" if action=="accept" else "rejected"; ref.update({"status":status,"decided_at":svc().now()})
    if action=="accept": svc().ref("friendships", "_".join(sorted([data["from_id"],data["to_id"]]))).set({"members":[data["from_id"],data["to_id"]],"created_at":svc().now()})
    elif current == "accepted": svc().ref("friendships", "_".join(sorted([data["from_id"],data["to_id"]]))).delete()
    return {"request_id":request_id,"status":status}

@bp.get("/friends")
@require_device
def list_friends():
    """Return accepted friends plus the permission and last-location state.

    This is the REST equivalent of the reference app's friends/{deviceId}
    listener and active_shares/{friendId} snapshot.
    """
    rows = []
    for snap in svc().db.collection("friendships").stream():
        data = snap.to_dict() or {}
        members = data.get("members", [])
        if g.device_id not in members:
            continue
        friend_id = next((member for member in members if member != g.device_id), None)
        if not friend_id:
            continue
        friend_profile = profile(friend_id)
        permission_snap = svc().ref("locationPermissions", location_permission_id(friend_id, g.device_id)).get()
        permission = permission_snap.to_dict() if permission_snap.exists else {}
        location_snap = svc().ref("latestLocations", friend_id).get()
        location = location_snap.to_dict() if location_snap.exists else None
        preference = svc().ref("userPreferences", friend_id).get().to_dict() or {}
        can_view = permission.get("enabled") is True
        row = {
            "friend_id": friend_id,
            "name": friend_profile["name"],
            "device_model": friend_profile["device_model"],
            "avatar": friend_profile["avatar"],
            "permission_granted": can_view,
            "sharing_enabled": bool(preference.get("location_sharing_enabled", False)),
            "location_request_status": permission.get("request_status", "none"),
            "last_location": None,
        }
        if can_view and location:
            row["last_location"] = {
                "device_id": friend_id,
                "latitude": location.get("latitude"),
                "longitude": location.get("longitude"),
                "battery_percentage": location.get("battery_percentage"),
                "updated_at": iso_timestamp(location.get("updated_at")),
                "sharing_enabled": row["sharing_enabled"],
            }
        rows.append(row)
    return {"friends": rows}

@bp.post("/friends/location-requests")
@require_device
def request_location():
    friend_id = (request.get_json(silent=True) or {}).get("friend_id", "").strip()
    if not friend_id or friend_id == g.device_id:
        return {"error": "a valid friend_id is required"}, 400
    if not is_friend(g.device_id, friend_id):
        return {"error": "you can request location only from an accepted friend"}, 403
    permission_ref = svc().ref("locationPermissions", location_permission_id(friend_id, g.device_id))
    permission = permission_ref.get().to_dict() or {}
    if permission.get("enabled") is True:
        return {"status": "accepted", "already_granted": True}, 200
    request_id = f"{g.device_id}_{friend_id}"
    existing = svc().ref("locationRequests", request_id).get()
    if existing.exists and (existing.to_dict() or {}).get("status") == "pending":
        return {"request_id": request_id, "status": "pending"}, 200
    svc().ref("locationRequests", request_id).set({
        "from_id": g.device_id,
        "to_id": friend_id,
        "status": "pending",
        "created_at": svc().now(),
    })
    permission_ref.set({"owner_id": friend_id, "viewer_id": g.device_id, "enabled": False, "request_status": "pending"}, merge=True)
    return {"request_id": request_id, "status": "pending"}, 201

@bp.get("/friends/location-requests")
@require_device
def list_location_requests():
    rows = []
    for snap in svc().db.collection("locationRequests").stream():
        row = snap.to_dict() or {}
        if row.get("from_id") == g.device_id or row.get("to_id") == g.device_id:
            rows.append(request_location_row(snap))
    return {"requests": rows}

@bp.post("/friends/location-requests/<request_id>")
@require_device
def decide_location_request(request_id):
    action = (request.get_json(silent=True) or {}).get("action")
    if action not in {"accept", "reject", "cancel"}:
        return {"error": "action must be accept, reject, or cancel"}, 400
    ref = svc().ref("locationRequests", request_id)
    snap = ref.get()
    if not snap.exists:
        return {"error": "location request not found"}, 404
    data = snap.to_dict() or {}
    if not is_friend(data.get("from_id", ""), data.get("to_id", "")):
        return {"error": "location request is no longer valid"}, 409
    if action == "cancel":
        if data.get("from_id") != g.device_id or data.get("status") != "pending":
            return {"error": "location request not found"}, 404
        ref.update({"status": "cancelled", "decided_at": svc().now()})
        svc().ref("locationPermissions", location_permission_id(data["to_id"], data["from_id"])).set({"enabled": False, "request_status": "cancelled"}, merge=True)
        return {"request_id": request_id, "status": "cancelled"}
    if data.get("to_id") != g.device_id:
        return {"error": "location request not found"}, 404
    if action == "accept" and data.get("status") != "pending":
        return {"error": "location request already decided"}, 409
    status = "accepted" if action == "accept" else "rejected"
    ref.update({"status": status, "decided_at": svc().now()})
    svc().ref("locationPermissions", location_permission_id(data["to_id"], data["from_id"])).set({
        "owner_id": data["to_id"],
        "viewer_id": data["from_id"],
        "enabled": action == "accept",
        "request_status": status,
        "updated_at": svc().now(),
    }, merge=True)
    return {"request_id": request_id, "status": status}
