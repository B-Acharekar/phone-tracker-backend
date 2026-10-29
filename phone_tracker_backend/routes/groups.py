from datetime import timedelta
from flask import Blueprint, request, current_app, g
from ..auth import current_service, require_device
from ..profile_utils import public_profile
bp=Blueprint("groups",__name__)
def svc(): return current_service()

def iso_timestamp(value):
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)

def user_profile(device_id):
    snap = svc().ref("users", device_id).get()
    return public_profile(device_id, snap.to_dict() if snap.exists else {})

def profile_for_group_list(device_id):
    """Return the 0011 group-list profile plus current sharing state."""
    profile = user_profile(device_id)
    preference = svc().ref("userPreferences", device_id).get()
    preference_data = preference.to_dict() if preference.exists else {}
    profile["sharing_enabled"] = bool(preference_data.get("location_sharing_enabled", False))
    return profile

def group_members(group_id, include_sharing=False):
    rows = []
    memberships = svc().db.collection("groupMemberships").where("group_id", "==", group_id).stream()
    for membership_snap in memberships:
        membership = membership_snap.to_dict() or {}
        member_id = membership.get("device_id")
        if not member_id:
            continue
        profile = profile_for_group_list(member_id) if include_sharing else user_profile(member_id)
        rows.append({
            **profile,
            "role": membership.get("role") or "member",
            "created_at": iso_timestamp(membership.get("created_at")),
        })
    rows.sort(key=lambda member: (member.get("name", "").casefold(), member["device_id"]))
    return rows

def accepted_friend_ids():
    friend_ids = set()
    for friendship_snap in svc().db.collection("friendships").stream():
        members = (friendship_snap.to_dict() or {}).get("members", [])
        if g.device_id in members:
            friend_ids.update(member for member in members if member and member != g.device_id)

    # Include accepted requests from older records that do not have a
    # corresponding friendships document yet.
    for request_snap in svc().db.collection("friendRequests").stream():
        row = request_snap.to_dict() or {}
        if row.get("status") != "accepted":
            continue
        members = {row.get("from_id"), row.get("to_id")}
        if g.device_id in members:
            friend_ids.update(member for member in members if member and member != g.device_id)
    return friend_ids

def delete_documents(documents):
    """Delete Firestore documents in batches below Firestore's batch limit."""
    batch = None
    pending = 0
    for document in documents:
        if batch is None:
            batch = svc().db.batch()
        batch.delete(document)
        pending += 1
        if pending == 450:
            batch.commit()
            batch = None
            pending = 0
    if batch is not None:
        batch.commit()

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

@bp.get("/groups")
@require_device
def list_groups():
    groups = []
    seen_group_ids = set()
    is_0011 = g.app_id == "phone-tracker-0011"
    friend_profiles = [profile_for_group_list(friend_id) for friend_id in sorted(accepted_friend_ids())] if is_0011 else []
    memberships = svc().db.collection("groupMemberships").where("device_id", "==", g.device_id).stream()

    for membership_snap in memberships:
        membership = membership_snap.to_dict() or {}
        group_id = membership.get("group_id")
        if not group_id or group_id in seen_group_ids:
            continue

        group_snap = svc().ref("groups", group_id).get()
        if not group_snap.exists:
            # Ignore memberships left behind by an older/incomplete delete.
            continue

        group = group_snap.to_dict() or {}
        seen_group_ids.add(group_id)
        group_response = {
            "group_id": group_id,
            "name": group.get("name"),
            "icon": group.get("icon"),
            "owner_id": group.get("owner_id"),
            "role": membership.get("role") or ("owner" if group.get("owner_id") == g.device_id else "member"),
            "created_at": iso_timestamp(group.get("created_at")),
        }
        if is_0011:
            members = group_members(group_id, include_sharing=True)
            group_response.update({
                "groupId": group_id,
                "groupName": group.get("name"),
                "ownerId": group.get("owner_id"),
                # `members` contains the people already in this group. `friends`
                # contains every accepted friend available to the 0011 group UI.
                "members": members,
                "friends": friend_profiles,
            })
        groups.append(group_response)

    groups.sort(key=lambda group: (group.get("created_at") or "", group["group_id"]))
    return {"groups": groups}

@bp.get("/groups/friends")
@require_device
def list_group_friends():
    """Return every accepted friend with a display name for group pickers."""
    if g.app_id != "phone-tracker-0011":
        return {"error": "group friends endpoint not found"}, 404
    return {"friends": [user_profile(friend_id) for friend_id in sorted(accepted_friend_ids())]}

@bp.get("/groups/<group_id>/members")
@require_device
def list_group_members(group_id):
    """Return all members of a group, including their public profile names."""
    if g.app_id != "phone-tracker-0011":
        return {"error": "group members endpoint not found"}, 404
    membership = svc().ref("groupMemberships", f"{group_id}_{g.device_id}").get()
    if not membership.exists:
        return {"error": "group not found"}, 404
    return {"group_id": group_id, "members": group_members(group_id)}

@bp.delete("/groups/<group_id>")
@require_device
def delete_group(group_id):
    group_ref = svc().ref("groups", group_id)
    group_snap = group_ref.get()
    if not group_snap.exists:
        return {"error": "group not found"}, 404

    group = group_snap.to_dict() or {}
    if group.get("owner_id") != g.device_id:
        return {"error": "only the group owner can delete this group"}, 403

    memberships = svc().db.collection("groupMemberships").where("group_id", "==", group_id).stream()
    invitations = svc().db.collection("groupInvitations").where("group_id", "==", group_id).stream()
    documents = [group_ref]
    documents.extend(membership.reference for membership in memberships)
    documents.extend(invitation.reference for invitation in invitations)
    delete_documents(documents)

    return {"group_id": group_id, "status": "deleted"}

@bp.post("/groups/join")
@require_device
def join_group():
    code=(request.get_json(silent=True) or {}).get("code","").strip().upper(); snap=svc().ref("groupInvitations",code).get()
    if not snap.exists: return {"error":"invalid invite"},400
    data=snap.to_dict()
    if data.get("status")!="active" or data.get("expires_at")<=svc().now(): return {"error":"expired invite"},400
    svc().ref("groupMemberships",f"{data['group_id']}_{g.device_id}").set({"group_id":data["group_id"],"device_id":g.device_id,"role":"member","created_at":svc().now()},merge=True)
    return {"group_id":data["group_id"],"status":"joined"}
