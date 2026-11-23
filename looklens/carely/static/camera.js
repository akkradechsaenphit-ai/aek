// Carely camera: pose estimation in the browser, nothing but derived values leave the page.
//
// Every frame: PoseNet finds ~17 body keypoints, the Teachable Machine model
// (my-pose-model: นอน นั่ง ลุก เดิน ล้ม) classifies the pose, and simple keypoint
// rules count arm raises and claps. Once a second the page sends Carely
// {presence, moving_energy, posture, fall}; each counted move is sent as a rep.

const $ = (s) => document.querySelector(s);

// --- tuning --------------------------------------------------------------------
const SIZE = 360;              // square crop the model sees (px)
const KP_MIN = 0.4;            // keypoint score to trust a point
const MIN_POINTS = 6;          // fewer trusted points than this = nobody in view
const LABEL_MIN = 0.5;         // model probability to count a frame's label
const ENERGY_FLOOR = 0.012;    // per-frame keypoint jitter (fraction of torso length) treated as stillness
const ENERGY_FULL = 0.05;      // per-frame movement that reads as 100
const FALL_SECONDS = 2;        // "ล้ม" must win this many seconds in a row before we flag a fall
const CLAP_TOGETHER = 0.35;    // wrist gap / shoulder width
const CLAP_APART = 0.7;

const LABEL_POSTURE = { "นอน": "lying", "นั่ง": "sitting", "ลุก": "standing", "เดิน": "standing", "ล้ม": "floor" };
const POSTURE_TH = { standing: "ยืน / เดิน", sitting: "นั่ง", lying: "นอน", floor: "อยู่บนพื้น" };

// --- state ---------------------------------------------------------------------
const view = $("#view"), ctx = view.getContext("2d");
let model = null, stream = null, video = null, running = false, frameReq = null, secondTimer = null;
let session = newSession();
let acc = newAcc();
let recent = [];               // [{t, label, prob}] for the last second
let prevKp = null;
let posture = null, postureConf = 0, fallStreak = 0;
let armState = "down", clapState = "apart", lastClap = 0;

function newSession() { return { startedAt: null, rows: [], reps: [] }; }
function newAcc() { return { frames: 0, present: 0, energySum: 0, energyN: 0, arms: 0, claps: 0 }; }

const dist = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
const mid = (a, b) => ({ x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 });
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
const mmss = (s) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;

function setStatus(text, cls = "") {
  const el = $("#status");
  el.textContent = `สถานะ: ${text}`;
  el.className = `status ${cls}`;
}

function setLink(ok) {
  const chip = $("#linkChip");
  if (!$("#sendToCarely").checked || !running) { chip.className = "chip off"; chip.innerHTML = '<span class="dot"></span> ยังไม่ส่งข้อมูล'; return; }
  chip.className = ok ? "chip" : "chip bad";
  chip.innerHTML = `<span class="dot"></span> ${ok ? "ส่งเข้า Carely อยู่" : "ส่งเข้า Carely ไม่ได้"}`;
}

async function send(url, body) {
  if (!$("#sendToCarely").checked) return;
  try {
    const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    setLink(r.ok);
  } catch { setLink(false); }
}

// --- camera on / off --------------------------------------------------------------
async function start() {
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
    setStatus("เบราว์เซอร์ไม่อนุญาตให้ใช้กล้องในหน้านี้ ต้องเปิดผ่าน localhost หรือ HTTPS", "bad");
    return;
  }
  $("#startBtn").disabled = true;
  try {
    if (!model) {
      if (!window.tmPose) throw Object.assign(new Error("lib"), { name: "LibraryError" });
      setStatus("กำลังโหลดโมเดลท่าทาง…");
      model = await tmPose.load("/static/model/model.json", "/static/model/metadata.json");
    }
    setStatus("กำลังขอสิทธิ์ใช้กล้อง…");
    const pick = $("#cameraPick").value;
    stream = await navigator.mediaDevices.getUserMedia({
      audio: false,
      video: pick ? { deviceId: { exact: pick } } : { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" },
    });
    video = document.createElement("video");  // never attached to the page; frames are drawn and dropped
    video.muted = true; video.playsInline = true; video.srcObject = stream;
    await video.play();
    await listCameras();
  } catch (e) {
    stopTracks();
    $("#startBtn").disabled = !$("#agree").checked;
    const msg = {
      NotAllowedError: "ไม่ได้รับอนุญาตให้ใช้กล้อง ถ้าต้องการลองใหม่ ให้อนุญาตกล้องในการตั้งค่าเบราว์เซอร์แล้วกด \"เปิดกล้อง\" อีกครั้ง",
      NotFoundError: "ไม่พบกล้องในเครื่องนี้",
      OverconstrainedError: "ไม่พบกล้องที่เลือก ลองเลือกกล้องตัวอื่น",
      NotReadableError: "กล้องถูกใช้งานโดยโปรแกรมอื่นอยู่ ปิดโปรแกรมนั้นแล้วลองใหม่",
      LibraryError: "โหลดไลบรารีโมเดลไม่ได้ ตรวจการเชื่อมต่ออินเทอร์เน็ตแล้วโหลดหน้าใหม่",
    }[e.name] || `เปิดกล้องไม่สำเร็จ (${e.name || e.message})`;
    setStatus(msg, "bad");
    return;
  }

  running = true;
  if (!session.startedAt) session.startedAt = new Date();
  acc = newAcc(); recent = []; prevKp = null; fallStreak = 0; posture = null;
  $("#placeholder").hidden = true; $("#live").hidden = false; $("#poseTag").hidden = false;
  $("#startBtn").hidden = true; $("#stopBtn").hidden = false;
  setStatus("กล้องทำงาน กำลังประมวลผลในเครื่องนี้", "ok");
  setLink(true);
  secondTimer = setInterval(everySecond, 1000);
  frameReq = requestAnimationFrame(loop);
}

function stopTracks() {
  stream?.getTracks().forEach((t) => t.stop());
  stream = null;
  if (video) { video.srcObject = null; video = null; }
}

function stop() {
  if (!running) return;
  running = false;
  cancelAnimationFrame(frameReq);
  clearInterval(secondTimer);
  stopTracks();
  send("/api/camera", { presence: false, moving_energy: 0 });  // tell Carely the camera no longer knows
  ctx.clearRect(0, 0, SIZE, SIZE);
  $("#placeholder").hidden = false; $("#placeholder").innerHTML = "กล้องปิดแล้ว<br>กด \"เปิดกล้อง\" เพื่อเริ่มใหม่";
  $("#live").hidden = true; $("#poseTag").hidden = true;
  $("#stopBtn").hidden = true; $("#startBtn").hidden = false; $("#startBtn").disabled = !$("#agree").checked;
  setStatus("หยุดกล้องแล้ว ปิดการใช้กล้องเรียบร้อย");
  setLink(false);
}

async function listCameras() {
  const cams = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === "videoinput");
  const sel = $("#cameraPick");
  const current = stream?.getVideoTracks()[0]?.getSettings().deviceId;
  sel.innerHTML = cams.map((c, i) => `<option value="${c.deviceId}" ${c.deviceId === current ? "selected" : ""}>${c.label || `กล้อง ${i + 1}`}</option>`).join("");
  sel.hidden = cams.length < 2;
}

// --- per frame ------------------------------------------------------------------------
async function loop() {
  if (!running) return;
  if (video && video.readyState >= 2) {
    const vw = video.videoWidth, vh = video.videoHeight, s = Math.min(vw, vh);
    ctx.drawImage(video, (vw - s) / 2, (vh - s) / 2, s, s, 0, 0, SIZE, SIZE);
    try {
      const { pose, posenetOutput } = await model.estimatePose(view);
      const pred = await model.predict(posenetOutput);
      onFrame(pose, pred);
      if (pose && running) {
        tmPose.drawKeypoints(pose.keypoints, KP_MIN, ctx);
        tmPose.drawSkeleton(pose.keypoints, KP_MIN, ctx);
      }
    } catch (e) { console.error(e); }
  }
  if (running) frameReq = requestAnimationFrame(loop);
}

function onFrame(pose, pred) {
  const now = performance.now();
  const kp = {};
  (pose?.keypoints || []).forEach((k) => { if (k.score >= KP_MIN) kp[k.part] = k.position; });
  const present = Object.keys(kp).length >= MIN_POINTS;
  acc.frames++;
  if (present) acc.present++;

  // Body scale: torso length, so distances mean the same near or far from the camera.
  let scale = SIZE * 0.25;
  if (kp.leftShoulder && kp.rightShoulder) {
    const sh = mid(kp.leftShoulder, kp.rightShoulder);
    scale = kp.leftHip && kp.rightHip ? dist(sh, mid(kp.leftHip, kp.rightHip)) : dist(kp.leftShoulder, kp.rightShoulder) * 1.4;
  }
  scale = Math.max(scale, 20);

  // Movement: mean keypoint shift since the last frame.
  if (present && prevKp) {
    let sum = 0, n = 0;
    for (const [part, p] of Object.entries(kp)) if (prevKp[part]) { sum += dist(p, prevKp[part]); n++; }
    if (n >= 4) { acc.energySum += sum / n / scale; acc.energyN++; }
  }
  prevKp = present ? kp : null;

  // Posture label for this frame.
  const top = pred.reduce((a, b) => (b.probability > a.probability ? b : a));
  recent.push({ t: now, label: present && top.probability >= LABEL_MIN ? top.className : null, prob: top.probability });
  recent = recent.filter((r) => now - r.t <= 1000);
  showProbs(pred, present);

  if (present) countMoves(kp, scale, now);
}

function countMoves(kp, scale, now) {
  const lw = kp.leftWrist, rw = kp.rightWrist, ls = kp.leftShoulder, rs = kp.rightShoulder;
  if (!lw || !rw) return;
  const shY = ls && rs ? (ls.y + rs.y) / 2 : null;
  const headY = kp.nose ? kp.nose.y : shY != null ? shY - 0.45 * scale : null;

  // Arm raise: both wrists above the head, counted once until both come back below the shoulders.
  if (headY != null && shY != null) {
    if (armState === "down" && lw.y < headY && rw.y < headY) { armState = "up"; rep("arms_up"); }
    else if (armState === "up" && lw.y > shY && rw.y > shY) armState = "down";
  }

  // Clap: wrists meet in front of the body (below the head), then part again.
  const width = ls && rs ? dist(ls, rs) : scale * 0.8;
  const gap = dist(lw, rw) / Math.max(width, 10);
  const belowHead = headY == null || (lw.y > headY && rw.y > headY);
  if (clapState === "apart" && gap < CLAP_TOGETHER && belowHead && now - lastClap > 300) {
    clapState = "together"; lastClap = now; rep("clap");
  } else if (clapState === "together" && gap > CLAP_APART) clapState = "apart";
}

function rep(move) {
  const t = secondsSinceStart();
  session.reps.push({ t, move });
  if (move === "arms_up") acc.arms++; else acc.claps++;
  $("#tArms").textContent = session.reps.filter((r) => r.move === "arms_up").length;
  $("#tClaps").textContent = session.reps.filter((r) => r.move === "clap").length;
  send("/api/camera/rep", { move });
}

function showProbs(pred, present) {
  $("#probs").innerHTML = pred.map((p) => {
    const pct = present ? Math.round(p.probability * 100) : 0;
    return `<div><span>${p.className}</span><div class="meter"><i style="width:${pct}%"></i></div><b>${present ? pct + "%" : "–"}</b></div>`;
  }).join("");
}

// --- once a second ----------------------------------------------------------------------
function secondsSinceStart() { return session.startedAt ? Math.round((Date.now() - session.startedAt) / 100) / 10 : 0; }

function everySecond() {
  const present = acc.frames > 0 && acc.present > acc.frames / 2;
  const raw = acc.energyN ? acc.energySum / acc.energyN : 0;
  const energy = present ? Math.round(clamp((raw - ENERGY_FLOOR) / (ENERGY_FULL - ENERGY_FLOOR), 0, 1) * 100) : 0;

  // Majority label over the last second; keep the previous posture when nothing wins.
  const labelled = recent.filter((r) => r.label);
  const votes = {};
  labelled.forEach((r) => { votes[r.label] = (votes[r.label] || 0) + 1; });
  const [winner, n] = Object.entries(votes).sort((a, b) => b[1] - a[1])[0] || [null, 0];
  if (!present) { posture = null; postureConf = 0; }
  else if (winner && n > labelled.length / 2) {
    posture = LABEL_POSTURE[winner] || posture;
    const probs = labelled.filter((r) => r.label === winner).map((r) => r.prob);
    postureConf = probs.reduce((a, b) => a + b, 0) / probs.length;
  }
  fallStreak = present && posture === "floor" ? fallStreak + 1 : 0;
  const fall = fallStreak >= FALL_SECONDS;

  const row = {
    t: secondsSinceStart(), presence: present, posture: present ? posture : null,
    confidence: Math.round(postureConf * 100) / 100, moving_energy: energy, fall,
    arms_up: acc.arms, clap: acc.claps,
  };
  session.rows.push(row);
  if (session.rows.length > 4 * 3600) session.rows.shift();  // cap at 4 hours
  acc = newAcc();

  send("/api/camera", { presence: present, moving_energy: energy, posture: row.posture, fall });
  renderNow(row);
  renderSummary();
}

function renderNow(row) {
  const label = !row.presence ? "ไม่เห็นคน" : row.fall ? "⚠️ สงสัยล้ม" : POSTURE_TH[row.posture] || "ไม่แน่ใจ";
  $("#tPose").textContent = label;
  $("#poseNow").textContent = label;
  $("#poseNow").className = row.fall ? "fall" : "";
  $("#presenceNow").textContent = row.presence ? `ขยับ ${row.moving_energy}` : "ไม่เห็นคนในภาพ";
  $("#tEnergy").textContent = row.presence ? row.moving_energy : "–";
  $("#tEnergyBar").style.width = `${row.moving_energy}%`;
}

function renderSummary() {
  const rows = session.rows;
  const has = rows.length > 0;
  ["#exportJson", "#exportCsv", "#clearBtn"].forEach((s) => { $(s).disabled = !has; });
  if (!has) { $("#summary").innerHTML = '<tr><td colspan="2" style="color:var(--muted)">ยังไม่มีข้อมูล</td></tr>'; return; }
  const seen = rows.filter((r) => r.presence);
  const per = (p) => rows.filter((r) => r.presence && r.posture === p).length;
  const avg = seen.length ? Math.round(seen.reduce((a, r) => a + r.moving_energy, 0) / seen.length) : 0;
  const lines = [
    ["ระยะเวลาที่เปิดกล้อง", mmss(rows.length)],
    ["เห็นคนในภาพ", `${Math.round((100 * seen.length) / rows.length)}%`],
    ["ยืน / เดิน", mmss(per("standing"))],
    ["นั่ง", mmss(per("sitting"))],
    ["นอน", mmss(per("lying"))],
    ["อยู่บนพื้น", mmss(per("floor"))],
    ["การขยับเฉลี่ยตอนเห็นคน (0–100)", avg],
    ["🙌 ยกแขนแตะฟ้า", `${session.reps.filter((r) => r.move === "arms_up").length} ครั้ง`],
    ["👏 ปรบมือ", `${session.reps.filter((r) => r.move === "clap").length} ครั้ง`],
    ["ช่วงที่สงสัยล้ม", `${rows.filter((r) => r.fall).length} วินาที`],
  ];
  $("#summary").innerHTML = lines.map(([k, v]) => `<tr><td>${k}</td><td>${v}</td></tr>`).join("");
}

// --- export / clear ---------------------------------------------------------------------
function save(name, text, type) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = Object.assign(document.createElement("a"), { href: url, download: name });
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
const stamp = () => (session.startedAt || new Date()).toISOString().slice(0, 16).replace(/[:T]/g, "-");

$("#exportJson").onclick = () => save(`carely-camera-${stamp()}.json`, JSON.stringify({
  schema: "carely-camera/1",
  started_at: session.startedAt?.toISOString(),
  exported_at: new Date().toISOString(),
  model: "my-pose-model (Teachable Machine pose 0.8.6 บน PoseNet MobileNetV1)",
  fields: {
    t: "วินาทีนับจากเริ่ม", presence: "เห็นคนในภาพ", posture: "standing | sitting | lying | floor",
    confidence: "ความน่าจะเป็นเฉลี่ยของท่านั้น (0-1)", moving_energy: "การขยับ 0-100", fall: "สงสัยล้ม",
    arms_up: "ยกแขนที่นับได้ในวินาทีนั้น", clap: "ปรบมือที่นับได้ในวินาทีนั้น",
  },
  rows: session.rows,
  reps: session.reps,
}, null, 2), "application/json");

$("#exportCsv").onclick = () => {
  const cols = ["t", "presence", "posture", "confidence", "moving_energy", "fall", "arms_up", "clap"];
  const csv = [cols.join(","), ...session.rows.map((r) => cols.map((c) => r[c] ?? "").join(","))].join("\n");
  save(`carely-camera-${stamp()}.csv`, csv, "text/csv");
};

$("#clearBtn").onclick = () => {
  session = newSession();
  if (running) session.startedAt = new Date();
  $("#tArms").textContent = "0"; $("#tClaps").textContent = "0";
  renderSummary();
  setStatus(running ? "ล้างข้อมูลในหน้านี้แล้ว กล้องยังทำงานอยู่" : "ล้างข้อมูลในหน้านี้แล้ว", running ? "ok" : "");
};

// --- wiring ------------------------------------------------------------------------------
$("#agree").onchange = (e) => { $("#startBtn").disabled = !e.target.checked || running; };
$("#startBtn").onclick = start;
$("#stopBtn").onclick = stop;
$("#cameraPick").onchange = async () => { if (running) { stop(); await start(); } };
$("#sendToCarely").onchange = () => setLink(true);
window.addEventListener("pagehide", stop);
showProbs((["นอน", "นั่ง", "ลุก", "เดิน", "ล้ม"]).map((c) => ({ className: c, probability: 0 })), false);
