"""The brain of the home: receives radar readings, runs the detectors, and
turns events into actions (LINE alerts, voice prompts, games on the elder screen).
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from urllib.parse import parse_qs

from . import ai, games
from . import line as L
from .config import POSTURE_TH, UNKNOWN, Device, Settings
from .detector import NORMAL, ActivityMonitor, BathroomMonitor, FallDetector
from .radar import PostureEstimator, Reading
from .store import Store

log = logging.getLogger("carely.hub")

# kind -> (level, title, detail template)
ALERTS = {
    "fall": ("urgent", "ตรวจพบการล้ม", "อยู่บนพื้นและยังไม่ลุกขึ้นมา {seconds} วินาที"),
    "bathroom_still": ("urgent", "อยู่ในห้องน้ำนิ่งผิดปกติ", "ไม่มีการเคลื่อนไหวเลย {minutes} นาที อาจหมดสติหรือล้ม"),
    "bathroom_long": ("warning", "อยู่ในห้องน้ำนานผิดปกติ", "อยู่ในห้องน้ำมาแล้ว {minutes} นาที"),
    "sos": ("urgent", "กดปุ่มขอความช่วยเหลือ", "กดปุ่มขอความช่วยเหลือจากหน้าจอที่บ้าน"),
}
MAX_SENDS = 5  # stop re-sending an unanswered alert after this many


@dataclass
class DeviceState:
    device: Device
    est: PostureEstimator
    fall: FallDetector
    bath: BathroomMonitor | None
    last: Reading | None = None
    last_seen: float = 0.0
    presence: bool = False
    height: float | None = None
    posture: str = UNKNOWN
    moving: bool = False
    history: list = field(default_factory=list)  # recent (t, height) for the dashboard chart
    logged_posture: str | None = None


def start_of_today() -> float:
    lt = time.localtime()
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))


class Hub:
    def __init__(self, s: Settings, store: Store, line: L.LineClient):
        self.s = s
        self.store = store
        self.line = line
        self.devices: dict[str, DeviceState] = {}
        self.activity = ActivityMonitor(s)
        self.location: str | None = None
        self.subscribers: set[asyncio.Queue] = set()
        self.current_play: dict | None = None
        self.last_message: dict | None = None
        self.fall_check: dict | None = None  # shown on the elder screen while a fall is suspected
        for d in s.devices.values():
            self._dev(d.id)

    # --- plumbing ----------------------------------------------------------

    def _dev(self, device_id: str) -> DeviceState:
        if device_id not in self.devices:
            d = self.s.device(device_id)
            self.devices[device_id] = DeviceState(
                d, PostureEstimator(self.s, d), FallDetector(self.s),
                BathroomMonitor(self.s) if d.room == "bathroom" else None)
        return self.devices[device_id]

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self.subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self.subscribers.discard(q)

    def broadcast(self, kind: str, **data) -> None:
        msg = {"type": kind, "ts": time.time(), **data}
        for q in list(self.subscribers):
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                pass

    def family_ids(self) -> list[str]:
        return [f["user_id"] for f in self.store.family()]

    def room_name(self, device_id: str | None) -> str:
        return self.s.device(device_id).name if device_id else "หน้าจอที่บ้าน"

    # --- radar -------------------------------------------------------------

    async def ingest(self, r: Reading) -> None:
        ds = self._dev(r.device)
        ds.last, ds.last_seen = r, r.t
        await self._process(ds, r)

    async def _process(self, ds: DeviceState, r: Reading) -> None:
        height, posture = ds.est.update(r)
        was_present = ds.presence
        ds.presence, ds.height, ds.posture = r.presence, height, posture
        ds.moving = r.presence and r.moving_energy >= self.s.moving_energy_min
        ds.history.append((round(r.t, 1), None if height is None else round(height)))
        del ds.history[:-90]

        # Where is the elder? The radar that most recently started seeing someone.
        if r.presence and not was_present:
            self.location = ds.device.id
        elif not r.presence and self.location == ds.device.id:
            others = [d for d in self.devices.values() if d.presence]
            self.location = others[0].device.id if others else None

        events = ds.fall.update(r.t, height, posture, r.fall)
        if ds.bath:
            events += ds.bath.update(r.t, r.presence, ds.moving)
        if self.location is None:
            self.activity.away()
        elif self.location == ds.device.id:
            if ds.device.room == "bathroom":
                self.activity.away()  # sitting on the toilet is not "sitting too long"
            else:
                events += self.activity.update(r.t, posture, time.localtime(r.t).tm_hour)

        if posture != UNKNOWN and ds.logged_posture != posture:
            ds.logged_posture = posture
            self.store.add_event("posture", ds.device.id, ds.device.name, height, {"posture": posture})
        for kind, meta in events:
            await self._handle(ds, kind, meta)

    async def _handle(self, ds: DeviceState, kind: str, meta: dict) -> None:
        dev = ds.device
        self.store.add_event(kind, dev.id, dev.name, meta.get("seconds"), meta)
        log.info("%s %s %s", dev.id, kind, meta)
        name = self.s.elder_name
        if kind == "fall_suspected":
            self.fall_check = {"device": dev.id, "room": dev.name, "ts": time.time()}
            self.broadcast("fall_check", room=dev.name,
                           say=f"{name}คะ เป็นอะไรไหมคะ ถ้าไม่เป็นไร แตะปุ่มสีเขียวบนจอนะคะ")
        elif kind == "fall":
            await self.raise_alert("fall", dev.id, seconds=meta["seconds"])
        elif kind == "fall_recovered":
            self.fall_check = None
            self.broadcast("fall_clear", say="ดีใจที่ไม่เป็นอะไรค่ะ ค่อยๆ ลุกนะคะ")
        elif kind == "fall_resolved":
            self.fall_check = None
            how = f"{name}กดปุ่ม \"ฉันไม่เป็นไร\" ที่หน้าจอ" if meta.get("by") == "elder" else "เรดาร์เห็นว่าลุกขึ้นมาได้แล้ว"
            await self.resolve_alerts(dev.id, ("fall",), f"✅ {name}ลุกขึ้นได้แล้วค่ะ ({how})")
            self.broadcast("fall_clear", say="ดีใจที่ลุกขึ้นได้แล้วค่ะ")
        elif kind == "bathroom_still":
            if ds.fall.state == NORMAL:  # if a fall is already being handled, one alert is enough
                await self.raise_alert("bathroom_still", dev.id, minutes=max(1, round(meta["seconds"] / 60)))
        elif kind == "bathroom_long":
            await self.raise_alert("bathroom_long", dev.id, minutes=max(1, round(meta["seconds"] / 60)))
        elif kind == "bathroom_ok":
            msg = "ขยับตัวแล้ว" if meta["reason"] == "moving" else "ออกจากห้องน้ำแล้ว"
            await self.resolve_alerts(dev.id, ("bathroom_still", "bathroom_long"), f"✅ {name}{msg}ค่ะ")
        elif kind == "nudge":
            if not self.store.active_alerts():
                asyncio.create_task(self.offer_game(trigger=meta["reason"], minutes=round(meta["seconds"] / 60)))

    # --- alerts ------------------------------------------------------------

    async def raise_alert(self, kind: str, device_id: str | None, **fmt) -> dict | None:
        for a in self.store.active_alerts():
            if a["kind"] == kind and a["device"] == device_id:
                return None  # already alerting about this
        level, title, detail = ALERTS[kind]
        a = self.store.open_alert(kind, level, device_id, self.room_name(device_id), title, detail.format(**fmt))
        self.store.add_event("alert_sent", device_id, a["room"], None, {"alert": a["id"], "kind": kind})
        await self.line.push(self.family_ids(), [L.alert_card(a, self.s.elder_name, self.s.elder_phone, ack=not self.line.broadcast)])
        self.broadcast("alert", alert=a, say="ระบบแจ้งลูกหลานแล้วนะคะ อยู่นิ่งๆ ก่อน เดี๋ยวมีคนมาช่วยค่ะ")
        return a

    async def ack(self, alert_id: int, by: str) -> dict | None:
        a = self.store.alert(alert_id)
        if not a or a["status"] != "open":
            return a
        a = self.store.ack_alert(alert_id, by)
        self.store.add_event("alert_ack", a["device"], a["room"], None, {"alert": alert_id, "by": by})
        await self.line.push(self.family_ids(), [L.text(f"👍 {by} รับทราบแล้ว กำลังไปดู{self.s.elder_name}ค่ะ")])
        self.broadcast("alert_ack", alert=a, say=f"{by}รับทราบแล้ว กำลังมาหานะคะ")
        return a

    async def resolve_alerts(self, device_id: str | None, kinds: tuple, message: str) -> None:
        resolved = False
        for a in self.store.active_alerts():
            if a["kind"] in kinds and a["device"] == device_id:
                self.store.resolve_alert(a["id"])
                resolved = True
        if resolved:
            await self.line.push(self.family_ids(), [L.text(message)])
            self.broadcast("alert_resolved")

    async def elder_ok(self) -> None:
        """Elder tapped "I'm OK": cancels a suspected/confirmed fall and an SOS."""
        now = time.time()
        for ds in self.devices.values():
            for kind, meta in ds.fall.cancel(now):
                await self._handle(ds, kind, meta)
        await self.resolve_alerts(None, ("sos",), f"✅ {self.s.elder_name}กดปุ่ม \"ฉันไม่เป็นไร\" แล้วค่ะ")
        self.fall_check = None
        self.broadcast("fall_clear")

    async def sos(self) -> dict | None:
        return await self.raise_alert("sos", None)

    async def tick(self) -> None:
        """Called every second: keeps timers running even if a radar goes quiet,
        and re-sends alerts nobody has answered."""
        now = time.time()
        for ds in self.devices.values():
            if ds.last is None or now - ds.last_seen < 1.5:
                continue
            if now - ds.last_seen < self.s.device_timeout_s:
                await self._process(ds, Reading(**{**ds.last.__dict__, "t": now}))
            else:  # offline: only keep the fall clock running
                for kind, meta in ds.fall.update(now, None, UNKNOWN):
                    await self._handle(ds, kind, meta)
                if ds.presence:
                    ds.presence, ds.posture, ds.height = False, UNKNOWN, None
                    if self.location == ds.device.id:
                        self.location = None
        for a in self.store.active_alerts():
            if a["status"] == "open" and now - a["last_sent"] >= self.s.realert_s and a["sends"] < MAX_SENDS:
                self.store.mark_resent(a["id"])
                a["sends"] += 1
                card = L.alert_card({**a, "title": f"{a['title']} (แจ้งซ้ำครั้งที่ {a['sends']})"},
                                    self.s.elder_name, self.s.elder_phone, ack=not self.line.broadcast)
                await self.line.push(self.family_ids(), [card])
        p = self.current_play
        if p and p["status"] == "offered" and now - p["ts"] > 180:
            await self.game_update(p["id"], "skipped")

    # --- games -------------------------------------------------------------

    async def offer_game(self, trigger: str = "elder_asked", minutes: int = 0, game_id: str | None = None,
                         source: str | None = None, sent_by: str | None = None) -> dict:
        if self.current_play and self.current_play["status"] == "playing":
            return {"error": "busy", "play": self.current_play}
        name = self.s.elder_name
        if game_id:
            g = games.BY_ID[game_id]
            if sent_by:
                say = f"{name}คะ {sent_by}ส่งเกม{g['title']}มาให้เล่นค่ะ มาเล่นกันนะคะ"
            else:
                say = f"{name}คะ มาเล่นเกม{g['title']}กันนะคะ"
            pick = {"game_id": game_id, "say": say, "reason": "", "by": source or "family"}
        else:
            ctx = {
                "elder_name": name, "notes": self.s.elder_notes, "trigger": trigger, "minutes": minutes,
                "hour": time.localtime().tm_hour,
                "played_today": [{"game_id": p["game_id"], "status": p["status"]} for p in self.store.plays_since(start_of_today())],
            }
            pick = await asyncio.to_thread(ai.pick, ctx, self.s.ai_model)
        if self.current_play and self.current_play["status"] == "offered":
            self.store.update_play(self.current_play["id"], "skipped")
        src = source or pick["by"]
        play_id = self.store.add_play(pick["game_id"], src, sent_by)
        self.current_play = {"id": play_id, "ts": time.time(), "status": "offered", "trigger": trigger,
                             "minutes": minutes, "source": src, "sent_by": sent_by, **pick}
        self.store.add_event("game_offer", None, None, None,
                             {"game": pick["game_id"], "by": src, "sent_by": sent_by, "trigger": trigger, "reason": pick["reason"]})
        self.broadcast("game_offer", play=self.current_play, game=games.BY_ID[pick["game_id"]], say=pick["say"])
        return self.current_play

    async def game_update(self, play_id: int, status: str, score: float | None = None) -> None:
        p = self.store.play(play_id)
        if not p:
            return
        self.store.update_play(play_id, status, score)
        g = games.BY_ID[p["game_id"]]
        now = time.time()
        if status in ("playing", "done"):
            self.activity.active(now)
        if self.current_play and self.current_play["id"] == play_id:
            self.current_play["status"] = status
            if status in ("done", "skipped"):
                self.current_play = None
        if status in ("done", "skipped"):
            self.store.add_event(f"game_{status}", None, None, score, {"game": g["id"], "source": p["source"]})
            self.broadcast("game_end", status=status)
        # Tell the family only about games they sent (keeps within the LINE free message quota).
        if p["source"] == "family" and status in ("done", "skipped"):
            name = self.s.elder_name
            if status == "done":
                extra = ""
                if score is not None:
                    extra = f" ทำท่าได้ {score:g}% ของที่ตั้งไว้"
                msg = f"🎉 {name}เล่นเกม{g['title']}ที่{p['sent_by'] or 'คุณ'}ส่งมาเสร็จแล้ว{extra} 👏"
            else:
                msg = f"🙂 {name}ยังไม่สะดวกเล่นเกม{g['title']}ตอนนี้ ลองส่งใหม่ภายหลังนะคะ"
            await self.line.push(self.family_ids(), [L.text(msg)])

    async def family_message(self, text: str, sender: str) -> None:
        self.last_message = {"text": text[:300], "sender": sender, "ts": time.time()}
        self.store.add_event("family_message", None, None, None, self.last_message)
        self.broadcast("family_message", **self.last_message,
                       say=f"ข้อความจาก{sender}ค่ะ {text[:300]}")

    # --- LINE webhook ------------------------------------------------------

    async def handle_line(self, ev: dict) -> None:
        user = (ev.get("source") or {}).get("userId")
        token = ev.get("replyToken")
        if not user or not token:
            return

        async def reply(*msgs):
            await self.line.reply(token, list(msgs))

        name = self.store.family_name(user)
        if ev["type"] == "follow":
            await reply(L.text(f"สวัสดีค่ะ ยินดีต้อนรับสู่ Carely 🌷\nพิมพ์ \"ลงทะเบียน\" ตามด้วยรหัสครอบครัว "
                               f"เพื่อรับแจ้งเตือนเกี่ยวกับ{self.s.elder_name}ค่ะ"))
            return
        if ev["type"] == "postback":
            if not name:
                await reply(L.text("กรุณาลงทะเบียนก่อนนะคะ: พิมพ์ \"ลงทะเบียน <รหัสครอบครัว>\""))
                return
            q = {k: v[0] for k, v in parse_qs(ev["postback"]["data"]).items()}
            if q.get("action") == "ack" and q.get("alert", "").isdigit():
                a = await self.ack(int(q["alert"]), name)
                if a and a["acked_by"] and a["acked_by"] != name:
                    await reply(L.text(f"{a['acked_by']} รับทราบไปแล้วค่ะ"))
                else:
                    await reply(L.text(f"รับทราบค่ะ ระบบบอก{self.s.elder_name}แล้วว่าคุณกำลังไป 🙏"))
            elif q.get("action") == "play" and q.get("game") in games.BY_ID:
                r = await self.offer_game(game_id=q["game"], source="family", sent_by=name)
                if r.get("error") == "busy":
                    await reply(L.text(f"{self.s.elder_name}กำลังเล่นเกมอื่นอยู่ค่ะ ลองส่งใหม่อีกสักครู่นะคะ"))
                else:
                    await reply(L.text(f"ส่งเกม {games.BY_ID[q['game']]['title']} ไปที่บ้านแล้วค่ะ "
                                       f"จะแจ้งเมื่อ{self.s.elder_name}เล่นเสร็จนะคะ 🎮"))
            return
        if ev["type"] != "message" or ev["message"].get("type") != "text":
            return
        msg = ev["message"]["text"].strip()

        if msg.startswith("ลงทะเบียน"):
            code = msg.removeprefix("ลงทะเบียน").strip()
            if self.s.family_code and code != self.s.family_code:
                await reply(L.text("รหัสครอบครัวไม่ถูกต้องค่ะ"))
                return
            display = await self.line.display_name(user)
            self.store.add_family(user, display)
            self.store.add_event("family_join", None, None, None, {"name": display})
            await reply(L.text(f"ลงทะเบียนเรียบร้อยค่ะ คุณ{display} จะได้รับแจ้งเตือนเมื่อ{self.s.elder_name}ล้มหรือต้องการความช่วยเหลือ 🙏"),
                        L.text(L.HELP_TEXT))
            return
        if not name:
            await reply(L.text("กรุณาลงทะเบียนก่อนนะคะ: พิมพ์ \"ลงทะเบียน <รหัสครอบครัว>\""))
            return
        if msg in ("ยกเลิกแจ้งเตือน", "เลิกรับแจ้งเตือน"):
            self.store.remove_family(user)
            await reply(L.text("ยกเลิกการรับแจ้งเตือนแล้วค่ะ"))
        elif msg.lower() in ("เกม", "game", "games", "โหมดเกม", "เลือกเกม"):
            await reply(L.games_carousel(f"เลือกเกมส่งให้{self.s.elder_name}เล่น"))
        elif msg in ("สถานะ", "status", "เป็นไงบ้าง"):
            await reply(L.status_card(self.status()))
        elif msg.lower() in ("ช่วยเหลือ", "help", "?", "วิธีใช้"):
            await reply(L.text(L.HELP_TEXT))
        else:
            await self.family_message(msg, name)
            await reply(L.text(f"💌 ส่งข้อความไปอ่านออกเสียงให้{self.s.elder_name}ฟังแล้วค่ะ"))

    # --- status ------------------------------------------------------------

    def status(self) -> dict:
        now = time.time()
        today = start_of_today()
        loc = self.devices.get(self.location) if self.location else None
        posture = loc.posture if loc else UNKNOWN
        resting = self.activity.resting_seconds(now)
        active = self.store.active_alerts()
        plays = self.store.plays_since(today)
        return {
            "now": now,
            "elder_name": self.s.elder_name,
            "elder_phone": self.s.elder_phone,
            "where": loc.device.name if loc else None,
            "location": self.location,
            "posture": posture,
            "posture_th": POSTURE_TH.get(posture, posture) if loc else "ไม่พบในบ้าน",
            "posture_minutes": round(resting / 60) if resting else 0,
            "resting_seconds": round(resting),
            "moving": bool(loc and loc.moving),
            "devices": [{
                "id": d.device.id, "name": d.device.name, "room": d.device.room,
                "online": d.last is not None and now - d.last_seen < self.s.device_timeout_s,
                "presence": d.presence, "height": None if d.height is None else round(d.height),
                "posture": d.posture, "moving": d.moving,
                "moving_energy": d.last.moving_energy if d.last else 0,
                "still_energy": d.last.still_energy if d.last else 0,
                "fall_state": d.fall.state,
                "bathroom_inside_s": round(now - d.bath.entered) if d.bath and d.bath.inside else None,
                "history": d.history[-60:],
            } for d in self.devices.values()],
            "alerts": active,
            "open_alerts": len(active),
            "fall_check": self.fall_check,
            "current_play": self.current_play,
            "last_message": self.last_message,
            "games_today": sum(p["status"] == "done" for p in plays),
            "plays_today": plays,
            "bathroom_today": self.store.count_since("bathroom_visit", today),
            "family": self.store.family(),
            "line_live": self.line.live,
            "line_broadcast": self.line.broadcast,
            "ai": "claude" if ai.ai_enabled() else "rules",
            "demo": self.s.demo,
            "limits": {"sit_s": self.s.sit_limit_s, "lie_s": self.s.lie_limit_s,
                       "fall_confirm_s": self.s.fall_confirm_s, "bathroom_still_s": self.s.bathroom_still_s},
        }
