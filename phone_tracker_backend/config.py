import os
from dotenv import load_dotenv

load_dotenv()

ACTIVE_APP_ID = os.getenv("ACTIVE_APP_ID", "phone-tracker-0012")
credential_key = "APP_0011_CREDENTIALS" if ACTIVE_APP_ID == "phone-tracker-0011" else "APP_0012_CREDENTIALS"
project_key = "APP_0011_FIREBASE_PROJECT_ID" if ACTIVE_APP_ID == "phone-tracker-0011" else "APP_0012_FIREBASE_PROJECT_ID"
credential_path = os.getenv(credential_key, "")
if credential_path:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credential_path

class Config:
    SERVICE_APP_ID = ACTIVE_APP_ID
    FIREBASE_PROJECT_ID = os.getenv(project_key, "")
    GROUP_ICONS = {"home", "heart", "building", "tree", "people"}
    INVITE_TTL_HOURS = int(os.getenv("INVITE_TTL_HOURS", "24"))
    SESSION_DAYS = int(os.getenv("SESSION_DAYS", "30"))
    MAX_LOCATION_UPDATES_PER_MINUTE = int(os.getenv("MAX_LOCATION_UPDATES_PER_MINUTE", "120"))
    # Live coordinates are delivered over Socket.IO. Firestore keeps only a
    # periodic snapshot so updates do not consume a write on every event.
    LOCATION_SNAPSHOT_INTERVAL_SECONDS = int(os.getenv("LOCATION_SNAPSHOT_INTERVAL_SECONDS", "3600"))
