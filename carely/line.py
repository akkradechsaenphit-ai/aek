"""LINE Official Account (Messaging API): push alerts to the family, read their
commands from the webhook, and build the Flex cards.

With no channel token configured it runs in preview mode: nothing is sent, but
every message is kept in `outbox` so the dashboard can show what LINE would get.
"""

import base64
import hashlib
import hmac
import logging
import time
from collections import deque

import httpx

from . import games

log = logging.getLogger("carely.line")
API = "https://api.line.me/v2/bot"

SAGE, CORAL, RED, AMBER, INK, MUTED = "#718b72", "#d69a8c", "#a33d3b", "#9d712c", "#3f4541", "#858d88"


def verify_signature(secret: str, body: bytes, signature: str) -> bool:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    return hmac.compare_digest(base64.b64encode(digest).decode(), signature or "")


class LineClient:
    def __init__(self, token: str, secret: str, broadcast: bool = False):
        self.token = token
        self.secret = secret
        self.broadcast = broadcast  # send to every friend of the OA instead of registered family
        self.outbox: deque[dict] = deque(maxlen=40)
        self.http = httpx.AsyncClient(timeout=10.0)

    @property
    def live(self) -> bool:
        return bool(self.token)

    async def _post(self, path: str, payload: dict, to: str) -> bool:
        entry = {"ts": time.time(), "to": to, "messages": payload["messages"], "sent": False, "error": None}
        self.outbox.appendleft(entry)
        if not self.live:
            return False
        try:
            r = await self.http.post(f"{API}{path}", json=payload, headers={"Authorization": f"Bearer {self.token}"})
            entry["sent"] = r.status_code == 200
            if r.status_code != 200:
                entry["error"] = f"{r.status_code} {r.text[:200]}"
                log.warning("LINE %s failed: %s", path, entry["error"])
        except httpx.HTTPError as e:
            entry["error"] = str(e)
            log.warning("LINE %s failed: %s", path, e)
        return entry["sent"]

    async def push(self, user_ids: list[str], messages: list[dict]) -> bool:
        if self.broadcast:
            return await self._post("/message/broadcast", {"messages": messages}, "เพื่อนทุกคนของ OA")
        if not user_ids:
            self.outbox.appendleft({"ts": time.time(), "to": "(ยังไม่มีลูกหลานลงทะเบียน)",
                                    "messages": messages, "sent": False, "error": "no recipients"})
            return False
        if len(user_ids) == 1:
            return await self._post("/message/push", {"to": user_ids[0], "messages": messages}, user_ids[0])
        return await self._post("/message/multicast", {"to": user_ids, "messages": messages}, f"{len(user_ids)} คน")

    async def reply(self, reply_token: str, messages: list[dict]) -> bool:
        return await self._post("/message/reply", {"replyToken": reply_token, "messages": messages}, "reply")

    async def display_name(self, user_id: str) -> str:
        if not self.live:
            return "ลูกหลาน"
        try:
            r = await self.http.get(f"{API}/profile/{user_id}", headers={"Authorization": f"Bearer {self.token}"})
            if r.status_code == 200:
                return r.json().get("displayName", "ลูกหลาน")
        except httpx.HTTPError:
            pass
        return "ลูกหลาน"


# --- Message builders ------------------------------------------------------

def text(t: str) -> dict:
    return {"type": "text", "text": t[:5000]}


def _txt(t, **kw):
    return {"type": "text", "text": t, "wrap": True, **kw}


def _button(label: str, action: dict, style="secondary", color=None) -> dict:
    b = {"type": "button", "style": style, "height": "sm", "action": {**action, "label": label[:20]}}
    if color:
        b["color"] = color
    return b


def alert_card(alert: dict, elder_name: str, phone: str, ack: bool = True) -> dict:
    """Red card for a fall / bathroom alert with "on my way" and "call" buttons.
    `ack=False` (broadcast mode, no webhook) drops "on my way": nobody would receive the tap."""
    urgent = alert["level"] == "urgent"
    color = RED if urgent else AMBER
    at = time.strftime("%H:%M", time.localtime(alert["ts"]))
    buttons = []
    if ack:
        buttons.append(_button("🚗 ฉันกำลังไป", {"type": "postback", "data": f"action=ack&alert={alert['id']}",
                                               "displayText": "ฉันกำลังไปดูค่ะ/ครับ"}, "primary", color))
    if phone:
        buttons.append(_button(f"📞 โทรหา{elder_name}", {"type": "uri", "uri": f"tel:{phone}"},
                               "secondary" if ack else "primary", None if ack else color))
    return {
        "type": "flex",
        "altText": f"🚨 {alert['title']} ({alert['room']} {at} น.)",
        "contents": {
            "type": "bubble",
            "header": {"type": "box", "layout": "vertical", "backgroundColor": color, "paddingAll": "16px", "contents": [
                _txt("🚨 แจ้งเตือนด่วน" if urgent else "⚠️ ควรตรวจสอบ", color="#ffffff", size="sm"),
                _txt(alert["title"], color="#ffffff", size="xl", weight="bold"),
            ]},
            "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [
                _txt(f"👵 {elder_name}", weight="bold", color=INK),
                _txt(f"📍 {alert['room']}   🕐 {at} น.", color=INK, size="sm"),
                _txt(alert["detail"], color=MUTED, size="sm"),
                _txt("ระบบอาจประเมินผิดพลาด กรุณาโทรหรือไปดูโดยเร็ว", color=MUTED, size="xs"),
            ]},
            "footer": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": buttons},
        },
    }


def games_carousel(note: str = "") -> dict:
    bubbles = []
    for g in games.GAMES:
        bubbles.append({
            "type": "bubble", "size": "micro",
            "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [
                _txt(g["emoji"], size="3xl", align="center"),
                _txt(g["title"], weight="bold", size="md", align="center", color=INK),
                _txt(g["desc"], size="xs", color=MUTED),
                _txt(f"{'🏃 ขยับร่างกาย' if g['kind'] == 'move' else '🧠 ฝึกสมอง'} · {g['minutes']} นาที", size="xxs", color=SAGE),
            ]},
            "footer": {"type": "box", "layout": "vertical", "contents": [
                _button("ส่งเกมนี้", {"type": "postback", "data": f"action=play&game={g['id']}",
                                      "displayText": f"ส่งเกม {g['title']}"}, "primary", SAGE),
            ]},
        })
    return {"type": "flex", "altText": note or "เลือกเกมส่งให้เล่น", "contents": {"type": "carousel", "contents": bubbles}}


def status_card(st: dict) -> dict:
    lines = [
        _txt(f"👵 {st['elder_name']}", weight="bold", size="lg", color=INK),
        _txt(f"📍 {st['where'] or 'ไม่พบในบ้าน (อาจออกไปข้างนอก)'}", size="sm", color=INK),
        _txt(f"🧍 ตอนนี้: {st['posture_th']}" + (f" มา {st['posture_minutes']} นาที" if st['posture_minutes'] else ""), size="sm", color=INK),
        _txt(f"🎮 วันนี้เล่นเกมแล้ว {st['games_today']} เกม · เข้าห้องน้ำ {st['bathroom_today']} ครั้ง", size="sm", color=INK),
    ]
    if st["open_alerts"]:
        lines.append(_txt(f"🚨 มีแจ้งเตือนค้าง {st['open_alerts']} รายการ", size="sm", color=RED, weight="bold"))
    else:
        lines.append(_txt("✅ ไม่มีเหตุผิดปกติ", size="sm", color=SAGE))
    return {
        "type": "flex", "altText": f"สถานะ{st['elder_name']}: {st['posture_th']}",
        "contents": {"type": "bubble", "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": lines},
                     "footer": {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                         _button("🎮 ส่งเกม", {"type": "message", "text": "เกม"}, "primary", SAGE),
                         _button("🔄 อัปเดต", {"type": "message", "text": "สถานะ"}),
                     ]}},
    }


HELP_TEXT = (
    "พิมพ์คำสั่งได้เลยค่ะ\n"
    "• เกม — เลือกเกมส่งให้เล่น\n"
    "• สถานะ — ดูว่าตอนนี้เป็นอย่างไร\n"
    "• ข้อความอื่นๆ — ระบบจะอ่านออกเสียงให้ที่บ้านฟัง 💌"
)
