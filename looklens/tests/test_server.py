"""End-to-end through the HTTP API, with LINE in preview mode (nothing is sent)."""

import base64
import hashlib
import hmac
import importlib
import json

import pytest
from fastapi.testclient import TestClient

SECRET = "test-secret"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CARELY_DB", str(tmp_path / "t.db"))
    monkeypatch.setenv("LINE_CHANNEL_SECRET", SECRET)
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "")
    monkeypatch.setenv("FAMILY_CODE", "1234")
    monkeypatch.setenv("RADAR_TOKEN", "radar-secret")
    monkeypatch.setenv("CARELY_AI", "off")
    monkeypatch.setenv("CARELY_ADMIN_KEY", "")
    import carely.server as server
    server = importlib.reload(server)
    with TestClient(server.app) as c:
        c.server = server
        yield c


def line_event(c, ev):
    body = json.dumps({"events": [{"replyToken": "r", "source": {"userId": "U1"}, **ev}]}).encode()
    sig = base64.b64encode(hmac.new(SECRET.encode(), body, hashlib.sha256).digest()).decode()
    return c.post("/line/webhook", content=body, headers={"x-line-signature": sig, "content-type": "application/json"})


def text(c, t):
    return line_event(c, {"type": "message", "message": {"type": "text", "text": t}})


def last_reply(c):
    return c.server.line.outbox[0]["messages"]


def test_webhook_rejects_bad_signature(client):
    r = client.post("/line/webhook", content=b'{"events":[]}', headers={"x-line-signature": "bad"})
    assert r.status_code == 401


def test_family_flow(client):
    hub = client.server.hub
    text(client, "เกม")
    assert "ลงทะเบียน" in last_reply(client)[0]["text"]  # must register first
    text(client, "ลงทะเบียน 9999")
    assert hub.family_ids() == []
    text(client, "ลงทะเบียน 1234")
    assert hub.family_ids() == ["U1"]

    text(client, "เกม")
    assert last_reply(client)[0]["contents"]["type"] == "carousel"

    line_event(client, {"type": "postback", "postback": {"data": "action=play&game=clap"}})
    play = hub.current_play
    assert play["game_id"] == "clap" and play["source"] == "family"

    r = client.post("/api/elder/play", json={"play_id": play["id"], "status": "done", "score": 80})
    assert r.status_code == 200
    pushed = client.server.line.outbox[0]
    assert pushed["to"] == "U1" and "80%" in pushed["messages"][0]["text"]

    text(client, "กินข้าวหรือยังคะ")
    assert hub.last_message["text"] == "กินข้าวหรือยังคะ"


def test_sos_alert_and_ack_from_line(client):
    hub = client.server.hub
    text(client, "ลงทะเบียน 1234")
    a = client.post("/api/elder/sos").json()["alert"]
    card = client.server.line.outbox[0]["messages"][0]
    assert card["type"] == "flex" and str(a["id"]) in json.dumps(card)
    line_event(client, {"type": "postback", "postback": {"data": f"action=ack&alert={a['id']}"}})
    assert hub.store.alert(a["id"])["status"] == "acked"
    client.post("/api/elder/ok")
    assert hub.store.active_alerts() == []


def test_radar_needs_token_and_tracks_posture(client):
    assert client.post("/api/radar", json={"device": "living", "presence": True}).status_code == 401
    h = {"x-radar-token": "radar-secret"}
    for _ in range(3):
        r = client.post("/api/radar", headers=h, json={"device": "living", "presence": True, "distance_cm": 150})
        assert r.status_code == 200
    st = client.get("/api/state").json()
    assert st["where"] == "ห้องนั่งเล่น" and st["posture"] == "sitting"


def test_sitting_in_bathroom_does_not_count_as_sitting_long(client):
    hub = client.server.hub
    h = {"x-radar-token": "radar-secret"}
    for _ in range(3):
        client.post("/api/radar", headers=h, json={"device": "bathroom", "presence": True, "distance_cm": 130})
    assert hub.status()["posture"] == "sitting"
    assert hub.activity.resting_since is None


def test_camera_posture_fall_and_reps(client):
    hub = client.server.hub
    assert client.get("/camera").status_code == 200
    # posture from the camera page, no radar token needed (same-origin page)
    r = client.post("/api/camera", json={"presence": True, "moving_energy": 50, "posture": "sitting"})
    assert r.status_code == 200
    st = client.get("/api/state").json()
    cam = next(d for d in st["devices"] if d["id"] == "camera")
    assert cam["online"] and cam["moving"] and st["posture"] == "sitting"
    assert client.post("/api/camera", json={"presence": True, "posture": "dancing"}).status_code == 400

    # a fall flagged by the camera goes through the same fall detector as the radar
    client.post("/api/camera", json={"presence": True, "posture": "floor", "fall": True})
    assert hub.devices["camera"].fall.state == "SUSPECTED"
    assert any(e["kind"] == "fall_suspected" and e["device"] == "camera" for e in hub.store.events())

    # counted moves are passed on to the elder screen
    q = hub.subscribe()
    assert client.post("/api/camera/rep", json={"move": "arms_up"}).status_code == 200
    assert q.get_nowait()["move"] == "arms_up"
    assert client.post("/api/camera/rep", json={"move": "jump"}).status_code == 400


def test_three_camera_games():
    from carely import games
    assert [g["id"] for g in games.GAMES] == ["arm_sky", "march", "clap"]
    moves = {s.get("detect") for g in games.GAMES for s in g["steps"]} - {None}
    assert moves == {"arms_up", "clap"}
