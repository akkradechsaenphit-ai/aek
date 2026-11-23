import base64
import hashlib
import hmac
import json

from carely import ai, games
from carely import line as L
from carely.radar import LD2410Parser, Reading


def frame(state, mdist, menergy, sdist, senergy):
    data = bytes([0x02, 0xAA, state]) + mdist.to_bytes(2, "little") + bytes([menergy]) \
        + sdist.to_bytes(2, "little") + bytes([senergy]) + (300).to_bytes(2, "little") + bytes([0x55, 0x00])
    return bytes([0xF4, 0xF3, 0xF2, 0xF1]) + len(data).to_bytes(2, "little") + data + bytes([0xF8, 0xF7, 0xF6, 0xF5])


def test_ld2410_parser_handles_split_and_noise():
    p = LD2410Parser()
    raw = b"\x00\x13" + frame(1, 110, 60, 0, 0) + frame(2, 0, 0, 235, 40)
    out = p.feed(raw[:9]) + p.feed(raw[9:])
    assert out[0] == {"presence": True, "moving_energy": 60, "still_energy": 0, "distance_cm": 110}
    assert out[1] == {"presence": True, "moving_energy": 0, "still_energy": 40, "distance_cm": 235}


def test_payload_ignores_unknown_posture():
    r = Reading.from_payload({"device": "living", "presence": True, "posture": "flying", "distance_cm": 100}, 5.0)
    assert r.posture is None and r.distance_cm == 100 and r.t == 5.0


def test_line_signature():
    body = b'{"events":[]}'
    sig = base64.b64encode(hmac.new(b"secret", body, hashlib.sha256).digest()).decode()
    assert L.verify_signature("secret", body, sig)
    assert not L.verify_signature("secret", body, "nope")


def test_button_labels_fit_line_limit():
    card = L.alert_card({"id": 1, "ts": 0, "level": "urgent", "title": "ตรวจพบการล้ม", "room": "ห้องน้ำ", "detail": "x"},
                        "คุณยายมะลิวัลย์", "0812345678")
    for b in card["contents"]["footer"]["contents"]:
        assert len(b["action"]["label"]) <= 20
    assert len(L.games_carousel()["contents"]["contents"]) <= 12


def test_rule_pick_respects_knees_and_variety(monkeypatch):
    monkeypatch.setenv("CARELY_AI", "off")
    ctx = {"trigger": "sitting", "notes": "ปวดเข่า", "played_today": [{"game_id": "march", "status": "done"}]}
    for _ in range(30):
        p = ai.pick(ctx)
        assert games.BY_ID[p["game_id"]]["knee_safe"]
        assert p["game_id"] != "march"
        assert p["by"] == "rules"


def test_broadcast_mode_needs_no_registration():
    import asyncio
    c = L.LineClient("", "", broadcast=True)
    asyncio.run(c.push([], [L.text("hi")]))
    assert c.outbox[0]["to"] == "เพื่อนทุกคนของ OA"
    alert = {"id": 1, "level": "urgent", "ts": 0, "title": "ล้ม", "room": "ห้องน้ำ", "detail": ""}
    no_ack = json.dumps(L.alert_card(alert, "คุณยาย", "0812345678", ack=False), ensure_ascii=False)
    assert "postback" not in no_ack and "tel:0812345678" in no_ack
    assert "postback" in json.dumps(L.alert_card(alert, "คุณยาย", "0812345678"))
