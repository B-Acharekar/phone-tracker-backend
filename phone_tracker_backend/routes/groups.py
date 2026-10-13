from datetime import timedelta
from flask import Blueprint, request, current_app, g
from ..auth import require_device
bp=Blueprint("groups",__name__)
def svc(): return current_app.extensions["firebase_service"]
@bp.post("/groups")
@require_device
def create_group():
    data=request.get_json(silent=True) or {}; name=str(data.get("name","")).strip(); icon=data.get("icon")
    if not name or len(name)>80 or icon not in current_app.config["GROUP_ICONS"]: return {"error":"valid name and icon are required"},400
    group_id=svc().db.collection("groups").document().id; code=svc().invite_code(); now=svc().now()
    svc().ref("groups",group_id).set({"name":name,"icon":icon,"owner_id":g.device_id,"created_at":now})
    svc().ref("groupMemberships",f"{group_id}_{g.device_id}").set({"group_id":group_id,"device_id":g.device_id,"role":"owner","created_at":now})
    svc().ref("groupInvitations",code).set({"code":code,"group_id":group_id,"status":"active","expires_at":now+timedelta(hours=current_app.config["INVITE_TTL_HOURS"])})
    return {"group_id":group_id,"invite_code":code},201
@bp.post("/groups/join")
@require_device
def join_group():
    code=(request.get_json(silent=True) or {}).get("code","").strip().upper(); snap=svc().ref("groupInvitations",code).get()
    if not snap.exists: return {"error":"invalid invite"},400
    data=snap.to_dict()
    if data.get("status")!="active" or data.get("expires_at")<=svc().now(): return {"error":"expired invite"},400
    svc().ref("groupMemberships",f"{data['group_id']}_{g.device_id}").set({"group_id":data["group_id"],"device_id":g.device_id,"role":"member","created_at":svc().now()},merge=True)
    return {"group_id":data["group_id"],"status":"joined"}
