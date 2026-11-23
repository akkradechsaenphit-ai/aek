#!/usr/bin/env python3
"""LookLens local server (Python standard library only).

  py server.py            ->  http://<this PC>:8090  (HTTP)  and, if cert.pem + key.pem exist, https://<this PC>:8443

* Serves index.html, family.html and carely-shared.js to the PC and to phones on the same Wi-Fi.
* Handles many requests at once (the old `http.server` served one at a time and could hang).
* Relays the messages the two pages send each other, so the home screen on this PC and the
  family app on a phone can talk (status, alerts, exercise notices, call signalling).
  Nothing is stored on disk; the relay keeps only the latest status in memory.
"""
import http.server
import json
import os
import queue
import socket
import socketserver
import ssl
import sys
import threading
import urllib.parse

ROOT = os.path.dirname(os.path.abspath(__file__))
HTTP_PORT = int(os.environ.get("LOOKLENS_PORT", "8090"))
HTTPS_PORT = int(os.environ.get("LOOKLENS_HTTPS_PORT", "8443"))

seen_senders = set()
clients = {}          # client id -> queue of raw JSON strings waiting to be sent
last_state = None     # latest "state" message, so a phone that joins late sees the current status
lock = threading.Lock()

# ---------------------------------------------------------------- private pairing
# This PC (loopback / its own address) is trusted. One other device may pair, and only an Android phone,
# by typing the 6-digit code printed here. After that the door is shut: other devices on the Wi-Fi get nothing.
import hashlib
import json as _json
import secrets
import time

PAIR_FILE = os.environ.get("LOOKLENS_PAIR_FILE") or os.path.join(ROOT, "pairing.json")
ANY_DEVICE = "--any-device" in sys.argv          # allow a non-Android device (tablet, iPhone, another browser) to pair
MAX_REMOTE = 1                                   # one paired phone
pairing = {"pin": "", "tokens": []}
fails = {}                                       # ip -> [count, locked_until]
local_ips = {"127.0.0.1", "::1"}


def _save_pairing():
    try:
        with open(PAIR_FILE, "w", encoding="utf-8") as f:
            _json.dump(pairing, f)
    except OSError:
        pass


def _load_pairing():
    global pairing
    if "--reset-pairing" not in sys.argv:
        try:
            with open(PAIR_FILE, encoding="utf-8-sig") as f:
                data = _json.load(f)
            if data.get("pin"):
                toks = [t if isinstance(t, dict) else {"h": t, "ip": ""} for t in data.get("tokens", [])]
                pairing = {"pin": data["pin"], "tokens": toks}
                return
        except (OSError, ValueError):
            pass
    pairing = {"pin": f"{secrets.randbelow(10 ** 6):06d}", "tokens": []}
    _save_pairing()


def _hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def broadcast(sender, raw, msg):
    """Send a message to every connected page except the one that sent it."""
    global last_state
    with lock:
        if isinstance(msg, dict) and msg.get("type") == "state":
            last_state = raw
        for cid, q in clients.items():
            if cid == sender:
                continue
            try:
                q.put_nowait(raw)
            except queue.Full:                      # slow client: drop its oldest message
                try:
                    q.get_nowait()
                    q.put_nowait(raw)
                except queue.Empty:
                    pass


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".js": "text/javascript; charset=utf-8",
        ".html": "text/html; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".svg": "image/svg+xml",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        if "/api/" not in (self.path or ""):
            super().log_message(fmt, *args)

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    BLOCKED = {"key.pem", "server.py", "pairing.json", ".env", ".env.example"}           # never hand these out to other devices
    LOCAL_ONLY = {"family.html", "summary.html", "activities.html"}                      # pages that only open on this PC

    # --- who is asking?
    PROXY_HEADERS = ("cf-connecting-ip", "x-forwarded-for", "x-forwarded-host", "x-real-ip", "forwarded", "cf-ray", "cf-visitor")

    def _via_proxy(self):
        """A tunnel (Cloudflare, ngrok...) forwards from this very PC, so loopback alone must not mean "this PC"."""
        return any(self.headers.get(h) for h in self.PROXY_HEADERS)

    def _client_ip(self):
        fwd = (self.headers.get("cf-connecting-ip") or self.headers.get("x-forwarded-for") or "").split(",")[0].strip()
        return fwd or self.client_address[0]

    def _is_local(self):
        return self.client_address[0] in local_ips and not self._via_proxy()

    def _authorized(self, query):
        if self._is_local():
            return True
        token = urllib.parse.parse_qs(query).get("t", [""])[0]
        return bool(token) and any(t["h"] == _hash(token) for t in pairing["tokens"])

    def _is_android(self):
        return "android" in (self.headers.get("User-Agent") or "").lower()

    def _pair(self):
        ip = self._client_ip()
        key = "tunnel" if self._via_proxy() else ip
        count, until = fails.get(key, [0, 0])
        if time.time() < until:
            return self._json(429, {"error": "locked", "wait": int(until - time.time())})
        if self._is_local():
            return self._json(200, {"token": "", "local": True})
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = _json.loads(self.rfile.read(min(n, 2000)).decode() or "{}")
        except ValueError:
            body = {}
        if not (ANY_DEVICE or self._is_android()):
            return self._json(403, {"error": "android-only"})
        with lock:
            # the one paired phone may pair again from the same address (e.g. switching between the http and https page)
            same_phone = any(t.get("ip") == ip for t in pairing["tokens"])
            if len(pairing["tokens"]) >= MAX_REMOTE and not same_phone:
                return self._json(403, {"error": "full"})
            if not secrets.compare_digest(str(body.get("pin", "")), pairing["pin"]):
                count += 1
                fails[key] = [count, 0]
                if count >= 5:
                    fails[key] = [0, time.time() + (300 if key == "tunnel" else 60)]
                return self._json(403, {"error": "wrong-pin"})
            token = secrets.token_urlsafe(24)
            pairing["tokens"] = [t for t in pairing["tokens"] if t.get("ip") != ip]
            pairing["tokens"].append({"h": _hash(token), "ip": ip})
            _save_pairing()
            fails.pop(key, None)
        print(f" ✔ จับคู่โทรศัพท์สำเร็จ ({ip}) ปิดรับเครื่องอื่นแล้ว")
        return self._json(200, {"token": token})

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        if os.path.basename(urllib.parse.unquote(url.path)).lower() in self.BLOCKED:
            return self._json(404, {"error": "not found"})
        # the family app and the health summary are for this PC only; a phone only gets the home screen (the camera side)
        if os.path.basename(urllib.parse.unquote(url.path)).lower() in self.LOCAL_ONLY and not self._is_local():
            body = ("<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
                    "<body style='font-family:sans-serif;padding:28px;line-height:1.6'><h2>หน้านี้เปิดได้เฉพาะในคอมเครื่องที่รันโปรแกรม</h2>"
                    "<p>โทรศัพท์ใช้หน้าจอในบ้านเพื่อส่งภาพกล้องไปให้คอมดู</p><p><a href='/index.html'>เปิดหน้าจอในบ้าน</a></p></body>").encode()
            self.send_response(403)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if url.path == "/api/ping":
            ok = self._authorized(url.query)
            return self._json(200, {"carely": True, "authorized": ok, "local": self._is_local(),
                                    "open": len(pairing["tokens"]) < MAX_REMOTE, "androidOnly": not ANY_DEVICE})
        if url.path == "/api/stream":
            if not self._authorized(url.query):
                return self._json(401, {"error": "pair first"})
            cid = urllib.parse.parse_qs(url.query).get("cid", ["?"])[0]
            return self._stream(cid)
        return super().do_GET()

    def do_POST(self):
        url = urllib.parse.urlparse(self.path)
        if url.path == "/api/pair":
            return self._pair()
        if url.path != "/api/send":
            return self._json(404, {"error": "not found"})
        if not self._authorized(url.query):
            return self._json(401, {"error": "pair first"})
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > 3_000_000:
            return self._json(413, {"error": "bad size"})
        raw = self.rfile.read(n).decode("utf-8", "replace")
        try:
            msg = json.loads(raw)
        except ValueError:
            return self._json(400, {"error": "bad json"})
        # a paired phone speaks only as the home screen; it cannot act as the family app (ack, send games, ...)
        if not self._is_local() and isinstance(msg, dict) and msg.get("_from") != "elder":
            return self._json(403, {"error": "phone is the home screen only"})
        cid = urllib.parse.parse_qs(url.query).get("cid", ["?"])[0]
        if not self._is_local() and cid not in seen_senders:
            seen_senders.add(cid)
            print(f" ~ โทรศัพท์ {self.client_address[0]} เริ่มส่งข้อมูลมาแล้ว")
        broadcast(cid, raw, msg)
        self.send_response(204)
        self.end_headers()

    def _stream(self, cid):
        q = queue.Queue(maxsize=300)
        print(f" ~ เชื่อมต่อสตรีม {self.client_address[0]} ({'คอมนี้' if self._is_local() else 'โทรศัพท์'})")
        with lock:
            clients[cid] = q
            first = last_state
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            if first:
                self.wfile.write(f"data: {first}\n\n".encode())
            self.wfile.flush()
            while True:
                try:
                    raw = q.get(timeout=15)
                    self.wfile.write(f"data: {raw}\n\n".encode())
                except queue.Empty:
                    self.wfile.write(b": ping\n\n")     # keep the connection alive
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError, ssl.SSLError):
            pass
        finally:
            with lock:
                if clients.get(cid) is q:
                    del clients[cid]


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 64


def lan_ips():
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))             # no packet is sent; just picks the Wi-Fi/LAN address
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    return sorted(i for i in ips if not i.startswith(("127.", "169.254.")))


def serve(port, tls):
    srv = Server(("0.0.0.0", port), Handler)
    if tls:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(os.path.join(ROOT, "cert.pem"), os.path.join(ROOT, "key.pem"))
        srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main():
    _load_pairing()
    if "--strict-local" not in sys.argv:            # by default, opening the pages through this PC's own Wi-Fi address still counts as "this PC"
        local_ips.update(lan_ips())
    have_cert = os.path.exists(os.path.join(ROOT, "cert.pem")) and os.path.exists(os.path.join(ROOT, "key.pem"))
    try:
        serve(HTTP_PORT, False)
    except OSError as e:
        print(f"เปิดพอร์ต {HTTP_PORT} ไม่ได้: {e}\n(อาจมีโปรแกรมเซิร์ฟเวอร์เดิมเปิดค้างอยู่ ให้ปิดหน้าต่างเก่าก่อน)")
        sys.exit(1)
    if have_cert:
        try:
            serve(HTTPS_PORT, True)
        except (OSError, ssl.SSLError) as e:
            print(f"เปิด HTTPS ไม่ได้: {e}")
            have_cert = False
    ips = lan_ips()
    print("=" * 62)
    print(" LookLens กำลังทำงาน  (ปิดหน้าต่างนี้เพื่อหยุด)")
    print("=" * 62)
    print(f" บนคอมเครื่องนี้ (เปิดได้เฉพาะที่นี่) :")
    print(f"      แอปลูกหลาน   http://localhost:{HTTP_PORT}/family.html")
    print(f"      สรุป/PDF      http://localhost:{HTTP_PORT}/summary.html")
    for ip in ips:
        print(f" บนโทรศัพท์ = กล้องวงจรปิด :  http://{ip}:{HTTP_PORT}/camera.html")
        if have_cert:
            print(f"      (มือถือเปิดกล้องได้ต้องใช้ https) :  https://{ip}:{HTTPS_PORT}/camera.html")
    print("-" * 62)
    if len(pairing["tokens"]) < MAX_REMOTE:
        print(f" รหัสจับคู่โทรศัพท์แอนดรอย :  {pairing['pin']}   (ใช้ครั้งเดียว ใส่ในหน้าแรกของแอปบนมือถือ)")
    else:
        print(" จับคู่โทรศัพท์แล้ว 1 เครื่อง (เครื่องอื่นเข้าไม่ได้)  ถ้าจะเปลี่ยนมือถือ: py server.py --reset-pairing")
    if ANY_DEVICE:
        print(" * โหมด --any-device: อุปกรณ์ที่ไม่ใช่แอนดรอยก็จับคู่ได้")
    if not have_cert:
        print(" * โทรวิดีโอจากโทรศัพท์ต้องใช้ HTTPS: รัน  make-cert.ps1  หนึ่งครั้ง แล้วเปิดโปรแกรมนี้ใหม่")
    print("=" * 62)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
