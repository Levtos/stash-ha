"""Tests for the pure playback-detection helpers in playback_logic.py."""

from __future__ import annotations

import pytest

import sh_const as C
import sh_playback as P


# --------------------------------------------------------- rewrite_url


def test_rewrite_url_swaps_authority_keeps_path():
    base = "https://stash.example.com:8443"
    url = "http://internal-stash:9999/scene/123/screenshot?token=abc"
    rewritten = P.rewrite_url(base, url)
    assert rewritten == "https://stash.example.com:8443/scene/123/screenshot?token=abc"


def test_rewrite_url_handles_relative_path():
    base = "https://stash.example.com:8443"
    assert P.rewrite_url(base, "/scene/1") == "https://stash.example.com:8443/scene/1"
    assert P.rewrite_url(base, "scene/1") == "https://stash.example.com:8443/scene/1"


# --------------------------------------------------------- parse_play_duration


@pytest.mark.parametrize("raw,expected", [
    (12.5, 12.5),
    ("8.3", 8.3),
    (None, 0.0),
    ("garbage", 0.0),
    (0, 0.0),
])
def test_parse_play_duration_normalises(raw, expected):
    assert P.parse_play_duration(raw) == expected


# --------------------------------------------------------- is_streaming


def test_is_streaming_within_grace_window():
    now = 1000.0
    assert P.is_streaming(now - 10.0, now) is True
    # Grace window is STREAM_ACTIVITY_GRACE_SECONDS = 60.
    assert P.is_streaming(now - 59.9, now) is True
    assert P.is_streaming(now - 60.1, now) is False
    assert P.is_streaming(None, now) is False


# --------------------------------------------------------- evaluate_scene_signal


def test_first_observation_fresh_play_is_streaming():
    now = 1000.0
    result = P.evaluate_scene_signal(
        play_duration=42.0,
        prev_signal=None,
        last_played_age_s=5.0,
        now_ts=now,
    )
    assert result["fresh_first_seen"] is True
    assert result["last_activity_ts"] == now
    assert result["streaming"] is True


def test_first_observation_stale_play_is_idle():
    now = 1000.0
    result = P.evaluate_scene_signal(
        play_duration=42.0,
        prev_signal=None,
        last_played_age_s=300.0,  # well past FRESH threshold
        now_ts=now,
    )
    assert result["fresh_first_seen"] is False
    assert result["last_activity_ts"] is None
    assert result["streaming"] is False


def test_play_duration_advance_marks_streaming():
    now = 1000.0
    result = P.evaluate_scene_signal(
        play_duration=50.0,
        prev_signal={"play_duration": 40.0, "last_activity_ts": now - 30},
        last_played_age_s=120.0,
        now_ts=now,
    )
    assert result["delta_advanced"] is True
    assert result["last_activity_ts"] == now
    assert result["streaming"] is True


def test_play_duration_stagnates_keeps_prev_activity_ts():
    now = 1000.0
    result = P.evaluate_scene_signal(
        play_duration=40.0,
        prev_signal={"play_duration": 40.0, "last_activity_ts": now - 30},
        last_played_age_s=120.0,
        now_ts=now,
    )
    assert result["delta_advanced"] is False
    # last_activity_ts is preserved → still streaming within the grace window.
    assert result["last_activity_ts"] == now - 30
    assert result["streaming"] is True


def test_play_duration_stagnates_past_grace_drops_to_idle():
    now = 1000.0
    result = P.evaluate_scene_signal(
        play_duration=40.0,
        prev_signal={"play_duration": 40.0, "last_activity_ts": now - 200},
        last_played_age_s=600.0,
        now_ts=now,
    )
    assert result["streaming"] is False


# --------------------------------------------------------- prune_stale_signals


def test_prune_stale_signals_keeps_seen_and_drops_old():
    now = 1000.0
    signals = {
        "a": {"play_duration": 1.0, "last_activity_ts": now - 30},
        "b": {"play_duration": 2.0, "last_activity_ts": now - 500},  # very stale
        "c": {"play_duration": 3.0, "last_activity_ts": now - 30},
    }
    P.prune_stale_signals(signals, seen_ids={"a"}, now_ts=now)
    # `a` was just seen, keeps state. `b` was not seen and is past 2*grace → drop.
    # `c` was not seen but is still inside 2*grace → keep.
    assert set(signals) == {"a", "c"}


# --------------------------------------------------------- summarise_last_played


def test_summarise_last_played_picks_useful_fields():
    scene = {
        "id": "42",
        "title": "Test",
        "last_played_at": "2026-01-12T09:00:00+00:00",
        "studio": {"name": "Studio A"},
        "performers": [{"name": "X"}, {"name": "Y"}, {"name": ""}],
        "paths": {"screenshot": "https://stash.example.com/screens/42.jpg"},
    }
    out = P.summarise_last_played(scene)
    assert out == {
        "id": "42",
        "title": "Test",
        "last_played_at": "2026-01-12T09:00:00+00:00",
        "studio": "Studio A",
        "performers": ["X", "Y"],
        "screenshot": "https://stash.example.com/screens/42.jpg",
    }


def test_summarise_handles_missing_pieces_gracefully():
    out = P.summarise_last_played({"id": "1", "title": None})
    assert out["studio"] is None
    assert out["performers"] == []
    assert out["screenshot"] is None


# --------------------------------------------------------- current_playing_title
# Regression: the Currently Playing sensor state must NOT combine multiple active
# scene titles into "A | B" (that would create a bogus A|B Title Classifier
# catalog entry). It returns the most-recently-active single title.


def test_current_playing_title_single_scene():
    assert P.current_playing_title([{"id": "1", "title": "Title A"}]) == "Title A"


def test_current_playing_title_two_scenes_no_join():
    # scenes are last_played_at DESC → scenes[0] ("Title A") is most recent.
    scenes = [
        {"id": "1", "title": "Title A"},
        {"id": "2", "title": "Title B"},
    ]
    state = P.current_playing_title(scenes)
    assert " | " not in state          # never a combined A|B state
    assert state == "Title A"          # exactly the most-recent scene's title


def test_current_playing_title_empty_or_untitled_is_none():
    assert P.current_playing_title([]) is None
    assert P.current_playing_title(None) is None
    assert P.current_playing_title([{"id": "1", "title": None}]) is None


# --------------------------------------------------------- assign_slots
# Sticky scene_id -> slot mapping for the fixed slot title sensors.


def _scene(sid, title=None):
    return {"id": sid, "title": title or f"T{sid}"}


def test_assign_slots_single_scene_takes_slot_1():
    assert P.assign_slots([_scene("a")], {}, 4) == {"a": 1}


def test_assign_slots_two_scenes_separate_slots():
    scenes = [_scene("a"), _scene("b")]
    assert P.assign_slots(scenes, {}, 4) == {"a": 1, "b": 2}


def test_assign_slots_reorder_keeps_sticky_slots():
    prev = {"a": 1, "b": 2}
    # scenes come back in the opposite order (last_played_at re-sorted).
    reordered = [_scene("b"), _scene("a")]
    assert P.assign_slots(reordered, prev, 4) == {"a": 1, "b": 2}


def test_assign_slots_stopped_scene_frees_its_slot():
    prev = {"a": 1, "b": 2}
    # 'a' stopped; 'b' keeps slot 2 (not shifted down to slot 1).
    assert P.assign_slots([_scene("b")], prev, 4) == {"b": 2}


def test_assign_slots_new_scene_takes_lowest_free_slot():
    prev = {"b": 2}  # slot 1 is free
    result = P.assign_slots([_scene("b"), _scene("c")], prev, 4)
    assert result == {"b": 2, "c": 1}


def test_assign_slots_overflow_only_fills_available_slots():
    scenes = [_scene(x) for x in ("a", "b", "c", "d", "e")]  # 5 > 4
    result = P.assign_slots(scenes, {}, 4)
    assert len(result) == 4
    assert set(result.values()) == {1, 2, 3, 4}
    # exactly one scene got no slot (the 5th in order)
    assert sum(1 for s in scenes if str(s["id"]) not in result) == 1


def test_assign_slots_skips_scenes_without_id():
    scenes = [{"title": "no id"}, _scene("a")]
    assert P.assign_slots(scenes, {}, 4) == {"a": 1}


def test_assign_slots_does_not_mutate_prev_mapping():
    prev = {"a": 1}
    P.assign_slots([_scene("a"), _scene("b")], prev, 4)
    assert prev == {"a": 1}


# --------------------------------------------------------- slots_view


def test_slots_view_empty_slots_are_none_not_idle():
    view = P.slots_view([_scene("a")], {"a": 1}, 4)
    assert view[1]["title"] == "Ta"
    # Empty slots must be None so the sensor reports no title (no "idle" string).
    assert view[2] is None
    assert view[3] is None
    assert view[4] is None


def test_slots_view_two_occupied_slots():
    scenes = [_scene("a", "Alpha"), _scene("b", "Beta")]
    view = P.slots_view(scenes, {"a": 1, "b": 2}, 4)
    assert view[1]["title"] == "Alpha"
    assert view[2]["title"] == "Beta"
    assert view[3] is None and view[4] is None


def test_slots_view_stale_mapping_entry_resolves_to_none():
    # mapping points at a scene that is no longer active -> slot is None.
    view = P.slots_view([_scene("a")], {"a": 1, "gone": 2}, 4)
    assert view[1]["title"] == "Ta"
    assert view[2] is None


# --------------------------------------------------------- per-slot display text

EMPTY = C.SLOT_EMPTY_TITLE  # "Kein Stream aktiv"


def _full_scene():
    return {
        "id": "1",
        "title": "Overcharged Breeding",
        "studio": {"name": "Next Door Raw"},
        "performers": [{"name": "A"}, {"name": "B"}, {"name": ""}],
        "tags": [{"name": "T1"}, {"name": "T2"}],
        "paths": {"screenshot": "http://x/1.jpg"},
    }


def test_slot_title_active_and_empty():
    assert P.slot_title(_full_scene(), EMPTY) == "Overcharged Breeding"
    assert P.slot_title(None, EMPTY) == EMPTY
    # occupied but title-less falls back to the placeholder (never None)
    assert P.slot_title({"id": "1", "title": None}, EMPTY) == EMPTY


def test_slot_studio_active_empty_unknown():
    assert P.slot_studio(_full_scene(), EMPTY) == "Next Door Raw"
    assert P.slot_studio(None, EMPTY) == EMPTY
    assert P.slot_studio({"id": "1"}, EMPTY) is None  # active but unknown


def test_slot_performers_active_empty_none():
    assert P.slot_performers(_full_scene(), EMPTY) == "A, B"
    assert P.slot_performers(None, EMPTY) == EMPTY
    assert P.slot_performers({"id": "1"}, EMPTY) is None


def test_slot_tags_active_empty_none():
    assert P.slot_tags(_full_scene(), EMPTY) == "T1, T2"
    assert P.slot_tags(None, EMPTY) == EMPTY
    assert P.slot_tags({"id": "1"}, EMPTY) is None


def test_slot_display_text_variants():
    assert P.slot_display_text(_full_scene(), EMPTY) == "Overcharged Breeding — Next Door Raw"
    # title only (no studio)
    assert P.slot_display_text({"id": "1", "title": "Solo"}, EMPTY) == "Solo"
    # empty / title-less -> placeholder
    assert P.slot_display_text(None, EMPTY) == EMPTY
    assert P.slot_display_text({"id": "1", "title": None}, EMPTY) == EMPTY


def test_slot_cover_url_active_empty_missing():
    assert P.slot_cover_url(_full_scene()) == "http://x/1.jpg"
    assert P.slot_cover_url(None) is None
    assert P.slot_cover_url({"id": "1"}) is None  # no paths/screenshot
