"""HA-free spec declaration for Stash HA."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final


class _P(str, Enum):
    SENSOR = "sensor"
    IMAGE = "image"
    MEDIA_PLAYER = "media_player"


class ModuleStatus(str, Enum):
    READY = "READY"


@dataclass(frozen=True)
class ModuleSpec:
    module_id: str
    name: str
    description: str
    status: ModuleStatus
    platforms: tuple[_P, ...]
    has_services: bool = False
    icon: str | None = None


SPEC: Final[ModuleSpec] = ModuleSpec(
    module_id="stash_ha",
    name="Stash HA",
    description=(
        "Stash-Mediaplayer-Bridge: GraphQL-Client, Library-Statistik-Coordinator, "
        "Playback-Erkennung über play_duration-Delta, Cover-Image und Display-Only "
        "Media-Player."
    ),
    status=ModuleStatus.READY,
    platforms=(_P.SENSOR, _P.IMAGE, _P.MEDIA_PLAYER),
    has_services=True,
    icon="mdi:movie-play",
)
