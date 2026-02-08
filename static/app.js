(function () {
  "use strict";

  const VIEWS = ["landing", "active", "summary", "stats"];
  let currentSession = null;
  let distractionCount = 0;
  let timerInterval = null;
  let summaryData = null;

  const $ = (sel, el = document) => el.querySelector(sel);
  const $$ = (sel, el = document) => el.querySelectorAll(sel);

  function showView(name) {
    VIEWS.forEach((v) => {
      const el = document.getElementById("view-" + v);
      if (el) el.classList.toggle("hidden", v !== name);
    });
    if (name === "active" && currentSession) startTimer();
    if (name === "stats") loadStats();
  }

  function formatDuration(seconds) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
    return `${m}:${String(s).padStart(2, "0")}`;
  }

  function formatStreak(seconds) {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    const m = Math.floor(seconds / 60);
    const s = Math.round(seconds % 60);
    if (m < 60) return s > 0 ? `${m}m ${s}s` : `${m}m`;
    const h = Math.floor(m / 60);
    const mm = m % 60;
    return mm > 0 ? `${h}h ${mm}m` : `${h}h`;
  }

  function elapsedSeconds(startedAtIso) {
    const start = new Date(startedAtIso).getTime();
    return (Date.now() - start) / 1000;
  }

  function updateTimerDisplay() {
    if (!currentSession) return;
    const el = $("#timer-display");
    if (el) el.textContent = formatDuration(elapsedSeconds(currentSession.started_at));
  }

  function startTimer() {
    if (timerInterval) clearInterval(timerInterval);
    updateTimerDisplay();
    timerInterval = setInterval(updateTimerDisplay, 1000);
  }

  function stopTimer() {
    if (timerInterval) {
      clearInterval(timerInterval);
      timerInterval = null;
    }
  }

  function playClickBeep() {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.frequency.value = 400;
      osc.type = "sine";
      gain.gain.setValueAtTime(0.15, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.08);
      osc.start(ctx.currentTime);
      osc.stop(ctx.currentTime + 0.08);
    } catch (_) {}
  }

  async function api(method, path, body) {
    const opts = { method, headers: {} };
    if (body) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    const res = await fetch(path, opts);
    if (!res.ok) throw new Error(await res.text());
    return res.json ? res.json() : null;
  }

  // --- Landing
  $("#btn-start")?.addEventListener("click", async () => {
    try {
      const session = await api("POST", "/api/sessions");
      currentSession = session;
      distractionCount = 0;
      $("#distraction-count").textContent = "0";
      showView("active");
    } catch (e) {
      console.error(e);
    }
  });

  // --- Active: distraction
  $("#btn-distraction")?.addEventListener("click", async () => {
    if (!currentSession) return;
    playClickBeep();
    const btn = document.getElementById("btn-distraction");
    if (btn) {
      btn.classList.remove("btn-distraction--pulse");
      btn.offsetHeight;
      btn.classList.add("btn-distraction--pulse");
      setTimeout(() => btn.classList.remove("btn-distraction--pulse"), 350);
    }
    try {
      await api("POST", `/api/sessions/${currentSession.id}/distractions`);
      distractionCount += 1;
      $("#distraction-count").textContent = String(distractionCount);
    } catch (e) {
      console.error(e);
    }
  });

  // --- Active: end session
  $("#btn-end")?.addEventListener("click", async () => {
    if (!currentSession) return;
    stopTimer();
    try {
      await api("PATCH", `/api/sessions/${currentSession.id}`);
      summaryData = await api("GET", `/api/sessions/${currentSession.id}/summary`);
      currentSession = null;
      distractionCount = 0;

      $("#summary-duration").textContent = formatDuration(summaryData.duration_seconds);
      $("#summary-distractions").textContent = String(summaryData.distraction_count);
      $("#summary-streak").textContent = formatStreak(summaryData.longest_streak_seconds);
      showView("summary");
    } catch (e) {
      console.error(e);
    }
  });

  // --- Summary: back
  $("#btn-back")?.addEventListener("click", () => {
    summaryData = null;
    showView("landing");
  });

  // --- Stats
  function loadStats() {
    api("GET", "/api/stats")
      .then((data) => {
        $("#stat-sessions").textContent = String(data.today_sessions);
        $("#stat-per-hour").textContent = String(data.today_distractions_per_hour);
        $("#stat-streak").textContent =
          data.today_longest_streak_seconds > 0
            ? formatStreak(data.today_longest_streak_seconds)
            : "—";
        const list = $("#trend-list");
        if (list) {
          list.innerHTML = "";
          (data.last_7_days || []).forEach((day) => {
            const div = document.createElement("div");
            div.className = "trend-day";
            div.innerHTML = `<span>${day.date}</span><span>${day.session_count} sessions, ${day.total_distractions} distractions, ${formatStreak(day.longest_streak_seconds)} streak</span>`;
            list.appendChild(div);
          });
        }
      })
      .catch((e) => console.error(e));
  }

  $("#link-back-from-stats")?.addEventListener("click", (e) => {
    e.preventDefault();
    window.location.hash = "";
    showView(currentSession ? "active" : "landing");
  });

  // --- Hash routing
  function onHashChange() {
    if (window.location.hash === "#stats") {
      showView("stats");
      return;
    }
    if (currentSession) showView("active");
    else showView("landing");
  }

  window.addEventListener("hashchange", onHashChange);

  // --- Service worker (served at root so scope / works for PWA)
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/service-worker.js", { scope: "/" });
  }

  // --- Init: always restore active session first, then show view (so Back from stats shows active)
  (function init() {
    api("GET", "/api/sessions/active")
      .then((data) => {
        currentSession = { id: data.id, started_at: data.started_at };
        distractionCount = data.distraction_count || 0;
        const el = $("#distraction-count");
        if (el) el.textContent = String(distractionCount);
        if (window.location.hash === "#stats") {
          showView("stats");
        } else {
          showView("active");
        }
      })
      .catch(() => {
        if (window.location.hash === "#stats") {
          showView("stats");
        } else {
          showView(currentSession ? "active" : "landing");
        }
      });
  })();
})();
