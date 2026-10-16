"use strict";

const $ = (selector) => document.querySelector(selector);
const names = {m:"万", s:"条", p:"筒"};
let token = null;
let currentState = null;
let busy = false;
let currentPreview = null;
const playSound = (event) => window.MahTrainSound?.play(event);
const tileName = (tile) => tile.slice(1) + names[tile[0]];
// Cropping the ORIGINAL 560x420 project sprite sheet, not using synthetic SVG.
const tileUrl = (tile) => "/assets/tiles/" + encodeURIComponent(names[tile[0]] + tile.slice(1) + ".png");
const atlasMap = {p:0, m:1, s:2};
function atlasFace(tile) {
  const row = atlasMap[tile[0]];
  const col = Number(tile[1]) - 1;
  const cropX = 16 + 60 * col;  // 9 columns, 60px step.
  const cropY = [25,103,180][row]; // 筒/万/条, top to bottom in atlas.
  const face = node("span", "tile-atlas-face");
  face.style.backgroundPosition =
      (100 * cropX / (560 - 46)).toFixed(5) + "% " +
      (100 * cropY / (420 - 60)).toFixed(5) + "%";
  face.setAttribute("aria-hidden", "true");
  return face;
}

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = String(text);
  return element;
}
function tileElement(tile, {small=false, selectable=false, drawn=false, missing=false, onClick=null}={}) {
  const button = node("button", "tile" + (small?" mini":"") + (selectable?" selectable":"") + (missing?" missing-tile":""));
  button.type = "button";
  button.title = tileName(tile);
  button.setAttribute("aria-label", tileName(tile) + (selectable ? "，点击打出" : ""));
  button.append(atlasFace(tile));
  if (drawn) button.append(node("span", "drawn", "本轮摸牌"));
  if (selectable && onClick) button.addEventListener("click", onClick);
  else button.disabled = true;
  return button;
}
function toast(message) {
  const panel = $("#toast");
  panel.textContent = message;
  panel.hidden = false;
}
function clearToast() { $("#toast").hidden = true; }

async function request(action, extras={}) {
  if (busy) return;
  busy = true;
  window.MahTrainSound?.unlock();
  clearToast();
  try {
    const response = await fetch("/api/action", {
      method:"POST",
      headers:{"Content-Type":"application/json", "X-MahTrain":"1"},
      body:JSON.stringify({action, token, ...extras}),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "操作失败");
    if (action === "preview" && result.initial_hand) {
      showDealtPreview(result);
    }
    if (result.token) token = result.token;
    if (result.state) {
      currentState = result.state;
      render(currentState, result.feedback, result.report);
      if(currentState.phase === "finished" && (action==="discard" || action==="win")){
        window.MahTrainHistory?.refresh();
      }
      if (action === "draw") playSound("draw");
      else if (action === "discard") playSound("discard");
      else if (action === "win" && extras.accept === true) playSound("win");
      else if (action === "kong" && extras.tile) {
        playSound("kong");
        setTimeout(() => playSound("draw"), 390);
      }
    }
  } catch (error) { toast(error.message); }
  finally { busy = false; }
}

function showDealtPreview(response) {
  currentPreview = {seed:Number($("#seed").value), hand:response.initial_hand};
  $("#preview-section").hidden = false;
  const hand = $("#preview-hand");
  hand.replaceChildren();
  let suit = null;
  response.initial_hand.forEach(tile => {
    if (suit && suit !== tile[0]) hand.append(node("span","suit-spacer"));
    suit = tile[0];
    hand.append(tileElement(tile,{small:true}));
  });
  $("#preview-count").textContent = response.initial_hand.length + "张";
  const select = $("#missing");
  select.disabled = false;
  select.value = "";
  const hint = $("#preview-hint");
  if (response.tianque) {
    const choices = response.absent_suits.map(s => names[s]).join("、");
    hint.className = "preview-hint tianque";
    hint.textContent = "天缺：手中只有两门或更少，可直接定缺少的「" +
      choices + "」。本练习不模拟换三张。";
    if (response.absent_suits.length === 1) {
      select.value = response.absent_suits[0]; // a suggested choice, not confirmed.
    }
  } else {
    hint.className = "preview-hint";
    hint.textContent = "已看到13张起手牌，请从万、条、筒中选择要定缺的一门。正式对局应在换三张后定缺。";
  }
  $("#begin-training").disabled = !select.value;
}
function invalidatePreview() {
  currentPreview = null;
  $("#preview-section").hidden = true;
  $("#missing").value = "";
  $("#missing").disabled = true;
  $("#begin-training").disabled = true;
}

function renderWinDiagnosis(state) {
  const panel = $("#win-diagnosis");
  const result = state.win_status;
  if (!result) {
    panel.textContent = "尚未进行胡牌结构判断。";
    panel.className = "win-diagnosis";
    return;
  }
  const missing = result.missing_suit_tile_count;
  const suit = names[state.missing_suit];
  if (missing > 0) {
    panel.className = "win-diagnosis blocked";
    panel.textContent = result.structural_win
      ? "牌型结构已经成胡，但仍有 " + missing + " 张定缺「" + suit + "」！川麻须先打光定缺牌，暂时不能胡牌。"
      : "定缺提醒：手中还有 " + missing + " 张「" + suit + "」，须先打光该花色才能胡牌。";
  } else if (result.legal_win) {
    panel.className = "win-diagnosis ready";
    panel.textContent = "胡牌判断通过：已打光定缺且满足胡牌结构，系统正在提示是否胡牌。";
  } else {
    panel.className = "win-diagnosis clear";
    panel.textContent = "已打光定缺「" + suit + "」，但当前手牌尚未满足胡牌结构。";
  }
}

function renderHand(state) {
  const list = $("#hand");
  list.replaceChildren();
  if (state.hand.length === 0) list.append(node("span", "placeholder", "暗手牌已全部移出"));
  let previousSuit = null;
  let markedDraw = false;
  for (const tile of state.hand) {
    if (previousSuit !== null && previousSuit !== tile[0]) list.append(node("div", "suit-spacer"));
    previousSuit = tile[0];
    list.append(tileElement(tile, {
      selectable:state.phase === "await_discard",
      drawn:!markedDraw && tile === state.drawn_tile && state.phase === "await_discard",
      missing:tile[0] === state.missing_suit,
      onClick:()=>request("discard", {tile}),
    }));
    if (tile === state.drawn_tile && state.phase === "await_discard") markedDraw = true;
  }
  renderWinDiagnosis(state);
  const kong = $("#kong-area");
  kong.replaceChildren();
  if (!state.exposed_kongs.length) kong.append(node("span","placeholder","暂无开杠"));
  state.exposed_kongs.forEach((group) => {
    const container = node("div", "kong-block");
    container.append(node("div","tiny-caption", "暗杠 · " + tileName(group.tile) + " · 已锁定"));
    const four = node("div","kong-four");
    group.tiles.forEach((tile) => four.append(tileElement(tile,{small:true})));
    container.append(four);
    kong.append(container);
  });
  const discard = $("#discards");
  discard.replaceChildren();
  if (!state.discard_history.length) discard.append(node("span","placeholder","暂无弃牌"));
  else state.discard_history.forEach((tile)=>discard.append(tileElement(tile,{small:true})));
}

function promptActions(state) {
  const layer=$("#prompt-layer");
  const buttons=$("#prompt-buttons");
  const slots=$("#prompt-tiles");
  buttons.replaceChildren();
  slots.replaceChildren();
  if (!["offer_win","offer_kong"].includes(state.phase)) { layer.hidden=true; return; }
  layer.hidden=false;
  const addAction = (text, className, onClick) => {
    const button=node("button",className,text);
    button.type="button";
    button.addEventListener("click", onClick);
    buttons.append(button);
  };
  if (state.phase==="offer_win") {
    $("#prompt-kicker").textContent="SELF-DRAW · HU";
    $("#prompt-title").textContent="系统判断：已经胡牌！";
    $("#prompt-message").textContent="当前手牌满足定缺及胡牌结构。是否确认自摸胡牌？选择「暂不胡」将继续本轮操作。";
    addAction("暂不胡", "", ()=>request("win",{accept:false}));
    addAction("确认胡牌", "confirm", ()=>request("win",{accept:true}));
  } else {
    $("#prompt-kicker").textContent="CONCEALED KONG · AN GANG";
    $("#prompt-title").textContent="检测到可以开暗杠";
    $("#prompt-message").textContent="确认后把这四张同牌移至右侧独立杠区，之后不能再切出或操作；系统自动从牌墙尾部补一张，并再次检查是否能胡。";
    state.kong_options.forEach((tile)=> {
      for(let i=0;i<4;i++) slots.append(tileElement(tile,{small:true}));
      addAction("暗杠 " + tileName(tile), "confirm", ()=>request("kong",{tile}));
    });
    addAction("本次不开杠", "", ()=>request("kong",{tile:null}));
  }
}

function renderFeedback(feedback) {
  if (!feedback) return;
  const area=$("#feedback");
  area.classList.remove("empty");
  area.replaceChildren();
  area.append(node("strong",feedback.correct?"✓ 本轮选择正确":"· 本轮还可优化"));
  area.append(node("p","",feedback.explanation));
  const best=feedback.best_actions || [];
  if (best.length) area.append(node("p","",
    "正确动作：" + best.map(t=>t==="win"?"胡牌":tileName(t)).join("、")));
  if (feedback.win_type) area.append(node("span","tag",
    feedback.win_type==="kong_bloom"?"杠上花":"自摸胡牌"));
  if (feedback.selected_candidate) {
    const chosen=feedback.selected_candidate;
    area.append(node("span","tag","切后向听：" + chosen.shanten));
    area.append(node("span","tag","有效进张：" + chosen.effective_tile_count + "张"));
    area.append(node("span","tag","下一摸概率：" +
      (100*chosen.next_draw_probability).toFixed(2)+"%"));
  }
}

function renderReport(report) {
  window.MahTrainReview.render(report, tileName);
  window.MahTrainRetry.render(report);
}

function render(state,feedback=null,report=null) {
  $("#game").hidden=false;
  $("#progress").textContent=state.completed_rounds+" / "+state.round_limit;
  $("#wall").textContent=state.wall_remaining_count;
  $("#kong-count").textContent=state.kong_count;
  $("#missing-name").textContent=names[state.missing_suit];
  const phases={
    ready_to_draw:"等待摸牌",offer_win:"等待胡牌确认",
    offer_kong:"等待暗杠确认",await_discard:"请选择切牌",finished:"训练结束",
  };
  $("#phase-label").textContent=phases[state.phase] || "进行中";
  $("#drawn-label").textContent=state.drawn_tile?
      "最近摸到 "+tileName(state.drawn_tile):"等待摸牌";
  renderHand(state);
  const draw=$("#draw-button");
  draw.hidden=state.phase!=="ready_to_draw";
  draw.disabled=state.phase!=="ready_to_draw";
  const hint={
    ready_to_draw:"点击摸牌按钮继续下一轮。",
    offer_win:"系统已自动识别合法胡牌，请在弹窗中选择。",
    offer_kong:"检测到暗杠机会，请在弹窗中决定是否开杠。",
    await_discard:"直接点击暗手牌切牌；右侧杠区的牌不可操作。",
    finished:"训练已结束，请查看下方报告。",
  };
  $("#action-hint").textContent=hint[state.phase];
  renderFeedback(feedback);
  renderReport(report);
  promptActions(state);
}

$("#preview-button").addEventListener("click", () => {
  request("preview",{seed:Number($("#seed").value),rounds:14});
});
$("#seed").addEventListener("input",invalidatePreview);
$("#missing").addEventListener("change",()=>{
  $("#begin-training").disabled = !currentPreview || !$("#missing").value;
});
$("#start-form").addEventListener("submit",(event)=>{
  event.preventDefault();
  if (!currentPreview || currentPreview.seed !== Number($("#seed").value)
      || !$("#missing").value) {
    toast("请先发牌查看手牌，再选择定缺。");
    return;
  }
  $("#feedback").textContent="提交切牌后，这里会显示本轮判题结果。";
  $("#feedback").className="feedback empty";
  $("#report-panel").hidden=true;
  request("new",{
    seed:Number($("#seed").value),
    missing_suit:$("#missing").value || null,
    rounds:14,
  });
});
$("#draw-button").addEventListener("click",()=>request("draw"));
$("#sound-toggle").addEventListener("click",()=>{
  const current = window.MahTrainSound?.getEnabled() ?? false;
  const next = window.MahTrainSound?.setEnabled(!current) ?? false;
  const button=$("#sound-toggle");
  button.textContent=next?"🔊 音效开启":"🔇 音效关闭";
  button.setAttribute("aria-pressed",String(next));
  if(next)playSound("draw");
});


// Controlled view helpers for the independent mistake-replay panel.
window.MahTrainUI = {getToken:()=>token, tileElement, tileName};
window.MahTrainHistory?.init();
window.MahTrainQuiz?.init();
window.MahTrainQuizHistory?.init();
window.MahTrainTableDemo?.init();
window.MahTrainMatch?.init();
window.MahTrainAIReplay?.init();
window.MahTrainAIBaseline?.init();
