import os
from dotenv import load_dotenv

load_dotenv()

DEFAULT_APP_IDS = ("phone-tracker-0011", "phone-tracker-0012")
configured_app_ids = os.getenv("SUPPORTED_APP_IDS", ",".join(DEFAULT_APP_IDS))
SUPPORTED_APP_IDS = tuple(item.strip() for item in configured_app_ids.split(",") if item.strip())

# Both Android variants use one backend deployment and one Firebase project.
# Keep the old per-variant variables as fallbacks so existing deployments can
# migrate without changing their secret names immediately.
credential_path = (
    os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    or os.getenv("APP_0011_CREDENTIALS")
    or os.getenv("APP_0012_CREDENTIALS")
    or ""
)
if credential_path:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credential_path

class Config:
    SUPPORTED_APP_IDS = SUPPORTED_APP_IDS
    FIREBASE_PROJECT_ID = (
        os.getenv("FIREBASE_PROJECT_ID")
        or os.getenv("APP_0011_FIREBASE_PROJECT_ID")
        or os.getenv("APP_0012_FIREBASE_PROJECT_ID")
        or ""
    )
    GROUP_ICONS = {"home", "heart", "building", "tree", "people"}
    INVITE_TTL_HOURS = int(os.getenv("INVITE_TTL_HOURS", "24"))
    SESSION_DAYS = int(os.getenv("SESSION_DAYS", "30"))
    MAX_LOCATION_UPDATES_PER_MINUTE = int(os.getenv("MAX_LOCATION_UPDATES_PER_MINUTE", "120"))
    # Live coordinates are delivered over Socket.IO. Firestore keeps only a
    # periodic snapshot so updates do not consume a write on every event.
    LOCATION_SNAPSHOT_INTERVAL_SECONDS = int(os.getenv("LOCATION_SNAPSHOT_INTERVAL_SECONDS", "3600"))
