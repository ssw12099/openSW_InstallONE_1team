"use strict";

// 상태 이름 → 화면 표기·색
const STATUS = {
  pending: { label: "대기", tone: "idle" },
  running: { label: "진행 중", tone: "run" },
  success: { label: "성공", tone: "ok" },
  already_installed: { label: "이미 설치됨", tone: "same" },
  connect_failed: { label: "연결 실패", tone: "bad" },
  install_failed: { label: "설치 실패", tone: "bad" },
  verify_failed: { label: "검증 실패", tone: "warn" },
  error: { label: "오류", tone: "bad" },
};
const STAGES = [["connect", "연결"], ["install", "설치"], ["verify", "검증"]];
const FAILED_AT = { connect_failed: "connect", install_failed: "install", verify_failed: "verify" };
const EXAMPLES = [
  "1번부터 4번 PC에 Python 실습환경 설치해 줘",
  "2, 3번 PC에 데이터 분석 실습 환경 깔아 줘",
  "전체 PC에 VS Code랑 Git 설치해 줘",
  "3번 자리에 자바 실습 환경 부탁해",
];

const state = { catalog: null, parse: null, jobId: null, timer: null, logSeat: null };
const $ = (id) => document.getElementById(id);

// 사용자 입력을 innerHTML에 넣지 않도록 요소를 직접 만듭니다.
function h(tag, props, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

async function api(path, options = {}) {
  const response = await fetch(path, { headers: { "Content-Type": "application/json" }, ...options });
  let data = {};
  try { data = await response.json(); } catch (_) { /* 본문 없음 */ }
  if (!response.ok) {
    const detail = Array.isArray(data.detail) ? data.detail.map((d) => d.msg).join(", ") : data.detail;
    throw new Error(detail || `서버가 요청을 처리하지 못했어요 (${response.status})`);
  }
  return data;
}

// [1,2,3,4,6] → "1~4, 6번" (서버의 format_seats와 같은 규칙)
function formatSeats(numbers) {
  if (!numbers.length) return "없음";
  const sorted = [...new Set(numbers)].sort((a, b) => a - b);
  const parts = [];
  let start = sorted[0];
  let prev = sorted[0];
  for (const n of [...sorted.slice(1), null]) {
    if (n !== null && n === prev + 1) { prev = n; continue; }
    parts.push(prev - start >= 2 ? `${start}~${prev}` : prev !== start ? `${start}, ${prev}` : `${start}`);
    if (n !== null) { start = n; prev = n; }
  }
  return `${parts.join(", ")}번`;
}

function formatTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

// ── 좌석 배치도 ───────────────────────────────────────
function trackStates(result) {
  const status = result ? result.status : "pending";
  if (["success", "already_installed"].includes(status)) return { connect: "done", install: "done", verify: "done" };
  const failedAt = FAILED_AT[status];
  const current = failedAt || (status === "running" ? result.stage : null);
  const states = {};
  let reached = false;
  for (const [key] of STAGES) {
    if (!current || reached) states[key] = "todo";
    else if (key === current) { states[key] = failedAt ? "failed" : "active"; reached = true; }
    else states[key] = "done";
  }
  return states;
}

function renderSeatMap(resultsBySeat = {}) {
  const map = $("seat-map");
  map.replaceChildren();
  for (const seat of state.catalog.seats) {
    const result = resultsBySeat[seat.number];
    const status = STATUS[result ? result.status : "pending"];
    const steps = trackStates(result);
    const mock = seat.mode === "mock";
    map.append(
      h("li", { class: `seat${mock ? " mock" : ""}`, "data-tone": result ? status.tone : "idle" },
        h("div", { class: "seat-top" },
          h("span", { class: "seat-no", text: seat.number }),
          h("span", { class: "seat-mode", text: mock ? "모의" : "실제" })),
        h("div", { class: "seat-name", text: seat.name }),
        h("ol", { class: "track", "aria-label": `${seat.number}번 진행 단계` },
          STAGES.map(([key, label]) => h("li", { "data-state": steps[key], text: label }))),
        h("div", { class: "seat-status", text: result ? status.label : "대기" })));
  }
}

// ── 1. 요청 ─────────────────────────────────────────
function renderExamples() {
  const box = $("examples");
  for (const text of EXAMPLES) {
    box.append(h("button", {
      type: "button", class: "example", text,
      onclick: () => { $("request-text").value = text; $("request-text").focus(); },
    }));
  }
}

async function onParse(event) {
  event.preventDefault();
  const text = $("request-text").value.trim();
  $("parse-error").textContent = "";
  if (!text) {
    $("parse-error").textContent = "요청 문장을 입력해 주세요.";
    $("request-text").focus();
    return;
  }
  const button = $("parse-btn");
  button.disabled = true;
  button.textContent = "해석하는 중";
  try {
    state.parse = await api("/api/parse", { method: "POST", body: JSON.stringify({ text }) });
    renderConfirm();
  } catch (error) {
    $("parse-error").textContent = error.message;
  } finally {
    button.disabled = false;
    button.textContent = "해석하기";
  }
}

// ── 2. 확인 ─────────────────────────────────────────
function renderConfirm() {
  const result = state.parse;
  $("confirm-step").hidden = false;
  const who = result.parser === "ai" ? `AI 해석 (${result.provider})` : "규칙 기반 해석";
  $("parser-line").replaceChildren(h("strong", { text: who }),
    `: 좌석 ${formatSeats(result.seats)}, 프로필 ${result.profiles.length}개`);
  $("reason").textContent = result.reason || "";
  $("warnings").replaceChildren(...result.warnings.map((w) => h("li", { text: w })));

  $("seat-picks").replaceChildren(...state.catalog.seats.map((seat) =>
    h("label", { class: "pick" },
      h("input", { type: "checkbox", name: "seat", value: seat.number, checked: result.seats.includes(seat.number), onchange: updateRunButton }),
      h("span", { text: `${seat.number}번${seat.mode === "mock" ? " (모의)" : ""}` }))));

  $("profile-picks").replaceChildren(...state.catalog.profiles.map((profile) =>
    h("label", { class: "profile" },
      h("input", { type: "checkbox", name: "profile", value: profile.id, checked: result.profiles.includes(profile.id), onchange: updateRunButton }),
      h("span", { class: "profile-name", text: profile.name }),
      h("span", { class: "profile-desc", text: profile.description }),
      h("span", { class: "profile-items", text: `설치: ${profile.items.join(", ")}` }))));

  $("run-error").textContent = "";
  updateRunButton();
  $("confirm-step").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function checkedValues(name) {
  return [...document.querySelectorAll(`input[name="${name}"]:checked`)].map((input) => input.value);
}

function updateRunButton() {
  const ready = checkedValues("seat").length > 0 && checkedValues("profile").length > 0;
  $("run-btn").disabled = !ready;
  $("run-error").textContent = ready ? "" : "좌석과 프로필을 하나 이상 골라야 실행할 수 있어요.";
}

async function onRun() {
  const seats = checkedValues("seat").map(Number);
  const profiles = checkedValues("profile");
  const button = $("run-btn");
  button.disabled = true;
  button.textContent = "설치를 시작하는 중";
  try {
    const { job_id: jobId } = await api("/api/jobs", {
      method: "POST",
      body: JSON.stringify({ request_id: state.parse ? state.parse.request_id : null, seats, profiles }),
    });
    $("confirm-step").hidden = true;
    await showJob(jobId);
  } catch (error) {
    $("run-error").textContent = error.message;
    button.disabled = false;
  } finally {
    button.textContent = "설치 실행";
  }
}

// ── 3. 결과 ─────────────────────────────────────────
async function showJob(jobId) {
  clearTimeout(state.timer);
  state.jobId = jobId;
  let job;
  try {
    job = await api(`/api/jobs/${jobId}`);
  } catch (error) {
    $("summary").textContent = error.message;
    return;
  }
  renderJob(job);
  if (state.logSeat !== null) loadLog(state.logSeat, false);
  const running = job.status === "queued" || job.status === "running";
  if (running) state.timer = setTimeout(() => showJob(jobId), 1000);
  else loadHistory();
}

function renderJob(job) {
  const bySeat = Object.fromEntries(job.seats.map((s) => [s.seat_no, s]));
  renderSeatMap(bySeat);
  const running = job.status === "queued" || job.status === "running";
  const request = job.request_text ? `"${job.request_text}"` : "직접 고른 작업";
  $("room-job").textContent = `작업 #${job.id} ${running ? "설치 중" : "끝남"}: ${request}`;

  $("results").hidden = false;
  const counts = job.counts || {};
  const parts = Object.entries(counts)
    .filter(([status]) => STATUS[status])
    .map(([status, n]) => `${STATUS[status].label} ${n}`);
  $("summary").textContent = `작업 #${job.id} ${running ? "진행 중" : "끝남"}: ${parts.join(", ")}`;

  $("result-rows").replaceChildren(...job.seats.map((seat) => {
    const status = STATUS[seat.status] || STATUS.pending;
    const versions = Object.entries(seat.versions || {});
    const stage = seat.status === "running" && seat.stage ? ` (${(STAGES.find(([k]) => k === seat.stage) || [, ""])[1]})` : "";
    return h("tr", {},
      h("td", { class: "seat-cell" }, `${seat.seat_no}번`, h("span", { class: "tag mode", text: seat.mode === "mock" ? "모의" : "실제" })),
      h("td", {}, h("span", { class: "tag", "data-tone": status.tone, text: status.label + stage })),
      h("td", {}, versions.length
        ? h("ul", { class: "versions" }, versions.map(([k, v]) => h("li", { text: `${k}: ${v}` })))
        : h("span", { class: "muted", text: "—" })),
      h("td", { text: seat.example_output || "—" }),
      h("td", { text: seat.message || "" }),
      h("td", {}, h("button", { type: "button", class: "link-btn", text: "기록", onclick: () => loadLog(seat.seat_no, true) })));
  }));
}

async function loadLog(seatNo, reveal) {
  state.logSeat = seatNo;
  try {
    const { events } = await api(`/api/jobs/${state.jobId}/events?seat=${seatNo}`);
    $("log-title").textContent = `${seatNo}번 좌석 실행 기록`;
    $("log").textContent = events.length
      ? events.map((e) => `${e.created_at.slice(11)}  ${e.ok ? "  " : "✗ "}${e.kind.padEnd(11)} ${e.task}${e.detail ? `\n           ${e.detail}` : ""}`).join("\n")
      : "아직 기록이 없어요.";
    $("log-box").hidden = false;
    if (reveal) $("log-box").scrollIntoView({ behavior: "smooth", block: "nearest" });
  } catch (error) {
    $("log").textContent = error.message;
  }
}

// ── 이력 ─────────────────────────────────────────────
async function loadHistory() {
  const list = $("history");
  try {
    const { jobs } = await api("/api/jobs");
    if (!jobs.length) {
      list.replaceChildren(h("li", { class: "empty", text: "아직 설치 이력이 없어요. 위에서 첫 요청을 보내 보세요." }));
      return jobs;
    }
    list.replaceChildren(...jobs.map((job) => {
      const counts = Object.entries(job.counts || {})
        .filter(([status]) => STATUS[status]).map(([status, n]) => `${STATUS[status].label} ${n}`).join(", ");
      return h("li", {}, h("button", { type: "button", onclick: () => showJob(job.id) },
        h("span", { class: "h-id", text: `#${job.id}` }),
        h("span", { class: "h-text", text: `${formatTime(job.created_at)}  ${job.request_text || "직접 선택한 작업"}` }),
        h("span", { class: "h-counts", text: counts })));
    }));
    return jobs;
  } catch (error) {
    list.replaceChildren(h("li", { class: "empty", text: error.message }));
    return [];
  }
}

// ── 시작 ─────────────────────────────────────────────
async function init() {
  try {
    state.catalog = await api("/api/catalog");
  } catch (error) {
    $("room-job").textContent = `서버에서 좌석 목록을 받지 못했어요: ${error.message}`;
    return;
  }
  const ai = state.catalog.ai;
  $("ai-state").textContent = ai.enabled ? `AI 해석 켜짐 (${ai.provider})` : "AI 꺼짐: 규칙 기반 해석";
  $("ai-state").classList.toggle("on", ai.enabled);
  renderSeatMap();
  renderExamples();
  $("parse-form").addEventListener("submit", onParse);
  $("run-btn").addEventListener("click", onRun);
  $("log-close").addEventListener("click", () => { $("log-box").hidden = true; state.logSeat = null; });
  const jobs = await loadHistory();
  if (jobs.length) showJob(jobs[0].id);  // 마지막 작업을 배치도에 보여 줌
}

init();
