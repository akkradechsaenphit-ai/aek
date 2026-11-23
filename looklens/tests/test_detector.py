from carely.config import FLOOR, LYING, SITTING, STANDING, Settings
from carely.detector import FALLEN, NORMAL, SUSPECTED, ActivityMonitor, BathroomMonitor, FallDetector
from carely.radar import classify


def run(det, frames):
    """frames: list of (t, height, posture). Returns all event kinds."""
    out = []
    for t, h, p in frames:
        out += [k for k, _ in det.update(t, h, p)]
    return out


def test_classify_heights():
    s = Settings()
    assert classify(150, s) == STANDING
    assert classify(110, s) == SITTING
    assert classify(65, s) == LYING
    assert classify(25, s) == FLOOR


def test_fast_drop_to_floor_then_alert():
    s = Settings()
    d = FallDetector(s)
    kinds = run(d, [(0, 150, STANDING), (1, 150, STANDING), (2, 25, FLOOR)])
    assert kinds == ["fall_suspected"] and d.state == SUSPECTED
    kinds = run(d, [(t, 25, FLOOR) for t in range(3, 3 + int(s.fall_confirm_s) + 1)])
    assert kinds == ["fall"] and d.state == FALLEN
    assert run(d, [(40, 150, STANDING)]) == ["fall_resolved"] and d.state == NORMAL


def test_get_up_before_confirm_is_not_an_alert():
    d = FallDetector(Settings())
    run(d, [(0, 150, STANDING), (1, 25, FLOOR)])
    assert run(d, [(5, 110, SITTING)]) == ["fall_recovered"]


def test_sitting_down_fast_or_lying_on_bed_is_not_a_fall():
    d = FallDetector(Settings())
    assert run(d, [(0, 150, STANDING), (1, 105, SITTING), (60, 105, SITTING)]) == []
    assert run(d, [(61, 150, STANDING), (62, 65, LYING), (200, 65, LYING)]) == []
    assert d.state == NORMAL


def test_slow_slide_to_floor_is_caught():
    s = Settings()
    d = FallDetector(s)
    frames = [(t, 110 - t * 10, SITTING if 110 - t * 10 > 85 else LYING) for t in range(0, 7)]
    frames += [(t, 30, FLOOR) for t in range(7, 7 + int(s.floor_stay_s) + 1)]
    assert run(d, frames) == ["fall_suspected"]


def test_elder_pressing_ok_cancels_and_does_not_refire_at_once():
    s = Settings()
    d = FallDetector(s)
    run(d, [(0, 150, STANDING), (1, 25, FLOOR)])
    assert [k for k, _ in d.cancel(3)] == ["fall_recovered"]
    assert run(d, [(4, 25, FLOOR), (5, 25, FLOOR)]) == []


def test_sensor_fall_flag():
    d = FallDetector(Settings())
    assert [k for k, _ in d.update(0, None, "unknown", sensor_fall=True)] == ["fall_suspected"]


def test_bathroom_still_and_leave():
    s = Settings()
    b = BathroomMonitor(s)
    kinds = []
    for t in range(0, int(s.bathroom_still_s) + 2):
        kinds += [k for k, _ in b.update(t, True, moving=t < 1)]
    assert "bathroom_still" in kinds
    kinds = [k for k, _ in b.update(400, True, moving=True)]
    assert kinds == ["bathroom_ok"]
    b.update(401, False, False)
    kinds = [k for k, _ in b.update(401 + b.LEAVE_GRACE_S, False, False)]
    assert kinds == ["bathroom_visit"]


def test_bathroom_brief_dropout_is_not_leaving():
    b = BathroomMonitor(Settings())
    b.update(0, True, True)
    b.update(10, False, False)
    b.update(12, True, False)
    assert b.inside


def test_nudge_after_sitting_long_in_daytime_only():
    s = Settings()
    a = ActivityMonitor(s)
    assert a.update(0, SITTING, hour=10) == []
    assert [k for k, _ in a.update(s.sit_limit_s, SITTING, hour=10)] == ["nudge"]
    # cooldown
    assert a.update(s.sit_limit_s + 60, SITTING, hour=10) == []
    night = ActivityMonitor(s)
    night.update(0, LYING, hour=23)
    assert night.update(s.lie_limit_s * 2, LYING, hour=23) == []


def test_standing_up_resets_the_timer():
    s = Settings()
    a = ActivityMonitor(s)
    a.update(0, SITTING, hour=10)
    a.update(s.sit_limit_s - 10, STANDING, hour=10)
    a.update(s.sit_limit_s - 5, SITTING, hour=10)
    assert a.update(s.sit_limit_s + 5, SITTING, hour=10) == []
