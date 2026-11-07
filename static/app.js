"use strict";

/* 轻步 LightStep 前端逻辑：与后端 /api/* 交互，渲染「小步」的对话。 */

const $ = (sel) => document.querySelector(sel);

// 同一浏览器持久化一个 user_id，让记忆（摩擦地图 / 跨天交接）跨会话保留
let userId = localStorage.getItem("lightstep_user");
if (!userId) {
  userId = "u_" + Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
  localStorage.setItem("lightstep_user", userId);
}

const messagesEl = $("#messages");
const inputEl = $("#input");
const composerEl = $("#composer");
const quickEl = $("#quickActions");

// 用于「完成这一步」时回传真实耗时
let lastStep = null;
let stepStartedAt = null;
let noteMode = false;

// ---------- HTTP ----------

async function post(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(path + " " + res.status);
  return res.json();
}

async function get(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(path + " " + res.status);
  return res.json();
}

// ---------- 按钮 → 动作映射 ----------

const BUTTON_ACTIONS = {
  "现在开始": () => post("/api/task/choose_time", { user_id: userId, when: "now" }),
  "待会儿": () => post("/api/task/choose_time", { user_id: userId, when: "later" }),
  "今天不做": () => post("/api/task/choose_time", { user_id: userId, when: "not_today" }),
  "行": () => post("/api/task/commit", { user_id: userId, agree: true }),
  "再想想": () => post("/api/task/commit", { user_id: userId, agree: false }),
  "完成这一步": () => {
    const duration = stepStartedAt ? Math.max(1000, Date.now() - stepStartedAt) : 30000;
    return post("/api/step/complete", { user_id: userId, duration_ms: duration });
  },
  "太重了": () => post("/api/step/resize", { user_id: userId, direction: "smaller" }),
  "今天到这吧": () => post("/api/task/exit", { user_id: userId, gentle: false }),
  "接着做": () => post("/api/handoff/resume", { user_id: userId }),
  "翻篇": () => post("/api/handoff/dismiss", { user_id: userId }),
};

const STATE_LABEL = { ready: "待开始", committing: "轻轻承诺", executing: "进行中", done: "完成" };
const GRAN_LABEL = { fine: "细", normal: "中", coarse: "粗" };

// ---------- 渲染 ----------

function addBubble(kind, node) {
  const wrap = document.createElement("div");
  wrap.className = "msg " + kind;
  wrap.appendChild(node);
  messagesEl.appendChild(wrap);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return wrap;
}

function userBubble(text) {
  const el = document.createElement("div");
  el.className = "bubble user";
  el.textContent = text;
  addBubble("user", el);
}

function systemNote(text) {
  const el = document.createElement("div");
  el.className = "bubble system";
  el.textContent = text;
  addBubble("cat", el);
}

function handleTaskTiming(task) {
  if (task && task.state === "executing") {
    if (task.current_step !== lastStep) {
      lastStep = task.current_step;
      stepStartedAt = Date.now();
    }
  } else {
    lastStep = null;
    stepStartedAt = null;
  }
}

function taskCard(task) {
  const card = document.createElement("div");
  card.className = "task-card";

  const head = document.createElement("div");
  head.className = "task-head";
  const title = document.createElement("span");
  title.className = "task-title";
  title.textContent = task.title;
  head.appendChild(title);
  const chip = document.createElement("span");
  chip.className = "chip state-" + task.state;
  chip.textContent = STATE_LABEL[task.state] || task.state;
  head.appendChild(chip);
  card.appendChild(head);

  const step = document.createElement("div");
  step.className = "task-step";
  step.textContent = task.current_step;
  card.appendChild(step);

  const meta = document.createElement("div");
  meta.className = "task-meta";
  meta.textContent = "已完成 " + task.steps_done + " 小步 · 粒度 " + (GRAN_LABEL[task.granularity] || task.granularity);
  card.appendChild(meta);

  return card;
}

function buttonRow(buttons) {
  const row = document.createElement("div");
  row.className = "button-row";
  buttons.forEach((label, i) => {
    const b = document.createElement("button");
    b.className = "action-btn" + (i === 0 ? " primary" : "");
    b.textContent = label;
    b.addEventListener("click", () => onButton(label, row));
    row.appendChild(b);
  });
  return row;
}

function catBubble(data) {
  const box = document.createElement("div");
  box.className = "bubble cat";

  if (data.reply) {
    const p = document.createElement("div");
    p.className = "reply-text";
    p.textContent = data.reply;
    box.appendChild(p);
  }

  if (data.task) box.appendChild(taskCard(data.task));

  if (data.summary) {
    const s = document.createElement("div");
    s.className = "summary";
    s.textContent = data.summary;
    box.appendChild(s);
  }

  if (data.due_reminders && data.due_reminders.length) {
    const r = document.createElement("div");
    r.className = "reminder";
    r.textContent = "提醒：" + data.due_reminders.join("、");
    box.appendChild(r);
  }

  if (data.buttons && data.buttons.length) box.appendChild(buttonRow(data.buttons));

  handleTaskTiming(data.task);
  addBubble("cat", box);
  refreshTodayIfActive();
}

async function onButton(label, row) {
  row.querySelectorAll("button").forEach((x) => (x.disabled = true));
  try {
    const fn = BUTTON_ACTIONS[label];
    const data = fn ? await fn() : await post("/api/chat", { user_id: userId, message: label });
    catBubble(data);
  } catch (e) {
    systemNote("没连上后端：" + e.message);
  }
}

async function sendChat(text) {
  userBubble(text);
  try {
    const data = await post("/api/chat", { user_id: userId, message: text });
    catBubble(data);
  } catch (e) {
    systemNote("没连上后端：" + e.message);
  }
}

// ---------- 快捷小事 ----------

const QUICK_ACTIONS = [
  { label: "换件小事", text: "换件事" },
  { label: "发呆", text: "发呆" },
  { label: "今天什么都不想干", text: "今天什么都不想干" },
  { label: "温柔收尾", text: "温柔收尾" },
  { label: "走神记笔记", note: true },
];

function buildQuickActions() {
  QUICK_ACTIONS.forEach((qa) => {
    const b = document.createElement("button");
    b.className = "quick-btn";
    b.textContent = qa.label;
    b.addEventListener("click", () => {
      if (qa.note) {
        noteMode = true;
        inputEl.placeholder = "记点什么…（走神的时候写下来）";
        inputEl.focus();
      } else {
        sendChat(qa.text);
      }
    });
    quickEl.appendChild(b);
  });
}

// ---------- 输入框 ----------

function resetComposer() {
  noteMode = false;
  inputEl.placeholder = "说点什么，或者点上面的一件小事…";
}

composerEl.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = inputEl.value.trim();
  if (!text) return;
  inputEl.value = "";
  inputEl.style.height = "auto";

  if (noteMode) {
    resetComposer();
    userBubble("（记笔记）" + text);
    try {
      const data = await post("/api/note", { user_id: userId, content: text });
      catBubble(data);
    } catch (err) {
      systemNote("没连上后端：" + err.message);
    }
  } else {
    sendChat(text);
  }
});

inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    composerEl.requestSubmit();
  }
});

inputEl.addEventListener("input", () => {
  inputEl.style.height = "auto";
  inputEl.style.height = Math.min(inputEl.scrollHeight, 120) + "px";
});

// ---------- 侧栏 ----------

function wireTabs() {
  document.querySelectorAll("#tabs .tab").forEach((tab) => {
    tab.addEventListener("click", () => switchTab(tab.dataset.tab, tab));
  });
}

function switchTab(key, btn) {
  document.querySelectorAll("#tabs .tab").forEach((t) => t.classList.remove("active"));
  btn.classList.add("active");
  ["today", "journal", "history"].forEach((k) => {
    $("#panel-" + k).hidden = k !== key;
  });
  loadPanel(key);
}

async function loadPanel(key) {
  try {
    if (key === "today") {
      renderToday(await get("/api/daily/summary?user_id=" + userId));
    } else if (key === "journal") {
      renderJournal(await get("/api/journal?user_id=" + userId));
    } else if (key === "history") {
      renderHistory(await get("/api/history?user_id=" + userId));
    }
  } catch (e) {
    /* 后端未启动时静默 */
  }
}

function refreshTodayIfActive() {
  const active = document.querySelector("#tabs .tab.active");
  if (active && active.dataset.tab === "today") loadPanel("today");
}

function renderToday(s) {
  const el = $("#panel-today");
  el.innerHTML = "";
  if (!s.titles || !s.titles.length) {
    const p = document.createElement("div");
    p.className = "muted";
    p.textContent = "今天还没做什么，也没关系。";
    el.appendChild(p);
    return;
  }
  const big = document.createElement("div");
  big.className = "today-steps";
  big.textContent = s.steps_done;
  el.appendChild(big);
  const cap = document.createElement("div");
  cap.className = "today-cap";
  cap.textContent = "今天的小步数";
  el.appendChild(cap);
  s.titles.forEach((t) => {
    const d = document.createElement("div");
    d.className = "today-title";
    d.textContent = "· " + t;
    el.appendChild(d);
  });
}

function renderJournal(list) {
  const el = $("#panel-journal");
  el.innerHTML = "";

  const form = document.createElement("form");
  form.className = "journal-form";
  const inp = document.createElement("input");
  inp.placeholder = "写一句今天的…";
  const addBtn = document.createElement("button");
  addBtn.type = "submit";
  addBtn.textContent = "记下";
  form.appendChild(inp);
  form.appendChild(addBtn);
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const note = inp.value.trim();
    if (!note) return;
    await post("/api/journal/add", { user_id: userId, note });
    inp.value = "";
    loadPanel("journal");
  });
  el.appendChild(form);

  if (!list.length) {
    const empty = document.createElement("div");
    empty.className = "muted";
    empty.textContent = "还没有手帐。";
    el.appendChild(empty);
  }

  list.forEach((entry) => {
    const card = document.createElement("div");
    card.className = "journal-item";

    const top = document.createElement("div");
    top.className = "journal-top";
    const date = document.createElement("span");
    date.className = "journal-date";
    date.textContent = entry.date;
    top.appendChild(date);
    const del = document.createElement("button");
    del.className = "del-btn";
    del.textContent = "删除";
    del.addEventListener("click", async () => {
      await fetch("/api/journal/" + entry.id + "?user_id=" + userId, { method: "DELETE" });
      loadPanel("journal");
    });
    top.appendChild(del);
    card.appendChild(top);

    if (entry.titles && entry.titles.length) {
      const t = document.createElement("div");
      t.className = "journal-titles";
      t.textContent = entry.titles.join("、");
      card.appendChild(t);
    }
    const steps = document.createElement("div");
    steps.className = "journal-steps";
    steps.textContent = entry.steps_done + " 小步";
    card.appendChild(steps);
    if (entry.note) {
      const n = document.createElement("div");
      n.className = "journal-note";
      n.textContent = entry.note;
      card.appendChild(n);
    }
    el.appendChild(card);
  });
}

function renderHistory(list) {
  const el = $("#panel-history");
  el.innerHTML = "";
  if (!list.length) {
    const p = document.createElement("div");
    p.className = "muted";
    p.textContent = "还没有历史。";
    el.appendChild(p);
    return;
  }
  list.forEach((item) => {
    const d = document.createElement("div");
    d.className = "history-item";
    const date = document.createElement("span");
    date.className = "history-date";
    date.textContent = item.date;
    const title = document.createElement("span");
    title.className = "history-title";
    title.textContent = item.title;
    d.appendChild(date);
    d.appendChild(title);
    el.appendChild(d);
  });
}

// ---------- 启动 ----------

async function init() {
  wireTabs();
  buildQuickActions();
  loadPanel("today");
  try {
    const data = await post("/api/session/open", { user_id: userId });
    catBubble(data);
  } catch (e) {
    systemNote("没连上后端。请先运行 python run.py，再打开本页。");
  }
}

init();
