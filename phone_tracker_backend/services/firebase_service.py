import hashlib, secrets, string
from datetime import datetime, timedelta, timezone
import firebase_admin
from firebase_admin import credentials, firestore

class FirebaseService:
    def __init__(self):
        if not firebase_admin._apps:
            firebase_admin.initialize_app(credentials.ApplicationDefault())
        self.db = firestore.client()

    @staticmethod
    def now(): return datetime.now(timezone.utc)
    @staticmethod
    def token_hash(value): return hashlib.sha256(value.encode()).hexdigest()
    @staticmethod
    def invite_code(): return "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    def ref(self, collection, key): return self.db.collection(collection).document(key)
    def register(self, device_id, app_id):
        ref = self.ref("installations", device_id); snap = ref.get()
        raw = secrets.token_urlsafe(32)
        ref.set({"device_id": device_id, "app_id": app_id, "session_token_hash": self.token_hash(raw), "session_expires_at": self.now() + timedelta(days=30), "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)
        self.ref("users", device_id).set({"device_id": device_id, "app_id": app_id, "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)
        return raw
    def valid_session(self, device_id, app_id, token):
        snap = self.ref("installations", device_id).get()
        if not snap.exists: return False
        data = snap.to_dict(); expiry = data.get("session_expires_at")
        return data.get("app_id") == app_id and data.get("session_token_hash") == self.token_hash(token) and expiry and expiry > self.now()
