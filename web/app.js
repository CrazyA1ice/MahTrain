"use strict";

const $ = (selector) => document.querySelector(selector);
const names = {m:"万", s:"条", p:"筒"};
let token = null;
let currentState = null;
let busy = false;
const tileName = (tile) => tile.slice(1) + names[tile[0]];
const tileUrl = (tile) => "/assets/tiles/" + encodeURIComponent(names[tile[0]] + tile.slice(1) + ".png");

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = String(text);
  return element;
}
function tileElement(tile, {small=false, selectable=false, drawn=false, onClick=null}={}) {
  const button = node("button", "tile" + (small?" mini":"") + (selectable?" selectable":""));
  button.type = "button";
  button.title = tileName(tile);
  button.setAttribute("aria-label", tileName(tile) + (selectable ? "，点击打出" : ""));
  const img = node("img");
  img.src = tileUrl(tile);
  img.alt = tileName(tile);
  button.append(img);
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
  clearToast();
  try {
    const response = await fetch("/api/action", {
      method:"POST",
      headers:{"Content-Type":"application/json", "X-MahTrain":"1"},
      body:JSON.stringify({action, token, ...extras}),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "操作失败");
    if (result.token) token = result.token;
    if (result.state) {
      currentState = result.state;
      render(currentState, result.feedback, result.report);
    }
  } catch (error) { toast(error.message); }
  finally { busy = false; }
}

function renderHand(state) {
  const list = $("#hand");
  list.replaceChildren();
  if (state.hand.length === 0) list.append(node("span", "placeholder", "暗手牌已全部移出"));
  let previousSuit = null;
  for (const tile of state.hand) {
    if (previousSuit !== null && previousSuit !== tile[0]) list.append(node("div", "suit-spacer"));
    previousSuit = tile[0];
    list.append(tileElement(tile, {
      selectable:state.phase === "await_discard",
      drawn:tile === state.drawn_tile && state.phase === "await_discard",
      onClick:()=>request("discard", {tile}),
    }));
  }
  const kong = $("#kong-area");
  kong.replaceChildren();
  if (!state.exposed_kongs.length) kong.append(node("span","placeholder","暂无开杠"));
  state.exposed_kongs.forEach((group) => {
    const container = node("div", "kong-block");
    container.append(node("div","tiny-caption", "暗杠 · " + tileName(group.tile) + " · 已锁定"));
    const four = node("div","kong-four");
    group.tiles.forEach((tile) => four.append(tileElement(tile)));
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
  const panel=$("#report-panel");
  if (!report) {panel.hidden=true; return;}
  panel.hidden=false;
  const root=$("#report");
  root.replaceChildren();
  const grid=node("div","report-grid");
  const metrics=[
    ["完成轮数",report.completed_rounds],
    ["最优正确率",(report.accuracy*100).toFixed(1)+"%"],
    ["退向听次数",report.shanten_regression_rounds],
    ["暗杠次数",report.kong_count],
  ];
  metrics.forEach(([title,value])=>{
    const cell=node("div");
    cell.append(node("strong","",value));
    cell.append(node("span","",title));
    grid.append(cell);
  });
  root.append(grid);
  root.append(node("p","",
    report.finished_reason==="self_drawn_win"?"本次已确认自摸胡牌，训练提前结束。":
    "本次训练完成，可更换种子再练习。"));
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

$("#start-form").addEventListener("submit",(event)=>{
  event.preventDefault();
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
