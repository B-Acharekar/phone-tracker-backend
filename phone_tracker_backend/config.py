import os
from dotenv import load_dotenv

load_dotenv()

DEFAULT_APP_IDS = ("phone-tracker-0011", "phone-tracker-0012")
configured_app_ids = os.getenv("SUPPORTED_APP_IDS", ",".join(DEFAULT_APP_IDS))
SUPPORTED_APP_IDS = tuple(item.strip() for item in configured_app_ids.split(",") if item.strip())

# Both Android variants use one backend deployment, while each app can use an
# independent Firebase project. Shared variables remain valid as a fallback.
shared_credential_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
shared_project_id = os.getenv("FIREBASE_PROJECT_ID", "")
app_credentials = {
    "phone-tracker-0011": os.getenv("APP_0011_CREDENTIALS", "") or shared_credential_path,
    "phone-tracker-0012": os.getenv("APP_0012_CREDENTIALS", "") or shared_credential_path,
}
app_project_ids = {
    "phone-tracker-0011": os.getenv("APP_0011_FIREBASE_PROJECT_ID", "") or shared_project_id,
    "phone-tracker-0012": os.getenv("APP_0012_FIREBASE_PROJECT_ID", "") or shared_project_id,
}

class Config:
    SUPPORTED_APP_IDS = SUPPORTED_APP_IDS
    APP_CREDENTIALS = app_credentials
    APP_PROJECT_IDS = app_project_ids
    FIREBASE_PROJECT_ID = shared_project_id
    GROUP_ICONS = {"home", "heart", "building", "tree", "people"}
    INVITE_TTL_HOURS = int(os.getenv("INVITE_TTL_HOURS", "24"))
    SESSION_DAYS = int(os.getenv("SESSION_DAYS", "30"))
    MAX_LOCATION_UPDATES_PER_MINUTE = int(os.getenv("MAX_LOCATION_UPDATES_PER_MINUTE", "120"))
    # Live coordinates are delivered over Socket.IO. Firestore keeps only a
    # periodic snapshot so updates do not consume a write on every event.
    LOCATION_SNAPSHOT_INTERVAL_SECONDS = int(os.getenv("LOCATION_SNAPSHOT_INTERVAL_SECONDS", "3600"))
