/* Local UX-01 prototype. All state is synthetic and remains in this page. */
"use strict";
const ui = { page: "live", state: "Recording", data: "Populated", view: "latest", pitch: 5 };
const states = {
  Idle: ["Prepare Session", "No camera preview or recording requested."],
  Preview: ["Complete Setup", "Cameras live · recording blocked until the named checks pass."],
  Ready: ["Start Recording", "Preparation checked · cameras live · no pitches are being saved."],
  Recording: ["Pause", "Cameras live · recording pitches · estimated measurements."],
  Paused: ["Resume Recording", "Recording paused · cameras remain live · pitches are not being saved."],
  Finalizing: ["Finalizing…", "Accepted pitch analysis and artifact writes are draining. Keep the app open."],
  Completed: ["Review Session", "Session finalized · recorded artifacts ready for review."],
  Error: ["Retry End Session", "End Session failed · last confirmed state: Recording. Recording may still be active."]
};
const pitches = [71.2, 72.4, 71.8, 73.0, 72.6];
const content = document.getElementById("page-content");
const stage = document.getElementById("stage");
const badge = (text, tone="") => `<span class="badge ${tone}">${text}</span>`;
const title = (name, detail, extra="") => `<div class="page-title"><div><h1>${name}</h1><p class="subtext">${detail}</p></div>${extra}</div>`;
const preview = () => `<div class="preview"><div><svg viewBox="0 0 500 180" aria-label="Synthetic camera schematic"><path d="M30 170L250 30L470 170" fill="none" stroke="#475569" stroke-width="2"/><rect x="213" y="75" width="74" height="96" fill="none" stroke="#94a3b8"/><circle cx="258" cy="123" r="5" fill="#60a5fa"/></svg><span>Synthetic camera schematic · no footage</span></div></div>`;
const trend = () => `<svg class="trend" viewBox="0 0 600 190" role="img" aria-label="Synthetic velocity trend: 71.2, 72.4, 71.8, 73.0 and 72.6 miles per hour"><path d="M50 20V150H580" fill="none" stroke="#d7e0ea"/><path d="M50 110L180 63L310 87L440 40L570 55" fill="none" stroke="#2563eb" stroke-width="3"/><g fill="#475569" font-size="12"><text x="12" y="32">74</text><text x="12" y="92">72</text><text x="12" y="152">70</text><text x="240" y="182">Pitch number (1–5) · mph</text></g></svg>`;
function pitchTable(selectable=false) {
  return `<table><caption class="subtext">Synthetic pitch results · all measurements estimated</caption><thead><tr><th>Pitch</th><th>Velocity</th><th>Outcome</th>${selectable?"<th>Review</th>":""}</tr></thead><tbody>${pitches.map((speed,i)=>`<tr><td>#${i+1}</td><td class="numeric">${speed.toFixed(1)} mph</td><td>${i===2?"Ball":"Strike"}</td>${selectable?`<td><button data-pitch="${i+1}" aria-pressed="${ui.pitch===i+1}">Select #${i+1}</button></td>`:""}</tr>`).join("")}</tbody></table>`;
}
function live() {
  const unavailable = ["Unavailable", "Rejected"].includes(ui.data);
  const empty = ui.data==="Empty" || ["Idle","Ready","Preview"].includes(ui.state);
  let body;
  if (ui.view==="trends") {
    body = empty ? `<div class="empty"><h2>No session trends yet</h2><p>Recorded pitches will appear here.</p></div>` : `<section class="panel"><h2>Session velocity</h2>${trend()}${pitchTable()}</section>`;
  } else if (ui.view==="games") {
    body = `<section class="panel"><h2>Practice games</h2><p>Existing game modes stay available here. Unavailable pitches do not count as attempts.</p><button data-dialog="games">Choose a practice game</button></section>`;
  } else {
    body = `<div class="live-grid"><section class="panel"><div class="eyebrow">LATEST PITCH ${empty?"":"· #5"}</div><div class="metric-number">${empty||unavailable?"—":"72.6"}<span>mph</span></div><div class="measurement-detail">${empty?"Waiting for the first recorded pitch.":unavailable?"Measurement unavailable · insufficient accepted observations.":"Vision fit · first observed point · estimated"}</div><p class="outcome">${empty?"No result yet":unavailable?ui.data:"Strike"}</p><div class="zone-wrap"><div class="zone" role="img" aria-label="${empty||unavailable?"No accepted pitch location":"Synthetic pitch location near the center of the zone"}">${empty||unavailable?"":'<span class="pitch-dot"></span>'}</div><div><h3>Plate location</h3><p class="subtext">${empty?"Waiting for a pitch":unavailable?"No accepted location":"Estimated · synthetic example"}</p><p class="subtext">Movement unavailable<br>Validation evidence required</p></div></div></section><section class="panel"><h2>${ui.state==="Idle"?"Camera preview":"Live camera"}</h2>${ui.state==="Idle"?'<div class="preview"><span>No camera preview requested</span></div>':preview()}<div class="preview-controls"><button aria-pressed="true" data-dialog="camera">Left camera</button><button data-dialog="camera">Right camera</button><button class="ghost" data-dialog="replay">Replay last pitch</button></div><p class="measurement-detail">Recording and preview are separate controls.</p></section></div><section class="recent"><h2>Recent pitches</h2>${empty?'<p class="subtext">Your recorded pitches will appear here.</p>':unavailable?'<p class="subtext">Latest attempt retained · outcome unavailable · no strike/ball call.</p>':pitchTable()}</section>`;
  }
  return title("Live", "See the latest pitch, then decide what to adjust.", '<button data-dialog="advanced">Advanced tools</button>') + `<div class="tabs" aria-label="Live views"><button data-view="latest" aria-pressed="${ui.view==="latest"}">Latest Pitch</button><button data-view="trends" aria-pressed="${ui.view==="trends"}">Session Trends</button><button data-view="games" aria-pressed="${ui.view==="games"}">Games</button></div>` + body;
}
function sessions() {
  if(ui.data==="Empty") return title("Sessions","Completed sessions and their recorded pitches.")+'<div class="empty"><h2>No completed sessions yet</h2><p>End and finalize a recording to review it here.</p><button data-page="live">Go to Live</button></div>';
  return title("Sessions", "Historical selection · separate from your active recording.") + `<div class="session-grid"><section><h2>Completed sessions</h2><button class="session-entry" aria-pressed="true" data-dialog="history"><strong>Example Pitcher</strong><small>Synthetic bullpen · Oct 13<br>5 pitches · finalized</small></button><button data-dialog="open">Open local session</button><button data-dialog="analytics">Session summary</button></section><section class="panel"><h2>Synthetic bullpen · Pitch #${ui.pitch}</h2>${preview()}<div class="preview-controls"><button data-dialog="playback">Play / Pause</button><button data-step="-1">Previous pitch</button><button data-step="1">Next pitch</button><button data-dialog="export">Export selected pitch</button></div><div class="inline-metrics"><div><span class="eyebrow">VELOCITY</span><strong>${["Unavailable","Rejected"].includes(ui.data)?"—":pitches[ui.pitch-1].toFixed(1)} mph</strong></div><div><span class="eyebrow">OUTCOME</span><strong>${["Unavailable","Rejected"].includes(ui.data)?"Unavailable":ui.pitch===3?"Ball":"Strike"}</strong></div><div>${badge("Estimated")}<p class="subtext">Vision · first observed point</p></div></div>${pitchTable(true)}<details><summary>Advanced review tools</summary><p>Detection tuning, trajectory diagnostics, research annotation and refitting are explicit tasks. Reprocessing is unavailable while capture is active.</p></details></section></div>`;
}
function players() {
  return title("Players", "Browsing a player does not change the active session pitcher.", '<button data-dialog="add-player">Add Player</button>') + (ui.data==="Empty" ? '<div class="empty"><h2>No players yet</h2><p>Add a player to prepare your first session.</p><button data-dialog="add-player">Add Player</button></div>' : `<div class="player-list">${["Example Pitcher","Sample Pitcher"].map((name,i)=>`<section class="panel player-row"><div><h2>${name}</h2><p class="subtext">${i===0?"Active pitcher · 1 synthetic completed session":"No recorded sessions in this example"}</p></div><div><button data-page="sessions">View Sessions</button><button data-dialog="switch-player">Use for Next Pitch</button></div></section>`).join("")}</div><p class="measurement-detail">Changing the pitcher is an explicit session command at a safe pitch boundary.</p>`);
}
function setup() {
  const busy=["Preview","Ready","Recording","Paused","Finalizing","Error"].includes(ui.state);
  return title("Setup", "Saved rig configuration, checks and research recording readiness.") + `<div class="setup-steps"><span>1 · Cameras</span><span>2 · Image checks</span><span>3 · Calibration</span><span>4 · Field and regions</span><span>5 · Ready</span></div><div class="notice ${busy?"warning-notice":""}">${busy?"Runtime capture owns this rig. Setup is view-only. Use explicit session and preview controls before editing.":"Valid changes save immediately. Affected checks must pass again before recording."}</div><div class="setup-grid"><section class="panel"><h2>Cameras</h2><p class="subtext">Synthetic saved rig · no hardware acquisition</p><label class="form-field">Left camera<input value="Simulated left" readonly></label><label class="form-field">Right camera<input value="Simulated right" readonly></label><div class="preview-controls"><button data-dialog="setup" ${busy?'disabled title="Runtime capture owns the rig"':""}>Discover Cameras</button><button data-dialog="setup" ${busy?'disabled title="Runtime capture owns the rig"':""}>Preview Selected Cameras</button></div></section><section class="panel"><h2>Checks and next steps</h2><p>${badge("Needs checks", "warning")}</p><p class="subtext">Image checks, metric calibration and field references must pass for the current saved revision.</p><button data-page="live">Return to Live</button><details><summary>Saved configuration details</summary><p>Generations, evidence fingerprints and structured diagnostics remain available here.</p></details><p class="measurement-detail">Passing setup enables estimated research recording. Independent physical qualification is required for accuracy approval.</p></section></div>`;
}
function render() {
  document.getElementById("fixture-state").value=ui.state;
  document.getElementById("recording-state").textContent=ui.state==="Error"?"Error · Recording":ui.state;
  document.getElementById("recording-state").className="badge "+(ui.state==="Error"?"error":ui.state==="Paused"?"warning":ui.state==="Recording"?"recording":"");
  const action=document.getElementById("primary-action"); action.textContent=states[ui.state][0]; action.disabled=ui.state==="Finalizing";
  document.getElementById("state-detail").textContent=states[ui.state][1];
  document.getElementById("end-action").hidden=!["Recording","Paused"].includes(ui.state);
  document.getElementById("active-session").textContent=ui.state==="Idle"?"No active session":"Synthetic bullpen";
  document.getElementById("session-context").textContent=ui.state==="Completed"?"LAST COMPLETED SESSION":ui.state==="Idle"?"SESSION":"ACTIVE SESSION";
  document.getElementById("active-player").textContent=ui.state==="Idle"?"Choose a pitcher to prepare":"Example Pitcher";
  const checkedRig=["Ready","Recording","Paused","Finalizing","Completed","Error"].includes(ui.state);
  document.querySelector(".rig-status").textContent=checkedRig?"Rig · research ready":"Rig · needs checks";
  document.querySelectorAll("nav [data-page]").forEach(b=>b.setAttribute("aria-current",b.dataset.page===ui.page?"page":"false"));
  content.innerHTML=({live,sessions,players,setup})[ui.page]();
  if(ui.page==="setup" && checkedRig) {
    const readiness=content.querySelector(".setup-grid .badge");
    readiness.textContent="Research ready"; readiness.className="badge";
    readiness.parentElement.nextElementSibling.textContent="Saved revision checks passed. Runtime ownership must be released through explicit controls before edits.";
  }
  if(ui.page==="sessions" && ["Unavailable","Rejected"].includes(ui.data)) {
    const quality=content.querySelector(".inline-metrics .badge");
    if(quality) {quality.textContent=ui.data;quality.nextElementSibling.textContent="No accepted measurement for this selection.";}
  }
}
const dialogs = {
  settings:["Settings",'<p>Session preferences and supported application settings use shared form controls. Rig changes belong in Setup.</p><label class="form-field">Ball type<select><option>Baseball</option><option>Softball</option></select></label><p class="subtext">Design example only; values are not saved.</p>'],
  help:["Help",'<p>Context help links to maintained operator guidance.</p><p><a href="../../OPERATOR_RUNBOOK.md">Operator runbook</a> · <a href="../../GUIDED_SETUP.md">Guided setup</a></p>'],
  advanced:["Advanced tools",'<p>Capture diagnostics, detector trials and research comparisons stay available as explicit tasks with existing admission checks.</p>'],
  analytics:["Session summary",`<div class="stat-strip"><div><strong>5</strong>Attempts</div><div><strong>72.2</strong>Average mph</div><div><strong>4 / 5</strong>Accepted strikes</div></div>${trend()}<p class="subtext">Synthetic example · estimated measurements. Missing and rejected attempts remain in reported denominators.</p>${pitchTable()}`],
  "add-player":["Add Player",'<label class="form-field">Player name<input placeholder="Enter a player name"></label><p class="subtext">Design example; no roster changes are saved.</p>'],
  "switch-player":["Change active pitcher",'<p>Request a pitcher change through the session owner. Apply it at a safe pitch boundary; the current pitch retains its attribution.</p>'],
  prepare:["Prepare Session",'<label class="form-field">Pitcher<select><option>Example Pitcher</option></select></label><label class="form-field">Session name<input value="Synthetic bullpen"></label><p>Confirm rig readiness before explicitly starting recording.</p><p class="subtext">Choose Ready in the prototype controls to inspect the prepared layout.</p>']
};
function openDialog(kind) {
  const [name,body]=dialogs[kind] || ["Design interaction",`<p>This control represents the existing ${kind.replaceAll("-"," ")} workflow. Its service implementation belongs to a later UX package.</p><p class="subtext">No application operation is executed.</p>`];
  document.getElementById("dialog-title").textContent=name;
  document.getElementById("dialog-content").innerHTML=body;
  document.getElementById("task-dialog").showModal();
}
document.addEventListener("click",e=>{
  const b=e.target.closest("button"); if(!b)return;
  if(b.dataset.page) {ui.page=b.dataset.page;render();content.focus();}
  else if(b.dataset.view) {ui.view=b.dataset.view;render();content.focus();}
  else if(b.dataset.pitch) {ui.pitch=Number(b.dataset.pitch);render();content.focus();}
  else if(b.dataset.step) {ui.pitch=Math.max(1,Math.min(5,ui.pitch+Number(b.dataset.step)));render();content.focus();}
  else if(b.dataset.dialog) openDialog(b.dataset.dialog);
});
document.getElementById("fixture-state").addEventListener("change",e=>{ui.state=e.target.value;render();});
document.getElementById("fixture-data").addEventListener("change",e=>{ui.data=e.target.value;render();});
document.getElementById("viewport").addEventListener("change",e=>{
  const [w,h]=e.target.value.split(" × ").map(Number);
  stage.style.setProperty("--viewport-width",w+"px"); stage.style.setProperty("--viewport-height",h+"px");
  stage.classList.toggle("compact",w<=1024);
});
document.getElementById("primary-action").addEventListener("click",()=>{
  if(ui.state==="Idle")openDialog("prepare");
  else if(ui.state==="Preview")ui.page="setup";
  else if(ui.state==="Completed")ui.page="sessions";
  else ui.state=({Ready:"Recording",Recording:"Paused",Paused:"Recording",Error:"Finalizing"})[ui.state] || ui.state;
  render();
});
document.getElementById("end-action").addEventListener("click",()=>{ui.state="Finalizing";render();});
render();
