from collections import defaultdict
from flask import request
from flask_socketio import emit, join_room
from .services.firebase_service import FirebaseService

def register_realtime(socketio, app):
    sessions = {}
    latest = {}
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
        latest[device_id]={"device_id":device_id,"latitude":lat,"longitude":lon,"battery_percentage":battery,"updated_at":service.now().isoformat()}
        recipients = set()
        for snap in service.db.collection("friendships").stream():
            members=snap.to_dict().get("members",[])
            if device_id in members: recipients.update(x for x in members if x != device_id)
        for snap in service.db.collection("groupMemberships").where("device_id","==",device_id).stream():
            group_id=snap.to_dict().get("group_id")
            for member in service.db.collection("groupMemberships").where("group_id","==",group_id).stream():
                member_id=member.to_dict().get("device_id")
                if member_id and member_id != device_id: recipients.add(member_id)
        for recipient in recipients: emit("location_updated", latest[device_id], room=recipient)
    @socketio.on("disconnect")
    def disconnect(): sessions.pop(request.sid, None)
