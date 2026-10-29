import hashlib, secrets, string
from datetime import datetime, timedelta, timezone
from threading import Lock
from urllib.parse import quote
import firebase_admin
from firebase_admin import credentials, firestore, storage

class FirebaseService:
    def __init__(self, credential_path="", project_id="", storage_bucket="", app_name="default", session_days=30):
        self.session_days = session_days
        try:
            firebase_app = firebase_admin.get_app(app_name)
        except ValueError:
            app_credential = credentials.Certificate(credential_path) if credential_path else credentials.ApplicationDefault()
            options = {}
            if project_id:
                options["projectId"] = project_id
            if storage_bucket:
                options["storageBucket"] = storage_bucket
            options = options or None
            firebase_app = firebase_admin.initialize_app(app_credential, options=options, name=app_name)
        self.firebase_app = firebase_app
        self.db = firestore.client(app=firebase_app)

    @staticmethod
    def now(): return datetime.now(timezone.utc)
    @staticmethod
    def token_hash(value): return hashlib.sha256(value.encode()).hexdigest()
    @staticmethod
    def invite_code(): return "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    def ref(self, collection, key): return self.db.collection(collection).document(key)

    def upload_avatar(self, device_id, content, content_type):
        """Upload an avatar and return a stable Firebase Storage download URL."""
        bucket = storage.bucket(app=self.firebase_app)
        object_name = f"avatars/{device_id}/{secrets.token_urlsafe(18)}"
        token = secrets.token_urlsafe(24)
        blob = bucket.blob(object_name)
        blob.metadata = {"firebaseStorageDownloadTokens": token}
        blob.upload_from_string(content, content_type=content_type)
        return (
            f"https://firebasestorage.googleapis.com/v0/b/{quote(bucket.name, safe='')}/o/"
            f"{quote(object_name, safe='')}?alt=media&token={token}"
        )
    def register(self, device_id, app_id):
        ref = self.ref("installations", device_id); snap = ref.get()
        raw = secrets.token_urlsafe(32)
        ref.set({"device_id": device_id, "app_id": app_id, "session_token_hash": self.token_hash(raw), "session_expires_at": self.now() + timedelta(days=self.session_days), "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)
        self.ref("users", device_id).set({"device_id": device_id, "app_id": app_id, "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)
        return raw
    def valid_session(self, device_id, app_id, token):
        snap = self.ref("installations", device_id).get()
        if not snap.exists: return False
        data = snap.to_dict(); expiry = data.get("session_expires_at")
        return data.get("app_id") == app_id and data.get("session_token_hash") == self.token_hash(token) and expiry and expiry > self.now()

class FirebaseServiceRegistry:
    """Lazily creates one isolated Firebase client per supported app ID."""
    def __init__(self, config):
        self.supported_app_ids = tuple(config["SUPPORTED_APP_IDS"])
        self.credentials = config.get("APP_CREDENTIALS", {})
        self.project_ids = config.get("APP_PROJECT_IDS", {})
        self.storage_buckets = config.get("APP_STORAGE_BUCKETS", {})
        self.session_days = config.get("SESSION_DAYS", 30)
        self._services = {}
        self._lock = Lock()

    def for_app(self, app_id):
        if app_id not in self.supported_app_ids:
            raise ValueError(f"unsupported app ID: {app_id}")
        with self._lock:
            service = self._services.get(app_id)
            if service is None:
                service = FirebaseService(
                    credential_path=self.credentials.get(app_id, ""),
                    project_id=self.project_ids.get(app_id, ""),
                    storage_bucket=self.storage_buckets.get(app_id, ""),
                    app_name=f"phone-tracker-{app_id}",
                    session_days=self.session_days,
                )
                self._services[app_id] = service
            return service
