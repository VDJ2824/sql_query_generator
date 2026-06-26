const API_BASE_URL = "http://127.0.0.1:8000";

const state = {
  token: sessionStorage.getItem("sgip_sql_demo_token") || "",
  username: sessionStorage.getItem("sgip_sql_demo_username") || "",
  role: sessionStorage.getItem("sgip_sql_demo_role") || "",
  options: [],
  selectedOptionId: null,
  selectedOption: null,
  preview: null,
};

const els = {
  sessionBadge: document.getElementById("sessionBadge"),
  usernameInput: document.getElementById("usernameInput"),
  passwordInput: document.getElementById("passwordInput"),
  loginBtn: document.getElementById("loginBtn"),
  logoutBtn: document.getElementById("logoutBtn"),
  loginStatus: document.getElementById("loginStatus"),
  roleStatus: document.getElementById("roleStatus"),
  tablesStatus: document.getElementById("tablesStatus"),
  rowRules: document.getElementById("rowRules"),
  promptInput: document.getElementById("promptInput"),
  generateBtn: document.getElementById("generateBtn"),
  clearBtn: document.getElementById("clearBtn"),
  optionsContainer: document.getElementById("optionsContainer"),
  previewBtn: document.getElementById("previewBtn"),
  previewOutput: document.getElementById("previewOutput"),
  executionNotice: document.getElementById("executionNotice"),
  executeBtn: document.getElementById("executeBtn"),
  executionOutput: document.getElementById("executionOutput"),
  historyBtn: document.getElementById("historyBtn"),
  historyOutput: document.getElementById("historyOutput"),
  confirmModal: document.getElementById("confirmModal"),
  confirmExecuteBtn: document.getElementById("confirmExecuteBtn"),
  cancelExecuteBtn: document.getElementById("cancelExecuteBtn"),
  toast: document.getElementById("toast"),
};

const protectedControls = [
  els.generateBtn,
  els.clearBtn,
  els.previewBtn,
  els.executeBtn,
  els.historyBtn,
  els.promptInput,
];

function authHeaders() {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${state.token}`,
  };
}

async function apiRequest(path, options = {}) {
  const isProtectedCall = path !== "/login";
  const requestOptions = {...options};
  requestOptions.headers = isProtectedCall
    ? {...authHeaders(), ...(options.headers || {})}
    : options.headers || {"Content-Type": "application/json"};

  const response = await fetch(`${API_BASE_URL}${path}`, requestOptions);
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : {};

  if (!response.ok) {
    const message = payload.detail || `Request failed with status ${response.status}`;
    if (response.status === 401) {
      logout("Your session expired. Please log in again.");
    }
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }
  return payload;
}

async function protectedRequest(path, options = {}) {
  if (!state.token) {
    throw new Error("Login is required for this action.");
  }
  return apiRequest(path, options);
}

function showToast(message) {
  els.toast.textContent = message;
  els.toast.classList.remove("hidden");
  window.setTimeout(() => els.toast.classList.add("hidden"), 3200);
}

function showError(container, message) {
  container.innerHTML = `<p class="error-line">${escapeHtml(message)}</p>`;
}

function showLoading(container, message) {
  container.innerHTML = `<p class="loading-line">${escapeHtml(message)}</p>`;
}

function setButtonLoading(button, isLoading, loadingText = "Loading...") {
  if (!button.dataset.defaultText) {
    button.dataset.defaultText = button.textContent;
  }
  button.disabled = isLoading;
  button.textContent = isLoading ? loadingText : button.dataset.defaultText;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function updateSessionUi() {
  const isLoggedIn = Boolean(state.token);
  if (state.token) {
    els.sessionBadge.textContent = `${state.username} (${state.role})`;
    els.loginStatus.textContent = `Logged in as ${state.username} with role ${state.role}.`;
  } else {
    els.sessionBadge.textContent = "Not logged in";
    els.loginStatus.textContent = "Use a seeded account such as admin/admin123.";
  }
  els.roleStatus.textContent = state.role || "-";
  document.querySelectorAll(".protected-section").forEach((section) => {
    section.classList.toggle("locked", !isLoggedIn);
  });
  protectedControls.forEach((control) => {
    control.disabled = !isLoggedIn;
  });
  els.loginBtn.disabled = isLoggedIn;
  els.logoutBtn.disabled = !isLoggedIn;
  updateExecutionVisibility();
}

async function login() {
  const username = els.usernameInput.value.trim();
  const password = els.passwordInput.value;
  if (!username || !password) {
    showToast("Enter both username and password.");
    return;
  }

  try {
    setButtonLoading(els.loginBtn, true, "Logging in...");
    const payload = await apiRequest("/login", {
      method: "POST",
      body: JSON.stringify({username, password}),
    });
    state.token = payload.access_token;
    state.username = payload.username;
    state.role = payload.role;
    sessionStorage.setItem("sgip_sql_demo_token", state.token);
    sessionStorage.setItem("sgip_sql_demo_username", state.username);
    sessionStorage.setItem("sgip_sql_demo_role", state.role);
    updateSessionUi();
    await Promise.all([loadSecurityStatus(), loadHistory()]);
    showToast("Login successful.");
  } catch (error) {
    showToast(error.message);
  } finally {
    setButtonLoading(els.loginBtn, false);
  }
}

function logout(message = "") {
  sessionStorage.removeItem("sgip_sql_demo_token");
  sessionStorage.removeItem("sgip_sql_demo_username");
  sessionStorage.removeItem("sgip_sql_demo_role");
  state.token = "";
  state.username = "";
  state.role = "";
  state.options = [];
  state.selectedOptionId = null;
  state.selectedOption = null;
  state.preview = null;
  updateSessionUi();
  renderOptions([]);
  els.previewOutput.textContent = "Select one query option, then preview the security-enforced query.";
  els.executionOutput.textContent = "Execution results will appear here.";
  els.historyOutput.textContent = "Login to view your query history.";
  els.tablesStatus.textContent = "-";
  els.rowRules.textContent = "Login to load row-level restrictions.";
  updateExecutionVisibility();
  if (message) {
    showToast(message);
  }
}

async function loadSecurityStatus() {
  if (!state.token) return;

  try {
    const payload = await protectedRequest("/schema", {
      method: "GET",
    });
    els.roleStatus.textContent = payload.role;
    els.tablesStatus.textContent = payload.allowed_tables.map((table) => table.table_name).join(", ") || "-";
    els.rowRules.innerHTML = payload.allowed_tables.length
      ? payload.allowed_tables
          .map((table) => `<span class="rule-pill">${escapeHtml(table.table_name)}: ${escapeHtml(table.row_access_rule)}</span>`)
          .join("")
      : "No table access is available for this role.";
  } catch (error) {
    showToast(error.message);
  }
}

async function generateOptions() {
  if (!state.token) {
    showToast("Login before generating queries.");
    return;
  }

  const prompt = els.promptInput.value.trim();
  if (!prompt) {
    showToast("Enter a natural language request.");
    return;
  }

  try {
    setButtonLoading(els.generateBtn, true, "Generating...");
    showLoading(els.optionsContainer, "Generating query options...");
    const payload = await protectedRequest("/generate", {
      method: "POST",
      body: JSON.stringify({prompt}),
    });
    state.options = payload.query_options || [];
    state.selectedOptionId = null;
    state.selectedOption = null;
    state.preview = null;
    renderOptions(state.options);
    els.previewOutput.textContent = "Select one query option, then preview it.";
    els.executionOutput.textContent = "Execution results will appear here.";
    await loadHistory();
  } catch (error) {
    showError(els.optionsContainer, error.message);
    showToast(error.message);
  } finally {
    setButtonLoading(els.generateBtn, false);
    updateSessionUi();
  }
}

function renderOptions(options) {
  if (!options.length) {
    els.optionsContainer.className = "option-list empty-state";
    els.optionsContainer.textContent = "Generate options to review possible SQL queries.";
    return;
  }

  els.optionsContainer.className = "option-list";
  els.optionsContainer.innerHTML = options.map((option) => {
    const warnings = (option.warnings || [])
      .map((warning) => `<li>${escapeHtml(warning)}</li>`)
      .join("");
    return `
      <article class="option-card">
        <div class="option-header">
          <label class="option-title">
            <input type="radio" name="queryOption" value="${option.option_id}" />
            <span>
              <strong>${escapeHtml(option.title)}</strong><br />
              <small>${escapeHtml(option.explanation)}</small>
            </span>
          </label>
          <span class="meta-pill risk-${escapeHtml(String(option.risk_level).toLowerCase())}">
            ${escapeHtml(option.risk_level)}
          </span>
        </div>
        <h3>Generated SQL</h3>
        <pre class="sql-block">${escapeHtml(option.sql || "No executable SQL returned.")}</pre>
        <div class="meta-row">
          <span class="meta-pill">Tables: ${escapeHtml((option.tables_used || []).join(", ") || "-")}</span>
          <span class="meta-pill">Columns: ${escapeHtml((option.columns_used || []).join(", ") || "-")}</span>
          <span class="meta-pill status-${option.execution_allowed}">Execution allowed: ${option.execution_allowed}</span>
          <span class="meta-pill">Type: ${escapeHtml(option.query_type)}</span>
        </div>
        ${warnings ? `<ul class="warnings">${warnings}</ul>` : ""}
      </article>
    `;
  }).join("");

  document.querySelectorAll("input[name='queryOption']").forEach((radio) => {
    radio.addEventListener("change", () => {
      state.selectedOptionId = Number(radio.value);
      state.selectedOption = state.options.find((option) => option.option_id === state.selectedOptionId);
      state.preview = null;
      updateExecutionVisibility();
    });
  });
}

async function selectCurrentOption() {
  if (!state.selectedOption) {
    throw new Error("Select exactly one query option first.");
  }

  await protectedRequest("/select-query", {
    method: "POST",
    body: JSON.stringify({
      option_id: state.selectedOption.option_id,
      title: state.selectedOption.title,
      sql: state.selectedOption.sql,
      query_type: state.selectedOption.query_type,
    }),
  });
}

async function previewSelectedQuery() {
  if (!state.token) {
    showToast("Login before previewing.");
    return;
  }

  try {
    setButtonLoading(els.previewBtn, true, "Previewing...");
    showLoading(els.previewOutput, "Building safe preview...");
    await selectCurrentOption();
    const payload = await protectedRequest("/preview-selected-query", {
      method: "POST",
      body: JSON.stringify({selected_option_id: state.selectedOptionId}),
    });
    state.preview = payload;
    renderPreview(payload);
    updateExecutionVisibility();
  } catch (error) {
    showError(els.previewOutput, error.message);
    showToast(error.message);
  } finally {
    setButtonLoading(els.previewBtn, false);
    updateSessionUi();
  }
}

function renderPreview(payload) {
  const warningHtml = (payload.warnings || []).length
    ? `<ul class="warnings">${payload.warnings.map((warning) => `<li>${escapeHtml(warning)}</li>`).join("")}</ul>`
    : "";

  els.previewOutput.className = "preview-output";
  els.previewOutput.innerHTML = `
    <p><strong>Query type:</strong> ${escapeHtml(payload.query_type)}</p>
    <p><strong>Estimated rows:</strong> ${payload.estimated_rows}</p>
    <p><strong>Impact:</strong> ${escapeHtml(payload.impact_message)}</p>
    ${payload.generated_sql ? `<h3>Generated SQL</h3><pre class="sql-block">${escapeHtml(payload.generated_sql)}</pre>` : ""}
    ${payload.preview_sql ? `<h3>Preview Query</h3><pre class="sql-block">${escapeHtml(payload.preview_sql)}</pre>` : ""}
    ${payload.final_enforced_sql ? `<h3>Security-Enforced SQL</h3><pre class="sql-block">${escapeHtml(payload.final_enforced_sql)}</pre>` : ""}
    ${warningHtml}
    ${renderTable(payload.preview_rows)}
  `;
}

function updateExecutionVisibility() {
  const queryType = state.preview?.query_type || state.selectedOption?.query_type || "";
  const blockedTypes = ["TCL", "DCL", "DDL"];
  const backendAllowsExecution = state.preview
    ? state.preview.execution_allowed
    : Boolean(state.selectedOption?.execution_allowed);

  if (queryType === "TCL") {
    els.executionNotice.textContent = "TCL commands are view-only and cannot be executed.";
    els.executeBtn.classList.add("hidden");
    els.executeBtn.disabled = true;
    return;
  }

  if (blockedTypes.includes(queryType)) {
    els.executionNotice.textContent = `${queryType} commands cannot be executed in this application.`;
    els.executeBtn.classList.add("hidden");
    els.executeBtn.disabled = true;
    return;
  }

  els.executionNotice.textContent = state.preview
    ? backendAllowsExecution
      ? "Review the preview before execution."
      : "Backend response says execution is not allowed."
    : "Preview a query before executing it.";
  els.executeBtn.classList.remove("hidden");
  els.executeBtn.disabled = !state.token || !backendAllowsExecution;
}

async function executeSelectedQuery(confirmed = false) {
  if (!state.selectedOption) {
    showToast("Select one query option first.");
    return;
  }

  try {
    await selectCurrentOption();
    setButtonLoading(els.executeBtn, true, "Executing...");
    showLoading(els.executionOutput, "Submitting execution request...");
    const payload = await protectedRequest("/execute-selected-query", {
      method: "POST",
      body: JSON.stringify({
        selected_option_id: state.selectedOptionId,
        confirmed,
      }),
    });
    renderExecution(payload);
    await loadHistory();
  } catch (error) {
    showError(els.executionOutput, error.message);
    showToast(error.message);
  } finally {
    setButtonLoading(els.executeBtn, false);
    updateExecutionVisibility();
  }
}

function maybeExecuteSelectedQuery() {
  const queryType = state.preview?.query_type || state.selectedOption?.query_type || "";
  const requiresConfirmation = state.preview?.requires_confirmation
    || state.selectedOption?.requires_confirmation;
  if (["UPDATE", "INSERT", "DELETE"].includes(queryType) && requiresConfirmation) {
    els.confirmModal.classList.remove("hidden");
    return;
  }
  executeSelectedQuery(false);
}

function renderExecution(payload) {
  els.executionOutput.className = "output-box";
  els.executionOutput.innerHTML = `
    <p><strong>${payload.success ? "Success" : "Blocked"}:</strong> ${escapeHtml(payload.message)}</p>
    <p><strong>Rows affected:</strong> ${payload.rows_affected}</p>
    <p><strong>Execution allowed:</strong> ${payload.execution_allowed}</p>
    ${payload.generated_sql ? `<h3>Generated SQL</h3><pre>${escapeHtml(payload.generated_sql)}</pre>` : ""}
    ${payload.final_enforced_sql ? `<h3>Security-Enforced SQL</h3><pre>${escapeHtml(payload.final_enforced_sql)}</pre>` : ""}
    ${renderTable(payload.result_rows)}
  `;
}

async function loadHistory() {
  if (!state.token) return;

  try {
    const payload = await protectedRequest("/history", {
      method: "GET",
    });
    renderHistory(payload);
  } catch (error) {
    showError(els.historyOutput, error.message);
    showToast(error.message);
  }
}

function renderHistory(items) {
  if (!items.length) {
    els.historyOutput.className = "history-list empty-state";
    els.historyOutput.textContent = "No query history yet.";
    return;
  }

  els.historyOutput.className = "history-list";
  els.historyOutput.innerHTML = items.slice(0, 12).map((item) => `
    <article class="history-item">
      <strong>${escapeHtml(item.query_type)} - ${escapeHtml(item.status)}</strong>
      <p>${escapeHtml(item.prompt)}</p>
      <small>${escapeHtml(item.timestamp)} | Rows: ${item.rows_affected ?? "-"}</small>
    </article>
  `).join("");
}

function renderTable(rows) {
  if (!rows || !rows.length) {
    return `<p class="empty-state">No rows to display.</p>`;
  }

  const columns = Object.keys(rows[0]);
  const header = columns.map((column) => `<th>${escapeHtml(column)}</th>`).join("");
  const body = rows.map((row) => `
    <tr>
      ${columns.map((column) => `<td>${escapeHtml(row[column])}</td>`).join("")}
    </tr>
  `).join("");

  return `
    <table class="data-table">
      <thead><tr>${header}</tr></thead>
      <tbody>${body}</tbody>
    </table>
  `;
}

function clearPromptAndResults() {
  els.promptInput.value = "";
  state.options = [];
  state.selectedOptionId = null;
  state.selectedOption = null;
  state.preview = null;
  renderOptions([]);
  els.previewOutput.textContent = "Select one query option, then preview the security-enforced query.";
  els.executionOutput.textContent = "Execution results will appear here.";
}

els.loginBtn.addEventListener("click", login);
els.logoutBtn.addEventListener("click", logout);
els.generateBtn.addEventListener("click", generateOptions);
els.clearBtn.addEventListener("click", clearPromptAndResults);
els.previewBtn.addEventListener("click", previewSelectedQuery);
els.executeBtn.addEventListener("click", maybeExecuteSelectedQuery);
els.historyBtn.addEventListener("click", loadHistory);
els.confirmExecuteBtn.addEventListener("click", () => {
  els.confirmModal.classList.add("hidden");
  executeSelectedQuery(true);
});
els.cancelExecuteBtn.addEventListener("click", () => {
  els.confirmModal.classList.add("hidden");
});

updateSessionUi();
updateExecutionVisibility();
if (state.token) {
  loadSecurityStatus();
  loadHistory();
}
