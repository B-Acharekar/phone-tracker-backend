from flask import request
from flask_socketio import emit, join_room

def friendship_id(first_id, second_id):
    return "_".join(sorted([first_id, second_id]))

def permission_id(owner_id, viewer_id):
    return f"{owner_id}_{viewer_id}"

def register_realtime(socketio, app):
    sessions = {}
    def friend_ids(service, device_id):
        ids = set()
        for snap in service.db.collection("friendships").stream():
            members = (snap.to_dict() or {}).get("members", [])
            if device_id in members:
                ids.update(member for member in members if member != device_id)
        return ids

    def can_view(service, owner_id, viewer_id):
        if viewer_id not in friend_ids(service, owner_id):
            return False
        permission = service.ref("locationPermissions", permission_id(owner_id, viewer_id)).get().to_dict() or {}
        return permission.get("enabled") is True

    def location_payload(service, owner_id):
        snapshot = service.ref("latestLocations", owner_id).get()
        if not snapshot.exists:
            return None
        data = snapshot.to_dict() or {}
        preference = service.ref("userPreferences", owner_id).get().to_dict() or {}
        return {
            "device_id": owner_id,
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
            "battery_percentage": data.get("battery_percentage"),
            "updated_at": data.get("updated_at").isoformat() if hasattr(data.get("updated_at"), "isoformat") else str(data.get("updated_at")),
            "sharing_enabled": bool(preference.get("location_sharing_enabled", False)),
        }
    @socketio.on("authenticate")
    def authenticate(data):
        data=data or {}; service=app.extensions["firebase_service"]; device_id=data.get("device_id"); app_id=data.get("app_id"); token=data.get("session_token")
        if app_id != app.config["SERVICE_APP_ID"] or not device_id or not service.valid_session(device_id, app_id, token): emit("error", {"error":"authentication failed"}); return
        sessions[request.sid]=device_id; join_room(device_id)
        # Subscribe only to currently authorized friends and groups.
        for snap in service.db.collection("friendships").stream():
            members=snap.to_dict().get("members",[])
            if device_id in members:
                other=next((x for x in members if x != device_id), None)
                if other: join_room(other)
        for snap in service.db.collection("groupMemberships").where("device_id","==",device_id).stream():
            group_id=snap.to_dict().get("group_id")
            for member in service.db.collection("groupMemberships").where("group_id","==",group_id).stream(): join_room(member.to_dict().get("device_id"))
        # Hydrate the map immediately with each friend's persisted last location.
        # This is the equivalent of the reference app's active_shares listener.
        for friend_id in friend_ids(service, device_id):
            if can_view(service, friend_id, device_id):
                payload = location_payload(service, friend_id)
                if payload:
                    emit("location_updated", payload)
        emit("authenticated", {"device_id":device_id})
    @socketio.on("location_update")
    def location_update(data):
        service=app.extensions["firebase_service"]; device_id=sessions.get(request.sid); data=data or {}
        if not device_id: emit("error", {"error":"authenticate first"}); return
        try: lat=float(data["latitude"]); lon=float(data["longitude"]); battery=float(data["battery_percentage"])
        except (KeyError,TypeError,ValueError): emit("error", {"error":"latitude, longitude and battery_percentage are required"}); return
        if not (-90<=lat<=90 and -180<=lon<=180 and 0<=battery<=100): emit("error", {"error":"invalid telemetry"}); return
        preference=service.ref("userPreferences",device_id).get().to_dict() or {}
        if not preference.get("location_sharing_enabled", True): return
        location = {"latitude":lat,"longitude":lon,"battery_percentage":battery,"updated_at":service.now()}
        service.ref("latestLocations", device_id).set(location, merge=True)
        payload = {"device_id":device_id, **location, "updated_at":location["updated_at"].isoformat(), "sharing_enabled":True}
        recipients = set()
        for recipient in friend_ids(service, device_id):
            if can_view(service, device_id, recipient):
                recipients.add(recipient)
        for snap in service.db.collection("groupMemberships").where("device_id","==",device_id).stream():
            group_id=snap.to_dict().get("group_id")
            for member in service.db.collection("groupMemberships").where("group_id","==",group_id).stream():
                member_id=member.to_dict().get("device_id")
                if member_id and member_id != device_id: recipients.add(member_id)
        for recipient in recipients: emit("location_updated", payload, room=recipient)
    @socketio.on("disconnect")
    def disconnect(): sessions.pop(request.sid, None)
