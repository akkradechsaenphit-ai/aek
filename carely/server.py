"""Web server: radar input, LINE webhook, the elder screen and the family dashboard.

Run:  uv run uvicorn carely.server:app --host 0.0.0.0 --port 8000
"""

import asyncio
import contextlib
import hmac
import json
import logging
import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import games
from .config import FLOOR, LYING, ROOT, SITTING, STANDING, Device, load_settings
from .hub import Hub
from .line import LineClient, verify_signature
from .radar import Reading
from .sim import VirtualHome
from .store import Store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
log = logging.getLogger("carely")

settings = load_settings()
store = Store(settings.db_path)
line = LineClient(settings.line_token, settings.line_secret, settings.line_broadcast)
hub = Hub(settings, store, line)
sim = VirtualHome(hub)
STATIC = ROOT / "carely" / "static"


async def ticker():
    while True:
        try:
            await hub.tick()
        except Exception:
            log.exception("tick failed")
        await asyncio.sleep(1.0)


@contextlib.asynccontextmanager
async def lifespan(_app):
    task = asyncio.create_task(ticker())
    log.info("Carely ready | demo=%s | LINE=%s | AI=%s", settings.demo,
             "live" if line.live else "preview", hub.status()["ai"])
    yield
    task.cancel()
    await sim.act("stop")


app = FastAPI(title="Carely", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")

PUBLIC = ("/line/webhook", "/api/radar", "/static/", "/favicon")


@app.middleware("http")
async def admin_key(request: Request, call_next):
    """If CARELY_ADMIN_KEY is set, pages need ?key=... once (then a cookie)."""
    key = settings.admin_key
    path = request.url.path
    if not key or path.startswith(PUBLIC):
        return await call_next(request)
    given = request.query_params.get("key") or request.cookies.get("carely_key") or ""
    if not hmac.compare_digest(given, key):
        return JSONResponse({"error": "ต้องใส่ ?key=... ในลิงก์"}, status_code=401)
    response = await call_next(request)
    if request.query_params.get("key"):
        response.set_cookie("carely_key", key, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 365)
    return response


# --- pages -----------------------------------------------------------------

@app.get("/")
async def dashboard():
    return FileResponse(STATIC / "dashboard.html")


@app.get("/elder")
async def elder():
    return FileResponse(STATIC / "elder.html")


@app.get("/camera")
async def camera_page():
    return FileResponse(STATIC / "camera.html")


@app.get("/favicon.ico")
async def favicon():
    return RedirectResponse("/static/icon.svg")


# --- radar -----------------------------------------------------------------

@app.post("/api/radar")
async def radar(request: Request):
    """Body: one reading, a list, or {"readings": [...]}. See README for the fields."""
    if settings.radar_token and not hmac.compare_digest(request.headers.get("x-radar-token", ""), settings.radar_token):
        raise HTTPException(401, "bad radar token")
    body = await request.json()
    items = body.get("readings", [body]) if isinstance(body, dict) else body
    now = time.time()
    for p in items[:20]:
        await hub.ingest(Reading.from_payload(p, now))
    return {"ok": True, "n": len(items[:20])}


# --- camera (camera.html) ----------------------------------------------------
# The browser does the pose estimation itself; only these derived values arrive
# here. No image, video or keypoint ever reaches the server.

CAMERA = "camera"
CAMERA_MOVES = ("arms_up", "clap")


class CameraReading(BaseModel):
    presence: bool
    moving_energy: int = 0  # 0-100, how much the body moved in the last second
    posture: str | None = None  # standing | sitting | lying | floor
    fall: bool = False


class CameraRep(BaseModel):
    move: str


@app.post("/api/camera")
async def camera_reading(c: CameraReading):
    if c.posture not in (None, STANDING, SITTING, LYING, FLOOR):
        raise HTTPException(400, "bad posture")
    settings.devices.setdefault(CAMERA, Device(CAMERA, "living", "กล้อง (ห้องนั่งเล่น)"))
    energy = max(0, min(100, c.moving_energy))
    await hub.ingest(Reading.from_payload({
        "device": CAMERA, "presence": c.presence, "moving_energy": energy,
        "still_energy": 60 if c.presence and energy < settings.moving_energy_min else 0,
        "posture": c.posture, "fall": c.fall,
    }, time.time()))
    return {"ok": True}


@app.post("/api/camera/rep")
async def camera_rep(r: CameraRep):
    """One arm raise / clap seen by the camera; the elder screen counts it during a game."""
    if r.move not in CAMERA_MOVES:
        raise HTTPException(400, "bad move")
    hub.broadcast("rep", move=r.move)
    return {"ok": True}


# --- state / live stream -----------------------------------------------------

@app.get("/api/state")
async def state():
    return {**hub.status(), "sim": sim.state()}


@app.get("/api/events")
async def events(limit: int = 60):
    return store.events(min(limit, 300))


@app.get("/api/alerts")
async def alerts():
    return store.recent_alerts(20)


@app.get("/api/games")
async def game_list():
    return {"games": games.GAMES}


@app.get("/api/line/outbox")
async def outbox():
    return list(line.outbox)


@app.get("/api/stream")
async def stream(request: Request):
    """Server-sent events: alerts, game offers and family messages, as they happen."""
    q = hub.subscribe()

    async def gen():
        try:
            yield "event: hello\ndata: {}\n\n"
            while not await request.is_disconnected():
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"data: {json.dumps(msg, ensure_ascii=False, default=str)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            hub.unsubscribe(q)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# --- elder screen actions ----------------------------------------------------

class PlayUpdate(BaseModel):
    play_id: int
    status: str  # playing | done | skipped
    score: float | None = None


@app.post("/api/elder/ok")
async def elder_ok():
    await hub.elder_ok()
    return {"ok": True}


@app.post("/api/elder/sos")
async def elder_sos():
    a = await hub.sos()
    return {"ok": True, "alert": a}


@app.post("/api/elder/want-game")
async def elder_wants_game():
    return await hub.offer_game(trigger="elder_asked")


@app.post("/api/elder/play")
async def elder_play(u: PlayUpdate):
    if u.status not in ("playing", "done", "skipped"):
        raise HTTPException(400, "bad status")
    await hub.game_update(u.play_id, u.status, u.score)
    return {"ok": True}


# --- family dashboard actions ----------------------------------------------

class SendGame(BaseModel):
    game_id: str | None = None  # None = let the AI pick
    sender: str = "ลูกหลาน"


class Message(BaseModel):
    text: str
    sender: str = "ลูกหลาน"


class Ack(BaseModel):
    by: str = "ลูกหลาน (เว็บ)"


@app.post("/api/family/game")
async def family_game(b: SendGame):
    if b.game_id and b.game_id not in games.BY_ID:
        raise HTTPException(404, "no such game")
    if b.game_id:
        return await hub.offer_game(game_id=b.game_id, source="family", sent_by=b.sender[:30])
    return await hub.offer_game(trigger="sitting", minutes=round(hub.activity.resting_seconds(time.time()) / 60))


@app.post("/api/family/message")
async def family_message(m: Message):
    if not m.text.strip():
        raise HTTPException(400, "empty")
    await hub.family_message(m.text.strip(), m.sender[:30])
    return {"ok": True}


@app.post("/api/alerts/{alert_id}/ack")
async def ack(alert_id: int, b: Ack):
    a = await hub.ack(alert_id, b.by[:30])
    if not a:
        raise HTTPException(404, "no such alert")
    return a


# --- simulator ---------------------------------------------------------------

class SimAction(BaseModel):
    action: str
    room: str | None = None


@app.post("/api/sim")
async def simulate(a: SimAction):
    if a.room and a.room not in settings.devices:
        raise HTTPException(404, "no such room")
    return await sim.act(a.action, a.room)


# --- LINE ----------------------------------------------------------------------

@app.post("/line/webhook")
async def line_webhook(request: Request):
    body = await request.body()
    if not settings.line_secret or not verify_signature(settings.line_secret, body, request.headers.get("x-line-signature", "")):
        raise HTTPException(401, "bad signature")
    for ev in json.loads(body).get("events", []):
        try:
            await hub.handle_line(ev)
        except Exception:
            log.exception("LINE event failed: %s", ev.get("type"))
    return {"ok": True}


@app.post("/api/line/test")
async def line_test():
    ids = hub.family_ids()
    ok = await line.push(ids, [{"type": "text", "text": "🔔 ทดสอบระบบ Carely: ถ้าเห็นข้อความนี้ แปลว่าการแจ้งเตือนพร้อมใช้งานแล้วค่ะ"}])
    return {"sent": ok, "recipients": "เพื่อนทุกคนของ OA" if line.broadcast else len(ids), "live": line.live}
