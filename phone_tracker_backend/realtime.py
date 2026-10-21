from flask import request
from flask_socketio import emit, join_room
from threading import Lock

def realtime_room(app_id, device_id):
    return f"{app_id}:{device_id}"

def friendship_id(first_id, second_id):
    return "_".join(sorted([first_id, second_id]))

def permission_id(owner_id, viewer_id):
    return f"{owner_id}_{viewer_id}"

def register_realtime(socketio, app):
    # Socket.IO is the live transport. Keep the authorization decision in the
    # socket session so location_update does not query Firestore for every GPS
    # event.
    sessions = {}
    state_lock = Lock()
    last_snapshot_at = {}
    app.extensions["realtime_sessions"] = sessions

    def cache_recipients(service, device_id):
        recipients = set()
        authorized_friends = set()
        for snap in service.db.collection("friendships").stream():
            members = (snap.to_dict() or {}).get("members", [])
            if device_id not in members:
                continue
            other = next((member for member in members if member != device_id), None)
            if not other:
                continue
            permission = service.ref("locationPermissions", permission_id(device_id, other)).get().to_dict() or {}
            if permission.get("enabled") is True:
                recipients.add(other)
                authorized_friends.add(other)

        for snap in service.db.collection("groupMemberships").where("device_id", "==", device_id).stream():
            group_id = snap.to_dict().get("group_id")
            if not group_id:
                continue
            for member in service.db.collection("groupMemberships").where("group_id", "==", group_id).stream():
                member_id = member.to_dict().get("device_id")
                if member_id and member_id != device_id:
                    recipients.add(member_id)
        return recipients, authorized_friends

    def snapshot_is_due(device_id, now):
        interval = app.config["LOCATION_SNAPSHOT_INTERVAL_SECONDS"]
        with state_lock:
            previous = last_snapshot_at.get(device_id)
            if previous is not None and (now - previous).total_seconds() < interval:
                return False
            # Reserve the slot before the write so concurrent socket events do
            # not issue duplicate snapshots. Roll it back if the write fails.
            last_snapshot_at[device_id] = now
            return True

    def rollback_snapshot(device_id, timestamp):
        with state_lock:
            if last_snapshot_at.get(device_id) == timestamp:
                last_snapshot_at.pop(device_id, None)
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
        owner_profile = service.ref("users", owner_id).get().to_dict() or {}
        owner_name = owner_profile.get("name") or owner_profile.get("device_model") or owner_id
        preference = service.ref("userPreferences", owner_id).get().to_dict() or {}
        return {
            "device_id": owner_id,
            "name": owner_name,
            "device_model": owner_profile.get("device_model") or owner_name,
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
            "battery_percentage": data.get("battery_percentage"),
            "updated_at": data.get("updated_at").isoformat() if hasattr(data.get("updated_at"), "isoformat") else str(data.get("updated_at")),
            "sharing_enabled": bool(preference.get("location_sharing_enabled", False)),
        }
    @socketio.on("authenticate")
    def authenticate(data):
        data=data or {}; registry=app.extensions["firebase_service"]; device_id=data.get("device_id"); app_id=data.get("app_id"); token=data.get("session_token")
        if app_id not in app.config["SUPPORTED_APP_IDS"] or not device_id:
            emit("error", {"error":"authentication failed"}); return
        try:
            service = registry.for_app(app_id)
            if not service.valid_session(device_id, app_id, token):
                emit("error", {"error":"authentication failed"}); return
        except Exception:
            app.logger.exception("Socket authentication could not reach Firebase for %s", app_id)
            emit("error", {"error":"backend data service temporarily unavailable"}); return
        owner_profile = service.ref("users", device_id).get().to_dict() or {}
        preference = service.ref("userPreferences", device_id).get().to_dict() or {}
        recipients, authorized_friends = cache_recipients(service, device_id)
        session = {
            "device_id": device_id,
            "app_id": app_id,
            "owner_name": owner_profile.get("name") or owner_profile.get("device_model") or device_id,
            "device_model": owner_profile.get("device_model") or owner_profile.get("name") or "Android device",
            "sharing_enabled": bool(preference.get("location_sharing_enabled", False)),
            "recipients": recipients,
        }
        sessions[request.sid] = session
        join_room(realtime_room(app_id, device_id))
        # Hydrate the map immediately with each friend's persisted last location.
        # This is the equivalent of the reference app's active_shares listener.
        for friend_id in authorized_friends:
            friend_profile = service.ref("users", friend_id).get().to_dict() or {}
            emit("friendship_accepted", {
                "friend_id": friend_id,
                "friend_name": friend_profile.get("name") or friend_profile.get("device_model") or friend_id,
                "sharing_enabled": True,
            })
            payload = location_payload(service, friend_id)
            if payload:
                emit("location_updated", payload)
        emit("authenticated", {"device_id":device_id})
    @socketio.on("location_update")
    def location_update(data):
        registry=app.extensions["firebase_service"]; session=sessions.get(request.sid); data=data or {}
        if not session: emit("error", {"error":"authenticate first"}); return
        device_id=session["device_id"]
        try:
            service = registry.for_app(session["app_id"])
        except Exception:
            app.logger.exception("Socket location update could not reach Firebase for %s", session.get("app_id"))
            emit("error", {"error":"backend data service temporarily unavailable"}); return
        try: lat=float(data["latitude"]); lon=float(data["longitude"]); battery=float(data["battery_percentage"])
        except (KeyError,TypeError,ValueError): emit("error", {"error":"latitude, longitude and battery_percentage are required"}); return
        if not (-90<=lat<=90 and -180<=lon<=180 and 0<=battery<=100): emit("error", {"error":"invalid telemetry"}); return
        location = {"latitude":lat,"longitude":lon,"battery_percentage":battery,"updated_at":service.now()}
        if not session["sharing_enabled"]: return
        if snapshot_is_due(device_id, location["updated_at"]):
            try:
                service.ref("latestLocations", device_id).set(location, merge=True)
            except Exception:
                rollback_snapshot(device_id, location["updated_at"])
                app.logger.exception("Could not persist hourly location snapshot for %s", device_id)

        # Deliver the current coordinate directly from the socket payload. No
        # Firestore reads are needed for the live path.
        payload = {"device_id":device_id, "name":session["owner_name"], "device_model":session["device_model"], **location, "updated_at":location["updated_at"].isoformat(), "sharing_enabled":True}
        for recipient in session["recipients"]:
            emit("location_updated", payload, room=realtime_room(session["app_id"], recipient))
    @socketio.on("disconnect")
    def disconnect(): sessions.pop(request.sid, None)
