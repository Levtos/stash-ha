"""Constants for the Stash Player integration."""

from __future__ import annotations

DOMAIN = "stash_player"
PLATFORMS = ["media_player", "camera"]

CONF_STASH_URL = "stash_url"
CONF_API_KEY = "api_key"
CONF_PLAYER_NAME = "player_name"
CONF_POLL_INTERVAL = "poll_interval"
CONF_USE_WEBHOOK = "use_webhook"
CONF_WEBHOOK_PORT = "webhook_port"
CONF_NSFW_MODE = "nsfw_mode"

DEFAULT_PLAYER_NAME = "Stash"
DEFAULT_POLL_INTERVAL = 5
DEFAULT_USE_WEBHOOK = False
DEFAULT_WEBHOOK_PORT = 8765
DEFAULT_NSFW_MODE = "blur"

NSFW_BLUR = "blur"
NSFW_HIDDEN = "hidden"
NSFW_FULL = "full"
NSFW_MODES = [NSFW_BLUR, NSFW_HIDDEN, NSFW_FULL]

COORDINATOR_KEY = "coordinator"
CLIENT_KEY = "client"
WEBHOOK_VIEW_KEY = "webhook_view"

ACTIVE_SCENE_QUERY = """
query ActiveScene {
  findScenes(
    scene_filter: { interactive: false }
    filter: { per_page: 2, sort: "updated_at", direction: DESC }
  ) {
    scenes {
      id
      title
      date
      rating100
      play_count
      resume_time
      duration: file { duration }
      paths {
        screenshot
        preview
        stream
      }
      performers {
        name
        gender
      }
      tags {
        name
      }
      studio {
        name
        image_path
      }
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

SAVE_ACTIVITY_MUTATION = """
mutation SaveScene($id: ID!, $pos: Float!) {
  sceneSaveActivity(id: $id, resume_time: $pos) { id }
}
"""

GENERATE_SCREENSHOT_MUTATION = """
mutation GenerateScreenshot($id: ID!) {
  sceneGenerateScreenshot(id: $id)
}
"""
