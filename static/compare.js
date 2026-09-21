"use strict";
(() => {
  const el = id => document.getElementById(id);
  const token = document.querySelector('meta[name="app-token"]').content;
  let state = null, pending = false, visible = false, pollTimer = null;
  let engineIds = [], engineSignature = "";
  const selectedNames = () => state?.mode === "both" ? engineIds : [state?.mode || engineIds[0]];
  const number = value => value == null ? "—" : Number(value).toFixed(1);
  const names = {};
  const statusText = {ready: "READY", preparing: "PREPARING", running: "RUNNING AT FULL SPEED", paused: "PAUSED", finished: "COMPLETE", game_over: "GAME OVER", error: "REQUEST FAILED"};
  function ensureEngines(s) {
    const signature=JSON.stringify(s.engines);
    if(signature===engineSignature)return;
    engineSignature=signature;engineIds=s.engines.map(e=>e.id);
    el("compare-grid").replaceChildren();el("compare-models").replaceChildren();
    el("compare-models").add(new Option(engineIds.length===2?"Both · side by side":"All engines · side by side","both"));
    const title=s.engines.length===2?`${s.engines[0].label} meets ${s.engines[1].label}.`:"One board. Different engines.";
    el("compare-heading").textContent=title;
    for (const engine of s.engines) {
    const name=engine.id;names[name]=engine.label;
    el("compare-models").add(new Option(`${engine.label} · ${engine.caption}`,name));
    const card = document.createElement("article");
    card.className = "compare-card";
    card.style.setProperty("--engine-color", engine.color);
    card.id = `card-${name}`;
    card.innerHTML = `<div class="compare-card-head"><div><span class="eyebrow"><span id="${name}-caption"></span></span><h2><span id="${name}-label"></span> <span class="pill" id="${name}-provider"></span></h2><p id="${name}-model"></p></div><span class="lane-status" id="${name}-status">READY</span></div>
      <div class="race-progress"><i id="${name}-progress"></i></div>
      <div class="compare-top-metrics"><div><span>SCORE</span><strong id="${name}-score">00</strong></div><div><span>MOVES</span><strong id="${name}-moves">0 / 300</strong></div><div class="throughput"><span>AVERAGE SPEED</span><strong id="${name}-speed">— <small>moves/s</small></strong></div></div>
      <div class="board-wrap"><canvas id="${name}-board" width="960" height="640" role="img" aria-label="Snake board"></canvas></div>
      <div class="board-footer"><span><i class="legend-snake"></i> <span id="${name}-legend"></span> <i class="legend-food"></i> Food</span><span id="${name}-elapsed">0.0 s elapsed</span></div>
      <div class="compare-latencies"><div><span>Last request</span><strong id="${name}-last">— <small>ms</small></strong></div><div><span>Median request</span><strong id="${name}-median">— <small>ms</small></strong></div><div><span>P95 request</span><strong id="${name}-p95">— <small>ms</small></strong></div><div><span>Shield overrides</span><strong id="${name}-shield">0</strong></div></div>
      <div class="compare-probabilities" id="${name}-probabilities">${["UP","DOWN","LEFT","RIGHT"].map(direction=>`<div data-direction="${direction}"><div><span>${direction}</span><strong>—</strong></div><div class="track"><i></i></div></div>`).join("")}</div>
      <div class="compare-decision"><span>ENGINE <b id="${name}-proposed">—</b> → EXECUTED <b id="${name}-executed">—</b></span><span id="${name}-tokens">0 input tokens</span></div><p class="lane-error" id="${name}-error" role="alert" hidden></p>`;
    el("compare-grid").appendChild(card);
    el(`${name}-label`).textContent=engine.label;
    el(`${name}-caption`).textContent=engine.caption.toUpperCase();
    el(`${name}-provider`).textContent=engine.provider.toUpperCase();
    el(`${name}-legend`).textContent=engine.label;
    }
  }

  function render(s) {
    state = s;
    ensureEngines(s);
    for (const [id,value] of [["compare-models",s.mode],["compare-seed",s.seed],["compare-limit",s.limit]]) {
      if (document.activeElement !== el(id)) el(id).value = value;
      el(id).disabled = pending || s.active;
    }
    el("compare-limit").max=s.max_moves;
    el("compare-shield").checked = s.guarded;
    el("compare-shield").disabled = pending || s.active;
    el("compare-grid").classList.toggle("single-engine", s.mode !== "both");
    const boardSize=s.lanes[engineIds[0]].game;
    document.querySelector(".comparison-method span").textContent=`${boardSize.width} × ${boardSize.height} board · 3 questions per move · No pacing delay`;
    const selected = selectedNames().map(n => s.lanes[n]);
    const finished = selected.every(l => ["finished","game_over","error"].includes(l.state));
    el("compare-start").disabled = pending || s.active || finished || (selectedNames().includes(s.solo_engine) && !s.solo_ready);
    el("compare-start").textContent = selected.some(l=>l.game.ticks>0) ? "▶ Resume comparison" : "▶ Start comparison";
    el("compare-pause").disabled = pending || !s.active || s.pausing;
    el("compare-pause").textContent = s.pausing ? "Finishing request…" : "Ⅱ Pause";
    el("compare-reset").disabled = pending || s.active;
    el("compare-export").disabled = !selected.some(l=>l.game.ticks>0);
    el("compare-connection").textContent = selectedNames().every(n=>s.lanes[n].engine.provider === "ggmlc") ? "Runs locally. No TypeSafe requests." : "3 questions per request · Credentials handled server-side";
    if (visible) {
      el("connection-label").textContent = "DECISION ENGINE COMPARISON";
      el("footer-runtime").textContent = "Configured decision engines";
    }
    for (const name of engineIds) {
      const lane = s.lanes[name], game = lane.game, d = lane.last;
      el(`card-${name}`).hidden = !lane.selected;
      el(`${name}-model`).textContent = lane.model;
      el(`${name}-status`).textContent = statusText[lane.state] || lane.state;
      el(`${name}-status`).dataset.state = lane.state;
      el(`${name}-score`).textContent = String(game.score).padStart(2,"0");
      el(`${name}-moves`).textContent = `${game.ticks} / ${s.limit}`;
      el(`${name}-speed`).innerHTML = `${game.ticks ? number(lane.average_rate) : "—"} <small>moves/s</small>`;
      el(`${name}-last`).innerHTML = `${number(d?.inference_ms)} <small>ms</small>`;
      el(`${name}-median`).innerHTML = `${number(lane.median_ms)} <small>ms</small>`;
      el(`${name}-p95`).innerHTML = `${number(lane.p95_ms)} <small>ms</small>`;
      el(`${name}-elapsed`).textContent = `${number(lane.elapsed_s)} s elapsed`;
      el(`${name}-shield`).textContent = lane.interventions;
      el(`${name}-progress`).style.width = `${100*game.ticks/s.limit}%`;
      el(`${name}-proposed`).textContent = d?.proposed || "—";
      el(`${name}-executed`).textContent = d?.executed || "—";
      el(`${name}-tokens`).textContent = `${lane.input_tokens.toLocaleString()} input tokens`;
      el(`${name}-error`).hidden = !lane.error;
      el(`${name}-error`).textContent = lane.error || "";
      el(`${name}-probabilities`).querySelectorAll("[data-direction]").forEach(row=> {
        const value = d?.probabilities[row.dataset.direction];
        row.querySelector("strong").textContent = value == null ? "—" : `${(value*100).toFixed(1)}%`;
        row.querySelector(".track i").style.width = `${(value||0)*100}%`;
        row.classList.toggle("chosen", d?.proposed === row.dataset.direction);
      });
      window.SnakeBoard.draw(el(`${name}-board`),game);
      el(`${name}-board`).setAttribute("aria-label", `${names[name]} board: score ${game.score}, ${game.ticks} moves, ${statusText[lane.state]}`);
    }
    const rates=selectedNames().map(n=>`${names[n]} ${number(s.lanes[n].average_rate)} moves/s`).join(" · ");
    const anyMoves=selected.some(l=>l.game.ticks>0);
    el("compare-summary").textContent = anyMoves
      ? `${finished?"Run ended":"In progress"}: ${rates}. ${finished?"Export the decisions to inspect the result.":"Wait for all engines to finish before comparing final rates."}`
      : "Same seed, same move budget. Start a run to measure your selected engines.";

  }

  async function command(action, extra={}) {
    if (pending) return false;
    pending=true;
    if(state) render(state);
    try {
      const res=await fetch("/api/compare/control",{method:"POST",headers:{"Content-Type":"application/json","X-App-Token":token},body:JSON.stringify({action,...extra})});
      const data=await res.json();
      if(!res.ok) throw new Error(data.error||"Comparison request failed");
      el("compare-error").hidden=true;
      state=data;
      return true;
    } catch(error) {
      el("compare-error").hidden=false;
      el("compare-error").textContent=error.message;
      return false;
    } finally {pending=false;if(state)render(state);}
  }

  async function poll() {
    clearTimeout(pollTimer);
    if(!visible) return;
    try {
      const res=await fetch("/api/compare/state",{signal:AbortSignal.timeout(5000),cache:"no-store"});
      if(!res.ok) throw new Error("Cannot load comparison. Restart the app to load the update.");
      const data=await res.json();
      if(!pending)render(data);
    } catch(error) {el("compare-error").hidden=false;el("compare-error").textContent=error.message;}
    if(visible)pollTimer=setTimeout(poll,150);
  }

  async function switchMode(compare) {
    if(pending) return;
    if(compare) {
      await window.SnakeSolo.pause();
    } else if(state?.active) {
      await command("pause");
    }
    visible=compare;
    window.snakeCompareVisible=compare;
    el("solo-view").hidden=compare;el("compare-view").hidden=!compare;
    el("mode-solo").setAttribute("aria-pressed",String(!compare));
    el("mode-compare").setAttribute("aria-pressed",String(compare));
    el("export").hidden=compare;
    if(compare)poll();
    else {clearTimeout(pollTimer);el("connection-label").textContent="LOCAL INFERENCE";el("footer-runtime").textContent="Runs on your computer";}
  }
  el("mode-compare").addEventListener("click",()=>switchMode(true));
  el("mode-solo").addEventListener("click",()=>switchMode(false));
  el("compare-start").addEventListener("click",()=>command("start"));
  el("compare-pause").addEventListener("click",()=>command("pause"));
  el("compare-reset").addEventListener("click",()=>command("reset"));
  for(const id of ["compare-models","compare-seed","compare-limit","compare-shield"]) {
    el(id).addEventListener("change",()=>command("configure",{mode:el("compare-models").value,seed:Number(el("compare-seed").value),limit:Number(el("compare-limit").value),guarded:el("compare-shield").checked}));
  }
  el("compare-export").addEventListener("click",()=>{const a=document.createElement("a");a.href="/api/compare/recording";a.download="snake-engine-comparison.json";a.click();});
  window.addEventListener("snake-shutdown",()=>{
    visible=false;clearTimeout(pollTimer);
    el("compare-summary").textContent="App stopped. You can close this tab; use the launcher to reopen it.";
  });
  document.addEventListener("keydown",event=>{
    if(!visible||!state||event.repeat||/INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName))return;
    if(event.code==="Space"){event.preventDefault();if(state.active)command("pause");else if(!el("compare-start").disabled)command("start");}
  });
})();
