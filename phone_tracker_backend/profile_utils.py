"""Consistent public profile-field handling for all app variants."""

UNKNOWN_USER = "Unknown user"


def _first_text(data, keys):
    for key in keys:
        value = data.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def display_name(data, fallback="", prefer_legacy=True):
    """Return a profile name using the selected app's field precedence."""
    if not prefer_legacy:
        return _first_text(data or {}, ("name", "device_model")) or fallback
    return _first_text(
        data or {},
        (
            "profile_name",
            "profileName",
            "full_name",
            "fullName",
            "username",
            "name",
        ),
    ) or fallback


def legacy_display_name(data, fallback=""):
    """Preserve the pre-refactor 0012 display-name behavior."""
    return display_name(data, fallback, prefer_legacy=False)


def avatar_value(data):
    return _first_text(data or {}, ("avatar", "profile_picture", "profilePicture")) or None


def public_profile(device_id, data):
    data = data or {}
    name = display_name(data, UNKNOWN_USER)
    avatar = avatar_value(data)
    return {
        "device_id": device_id,
        "id": device_id,
        "userId": device_id,
        "name": name,
        "display_name": name,
        "profile_name": name,
        "fullName": name,
        "avatar": avatar,
        "profilePicture": avatar,
        "profile": {
            "name": name,
            "avatar": avatar,
            "profilePicture": avatar,
        },
        "device_model": _first_text(data, ("device_model",)) or "Android device",
    }
