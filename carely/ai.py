"""Picks which game to invite the elder to play, and writes the spoken invitation.

Uses Claude when an API key is configured; otherwise (or if the call fails)
falls back to simple rules, so the nudge always works offline.
"""

import logging
import os
import random
from typing import Literal

import anthropic
from pydantic import BaseModel, Field

from . import games

log = logging.getLogger("carely.ai")

GameId = Literal[tuple(g["id"] for g in games.GAMES)]


class GamePick(BaseModel):
    game_id: GameId
    say: str = Field(description="คำชวนภาษาไทยที่จะพูดออกเสียงให้ผู้สูงอายุฟัง 1-2 ประโยค สุภาพ อบอุ่น ลงท้ายด้วย ค่ะ/นะคะ")
    reason: str = Field(description="เหตุผลสั้นๆ ภาษาไทยที่เลือกเกมนี้ สำหรับให้ลูกหลานอ่าน")


SYSTEM = """คุณคือผู้ช่วยดูแลผู้สูงอายุที่อยู่บ้านคนเดียว ทำหน้าที่เลือกเกมสั้นๆ ให้ผู้สูงอายุเล่น
เพื่อให้ได้ลุกขึ้นขยับร่างกายและคลายเหงา เลือกจากรายการเกมที่ให้มาเท่านั้น

หลักการเลือก:
- ความปลอดภัยมาก่อน: ถ้าข้อมูลสุขภาพบอกว่าปวดเข่า เดินลำบาก หรือเสี่ยงล้ม ห้ามเลือกเกมที่ knee_safe เป็น false
  และถ้าเพิ่งนอนนาน ให้เริ่มจากเกมที่ทำได้ขณะนั่ง (seated_ok) ก่อน
- นั่งหรือนอนนาน: เลือกเกมเคลื่อนไหว (kind = move) เป็นหลัก
- ผู้สูงอายุกดขอเล่นเอง หรือช่วงเย็นค่ำ: เกมฝึกสมอง (kind = brain) ก็ได้
- หลีกเลี่ยงเกมที่เพิ่งเล่นไปวันนี้ เพื่อไม่ให้เบื่อ ถ้าเกมไหนถูกข้ามบ่อย ให้ลองเกมอื่น
- คำชวนใช้ภาษาพูดที่อบอุ่น เรียกชื่อผู้สูงอายุ เป็นเสียงผู้หญิง (ค่ะ/นะคะ) ไม่เกิน 2 ประโยค ไม่ใช้อีโมจิ
  ไม่ตำหนิว่านั่งนาน ให้ชวนแบบสนุก"""


def ai_enabled() -> bool:
    if os.environ.get("CARELY_AI", "").lower() == "off":
        return False
    return bool(
        os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("ANTHROPIC_AUTH_TOKEN")
        or os.environ.get("CARELY_AI", "").lower() == "on"  # use an `ant auth login` profile
    )


def describe_context(ctx: dict) -> str:
    trigger = {
        "sitting": f"นั่งต่อเนื่องมาแล้ว {ctx.get('minutes', 0)} นาที",
        "lying": f"นอนต่อเนื่องมาแล้ว {ctx.get('minutes', 0)} นาที (ช่วงกลางวัน)",
        "elder_asked": "ผู้สูงอายุกดปุ่มขอเล่นเกมเอง",
    }.get(ctx.get("trigger"), str(ctx.get("trigger")))
    played = ", ".join(f"{p['game_id']} ({p['status']})" for p in ctx.get("played_today", [])) or "ยังไม่ได้เล่น"
    lines = [
        f"ชื่อที่ใช้เรียก: {ctx.get('elder_name', 'คุณยาย')}",
        f"ข้อมูลสุขภาพ/ความชอบ: {ctx.get('notes') or 'ไม่มีข้อมูล'}",
        f"เวลาตอนนี้: {ctx.get('hour', 12):02d}:00 น.",
        f"เหตุที่ชวนเล่น: {trigger}",
        f"เกมที่เล่นวันนี้ (สถานะ): {played}",
        "",
        "รายการเกม:",
    ]
    for g in games.summary():
        lines.append(
            f"- {g['id']}: {g['title']} | kind={g['kind']} | {g['minutes']} นาที | "
            f"seated_ok={g['seated_ok']} | knee_safe={g['knee_safe']} | {g['desc']}"
        )
    return "\n".join(lines)


def ask_claude(ctx: dict, model: str) -> GamePick | None:
    client = anthropic.Anthropic(timeout=25.0, max_retries=1)
    response = client.beta.messages.parse(
        model=model,
        max_tokens=4000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "low"},
        system=SYSTEM,
        messages=[{"role": "user", "content": describe_context(ctx)}],
        output_format=GamePick,
    )
    if response.stop_reason == "refusal":
        log.warning("AI declined to pick a game; using rules")
        return None
    return response.parsed_output


def pick(ctx: dict, model: str = "claude-opus-5-5") -> dict:
    """Returns {"game_id", "say", "reason", "by": "ai" | "rules"}."""
    if ai_enabled():
        try:
            p = ask_claude(ctx, model)
            if p and p.game_id in games.BY_ID and _allowed(games.BY_ID[p.game_id], ctx):
                return {"game_id": p.game_id, "say": p.say.strip(), "reason": p.reason.strip(), "by": "ai"}
        except anthropic.APIConnectionError:
            log.warning("AI unreachable; using rules")
        except anthropic.APIStatusError as e:
            log.warning("AI error %s; using rules", e.status_code)
        except Exception:  # never let the AI break a nudge
            log.exception("AI pick failed; using rules")
    return rule_pick(ctx)


# --- Offline rules ---------------------------------------------------------

PREFER = {
    "lying": ["arm_sky", "clap", "march"],
    "sitting": ["march", "arm_sky", "clap"],
    "elder_asked": ["clap", "arm_sky", "march"],
}


def _careful(ctx: dict) -> bool:
    notes = (ctx.get("notes") or "").lower()
    return any(w in notes for w in ("เข่า", "ล้ม", "เดินลำบาก", "ไม้เท้า", "knee", "walker"))


def _allowed(game: dict, ctx: dict) -> bool:
    return game["knee_safe"] or not _careful(ctx)


def rule_pick(ctx: dict) -> dict:
    trigger = ctx.get("trigger", "sitting")
    recent = [p["game_id"] for p in ctx.get("played_today", [])][-3:]
    order = list(PREFER.get(trigger, PREFER["sitting"]))
    if trigger == "elder_asked" and ctx.get("hour", 12) < 17:
        order = order[2:] + order[:2]  # daytime: the more active game first
    order += [g["id"] for g in games.GAMES if g["id"] not in order]
    options = [i for i in order if i not in recent and _allowed(games.BY_ID[i], ctx)]
    options = options or [i for i in order if _allowed(games.BY_ID[i], ctx)]
    game_id = random.choice(options[:2]) if len(options) > 1 else options[0]
    g = games.BY_ID[game_id]
    name = ctx.get("elder_name", "คุณยาย")
    opener = {
        "sitting": f"{name}คะ นั่งมาสักพักแล้ว",
        "lying": f"{name}คะ ตื่นมายืดเส้นยืดสายกันหน่อย",
        "elder_asked": f"ได้เลยค่ะ{name}",
    }.get(trigger, f"{name}คะ")
    return {
        "game_id": game_id,
        "say": f"{opener} มาเล่นเกม{g['title']}กันไหมคะ",
        "reason": f"เลือกตามกฎพื้นฐาน: {trigger}, ไม่ซ้ำกับเกมที่เพิ่งเล่น",
        "by": "rules",
    }
