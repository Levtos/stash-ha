"""Constants for Stash Player integration."""

from __future__ import annotations

DOMAIN = "stash_player"

CONF_URL = "url"
CONF_API_KEY = "api_key"
CONF_PLAYER_NAME = "player_name"
CONF_POLL_INTERVAL = "poll_interval"
CONF_USE_WEBHOOK = "use_webhook"
CONF_WEBHOOK_PORT = "webhook_port"
CONF_NSFW_MODE = "nsfw_mode"

DEFAULT_PLAYER_NAME = "Stash"
DEFAULT_POLL_INTERVAL = 5
DEFAULT_SCAN_INTERVAL = 300
DEFAULT_USE_WEBHOOK = False
DEFAULT_WEBHOOK_PORT = 8765
DEFAULT_NSFW_MODE = "blur"

NSFW_BLUR = "blur"
NSFW_HIDDEN = "hidden"
NSFW_FULL = "full"

COORDINATOR_KEY = "coordinator"
LIBRARY_COORDINATOR_KEY = "library_coordinator"
CLIENT_KEY = "client"
WEBHOOK_VIEW_KEY = "webhook_view"

PLATFORMS = ["media_player", "camera", "sensor", "button", "binary_sensor"]

# ── GraphQL queries (playback) ────────────────────────────────────────────────

ACTIVE_SCENE_QUERY = """
query ActiveScene {
  findScenes(
    filter: { per_page: 2, sort: "updated_at", direction: DESC }
  ) {
    scenes {
      id
      title
      rating100
      play_count
      resume_time
      paths {
        screenshot
      }
      performers { name }
      tags { name }
      studio { name }
      files {
        duration
        size
        width
        height
      }
    }
  }
}
"""

PLAYING_STATE_QUERY = """
query PlayingState {
  sceneStreams {
    url
    mime_type
  }
}
"""

SCENE_BY_ID_QUERY = """
query SceneById($id: ID!) {
  findScene(id: $id) {
    id
    title
    rating100
    play_count
    resume_time
    paths {
      screenshot
    }
    performers { name }
    tags { name }
    studio { name }
    files {
      duration
      size
      width
      height
    }
  }
}
"""

GENERATE_SCREENSHOT_MUTATION = """
mutation GenerateScreenshot($id: ID!) {
  sceneGenerateScreenshot(id: $id)
}
"""

SAVE_ACTIVITY_MUTATION = """
mutation SaveScene($id: ID!, $pos: Float!) {
  sceneSaveActivity(id: $id, resume_time: $pos) { id }
}
"""
