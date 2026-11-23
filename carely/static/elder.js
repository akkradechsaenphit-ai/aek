// Carely elder screen: runs on a tablet in the living room.
// Talks (Thai text-to-speech), shows game invitations, runs the games,
// and asks "are you OK?" when the radar thinks there was a fall.

const $ = (s) => document.querySelector(s);
const TH_NUM = ["หนึ่ง", "สอง", "สาม", "สี่", "ห้า", "หก", "เจ็ด", "แปด", "เก้า", "สิบ",
  "สิบเอ็ด", "สิบสอง", "สิบสาม", "สิบสี่", "สิบห้า", "สิบหก", "สิบเจ็ด", "สิบแปด", "สิบเก้า", "ยี่สิบ"];
const CHEER = ["เก่งมากค่ะ", "อีกนิดเดียวค่ะ", "สู้ๆ นะคะ", "ยอดเยี่ยมเลยค่ะ"];

let GAMES = {};
let state = null;
let unlocked = false;
let emergency = null;      // null | "fallcheck" | "alert"
let sosAsk = false;
let offer = null;          // play offered by the server
let playing = null;        // {play, game}
let doneShowing = false;
let abortCtl = null;
let fallVoiceTimer = null;
let wakeLock = null;

// ---------- helpers ----------
const sleep = (ms) => new Promise((resolve, reject) => {
  const t = setTimeout(resolve, ms);
  abortCtl?.signal.addEventListener("abort", () => { clearTimeout(t); reject(new DOMException("stopped", "AbortError")); }, { once: true });
});
const shuffle = (a) => { a = [...a]; for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };
const pick = (a) => a[Math.floor(Math.random() * a.length)];
async function getJSON(url) { const r = await fetch(url); if (!r.ok) throw new Error(r.status); return r.json(); }
async function post(url, body = {}) {
  try { const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }); return r.ok ? r.json() : null; }
  catch { return null; }
}
function esc(s) { return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }

// ---------- voice & sound ----------
let thVoice = null;
function loadVoice() {
  const vs = window.speechSynthesis?.getVoices() || [];
  thVoice = vs.find((v) => v.lang?.toLowerCase().startsWith("th")) || null;
}
if ("speechSynthesis" in window) { loadVoice(); speechSynthesis.onvoiceschanged = loadVoice; }

function say(text, queue = false) {
  if (!unlocked || !text || !("speechSynthesis" in window)) return;
  if (!queue) speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "th-TH";
  if (thVoice) u.voice = thVoice;
  u.rate = 0.9;
  speechSynthesis.speak(u);
}

let audioCtx = null;
function chime(urgent = false) {
  try {
    audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
    const notes = urgent ? [880, 660, 880, 660] : [660, 880];
    notes.forEach((f, i) => {
      const o = audioCtx.createOscillator(), g = audioCtx.createGain();
      o.frequency.value = f; o.type = "sine";
      const t = audioCtx.currentTime + i * 0.22;
      g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.25, t + 0.02); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.2);
      o.connect(g).connect(audioCtx.destination); o.start(t); o.stop(t + 0.22);
    });
  } catch { /* no audio */ }
}

async function keepAwake() {
  try { wakeLock = await navigator.wakeLock?.request("screen"); } catch { /* not supported */ }
}
document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible" && unlocked) keepAwake(); });

// ---------- screens ----------
function render() {
  let id = "home";
  if (!unlocked) id = "splash";
  else if (emergency) id = emergency;
  else if (sosAsk) id = "sosconfirm";
  else if (playing) id = "game";
  else if (doneShowing) id = "done";
  else if (offer) id = "offer";
  document.querySelectorAll(".screen").forEach((s) => { s.hidden = s.id !== id; });
  clearInterval(fallVoiceTimer);
  if (id === "fallcheck") {
    fallVoiceTimer = setInterval(() => say(`${state?.elder_name || ""}คะ เป็นอะไรไหมคะ ถ้าไม่เป็นไร แตะปุ่มสีเขียวนะคะ`), 12000);
  }
}

function greeting() {
  const h = new Date().getHours();
  const part = h < 11 ? "สวัสดีตอนเช้า" : h < 16 ? "สวัสดีตอนบ่าย" : h < 19 ? "สวัสดีตอนเย็น" : "สวัสดีตอนค่ำ";
  return `${part}ค่ะ ${state?.elder_name || ""} 🌷`;
}

function tickClock() {
  const d = new Date();
  $("#clock").textContent = d.toLocaleTimeString("th-TH", { hour: "2-digit", minute: "2-digit" });
  $("#date").textContent = d.toLocaleDateString("th-TH", { weekday: "long", day: "numeric", month: "long" });
  $("#greet").textContent = greeting();
}

function showOffer(play, game) {
  offer = play;
  $("#offerEmoji").textContent = game.emoji;
  $("#offerTitle").textContent = game.title;
  $("#offerSay").textContent = play.say;
  const from = play.source === "family" ? `💌 จาก ${play.sent_by || "ลูกหลาน"}` : (play.source === "elder" ? "" : "✨ Carely เลือกให้");
  $("#offerFrom").textContent = from;
  $("#offerFrom").hidden = !from;
}

function showToast(sender, text) {
  $("#toastFrom").textContent = `ข้อความจาก ${sender}`;
  $("#toastText").textContent = text;
  $("#toast").hidden = false;
  clearTimeout(showToast.t);
  showToast.t = setTimeout(() => { $("#toast").hidden = true; }, 30000);
}

function setAlert(a) {
  const name = state?.elder_name || "";
  $("#alertTitle").textContent = a.status === "acked" ? `${a.acked_by} กำลังมาค่ะ` : "แจ้งลูกหลานแล้วค่ะ";
  $("#alertText").textContent = a.status === "acked"
    ? `${a.acked_by} รับทราบแล้ว อยู่นิ่งๆ รอสักครู่นะคะ${name}`
    : "อยู่นิ่งๆ ก่อนนะคะ เดี๋ยวมีคนมาช่วย";
}

// ---------- server sync ----------
async function sync() {
  try { state = await getJSON("/api/state"); } catch { $("#guard").className = "chip off"; $("#guard").innerHTML = '<span class="dot"></span> เชื่อมต่อไม่ได้'; return; }
  const urgent = state.alerts.filter((a) => a.level === "urgent" && a.status !== "resolved");
  if (urgent.length) { emergency = "alert"; setAlert(urgent[0]); stopGame(); }
  else if (state.fall_check) { emergency = "fallcheck"; stopGame(); }
  else emergency = null;

  const p = state.current_play;
  if (!playing) {
    if (p && p.status === "offered") showOffer(p, GAMES[p.game_id]);
    else offer = null;
  }
  const radars = state.devices.filter((d) => d.online && d.id !== "camera").length;
  const cam = camDevice(state);
  const watching = [radars && `เรดาร์ ${radars} ห้อง`, cam && "กล้อง"].filter(Boolean).join(" + ");
  const g = $("#guard");
  g.className = watching ? "chip" : "chip warn";
  g.innerHTML = `<span class="dot"></span> ${watching ? `ดูแลอยู่: ${watching}` : "เรดาร์และกล้องยังไม่เชื่อมต่อ"}`;
  if (state.last_message) {
    $("#lastMsg").hidden = false;
    $("#lastMsgFrom").textContent = `ข้อความล่าสุดจาก ${state.last_message.sender}`;
    $("#lastMsgText").textContent = state.last_message.text;
  }
  render();
}

function listen() {
  const es = new EventSource("/api/stream");
  es.onmessage = (e) => {
    const m = JSON.parse(e.data);
    switch (m.type) {
      case "fall_check":
        stopGame(); emergency = "fallcheck"; render(); chime(true); say(m.say); break;
      case "fall_clear":
        if (m.say) say(m.say);
        sync(); break;
      case "alert":
        if (m.alert.level === "urgent") { stopGame(); emergency = "alert"; setAlert(m.alert); render(); chime(true); say(m.say); }
        break;
      case "alert_ack":
        setAlert(m.alert); say(m.say); sync(); break;
      case "alert_resolved":
        sync(); break;
      case "game_offer":
        if (playing || emergency) break;
        showOffer(m.play, m.game); render(); chime(); say(m.say); break;
      case "rep":
        repWaiters.forEach((w) => w(m.move)); break;
      case "family_message":
        showToast(m.sender, m.text); chime(); say(m.say); sync(); break;
    }
  };
}

// ---------- games ----------
async function startGame(play) {
  const game = GAMES[play.game_id];
  offer = null; playing = { play, game }; abortCtl = new AbortController();
  $("#toast").hidden = true;
  $("#gameTitle").textContent = `${game.emoji} ${game.title}`;
  render();
  post("/api/elder/play", { play_id: play.id, status: "playing" });
  try {
    const score = await runSteps(game.steps);
    await post("/api/elder/play", { play_id: play.id, status: "done", score });
    playing = null;
    showDone(game, score);
  } catch (e) {
    if (e.name !== "AbortError") console.error(e);
    post("/api/elder/play", { play_id: play.id, status: "skipped" });
    playing = null; speechSynthesis?.cancel(); render();
  }
}

function stopGame() { if (playing) abortCtl?.abort(); }

function waitClick(btn) {
  return new Promise((resolve, reject) => {
    btn.onclick = () => resolve();
    abortCtl.signal.addEventListener("abort", () => reject(new DOMException("stopped", "AbortError")), { once: true });
  });
}

// ---------- camera (camera.html sends arm raises / claps and movement) ----------
const repWaiters = new Set();
const REP_HINT = { arms_up: "ยกแขนสองข้างให้สูงกว่าศีรษะนะคะ", clap: "ปรบมือให้มือสองข้างแตะกันนะคะ" };
const camDevice = (s) => s?.devices.find((d) => d.id === "camera" && d.online);

function waitRep(move, ms) {
  return new Promise((resolve, reject) => {
    const w = (m) => { if (m === move) done(true); };
    const t = setTimeout(() => done(false), ms);
    const stop = () => { clearTimeout(t); repWaiters.delete(w); reject(new DOMException("stopped", "AbortError")); };
    function done(seen) { clearTimeout(t); repWaiters.delete(w); abortCtl.signal.removeEventListener("abort", stop); resolve(seen); }
    repWaiters.add(w);
    abortCtl.signal.addEventListener("abort", stop, { once: true });
  });
}

async function sensorMoving() {
  try {
    const s = await getJSON("/api/state");
    const cam = camDevice(s);
    return cam ? cam.moving : s.moving;
  } catch { return true; }
}

async function runSteps(steps) {
  const body = $("#gameBody");
  body.innerHTML = `<div class="step-emoji" id="stEmoji"></div><p class="lead" id="stSay"></p>
    <div class="counter" id="stCount"></div><div class="bar"><i id="stBar"></i></div>
    <div class="motion-hint" id="stHint"></div><button class="big-btn primary" id="stConfirm" hidden></button>`;
  const emoji = $("#stEmoji"), text = $("#stSay"), count = $("#stCount"), bar = $("#stBar"), hint = $("#stHint"), btn = $("#stConfirm");
  const pop = () => { emoji.classList.add("pop"); setTimeout(() => emoji.classList.remove("pop"), 180); };
  const parts = [];  // share of each checked step that was really done (camera reps, movement seconds)
  for (const step of steps) {
    emoji.textContent = step.emoji; text.textContent = step.say; count.textContent = ""; hint.textContent = "";
    bar.style.width = "0"; btn.hidden = true; pop();
    say(step.say);
    await sleep(2200);
    if (step.reps && step.detect && camDevice(state)) {
      let got = 0;
      const deadline = Date.now() + step.reps * step.beat * 3000;
      count.textContent = `0 / ${step.reps}`;
      hint.textContent = "📷 กล้องกำลังนับให้ค่ะ"; hint.className = "motion-hint ok";
      while (got < step.reps && Date.now() < deadline) {
        if (await waitRep(step.detect, Math.min(12000, deadline - Date.now()))) {
          got++;
          count.textContent = `${got} / ${step.reps}`;
          bar.style.width = `${(100 * got) / step.reps}%`;
          hint.textContent = "📷 เห็นแล้วค่ะ เยี่ยมเลย"; hint.className = "motion-hint ok";
          pop(); say(TH_NUM[got - 1] || String(got), true);
        } else {
          hint.textContent = REP_HINT[step.detect]; hint.className = "motion-hint";
          say(REP_HINT[step.detect], true);
        }
      }
      parts.push(got / step.reps);
    } else if (step.reps) {
      for (let r = 1; r <= step.reps; r++) {
        count.textContent = `${r} / ${step.reps}`;
        bar.style.width = `${(100 * r) / step.reps}%`;
        pop(); say(TH_NUM[r - 1] || String(r), true);
        await sleep(step.beat * 1000);
      }
    } else if (step.confirm) {
      btn.textContent = step.confirm; btn.hidden = false;
      await waitClick(btn);
      btn.hidden = true;
    } else if (step.motion) {
      const sensorOn = state?.devices.some((d) => d.online);
      let got = 0, elapsed = 0;
      while (got < step.seconds && elapsed < step.seconds * 2.5) {
        await sleep(1000); elapsed++;
        const moving = sensorOn ? await sensorMoving() : true;
        if (moving) { got++; hint.textContent = "เยี่ยมเลย กำลังขยับ 💪"; hint.className = "motion-hint ok"; }
        else { hint.textContent = "ขยับอีกนิดนะคะ ยังไม่เห็นการขยับ"; hint.className = "motion-hint"; }
        bar.style.width = `${(100 * got) / step.seconds}%`;
        count.textContent = `${Math.max(0, step.seconds - got)} วินาที`;
        if (elapsed % 12 === 0) say(pick(CHEER), true);
      }
      parts.push(got / elapsed);
    } else if (step.seconds) {
      for (let s = step.seconds; s > 0; s--) {
        count.textContent = s; bar.style.width = `${(100 * (step.seconds - s + 1)) / step.seconds}%`;
        await sleep(1000);
      }
    }
  }
  return parts.length ? Math.round((100 * parts.reduce((a, b) => a + b, 0)) / parts.length) : null;
}

function showDone(game, score) {
  doneShowing = true;
  let text = "ได้ขยับร่างกายแล้ว สดชื่นขึ้นเยอะเลย";
  let stars = "";
  if (score != null) { text = `ทำท่าได้ ${score}% ของที่ตั้งไว้`; stars = "⭐".repeat(Math.max(1, Math.round(score / 20))); }
  $("#doneTitle").textContent = "เก่งมากค่ะ";
  $("#doneText").textContent = text;
  $("#doneStars").textContent = stars;
  render(); chime();
  say(`เก่งมากค่ะ ${text} อย่าลืมดื่มน้ำด้วยนะคะ`);
  setTimeout(() => { doneShowing = false; render(); }, 7000);
}

// ---------- buttons ----------
$("#splash").onclick = () => {
  unlocked = true; loadVoice(); keepAwake(); chime();
  say(`สวัสดีค่ะ ${state?.elder_name || ""} Carely พร้อมดูแลแล้วค่ะ`);
  render();
};
$("#wantGame").onclick = async () => {
  const b = $("#wantGame"); b.disabled = true; b.innerHTML = '<span class="ic">⏳</span> กำลังเลือกเกม…';
  const play = await post("/api/elder/want-game");
  b.disabled = false; b.innerHTML = '<span class="ic">🎮</span> อยากเล่นเกม';
  if (play && play.game_id && !playing) { showOffer(play, GAMES[play.game_id]); render(); say(play.say); }
};
$("#offerYes").onclick = () => { if (offer) startGame(offer); };
$("#offerLater").onclick = () => {
  if (offer) post("/api/elder/play", { play_id: offer.id, status: "skipped" });
  offer = null; say("ได้ค่ะ ไว้เล่นกันทีหลังนะคะ"); render();
};
$("#gameStop").onclick = () => { stopGame(); say("ไม่เป็นไรค่ะ พักก่อนนะคะ"); };
$("#sosBtn").onclick = () => { sosAsk = true; render(); say("ต้องการเรียกลูกหลานใช่ไหมคะ"); };
$("#sosNo").onclick = () => { sosAsk = false; render(); };
$("#sosYes").onclick = async () => {
  sosAsk = false;
  const r = await post("/api/elder/sos");
  if (r?.alert) { emergency = "alert"; setAlert(r.alert); render(); }
  say("ส่งแจ้งเตือนถึงลูกหลานแล้วค่ะ รอสักครู่นะคะ");
  sync();
};
document.querySelectorAll("[data-ok]").forEach((b) => {
  b.onclick = async () => {
    b.disabled = true;
    await post("/api/elder/ok");
    b.disabled = false; emergency = null; render();
    say("ดีใจที่ไม่เป็นอะไรค่ะ ระบบบอกลูกหลานให้แล้วนะคะ");
    sync();
  };
});
$("#toastClose").onclick = () => { $("#toast").hidden = true; };

// ---------- start ----------
(async function init() {
  try {
    const data = await getJSON("/api/games");
    data.games.forEach((g) => { GAMES[g.id] = g; });
  } catch (e) { console.error(e); }
  tickClock(); setInterval(tickClock, 1000);
  await sync(); setInterval(sync, 5000);
  listen();
  render();
})();
