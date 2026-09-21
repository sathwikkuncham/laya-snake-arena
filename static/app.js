"use strict";
document.body.classList.toggle("capture", new URLSearchParams(location.search).has("capture"));
const $ = id => document.getElementById(id);
const token = document.querySelector('meta[name="app-token"]').content;
const canvas = $("board");
let current = null, pending = false, stopped = false, pollBusy = false, toastTimer;
let pacedFps = 8;
const fmt = value => String(value).padStart(2, "0");
const percent = value => `${(100 * value).toFixed(1)}%`;

function toast(message) {
  $("toast").textContent = message;
  $("toast").hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { $("toast").hidden = true; }, 4000);
}

function draw(game) { window.SnakeBoard.draw(canvas, game); }

function render(s) {
  current = s;
  const g = s.game, d = s.last;
  $("solo-engine-title").textContent = s.engine.label;
  $("solo-engine-legend").textContent = s.engine.label;
  $("solo-intro-copy").textContent = `Watch ${s.engine.label} choose its next move. Every step calls the selected engine.`;
  $("solo-engine-provider").textContent = s.engine.provider.toUpperCase();
  if (!window.snakeCompareVisible) $("connection-label").textContent = s.engine.caption.toUpperCase();
  $("hardware").textContent = s.hardware;
  $("score").textContent = fmt(g.score); $("length").textContent = fmt(g.length);
  $("moves").textContent = g.ticks; $("best").textContent = fmt(s.best);
  $("seed-label").textContent = `SEED ${g.seed} · ${g.width} × ${g.height}`;
  $("mode-label").textContent = s.guarded ? `${s.engine.label.toUpperCase()} + CYCLE SAFETY` : "RAW MODEL MOVES";
  $("shield").checked = s.guarded;
  $("shield-caption").textContent = s.guarded ? "Protects against unsafe proposals." : "Off. The model's first choice is executed.";
  if (document.activeElement !== $("speed")) $("speed").value = s.fps;
  $("interventions").textContent = s.interventions;
  $("rate").innerHTML = `${s.running ? s.rate.toFixed(1) : "—"} <small>moves/s</small>`;
  const fullSpeed = s.fps === 0;
  if (s.fps > 0) pacedFps = s.fps;
  $("full-speed-strip").classList.toggle("active", fullSpeed);
  $("full-speed").setAttribute("aria-pressed", String(fullSpeed));
  $("full-speed").textContent = fullSpeed ? "↙ Return to paced" : "↗ Run at full speed";
  $("full-speed").disabled = pending || !s.ready || !!s.error || !g.alive || g.won;
  $("full-speed-rate").innerHTML = `${s.running ? s.rate.toFixed(1) : "—"} <small>moves/s</small>`;
  $("speed-reading-label").textContent = s.running ? (fullSpeed ? "FULL SPEED · MEASURED" : "PACED · MEASURED") : "MEASURED GAME SPEED";
  $("full-speed-note").textContent = fullSpeed
    ? (s.running ? "No pace limit. Counts completed moves; the display may skip frames." : "Full speed selected. Press Resume to continue measuring.")
    : "Remove the pace limit to measure your computer's actual speed.";
  $("latency").innerHTML = `${d ? d.inference_ms.toFixed(0) : "—"} <small>ms</small>`;
  $("safe").textContent = d ? d.safe_count : "—";
  $("safe-prob").textContent = d ? percent(1 - d.dead_end_risk) : "—";
  $("food-prob").textContent = d ? percent(d.food_reachable) : "—";
  $("proposed").textContent = d ? d.proposed : "—";
  $("executed").textContent = d ? d.executed : "—";
  $("override").hidden = !d?.intervened;
  document.querySelectorAll(".direction").forEach(row => {
    const direction = row.dataset.direction;
    row.classList.toggle("selected", d?.proposed === direction);
    row.querySelector("strong").textContent = d ? percent(d.probabilities[direction]) : "—";
    row.querySelector(".track i").style.width = d ? percent(d.probabilities[direction]) : "0%";
  });
  $("error").hidden = !s.error; $("error").textContent = s.error || "";
  $("status").textContent = s.error ? "RUNTIME ERROR" : !s.ready ? "LOADING MODEL" : g.won ? "BOARD COMPLETED" : !g.alive ? "GAME OVER" : s.running ? "ENGINE PLAYING" : g.ticks ? "PAUSED" : "READY TO PLAY";
  $("play").textContent = s.running ? "Ⅱ Pause" : g.ticks ? "▶ Resume" : "▶ Start game";
  $("play").disabled = pending || !s.ready || !!s.error || !g.alive || g.won;
  $("step").disabled = pending || !s.ready || !!s.error || s.running || s.busy || !g.alive || g.won;
  $("export").disabled = !s.recorded;
  $("overlay").hidden = s.ready && !s.error && g.alive && !g.won && (s.running || g.ticks > 0);
  if (!s.ready) {
    $("overlay-kicker").textContent = "LOCAL MODEL"; $("overlay-title").textContent = `Preparing ${s.engine.label}`;
    $("overlay-copy").textContent = s.loading;
  } else if (!g.alive || g.won) {
    $("overlay-kicker").textContent = g.won ? "BOARD COMPLETE" : "ROUND FINISHED";
    $("overlay-title").textContent = g.won ? "Every square. Covered." : "The snake hit a " + g.death_reason;
    $("overlay-copy").textContent = `Score ${g.score} after ${g.ticks} moves. Choose New game to play again.`;
  } else {
    $("overlay-kicker").textContent = s.engine.caption.toUpperCase(); $("overlay-title").textContent = `${s.engine.label} is ready.`;
    $("overlay-copy").textContent = "Press Start game, or Step once to inspect a single decision.";
  }
  if (s.error) {
    $("overlay-title").textContent = "Game paused"; $("overlay-kicker").textContent = "RUNTIME ERROR";
    $("overlay-copy").textContent = "See the error above. Quit and reopen the app to retry.";
  }
  draw(g);
}

async function control(action, extra = {}) {
  if (pending || stopped) return false;
  let succeeded = false;
  pending = true;
  if (current) render(current);
  try {
    const res = await fetch("/api/control", {method: "POST", headers: {"Content-Type": "application/json", "X-App-Token": token}, body: JSON.stringify({action, ...extra})});
    const result = await res.json();
    if (!res.ok) throw new Error(result.error || "Action failed");
    current = result;
    succeeded = true;
  } catch (error) { toast(error.message); }
  finally { pending = false; if (current) render(current); }
  return succeeded;
}

$("play").addEventListener("click", () => control(current?.running ? "pause" : "start"));
$("step").addEventListener("click", () => control("step"));
$("reset").addEventListener("click", () => control("reset"));
$("speed").addEventListener("change", event => control("speed", {fps: Number(event.target.value)}));
$("full-speed").addEventListener("click", async () => {
  if (!current || pending) return;
  if (current.fps === 0) {
    await control("speed", {fps: pacedFps});
  } else if (await control("speed", {fps: 0})) {
    if (!current.running) await control("start");
  }
});
$("shield").addEventListener("change", event => control("shield", {enabled: event.target.checked}));
$("export").addEventListener("click", () => {
  const a = document.createElement("a"); a.href = "/api/recording"; a.download = "laya-snake-recording.json"; a.click();
});
$("quit").addEventListener("click", async () => {
  try {
    const res = await fetch("/api/shutdown", {method: "POST", headers: {"Content-Type": "application/json", "X-App-Token": token}, body: "{}"});
    if (!res.ok) throw new Error("Could not stop the app");
    stopped = true; document.body.classList.add("stopped");
    window.dispatchEvent(new Event("snake-shutdown"));
    $("status").textContent = "APP STOPPED"; $("overlay").hidden = false;
    $("overlay-kicker").textContent = "SESSION ENDED"; $("overlay-title").textContent = "See you next round.";
    $("overlay-copy").textContent = "The model is unloading. You can close this tab. Use the launcher to play again.";
    document.querySelectorAll("button,select,input").forEach(el => el.disabled = true);
  } catch (error) { toast(error.message); }
});
document.addEventListener("keydown", event => {
  if (window.snakeCompareVisible) return;
  if (event.repeat || /INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName) || !current || stopped) return;
  if (event.code === "Space") { event.preventDefault(); if (!$("play").disabled) $("play").click(); }
  if (event.key.toLowerCase() === "r") { event.preventDefault(); control("reset"); }
});

async function poll() {
  if (stopped || pollBusy) return;
  pollBusy = true;
  try {
    const res = await fetch("/api/state", {cache: "no-store", signal: AbortSignal.timeout(5000)});
    if (!res.ok) throw new Error("Server error");
    const value = await res.json();
    if (!pending) render(value);
  } catch (error) {
    if (!stopped) { $("error").hidden = false; $("error").textContent = "Connection lost. Reopen Start Laya Snake to reconnect."; $("play").disabled = $("step").disabled = true; }
  } finally { pollBusy = false; if (!stopped) setTimeout(poll, 100); }
}
poll();
window.SnakeSolo = {pause: () => control("pause")};
