// Shared by index.html (home screen), activities.html and family.html.
// Holds the exercise list, extra icons and the daily-summary maths so the three pages always agree.
(function (g) {
  'use strict';

  const ICONS = {
    foot: '<path d="M12 4v10M8 8l4-4 4 4M5 20h14"/>',
    stretch: '<circle cx="12" cy="5" r="2"/><path d="M12 7v7M5 10l7 2 7-2M9 22l3-8 3 8"/>',
    rotate: '<path d="M21 12a9 9 0 11-3-6.7M21 4v5h-5"/>',
    legs: '<path d="M12 4v8l5 4M12 12l-5 8"/>',
    droplet: '<path d="M12 3s6 6.5 6 11a6 6 0 01-12 0c0-4.5 6-11 6-11z"/>',
    moon: '<path d="M20 14A8 8 0 0110 4a8 8 0 1010 10z"/>',
    chevronRight: '<path d="M9 5l7 7-7 7"/>',
    chevronLeft: '<path d="M15 5l-7 7 7 7"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    trend: '<path d="M3 17l6-6 4 4 8-8M15 7h6v6"/>',
    gift: '<rect x="3" y="8" width="18" height="4" rx="1"/><path d="M12 8v13M5 12v9h14v-9M12 8c-2-4-6-3-5 0 .5 1.5 3 1 5 0zM12 8c2-4 6-3 5 0-.5 1.5-3 1-5 0z"/>',
    ticket: '<path d="M3 8h18v3a2 2 0 000 4v3H3v-3a2 2 0 000-4z"/><path d="M13 8v10"/>',
    lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 018 0v3"/>',
    share: '<circle cx="6" cy="12" r="2.5"/><circle cx="18" cy="6" r="2.5"/><circle cx="18" cy="18" r="2.5"/><path d="M8.2 11l7.6-4M8.2 13l7.6 4"/>',
    users: '<circle cx="9" cy="8" r="3.5"/><path d="M2 20c0-3.5 3-5.5 7-5.5s7 2 7 5.5M17 5a3.5 3.5 0 010 7M22 20c0-2.5-1.5-4-4-4.8"/>',
    coffee: '<path d="M4 8h13v6a5 5 0 01-5 5H9a5 5 0 01-5-5zM17 10h2a2 2 0 010 4h-2M7 3v2M11 3v2M15 3v2"/>',
    pill: '<rect x="2.5" y="8.5" width="19" height="7" rx="3.5" transform="rotate(-45 12 12)"/><path d="M9.5 9.5l5 5"/>',
    calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
    tv: '<rect x="3" y="5" width="18" height="12" rx="2"/><path d="M8 21h8M12 17v4"/>',
    sunrise: '<path d="M3 18h18M7 18a5 5 0 0110 0M12 6v3M4.5 10.5l2 2M19.5 10.5l-2 2"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
    close: '<path d="M6 6l12 12M18 6L6 18"/>',
    send: '<path d="M22 2L11 13M22 2l-7 20-4-9-9-4z"/>',
    contact: '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="10" cy="11" r="2.5"/><path d="M6 17c.5-2 2-3 4-3s3.5 1 4 3M16 9h3M16 13h3"/>',
    history: '<path d="M3 12a9 9 0 109-9 9 9 0 00-7 3.4M3 4v4h4M12 8v4l3 2"/>',
    up: '<path d="M12 19V5M5 12l7-7 7 7"/>',
    // solid pictograms (head + thick limbs), after the iStock exercise icon set
    pStand: '<circle cx="12" cy="4.4" r="2.8" fill="currentColor" stroke="none"/><path d="M12 9.5V15.5M12 10.5L7.5 14.5M12 10.5L16.5 14.5M12 15.5L9.5 21M12 15.5L14.5 21" stroke-width="3.3"/>',
    pArmsUp: '<circle cx="12" cy="5.6" r="2.8" fill="currentColor" stroke="none"/><path d="M12 10.5V16M12 11L5.5 6.5M12 11L18.5 6.5M12 16L9 21.5M12 16L15 21.5" stroke-width="3.3"/>',
    pShoulder: '<circle cx="12" cy="5" r="2.8" fill="currentColor" stroke="none"/><path d="M12 10V16M12 10.5L7 12.5L7.5 8.5M12 10.5L17 12.5L16.5 8.5M12 16L9.5 21.5M12 16L14.5 21.5" stroke-width="3.2"/><path d="M3 9.5a5.5 5.5 0 013-4.5M21 9.5a5.5 5.5 0 00-3-4.5" stroke-width="1.6"/>',
    pSit: '<circle cx="9.5" cy="4.8" r="2.8" fill="currentColor" stroke="none"/><path d="M9.5 9.5V15M9.5 15H16M16 15V21M9.5 11L14 13.2" stroke-width="3.3"/><path d="M5 17.5V21M6 17.5H12" stroke-width="2"/>',
    pChairStand: '<circle cx="8.5" cy="4.8" r="2.8" fill="currentColor" stroke="none"/><path d="M8.5 9.5L10.5 15M9.5 11.5L14.5 10.5M10.5 15H15.5M15.5 15V21" stroke-width="3.2"/><path d="M4 17.5H11M4.5 17.5V21" stroke-width="2"/><path d="M20 15V8M17.5 10.5L20 8L22.5 10.5" stroke-width="2"/>',
    video: '<rect x="3" y="6" width="13" height="12" rx="2.5"/><path d="M16 10.5l5-3v9l-5-3z"/>',
    videoOff: '<path d="M3 3l18 18M7 6h6a3 3 0 013 3v1.5M16 10.5l5-3v9M16 15v.5a2.5 2.5 0 01-2.5 2.5H6a3 3 0 01-3-3V9"/>',
    mic: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0014 0M12 18v3"/>',
    micOff: '<path d="M3 3l18 18M9 9v2a3 3 0 005 2.2M15 10V6a3 3 0 00-5.6-1.5M5 11a7 7 0 0011 5.5M12 18v3"/>',
    phoneDown: '<g transform="rotate(135 12 12)"><path d="M5 3h4l2 5-2.5 1.5a11 11 0 006 6L16 13l5 2v4a2 2 0 01-2 2A16 16 0 013 5a2 2 0 012-2z"/></g>',
    image: '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="M21 16l-5-5-8 9"/>',
    eye: '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  };

  const CATS = [['all', 'ทั้งหมด'], ['arm', 'แขนและไหล่'], ['leg', 'ขา']];

  // Only three exercises, run together as one daily routine (no picking game by game).
  const EXERCISES = [
    { id: 'shoulder_roll', title: 'หมุนไหล่', icon: 'pShoulder', cat: 'arm', minutes: 1, amount: '10 ครั้ง', seated: true,
      desc: 'หมุนไหล่ไปข้างหลังช้าๆ ช่วยคลายคอบ่าไหล่',
      steps: [
        { icon: 'pStand', say: 'นั่งหรือยืนหลังตรง ผ่อนคลายไหล่นะคะ', seconds: 4 },
        { icon: 'pShoulder', say: 'หมุนไหล่ไปข้างหลังช้าๆ นับไปพร้อมกันนะคะ', reps: 10, beat: 3 },
        { icon: 'pStand', say: 'หายใจเข้าลึกๆ แล้วผ่อนออกช้าๆ', seconds: 5 },
      ] },
    { id: 'arm_sky', title: 'ยกแขนขึ้นลง', icon: 'pArmsUp', cat: 'arm', minutes: 2, amount: '20 ครั้ง', seated: true,
      desc: 'ยกแขนสองข้างขึ้นสูงแล้ววางลง ทำได้ทั้งนั่งและยืน กล้องช่วยนับ',
      steps: [
        { icon: 'pSit', say: 'นั่งหลังตรง หรือยืนจับพนักเก้าอี้ไว้นะคะ', seconds: 5 },
        { icon: 'pArmsUp', say: 'ยกแขนสองข้างขึ้นแตะฟ้า แล้ววางลง นับไปพร้อมกันนะคะ', reps: 20, beat: 2.5, detect: 'arms_up' },
        { icon: 'pStand', say: 'หายใจเข้าลึกๆ แล้วผ่อนออกช้าๆ', seconds: 6 },
      ] },
    { id: 'chair_stand', title: 'ลุก-นั่งเก้าอี้', icon: 'pChairStand', cat: 'leg', minutes: 2, amount: '10 ครั้ง', seated: true,
      desc: 'ลุกขึ้นยืนแล้วนั่งลงช้าๆ เสริมกล้ามเนื้อขา กล้องช่วยนับเมื่อเห็นการลุก',
      steps: [
        { icon: 'pSit', say: 'นั่งที่ขอบเก้าอี้ที่มั่นคง ไขว้แขนที่หน้าอกนะคะ', seconds: 5 },
        { icon: 'pChairStand', say: 'ลุกขึ้นยืนแล้วนั่งลงช้าๆ นับไปพร้อมกันนะคะ', reps: 10, beat: 6, detect: 'stand_up' },
        { icon: 'pStand', say: 'พักหายใจสักครู่นะคะ', seconds: 6 },
      ] },
  ];
  const PROGRAM = { id: 'program', title: 'ออกกำลังกายวันนี้', icon: 'pStand', minutes: 5, amount: '3 ท่า', desc: 'หมุนไหล่ → ยกแขนขึ้นลง → ลุก-นั่งเก้าอี้ ทำต่อกันประมาณ 5 นาที', ids: ['shoulder_roll', 'arm_sky', 'chair_stand'] };  const EX_BY_ID = Object.fromEntries(EXERCISES.map(e => [e.id, e]));

  // ---------------- dates & formatting ----------------
  const pad = n => String(n).padStart(2, '0');
  const dKey = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const TH_DOW = ['อา', 'จ', 'อ', 'พ', 'พฤ', 'ศ', 'ส'];
  const fmtDur = m => { m = Math.round(Math.max(0, m || 0)); const h = Math.floor(m / 60); return h ? `${h} ชม. ${m % 60} น.` : `${m} น.`; };
  const store = { get(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : v; } catch { return d; } } };
  const sitLimit = () => Math.max(1, +store.get('carely-sit-limit', 60) || 60);

  // ---------------- one day's numbers ----------------
  function dayFromRecord(key, rec) {
    const t = rec.totals || {};
    const bt = rec.bathTimes || [], st = rec.standTimes || [];
    return {
      key, bathSensor: !!rec.bathSensor, bathroom: rec.bathSensor ? bt.length : null, bathTimes: bt,
      standTimes: st, standUps: st.length, sitMin: +t.sitting || 0, standMin: (+t.standing || 0) + (+t.walking || 0), lieMin: +t.low || 0,
      falls: +rec.fallCount || 0, sitMax: +rec.sitMax || 0, workouts: rec.workouts || [], events: rec.events || [], gamesToday: +rec.gamesToday || 0,
    };
  }
  function history() {
    const rem = g.CARELY && g.CARELY.remote && g.CARELY.remote.hist;       // sent by the home screen when this page runs on another device
    if (rem && rem.length) return rem.slice().sort((a, b) => a.key < b.key ? 1 : -1);
    const out = [];
    try {
      for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i), m = /^carely-(\d{4}-\d{2}-\d{2})$/.exec(k);
        if (!m) continue;
        out.push(dayFromRecord(m[1], JSON.parse(localStorage.getItem(k) || '{}')));
      }
    } catch {}
    return out.sort((a, b) => a.key < b.key ? 1 : -1);
  }

  // ---------------- sample data (clearly labelled as sample in the UI) ----------------
  function genTimes(base, count, seed) {
    const out = [];
    for (let i = 0; i < count; i++) {
      const frac = (i + 0.5) / count, wiggle = ((seed * 7 + i * 13) % 20 - 10) / 100 / count;
      out.push(base + Math.round((6.5 + (14.5 * (frac + wiggle))) * 3600000));
    }
    return out;
  }
  function sample() {
    const now = new Date(), base = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const at = (h, m) => base + (h * 60 + m) * 60000;
    const days = [];
    const today = {
      key: dKey(new Date(base)), bathSensor: true, bathroom: 6,
      bathTimes: [at(6, 40), at(8, 35), at(10, 10), at(11, 30), at(13, 20), at(15, 45)],
      standTimes: [at(6, 30), at(7, 10), at(8, 20), at(9, 0), at(9, 45), at(10, 5), at(10, 50), at(11, 35), at(12, 20), at(13, 10), at(14, 0), at(14, 50), at(15, 30), at(16, 15)],
      standUps: 14, sitMin: 252, standMin: 130, lieMin: 80, falls: 1, sitMax: 65,
      workouts: [{ id: 'shoulder_roll', title: 'หมุนไหล่', ts: at(9, 0), min: 1, score: 95 }, { id: 'arm_sky', title: 'ยกแขนขึ้นลง', ts: at(9, 30), min: 2, score: 92 }, { id: 'chair_stand', title: 'ลุก-นั่งเก้าอี้', ts: at(10, 20), min: 2, score: 80 }],
      gamesToday: 3, sample: true,
    };
    days.push(today);
    for (let i = 1; i < 28; i++) {
      const d0 = base - i * 86400000, v = (a, b, k) => a + ((i * 37 + k * 11) % (b - a + 1));
      const bath = v(4, 7, 1), stand = v(12, 19, 2);
      days.push({
        key: dKey(new Date(d0)), bathSensor: true, bathroom: bath, bathTimes: genTimes(d0, bath, i), standTimes: genTimes(d0, stand, i + 3), standUps: stand,
        sitMin: v(220, 280, 3), standMin: v(110, 170, 4), lieMin: v(60, 100, 5), falls: 0, sitMax: v(40, 58, 6),
        workouts: [{ id: 'arm_sky', title: 'ยกแขนขึ้นลง', ts: d0 + 9.5 * 3600000, min: 2, score: v(70, 95, 7) }], gamesToday: 1, sample: true,
      });
    }
    // the example notification list used for demos
    const notifs = [
      { ts: at(8, 23), title: 'ตื่นนอน', desc: 'ตรวจพบการเคลื่อนไหวแรกของวัน', icon: 'sunrise', kind: 'activity', level: '' },
      { ts: at(9, 2), title: 'นั่งดูทีวี', desc: 'เปลี่ยนเป็นท่านั่งในห้องนั่งเล่น', icon: 'tv', kind: 'activity', level: '' },
      { ts: at(10, 2), title: 'แจ้งเตือนให้ลุกเดิน', desc: 'นั่งต่อเนื่อง 60 นาที ระบบชวนให้ลุกเดินหรือเล่นเกม', icon: 'bell', kind: 'nudge', level: 'warn', action: 'send' },
      { ts: at(11, 47), title: 'ล้ม', desc: 'เซนเซอร์ตรวจพบการล้มที่ห้องนั่งเล่น โปรดโทรหาท่านทันที', icon: 'alert', kind: 'fall', level: 'bad', action: 'call' },
      { ts: at(11, 49), title: 'คุณกดเรียก 1669', desc: 'โทร 1669 และแจ้งผู้ติดต่อฉุกเฉินแล้ว', icon: 'phone', kind: 'call1669', level: 'bad' },
    ];
    return { days, notifs, stamps: 42 };
  }

  // ---------------- live events -> notification rows ----------------
  const stripEmoji = s => String(s ?? '').replace(/[\p{Extended_Pictographic}‍️]+\s*/gu, '').trim();
  const KIND_ICON = { fall: 'alert', sos: 'alert', call1669: 'phone', ok: 'checkCircle', ack: 'check', game_done: 'award', game_start: 'play', game_offer: 'gamepad', game_skipped: 'dot', message: 'mail', camera: 'camera', posture: 'walk', nudge: 'bell', bathroom: 'droplet' };
  const KIND_TYPE = { fall: 'important', sos: 'important', call1669: 'important', nudge: 'important', posture: 'activity', bathroom: 'activity', camera: 'activity', game_done: 'activity', game_start: 'activity', game_offer: 'message', message: 'message', ack: 'message', ok: 'message', game_skipped: 'activity' };
  function notifsFromEvents(evs) {
    return (evs || []).map(e => ({
      ts: e.ts, title: stripEmoji(e.text), desc: '', icon: KIND_ICON[e.kind] || 'dot', kind: e.kind, level: e.level || '',
      action: e.kind === 'fall' || e.kind === 'sos' ? 'call' : e.kind === 'nudge' ? 'send' : '',
    }));
  }

  // ---------------- summary for the dashboard ----------------
  function summarize(snap, isOnline, pref) {
    const hist = history();
    const hasReal = hist.some(d => d.sitMin + d.standMin + d.lieMin > 0 || d.falls || d.bathTimes.length || d.workouts.length);
    // "auto": real numbers only when there is something real to show (camera on, or any recorded activity)
    const snapHas = !!(isOnline && snap && ((snap.running && !snap.cctv) || (snap.totals && Object.values(snap.totals).some(v => v > 0)) || (snap.bathTimes || []).length || (snap.standTimes || []).length || snap.fallCount || (snap.workouts || []).length || (snap.events || []).length));
    const mode = pref === 'sample' ? 'sample' : pref === 'live' ? 'live' : (snapHas || hasReal) ? 'live' : 'sample';
    if (mode === 'sample') {
      const s = sample();
      return { mode, days: s.days, today: s.days[0], notifs: s.notifs, stamps: s.stamps, normal: normalRange(s.days), history: s.days };
    }
    const todayKey = dKey(new Date());
    let today = hist.find(d => d.key === todayKey) || dayFromRecord(todayKey, {});
    if (isOnline && snap) {
      const t = snap.totals || {};
      const curSit = snap.activity === 'sitting' && snap.activitySince ? (Date.now() - snap.activitySince) / 60000 : 0;
      today = {
        ...today, key: todayKey, bathSensor: !!snap.bathSensor, bathroom: snap.bathSensor ? (snap.bathTimes || []).length : null, bathTimes: snap.bathTimes || [],
        standTimes: snap.standTimes || [], standUps: (snap.standTimes || []).length, sitMin: +t.sitting || 0, standMin: (+t.standing || 0) + (+t.walking || 0), lieMin: +t.low || 0,
        falls: +snap.fallCount || 0, sitMax: Math.max(+snap.sitMax || 0, curSit), workouts: snap.workouts || [], events: snap.events || today.events, gamesToday: +snap.gamesToday || 0, curSit,
      };
    }
    const days = [today, ...hist.filter(d => d.key !== todayKey)].slice(0, 28);
    const stamps = days.reduce((a, d) => a + (d.gamesToday || d.workouts.length || 0), 0);
    return { mode, days, today, notifs: notifsFromEvents(today.events), stamps, normal: normalRange(days), history: days };
  }
  function normalRange(days) {
    const past = days.slice(1).map(d => d.bathroom).filter(v => v != null);
    if (past.length >= 3) {
      const m = past.reduce((a, b) => a + b, 0) / past.length, sd = Math.sqrt(past.reduce((a, b) => a + (b - m) ** 2, 0) / past.length);
      const w = Math.max(1, sd);
      return { lo: Math.max(0, Math.floor(m - w)), hi: Math.ceil(m + w), source: 'own', n: past.length };
    }
    return { lo: 4, hi: 8, source: 'guide', n: past.length };
  }
  // Early signs: today compared with this person's own recent average (needs 3+ days of data)
  function insights(days) {
    const out = [], t = days && days[0];
    const past = (days || []).slice(1).filter(d => d.sitMin + d.standMin + d.lieMin > 0);
    if (!t || past.length < 3) return out;
    const avg = f => past.reduce((a, d) => a + (f(d) || 0), 0) / past.length;
    const sitAvg = avg(d => d.sitMin), suAvg = avg(d => d.standUps), lieAvg = avg(d => d.lieMin);
    if (sitAvg >= 30 && t.sitMin > sitAvg * 1.25) out.push({ level: 'warn', text: `วันนี้นั่งนานกว่าปกติ ${Math.round((t.sitMin / sitAvg - 1) * 100)}% (เฉลี่ย ${Math.round(sitAvg)} นาที)` });
    if (suAvg >= 4 && t.standUps < suAvg * 0.6) out.push({ level: 'warn', text: `ลุกยืนน้อยกว่าปกติ ${Math.round((1 - t.standUps / suAvg) * 100)}% (วันนี้ ${t.standUps} ครั้ง · เฉลี่ย ${Math.round(suAvg)})` });
    if (lieAvg >= 10 && t.lieMin > lieAvg * 1.5) out.push({ level: 'warn', text: `นอน/อยู่ต่ำนานกว่าปกติ ${Math.round((t.lieMin / lieAvg - 1) * 100)}%` });
    if (!out.length) out.push({ level: 'ok', text: 'วันนี้การเคลื่อนไหวใกล้เคียงปกติของท่าน' });
    return out;
  }
  // Level: ok | warn | bad, plus the reasons shown under the main card.
  function evaluate(day, normal, limit) {
    const reasons = []; let level = 'ok';
    const raise = l => { if (l === 'bad' || (l === 'warn' && level === 'ok')) level = l; };
    if (day.falls > 0) { raise('bad'); reasons.push(`ล้ม ${day.falls} ครั้งวันนี้`); }
    let bath = 'none';
    if (day.bathroom != null) {
      bath = day.bathroom > normal.hi ? 'high' : day.bathroom < normal.lo ? 'low' : 'ok';
      if (bath === 'high') { raise('warn'); reasons.push(`ไปห้องน้ำบ่อยกว่าปกติ (${day.bathroom} ครั้ง · ปกติ ${normal.lo}–${normal.hi})`); }
      if (bath === 'low') { raise('warn'); reasons.push(`ไปห้องน้ำน้อยกว่าปกติ (${day.bathroom} ครั้ง · ปกติ ${normal.lo}–${normal.hi}) ลองดูเรื่องการดื่มน้ำ`); }
    }
    const stand = day.standUps < 6 ? 'low' : day.standUps > 30 ? 'high' : 'ok';
    if (stand === 'low' && (day.sitMin + day.standMin) > 120) { raise('warn'); reasons.push(`ลุกขึ้นยืนน้อย (${day.standUps} ครั้ง)`); }
    if (day.sitMax >= limit) { raise('warn'); reasons.push(`นั่งต่อเนื่องนานสุด ${fmtDur(day.sitMax)} (เกณฑ์ ${limit} น.)`); }
    if (day.sitMin >= 420) { raise('warn'); reasons.push(`นั่งรวมเกิน 7 ชั่วโมง (${fmtDur(day.sitMin)})`); }
    if (day.lieMin >= 240) { raise('warn'); reasons.push(`นอน/อยู่ต่ำรวม ${fmtDur(day.lieMin)} ในช่วงที่กล้องเห็น`); }
    return { level, reasons, bath, stand };
  }

  // ---------------- profiles (name + photo), shared by every page ----------------
  const PROFILES = { elder: { name: 'carely-elder', photo: 'carely-elder-photo', def: 'คุณยาย' }, family: { name: 'carely-sender', photo: 'carely-sender-photo', def: 'ลูก' } };
  const profile = role => {
    const k = PROFILES[role];
    const rem = role === 'elder' && g.CARELY && g.CARELY.remote && g.CARELY.remote.elder;   // the elder's profile lives on the home screen
    if (rem) return { name: rem.name || k.def, photo: rem.photo || '' };
    return { name: store.get(k.name, k.def), photo: store.get(k.photo, '') };
  };
  function saveProfile(role, name, photo) {
    const k = PROFILES[role];
    try {
      localStorage.setItem(k.name, (name || '').trim() || k.def);
      if (photo === null) localStorage.removeItem(k.photo); else if (photo) localStorage.setItem(k.photo, photo);
    } catch {}
  }
  // photo file -> small square JPEG data URL (kept on this device only)
  function readPhoto(file, size = 256) {
    return new Promise((resolve, reject) => {
      const url = URL.createObjectURL(file), img = new Image();
      img.onload = () => {
        const s = Math.min(img.width, img.height), c = document.createElement('canvas'); c.width = c.height = size;
        c.getContext('2d').drawImage(img, (img.width - s) / 2, (img.height - s) / 2, s, s, 0, 0, size, size);
        URL.revokeObjectURL(url); resolve(c.toDataURL('image/jpeg', 0.85));
      };
      img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('อ่านรูปไม่ได้')); };
      img.src = url;
    });
  }
  const avatar = (role, fallbackHtml) => { const p = profile(role); return p.photo ? `<img src="${p.photo}" alt="" style="width:100%;height:100%;object-fit:cover;border-radius:50%;display:block">` : fallbackHtml; };

  // ---------------- WebRTC: live view (camera -> family) and two-way video call ----------------
  // Signalling goes over the page-to-page bus (same browser). Media goes peer to peer.
  function makeRtc(o) {
    let pc = null, mode = null, st = 'idle', pending = [], remoteSet = false, local = null, ringTimer = 0, watchTimer = 0, denyTimer = 0, connTimer = 0;
    const msg = m => o.send({ type: 'rtc', ...m });
    const setState = s => {
      st = s;
      clearTimeout(connTimer);
      if (s === 'connecting') connTimer = setTimeout(() => { if (st === 'connecting') end('timeout', true); }, 20000);   // never stay stuck
      o.onState && o.onState(s, mode);
    };
    function end(why, notify) {
      clearTimeout(ringTimer); clearTimeout(watchTimer); clearTimeout(denyTimer); clearTimeout(connTimer);
      if (notify && st !== 'idle') msg({ k: 'hangup' });
      try { pc && pc.close(); } catch {}
      if (local) { local.getTracks().forEach(t => t.stop()); local = null; }
      const m = mode; pc = null; mode = null; pending = []; remoteSet = false;
      const was = st; st = 'idle'; o.onState && o.onState('idle', m);
      if (was !== 'idle') o.onEnd && o.onEnd(m, why);
    }
    async function newPc(m) {
      pc = new RTCPeerConnection({ iceServers: [] }); mode = m; remoteSet = false;
      pc.onicecandidate = e => { if (e.candidate) msg({ k: 'ice', cand: e.candidate.toJSON() }); };
      pc.ontrack = e => { o.onRemote && o.onRemote(e.streams[0] || new MediaStream([e.track]), m); };
      pc.onconnectionstatechange = () => {
        const s = pc && pc.connectionState;
        if (s === 'connected') { clearTimeout(watchTimer); setState('connected'); }
        else if (s === 'failed' || s === 'closed') end('connection-' + s, false);
      };
    }
    const flush = () => { pending.forEach(c => pc.addIceCandidate(c).catch(() => {})); pending = []; };
    async function sendOffer(stream, m) {
      await newPc(m);
      stream.getTracks().forEach(t => pc.addTrack(t, stream));
      await pc.setLocalDescription(await pc.createOffer());
      msg({ k: 'offer', mode: m, sdp: pc.localDescription.sdp });
    }
    async function handle(m) {
      if (m.type !== 'rtc') return;
      try {
        switch (m.k) {
          case 'watch': {                         // elder: family asks to see the camera
            if (o.role !== 'elder') return;
            if (st !== 'idle') { msg({ k: 'busy' }); return; }
            const s = o.canWatch && o.canWatch() ? await o.getWatchStream() : null;
            if (!s) { msg({ k: 'deny', reason: 'camera' }); return; }
            mode = 'watch'; setState('connecting'); await sendOffer(s, 'watch'); break;
          }
          case 'ring': {
            if (st !== 'idle') { msg({ k: 'busy' }); return; }
            mode = 'call'; setState('ringing-in'); o.onIncoming && o.onIncoming(m);
            ringTimer = setTimeout(() => end('missed', false), 45000); break;
          }
          case 'accept': {                        // caller: the other side picked up
            if (st !== 'ringing-out') return;
            clearTimeout(ringTimer); setState('connecting');
            local = await o.getCallStream(); if (!local) { end('no-media', true); return; }
            o.onLocal && o.onLocal(local); await sendOffer(local, 'call'); break;
          }
          case 'offer': {
            if (st !== 'connecting') return;
            clearTimeout(denyTimer);                // another screen said no, this one answered
            if (m.mode === 'call') { local = await o.getCallStream(); if (!local) { end('no-media', true); return; } o.onLocal && o.onLocal(local); }
            await newPc(m.mode);
            if (local) local.getTracks().forEach(t => pc.addTrack(t, local));
            await pc.setRemoteDescription({ type: 'offer', sdp: m.sdp }); remoteSet = true; flush();
            await pc.setLocalDescription(await pc.createAnswer());
            msg({ k: 'answer', sdp: pc.localDescription.sdp }); break;
          }
          case 'answer': if (pc) { await pc.setRemoteDescription({ type: 'answer', sdp: m.sdp }); remoteSet = true; flush(); } break;
          case 'ice': if (pc && remoteSet) pc.addIceCandidate(m.cand).catch(() => {}); else pending.push(m.cand); break;
          case 'busy': case 'deny':
            // with two home screens open, one may say no while the other answers: wait a moment before giving up on a live view
            if (st === 'connecting' && mode === 'watch' && o.role === 'family') { clearTimeout(denyTimer); denyTimer = setTimeout(() => end(m.k + (m.reason ? ':' + m.reason : ''), false), 1200); }
            else end(m.k + (m.reason ? ':' + m.reason : ''), false);
            break;
          case 'hangup': case 'decline': end(m.k, false); break;
        }
      } catch (e) { console.error('rtc', e); end('error:' + e.message, true); }
    }
    return {
      handle, get state() { return st; }, get mode() { return mode; },
      watch() {                                   // family: ask the elder screen for the live view
        if (st !== 'idle') return; mode = 'watch'; setState('connecting'); msg({ k: 'watch' });
        watchTimer = setTimeout(() => { if (st === 'connecting') end('timeout', true); }, 12000);
      },
      call() { if (st !== 'idle') return; mode = 'call'; setState('ringing-out'); msg({ k: 'ring', name: o.myName ? o.myName() : '', photo: o.myPhoto ? o.myPhoto() : '' }); ringTimer = setTimeout(() => end('noanswer', true), 40000); },
      accept() { if (st !== 'ringing-in') return; clearTimeout(ringTimer); setState('connecting'); msg({ k: 'accept' }); },
      decline() { if (st === 'ringing-in') { msg({ k: 'decline' }); end('declined', false); } },
      hangup() { end('hangup', true); },
      localStream: () => local,
    };
  }

  // Call screen (incoming ring, outgoing ring, in-call with picture-in-picture). `ic` draws icons.
  function mountCallUI(o) {
    if (!document.getElementById('rtc-css')) {
      const css = document.createElement('style'); css.id = 'rtc-css';
      css.textContent = `.rtc{position:fixed;inset:0;z-index:300;background:#0d1626;color:#fff;display:flex;flex-direction:column;align-items:center;justify-content:center;font-family:inherit}.rtc[hidden]{display:none}
.rtc .who{text-align:center;padding:24px}.rtc .pic{width:150px;height:150px;border-radius:50%;background:#cfe3ff;color:#0b3a78;margin:0 auto 18px;display:grid;place-items:center;overflow:hidden;animation:rtcpulse 1.6s infinite}.rtc .pic img{width:100%;height:100%;object-fit:cover}
.rtc h2{margin:0 0 6px;font-size:30px}.rtc p{margin:0;opacity:.8;font-size:19px}@keyframes rtcpulse{50%{box-shadow:0 0 0 18px rgba(207,227,255,.2)}}
.rtc .row{display:flex;gap:28px;margin-top:34px;justify-content:center}.rtc .rb{width:84px;height:84px;border-radius:50%;border:0;display:grid;place-items:center;cursor:pointer;color:#fff;padding:0}
.rtc .rb.go{background:#2b7bd8}.rtc .rb.no{background:#d03b3b}.rtc .rb.sw{background:rgba(255,255,255,.18)}.rtc .rb.off{background:#fff;color:#111}
.rtc .lbl{display:block;margin-top:8px;font-size:15px;opacity:.85;text-align:center}
.rtc .stage{position:absolute;inset:0;background:#000}.rtc video{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;background:#000}
.rtc .pip{position:absolute;right:14px;top:14px;width:128px;height:170px;border-radius:16px;overflow:hidden;border:2px solid rgba(255,255,255,.6);z-index:3;background:#222}.rtc .pip video{transform:scaleX(-1)}
.rtc .bar{position:absolute;left:0;right:0;bottom:0;padding:18px 12px 28px;display:flex;justify-content:center;gap:22px;z-index:4;background:linear-gradient(transparent,rgba(0,0,0,.65))}
.rtc .top{position:absolute;left:14px;top:14px;z-index:4;background:rgba(0,0,0,.45);border-radius:20px;padding:6px 14px;font-size:16px;font-weight:700}`;
      document.head.appendChild(css);
    }
    const root = document.createElement('div'); root.className = 'rtc'; root.hidden = true; root.setAttribute('role', 'dialog'); root.setAttribute('aria-modal', 'true');
    document.body.appendChild(root);
    let timer = 0, t0 = 0, ringT = 0, actx = null;
    const btn = (cls, icon, label, id) => `<div><button class="rb ${cls}" id="${id}" type="button" aria-label="${label}">${o.ic(icon, 38)}</button><span class="lbl">${label}</span></div>`;
    const stopRing = () => { clearInterval(ringT); ringT = 0; };
    function ring() {                              // simple repeating ring tone
      stopRing();
      const beep = () => { try { actx = actx || new (window.AudioContext || window.webkitAudioContext)(); [[740, 0], [988, .25]].forEach(([f, d]) => { const os = actx.createOscillator(), g = actx.createGain(), t = actx.currentTime + d; os.frequency.value = f; g.gain.setValueAtTime(.0001, t); g.gain.exponentialRampToValueAtTime(.25, t + .02); g.gain.exponentialRampToValueAtTime(.0001, t + .22); os.connect(g).connect(actx.destination); os.start(t); os.stop(t + .24); }); } catch {} };
      beep(); ringT = setInterval(beep, 1800);
    }
    const hide = () => { stopRing(); clearInterval(timer); root.hidden = true; root.innerHTML = ''; };
    const who = (name, sub, photoHtml) => `<div class="who"><div class="pic">${photoHtml}</div><h2>${o.esc(name)}</h2><p>${sub}</p></div>`;
    return {
      incoming(name, photoHtml, onAccept, onDecline) {
        root.hidden = false; ring();
        root.innerHTML = who(name, 'โทรวิดีโอเข้ามา', photoHtml) + `<div class="row">${btn('no', 'phoneDown', 'ปฏิเสธ', 'rtcNo')}${btn('go', 'video', 'รับสาย', 'rtcYes')}</div>`;
        root.querySelector('#rtcYes').onclick = () => { stopRing(); onAccept(); }; root.querySelector('#rtcNo').onclick = () => { hide(); onDecline(); };
      },
      outgoing(name, photoHtml, onCancel) {
        root.hidden = false; ring();
        root.innerHTML = who(name, 'กำลังโทร…', photoHtml) + `<div class="row">${btn('no', 'phoneDown', 'ยกเลิก', 'rtcNo')}</div>`;
        root.querySelector('#rtcNo').onclick = () => { hide(); onCancel(); };
      },
      connecting(name) { stopRing(); root.hidden = false; root.innerHTML = `<div class="who"><h2>${o.esc(name)}</h2><p>กำลังเชื่อมต่อ…</p></div>`; },
      inCall(name, onHangup) {
        stopRing(); root.hidden = false;
        root.innerHTML = `<div class="stage"><video id="rtcRemote" autoplay playsinline></video></div><div class="top"><span id="rtcName">${o.esc(name)}</span> · <span id="rtcTime">00:00</span></div>
          <div class="pip"><video id="rtcLocal" autoplay playsinline muted></video></div>
          <div class="bar">${btn('sw', 'mic', 'ไมค์', 'rtcMic')}${btn('no', 'phoneDown', 'วางสาย', 'rtcEnd')}${btn('sw', 'video', 'กล้อง', 'rtcCam')}</div>`;
        t0 = Date.now(); clearInterval(timer);
        timer = setInterval(() => { const s = Math.floor((Date.now() - t0) / 1000), el = root.querySelector('#rtcTime'); if (el) el.textContent = `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`; }, 1000);
        root.querySelector('#rtcEnd').onclick = () => { hide(); onHangup(); };
        const tog = (id, kind, on, off) => { root.querySelector(id).onclick = e => { const s = o.local && o.local(); if (!s) return; const tr = kind === 'a' ? s.getAudioTracks() : s.getVideoTracks(), nowOn = !(tr[0] && tr[0].enabled); tr.forEach(x => { x.enabled = nowOn; }); const b = e.currentTarget; b.classList.toggle('off', !nowOn); b.innerHTML = o.ic(nowOn ? on : off, 38); }; };
        tog('#rtcMic', 'a', 'mic', 'micOff'); tog('#rtcCam', 'v', 'video', 'videoOff');
        const l = o.local && o.local(); if (l) root.querySelector('#rtcLocal').srcObject = l;
      },
      setRemote(stream) { const v = root.querySelector('#rtcRemote'); if (v) v.srcObject = stream; },
      setLocal(stream) { const v = root.querySelector('#rtcLocal'); if (v) v.srcObject = stream; },
      hide, ring, stopRing, get visible() { return !root.hidden; },
    };
  }
  // ---------------- message bus between the pages ----------------
  // Same browser: BroadcastChannel (instant). Another device (phone): relayed by server.py (/api/stream + /api/send).
  // ?nobc=1 turns the same-browser shortcut off, which is how the relay is tested.
  function makeBus(from) {
    const noBc = new URLSearchParams(location.search).has('nobc');
    const ch = !noBc && 'BroadcastChannel' in window ? new BroadcastChannel('carely') : null, seen = [], seenSet = new Set(), handlers = [];
    const cid = Math.random().toString(36).slice(2) + Date.now().toString(36);
    let relay = false, needPair = false;
    const remember = id => { seenSet.add(id); seen.push(id); if (seen.length > 3000) seenSet.delete(seen.shift()); };
    const deliver = m => { if (!m || !m._id || seenSet.has(m._id)) return; remember(m._id); handlers.forEach(h => h(m)); };
    if (ch) ch.onmessage = e => deliver(e.data);
    if (!noBc) window.addEventListener('storage', e => { if (e.key === 'carely-bus' && e.newValue) { try { deliver(JSON.parse(e.newValue)); } catch {} } });
    // another device must be paired once (6-digit code printed by server.py); this PC is trusted without a code
    const token = () => { try { return localStorage.getItem('carely-token') || ''; } catch { return ''; } };
    const tq = () => token() ? '&t=' + encodeURIComponent(token()) : '';
    function connect() {
      fetch('/api/ping?x=1' + tq(), { cache: 'no-store' }).then(r => r.ok ? r.json() : null).then(j => {
        if (!j || !j.carely) return;
        if (!j.authorized) { needPair = true; handlers.forEach(h => h({ type: '_pair', open: j.open, androidOnly: j.androidOnly, _id: 'p' + Date.now() })); return; }
        needPair = false; relay = true;
        const es = new EventSource('/api/stream?cid=' + cid + tq());      // reconnects by itself if the Wi-Fi blips
        es.onmessage = e => { try { deliver(JSON.parse(e.data)); } catch {} };
        es.onopen = () => handlers.forEach(h => h({ type: '_relay', up: true, _id: 'r' + Date.now() }));
      }).catch(() => {});
    }
    if (/^https?:$/.test(location.protocol)) connect();
    async function pair(pin) {
      try {
        const r = await fetch('/api/pair', { method: 'POST', body: JSON.stringify({ pin: String(pin).trim() }), headers: { 'Content-Type': 'application/json' } });
        const j = await r.json().catch(() => ({}));
        if (r.ok && j.token !== undefined) { try { if (j.token) localStorage.setItem('carely-token', j.token); } catch {} connect(); return { ok: true }; }
        return { ok: false, error: j.error || 'failed', wait: j.wait };
      } catch { return { ok: false, error: 'network' }; }
    }    return {
      send(m) {
        m = { ...m, _id: Date.now().toString(36) + Math.random().toString(36).slice(2), _from: from };
        remember(m._id);
        ch && ch.postMessage(m);
        if (!noBc && m.type !== 'state' && m.type !== 'frame') { try { localStorage.setItem('carely-bus', JSON.stringify(m)); } catch {} }
        if (relay) return fetch('/api/send?cid=' + cid + tq(), { method: 'POST', body: JSON.stringify(m), headers: { 'Content-Type': 'application/json' } }).catch(() => {});
      },
      on(h) { handlers.push(h); },
      get relay() { return relay; }, get needPair() { return needPair; }, pair,
    };
  }

  g.CARELY = { remote: {}, makeBus, PROGRAM, profile, saveProfile, readPhoto, avatar, makeRtc, mountCallUI, ICONS, CATS, EXERCISES, EX_BY_ID, dKey, TH_DOW, fmtDur, sitLimit, history, sample, summarize, evaluate, insights, stripEmoji, normalRange };
})(window);
