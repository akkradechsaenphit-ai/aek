"""Radar readings: the JSON a device sends, turning distance into posture,
and a parser for the HLK-LD2410C serial protocol (for a radar plugged into USB).

The radar is mounted on the ceiling looking down. It reports how far away the
nearest part of the person is, so

    body-top height above floor = ceiling height - distance

Standing puts the head close to the sensor, sitting further, lying on a bed
further still, and lying on the floor furthest. That is enough to tell the
four postures apart without any camera.
"""

import statistics
from collections import deque
from dataclasses import dataclass

from .config import FLOOR, LYING, SITTING, STANDING, UNKNOWN, Device, Settings


@dataclass
class Reading:
    device: str
    t: float
    presence: bool
    moving_energy: int = 0  # 0-100
    still_energy: int = 0  # 0-100
    distance_cm: float | None = None  # sensor -> nearest body part
    height_cm: float | None = None  # sent directly by devices that know it
    posture: str | None = None  # sent directly by devices that know it (e.g. a camera)
    fall: bool = False  # the sensor itself flagged a fall (e.g. Seeed MR60FDA2)
    door_open: bool | None = None  # bathroom door switch (MC-38), if fitted

    @classmethod
    def from_payload(cls, p: dict, now: float) -> "Reading":
        def num(key):
            v = p.get(key)
            return None if v is None else float(v)

        return cls(
            device=str(p.get("device", "unknown"))[:40],
            t=now,  # the server clock is the only clock we trust
            presence=bool(p.get("presence", False)),
            moving_energy=int(p.get("moving_energy", 0) or 0),
            still_energy=int(p.get("still_energy", 0) or 0),
            distance_cm=num("distance_cm"),
            height_cm=num("height_cm"),
            posture=p.get("posture") if p.get("posture") in (STANDING, SITTING, LYING, FLOOR) else None,
            fall=bool(p.get("fall", False)),
            door_open=p.get("door_open") if isinstance(p.get("door_open"), bool) else None,
        )


class PostureEstimator:
    """Per-device: smooths the height and maps it to a posture."""

    def __init__(self, s: Settings, device: Device):
        self.s = s
        self.device = device
        self.heights: deque[float] = deque(maxlen=max(1, s.smoothing))

    def update(self, r: Reading) -> tuple[float | None, str]:
        if not r.presence:
            self.heights.clear()
            return None, UNKNOWN
        h = r.height_cm
        if h is None and r.distance_cm is not None:
            h = self.device.ceiling_cm - r.distance_cm
        if h is not None:
            self.heights.append(max(0.0, h))
        height = statistics.median(self.heights) if self.heights else None
        if r.posture:
            return height, r.posture
        return height, classify(height, self.s)


def classify(height: float | None, s: Settings) -> str:
    if height is None:
        return UNKNOWN
    if height >= s.standing_min_cm:
        return STANDING
    if height >= s.sitting_min_cm:
        return SITTING
    if height > s.floor_max_cm:
        return LYING
    return FLOOR


# --- HLK-LD2410C serial protocol (256000 baud) -----------------------------
# Data frame:  F4 F3 F2 F1 | len(2, LE) | type(0x01 engineering / 0x02 basic) 0xAA
#              target_state(1) moving_dist(2) moving_energy(1) still_dist(2)
#              still_energy(1) detect_dist(2) [engineering data] 0x55 0x00 | F8 F7 F6 F5
HEAD = bytes([0xF4, 0xF3, 0xF2, 0xF1])
TAIL = bytes([0xF8, 0xF7, 0xF6, 0xF5])


class LD2410Parser:
    """Feed raw serial bytes, get back target reports as dicts."""

    def __init__(self):
        self.buf = bytearray()

    def feed(self, data: bytes) -> list[dict]:
        self.buf += data
        out = []
        while True:
            start = self.buf.find(HEAD)
            if start < 0:
                del self.buf[:-3]  # keep a possible partial header
                return out
            del self.buf[:start]
            if len(self.buf) < 6:
                return out
            length = int.from_bytes(self.buf[4:6], "little")
            end = 6 + length + 4
            if len(self.buf) < end:
                return out
            frame = bytes(self.buf[:end])
            del self.buf[:end]
            if frame[-4:] != TAIL:
                continue
            report = parse_payload(frame[6:6 + length])
            if report:
                out.append(report)

    def __len__(self):
        return len(self.buf)


def parse_payload(d: bytes) -> dict | None:
    if len(d) < 13 or d[0] not in (0x01, 0x02) or d[1] != 0xAA:
        return None
    state = d[2]  # 0 none, 1 moving, 2 still, 3 moving + still
    moving_cm = int.from_bytes(d[3:5], "little")
    moving_energy = d[5]
    still_cm = int.from_bytes(d[6:8], "little")
    still_energy = d[8]
    present = state != 0
    is_moving = state in (1, 3)
    # When moving, the moving target is the person's current position;
    # otherwise use the still target.
    dist = moving_cm if is_moving and moving_cm else still_cm
    return {
        "presence": present,
        "moving_energy": moving_energy if is_moving else 0,
        "still_energy": still_energy if state in (2, 3) else 0,
        "distance_cm": dist if present else None,
    }
