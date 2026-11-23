"""State machines that turn radar readings into events. Pure logic: the caller
passes the time in, so every rule can be unit-tested without a radar.

Event = (kind, meta). Kinds:
  fall_suspected  body top dropped fast to the floor (or stayed on the floor a long time)
  fall            still on the floor after `fall_confirm_s`  -> alert the family
  fall_recovered  got up (or pressed "I'm OK") before the alert
  fall_resolved   got up (or pressed "I'm OK") after the alert
  bathroom_still  in the bathroom with no movement for `bathroom_still_s` -> alert
  bathroom_long   in the bathroom for `bathroom_long_s` -> warning
  bathroom_ok     moved again / came out after one of the two above
  bathroom_visit  came out of the bathroom (value = seconds inside)
  nudge           sat or lay down too long in the daytime -> invite to play a game
"""

from collections import deque

from .config import FLOOR, LYING, SITTING, STANDING, Settings

NORMAL = "NORMAL"
SUSPECTED = "SUSPECTED"  # on the floor after a fall, waiting to confirm
FALLEN = "FALLEN"  # alert sent, waiting for them to get up

Event = tuple[str, dict]


class FallDetector:
    """Per radar.

    A fall is: body top drops >= `fall_drop_cm` within `fall_drop_window_s` and ends
    on the floor (or stays on the floor for `floor_stay_s`, which catches a slow
    slide off a chair), and the person is still on the floor `fall_confirm_s` later.
    Sitting down fast or flopping onto a bed never reaches floor height, so it
    does not count.
    """

    def __init__(self, s: Settings):
        self.s = s
        self.state = NORMAL
        self.since = 0.0
        self.floor_since: float | None = None
        self.history: deque[tuple[float, float]] = deque()  # (t, height)

    def update(self, t: float, height: float | None, posture: str, sensor_fall: bool = False) -> list[Event]:
        if height is not None:
            self.history.append((t, height))
        while self.history and t - self.history[0][0] > self.s.fall_drop_window_s:
            self.history.popleft()

        on_floor = posture == FLOOR or sensor_fall
        if on_floor:
            self.floor_since = self.floor_since if self.floor_since is not None else t
        elif posture in (STANDING, SITTING, LYING):
            self.floor_since = None

        got_up = posture in (STANDING, SITTING) and not sensor_fall
        events: list[Event] = []
        if self.state == NORMAL and on_floor:
            reason, drop = None, 0.0
            if height is not None and self.history:
                drop = max(h for _, h in self.history) - height
            if sensor_fall:
                reason = "sensor"
            elif drop >= self.s.fall_drop_cm:
                reason = "drop"
            elif t - self.floor_since >= self.s.floor_stay_s:
                reason = "on_floor"
            if reason:
                self.state, self.since = SUSPECTED, t
                events.append(("fall_suspected", {"reason": reason, "drop_cm": round(drop)}))
        elif self.state == SUSPECTED:
            if got_up:
                self.state = NORMAL
                events.append(("fall_recovered", {"seconds": round(t - self.since), "by": "radar"}))
            elif t - self.since >= self.s.fall_confirm_s:
                self.state = FALLEN
                events.append(("fall", {"seconds": round(t - self.since)}))
        elif self.state == FALLEN and got_up:
            self.state = NORMAL
            events.append(("fall_resolved", {"seconds": round(t - self.since), "by": "radar"}))
        return events

    def cancel(self, t: float) -> list[Event]:
        """The elder pressed "I'm OK" on the screen."""
        if self.state == NORMAL:
            return []
        kind = "fall_recovered" if self.state == SUSPECTED else "fall_resolved"
        seconds = round(t - self.since)
        self.state = NORMAL
        # Forget the drop and restart the on-floor clock, so it does not fire again at once.
        self.history.clear()
        if self.floor_since is not None:
            self.floor_since = t
        return [(kind, {"seconds": seconds, "by": "elder"})]


class BathroomMonitor:
    """Per bathroom radar: how long inside, and how long without moving."""

    LEAVE_GRACE_S = 5.0  # radar can lose a still person for a moment

    def __init__(self, s: Settings):
        self.s = s
        self.inside = False
        self.entered = 0.0
        self.last_move = 0.0
        self.absent_since: float | None = None
        self.still_alerted = False
        self.long_alerted = False

    def update(self, t: float, presence: bool, moving: bool) -> list[Event]:
        events: list[Event] = []
        if presence:
            self.absent_since = None
            if not self.inside:
                self.inside, self.entered, self.last_move = True, t, t
                self.still_alerted = self.long_alerted = False
            if moving:
                self.last_move = t
                if self.still_alerted:
                    self.still_alerted = False
                    events.append(("bathroom_ok", {"reason": "moving"}))
            if not self.still_alerted and t - self.last_move >= self.s.bathroom_still_s:
                self.still_alerted = True
                events.append(("bathroom_still", {"seconds": round(t - self.last_move)}))
            if not self.long_alerted and t - self.entered >= self.s.bathroom_long_s:
                self.long_alerted = True
                events.append(("bathroom_long", {"seconds": round(t - self.entered)}))
        elif self.inside:
            self.absent_since = self.absent_since if self.absent_since is not None else t
            if t - self.absent_since >= self.LEAVE_GRACE_S:
                self.inside = False
                stay = self.absent_since - self.entered
                if self.still_alerted or self.long_alerted:
                    events.append(("bathroom_ok", {"reason": "left"}))
                events.append(("bathroom_visit", {"seconds": round(stay)}))
        return events


class ActivityMonitor:
    """Whole home: how long the elder has been resting (sitting or lying) without
    standing up. Moving an arm while seated does not count; standing up does."""

    def __init__(self, s: Settings):
        self.s = s
        self.resting_since: float | None = None
        self.posture: str | None = None
        self.last_nudge = float("-inf")

    def update(self, t: float, posture: str, hour: int) -> list[Event]:
        if posture == STANDING:
            self.resting_since, self.posture = None, STANDING
            return []
        if posture not in (SITTING, LYING):
            return []  # unknown, or on the floor (the fall detector handles that)
        if self.resting_since is None:
            self.resting_since = t
        self.posture = posture
        if not self.s.day_start_hour <= hour < self.s.day_end_hour:
            return []
        limit = self.s.lie_limit_s if posture == LYING else self.s.sit_limit_s
        rested = t - self.resting_since
        if rested >= limit and t - self.last_nudge >= self.s.nudge_cooldown_s:
            self.last_nudge = t
            return [("nudge", {"reason": posture, "seconds": round(rested)})]
        return []

    def away(self) -> None:
        """Nobody seen by any radar (went out, or another room without a radar)."""
        self.resting_since, self.posture = None, None

    def active(self, t: float) -> None:
        """Played a game: that counts as getting up."""
        self.resting_since = t if self.resting_since is not None else None
        self.last_nudge = t

    def resting_seconds(self, t: float) -> float:
        return 0.0 if self.resting_since is None else t - self.resting_since
