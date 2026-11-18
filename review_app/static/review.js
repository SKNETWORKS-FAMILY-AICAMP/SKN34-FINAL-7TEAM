const byId = id => document.getElementById(id);
const tabs = [...document.querySelectorAll("[data-page]")];
const pageSize = 8;
const splitNames = {train: "학습용", validation: "검증용", development: "검증용", test: "시험용", holdout: "시험용"};
const roleNames = {question_generator: "질문 에이전트", action_generator: "행동 에이전트", supervisor: "평가 에이전트"};
const number = new Intl.NumberFormat("ko-KR");
let questions = [];
let currentPage = "question";
let index = 0;
let selectedId = null;
let saving = false;
let hasLoaded = false;

function element(tag, text = "", className = "") {
  const node = document.createElement(tag);
  node.textContent = text;
  if (className) node.className = className;
  return node;
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(typeof data.detail === "string" ? data.detail : "요청을 처리하지 못했습니다.");
  }
  return data;
}

function filteredQuestions() {
  const search = byId("search").value.trim().toLowerCase();
  const split = byId("split").value;
  const status = byId("status").value;
  return questions.filter(row => {
    if (split && splitNames[row.split] !== splitNames[split]) return false;
    if (status && (row.review?.status ?? "미평가") !== status) return false;
    return !search || [row.question, row.review?.question, row.category]
      .some(value => value?.toLowerCase().includes(search));
  });
}

function renderQueue() {
  const rows = filteredQuestions();
  const totalPages = Math.max(1, Math.ceil(rows.length / pageSize));
  index = Math.min(index, totalPages - 1);
  const visible = rows.slice(index * pageSize, (index + 1) * pageSize);
  if (!visible.some(row => row.id === selectedId)) selectedId = visible[0]?.id ?? null;

  byId("count").textContent = number.format(rows.length) + "건";
  byId("queue-title").textContent = "질문 목록";
  byId("page-number").textContent = (index + 1) + " / " + totalPages;
  byId("previous").disabled = index === 0;
  byId("next").disabled = index >= totalPages - 1;
  const controls = visible.map(row => {
    const li = element("li");
    const button = element("button", row.review?.question ?? row.question, "question");
    button.type = "button";
    button.setAttribute("aria-pressed", String(row.id === selectedId));
    button.addEventListener("click", () => {
      selectedId = row.id;
      renderQueue();
      byId("questions").querySelector('[aria-pressed="true"]')?.focus();
    });
    li.append(button);
    return li;
  });
  byId("questions").replaceChildren(...controls);
  document.querySelector(".download").hidden = !questions.some(row =>
    row.split === "train" && row.review?.status === "승인"
  );
  renderDetail(visible.find(row => row.id === selectedId));
}

function block(label, value) {
  const section = element("div", "", "block");
  section.append(element("strong", label), element("p", value, "preserve-lines"));
  return section;
}

function renderDetail(row) {
  const target = byId("detail");
  target.replaceChildren(element("h2", roleNames[{
    question: "question_generator", action: "action_generator", evaluation: "supervisor",
  }[currentPage]]));
  if (!row) {
    target.append(element("p", hasLoaded ? "조건에 맞는 질문이 없습니다." : "질문을 불러오는 중입니다.", "muted"));
    return;
  }
  target.append(
    element("p", [splitNames[row.split], row.category, row.review?.status].filter(Boolean).join(" · "), "meta"),
    element("h3", row.review?.question ?? row.question),
  );

  if (currentPage === "question") {
    target.append(element("p", row.dataset === "단일 의도" ? "기존 합성 질문" : "기존 대화 시나리오", "muted"));
    const details = element("details");
    const turns = row.history ?? [];
    if (turns.length || row.review?.question && row.review.question !== row.question) {
      details.append(element("summary", "원문과 앞선 대화"));
      details.append(block("원래 질문", row.question));
      for (const turn of turns) details.append(block(turn.role === "user" ? "손님" : "카이페", turn.text ?? ""));
      target.append(details);
    }
  }

  if (currentPage === "action") {
    const action = row.review?.expected_action;
    const answer = row.review?.expected_answer;
    if (action) target.append(block("저장한 처리 방법", action));
    else if (row.actions.length) target.append(block("기존 시나리오의 예상 행동", row.actions.join("\n")));
    else target.append(element("p", "작성된 처리 방법이 없습니다.", "muted"));
    if (answer) target.append(block("저장한 안내 문구", answer));
  }

  if (currentPage === "evaluation") renderEvaluation(target, row);
}

function field(form, label, name, initial, limit) {
  const wrapper = element("label", label);
  const control = element("textarea");
  control.name = name;
  control.maxLength = limit;
  control.value = initial;
  wrapper.append(control);
  form.append(wrapper);
  return control;
}

function renderEvaluation(target, row) {
  if (row.review) {
    target.append(block("사용자 평가", row.review.status));
    if (row.review.comment) target.append(block("평가 의견", row.review.comment));
  }
  const editor = element("details");
  editor.append(element("summary", row.review ? "평가 수정" : "사용자 평가 남기기"));
  const form = element("form");
  const question = field(form, "질문", "question", row.review?.question ?? row.question, 4000);
  question.required = true;
  field(form, "처리 방법", "action", row.review?.expected_action ?? row.actions.join("\n"), 8000);
  field(form, "고객에게 보여줄 안내", "answer", row.review?.expected_answer ?? "", 8000);
  field(form, "의견", "comment", row.review?.comment ?? "", 8000);
  const label = element("label", "최종 평가");
  const select = element("select");
  select.name = "status";
  select.required = true;
  const placeholder = element("option", "평가 선택");
  placeholder.disabled = true;
  placeholder.value = "";
  select.append(placeholder, ...["승인", "수정 필요", "반려"].map(value => element("option", value)));
  select.value = row.review?.status ?? "";
  label.append(select);
  form.append(label);
  if (row.split === "train") form.append(element("p", "승인한 학습용 질문은 내려받을 수 있습니다.", "meta"));
  const save = element("button", "평가 저장", "button primary");
  save.type = "submit";
  const feedback = element("p", "", "feedback");
  feedback.setAttribute("role", "status");
  form.append(save, feedback);
  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (saving) return;
    saving = true;
    save.disabled = true;
    feedback.classList.remove("error");
    try {
      row.review = await fetchJson("/api/review/evaluation?question_id=" + encodeURIComponent(row.id), {
        method: "PUT",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(Object.fromEntries(new FormData(form))),
      });
      renderQueue();
      const saved = element("p", "평가를 저장했습니다.", "feedback");
      saved.setAttribute("role", "status");
      if (currentPage === "evaluation") byId("detail").append(saved);
    } catch (error) {
      feedback.textContent = error.message;
      feedback.classList.add("error");
    } finally {
      saving = false;
      save.disabled = false;
    }
  });
  editor.append(form);
  target.append(editor);
}

async function renderUsage() {
  const notice = byId("usage-notice");
  notice.hidden = true;
  try {
    const data = await fetchJson("/api/review/usage");
    byId("token-total").textContent = data.calls ? number.format(data.total) : "—";
    byId("call-total").textContent = number.format(data.calls);
    byId("usage-body").replaceChildren(...data.roles.map(role => {
      const row = element("tr");
      const label = element("th", roleNames[role.role]);
      label.scope = "row";
      row.append(label, ...["calls", "input", "output", "total"].map(key => element("td", number.format(role[key]))));
      return row;
    }));
    byId("usage-table").hidden = !data.roles.length;
  } catch (error) {
    notice.textContent = error.message;
    notice.hidden = false;
  }
}

tabs.forEach(button => button.addEventListener("click", () => {
  currentPage = button.dataset.page;
  tabs.forEach(tab => tab.setAttribute("aria-pressed", String(tab === button)));
  byId("workspace").hidden = currentPage === "usage";
  byId("usage").hidden = currentPage !== "usage";
  if (currentPage === "usage") renderUsage();
  else renderQueue();
}));

for (const id of ["search", "split", "status"]) {
  byId(id).addEventListener(id === "search" ? "input" : "change", () => {
    index = 0;
    selectedId = null;
    renderQueue();
  });
}
byId("previous").addEventListener("click", () => { index -= 1; renderQueue(); });
byId("next").addEventListener("click", () => { index += 1; renderQueue(); });

renderQueue();
try {
  const data = await fetchJson("/api/review");
  questions = data.questions;
  if (data.source_issues) {
    byId("load-notice").textContent = "일부 질문 자료를 불러오지 못했습니다.";
    byId("load-notice").hidden = false;
  }
} catch (error) {
  byId("load-notice").textContent = error.message;
  byId("load-notice").hidden = false;
} finally {
  hasLoaded = true;
  if (currentPage !== "usage") renderQueue();
}
