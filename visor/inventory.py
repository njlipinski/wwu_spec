"""
Inventory persistence:

Stores the user's saved sample IDs (their "inventory") across sessions.
On Windows/Mac (local dev), persists to a plain text file at the project root.
On Linux (production), uses the Notepad session-based storage system.
"""
import json
import logging
import random
import sys
from pathlib import Path

from django.conf import settings

from notetaking.notepad import Notepad
from visor.models import Sample

logger = logging.getLogger("django")

# Platforms that use the local-file persistence path instead of Notepad sessions.
_LOCAL_FILE_PLATFORMS = ('win32', 'cygwin', 'darwin')


def _local_inventory_path() -> Path:
    """Path to the local inventory file, anchored to the project directory."""
    return Path(settings.BASE_DIR) / "local_user_inventory.txt"


def ip(request) -> str:
    # forwarded ip from server layer -- this specific property may only
    # be populated by nginx
    forwarded_ip = request.META.get('HTTP_X_REAL_IP')
    if forwarded_ip is not None:
        return forwarded_ip
    return request.META.get('REMOTE_ADDR')


def session_id(request) -> str:
    address = ip(request)
    if request.session.get('identifier') is None:
        request.session[
            'identifier'
        ] = f"{address}_{random.randint(1000000, 9999999)}"
        logger.warning(
            f"started session with identifier "
            f"{request.session['identifier']}"
        )
    return request.session['identifier']


def get_inventory_id_json(request) -> str:
    """Load the user's inventory ID list as a JSON string."""
    if sys.platform in _LOCAL_FILE_PLATFORMS:
        inv = _local_inventory_path()
        if inv.exists():
            contents = inv.read_text().strip()
            return contents if contents else "[]"
        inv.write_text("[]")
        return "[]"
    try:
        user_notes = Notepad(_session_id(request))
    except FileNotFoundError:
        user_notes = Notepad.open(_session_id(request))
        user_notes['inventory'] = "[]"
    return user_notes['inventory']


def set_inventory_id_json(request) -> None:
    """Save the user's inventory ID list (from ?inventory=... query param)."""
    inventory_ids = request.GET.get("inventory")
    if inventory_ids is None:
        return
    if sys.platform in _LOCAL_FILE_PLATFORMS:
        inv = _local_inventory_path()
        inv.write_text(inventory_ids)
        return
    try:
        user_notes = Notepad(_session_id(request))
    except FileNotFoundError:
        user_notes = Notepad.open(_session_id(request))
    user_notes['inventory'] = inventory_ids


def load_inventory(inventory_id_json: str) -> str:
    inventory_id_list = json.loads(inventory_id_json)
    inventory_samples = Sample.objects.filter(id__in=inventory_id_list)
    return json.dumps(
        [sample.as_json(brief=True) for sample in inventory_samples]
    )
