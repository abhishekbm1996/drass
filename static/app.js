(function () {
  "use strict";

  const VIEWS = ["landing", "active", "summary", "stats"];
  const CACHE_KEY = "drass_active_session";
  const MAX_SESSION_AGE_HOURS = 24;
  let currentSession = null;
  let distractionCount = 0;
  let timerInterval = null;
  let summaryData = null;
  let sessionPromise = null; // Resolves to real session when Start API returns

  const $ = (sel, el = document) => el.querySelector(sel);
  const $$ = (sel, el = document) => el.querySelectorAll(sel);

  function saveSessionCache() {
    if (!currentSession || currentSession.id === -1) return;
    try {
      localStorage.setItem(
        CACHE_KEY,
        JSON.stringify({
          id: currentSession.id,
          started_at: currentSession.started_at,
          distraction_count: distractionCount,
        })
      );
    } catch (_) {}
  }

  function clearSessionCache() {
    try {
      localStorage.removeItem(CACHE_KEY);
    } catch (_) {}
  }

  function loadSessionCache() {
    try {
      const raw = localStorage.getItem(CACHE_KEY);
      if (!raw) return null;
      const data = JSON.parse(raw);
      const started = new Date(data.started_at).getTime();
      const ageHours = (Date.now() - started) / (1000 * 60 * 60);
      if (ageHours > MAX_SESSION_AGE_HOURS) {
        clearSessionCache();
        return null;
      }
      return {
        session: { id: data.id, started_at: data.started_at },
        distractionCount: data.distraction_count || 0,
      };
    } catch (_) {
      return null;
    }
  }

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
      const play = () => {
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
      };
      if (ctx.state === "suspended") {
        ctx.resume().then(play);
      } else {
        play();
      }
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

  // --- Landing (optimistic: show UI first, then sync with server)
  $("#btn-start")?.addEventListener("click", async () => {
    const optimisticStartedAt = new Date().toISOString();
    currentSession = { id: -1, started_at: optimisticStartedAt };
    distractionCount = 0;
    $("#distraction-count").textContent = "0";
    showView("active");
    sessionPromise = api("POST", "/api/sessions");
    try {
      const session = await sessionPromise;
      currentSession = session;
      saveSessionCache();
    } catch (e) {
      console.error(e);
      currentSession = null;
      sessionPromise = null;
      clearSessionCache();
      showView("landing");
    }
  });

  // --- Active: distraction (optimistic: update UI first, sync in background)
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
    const prevCount = distractionCount;
    distractionCount += 1;
    $("#distraction-count").textContent = String(distractionCount);
    try {
      let sessionId = currentSession.id;
      if (sessionId === -1 && sessionPromise) {
        const session = await sessionPromise;
        sessionId = session.id;
        currentSession = session;
      }
      if (sessionId !== -1) {
        await api("POST", `/api/sessions/${sessionId}/distractions`);
        saveSessionCache();
      }
    } catch (e) {
      console.error(e);
      distractionCount = prevCount;
      $("#distraction-count").textContent = String(distractionCount);
    }
  });

  // --- Active: end session (optimistic: show summary from local data first, sync in background)
  $("#btn-end")?.addEventListener("click", async () => {
    if (!currentSession) return;
    stopTimer();
    let sessionToEnd = currentSession;
    if (sessionToEnd.id === -1 && sessionPromise) {
      try {
        sessionToEnd = await sessionPromise;
        currentSession = sessionToEnd;
      } catch (_) {
        return;
      }
    }
    if (sessionToEnd.id === -1) return;
    const localDistractionCount = distractionCount;
    const localDuration = elapsedSeconds(sessionToEnd.started_at);
    currentSession = null;
    distractionCount = 0;
    sessionPromise = null;
    clearSessionCache();
    summaryData = {
      duration_seconds: localDuration,
      distraction_count: localDistractionCount,
      longest_streak_seconds: 0,
    };
    $("#summary-duration").textContent = formatDuration(localDuration);
    $("#summary-distractions").textContent = String(localDistractionCount);
    $("#summary-streak").textContent = "—";
    showView("summary");
    try {
      await api("PATCH", `/api/sessions/${sessionToEnd.id}`);
      summaryData = await api("GET", `/api/sessions/${sessionToEnd.id}/summary`);
      $("#summary-duration").textContent = formatDuration(summaryData.duration_seconds);
      $("#summary-distractions").textContent = String(summaryData.distraction_count);
      $("#summary-streak").textContent = formatStreak(summaryData.longest_streak_seconds);
    } catch (e) {
      console.error(e);
      currentSession = sessionToEnd;
      distractionCount = localDistractionCount;
      showView("active");
      startTimer();
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

  // --- Init: restore from cache immediately (no landing flash), then validate with API
  (function init() {
    const cached = loadSessionCache();
    if (cached) {
      currentSession = cached.session;
      distractionCount = cached.distractionCount;
      const el = $("#distraction-count");
      if (el) el.textContent = String(distractionCount);
      if (window.location.hash === "#stats") {
        showView("stats");
      } else {
        showView("active");
      }
    } else if (window.location.hash === "#stats") {
      showView("stats");
    } else {
      showView("landing");
    }
    api("GET", "/api/sessions/active")
      .then((data) => {
        currentSession = { id: data.id, started_at: data.started_at };
        distractionCount = data.distraction_count || 0;
        const el = $("#distraction-count");
        if (el) el.textContent = String(distractionCount);
        saveSessionCache();
        if (window.location.hash === "#stats") {
          showView("stats");
        } else {
          showView("active");
        }
      })
      .catch(() => {
        currentSession = null;
        distractionCount = 0;
        clearSessionCache();
        if (window.location.hash === "#stats") {
          showView("stats");
        } else {
          showView("landing");
        }
      });
  })();
})();
