/* El Fotobut - interfaz. El estado vive en Python (machine.py); aqui solo se dibuja. */
(() => {
  const $ = (s) => document.querySelector(s);
  const body = document.body;
  let snap = null, prev = {}, snapAt = performance.now();
  const params = new URLSearchParams(location.search);

  // ---------- focos de la marquesina ----------
  for (const id of ["#bulbs-top", "#bulbs-bot"]) {
    const el = $(id);
    for (let i = 0; i < 40; i++) { const s = document.createElement("span"); s.style.setProperty("--i", i); el.appendChild(s); }
  }

  // ---------- QR -> SVG (matriz de booleanos que manda el servidor) ----------
  function qrSvg(m) {
    const n = m.length, q = 2;
    let d = "";
    for (let y = 0; y < n; y++) {
      let x = 0;
      while (x < n) {
        if (m[y][x]) { let l = 1; while (x + l < n && m[y][x + l]) l++; d += `M${x + q},${y + q}h${l}v1h-${l}z`; x += l; } else x++;
      }
    }
    const t = n + 2 * q;
    return `<svg viewBox="0 0 ${t} ${t}" shape-rendering="crispEdges"><rect width="${t}" height="${t}" fill="#fff"/><path d="${d}" fill="#0b2e22"/></svg>`;
  }

  // ---------- helpers de animacion ----------
  function restart(el, cls) { el.classList.remove(cls); void el.offsetWidth; el.classList.add(cls); }
  function confetti() {
    const box = $("#confetti"), colors = ["#FF6A3D", "#FFD166", "#8EE3B0", "#FFF6E3", "#4cc9a0"];
    box.innerHTML = "";
    for (let i = 0; i < 70; i++) {
      const c = document.createElement("i");
      c.style.left = Math.random() * 100 + "%";
      c.style.background = colors[i % colors.length];
      c.style.setProperty("--dx", (Math.random() * 14 - 7) + "rem");
      c.style.setProperty("--rot", (Math.random() * 900 - 450) + "deg");
      c.style.animationDuration = (2.6 + Math.random() * 2.4) + "s";
      c.style.animationDelay = (Math.random() * .8) + "s";
      box.appendChild(c);
    }
    setTimeout(() => (box.innerHTML = ""), 6500);
  }

  // ---------- render ----------
  function buildFilters(list) {
    const ul = $("#filters");
    ul.innerHTML = list.map((f) => `<li><span class="sw" style="filter:${f.css}"></span>${f.name}</li>`).join("");
  }

  function setCam(on) {
    const cam = $("#cam");
    if (on && !cam.dataset.on) { cam.src = "/preview.mjpg?" + Date.now(); cam.dataset.on = "1"; }
    if (!on && cam.dataset.on) { cam.removeAttribute("src"); delete cam.dataset.on; }
  }

  function render(s) {
    const st = s.state, was = prev.state;
    body.dataset.state = st;
    body.style.setProperty("--flt", s.filter_css);
    $("#vf-filter").textContent = s.filters[s.filter_idx].name;
    if (!prev.filters) buildFilters(s.filters);
    [...$("#filters").children].forEach((li, i) => li.classList.toggle("on", i === s.filter_idx));
    const b = $("#badge-sim");
    b.hidden = !(s.sim || s.cam_sim);
    b.textContent = s.sim ? "SIMULACIÓN" : "SIN CÁMARA";
    $("#ssid").textContent = s.wifi.ssid;
    $("#wpass").textContent = s.wifi.pass;
    setCam(["READY", "COUNTDOWN", "CAPTURE"].includes(st));

    // cuenta regresiva
    if (st === "COUNTDOWN") {
      $("#shot-n").textContent = s.shot;
      if (s.count !== prev.count || was !== "COUNTDOWN") {
        $("#num").textContent = s.count;
        restart($("#num"), "pop");
        const r = $("#ring"); r.classList.remove("run"); void r.getBoundingClientRect(); r.classList.add("run");
      }
      $("#vf-msg").textContent = s.count === 1 ? "¡Sonríe!" : s.shot === 1 ? "¡Mira a la cámara!" : "¡Otra más, tú puedes!";
    }
    if (st === "CAPTURE") {
      $("#shot-n").textContent = s.shot;
      if (was !== "CAPTURE" || s.shot !== prev.shot) {
        restart($("#flash"), "go");
        $("#shot").src = s.photos[s.shot - 1] + "?" + Date.now();
      }
      $("#vf-msg").textContent = s.shot < s.shots ? `¡Foto ${s.shot}! Prepárate para la siguiente` : "¡Listo! Ya casi…";
    }
    // casillas de fotos
    document.querySelectorAll(".slot").forEach((el, i) => {
      const url = s.photos[i];
      if (url && el.dataset.u !== url) { el.style.backgroundImage = `url(${url})`; el.dataset.u = url; el.classList.add("full"); restart(el, "full"); }
      if (!url && el.dataset.u) { delete el.dataset.u; el.style.backgroundImage = ""; el.classList.remove("full"); }
    });
    document.querySelectorAll(".ph").forEach((el, i) => { if (s.photos[i]) el.style.backgroundImage = `url(${s.photos[i]})`; });

    // resultado
    if (st === "RESULT" && was !== "RESULT") {
      $("#strip").src = s.strip_url + "?" + Date.now();
      const ap = !!s.ap_active && !!s.qr_wifi;
      $("#card-wifi").hidden = !ap;
      $("#res-hint").hidden = !ap;
      $("#step-url").textContent = ap ? "2" : "1";
      $("#res-sub").textContent = ap ? "Llévatela en tu celular en dos pasos" : "Llévatela en tu celular: con tu celular en la misma red que la cabina, escanea";
      if (ap) $("#qr-wifi").innerHTML = qrSvg(s.qr_wifi);
      if (s.qr_url) $("#qr-url").innerHTML = qrSvg(s.qr_url);
      $("#url-txt").textContent = (s.share_url || "").replace("http://", "").replace(/\/s\/.*/, "");
      $("#strip").style.animation = "none"; void $("#strip").offsetWidth; $("#strip").style.animation = "";
      confetti();
    }
    if (st !== "RESULT") $("#confetti").innerHTML = "";

    if (params.has("debug")) {
      const d = $("#debug"); d.hidden = false;
      d.textContent = JSON.stringify({ state: s.state, pot: s.pot, filtro: s.filters[s.filter_idx].name, distancia_cm: s.distance, presente: s.present,
        uart_ok: s.uart_ok, hw: s.hw, telemetria: s.telemetry, camara_simulada: s.cam_sim, sesiones: s.sessions }, null, 1);
      if (!$("#oled-img")) { const im = document.createElement("img"); im.id = "oled-img"; $("#stage").appendChild(im); }
    }
    prev = { state: st, count: s.count, shot: s.shot, filters: true };
    snap = s; snapAt = performance.now();
  }

  // ---------- temporizadores locales (aviso de inactividad / anillo de resultado) ----------
  setInterval(() => {
    if (!snap || !snap.timeout_s) { $("#idle-note").textContent = ""; return; }
    const dt = performance.now() - snapAt;
    const left = Math.max(0, snap.timeout_s - (snap.age_ms + dt) / 1000);
    if (snap.state === "READY") {
      // READY se acaba por inactividad (nadie frente al sensor), no por tiempo en pantalla: se cuenta desde la ultima actividad
      const idle = Math.max(0, snap.timeout_s - ((snap.idle_ms || 0) + dt) / 1000);
      const show = !snap.present && idle < Math.min(12, snap.timeout_s - 1);
      const dest = snap.uart_ok ? "Entrando en reposo" : "Volviendo al inicio";
      $("#idle-note").textContent = show ? `¿Sigues ahí? ${dest} en ${Math.ceil(idle)} s…` : "";
    }
    if (snap.state === "RESULT") {
      $("#res-left").textContent = `o en ${Math.ceil(left)} s volvemos al inicio`;
      $("#rring").style.strokeDashoffset = 157 * (1 - left / snap.timeout_s);
    }
  }, 250);

  if (params.has("debug")) setInterval(() => { const im = $("#oled-img"); if (im) im.src = "/oled.png?" + Date.now(); }, 1500);

  // ---------- conexion SSE con reconexion ----------
  function connect() {
    const es = new EventSource("/events");
    es.onmessage = (e) => {
      const s = JSON.parse(e.data);
      // vision_gui vive, pero perdio a control_daemon (hardware): aviso discreto hasta que systemd lo levante
      $("#lost").textContent = "Reconectando sensores…";
      $("#lost").hidden = !(s.hw && s.hw.link === false);
      render(s);
    };
    es.onerror = () => { $("#lost").textContent = "Reconectando…"; $("#lost").hidden = false; es.close(); setTimeout(connect, 1000); };
  }
  connect();

  // ---------- simulador: teclado -> /api/sim ----------
  function sim(o) { fetch("/api/sim", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(o) }); }
  let potVal = 100, person = false;
  addEventListener("keydown", (e) => {
    if (!snap || !snap.sim) return;
    if (e.code === "Space") { e.preventDefault(); sim({ button: true }); }
    else if (e.key === "ArrowRight") { potVal = Math.min(1023, potVal + 64); sim({ pot: potVal }); }
    else if (e.key === "ArrowLeft") { potVal = Math.max(0, potVal - 64); sim({ pot: potVal }); }
    else if (/^[1-5]$/.test(e.key)) { potVal = Math.round((+e.key - .5) * 1024 / 5); sim({ pot: potVal }); }
    else if (e.key === "p" || e.key === "P") { person = !person; sim({ distance: person ? 80 : null }); }
    else if (e.key === "r" || e.key === "R") { sim({ reset: true }); }            // boton azul
    else if (e.key === "d" || e.key === "D") { $("#debug").hidden = !$("#debug").hidden; }
  });
  addEventListener("pointerdown", () => { if (snap && snap.sim) sim({ button: true }); });  // simulador: clic = boton
})();
