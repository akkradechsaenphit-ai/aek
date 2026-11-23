// Carely family dashboard: live status, alerts, game mode, messages, radar view and simulator.

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const hhmm = (ts) => new Date(ts * 1000).toLocaleTimeString("th-TH", { hour: "2-digit", minute: "2-digit" });
const POSTURE_TH = { standing: "ยืน / เดิน", sitting: "นั่ง", lying: "นอน", floor: "อยู่บนพื้น", unknown: "—" };
let GAMES = {};
let state = null;
let simRoom = "living";

async function getJSON(url) { const r = await fetch(url); if (!r.ok) throw new Error(r.status); return r.json(); }
async function post(url, body = {}) {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  return r.ok ? r.json() : null;
}
function toast(text) {
  const t = $("#toast"); t.textContent = text; t.hidden = false;
  clearTimeout(toast.t); toast.t = setTimeout(() => { t.hidden = true; }, 3500);
}

// ---------- status ----------
function renderState(s) {
  state = s;
  $("#chips").innerHTML = [
    bellReady() ? '<span class="chip"><span class="dot"></span> 🔔 เสียงแจ้งเตือนเปิดอยู่</span>'
      : '<button class="chip warn" data-bell>🔕 กดเพื่อเปิดเสียงแจ้งเตือน</button>',
    s.ai === "claude" ? '<span class="chip">✨ AI: Claude</span>' : '<span class="chip off">AI: กฎพื้นฐาน</span>',
    s.demo ? '<span class="chip warn">โหมดสาธิต (เวลาสั้น)</span>' : "",
    s.devices.some((d) => d.id === "camera" && d.online)
      ? '<a class="chip" href="/camera" style="text-decoration:none"><span class="dot"></span> 📷 กล้องทำงาน</a>'
      : '<a class="chip off" href="/camera" style="text-decoration:none">📷 เปิดหน้ากล้อง</a>',
  ].join("");
  const h = new Date().getHours();
  $("#hello").textContent = `${h < 11 ? "สวัสดีตอนเช้า" : h < 16 ? "สวัสดีตอนบ่าย" : "สวัสดีตอนเย็น"} 🌷`;
  $("#sub").textContent = `มาดูกันว่าวันนี้${s.elder_name}เป็นอย่างไรบ้าง`;
  $("#elderName").textContent = s.elder_name;
  $("#where").textContent = s.where ? `📍 อยู่ที่${s.where}${s.moving ? " · กำลังขยับ" : ""}` : "📍 ไม่พบในบ้าน (อาจออกไปข้างนอก หรืออยู่ห้องที่ไม่มีเรดาร์)";
  $("#posture").textContent = s.where ? s.posture_th : "—";
  $("#postureFor").textContent = s.posture_minutes ? `ต่อเนื่อง ${s.posture_minutes} นาที` : "";

  const resting = ["sitting", "lying"].includes(s.posture) && s.where;
  $("#rest").hidden = !resting;
  if (resting) {
    const limit = s.posture === "lying" ? s.limits.lie_s : s.limits.sit_s;
    const pct = Math.min(100, (100 * s.resting_seconds) / limit);
    $("#restBar").style.width = `${pct}%`;
    $("#restBar").className = pct > 80 ? "near" : "";
    const left = Math.max(0, Math.ceil((limit - s.resting_seconds) / 60));
    $("#restText").textContent = pct >= 100 ? "ถึงเวลาแล้ว ระบบชวนลุกขึ้นเล่นเกม"
      : `อีกประมาณ ${left} นาที ระบบจะพูดชวนลุกขึ้นเล่นเกม (ตั้งไว้ ${Math.round(limit / 60)} นาที)`;
  }

  $("#sGames").textContent = s.games_today;
  $("#sBath").textContent = s.bathroom_today;
  $("#sAlerts").textContent = s.open_alerts;
  $("#sSensors").textContent = s.devices.filter((d) => d.online).length;

  renderAlerts(s);
  renderPlay(s);
  renderDevices(s);
  renderSim(s.sim);
  renderSos(s);
}

function renderAlerts(s) {
  let checking = "";
  if (s.fall_check && !s.alerts.some((a) => a.kind === "fall" && a.status !== "resolved")) {
    const left = Math.max(0, Math.ceil(s.limits.fall_confirm_s - (s.now - s.fall_check.ts)));
    checking = `<div class="alert checking"><div class="big">⏳</div>
      <div><h3>อาจล้ม · ${esc(s.fall_check.room)}</h3>
        <p>กำลังถาม${esc(s.elder_name)}ที่จอในบ้านว่าเป็นอะไรไหม ถ้าไม่มีคำตอบใน ${left} วินาทีจะแจ้งเตือนด่วน</p></div></div>`;
  }
  $("#alerts").innerHTML = checking + s.alerts.map((a) => {
    const acked = a.status === "acked";
    const call = s.elder_phone ? `<a href="tel:${esc(s.elder_phone)}">📞 โทรหา${esc(s.elder_name)}</a>` : "";
    return `<div class="alert ${acked ? "acked" : a.level}">
      <div class="big">${a.level === "urgent" ? "🚨" : "⚠️"}</div>
      <div><h3>${esc(a.title)} · ${esc(a.room)}</h3>
        <p>${hhmm(a.ts)} น. — ${esc(a.detail)}${acked ? ` · 👍 ${esc(a.acked_by)} รับทราบแล้ว` : a.sends > 1 ? ` · แจ้งซ้ำแล้ว ${a.sends} ครั้ง` : ""}</p></div>
      <div class="acts">${acked ? "" : `<button data-ack="${a.id}">🚗 ฉันกำลังไป</button>`}${call}</div>
    </div>`;
  }).join("");
}

function renderPlay(s) {
  const p = s.current_play, el = $("#nowPlaying");
  if (!p) { el.hidden = true; return; }
  const g = GAMES[p.game_id] || { emoji: "🎮", title: p.game_id };
  const who = p.source === "family" ? `${p.sent_by} ส่งมา` : p.source === "ai" ? "AI เลือกให้" : "เลือกตามกฎ";
  el.hidden = false;
  el.innerHTML = `${g.emoji} <b>${esc(g.title)}</b> · ${esc(who)} · ${p.status === "playing" ? "▶️ กำลังเล่นอยู่" : "⏳ รอตอบรับที่หน้าจอ"}
    ${p.say ? `<br><small>“${esc(p.say)}”</small>` : ""}${p.reason ? `<br><small style="color:var(--muted)">เหตุผล: ${esc(p.reason)}</small>` : ""}`;
}

function spark(history) {
  const w = 120, h = 46, pts = history.filter(([, v]) => v != null);
  const y = (v) => h - 2 - (Math.min(180, v) / 180) * (h - 4);
  const lines = [[130, "#c9d6c9"], [85, "#e8d9b9"], [45, "#efc6c2"]]
    .map(([v, c]) => `<line x1="0" x2="${w}" y1="${y(v)}" y2="${y(v)}" stroke="${c}" stroke-dasharray="3 3"/>`).join("");
  if (pts.length < 2) return `<svg viewBox="0 0 ${w} ${h}" aria-hidden="true">${lines}</svg>`;
  const t0 = pts[0][0], t1 = pts[pts.length - 1][0] || t0 + 1;
  const path = pts.map(([t, v], i) => `${i ? "L" : "M"}${(((t - t0) / Math.max(1, t1 - t0)) * w).toFixed(1)},${y(v).toFixed(1)}`).join("");
  return `<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="กราฟความสูงลำตัว">${lines}<path d="${path}" fill="none" stroke="#718b72" stroke-width="2"/></svg>`;
}

function renderDevices(s) {
  $("#devices").innerHTML = s.devices.map((d) => {
    const chip = !d.online ? '<span class="chip off">ออฟไลน์</span>'
      : d.fall_state !== "NORMAL" ? '<span class="chip bad">ตรวจพบการล้ม</span>'
      : d.presence ? '<span class="chip">มีคนอยู่</span>' : '<span class="chip off">ว่าง</span>';
    const info = d.online && d.presence
      ? `${POSTURE_TH[d.posture]} · สูง ${d.height ?? "?"} ซม. · ขยับ ${d.moving_energy} · นิ่ง ${d.still_energy}${d.bathroom_inside_s != null ? ` · อยู่ใน ${Math.round(d.bathroom_inside_s / 60)} นาที` : ""}`
      : d.online ? "ไม่มีคนในห้อง" : "ยังไม่ได้รับข้อมูล";
    return `<div class="dev"><div class="name">${esc(d.name)} ${chip}</div>${spark(d.history)}<div class="info">${esc(info)}</div></div>`;
  }).join("");
}

function renderSim(sim) {
  const rooms = state.devices.filter((d) => d.id !== "camera").map((d) => [d.id, d.name]);
  $("#simRooms").innerHTML = rooms.map(([id, name]) => `<button data-room="${id}" class="${id === simRoom ? "on" : ""}">${esc(name)}</button>`).join("");
  $("#simState").textContent = sim.running
    ? `ทำงาน · ${sim.room ? (rooms.find((r) => r[0] === sim.room) || [, sim.room])[1] : "ไม่อยู่ในห้องใด"} · ${{ walk: "เดิน", stand: "ยืน", sit: "นั่ง", lie: "นอน", fall: "ล้มอยู่บนพื้น" }[sim.pose] || sim.pose}${sim.moving ? " (ขยับ)" : " (นิ่ง)"}`
    : "ปิดอยู่";
}

// ---------- urgent alerts: full-screen window, alarm sound, desktop notification ----------
let audioCtx = null, alarmTimer = null;
const hiddenAlerts = new Set();  // alerts this viewer chose to hide (still open for everyone else)
const notified = new Set();
let shownAlert = null;

const bellReady = () => audioCtx?.state === "running";
async function enableBell() {
  try {
    audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
    await audioCtx.resume();
  } catch { /* no audio on this device */ }
  if ("Notification" in window && Notification.permission === "default") {
    try { await Notification.requestPermission(); } catch { /* ignored */ }
  }
  renderBell();
  if (state) renderState(state);
}
function beep() {
  if (!bellReady()) return;
  [988, 740, 988, 740].forEach((f, i) => {
    const o = audioCtx.createOscillator(), g = audioCtx.createGain();
    o.type = "square"; o.frequency.value = f; g.gain.value = 0.12;
    o.connect(g); g.connect(audioCtx.destination);
    const t = audioCtx.currentTime + i * 0.24;
    o.start(t); o.stop(t + 0.2);
  });
}
function renderBell() {
  const notif = !("Notification" in window) ? "ป๊อปอัป: เบราว์เซอร์นี้ไม่รองรับ"
    : Notification.permission === "granted" ? "ป๊อปอัป: เปิดแล้ว"
    : Notification.permission === "denied" ? "ป๊อปอัป: ถูกปิดไว้ในเบราว์เซอร์" : "ป๊อปอัป: ยังไม่เปิด";
  $("#bellState").textContent = `${bellReady() ? "🔔 เสียง: เปิดแล้ว" : "🔕 เสียง: ยังไม่เปิด"} · ${notif}`;
  $("#bellBtn").hidden = bellReady() && (!("Notification" in window) || Notification.permission !== "default");
}

function notify(s, a) {
  if (notified.has(a.id)) return;
  notified.add(a.id);
  if (!("Notification" in window) || Notification.permission !== "granted") return;
  try {
    const n = new Notification(`🚨 ${a.title}`, {
      body: `${s.elder_name} · ${a.room} · ${hhmm(a.ts)} น.\n${a.detail}`,
      tag: `carely-alert-${a.id}`, requireInteraction: true,
    });
    n.onclick = () => { window.focus(); n.close(); };
  } catch { /* some browsers only allow notifications from a service worker */ }
}

function renderSos(s) {
  const open = s.alerts.filter((a) => a.level === "urgent" && a.status === "open");
  open.forEach((a) => notify(s, a));
  const a = open.find((x) => !hiddenAlerts.has(x.id));
  document.title = open.length ? `🚨 ${open[0].title} · Carely` : "Carely ลูกหลาน";
  $("#sos").hidden = !a;
  shownAlert = a || null;
  if (a) {
    $("#sosTitle").textContent = a.kind === "sos" ? `${s.elder_name}ขอความช่วยเหลือ` : a.title;
    $("#sosWhere").textContent = `👵 ${s.elder_name} · 📍 ${a.room} · 🕐 ${hhmm(a.ts)} น.`;
    $("#sosDetail").textContent = a.detail;
    $("#sosCall").hidden = !s.elder_phone;
    $("#sosCall").href = s.elder_phone ? `tel:${s.elder_phone}` : "#";
    $("#sosCall").textContent = `📞 โทรหา${s.elder_name}${s.elder_phone ? ` (${s.elder_phone})` : ""}`;
    if (!alarmTimer) { beep(); alarmTimer = setInterval(beep, 2500); }
  } else if (alarmTimer) { clearInterval(alarmTimer); alarmTimer = null; }
}

$("#sosGo").onclick = async () => {
  if (!shownAlert) return;
  $("#sosGo").disabled = true;
  await post(`/api/alerts/${shownAlert.id}/ack`, { by: $("#sender").value || "ลูกหลาน" });
  $("#sosGo").disabled = false;
  toast("แจ้งที่บ้านแล้วว่าคุณกำลังไป");
  tick(); refreshLists();
};
$("#sosHide").onclick = () => { if (shownAlert) hiddenAlerts.add(shownAlert.id); renderSos(state); };
$("#bellBtn").onclick = enableBell;
$("#bellTest").onclick = async () => { if (!bellReady()) await enableBell(); beep(); };

// ---------- timeline ----------
const EVENT = {
  posture: (e) => [`เปลี่ยนท่า: ${POSTURE_TH[e.meta.posture] || e.meta.posture}`, ""],
  fall_suspected: () => ["⚠️ อาจล้ม กำลังรอดูว่าลุกขึ้นได้ไหม", "bad"],
  fall: () => ["🚨 ล้มและยังไม่ลุก — แจ้งเตือนลูกหลานแล้ว", "bad"],
  fall_recovered: (e) => [e.meta.by === "elder" ? "✅ กด “ฉันไม่เป็นไร” ก่อนแจ้งเตือน" : "✅ ลุกขึ้นได้เอง ไม่ต้องแจ้งเตือน", "good"],
  fall_resolved: (e) => [e.meta.by === "elder" ? "✅ กด “ฉันไม่เป็นไร” หลังแจ้งเตือน" : "✅ ลุกขึ้นได้แล้ว", "good"],
  bathroom_visit: (e) => [`🚻 เข้าห้องน้ำ ${Math.max(1, Math.round(e.value / 60))} นาที`, ""],
  bathroom_still: () => ["🚨 อยู่ในห้องน้ำนิ่งผิดปกติ", "bad"],
  bathroom_long: () => ["⚠️ อยู่ในห้องน้ำนาน", "bad"],
  bathroom_ok: () => ["✅ ห้องน้ำ: กลับมาปกติ", "good"],
  nudge: (e) => [`⏰ ${e.meta.reason === "lying" ? "นอน" : "นั่ง"}นาน ${Math.round(e.value / 60)} นาที — ชวนลุกเล่นเกม`, ""],
  game_offer: (e) => [`🎮 ชวนเล่น ${GAMES[e.meta.game]?.title || e.meta.game} (${e.meta.sent_by ? `${e.meta.sent_by} ส่งมา` : e.meta.by === "ai" ? "AI เลือก" : e.meta.by === "rules" ? "เลือกตามกฎ" : e.meta.by})`, ""],
  game_done: (e) => [`🎉 เล่น${GAMES[e.meta.game]?.title || ""}จบแล้ว${e.value != null ? ` (คะแนน ${e.value})` : ""}`, "good"],
  game_skipped: (e) => [`🙂 ไม่ได้เล่น${GAMES[e.meta.game]?.title || ""}`, ""],
  alert_sent: (e) => [e.meta.kind === "sos" ? "🆘 กดปุ่มขอความช่วยเหลือ — แจ้งเตือนลูกหลานแล้ว" : "🔔 แจ้งเตือนลูกหลานแล้ว", "bad"],
  alert_ack: (e) => [`👍 ${e.meta.by} รับทราบ กำลังไป`, "good"],
  family_message: (e) => [`💌 ${e.meta.sender}: ${e.meta.text}`, ""],
  family_join: (e) => [`👪 ${e.meta.name} ลงทะเบียนรับแจ้งเตือน`, "good"],
};

async function refreshLists() {
  try {
    const events = await getJSON("/api/events?limit=80");
    const rows = events.map((e) => {
      const f = EVENT[e.kind]; if (!f) return "";
      const [text, cls] = f(e);
      return `<div class="ev ${cls}"><time>${hhmm(e.ts)}</time><div>${esc(text)}${e.room && e.kind !== "game_offer" ? ` <span style="color:var(--muted)">· ${esc(e.room)}</span>` : ""}</div></div>`;
    }).join("");
    $("#timeline").innerHTML = rows || '<div class="empty">ยังไม่มีเหตุการณ์</div>';
  } catch { /* server restarting */ }
}

// ---------- actions ----------
document.addEventListener("click", async (e) => {
  if (e.target.closest("[data-bell]")) { enableBell(); return; }
  const ack = e.target.closest("[data-ack]");
  if (ack) { ack.disabled = true; await post(`/api/alerts/${ack.dataset.ack}/ack`, { by: $("#sender").value || "ลูกหลาน" }); tick(); return; }
  const room = e.target.closest("[data-room]");
  if (room) { simRoom = room.dataset.room; renderSim(state.sim); return; }
  const sim = e.target.closest("[data-sim]");
  if (sim) { await post("/api/sim", { action: sim.dataset.sim, room: sim.dataset.sim === "enter" ? simRoom : null }); tick(); return; }
  const game = e.target.closest("[data-game]");
  if (game) {
    const r = await post("/api/family/game", { game_id: game.dataset.game, sender: $("#sender").value || "ลูกหลาน" });
    toast(r?.error === "busy" ? "กำลังเล่นเกมอื่นอยู่ ลองใหม่อีกสักครู่" : `ส่งเกม ${GAMES[game.dataset.game].title} ไปที่บ้านแล้ว`);
    tick();
  }
});

$("#aiPick").onclick = async () => {
  const b = $("#aiPick"); b.disabled = true; b.textContent = "⏳ กำลังเลือก…";
  const r = await post("/api/family/game", {});
  b.disabled = false; b.textContent = "✨ ให้ AI เลือกเกม";
  if (r?.error === "busy") toast("กำลังเล่นเกมอื่นอยู่");
  else if (r) toast(`${r.by === "ai" ? "AI" : "ระบบ"} เลือก “${GAMES[r.game_id].title}” แล้ว`);
  tick();
};

$("#msgForm").onsubmit = async (e) => {
  e.preventDefault();
  const text = $("#msgText").value.trim();
  if (!text) return;
  await post("/api/family/message", { text, sender: $("#sender").value || "ลูกหลาน" });
  $("#msgText").value = "";
  toast("ส่งข้อความแล้ว จะอ่านออกเสียงที่บ้าน");
  refreshLists();
};

// ---------- start ----------
async function tick() { try { renderState(await getJSON("/api/state")); } catch { $("#where").textContent = "เชื่อมต่อเซิร์ฟเวอร์ไม่ได้"; } }

(async function init() {
  const data = await getJSON("/api/games");
  data.games.forEach((g) => { GAMES[g.id] = g; });
  $("#games").innerHTML = data.games.map((g) => `<div class="game"><div class="e">${g.emoji}</div><strong>${esc(g.title)}</strong>
    <p>${esc(g.desc)}</p><div class="meta">${g.kind === "move" ? "🏃 ขยับร่างกาย" : "🧠 ฝึกสมอง"} · ${g.minutes} นาที${g.knee_safe ? "" : " · ⚠️ ไม่เหมาะกับคนปวดเข่า"}</div>
    <button data-game="${g.id}">ส่งเกมนี้</button></div>`).join("");
  renderBell();
  await tick(); refreshLists();
  setInterval(tick, 1000); setInterval(refreshLists, 2000);
  const es = new EventSource("/api/stream");
  es.onmessage = (e) => {
    const m = JSON.parse(e.data);
    if (m.type === "alert") toast(`🚨 ${m.alert.title} · ${m.alert.room}`);
    if (m.type === "fall_check") toast(`⏳ อาจล้มที่${m.room} กำลังถามที่จอในบ้าน`);
    tick(); refreshLists();
  };
})();
