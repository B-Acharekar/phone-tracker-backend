# Phone Tracker Backend

One Flask backend for both Android app variants. There is no signup or password login. The Android app sends `Settings.Secure.ANDROID_ID` as `device_id`.

## App variants

- `phone-tracker-0012`: friend requests, received requests, sent requests, and connection list.
- `phone-tracker-0011`: profile, groups, group invite codes, and location sharing.

## Run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

The backend uses Firebase Admin SDK and Firestore. It requires a Firebase service-account credential on the server.

## Rules

- Invite codes are six uppercase alphanumeric characters.
- `device_id` is unique in the backend; duplicate registration is rejected.
- Codes expire after 24 hours by default.
- A code is consumed after one successful use and cannot be reused.
- Location sharing is explicit and off by default.
- Location includes latitude, longitude, accuracy, battery percentage, and update time.
# Phone Tracker Backend

Modular Flask backend for Phone Tracker 0011 and 0012 in one deployment. Each app variant can use its own isolated Firebase project.

## Structure

- `app.py` — process entry point only.
- `phone_tracker_backend/config.py` — environment-backed settings.
- `phone_tracker_backend/services/firebase_service.py` — Firebase Admin/Firestore access.
- `phone_tracker_backend/auth.py` — device ID + session-token authentication.
- `phone_tracker_backend/routes/` — REST APIs for installation, friends, profile, sharing, and groups.
- `phone_tracker_backend/realtime.py` — authenticated Socket.IO location channel.

## Firebase service account

Do not commit or paste Firebase admin JSON files. Store them outside this repository and configure one credential path per app with `APP_0011_CREDENTIALS` and `APP_0012_CREDENTIALS`. `GOOGLE_APPLICATION_CREDENTIALS` is an optional shared fallback. The server uses Firebase Admin credentials only; Android never receives these files.

## Run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:SUPPORTED_APP_IDS='phone-tracker-0011,phone-tracker-0012'
$env:APP_0011_CREDENTIALS='C:\secure\phone-tracker-0011-firebase.json'
$env:APP_0011_FIREBASE_PROJECT_ID='pa-mkt-11-phone-tracker'
$env:APP_0012_CREDENTIALS='C:\secure\phone-tracker-0012-firebase.json'
$env:APP_0012_FIREBASE_PROJECT_ID='pa-mkt-12-phone-tracker'
python app.py
```

Register an installation first with `POST /api/v1/installations` using either `{ "device_id": "...", "app_id": "phone-tracker-0011" }` or `{ "device_id": "...", "app_id": "phone-tracker-0012" }`. Android ID is the user identity and app ID identifies which client variant is connecting. Store the returned session token securely in Android and send it with every REST request and Socket.IO authentication event.

Both variants run against the same backend URL, but each request is routed to the Firebase service configured for its app ID. Configure `APP_0011_CREDENTIALS` and `APP_0011_FIREBASE_PROJECT_ID` for 0011, and `APP_0012_CREDENTIALS` and `APP_0012_FIREBASE_PROJECT_ID` for 0012. Keep `SUPPORTED_APP_IDS=phone-tracker-0011,phone-tracker-0012`. A Firestore outage in one project returns a scoped `503` and does not change the other app's Firebase client or Socket.IO rooms.

Location telemetry is validated and delivered directly over the authenticated Socket.IO channel. Firestore stores only a periodic snapshot (one hour by default) in `latestLocations/{device_id}`. The snapshot throttle is process-local; use a shared cache/lock before running multiple backend instances.

## Group APIs

All group endpoints require the `X-Device-ID`, `X-App-ID`, and `X-Session-Token` headers returned by installation registration.

- `GET /api/v1/groups` returns the authenticated device's groups.
- `DELETE /api/v1/groups/{group_id}` deletes a group when called by its owner. The group's memberships and invite records are deleted with it.
