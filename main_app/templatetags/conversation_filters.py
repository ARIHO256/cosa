from pathlib import Path

from django import template

register = template.Library()


@register.filter
def is_from(entry, user):
    """
    Template helper that checks if the given conversation entry
    was sent by the provided user.
    """
    if entry is None or user is None:
        return False
    check = getattr(entry, "is_from_user", None)
    if callable(check):
        return check(user)
    return False


@register.filter
def is_image(attachment) -> bool:
    """Return True when the attachment path looks like an image."""
    if not attachment:
        return False

    name = getattr(attachment, "name", "")
    if not name:
        return False

    ext = Path(str(name)).suffix.lower()
    return ext in {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".webp",
        ".svg",
        ".heic",
        ".heif",
    }


@register.filter
def display_name(user):
    """Return a sensible display name for a user instance."""
    if user is None:
        return "Unknown"
    try:
        name = user.get_full_name()
    except Exception:
        name = ""
    if name:
        return name
    username = getattr(user, "username", "")
    return username or "Unknown"


@register.filter
def initial(user):
    """Return the first letter to use as an avatar fallback."""
    if user is None:
        return "?"
    try:
        name = user.get_full_name()
    except Exception:
        name = ""
    source = name.strip() if name else str(getattr(user, "username", "")).strip()
    if source:
        return source[0].upper()
    return "?"
