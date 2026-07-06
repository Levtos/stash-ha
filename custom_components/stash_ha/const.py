"""Constants for the standalone Stash HA integration."""
from __future__ import annotations

from typing import Final

DOMAIN: Final[str] = "stash_ha"
MODULE_ID = "stash_ha"
NAME = "Stash HA"

DATA_ENTRIES: Final[str] = "entries"
DATA_SERVICES_REGISTERED: Final[str] = "services_registered"

# Kept in ConfigEntry.data for entries migrated from the previous umbrella module.
CONF_MODULE_ID: Final[str] = "_module_id"

# --- Config / options ---
CONF_URL = "url"
CONF_API_KEY = "api_key"
CONF_PLAYER_NAME = "player_name"
CONF_POLL_INTERVAL = "poll_interval"
CONF_USE_WEBHOOK = "use_webhook"
CONF_NSFW_MODE = "nsfw_mode"

DEFAULT_PLAYER_NAME = "Stash"
DEFAULT_POLL_INTERVAL = 5            # seconds; >= 2 enforced in coordinator
DEFAULT_LIBRARY_SCAN_INTERVAL = 300  # 5 min
DEFAULT_USE_WEBHOOK = False
DEFAULT_NSFW_MODE = "blur"

# Playback-detection tuning (see docstring of StashPlaybackCoordinator).
STREAM_ACTIVITY_GRACE_SECONDS = 60
FRESH_PLAY_THRESHOLD_SECONDS = 30
ACTIVE_SCENE_WINDOW = 10

# Fixed number of slot title sensors — one observable state per active scene so
# the Title Classifier can watch each active stream as a separate source.
SLOT_COUNT = 4

NSFW_BLUR = "blur"
NSFW_HIDDEN = "hidden"
NSFW_FULL = "full"
NSFW_MODES = [NSFW_BLUR, NSFW_HIDDEN, NSFW_FULL]

# --- Services (registered as stash_ha.<action>) ---
SERVICE_METADATA_SCAN = "metadata_scan"
SERVICE_METADATA_CLEAN = "metadata_clean"
SERVICE_METADATA_GENERATE = "metadata_generate"
SERVICE_METADATA_AUTO_TAG = "metadata_auto_tag"
SERVICE_METADATA_IDENTIFY = "metadata_identify"
SERVICE_GENERATE_SCREENSHOT = "generate_screenshot"
SERVICE_SAVE_ACTIVITY = "save_activity"

# --- Entity unique-id suffixes ---
# Library sensors
UID_SCENES = "scenes_count"
UID_MOVIES = "movies_count"
UID_PERFORMERS = "performers_count"
UID_STUDIOS = "studios_count"
UID_TAGS = "tags_count"
UID_IMAGES = "images_count"
UID_GALLERIES = "galleries_count"
UID_MARKERS = "markers_count"
UID_VERSION = "version"
# Playback sensors
UID_ACTIVE_STREAMS = "active_streams"
UID_CURRENTLY_PLAYING = "currently_playing"
UID_LAST_PLAYED_TITLE = "last_played_title"
UID_LAST_PLAYED_AT = "last_played_at"


def uid_slot_title(slot: int) -> str:
    """Unique-id suffix for the slot-N title sensor (stable across polls)."""
    return f"slot_{slot}_title"
# Image + media_player
UID_COVER = "cover"
UID_PLAYER = "player"

# --- GraphQL queries -----------------------------------------------------------

ACTIVE_SCENE_QUERY = """
query ActiveScene {
  findScenes(
    scene_filter: { last_played_at: { modifier: NOT_NULL, value: "" } }
    filter: { per_page: 10, sort: "last_played_at", direction: DESC }
  ) {
    scenes {
      id
      title
      rating100
      play_count
      play_duration
      resume_time
      last_played_at
      paths { screenshot }
      performers { name }
      tags { name }
      studio { name }
      files { duration size width height }
    }
  }
}
"""


def storage_key(_module_id: str, suffix: str) -> str:
    """Stable Home Assistant storage key for this standalone integration."""
    return f"{DOMAIN}_{suffix}"


def service_name(_module_id: str, action: str) -> str:
    """Standalone service name, e.g. `stash_ha.metadata_scan`."""
    return action


def unique_id(_module_id: str, *parts: str) -> str:
    """Standalone unique_id with integration prefix."""
    return "_".join((DOMAIN, *parts))
