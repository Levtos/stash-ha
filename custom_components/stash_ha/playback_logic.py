"""Pure helpers for Stash playback detection.

Stash exposes no first-class "currently streaming" query. We poll the
recently-played scenes and infer activity from `play_duration` deltas. This
module isolates the reasoning so it can be unit-tested without HA / aiohttp.

Detection rule per scene:
  1. Primary — if `play_duration` strictly increased since the last poll, the
     scene is streaming *now*. We treat it as streaming for
     STREAM_ACTIVITY_GRACE_SECONDS after the last observed increase so
     variable save intervals do not flap state.
  2. Fallback for first observation (e.g. HA restart mid-stream) — if there
     is no prior signal for this scene but its `last_played_at` is younger
     than FRESH_PLAY_THRESHOLD_SECONDS, treat it as streaming until the next
     poll provides a real delta.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit, urlunsplit

from .const import (
    FRESH_PLAY_THRESHOLD_SECONDS,
    STREAM_ACTIVITY_GRACE_SECONDS,
)


def rewrite_url(base_url: str, url: str) -> str:
    """Replace scheme/host/port of a Stash-returned URL with our base.

    Stash often returns asset URLs with whatever hostname it sees itself as
    (`localhost`, the Docker service name, an internal IP). Those URLs are
    not reachable from Home Assistant, so we keep the path and query but
    swap the authority for the URL the user actually configured.
    """
    base = urlsplit(base_url)
    target = urlsplit(url)
    if not target.scheme and not target.netloc:
        # Relative path — just prepend the base.
        prefix = base_url
        return f"{prefix}{url if url.startswith('/') else '/' + url}"
    return urlunsplit(
        (base.scheme, base.netloc, target.path, target.query, target.fragment)
    )


def parse_play_duration(raw: Any) -> float:
    try:
        return float(raw or 0)
    except (TypeError, ValueError):
        return 0.0


def is_streaming(last_activity_ts: float | None, now_ts: float) -> bool:
    if last_activity_ts is None:
        return False
    return (now_ts - last_activity_ts) < STREAM_ACTIVITY_GRACE_SECONDS


def evaluate_scene_signal(
    *,
    play_duration: float,
    prev_signal: dict[str, Any] | None,
    last_played_age_s: float | None,
    now_ts: float,
) -> dict[str, Any]:
    """Decide whether a scene should count as streaming based on the latest
    poll.

    Returns:
        {
            "play_duration": float,
            "last_activity_ts": float | None,
            "delta_advanced": bool,
            "fresh_first_seen": bool,
            "streaming": bool,
        }
    """
    delta_advanced = False
    fresh_first_seen = False

    if prev_signal is None:
        if (
            last_played_age_s is not None
            and 0 <= last_played_age_s < FRESH_PLAY_THRESHOLD_SECONDS
        ):
            fresh_first_seen = True
    else:
        prev_duration = parse_play_duration(prev_signal.get("play_duration"))
        if play_duration > prev_duration:
            delta_advanced = True

    last_activity_ts = (prev_signal or {}).get("last_activity_ts")
    if delta_advanced or fresh_first_seen:
        last_activity_ts = now_ts

    return {
        "play_duration": play_duration,
        "last_activity_ts": last_activity_ts,
        "delta_advanced": delta_advanced,
        "fresh_first_seen": fresh_first_seen,
        "streaming": is_streaming(last_activity_ts, now_ts),
    }


def prune_stale_signals(
    signals: dict[str, dict[str, Any]],
    seen_ids: set[str],
    now_ts: float,
) -> None:
    """Drop signal state for scenes we haven't seen in a while. Mutates."""
    cutoff = STREAM_ACTIVITY_GRACE_SECONDS * 2
    stale = [
        sid for sid, sig in signals.items()
        if sid not in seen_ids
        and (now_ts - (sig.get("last_activity_ts") or 0)) > cutoff
    ]
    for sid in stale:
        signals.pop(sid, None)


def assign_slots(
    scenes: list[dict[str, Any]] | None,
    prev_mapping: dict[str, int] | None,
    slot_count: int = 4,
) -> dict[str, int]:
    """Sticky scene_id -> slot assignment for the fixed slot title sensors.

    Slots are 1-based (1..slot_count). Rules:
      * A still-active scene keeps the slot it already held (order changes of
        ``scenes`` never move an existing assignment — no flapping).
      * Scenes that are no longer active are dropped from the mapping.
      * New scenes take the lowest free slot, in ``scenes`` order (which is
        last_played_at DESC, so the most recent new scene gets the lowest slot).
      * When more scenes are active than there are slots, the overflow scenes
        simply get no slot (never crash, never a dynamic entity).
      * Scenes without an ``id`` are skipped (cannot be tracked stably).

    Returns a fresh mapping; ``prev_mapping`` is not mutated.
    """
    active_ids: list[str] = []
    seen: set[str] = set()
    for scene in scenes or []:
        sid_val = scene.get("id")
        if sid_val is None:
            continue
        sid = str(sid_val)
        if sid in seen:
            continue
        seen.add(sid)
        active_ids.append(sid)

    # 1. Keep valid existing assignments for scenes that are still active.
    new_mapping: dict[str, int] = {}
    used_slots: set[int] = set()
    for sid, slot in (prev_mapping or {}).items():
        if sid in seen and 1 <= slot <= slot_count and slot not in used_slots:
            new_mapping[sid] = slot
            used_slots.add(slot)

    # 2. Assign new scenes to the lowest free slot, in active order.
    free_slots = [n for n in range(1, slot_count + 1) if n not in used_slots]
    fi = 0
    for sid in active_ids:
        if sid in new_mapping:
            continue
        if fi >= len(free_slots):
            break  # overflow — no free slot, scene gets none
        new_mapping[sid] = free_slots[fi]
        fi += 1

    return new_mapping


def slots_view(
    scenes: list[dict[str, Any]] | None,
    mapping: dict[str, int] | None,
    slot_count: int = 4,
) -> dict[int, dict[str, Any] | None]:
    """Resolve a scene_id -> slot ``mapping`` into a {slot: scene | None} view.

    Every slot 1..slot_count is present; unoccupied slots map to None (so the
    slot sensor reports no title, never an "idle" string). A mapped scene_id
    that is not in ``scenes`` also resolves to None.
    """
    scenes_by_id = {
        str(s.get("id")): s for s in scenes or [] if s.get("id") is not None
    }
    view: dict[int, dict[str, Any] | None] = {
        n: None for n in range(1, slot_count + 1)
    }
    for sid, slot in (mapping or {}).items():
        if 1 <= slot <= slot_count:
            view[slot] = scenes_by_id.get(sid)
    return view


def current_playing_title(scenes: list[dict[str, Any]] | None) -> str | None:
    """State for the Currently Playing sensor: the most-recently-active scene's
    title. ``scenes`` are ordered last_played_at DESC, so ``scenes[0]`` is the
    most recent. Multiple active scenes are NEVER joined into a combined
    "A | B" state — the separate titles stay in the sensor's attributes.
    Returns None when nothing is streaming (or the top scene has no title).
    """
    if not scenes:
        return None
    return scenes[0].get("title")


def summarise_last_played(top_scene: dict[str, Any]) -> dict[str, Any]:
    """Build the `last_played` summary used by sensors."""
    studio = top_scene.get("studio") or {}
    performers = top_scene.get("performers") or []
    return {
        "id": top_scene.get("id"),
        "title": top_scene.get("title"),
        "last_played_at": top_scene.get("last_played_at"),
        "studio": studio.get("name"),
        "performers": [p.get("name") for p in performers if p.get("name")],
        "screenshot": (top_scene.get("paths") or {}).get("screenshot"),
    }
