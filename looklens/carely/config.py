"""Every threshold and setting lives here so it can be explained (and tuned) in one place.

Secrets and per-home settings come from `.env` (see `.env.example`).
Set CARELY_DEMO=1 to shrink all the waiting times so a demo fits in a few minutes.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


# Postures the radar can tell apart from "how high is the top of the body".
STANDING = "standing"
SITTING = "sitting"
LYING = "lying"  # lying on a bed / sofa (body top is still well above the floor)
FLOOR = "floor"  # body top is near the floor -> fallen, or lying on the floor
UNKNOWN = "unknown"

POSTURE_TH = {
    STANDING: "ยืน / เดิน",
    SITTING: "นั่ง",
    LYING: "นอน",
    FLOOR: "อยู่บนพื้น",
    UNKNOWN: "ไม่ทราบท่า",
}


@dataclass
class Device:
    """One radar unit. Mount it on the ceiling pointing straight down."""
    id: str
    room: str  # bathroom | living | bedroom | other
    name: str  # Thai name shown to the family
    ceiling_cm: float = 260.0  # sensor height above the floor


DEFAULT_DEVICES = {
    "bathroom": Device("bathroom", "bathroom", "ห้องน้ำ", 240.0),
    "living": Device("living", "living", "ห้องนั่งเล่น", 260.0),
    "bedroom": Device("bedroom", "bedroom", "ห้องนอน", 260.0),
}


@dataclass
class Settings:
    demo: bool = False

    # --- Posture from body-top height above the floor (cm) ---
    # The radar reports the distance to the nearest body part (head / shoulders),
    # so height = ceiling - distance. Calibrate these on site.
    standing_min_cm: float = 130.0  # head of a standing elder is ~140-160
    sitting_min_cm: float = 85.0  # sitting on a chair / toilet ~95-125
    floor_max_cm: float = 45.0  # lying on a bed ~55-80, lying on the floor < 45
    # Median of the last N readings, so one noisy reading cannot flip the posture.
    smoothing: int = 3

    # Moving energy (0-100, LD2410C scale) at or above this counts as "moving".
    moving_energy_min: int = 20

    # --- Fall detection ---
    # Body top drops at least this much within `fall_drop_window_s` and ends on the floor ...
    fall_drop_cm: float = 60.0
    fall_drop_window_s: float = 2.5
    # ... OR stays on the floor this long without a fast drop (slow slide off a chair).
    floor_stay_s: float = 60.0
    # Still on the floor this long after that -> alert the family.
    # Long enough to let someone get up by themselves or press "I'm OK".
    fall_confirm_s: float = 20.0
    # Nobody pressed "on my way" in LINE -> send the alert again.
    realert_s: float = 300.0

    # --- Bathroom ---
    # Inside and not moving at all this long -> may have fainted / fallen out of view.
    bathroom_still_s: float = 300.0
    # Inside this long -> gentle warning to the family.
    bathroom_long_s: float = 1800.0

    # --- Sitting / lying too long ---
    sit_limit_s: float = 3600.0
    lie_limit_s: float = 7200.0  # daytime only
    # Only nudge during the day (do not wake anyone up at night).
    day_start_hour: int = 7
    day_end_hour: int = 20
    # After a nudge, wait this long before nudging again.
    nudge_cooldown_s: float = 1800.0

    # A device that sends nothing for this long is shown as offline.
    device_timeout_s: float = 15.0

    devices: dict[str, Device] = field(default_factory=lambda: dict(DEFAULT_DEVICES))

    # --- Elder profile (used by the AI game picker and the voice) ---
    elder_name: str = "คุณยาย"
    elder_phone: str = ""
    elder_notes: str = ""  # e.g. "ปวดเข่า เดินช้า ชอบเพลงลูกทุ่ง"

    # --- Integrations ---
    line_token: str = ""
    line_secret: str = ""
    # Broadcast = send to every friend of the OA. Needs only the token: no webhook,
    # no public URL, no "ลงทะเบียน". On by default when there is no channel secret.
    line_broadcast: bool = False
    family_code: str = ""  # family types "ลงทะเบียน <code>" in LINE to receive alerts
    radar_token: str = ""  # devices must send this in the X-Radar-Token header
    admin_key: str = ""  # if set, the web pages need ?key=... once
    ai_model: str = "claude-opus-5-5"
    db_path: Path = ROOT / "data" / "carely.db"

    def device(self, device_id: str) -> Device:
        if device_id not in self.devices:
            self.devices[device_id] = Device(device_id, "other", device_id)
        return self.devices[device_id]


def demo_overrides(s: Settings) -> Settings:
    """Short waits so every feature can be shown live in a few minutes."""
    s.demo = True
    s.floor_stay_s = 15
    s.fall_confirm_s = 8
    s.realert_s = 60
    s.bathroom_still_s = 25
    s.bathroom_long_s = 90
    s.sit_limit_s = 40
    s.lie_limit_s = 60
    s.nudge_cooldown_s = 60
    s.day_start_hour, s.day_end_hour = 0, 24
    return s


def load_settings() -> Settings:
    s = Settings(
        elder_name=_env("ELDER_NAME", "คุณยาย"),
        elder_phone=_env("ELDER_PHONE"),
        elder_notes=_env("ELDER_NOTES"),
        line_token=_env("LINE_CHANNEL_ACCESS_TOKEN"),
        line_secret=_env("LINE_CHANNEL_SECRET"),
        line_broadcast=_env("LINE_BROADCAST", "0" if _env("LINE_CHANNEL_SECRET") else "1") == "1",
        family_code=_env("FAMILY_CODE"),
        radar_token=_env("RADAR_TOKEN"),
        admin_key=_env("CARELY_ADMIN_KEY"),
        ai_model=_env("CARELY_AI_MODEL", "claude-opus-5-5"),
    )
    if _env("CARELY_DB"):
        s.db_path = Path(_env("CARELY_DB"))
    if _env("CARELY_DEMO") in ("1", "true", "yes"):
        demo_overrides(s)
    return s
