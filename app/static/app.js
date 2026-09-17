const state = {
  format: "long",
  duration_minutes: 5,
  duration_seconds: 15,
  // vi-VN phải đứng TRƯỚC en-US: write-script-btn lấy "ngôn ngữ đầu tiên
  // đã chọn" (Array.from(Set)[0], theo đúng thứ tự thêm vào) làm ngôn ngữ
  // viết kịch bản — để sai thứ tự sẽ khiến kịch bản ra tiếng Anh dù người
  // dùng gõ ý tưởng bằng tiếng Việt (lỗi thật đã gặp, xem app.js dòng
  // write-script-btn).
  selectedLanguages: new Set(["vi-VN", "en-US"]),
  // Sổ Tay Nhân Vật (Bước 1, Mục 3 V3) — nguồn sự thật duy nhất cho danh
  // sách nhân vật, gửi kèm lúc sinh prompt cảnh (Bước 7) và lúc bắt đầu sản
  // xuất (Mục 8 — phát hiện nhân vật đổi hình dạng giữa các cảnh).
  characters: [],
  characterMax: 10,
  // Lựa chọn 2 (nút "Cách chạy" trước mục 1. Ý tưởng): "manual" = như cũ,
  // tự bấm từng nút; "auto" = sau khi "Tạo dự án" xong thì tự chạy hết
  // các bước tới "Tạo danh sách cảnh & Prompt" — xem runAutoPipeline().
  pipelineMode: "manual",
  // Nút "Dự án trước đó" (sidebar): mã định danh RIÊNG cho mỗi dự án, sinh ra lúc
  // bấm "Tạo dự án" (xem submit-btn) — dùng làm khoá lưu snapshot lẫn thư mục
  // projects/<projectId>/production/... (KHÔNG còn dùng chung "default" cho
  // mọi dự án, tránh dự án sau ghi đè video dự án trước). null = chưa "Tạo
  // dự án" lần nào trong tab này, chưa có gì để lưu.
  projectId: null,
  // Nút "Đăng bài" (sidebar): "auto" (mặc định) = video xong ngôn ngữ nào tự
  // đăng ngay lên các nền tảng đã bật (autoPublishPlatforms) + đã kết nối
  // (publishingStatusCache[p].configured); "manual" = giữ nguyên hành vi cũ,
  // người dùng tự tick chọn + bấm nút "Đăng" trong từng thẻ ngôn ngữ.
  publishMode: "auto",
  autoPublishPlatforms: new Set(),
};

const langGrid = document.getElementById("lang-grid");
const longDurations = document.getElementById("long-durations");
const shortDurations = document.getElementById("short-durations");
const longDurationSlider = document.getElementById("long-duration-slider");
const shortDurationSlider = document.getElementById("short-duration-slider");
const keyStatus = document.getElementById("key-status");
const storySection = document.getElementById("story-section");
const scriptSection = document.getElementById("script-section");
const notice = document.getElementById("notice");
const noticeText = document.getElementById("notice-text");
const noticeRetryBtn = document.getElementById("notice-retry-btn");
let languageNameByCode = {};
let retryAction = null;

// Bước hiện tại người dùng đang đứng — cập nhật thanh "Bước x/5" phía trên.
// done = đã xong (dấu tick xanh), current = đang làm (chấm tím đậm), còn lại = mờ, chưa tới.
let currentStepNumber = 1;
function setCurrentStep(stepNumber) {
  currentStepNumber = stepNumber;
  document.querySelectorAll(".step-node").forEach((node) => {
    const n = Number(node.dataset.step);
    node.classList.remove("current", "done");
    if (n < stepNumber) node.classList.add("done");
    else if (n === stepNumber) node.classList.add("current");
  });
}

// Thay cho alert() khô khan: hiện dòng chữ ấm áp ngay cạnh ô đang thiếu, không chặn màn hình.
function showFieldWarning(id) {
  const el = document.getElementById(id);
  el.classList.remove("visible");
  void el.offsetWidth; // reset animation nếu bấm nhiều lần liên tiếp
  el.classList.add("visible");
}
function hideFieldWarning(id) {
  document.getElementById(id).classList.remove("visible");
}

// Thay cho việc đổ JSON kỹ thuật ra màn hình: 1 câu tiếng Việt dễ hiểu + nút "Thử lại"
// giữ nguyên toàn bộ chữ người dùng đã gõ, không bắt làm lại từ đầu.
function showNotice(message, onRetry) {
  noticeText.textContent = message;
  retryAction = onRetry;
  notice.classList.add("visible");
  notice.scrollIntoView({ behavior: "smooth", block: "center" });
}
function hideNotice() {
  notice.classList.remove("visible");
  retryAction = null;
}
noticeRetryBtn.addEventListener("click", () => {
  const action = retryAction;
  hideNotice();
  if (action) action();
});

// Hiện đúng chữ theo ngôn ngữ đã lưu (mặc định tiếng Việt) ngay từ đầu — các thẻ
// data-i18n trong HTML đang để trống, phải gọi cái này thì chữ mới hiện ra.
i18n.apply(i18n.current);

setCurrentStep(1);

const apiKeyInputRow = document.getElementById("api-key-input-row");
const claudeCliWarning = document.getElementById("claude-cli-warning");
const codexCliWarning = document.getElementById("codex-cli-warning");
const geminiCliWarning = document.getElementById("gemini-cli-warning");

// Bước "Cài đặt LLM" (2026-09-14): gộp 3 tài khoản CLI (Claude/ChatGPT/Gemini)
// thành 1 thẻ bên trái có menu xổ xuống để chọn — mặc định Claude Pro/Max —
// còn "Dùng API key riêng" là thẻ riêng bên phải. Chỉ còn 2 thẻ để chọn,
// nhưng backend vẫn nhận đủ 4 giá trị cũ (api/claude_cli/codex_cli/gemini_cli),
// không đổi gì ở API server.
const CLI_BACKENDS = ["claude_cli", "codex_cli", "gemini_cli"];
const CLI_KEY_PREFIX = { claude_cli: "cli", codex_cli: "codex", gemini_cli: "gemini" };
// Trang tài khoản thật của từng dịch vụ — bấm "Mở tài khoản" là nhảy thẳng
// tới đây, KHÔNG chọn lại backend (xem stopPropagation trong .llm-account-link
// bên dưới), để người dùng xem/đăng nhập tài khoản mà không đổi lựa chọn hiện tại.
const CLI_ACCOUNT_LINKS = {
  claude_cli: "https://claude.ai",
  codex_cli: "https://chatgpt.com",
  gemini_cli: "https://gemini.google.com",
};
let lastCliBackend = "claude_cli"; // thẻ CLI nhớ lựa chọn gần nhất, kể cả khi đang chọn "API key riêng"

// Thẻ "Dùng API key riêng" (2026-09-17): giờ CŨNG có menu xổ xuống chọn 1
// trong 3 hãng (Anthropic/OpenAI/Google), giống hệt thẻ CLI bên cạnh — thay
// cho 1 radio "api" cứng duy nhất trước đây (chỉ Anthropic).
const API_BACKENDS = ["api", "openai_api", "gemini_api"];
const API_KEY_PREFIX = { api: "api_anthropic", openai_api: "api_openai", gemini_api: "api_gemini" };
const API_KEY_PLACEHOLDER = { api: "sk-ant-...", openai_api: "sk-proj-...", gemini_api: "AIzaSy..." };
const API_ACCOUNT_LINKS = {
  api: "https://console.anthropic.com/settings/keys",
  openai_api: "https://platform.openai.com/api-keys",
  gemini_api: "https://aistudio.google.com/apikey",
};
let lastApiBackend = "api"; // thẻ API nhớ lựa chọn gần nhất (Anthropic/OpenAI/Gemini), kể cả khi đang chọn tài khoản CLI

const llmCliCard = document.getElementById("llm-cli-card");
const llmCliCurrentTitle = document.getElementById("llm-cli-current-title");
const llmCliCurrentDesc = document.getElementById("llm-cli-current-desc");
const llmCliDropdownBtn = document.getElementById("llm-cli-dropdown-btn");
const llmCliDropdownMenu = document.getElementById("llm-cli-dropdown-menu");
const llmApiCard = document.getElementById("llm-api-card");
const llmApiCurrentTitle = document.getElementById("llm-api-current-title");
const llmApiCurrentDesc = document.getElementById("llm-api-current-desc");
const llmApiDropdownBtn = document.getElementById("llm-api-dropdown-btn");
const llmApiDropdownMenu = document.getElementById("llm-api-dropdown-menu");

// Bấm link "Mở tài khoản" chỉ để XEM/đăng nhập tài khoản đó — không được coi
// là bấm chọn thẻ/mục cha (tránh vừa mở tab mới vừa âm thầm đổi backend đang dùng).
document.querySelectorAll("#llm-backend-choice .llm-account-link").forEach((link) => {
  link.addEventListener("click", (e) => e.stopPropagation());
});

function closeCliDropdown() {
  llmCliDropdownMenu.hidden = true;
  llmCliCard.classList.remove("dropdown-open");
  llmCliDropdownBtn.setAttribute("aria-expanded", "false");
}

function closeApiDropdown() {
  llmApiDropdownMenu.hidden = true;
  llmApiCard.classList.remove("dropdown-open");
  llmApiDropdownBtn.setAttribute("aria-expanded", "false");
}

// Widget "Mở tài khoản" (2026-09-15, yêu cầu người dùng): app KHÔNG THỂ tự
// phát hiện tài khoản thật đã đăng nhập trên claude.ai/chatgpt.com/gemini.
// google.com — đó là domain khác, trình duyệt luôn chặn 1 trang web đọc
// cookie/phiên đăng nhập của trang web khác (quy tắc bảo mật cơ bản, không
// có cách nào lách hợp lệ). Vì vậy đây là NHÃN do chính người dùng tự gõ và
// lưu lại (localStorage, theo từng loại tài khoản CLI) để tự nhắc mình lần
// sau nên chọn tài khoản nào trên màn hình đăng nhập hiện ra — KHÔNG PHẢI
// cơ chế tự động chuyển thẳng vào đúng tài khoản đó. Mọi nhãn đã lưu VÀ link
// "đăng nhập tài khoản khác" đều mở CÙNG 1 địa chỉ (CLI_ACCOUNT_LINKS).
const SAVED_ACCOUNTS_STORAGE_KEY = "savedLlmAccounts";
const llmAccountWidget = document.getElementById("llm-account-widget");
const llmAccountTrigger = document.getElementById("llm-account-trigger");
const llmAccountPopover = document.getElementById("llm-account-popover");
const llmAccountSavedList = document.getElementById("llm-account-saved-list");
const llmAccountAddInput = document.getElementById("llm-account-add-input");
const llmAccountAddSaveBtn = document.getElementById("llm-account-add-save-btn");
const llmAccountGenericLink = document.getElementById("llm-account-generic-link");

function loadSavedAccounts(backend) {
  try {
    const all = JSON.parse(localStorage.getItem(SAVED_ACCOUNTS_STORAGE_KEY) || "{}");
    return Array.isArray(all[backend]) ? all[backend] : [];
  } catch {
    return [];
  }
}
function saveSavedAccounts(backend, list) {
  let all = {};
  try { all = JSON.parse(localStorage.getItem(SAVED_ACCOUNTS_STORAGE_KEY) || "{}"); } catch { /* ignore, start fresh */ }
  all[backend] = list;
  localStorage.setItem(SAVED_ACCOUNTS_STORAGE_KEY, JSON.stringify(all));
}

function renderAccountPopover() {
  const backend = lastCliBackend;
  const url = CLI_ACCOUNT_LINKS[backend];
  const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;");
  llmAccountGenericLink.href = url;
  const accounts = loadSavedAccounts(backend);
  llmAccountSavedList.innerHTML = accounts.length
    ? accounts
        .map(
          (label, i) => `<div class="llm-account-saved-item">
            <a href="${url}" target="_blank" rel="noopener noreferrer" title="${esc(label)}">${esc(label)}</a>
            <button type="button" class="llm-account-remove-btn" data-index="${i}" title="${i18n.t("llm_account_remove_title")}">✕</button>
          </div>`
        )
        .join("")
    : `<p class="hint">${i18n.t("llm_account_empty_hint")}</p>`;
  llmAccountSavedList.querySelectorAll(".llm-account-remove-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const list = loadSavedAccounts(backend);
      list.splice(Number(btn.dataset.index), 1);
      saveSavedAccounts(backend, list);
      renderAccountPopover();
    });
  });
}

function closeAccountPopover() {
  llmAccountPopover.hidden = true;
  llmAccountTrigger.setAttribute("aria-expanded", "false");
  llmAccountAddInput.value = "";
}
function openAccountPopover() {
  renderAccountPopover();
  llmAccountPopover.hidden = false;
  llmAccountTrigger.setAttribute("aria-expanded", "true");
}
llmAccountTrigger.addEventListener("click", (e) => {
  e.stopPropagation();
  if (llmAccountPopover.hidden) openAccountPopover();
  else closeAccountPopover();
});
llmAccountPopover.addEventListener("click", (e) => e.stopPropagation());
llmAccountAddSaveBtn.addEventListener("click", () => {
  const label = llmAccountAddInput.value.trim();
  if (!label) return;
  const backend = lastCliBackend;
  const list = loadSavedAccounts(backend);
  if (!list.includes(label)) list.push(label);
  saveSavedAccounts(backend, list);
  llmAccountAddInput.value = "";
  renderAccountPopover();
});
llmAccountAddInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    llmAccountAddSaveBtn.click();
  }
});
document.addEventListener("click", (e) => {
  if (!llmAccountPopover.hidden && !llmAccountWidget.contains(e.target)) closeAccountPopover();
});

function renderCliCardText() {
  const prefix = CLI_KEY_PREFIX[lastCliBackend];
  llmCliCurrentTitle.textContent = i18n.t(`llm_backend_${prefix}_title`);
  llmCliCurrentDesc.textContent = i18n.t(`llm_backend_${prefix}_desc`);
  llmCliDropdownMenu.querySelectorAll(".llm-cli-dropdown-item").forEach((el) => {
    el.classList.toggle("selected", el.dataset.backend === lastCliBackend);
  });
  closeAccountPopover();
}
document.addEventListener("i18n-changed", renderCliCardText);

function renderApiCardText() {
  const prefix = API_KEY_PREFIX[lastApiBackend];
  llmApiCurrentTitle.textContent = i18n.t(`llm_backend_${prefix}_title`);
  llmApiCurrentDesc.textContent = i18n.t(`llm_backend_${prefix}_desc`);
  llmApiDropdownMenu.querySelectorAll(".llm-cli-dropdown-item").forEach((el) => {
    el.classList.toggle("selected", el.dataset.backend === lastApiBackend);
  });
  const input = document.getElementById("api-key-input");
  if (input) input.placeholder = API_KEY_PLACEHOLDER[lastApiBackend];
  const currentLink = document.getElementById("llm-api-current-link");
  if (currentLink) currentLink.href = API_ACCOUNT_LINKS[lastApiBackend];
}
document.addEventListener("i18n-changed", renderApiCardText);

function applyBackendUi(backend, cliAvailable) {
  const isCli = CLI_BACKENDS.includes(backend);
  const isApi = API_BACKENDS.includes(backend);
  if (isCli) lastCliBackend = backend;
  if (isApi) lastApiBackend = backend;
  renderCliCardText();
  renderApiCardText();
  llmCliCard.classList.toggle("selected", isCli);
  llmCliCard.setAttribute("aria-checked", String(isCli));
  llmApiCard.classList.toggle("selected", isApi);
  llmApiCard.setAttribute("aria-checked", String(isApi));
  apiKeyInputRow.hidden = !isApi;
  claudeCliWarning.hidden = !(backend === "claude_cli" && !cliAvailable.claude);
  codexCliWarning.hidden = !(backend === "codex_cli" && !cliAvailable.codex);
  geminiCliWarning.hidden = !(backend === "gemini_cli" && !cliAvailable.gemini);
}

function cliAvailabilityFrom(data) {
  return { claude: data.claude_cli_available, codex: data.codex_cli_available, gemini: data.gemini_cli_available };
}

async function loadKeyStatus() {
  const res = await fetch("/api/settings");
  const data = await res.json();
  keyStatus.textContent = i18n.t(data.llm_configured ? "apikey_ok" : "apikey_missing");
  keyStatus.className = "status-badge " + (data.llm_configured ? "ok" : "missing");
  applyBackendUi(data.llm_backend, cliAvailabilityFrom(data));
}

async function selectLlmBackend(backend) {
  const res = await fetch("/api/settings/llm-backend", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ backend }),
  });
  if (res.ok) {
    const data = await res.json();
    keyStatus.textContent = i18n.t(data.llm_configured ? "apikey_ok" : "apikey_missing");
    keyStatus.className = "status-badge " + (data.llm_configured ? "ok" : "missing");
    applyBackendUi(data.llm_backend, cliAvailabilityFrom(data));
  }
}

llmCliDropdownBtn.addEventListener("click", (e) => {
  e.stopPropagation();
  const willOpen = llmCliDropdownMenu.hidden;
  llmCliDropdownMenu.hidden = !willOpen;
  llmCliCard.classList.toggle("dropdown-open", willOpen);
  llmCliDropdownBtn.setAttribute("aria-expanded", String(willOpen));
});
llmCliDropdownMenu.querySelectorAll(".llm-cli-dropdown-item").forEach((item) => {
  item.addEventListener("click", (e) => {
    e.stopPropagation();
    closeCliDropdown();
    selectLlmBackend(item.dataset.backend);
  });
  item.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      e.stopPropagation();
      closeCliDropdown();
      selectLlmBackend(item.dataset.backend);
    }
  });
});
llmCliCard.addEventListener("click", () => {
  closeCliDropdown();
  selectLlmBackend(lastCliBackend);
});
llmCliCard.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    closeCliDropdown();
    selectLlmBackend(lastCliBackend);
  }
});
document.addEventListener("click", (e) => {
  if (!llmCliCard.contains(e.target)) closeCliDropdown();
  if (!llmApiCard.contains(e.target)) closeApiDropdown();
});

// Menu xổ xuống thẻ "Dùng API key riêng" — mirror y hệt thẻ CLI bên cạnh:
// bấm mũi tên để mở/đóng, bấm 1 hãng trong danh sách để CHỌN NGAY (kích
// hoạt backend đó luôn, không cần bấm thêm gì khác), bấm thân thẻ (ngoài
// mũi tên) để chọn lại đúng hãng đã nhớ gần nhất (lastApiBackend).
llmApiDropdownBtn.addEventListener("click", (e) => {
  e.stopPropagation();
  const willOpen = llmApiDropdownMenu.hidden;
  llmApiDropdownMenu.hidden = !willOpen;
  llmApiCard.classList.toggle("dropdown-open", willOpen);
  llmApiDropdownBtn.setAttribute("aria-expanded", String(willOpen));
});
llmApiDropdownMenu.querySelectorAll(".llm-cli-dropdown-item").forEach((item) => {
  item.addEventListener("click", (e) => {
    e.stopPropagation();
    closeApiDropdown();
    selectLlmBackend(item.dataset.backend);
  });
  item.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      e.stopPropagation();
      closeApiDropdown();
      selectLlmBackend(item.dataset.backend);
    }
  });
});
llmApiCard.addEventListener("click", () => {
  closeCliDropdown();
  selectLlmBackend(lastApiBackend);
});
llmApiCard.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    closeCliDropdown();
    selectLlmBackend(lastApiBackend);
  }
});

document.getElementById("save-key-btn").addEventListener("click", async () => {
  const input = document.getElementById("api-key-input");
  const key = input.value.trim();
  if (!key) {
    showNotice(i18n.t("notice_apikey_empty"), null);
    return;
  }
  const res = await fetch("/api/settings/api-key", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key: key, backend: lastApiBackend }),
  });
  if (res.ok) {
    input.value = "";
    await loadKeyStatus();
  } else {
    showNotice(i18n.t("notice_apikey_failed"), () =>
      document.getElementById("save-key-btn").click()
    );
  }
});

async function loadLanguages() {
  const res = await fetch("/api/languages");
  const data = await res.json();
  langGrid.innerHTML = "";
  data.languages.forEach((lang) => {
    languageNameByCode[lang.code] = lang.name;
    const pill = document.createElement("div");
    pill.className = "pill" + (state.selectedLanguages.has(lang.code) ? " selected" : "");
    pill.textContent = lang.name;
    pill.dataset.code = lang.code;
    pill.addEventListener("click", () => {
      if (state.selectedLanguages.has(lang.code)) {
        state.selectedLanguages.delete(lang.code);
      } else {
        state.selectedLanguages.add(lang.code);
      }
      pill.classList.toggle("selected");
      // Bước 7/10 (2026-09-14): các ô này giờ LUÔN hiện sẵn (không còn ẩn
      // chờ tới lúc có kịch bản) — đổi ngôn ngữ ở Bước 3 phải cập nhật
      // ngay chip/dropdown ở đó, không đợi tới khi viết kịch bản xong.
      revealProductionConfigSteps();
      scheduleSaveProjectSnapshot();
    });
    langGrid.appendChild(pill);
  });
  revealProductionConfigSteps();
}

// QUAN TRỌNG: chỉ chọn trong .format-grid (đúng 2 thẻ Dài/Short) — class
// .format-choice dùng CHUNG kiểu dáng với nhiều nhóm khác không liên quan
// (llm-backend-choice, run-mode-choice, attach-mode-choice); nếu chọn
// document.querySelectorAll(".format-choice") không giới hạn, bấm vào BẤT
// KỲ thẻ nào trong các nhóm kia cũng xoá nhầm "selected" của mọi nhóm khác
// trên trang và ghi đè state.format = undefined.
document.querySelectorAll(".format-grid .format-choice").forEach((el) => {
  el.addEventListener("click", () => {
    document.querySelectorAll(".format-grid .format-choice").forEach((x) => x.classList.remove("selected"));
    el.classList.add("selected");
    state.format = el.dataset.format;
    longDurations.style.display = state.format === "long" ? "flex" : "none";
    shortDurations.style.display = state.format === "short" ? "flex" : "none";
    longDurationSlider.style.display = state.format === "long" ? "flex" : "none";
    shortDurationSlider.style.display = state.format === "short" ? "flex" : "none";
    scheduleSaveProjectSnapshot();
  });
});

function wirePillGroup(container, key, slider) {
  container.querySelectorAll(".pill").forEach((el) => {
    el.addEventListener("click", () => {
      container.querySelectorAll(".pill").forEach((x) => x.classList.remove("selected"));
      el.classList.add("selected");
      const value = Number(el.dataset.duration);
      state[key] = value;
      if (slider) slider.setValue(value, { syncPills: false });
      scheduleSaveProjectSnapshot();
    });
  });
}

// Thanh trượt NGANG dùng chung — kéo giữ chuột/ngón tay để chọn BẤT KỲ số
// nguyên nào trong khoảng [min, max] của thanh đó. Dùng cho cả thời lượng
// video (Bước 2, ngoài 7 mốc có sẵn) VÀ số nhân vật tối đa (2 thanh 1-10 /
// 11-20, xem setupCharacterMaxSliders bên dưới). Dùng Pointer Events (không
// phải mousedown/touchstart riêng) vì 1 API duy nhất xử lý được cả chuột
// lẫn cảm ứng, và setPointerCapture giữ đúng thao tác kéo dù ngón tay/con
// trỏ lỡ trượt ra ngoài track lúc đang kéo.
//
// `onChange(value)` là callback DUY NHẤT thanh trượt gọi mỗi khi giá trị
// đổi (do kéo, bấm nút pill đồng bộ qua, hay phím mũi tên) — nơi gọi
// setupRangeSlider tự quyết định làm gì với giá trị đó (ghi vào state,
// đồng bộ pill, đồng bộ thanh trượt kia...), bản thân hàm này không biết
// gì về "duration" hay "character" cụ thể.
function setupRangeSlider(row, { initialValue, onChange }) {
  const min = Number(row.dataset.min);
  const max = Number(row.dataset.max);
  const track = row.querySelector(".range-slider-track");
  const fill = row.querySelector(".range-slider-fill");
  const handle = row.querySelector(".range-slider-handle");
  const valueLabel = row.querySelector(".range-slider-value strong");
  let currentValue = initialValue;

  function render(value) {
    const percent = ((value - min) / (max - min)) * 100;
    fill.style.width = `${percent}%`;
    handle.style.left = `${percent}%`;
    valueLabel.textContent = String(value);
    track.setAttribute("aria-valuenow", String(value));
  }

  function setValue(rawValue, { silent = false } = {}) {
    const value = Math.min(max, Math.max(min, Math.round(rawValue)));
    currentValue = value;
    render(value);
    if (!silent) onChange(value);
    return value;
  }

  function valueFromClientX(clientX) {
    const rect = track.getBoundingClientRect();
    const percentFromLeft = (clientX - rect.left) / rect.width;
    return min + percentFromLeft * (max - min);
  }

  let dragging = false;
  track.addEventListener("pointerdown", (e) => {
    dragging = true;
    track.setPointerCapture(e.pointerId);
    setValue(valueFromClientX(e.clientX));
  });
  track.addEventListener("pointermove", (e) => {
    if (!dragging) return;
    setValue(valueFromClientX(e.clientX));
  });
  const stopDragging = (e) => {
    if (!dragging) return;
    dragging = false;
    try { track.releasePointerCapture(e.pointerId); } catch { /* đã tự nhả trước đó, bỏ qua */ }
  };
  track.addEventListener("pointerup", stopDragging);
  track.addEventListener("pointercancel", stopDragging);
  // Bàn phím: mũi tên lên/xuống nhích từng đơn vị — không bắt buộc phải kéo
  // chuột mới dùng được (hỗ trợ người dùng bàn phím/trình đọc màn hình).
  track.addEventListener("keydown", (e) => {
    if (e.key === "ArrowUp" || e.key === "ArrowRight") { setValue(currentValue + 1); e.preventDefault(); }
    else if (e.key === "ArrowDown" || e.key === "ArrowLeft") { setValue(currentValue - 1); e.preventDefault(); }
  });

  render(initialValue);
  return { setValue, get value() { return currentValue; } };
}

function setupDurationSlider(row, { key, pillContainer }) {
  const api = setupRangeSlider(row, {
    initialValue: state[key],
    onChange: (value) => {
      state[key] = value;
      // Nếu giá trị kéo tới TRÙNG đúng 1 mốc có sẵn (VD kéo đúng 10 phút),
      // tô sáng lại đúng nút mốc đó luôn cho nhất quán — không thì bỏ chọn
      // hết các mốc, vì đang dùng giá trị tự chọn không khớp mốc nào.
      pillContainer.querySelectorAll(".pill").forEach((el) => {
        el.classList.toggle("selected", Number(el.dataset.duration) === value);
      });
      scheduleSaveProjectSnapshot();
    },
  });
  return { setValue: (v) => api.setValue(v, { silent: false }) };
}

longDurationSlider.sliderApi = setupDurationSlider(longDurationSlider, {
  key: "duration_minutes", pillContainer: longDurations,
});
shortDurationSlider.sliderApi = setupDurationSlider(shortDurationSlider, {
  key: "duration_seconds", pillContainer: shortDurations,
});
wirePillGroup(longDurations, "duration_minutes", longDurationSlider.sliderApi);
wirePillGroup(shortDurations, "duration_seconds", shortDurationSlider.sliderApi);

// Lấy nội dung "tốt nhất hiện có" theo thứ tự Kịch bản (Bước 5) > Câu chuyện
// đã viết lại (Bước 2) > Ý tưởng (Bước 1) — để các nút Chủ đề/Hook/Nhân
// vật/SEO dùng được ngay từ Bước 1, không bắt người dùng phải đi tuần tự
// qua từng bước trước mới bấm được.
function bestAvailableStoryText() {
  const script = document.getElementById("script-text").value.trim();
  if (script) return script;
  const story = document.getElementById("story-text").value.trim();
  if (story) return story;
  return document.getElementById("idea").value.trim();
}

document.querySelectorAll('#pipeline-mode-choice input[name="pipeline-mode"]').forEach((radio) => {
  radio.addEventListener("change", (e) => {
    state.pipelineMode = e.target.value;
    document.querySelectorAll("#pipeline-mode-choice .format-choice").forEach((el) => {
      el.classList.toggle("selected", el.dataset.mode === e.target.value);
    });
    scheduleSaveProjectSnapshot();
  });
});

document.getElementById("submit-btn").addEventListener("click", async () => {
  hideFieldWarning("idea-warning");
  hideFieldWarning("lang-warning");

  const idea = document.getElementById("idea").value.trim();
  if (!idea) {
    showFieldWarning("idea-warning");
    document.getElementById("idea").focus();
    return;
  }
  if (state.selectedLanguages.size === 0) {
    showFieldWarning("lang-warning");
    return;
  }

  const payload = {
    idea_or_story: idea,
    format: state.format,
    duration_minutes: state.format === "long" ? state.duration_minutes : null,
    duration_seconds: state.format === "short" ? state.duration_seconds : null,
    output_languages: Array.from(state.selectedLanguages),
  };

  const submitBtn = document.getElementById("submit-btn");
  submitBtn.disabled = true;
  submitBtn.textContent = i18n.t("submit_btn_loading");
  // Nút "Dự án trước đó": mỗi lần "Tạo dự án" thành công là 1 dự án MỚI, tách biệt
  // khỏi dự án trước đó trong cùng tab (nếu có) — xem state.projectId.
  state.projectId = crypto.randomUUID();
  try {
    const res = await fetch("/api/project", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) {
      showNotice(data.detail || i18n.t("notice_project_failed"), () =>
        document.getElementById("submit-btn").click()
      );
      return;
    }

    submitBtn.textContent = i18n.t("rewrite_loading");
    const rewriteRes = await fetch("/api/story/rewrite", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ idea_or_story: idea }),
    });
    const rewriteData = await rewriteRes.json();
    if (!rewriteRes.ok) {
      // data.detail: lý do THẬT từ server (VD hết hạn mức Claude CLI, chưa
      // cấu hình LLM...) — ưu tiên hiện cái này, chỉ fallback về thông báo
      // chung chung khi server không trả detail (VD lỗi mạng).
      showNotice(rewriteData.detail || i18n.t("notice_rewrite_failed"), () =>
        document.getElementById("submit-btn").click()
      );
      return;
    }
    document.getElementById("story-text").value = rewriteData.story;
    setCurrentStep(4);
    storySection.scrollIntoView({ behavior: "smooth" });
    saveProjectSnapshot();
    if (state.pipelineMode === "auto") {
      await runAutoPipeline(rewriteData.story);
    }
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = i18n.t("submit_btn");
  }
});

// Bước 3 (chủ đề & mục tiêu) — 4 ô kết quả, cho sửa tay được, đọc lại lúc
// bấm "Viết kịch bản" để gửi kèm (xem currentTheme() bên dưới).
document.getElementById("determine-theme-btn").addEventListener("click", async () => {
  const story = bestAvailableStoryText();
  if (!story) {
    showNotice(i18n.t("notice_story_empty"), null);
    document.getElementById("idea").focus();
    return;
  }
  const btn = document.getElementById("determine-theme-btn");
  btn.disabled = true;
  btn.textContent = i18n.t("determine_theme_btn_loading");
  try {
    const res = await fetch("/api/story/theme", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ story }),
    });
    const data = await res.json();
    if (!res.ok) {
      showNotice(data.detail || i18n.t("notice_theme_failed"), () =>
        document.getElementById("determine-theme-btn").click()
      );
      return;
    }
    document.getElementById("theme-audience").value = data.target_audience;
    document.getElementById("theme-pain-point").value = data.audience_pain_point;
    document.getElementById("theme-core-message").value = data.core_message;
    document.getElementById("theme-best-angle").value = data.best_angle;
    document.getElementById("theme-result").classList.remove("section-hidden");
    saveProjectSnapshot();
  } finally {
    btn.disabled = false;
    btn.textContent = i18n.t("determine_theme_btn");
  }
});

function currentTheme() {
  const target_audience = document.getElementById("theme-audience").value.trim();
  const audience_pain_point = document.getElementById("theme-pain-point").value.trim();
  const core_message = document.getElementById("theme-core-message").value.trim();
  const best_angle = document.getElementById("theme-best-angle").value.trim();
  if (!target_audience && !audience_pain_point && !core_message && !best_angle) return null;
  return { target_audience, audience_pain_point, core_message, best_angle };
}

// Bước 4 (hook mở đầu) — 20 câu chia 5 nhóm (accordion) + 3 câu đề xuất
// mạnh nhất nổi bật, chọn 1 câu (hoặc tự sửa) làm hook chính thức.
const HOOK_GROUP_NAMES = {
  to_mo: "Tò mò", bat_ngo: "Bất ngờ", noi_dau: "Đánh vào nỗi đau",
  loi_ich: "Lợi ích rõ ràng", cach_lam_moi: "Cách làm mới",
};

function selectHookText(text) {
  document.getElementById("chosen-hook-text").value = text;
  document.querySelectorAll("#hooks-result .hook-pick").forEach((el) => {
    el.classList.toggle("selected", el.dataset.hookText === text);
  });
  scheduleSaveProjectSnapshot();
}

// Nút "Dự án trước đó": nhớ lại nguyên dữ liệu hooks vừa sinh để lưu vào snapshot
// và phát lại đúng qua renderHooks() lúc mở lại dự án, không phải tự dựng
// lại HTML bằng tay ở chỗ khác (xem collectProjectState/restoreProjectFromSnapshot).
let lastHooksData = null;

function renderHooks(data) {
  lastHooksData = data;
  const esc = (s) => s.replace(/&/g, "&amp;").replace(/"/g, "&quot;");
  document.getElementById("hooks-top3-list").innerHTML = data.top_3
    .map((text) => `<div class="hook-pick" data-hook-text="${esc(text)}">${text}</div>`)
    .join("");

  const byGroup = {};
  data.candidates.forEach((c) => {
    (byGroup[c.group] = byGroup[c.group] || []).push(c.text);
  });
  document.getElementById("hooks-all-groups").innerHTML = Object.entries(byGroup)
    .map(([group, texts]) => `
      <details class="hook-group">
        <summary>${HOOK_GROUP_NAMES[group] || group} (${texts.length})</summary>
        ${texts.map((t) => `<div class="hook-pick" data-hook-text="${esc(t)}">${t}</div>`).join("")}
      </details>
    `)
    .join("");

  document.querySelectorAll("#hooks-result .hook-pick").forEach((el) => {
    el.addEventListener("click", () => selectHookText(el.dataset.hookText));
  });
  if (data.top_3.length) selectHookText(data.top_3[0]);
}

async function generateHooksRequest(story, theme) {
  const res = await fetch("/api/story/hooks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ story, theme }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || i18n.t("notice_hooks_failed"));
  return data;
}

document.getElementById("generate-hooks-btn").addEventListener("click", async () => {
  const story = bestAvailableStoryText();
  if (!story) {
    showNotice(i18n.t("notice_story_empty"), null);
    document.getElementById("idea").focus();
    return;
  }
  const btn = document.getElementById("generate-hooks-btn");
  btn.disabled = true;
  btn.textContent = i18n.t("generate_hooks_btn_loading");
  try {
    const data = await generateHooksRequest(story, currentTheme());
    renderHooks(data);
    document.getElementById("hooks-result").classList.remove("section-hidden");
    saveProjectSnapshot();
  } catch (e) {
    showNotice(e.message, () => document.getElementById("generate-hooks-btn").click());
  } finally {
    btn.disabled = false;
    btn.textContent = i18n.t("generate_hooks_btn");
  }
});

function currentScriptPayload(story) {
  const firstLangCode = Array.from(state.selectedLanguages)[0];
  const languageName = languageNameByCode[firstLangCode] || "Tiếng Việt";
  return {
    story: story,
    is_long_format: state.format === "long",
    duration_minutes: state.format === "long" ? state.duration_minutes : null,
    duration_seconds: state.format === "short" ? state.duration_seconds : null,
    language_name: languageName,
    theme: currentTheme(),
    chosen_hook: document.getElementById("chosen-hook-text").value.trim() || null,
  };
}

async function writeScriptRequest(payload) {
  const res = await fetch("/api/story/script", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || i18n.t("notice_script_failed"));
  return data;
}

// Skill 11 (narration-length-budget): hiện số từ lời đọc thật/ngân sách mục
// tiêu — CHỈ cảnh báo (giống Mục 8 quality_warnings), không tự động cắt bớt
// gì, người dùng tự sửa lại kịch bản nếu muốn.
function applyScriptResult(data) {
  document.getElementById("script-text").value = data.script;
  const narrationInfo = document.getElementById("narration-length-info");
  const narrationWarning = document.getElementById("narration-length-warning");
  if (typeof data.narration_word_count === "number") {
    narrationInfo.textContent = i18n
      .t("narration_length_info")
      .replace("{actual}", data.narration_word_count)
      .replace("{target}", data.narration_target_word_count);
    narrationWarning.classList.toggle("visible", !!data.narration_over_budget);
  }
  revealProductionConfigSteps();
}

document.getElementById("write-script-btn").addEventListener("click", async () => {
  const story = document.getElementById("story-text").value.trim();
  if (!story) {
    showNotice(i18n.t("notice_story_empty"), null);
    document.getElementById("story-text").focus();
    return;
  }
  const btn = document.getElementById("write-script-btn");
  btn.disabled = true;
  btn.textContent = i18n.t("write_script_btn_loading");
  try {
    const data = await writeScriptRequest(currentScriptPayload(story));
    applyScriptResult(data);
    setCurrentStep(5);
    scriptSection.scrollIntoView({ behavior: "smooth" });
    saveProjectSnapshot();
  } catch (e) {
    showNotice(e.message, () => document.getElementById("write-script-btn").click());
  } finally {
    btn.disabled = false;
    btn.textContent = i18n.t("write_script_btn");
  }
});

// Bước 11 (chấm điểm kịch bản trước khi tốn công/credit sản xuất thật).
document.getElementById("score-script-btn").addEventListener("click", async () => {
  const scriptText = document.getElementById("script-text").value.trim();
  if (!scriptText) {
    showNotice("Chưa có kịch bản để chấm điểm.", null);
    return;
  }
  const btn = document.getElementById("score-script-btn");
  btn.disabled = true;
  btn.textContent = "Đang chấm điểm...";
  try {
    const res = await fetch("/api/quality/score", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ script_text: scriptText }),
    });
    const data = await res.json();
    if (!res.ok) {
      showNotice(data.detail || "Không chấm được điểm.", null);
      return;
    }
    document.getElementById("score-summary").textContent =
      `Điểm trung bình: ${data.total_score}/10 — ${data.summary}`;
    document.getElementById("score-criteria-list").innerHTML = data.criteria
      .map((c) => `<div class="production-scene-item"><strong>${c.key}</strong>: ${c.score}/10 — ${c.comment}</div>`)
      .join("");
    document.getElementById("score-result").classList.remove("section-hidden");
  } finally {
    btn.disabled = false;
    btn.textContent = "Chấm điểm kịch bản (Bước 11)";
  }
});

// Cài đặt đăng bài mạng xã hội + nút "Đăng" sau khi video xong (2026-09-14).
// CHƯA TEST THẬT với tài khoản thật (chưa có API key nào) — xem cảnh báo ở
// đầu app/services/publishing.py.
let publishingStatusCache = null;

async function loadPublishingSettings() {
  const res = await fetch("/api/publishing/status");
  if (!res.ok) return;
  publishingStatusCache = await res.json();
  const container = document.getElementById("publishing-settings-list");
  container.innerHTML = Object.entries(publishingStatusCache)
    .map(([platform, info]) => `
      <div class="production-language-card" data-settings-platform="${platform}">
        <h4>${info.display_name} — ${info.configured ? "✅ Đã cấu hình" : "⬜ Chưa cấu hình"}</h4>
        ${info.requires_public_video_url ? `<p class="hint">⚠️ Nền tảng này cần video ở 1 URL công khai, không nhận tải file trực tiếp.</p>` : ""}
        ${info.fields.map((f) => `<input type="text" data-env-key="${f.env_key}" placeholder="${f.label}" style="display:block;width:100%;margin:6px 0;padding:8px" />`).join("")}
        <div style="display:flex;gap:8px;margin-top:8px">
          <button class="btn-secondary save-publishing-settings-btn" data-platform="${platform}">Lưu</button>
          <button class="btn-secondary clear-publishing-settings-btn" data-platform="${platform}">Xoá</button>
        </div>
      </div>
    `)
    .join("");

  container.querySelectorAll(".save-publishing-settings-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const platform = btn.dataset.platform;
      const card = container.querySelector(`[data-settings-platform="${platform}"]`);
      const values = {};
      card.querySelectorAll("input[data-env-key]").forEach((input) => {
        if (input.value.trim()) values[input.dataset.envKey] = input.value.trim();
      });
      const res2 = await fetch(`/api/publishing/settings/${platform}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ values }),
      });
      if (res2.ok) await loadPublishingSettings();
      else showNotice("Không lưu được cấu hình.", null);
    });
  });
  container.querySelectorAll(".clear-publishing-settings-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await fetch(`/api/publishing/settings/${btn.dataset.platform}`, { method: "DELETE" });
      await loadPublishingSettings();
    });
  });
}
loadPublishingSettings();

// Nút "Đăng" hiện trong mỗi thẻ ngôn ngữ đã xong (xem renderProductionLanguages).
const PUBLISH_TARGETS = ["youtube", "facebook", "instagram", "tiktok", "threads", "twitter_x", "zalo"];

function renderPublishPanel(jobId, lang) {
  if (!publishingStatusCache) return "";
  const checkboxes = PUBLISH_TARGETS.map((p) => {
    const info = publishingStatusCache[p];
    const disabled = !info.configured ? "disabled" : "";
    return `<label style="display:inline-flex;align-items:center;gap:4px;margin-right:12px;opacity:${info.configured ? 1 : 0.5}">
      <input type="checkbox" value="${p}" ${disabled} /> ${info.display_name}
    </label>`;
  }).join("");
  return `
    <div style="margin-top:12px;border-top:1px solid #eee;padding-top:12px">
      <p class="hint">Đăng video này lên:</p>
      <div class="publish-checkboxes" data-job="${jobId}" data-lang="${lang.language_code}">${checkboxes}</div>
      <button class="btn-secondary publish-selected-btn" data-job="${jobId}" data-lang="${lang.language_code}" style="margin-top:8px">Đăng lên các nền tảng đã chọn</button>
      <div class="publish-results" data-job="${jobId}" data-lang="${lang.language_code}"></div>
    </div>
  `;
}

document.getElementById("production-languages").addEventListener("click", async (e) => {
  if (!e.target.classList.contains("publish-selected-btn")) return;
  const btn = e.target;
  const jobId = btn.dataset.job;
  const langCode = btn.dataset.lang;
  const checkboxes = document.querySelector(`.publish-checkboxes[data-job="${jobId}"][data-lang="${langCode}"]`);
  const selected = Array.from(checkboxes.querySelectorAll("input:checked")).map((i) => i.value);
  if (selected.length === 0) {
    showNotice("Chưa chọn nền tảng nào để đăng.", null);
    return;
  }
  const resultsBox = document.querySelector(`.publish-results[data-job="${jobId}"][data-lang="${langCode}"]`);
  btn.disabled = true;
  try {
    for (const platform of selected) {
      const res = await fetch("/api/publishing/publish", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ platform, job_id: jobId, language_code: langCode }),
      });
      const data = await res.json();
      const line = document.createElement("p");
      line.className = "hint";
      if (res.ok && data.success) {
        line.textContent = `✅ ${platform}: đăng thành công — ${data.post_url}`;
      } else {
        line.textContent = `❌ ${platform}: ${data.error || data.detail || "lỗi không rõ"}`;
      }
      resultsBox.appendChild(line);
    }
  } finally {
    btn.disabled = false;
  }
});

// Bước 12 mở rộng (2026-09-14): sinh tiêu đề/caption/hashtag CHUẨN SEO
// riêng cho từng nền tảng — mỗi nền tảng có 1 bộ quy tắc khác nhau, KHÔNG
// dùng chung 1 bản mô tả (xem quality_review.py::generate_seo_metadata).
const PLATFORM_LABELS = {
  youtube: "YouTube",
  tiktok: "TikTok",
  facebook_instagram: "Facebook & Instagram",
  threads: "Threads",
  twitter_x: "Twitter/X",
  zalo: "Zalo",
};

async function seoRequest(scriptText, platform) {
  const res = await fetch("/api/quality/seo", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ script_text: scriptText, platform }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Không sinh được nội dung SEO.");
  return data;
}

function renderSeoResult(platform, data) {
  const box = document.createElement("div");
  box.className = "production-language-card";
  box.innerHTML = `
    <h4>${PLATFORM_LABELS[platform] || platform}</h4>
    ${data.title ? `<p style="font-weight:700">${data.title}</p>` : ""}
    <p style="white-space:pre-wrap">${data.caption_or_description}</p>
    <p class="hint">${data.hashtags.join(" ")}</p>
    <p class="hint">💡 ${data.tip}</p>
  `;
  document.getElementById("seo-results").prepend(box);
}

document.querySelectorAll(".seo-btn").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const scriptText = bestAvailableStoryText();
    if (!scriptText) {
      showNotice("Cần có ít nhất Ý tưởng, Câu chuyện hoặc Kịch bản trước khi sinh nội dung SEO.", null);
      return;
    }
    const platform = btn.dataset.platform;
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = "Đang soạn...";
    try {
      const data = await seoRequest(scriptText, platform);
      renderSeoResult(platform, data);
    } catch (e) {
      showNotice(e.message, null);
    } finally {
      btn.disabled = false;
      btn.textContent = originalText;
    }
  });
});

// Bước 9+10+13 nối liền (Nhiệm vụ hoàn thiện app, 2026-09-14): từ kịch bản
// đã có timestamp -> tự chia cảnh -> tự sinh prompt -> tự tạo qua Google
// Flow -> tự dựng video -> tự lồng SFX theo từng cảnh. Chạy nền ở server,
// trang này chỉ polling tiến độ mỗi 4 giây.
const step6Section = document.getElementById("step6-section");
const step7Section = document.getElementById("step7-section");
const step8Section = document.getElementById("step8-section");
const step9Section = document.getElementById("step9-section");
const step10Section = document.getElementById("step10-section");
const productionStageText = document.getElementById("production-stage-text");
const sceneRowBoxes = document.getElementById("scene-row-boxes");
const sceneRowStatus = document.getElementById("scene-row-status");
const productionLanguagesEl = document.getElementById("production-languages");
const sceneReviewBanner = document.getElementById("scene-review-banner");
const sceneReviewText = document.getElementById("scene-review-text");
const approveSceneBtn = document.getElementById("approve-scene-btn");
const retrySceneBtn = document.getElementById("retry-scene-btn");
const skipSceneBtn = document.getElementById("skip-scene-btn");
// Bước 6: bấm vào 1 ô cảnh "Đã bỏ qua" để xem lại/khôi phục — banner riêng,
// không lẫn với sceneReviewBanner (banner đó chỉ hiện khi job ĐANG dừng chờ
// duyệt 1 cảnh, còn banner này hiện khi người dùng CHỦ ĐỘNG bấm vào 1 cảnh
// đã bỏ qua trước đó, job có thể vẫn đang chạy các cảnh khác song song).
const sceneRestoreBanner = document.getElementById("scene-restore-banner");
const sceneRestoreText = document.getElementById("scene-restore-text");
const restoreViewSceneBtn = document.getElementById("restore-view-scene-btn");
const restoreSceneBtn = document.getElementById("restore-scene-btn");
const restoreCloseBtn = document.getElementById("restore-close-btn");
let restoreSceneN = null;
// Bước 6: bấm vào 1 ô cảnh "Lỗi" (mà job đã chạy qua rồi, không dừng lại
// hỏi ngay như chế độ "review") để chọn tạo lại / bỏ qua / xoá file dở dang.
const sceneFailedBanner = document.getElementById("scene-failed-banner");
const sceneFailedText = document.getElementById("scene-failed-text");
const failedRetryBtn = document.getElementById("failed-retry-btn");
const failedSkipBtn = document.getElementById("failed-skip-btn");
const failedDeleteBtn = document.getElementById("failed-delete-btn");
const failedCloseBtn = document.getElementById("failed-close-btn");
let failedSceneN = null;
let currentProductionJobId = null;

// Bước 7/8/9/10 (2026-09-14): cấu hình đọc 1 LẦN lúc bấm "Bắt đầu sản xuất"
// (không đổi được giữa chừng như run_mode — xem production_pipeline.py).
// Hiện ra cùng lúc với Bước 5 (kịch bản) để người dùng chỉnh TRƯỚC khi bắt đầu.
const narrationVolumeSlider = document.getElementById("narration-volume-slider");
const narrationVolumeValue = document.getElementById("narration-volume-value");
narrationVolumeSlider.addEventListener("input", () => {
  narrationVolumeValue.textContent = `${Number(narrationVolumeSlider.value).toFixed(1)}×`;
  scheduleSaveProjectSnapshot();
});

const sfxVolumeSlider = document.getElementById("sfx-volume-slider");
const sfxVolumeValue = document.getElementById("sfx-volume-value");
sfxVolumeSlider.addEventListener("input", () => {
  const v = Number(sfxVolumeSlider.value);
  sfxVolumeValue.textContent = `${v >= 0 ? "+" : ""}${v.toFixed(1)} dB`;
  scheduleSaveProjectSnapshot();
});

// Bước 1 (Mục 3, V3): Sổ Tay Nhân Vật — trước đây app CHƯA có màn hình
// nhập nhân vật nên 2 chỗ gọi API storyboard/prompts và production/start
// LUÔN gửi characters: [] cứng; giờ lấy từ state.characters thật.
const characterListEl = document.getElementById("character-list");
const characterEmptyHint = document.getElementById("character-empty-hint");
const characterValidateStatus = document.getElementById("character-validate-status");

function renderCharacterList() {
  characterEmptyHint.classList.toggle("section-hidden", state.characters.length > 0);
  characterListEl.innerHTML = state.characters
    .map(
      (c, i) => `<div class="character-bible-item" data-index="${i}">
        <input type="text" class="profile-field character-name-input" placeholder="${i18n.t("character_name_placeholder")}" value="${(c.name || "").replace(/"/g, "&quot;")}" />
        <textarea class="character-desc-input" placeholder="${i18n.t("character_desc_placeholder")}">${c.description || ""}</textarea>
        <button type="button" class="character-remove-btn" title="${i18n.t("remove_character_title")}">✕</button>
      </div>`
    )
    .join("");
  characterListEl.querySelectorAll(".character-bible-item").forEach((item) => {
    const idx = Number(item.dataset.index);
    item.querySelector(".character-name-input").addEventListener("input", (e) => {
      state.characters[idx].name = e.target.value;
      scheduleSaveProjectSnapshot();
    });
    item.querySelector(".character-desc-input").addEventListener("input", (e) => {
      state.characters[idx].description = e.target.value;
      scheduleSaveProjectSnapshot();
    });
    item.querySelector(".character-remove-btn").addEventListener("click", () => {
      state.characters.splice(idx, 1);
      renderCharacterList();
      saveProjectSnapshot();
    });
  });
}
renderCharacterList();

// 2 thanh trượt SỐ NHÂN VẬT TỐI ĐA (thay cho 2 nút "Tối đa 10" / "Mở rộng
// tới 20" trước đây): thanh trái kéo 1-10, thanh phải kéo 11-20 — kéo bên
// nào thì bên đó trở thành characterMax hiện hành, thanh còn lại mờ đi
// (KHÔNG disable — vẫn kéo lại được bất cứ lúc nào để chuyển quyền chủ
// động sang thanh kia, chỉ mờ để người dùng biết đây không phải giá trị
// đang áp dụng).
const characterMaxLowRow = document.getElementById("character-max-slider-low");
const characterMaxHighRow = document.getElementById("character-max-slider-high");

function trySetCharacterMax(newMax, { sliderApi, revertValue }) {
  if (newMax < state.characters.length) {
    showFieldWarning("character-max-warning");
    sliderApi.setValue(revertValue, { silent: true });
    return;
  }
  hideFieldWarning("character-max-warning");
  state.characterMax = newMax;
  characterMaxLowRow.classList.toggle("inactive", newMax > 10);
  characterMaxHighRow.classList.toggle("inactive", newMax <= 10);
}

const characterMaxLowApi = setupRangeSlider(characterMaxLowRow, {
  initialValue: state.characterMax <= 10 ? state.characterMax : 10,
  onChange: (value) => trySetCharacterMax(value, { sliderApi: characterMaxLowApi, revertValue: state.characterMax }),
});
const characterMaxHighApi = setupRangeSlider(characterMaxHighRow, {
  initialValue: state.characterMax > 10 ? state.characterMax : 11,
  onChange: (value) => trySetCharacterMax(value, { sliderApi: characterMaxHighApi, revertValue: state.characterMax }),
});

document.getElementById("add-character-btn").addEventListener("click", () => {
  if (state.characters.length >= state.characterMax) {
    showFieldWarning("character-limit-warning");
    return;
  }
  hideFieldWarning("character-limit-warning");
  state.characters.push({ name: "", description: "" });
  renderCharacterList();
  saveProjectSnapshot();
  const inputs = characterListEl.querySelectorAll(".character-name-input");
  inputs[inputs.length - 1]?.focus();
});

async function suggestCharactersRequest(storyText) {
  const res = await fetch("/api/characters/suggest", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ story: storyText, max_characters: state.characterMax }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || i18n.t("notice_suggest_characters_failed"));
  return data;
}

document.getElementById("suggest-characters-btn").addEventListener("click", async () => {
  const storyText = bestAvailableStoryText();
  if (!storyText) {
    showNotice(i18n.t("notice_characters_need_story"), null);
    return;
  }
  if (state.characters.length > 0 && !window.confirm(i18n.t("confirm_replace_characters"))) return;
  const btn = document.getElementById("suggest-characters-btn");
  btn.disabled = true;
  const originalText = btn.textContent;
  btn.textContent = i18n.t("suggest_characters_btn_loading");
  try {
    const data = await suggestCharactersRequest(storyText);
    state.characters = data.characters || [];
    renderCharacterList();
    saveProjectSnapshot();
  } catch (e) {
    showNotice(e.message, () => document.getElementById("suggest-characters-btn").click());
  } finally {
    btn.disabled = false;
    btn.textContent = originalText;
  }
});

document.getElementById("validate-characters-btn").addEventListener("click", async () => {
  const validCharacters = currentCharactersPayload();
  const res = await fetch("/api/characters/validate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ characters: validCharacters, max_characters: state.characterMax }),
  });
  const data = await res.json();
  characterValidateStatus.classList.remove("section-hidden");
  if (res.ok) {
    characterValidateStatus.textContent = i18n.t("character_validate_ok").replace("{n}", data.count);
    characterValidateStatus.className = "status-badge ok";
  } else {
    characterValidateStatus.textContent = data.detail || i18n.t("character_validate_failed");
    characterValidateStatus.className = "status-badge missing";
  }
});

// Danh sách nhân vật thật sự dùng được (bỏ hàng trống người dùng vừa thêm
// nhưng chưa kịp điền) — dùng lúc sinh prompt cảnh và lúc bắt đầu sản xuất.
function currentCharactersPayload() {
  return state.characters
    .filter((c) => c.name.trim() && c.description.trim())
    .map((c) => ({ name: c.name.trim(), description: c.description.trim() }));
}

// Bước 9 (Nhiệm vụ 1, 2026-09-15): nút mở Chrome đăng nhập Google Flow thay
// cho việc người dùng phải tự gõ lệnh dòng lệnh trong màn hình Help.
document.getElementById("open-flow-browser-btn").addEventListener("click", async () => {
  const btn = document.getElementById("open-flow-browser-btn");
  const warningEl = document.getElementById("flow-browser-warning");
  hideFieldWarning("flow-browser-warning");
  btn.disabled = true;
  try {
    const res = await fetch("/api/production/open-flow-browser", { method: "POST" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      warningEl.textContent = data.detail || i18n.t("notice_flow_browser_failed");
      showFieldWarning("flow-browser-warning");
      return;
    }
    // Đã xác nhận THẬT (không còn báo mù quáng): "already_running" nghĩa là
    // Chrome hồ sơ Flow đã chạy sẵn từ trước — app chỉ cố đưa cửa sổ đó lên
    // trước mặt, KHÔNG mở thêm cửa sổ mới nào. Xem google_flow_driver.py.
    if (data.already_running) {
      showNotice(
        i18n.t(data.brought_to_front ? "notice_flow_browser_already_focused" : "notice_flow_browser_not_focused"),
        null
      );
    } else {
      showNotice(i18n.t("notice_flow_browser_launched"), null);
    }
  } catch {
    warningEl.textContent = i18n.t("notice_flow_browser_failed");
    showFieldWarning("flow-browser-warning");
  } finally {
    btn.disabled = false;
  }
});

document.querySelectorAll('#poster-choice input[name="poster-choice"]').forEach((radio) => {
  radio.addEventListener("change", (e) => {
    document.querySelectorAll("#poster-choice .format-choice").forEach((el) => {
      el.classList.toggle("selected", el.dataset.poster === e.target.value);
    });
    scheduleSaveProjectSnapshot();
  });
});

const exportSingleLangSelect = document.getElementById("export-single-lang-select");
document.querySelectorAll('#export-mode-choice input[name="export-mode"]').forEach((radio) => {
  radio.addEventListener("change", (e) => {
    document.querySelectorAll("#export-mode-choice .format-choice").forEach((el) => {
      el.classList.toggle("selected", el.dataset.export === e.target.value);
    });
    exportSingleLangSelect.classList.toggle("section-hidden", e.target.value !== "single");
    scheduleSaveProjectSnapshot();
  });
});

// Bước 6-10 giờ LUÔN hiện sẵn trên trang (không còn ẩn chờ tới lúc có
// kịch bản — người dùng yêu cầu 2026-09-14: các nút "Tạo dự án"/"Viết
// kịch bản"/"Bắt đầu sản xuất"/SEO phải luôn thấy được, bất kể Bước 1 đã
// có nội dung hay chưa). Hàm này chỉ còn việc điền ngôn ngữ đã chọn ở
// Bước 3 vào Bước 7 (chip hiển thị) và Bước 10 (dropdown xuất riêng lẻ) —
// gọi lại mỗi khi đổi ngôn ngữ ở Bước 3, hoặc sau khi viết kịch bản xong.
function revealProductionConfigSteps() {
  const codes = Array.from(state.selectedLanguages);
  document.getElementById("narration-lang-chips").innerHTML = codes
    .map((c) => `<span class="lang-chip">${languageNameByCode[c] || c}</span>`)
    .join("");
  exportSingleLangSelect.innerHTML = codes
    .map((c) => `<option value="${c}">${languageNameByCode[c] || c}</option>`)
    .join("");
}

function currentExportLanguageCodes() {
  const mode = document.querySelector('input[name="export-mode"]:checked')?.value || "all";
  if (mode === "single") return [exportSingleLangSelect.value];
  return Array.from(state.selectedLanguages);
}

// Bước 9, 2 chế độ chạy — đổi được bất cứ lúc nào, kể cả sau khi job đã bắt
// đầu (xem production_pipeline.py::set_run_mode). Trước khi bắt đầu job,
// chỉ đổi UI + nhớ lựa chọn để gửi kèm lúc bấm "Bắt đầu sản xuất".
function applyRunModeUi(mode) {
  document.querySelectorAll('input[name="run-mode"]').forEach((el) => { el.checked = el.value === mode; });
  document.querySelectorAll("#run-mode-choice .format-choice").forEach((el) => {
    el.classList.toggle("selected", el.dataset.mode === mode);
  });
}
document.querySelectorAll('input[name="run-mode"]').forEach((radio) => {
  radio.addEventListener("change", async (e) => {
    const mode = e.target.value;
    applyRunModeUi(mode);
    if (!currentProductionJobId) { scheduleSaveProjectSnapshot(); return; } // job chưa bắt đầu, chỉ cần nhớ lựa chọn
    const res = await fetch(`/api/production/${currentProductionJobId}/mode`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode }),
    });
    if (res.ok) pollProductionJob(currentProductionJobId); // cập nhật banner duyệt cảnh ngay, không đợi 4s
  });
});

function currentRunMode() {
  return document.querySelector('input[name="run-mode"]:checked')?.value || "auto";
}

async function resolveSceneReview(action) {
  const jobId = currentProductionJobId;
  const sceneN = approveSceneBtn.dataset.sceneN;
  if (!jobId || !sceneN || sceneReviewBanner.dataset.jobId !== jobId || approveSceneBtn.disabled) return;
  approveSceneBtn.disabled = true;
  retrySceneBtn.disabled = true;
  skipSceneBtn.disabled = true;
  try {
    const res = await fetch(`/api/production/${jobId}/scenes/${sceneN}/approve?action=${action}`, { method: "POST" });
    if (!res.ok) {
      const data = await res.json();
      throw new Error(data.detail || "Không gửi được lựa chọn duyệt cảnh. Hãy thử lại.");
    }
    await pollProductionJob(jobId);
  } catch (error) {
    if (jobId === currentProductionJobId) showNotice(error.message, null);
  } finally {
    approveSceneBtn.disabled = false;
    retrySceneBtn.disabled = false;
    skipSceneBtn.disabled = false;
  }
}
approveSceneBtn.addEventListener("click", () => resolveSceneReview("approve"));
retrySceneBtn.addEventListener("click", () => resolveSceneReview("retry"));
skipSceneBtn.addEventListener("click", () => resolveSceneReview("skip"));

function renderSceneReviewBanner(jobId, job) {
  if (jobId !== currentProductionJobId) return;
  const sn = job.awaiting_review_scene;
  if (sn == null) {
    sceneReviewBanner.classList.add("section-hidden");
    delete sceneReviewBanner.dataset.jobId;
    delete approveSceneBtn.dataset.sceneN;
    return;
  }
  sceneReviewBanner.dataset.jobId = jobId;
  sceneReviewBanner.classList.remove("section-hidden");
  sceneReviewText.textContent = `${i18n.t("scene_review_waiting_prefix")} ${sn} ${i18n.t("scene_review_waiting_suffix")}`;
  approveSceneBtn.dataset.sceneN = String(sn);
}

const STAGE_LABELS = {
  queued: "Đang xếp hàng chờ...",
  generating_scenes: "Đang tạo từng cảnh qua Google Flow (bước này lâu nhất, có thể mất nhiều phút)...",
  translating: "Đang dịch lời dẫn sang các ngôn ngữ đã chọn...",
  building_languages: "Đang dựng video cho từng ngôn ngữ đã chọn...",
  done: "Xong!",
  failed: "Có lỗi xảy ra.",
};

const LANGUAGE_STAGE_LABELS = {
  queued: "Đang chờ...",
  translating: "Đang dịch lời dẫn...",
  building_video: "Đang dựng giọng đọc + ghép video...",
  adding_sfx: "Đang nhờ Claude chọn hiệu ứng âm thanh...",
  adding_title: "Đang sinh tiêu đề + ghép poster...",
  done: "Xong!",
  failed: "Lỗi.",
};

function beatsForProduction(beats, scenes) {
  const beatList = beats.map((b, i) => ({
    label: `beat_${i}`,
    start_sec: b.start_sec,
    end_sec: b.end_sec,
    narration_text: b.text,
    scene_ns: [],
  }));
  for (const s of scenes) {
    const beat =
      beatList.find((b) => s.start_sec >= b.start_sec && s.start_sec < b.end_sec) ||
      beatList[beatList.length - 1];
    beat.scene_ns.push(s.scene_n);
  }
  return beatList.filter((b) => b.scene_ns.length > 0);
}

// Khung xem trước bên phải (2026-09-14, xem index.html #workspace-preview):
// 4 trạng thái người dùng yêu cầu — đang duyệt 1 cảnh / chưa có lời dẫn /
// có lời dẫn / có lời dẫn + SFX nền ("hoàn chỉnh"). Video trung gian lấy
// từ app/api/production.py (video/raw + video?stage=narration|sfx|final).
const previewLangWrap = document.getElementById("preview-lang-wrap");
const previewLangSelect = document.getElementById("preview-lang-select");
const previewVideoEl = document.getElementById("preview-video");
const previewEmptyHint = document.getElementById("preview-empty-hint");

// Thu gọn/mở toàn bộ khung xem trước (2026-09-14) — thu gọn thì cột trái
// về lại full-width như trước khi có cột preview; nhớ lựa chọn qua
// localStorage để lần sau mở app vẫn giữ đúng trạng thái đã chọn.
const pageScrollEl = document.querySelector(".page-scroll");
const previewCollapseBtn = document.getElementById("preview-collapse-btn");
const previewExpandBtn = document.getElementById("preview-expand-btn");
function setPreviewCollapsed(collapsed) {
  pageScrollEl.classList.toggle("preview-collapsed", collapsed);
  previewExpandBtn.classList.toggle("section-hidden", !collapsed);
  localStorage.setItem("previewCollapsed", collapsed ? "1" : "0");
}
previewCollapseBtn.addEventListener("click", () => setPreviewCollapsed(true));
previewExpandBtn.addEventListener("click", () => setPreviewCollapsed(false));
setPreviewCollapsed(localStorage.getItem("previewCollapsed") === "1");

let previewStage = null;
let previewLangCode = null;
let previewLastSrc = null;
let lastForcedReviewScene = null;
let previewJobId = null;
let previewJob = null;
let previewSceneN = null;
let previewSelectionManual = false;

function setPreviewStage(stage) {
  previewStage = stage;
  document.querySelectorAll(".preview-tab").forEach((btn) => btn.classList.toggle("active", btn.dataset.stage === stage));
}
document.querySelectorAll(".preview-tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    if (btn.disabled) return;
    previewSelectionManual = true;
    setPreviewStage(btn.dataset.stage);
    updatePreviewVideoSrc();
  });
});
previewLangSelect.addEventListener("change", () => {
  previewSelectionManual = true;
  previewLangCode = previewLangSelect.value;
  updatePreviewVideoSrc();
});

// Cảnh xem được ở khung "Xem trước" = đã "Xong", HOẶC "Đã bỏ qua" nhưng vẫn
// còn video cũ (skip SAU KHI tạo thành công — xem has_video ở job.to_dict()).
function _sceneIsViewable(s) {
  return !!s && (s.status === "done" || (s.status === "skipped" && s.has_video));
}

function availablePreviewScene(job, preferredScene = previewSceneN) {
  const scenes = job?.scenes || {};
  if (preferredScene != null && _sceneIsViewable(scenes[preferredScene])) return Number(preferredScene);
  if (job?.awaiting_review_scene != null && scenes[job.awaiting_review_scene]?.status === "done") {
    return Number(job.awaiting_review_scene);
  }
  const completed = Object.keys(scenes).filter((sceneN) => scenes[sceneN].status === "done").map(Number);
  return completed.length ? Math.max(...completed) : null;
}

function selectPreviewScene(sceneN) {
  if (previewJobId !== currentProductionJobId || !_sceneIsViewable(previewJob?.scenes[sceneN])) return;
  previewSceneN = Number(sceneN);
  previewSelectionManual = true;
  setPreviewStage("scene");
  updatePreviewVideoSrc();
  renderProductionScenes(previewJob);
}

// Bước 6: bấm vào 1 ô cảnh "Đã bỏ qua" để mở banner riêng — xem lại video cũ
// (nếu còn) hoặc khôi phục (đưa lại vào video / tạo lại nếu chưa từng có
// video) — xem production_pipeline.restore_scene() cho giới hạn (chỉ hoạt
// động trong lúc job còn đang ở bước tạo cảnh).
function openSceneRestoreBanner(sceneN) {
  const scene = previewJob?.scenes?.[sceneN];
  if (previewJobId !== currentProductionJobId || !scene || scene.status !== "skipped") return;
  restoreSceneN = Number(sceneN);
  const textKey = scene.has_video ? "restore_scene_has_video_text" : "restore_scene_no_video_text";
  sceneRestoreText.textContent = i18n.t(textKey).replace("{n}", sceneN);
  restoreViewSceneBtn.disabled = !scene.has_video;
  sceneRestoreBanner.classList.remove("section-hidden");
  sceneRestoreBanner.scrollIntoView({ behavior: "smooth", block: "nearest" });
}
function closeSceneRestoreBanner() {
  restoreSceneN = null;
  sceneRestoreBanner.classList.add("section-hidden");
}
restoreViewSceneBtn.addEventListener("click", () => {
  if (restoreSceneN != null) selectPreviewScene(restoreSceneN);
});
restoreCloseBtn.addEventListener("click", closeSceneRestoreBanner);
restoreSceneBtn.addEventListener("click", async () => {
  if (!currentProductionJobId || restoreSceneN == null) return;
  const jobId = currentProductionJobId;
  const sceneN = restoreSceneN;
  restoreSceneBtn.disabled = true;
  restoreViewSceneBtn.disabled = true;
  try {
    const res = await fetch(`/api/production/${jobId}/scenes/${sceneN}/restore`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) {
      showNotice(data.detail || i18n.t("restore_scene_failed_notice"), null);
      return;
    }
    closeSceneRestoreBanner();
    // "done" ngay = video cũ còn nguyên, khôi phục tức thì. "generating" =
    // đang tạo lại nền — cứ để khung Bước 6 tự cập nhật qua polling như 1
    // cảnh bình thường, không cần thêm thông báo cho trường hợp này.
    if (data.scenes?.[String(sceneN)]?.status === "done") {
      showNotice(i18n.t("restore_scene_success_notice").replace("{n}", sceneN), null);
    }
    await pollProductionJob(jobId);
  } catch (error) {
    showNotice(i18n.t("restore_scene_failed_notice"), null);
  } finally {
    restoreSceneBtn.disabled = false;
    restoreViewSceneBtn.disabled = false;
  }
});

// Bước 6: bấm vào 1 ô cảnh "Lỗi" mà job đã chạy qua rồi (chế độ "auto"
// không dừng lại hỏi ngay như "review") để mở banner riêng — chọn tạo lại /
// bỏ qua / xoá file dở dang. Xem production_pipeline.resolve_failed_scene()
// cho giới hạn (chỉ hoạt động trong lúc job còn đang ở bước tạo cảnh).
function openSceneFailedBanner(sceneN) {
  const scene = previewJob?.scenes?.[sceneN];
  if (previewJobId !== currentProductionJobId || !scene || scene.status !== "failed") return;
  failedSceneN = Number(sceneN);
  sceneFailedText.textContent = i18n.t("failed_scene_text")
    .replace("{n}", sceneN)
    .replace("{error}", scene.error || "?");
  sceneFailedBanner.classList.remove("section-hidden");
  sceneFailedBanner.scrollIntoView({ behavior: "smooth", block: "nearest" });
}
function closeSceneFailedBanner() {
  failedSceneN = null;
  sceneFailedBanner.classList.add("section-hidden");
}
failedCloseBtn.addEventListener("click", closeSceneFailedBanner);

async function resolveFailedScene(action) {
  if (!currentProductionJobId || failedSceneN == null) return;
  const jobId = currentProductionJobId;
  const sceneN = failedSceneN;
  [failedRetryBtn, failedSkipBtn, failedDeleteBtn].forEach((btn) => { btn.disabled = true; });
  try {
    const res = await fetch(`/api/production/${jobId}/scenes/${sceneN}/resolve-failed?action=${action}`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) {
      showNotice(data.detail || i18n.t("failed_scene_action_failed_notice"), null);
      return;
    }
    closeSceneFailedBanner();
    // "retry" chạy nền — để khung Bước 6 tự cập nhật qua polling như 1 cảnh
    // bình thường, chỉ cần 1 câu thông báo ngắn xác nhận đã bắt đầu.
    const noticeKey = action === "retry" ? "failed_scene_notice_retrying"
      : action === "delete" ? "failed_scene_notice_deleted" : "failed_scene_notice_skipped";
    showNotice(i18n.t(noticeKey).replace("{n}", sceneN), null);
    await pollProductionJob(jobId);
  } catch (error) {
    showNotice(i18n.t("failed_scene_action_failed_notice"), null);
  } finally {
    [failedRetryBtn, failedSkipBtn, failedDeleteBtn].forEach((btn) => { btn.disabled = false; });
  }
}
failedRetryBtn.addEventListener("click", () => resolveFailedScene("retry"));
failedSkipBtn.addEventListener("click", () => resolveFailedScene("skip"));
failedDeleteBtn.addEventListener("click", () => resolveFailedScene("delete"));

sceneRowBoxes.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-scene-n]");
  if (!button || button.disabled) return;
  const sceneN = button.dataset.sceneN;
  const status = previewJob?.scenes?.[sceneN]?.status;
  if (status === "skipped") {
    closeSceneFailedBanner();
    openSceneRestoreBanner(sceneN);
  } else if (status === "failed") {
    closeSceneRestoreBanner();
    openSceneFailedBanner(sceneN);
  } else {
    closeSceneRestoreBanner();
    closeSceneFailedBanner();
    selectPreviewScene(sceneN);
  }
});

function computePreviewSrc(jobId, job, stage, langCode) {
  if (!jobId || !job || !stage) return null;
  if (stage === "scene") {
    const sn = availablePreviewScene(job);
    return sn != null ? `/api/production/${jobId}/scenes/${sn}/video` : null;
  }
  if (stage === "raw") return job.raw_video_available ? `/api/production/${jobId}/video/raw` : null;
  if (stage === "narration" || stage === "sfx") {
    const lang = langCode ? job.languages[langCode] : null;
    if (!lang) return null;
    const available = stage === "narration" ? lang.narration_video_available : lang.sfx_video_available;
    return available ? `/api/production/${jobId}/video?language_code=${langCode}&stage=${stage}` : null;
  }
  return null;
}

function updatePreviewVideoSrc(job = previewJob) {
  const src = currentProductionJobId && previewJobId === currentProductionJobId && job
    ? computePreviewSrc(currentProductionJobId, job, previewStage, previewLangCode)
    : null;
  if (src) {
    if (previewLastSrc !== src) {
      previewVideoEl.src = src;
      previewLastSrc = src;
    }
    previewVideoEl.classList.remove("section-hidden");
    previewVideoEl.setAttribute("aria-label", previewStage === "scene" ? `Cảnh ${availablePreviewScene(job)}` : previewStage);
    const sceneTab = document.getElementById("preview-tab-scene");
    sceneTab.title = previewSceneN != null ? `Cảnh ${previewSceneN}` : "";
    previewEmptyHint.classList.add("section-hidden");
  } else {
    previewVideoEl.classList.add("section-hidden");
    previewEmptyHint.classList.remove("section-hidden");
    previewLastSrc = null;
  }
}

function resetPreviewPanel() {
  previewStage = null;
  previewLangCode = null;
  previewLastSrc = null;
  lastForcedReviewScene = null;
  previewJobId = null;
  previewJob = null;
  previewSceneN = null;
  previewSelectionManual = false;
  previewLangWrap.classList.add("section-hidden");
  previewLangSelect.innerHTML = "";
  delete previewLangSelect.dataset.rendered;
  document.querySelectorAll(".preview-tab").forEach((btn) => { btn.disabled = true; btn.classList.remove("active"); });
  previewVideoEl.removeAttribute("src");
  previewVideoEl.classList.add("section-hidden");
  previewEmptyHint.classList.remove("section-hidden");
}

function renderPreviewPanel(jobId, job) {
  if (jobId !== currentProductionJobId) return;
  if (previewJobId !== jobId) {
    resetPreviewPanel();
    previewJobId = jobId;
  }
  previewJob = job;
  const langCodes = Object.keys(job.languages);
  if (previewLangSelect.dataset.rendered !== langCodes.join(",")) {
    previewLangSelect.innerHTML = langCodes
      .map((c) => `<option value="${c}">${languageNameByCode[c] || c}</option>`)
      .join("");
    previewLangSelect.dataset.rendered = langCodes.join(",");
    if (!previewLangCode || !langCodes.includes(previewLangCode)) {
      previewLangCode = langCodes[0] || null;
      previewLangSelect.value = previewLangCode || "";
    }
  }
  previewLangWrap.classList.toggle("section-hidden", langCodes.length <= 1);

  const reviewScene = job.awaiting_review_scene;
  if (reviewScene != null && job.scenes[reviewScene]?.status === "done"
      && reviewScene !== lastForcedReviewScene && !previewSelectionManual
      && (previewVideoEl.paused || !previewLastSrc)) {
    previewSceneN = Number(reviewScene);
    setPreviewStage("scene");
  }
  lastForcedReviewScene = reviewScene;
  previewSceneN = availablePreviewScene(job);
  const sceneAvailable = previewSceneN != null;
  const rawAvailable = !!job.raw_video_available;
  const lang = previewLangCode ? job.languages[previewLangCode] : null;
  const narrationAvailable = !!(lang && lang.narration_video_available);
  const sfxAvailable = !!(lang && lang.sfx_video_available);
  const availableOf = { scene: sceneAvailable, raw: rawAvailable, narration: narrationAvailable, sfx: sfxAvailable };

  document.getElementById("preview-tab-scene").disabled = !sceneAvailable;
  document.getElementById("preview-tab-raw").disabled = !rawAvailable;
  document.getElementById("preview-tab-narration").disabled = !narrationAvailable;
  document.getElementById("preview-tab-sfx").disabled = !sfxAvailable;

  if (!previewStage || !availableOf[previewStage]) {
    const fallback = sfxAvailable ? "sfx" : narrationAvailable ? "narration" : rawAvailable ? "raw" : sceneAvailable ? "scene" : null;
    setPreviewStage(fallback);
  }
  updatePreviewVideoSrc(job);
}

// Bước 6 (2026-09-14): sơ đồ 2 hàng ngang song song — hàng trên là các ô
// cảnh (Cảnh 1 -> Cảnh 2 -> ... -> Cảnh N, N tuỳ kịch bản, KHÔNG cố định
// 37), hàng dưới là hiện trạng THẲNG HÀNG với đúng ô cảnh phía trên (cùng
// index trong danh sách -> cùng cột nhờ grid dùng chung số cột). Cuộn
// ngang khi nhiều cảnh (xem .scene-diagram-row trong style.css).
const ICON_OF_SCENE_STATUS = { queued: "⏳", generating: "🔄", done: "✅", failed: "❌", skipped: "⏭️" };
const LABEL_OF_SCENE_STATUS = { queued: "Chờ", generating: "Đang tạo", done: "Xong", failed: "Lỗi", skipped: "Đã bỏ qua" };

// Bước 8 (Mục 3, V3): icon nhỏ theo loại hình App tự quyết cho từng cảnh —
// chỉ hiển thị, không cho sửa tay (đúng đặc tả "App tự quyết").
const ICON_OF_SCENE_TYPE = { ai_video: "🎬", static_image: "🖼️", b_roll: "🌄", motion_text: "🔤", chart: "📊" };
const LABEL_OF_SCENE_TYPE = {
  ai_video: "Video AI", static_image: "Ảnh tĩnh", b_roll: "B-roll",
  motion_text: "Chữ động", chart: "Biểu đồ",
};

// Mục 8: cảnh báo chất lượng (nhân vật đổi hình dạng, giọng đọc lệch thời
// gian, chữ poster lỗi) — CHỈ hiển thị, không có nút "sửa tự động".
const qualityWarningsBanner = document.getElementById("quality-warnings-banner");
const qualityWarningsList = document.getElementById("quality-warnings-list");
function renderQualityWarnings(job) {
  const warnings = job.quality_warnings || [];
  if (!warnings.length) {
    qualityWarningsBanner.classList.add("section-hidden");
    return;
  }
  qualityWarningsBanner.classList.remove("section-hidden");
  qualityWarningsList.innerHTML = warnings
    .map((w) => `<li>${w.replace(/&/g, "&amp;").replace(/</g, "&lt;")}</li>`)
    .join("");
}

function renderProductionScenes(job) {
  const entries = Object.entries(job.scenes);
  const gridStyle = `grid-template-columns:repeat(${entries.length},minmax(84px,1fr))`;
  sceneRowBoxes.setAttribute("style", gridStyle);
  sceneRowStatus.setAttribute("style", gridStyle);
  const boxesHtml = entries
    .map(([sn, s]) => {
      const typeIcon = ICON_OF_SCENE_TYPE[s.scene_type] || "🎬";
      const typeLabel = LABEL_OF_SCENE_TYPE[s.scene_type] || s.scene_type;
      const selected = previewStage === "scene" && Number(sn) === previewSceneN;
      const clickable = s.status === "done" || s.status === "skipped" || s.status === "failed";
      return `<button type="button" class="scene-box" data-scene-n="${sn}" aria-pressed="${selected}" ${clickable ? "" : "disabled"} title="${typeLabel}">Cảnh ${sn}<span class="scene-type-badge">${typeIcon} ${typeLabel}</span></button>`;
    })
    .join("");
  if (sceneRowBoxes.dataset.renderedHtml !== boxesHtml) {
    sceneRowBoxes.innerHTML = boxesHtml;
    sceneRowBoxes.dataset.renderedHtml = boxesHtml;
  }
  const statusHtml = entries
    .map(([sn, s]) => `<div class="scene-status scene-status--${s.status}" title="${s.error ? s.error.replace(/"/g, "&quot;") : ""}">${ICON_OF_SCENE_STATUS[s.status] || "⏳"} ${LABEL_OF_SCENE_STATUS[s.status] || s.status}</div>`)
    .join("");
  if (sceneRowStatus.dataset.renderedHtml !== statusHtml) {
    sceneRowStatus.innerHTML = statusHtml;
    sceneRowStatus.dataset.renderedHtml = statusHtml;
  }
}

let productionPollTimer = null;
let productionPollVersion = 0;
// Nút "Dự án trước đó": bản job.to_dict() MỚI NHẤT nhận được — lưu kèm snapshot để
// nếu mở lại dự án SAU KHI server đã khởi động lại (job đã mất khỏi _JOBS,
// xem production_pipeline.py), vẫn còn cái để hiển thị lại (chỉ xem, không
// thao tác được nữa — xem restoreProjectFromSnapshot()).
let lastProductionStatus = null;
let lastSavedProductionStageKey = null;
// Bước 10 mở rộng (2026-09-17): "Tự động tải về" (mặc định) vs "Tự chọn nơi
// lưu" — nhớ lại (jobId, language_code) nào ĐÃ tự tải để không tải lặp lại
// mỗi 4s polling (renderProductionLanguages gọi lại liên tục trong lúc job
// còn "đang chạy" ở CÁC NGÔN NGỮ KHÁC — 1 ngôn ngữ xong trước không nên bị
// tải đi tải lại tới khi ngôn ngữ cuối cùng xong).
const autoDownloadedVideoKeys = new Set();

function currentDownloadMode() {
  return document.querySelector('input[name="download-mode"]:checked')?.value || "auto";
}

document.querySelectorAll('#download-mode-choice input[name="download-mode"]').forEach((radio) => {
  radio.addEventListener("change", () => {
    document.querySelectorAll("#download-mode-choice .format-choice").forEach((el) => {
      el.classList.toggle("selected", el.dataset.download === radio.value);
    });
  });
});

// Tạo 1 thẻ <a> ẩn rồi tự bấm — cách chuẩn để ép trình duyệt TẢI VỀ (không
// điều hướng rời trang) 1 URL cùng gốc (server đã trả Content-Disposition:
// attachment cho mọi route video, xem app/api/production.py — nên kể cả
// không set `a.download` trình duyệt vẫn tải chứ không phát video).
function triggerFileDownload(url) {
  const a = document.createElement("a");
  a.href = url;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

// Nút "Tải video" (chế độ "Tự chọn nơi lưu"): dùng File System Access API
// (`showSaveFilePicker`, chỉ Chrome/Edge — đúng trình duyệt app đã yêu cầu
// dùng cho Google Flow) để bật hẳn hộp thoại "Lưu vào đâu" của hệ điều
// hành, KHÔNG chỉ tải vào thư mục Downloads mặc định như link tải thường.
// Trình duyệt không hỗ trợ (Firefox/Safari) hoặc người dùng bấm Huỷ hộp
// thoại chọn hãng chưa hỗ trợ -> rơi về triggerFileDownload() như bình
// thường (vẫn tải được, chỉ không tự chọn được thư mục).
async function downloadWithPicker(url, suggestedName) {
  if (window.showSaveFilePicker) {
    try {
      const handle = await window.showSaveFilePicker({
        suggestedName,
        types: [{ description: "Video MP4", accept: { "video/mp4": [".mp4"] } }],
      });
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const writable = await handle.createWritable();
      await res.body.pipeTo(writable);
      return;
    } catch (err) {
      if (err && err.name === "AbortError") return; // người dùng bấm Huỷ hộp thoại — không làm gì thêm
      console.warn("showSaveFilePicker thất bại, dùng cách tải mặc định:", err);
    }
  }
  triggerFileDownload(url);
}

document.getElementById("production-languages").addEventListener("click", async (e) => {
  const btn = e.target.closest(".video-download-btn");
  if (!btn) return;
  const jobId = btn.dataset.job;
  const langCode = btn.dataset.lang;
  const url = `/api/production/${jobId}/video?language_code=${langCode}`;
  const originalText = btn.textContent;
  btn.disabled = true;
  btn.textContent = "Đang tải...";
  try {
    await downloadWithPicker(url, `video_${jobId}_${langCode}_final.mp4`);
  } finally {
    btn.disabled = false;
    btn.textContent = originalText;
  }
});

function stopProductionPolling() {
  clearInterval(productionPollTimer);
  productionPollTimer = null;
  productionPollVersion += 1;
}

function startProductionPolling(jobId) {
  stopProductionPolling();
  productionPollTimer = setInterval(() => pollProductionJob(jobId), 4000);
  pollProductionJob(jobId);
}

function renderProductionLanguages(jobId, job) {
  productionLanguagesEl.innerHTML = Object.values(job.languages)
    .map((lang) => {
      const stageText = LANGUAGE_STAGE_LABELS[lang.status] || lang.status;
      if (lang.status === "done") {
        const m = lang.metadata;
        return `<div class="production-language-card">
          <h4>${lang.language_code} — ✅ Xong</h4>
          ${m && m.titles && m.titles.length ? `<p style="font-weight:700;margin:4px 0">${m.titles[0]}</p><p class="hint" style="margin:0 0 8px">${m.subtitle}</p>` : ""}
          <div style="display:flex;gap:8px;flex-wrap:wrap">
            <a class="btn-secondary" href="/api/production/${jobId}/video?language_code=${lang.language_code}" target="_blank" style="display:inline-block;text-decoration:none;text-align:center">Xem / Tải video</a>
            <button type="button" class="btn-primary video-download-btn" data-job="${jobId}" data-lang="${lang.language_code}">📥 Chọn nơi lưu &amp; tải</button>
          </div>
          ${renderPublishPanel(jobId, lang)}
        </div>`;
      }
      if (lang.status === "failed") {
        return `<div class="production-language-card"><h4>${lang.language_code} — ❌ Lỗi</h4><p class="hint">${lang.error || ""}</p></div>`;
      }
      return `<div class="production-language-card"><h4>${lang.language_code} — ${stageText}</h4></div>`;
    })
    .join("");
}

async function pollProductionJob(jobId) {
  if (jobId !== currentProductionJobId) return;
  const requestVersion = ++productionPollVersion;
  try {
    const res = await fetch(`/api/production/${jobId}`, { cache: "no-store" });
    if (!res.ok) return;
    const job = await res.json();
    if (jobId !== currentProductionJobId || requestVersion !== productionPollVersion) return;
    productionStageText.textContent =
      (STAGE_LABELS[job.status] || job.status) + ` (${job.scenes_done}/${job.scenes_total} cảnh xong)`;
    applyRunModeUi(job.run_mode);
    renderSceneReviewBanner(jobId, job);
    renderQualityWarnings(job);
    renderProductionLanguages(jobId, job);
    renderPreviewPanel(jobId, job);
    renderProductionScenes(job);
    lastProductionStatus = job;
    // Chế độ "Tự động tải về" (mặc định, Bước 10): ngôn ngữ nào VỪA xong là
    // tự tải ngay, không đợi người dùng bấm gì — mỗi (jobId, ngôn ngữ) chỉ
    // tự tải đúng 1 lần (autoDownloadedVideoKeys), vì hàm này chạy lại mỗi
    // 4s cho tới khi CẢ job xong, không riêng từng ngôn ngữ.
    if (currentDownloadMode() === "auto") {
      Object.values(job.languages).forEach((lang) => {
        if (lang.status !== "done") return;
        const key = `${jobId}:${lang.language_code}`;
        if (autoDownloadedVideoKeys.has(key)) return;
        autoDownloadedVideoKeys.add(key);
        triggerFileDownload(`/api/production/${jobId}/video?language_code=${lang.language_code}`);
      });
    }
    // Nút "Dự án trước đó": chỉ lưu snapshot khi tiến độ THẬT SỰ đổi (không phải
    // mỗi 4s polling) — tránh ghi đĩa liên tục vô ích.
    const stageKey = `${job.status}:${job.scenes_done}:${job.scenes_failed}:${Object.values(job.languages).map((l) => l.status).join(",")}`;
    if (stageKey !== lastSavedProductionStageKey) {
      lastSavedProductionStageKey = stageKey;
      saveProjectSnapshot();
    }

    if (job.status === "done" || job.status === "failed") {
      stopProductionPolling();
      if (job.status === "failed" && !Object.values(job.languages).some((l) => l.status === "done")) {
        showNotice("Sản xuất video thất bại: " + (job.error || "lỗi không rõ"), null);
      }
    }
  } catch (error) {
    console.warn("Không cập nhật được trạng thái sản xuất:", error);
  }
}

// Nhiệm vụ 2 (2026-09-15): Bản tổng liệt kê toàn bộ cảnh + prompt AI —
// giống file "Kịch bản N cảnh" người dùng từng tự soạn tay cho phim Quang
// Trung 37 cảnh — hiện TRƯỚC khi bắt đầu sản xuất qua Google Flow, thay vì
// chỉ âm thầm sinh xong rồi chạy thẳng như trước đây. Cache lại theo đúng
// nội dung kịch bản đã dùng để sinh, để "Bắt đầu sản xuất" dùng lại NGUYÊN
// kết quả người dùng vừa xem qua, không gọi lại LLM sinh prompt lần 2 (tốn
// thêm 1 lượt gọi) trừ khi kịch bản đã đổi kể từ lần tạo gần nhất.
let storyboardCache = null; // { scriptText, beatsData, scenesData, promptsData, beatList }

async function generateStoryboard(scriptText) {
  const beatsRes = await fetch("/api/storyboard/beats", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ script_text: scriptText }),
  });
  const beatsData = await beatsRes.json();
  if (!beatsRes.ok) throw new Error(beatsData.detail || "Không chia được đoạn từ kịch bản.");

  const scenesRes = await fetch("/api/storyboard/scenes", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ beats: beatsData.beats }),
  });
  const scenesData = await scenesRes.json();
  if (!scenesRes.ok) throw new Error(scenesData.detail || "Không chia được cảnh từ kịch bản.");

  const promptsRes = await fetch("/api/storyboard/prompts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenes: scenesData.scenes, characters: currentCharactersPayload() }),
  });
  const promptsData = await promptsRes.json();
  if (!promptsRes.ok) throw new Error(promptsData.detail || "Không sinh được prompt cảnh.");

  const beatList = beatsForProduction(beatsData.beats, scenesData.scenes);
  storyboardCache = { scriptText, beatsData, scenesData, promptsData, beatList };
  return storyboardCache;
}

function formatSceneTimestamp(startSec, endSec) {
  const mm = (s) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
  return `${mm(startSec)}-${mm(endSec)}`;
}

function renderStoryboardList(storyboard) {
  const prompts = storyboard.promptsData.prompts;
  document.getElementById("storyboard-scene-count-label").textContent =
    i18n.t("storyboard_scene_count_label").replace("{n}", prompts.length);
  const esc = (s) => (s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;");
  document.getElementById("storyboard-scene-list").innerHTML = prompts
    .map((p) => {
      const icon = ICON_OF_SCENE_TYPE[p.scene_type] || "🎬";
      const label = LABEL_OF_SCENE_TYPE[p.scene_type] || p.scene_type;
      // Prompt tiếng Anh (dán thẳng vào Flow) hiện trước, bản dịch tiếng
      // Việt (CHỈ để đọc hiểu, không gửi đi đâu cả) hiện mờ hơn ngay bên
      // dưới — yêu cầu người dùng 2026-09-15.
      const viLine = p.prompt_vi
        ? `<p class="storyboard-scene-prompt-vi">🇻🇳 ${esc(p.prompt_vi)}</p>`
        : "";
      return `<div class="storyboard-scene-item">
        <div class="storyboard-scene-head">
          <strong>Cảnh ${p.scene_n}</strong>
          <span class="hint">${formatSceneTimestamp(p.start_sec, p.end_sec)}</span>
          <span class="scene-type-badge">${icon} ${label}</span>
        </div>
        <p class="storyboard-scene-prompt">🇬🇧 ${esc(p.prompt)}</p>
        ${viLine}
      </div>`;
    })
    .join("");
  document.getElementById("storyboard-list-wrap").classList.remove("section-hidden");
}

// Lựa chọn 2 của "Cách chạy" (trước mục 1. Ý tưởng): sau khi "Tạo dự án"
// xong, tự chạy tiếp toàn bộ các bước tới "Tạo danh sách cảnh & Prompt" mà
// không cần người dùng bấm từng nút — dùng lại đúng các hàm gọi API mà nút
// thủ công dùng (suggestCharactersRequest, generateHooksRequest,
// writeScriptRequest, seoRequest, generateStoryboard) để không lệch hành vi.
// Bước "Xác định chủ đề & mục tiêu" (Bước 3) KHÔNG có trong yêu cầu tự động
// hoá — bỏ qua có chủ đích, currentTheme() trả về null lúc đó và hooks/kịch
// bản vẫn chạy bình thường không cần chủ đề.
const autoPipelineStatusEl = document.getElementById("auto-pipeline-status");

function setAutoPipelineStatus(text) {
  autoPipelineStatusEl.textContent = text;
  autoPipelineStatusEl.classList.toggle("section-hidden", !text);
}

// Chạy 1 bước của pipeline tự động NHƯNG vẫn khoá + đổi chữ trên đúng cái
// nút thủ công của bước đó (suggest-characters-btn, generate-hooks-btn...)
// — lý do: dòng trạng thái nhỏ ở đầu trang (auto-pipeline-status) bị cuộn
// khuất khỏi màn hình ngay khi trang tự cuộn xuống mục đang làm, khiến
// người dùng tưởng app bị đứng dù vẫn đang chạy ngầm (báo lỗi 2026-09-16).
// Đổi chữ ngay trên nút NGAY TRƯỚC MẶT người dùng thì không thể hiểu lầm.
async function runWithButtonLoading(btn, loadingText, fn) {
  const original = btn.textContent;
  btn.disabled = true;
  btn.textContent = loadingText;
  try {
    return await fn();
  } finally {
    btn.disabled = false;
    btn.textContent = original;
  }
}

// Mờ nhấp nháy tiêu đề mục ĐANG được pipeline tự động xử lý (VD "Viết kịch
// bản" mờ trong lúc runAutoPipeline đang ở bước sinh kịch bản) — dấu hiệu
// ngay tại chỗ, không phải đọc dòng trạng thái nhỏ dễ bị cuộn khuất.
async function runWithHeadingActive(headingEl, fn) {
  headingEl?.classList.add("pipeline-heading-active");
  try {
    return await fn();
  } finally {
    headingEl?.classList.remove("pipeline-heading-active");
  }
}

async function runAutoPipeline(storyText) {
  const characterHeading = document.querySelector("#character-bible-section h2");
  const hooksHeading = document.querySelector("#hooks-section h2");
  const scriptHeading = document.querySelector("#script-section h2");
  const seoHeading = document.getElementById("seo-section-heading");
  const storyboardHeading = document.querySelector("#storyboard-list-section h2");
  try {
    setAutoPipelineStatus(`${i18n.t("auto_pipeline_running")} ${i18n.t("auto_pipeline_step_characters")}`);
    document.getElementById("character-bible-section").scrollIntoView({ behavior: "smooth" });
    const charData = await runWithHeadingActive(characterHeading, () =>
      runWithButtonLoading(
        document.getElementById("suggest-characters-btn"),
        i18n.t("suggest_characters_btn_loading"),
        () => suggestCharactersRequest(storyText)
      )
    );
    state.characters = charData.characters || [];
    renderCharacterList();
    saveProjectSnapshot();

    setAutoPipelineStatus(`${i18n.t("auto_pipeline_running")} ${i18n.t("auto_pipeline_step_hooks")}`);
    document.getElementById("hooks-section").scrollIntoView({ behavior: "smooth" });
    const hooksData = await runWithHeadingActive(hooksHeading, () =>
      runWithButtonLoading(
        document.getElementById("generate-hooks-btn"),
        i18n.t("generate_hooks_btn_loading"),
        () => generateHooksRequest(storyText, currentTheme())
      )
    );
    renderHooks(hooksData);
    document.getElementById("hooks-result").classList.remove("section-hidden");
    saveProjectSnapshot();

    setAutoPipelineStatus(`${i18n.t("auto_pipeline_running")} ${i18n.t("auto_pipeline_step_script")}`);
    document.getElementById("script-section").scrollIntoView({ behavior: "smooth" });
    const scriptData = await runWithHeadingActive(scriptHeading, () =>
      runWithButtonLoading(
        document.getElementById("write-script-btn"),
        i18n.t("write_script_btn_loading"),
        () => writeScriptRequest(currentScriptPayload(storyText))
      )
    );
    applyScriptResult(scriptData);
    setCurrentStep(5);
    const scriptText = (scriptData.script || "").trim();
    saveProjectSnapshot();

    setAutoPipelineStatus(`${i18n.t("auto_pipeline_running")} ${i18n.t("auto_pipeline_step_seo")}`);
    seoHeading?.scrollIntoView({ behavior: "smooth" });
    const seoBtn = document.querySelector('.seo-btn[data-platform="facebook_instagram"]');
    const seoData = await runWithHeadingActive(seoHeading, () =>
      seoBtn
        ? runWithButtonLoading(seoBtn, "Đang soạn...", () => seoRequest(scriptText, "facebook_instagram"))
        : seoRequest(scriptText, "facebook_instagram")
    );
    renderSeoResult("facebook_instagram", seoData);

    setAutoPipelineStatus(`${i18n.t("auto_pipeline_running")} ${i18n.t("auto_pipeline_step_storyboard")}`);
    document.getElementById("storyboard-list-section").scrollIntoView({ behavior: "smooth" });
    const storyboard = await runWithHeadingActive(storyboardHeading, () =>
      runWithButtonLoading(
        document.getElementById("generate-storyboard-btn"),
        i18n.t("generate_storyboard_btn_loading"),
        () => generateStoryboard(scriptText)
      )
    );
    renderStoryboardList(storyboard);
    saveProjectSnapshot();

    setAutoPipelineStatus(i18n.t("auto_pipeline_done"));
    document.getElementById("storyboard-list-section").scrollIntoView({ behavior: "smooth" });
  } catch (e) {
    console.error("runAutoPipeline:", e);
    const message = `${i18n.t("auto_pipeline_failed_prefix")} ${e.message}`;
    setAutoPipelineStatus(message);
    // showNotice = hộp thông báo nổi bật giữa trang — dòng chữ nhỏ ở đầu
    // trang (auto-pipeline-status) rất dễ bị cuộn khuất, còn lỗi thì
    // KHÔNG được phép để người dùng bỏ lỡ.
    showNotice(message, null);
  }
}

document.getElementById("generate-storyboard-btn").addEventListener("click", async () => {
  const scriptText = document.getElementById("script-text").value.trim();
  if (!scriptText) {
    showNotice(i18n.t("notice_story_empty_for_storyboard"), null);
    return;
  }
  const btn = document.getElementById("generate-storyboard-btn");
  btn.disabled = true;
  const originalText = btn.textContent;
  btn.textContent = i18n.t("generate_storyboard_btn_loading");
  try {
    const storyboard = await generateStoryboard(scriptText);
    renderStoryboardList(storyboard);
    document.getElementById("storyboard-list-section").scrollIntoView({ behavior: "smooth" });
    saveProjectSnapshot();
  } catch (e) {
    showNotice(e.message, () => document.getElementById("generate-storyboard-btn").click());
  } finally {
    btn.disabled = false;
    btn.textContent = originalText;
  }
});

document.getElementById("start-production-btn").addEventListener("click", async () => {
  const scriptText = document.getElementById("script-text").value.trim();
  if (!scriptText) {
    showNotice("Chưa có kịch bản để sản xuất video.", null);
    return;
  }
  const btn = document.getElementById("start-production-btn");
  btn.disabled = true;
  try {
    let storyboard;
    try {
      // Dùng lại đúng danh sách cảnh người dùng vừa xem qua ở khối "Danh
      // sách toàn bộ cảnh" phía trên, nếu kịch bản chưa đổi kể từ lúc đó —
      // chỉ tự sinh lại (fallback) khi người dùng bỏ qua bước xem trước đó.
      storyboard = storyboardCache && storyboardCache.scriptText === scriptText
        ? storyboardCache
        : await generateStoryboard(scriptText);
    } catch (e) {
      showNotice(e.message, null);
      return;
    }
    renderStoryboardList(storyboard);

    const { promptsData, beatList } = storyboard;
    // Kịch bản đang viết bằng ngôn ngữ ĐẦU TIÊN đã chọn ở Bước 1 (xem
    // write-script-btn). Mọi ngôn ngữ khác trong danh sách đã chọn sẽ được
    // TỰ ĐỘNG DỊCH — cảnh Flow chỉ tạo 1 lần dùng chung cho tất cả (Bước 3).
    const allLangCodes = Array.from(state.selectedLanguages);
    const sourceLangCode = allLangCodes[0] || "vi-VN";
    // Bước 10: người dùng có thể chỉ chọn xuất 1 ngôn ngữ ngay bây giờ —
    // `language_codes` gửi lên chỉ gồm ngôn ngữ(các) thực sự muốn dựng
    // trong job NÀY (xem currentExportLanguageCodes()).
    const exportLangCodes = currentExportLanguageCodes();

    const startRes = await fetch("/api/production/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        scenes: promptsData.prompts.map((p) => ({
          scene_n: p.scene_n, prompt: p.prompt, scene_type: p.scene_type,
          chart_data: p.chart_data, duration_sec: p.end_sec - p.start_sec,
          source_text: p.source_text,
        })),
        // Mục 8 (phát hiện nhân vật đổi hình dạng) — Sổ Tay Nhân Vật (Bước 1)
        // người dùng nhập ở đầu trang; rỗng thì backend tự bỏ qua kiểm tra này.
        characters: currentCharactersPayload(),
        beats: beatList.map((b) => ({ label: b.label, narration_text: b.narration_text, scene_ns: b.scene_ns })),
        source_language_code: sourceLangCode,
        language_codes: exportLangCodes,
        format: state.format,
        // Nút "Dự án trước đó": mỗi dự án dựng video vào thư mục projects/<projectId>/
        // RIÊNG (thay vì luôn dùng chung "default" như trước) — không thì dự
        // án sau sẽ ghi đè video dự án trước đó (xem app/api/production.py).
        project_id: state.projectId || "default",
        run_mode: currentRunMode(),
        narration_volume: Number(narrationVolumeSlider.value),
        sfx_volume_db: Number(sfxVolumeSlider.value),
        include_poster: document.querySelector('input[name="poster-choice"]:checked')?.value !== "no",
      }),
    });
    const startData = await startRes.json();
    if (!startRes.ok) {
      showNotice(startData.detail || "Không khởi động được job sản xuất video.", null);
      return;
    }

    currentProductionJobId = startData.job_id;
    const productionUrl = new URL(window.location.href);
    productionUrl.searchParams.set("production_job", startData.job_id);
    window.history.replaceState(null, "", productionUrl);
    setCurrentStep(6);
    step6Section.scrollIntoView({ behavior: "smooth" });
    startProductionPolling(startData.job_id);
    saveProjectSnapshot();
  } finally {
    btn.disabled = false;
  }
});

// Bấm ⊞ ở thanh trên = thu gọn 2 thanh menu thành 1 (giống Adobe Express).
// Bấm ⊞ ở thanh dưới (hiện ra sau khi thu gọn) = mở lại đủ 2 thanh.
const appswitcherBar = document.getElementById("appswitcher-bar");
const toggleExpandedBtn = document.getElementById("toggle-expanded-btn");
const toggleCollapsedBtn = document.getElementById("toggle-collapsed-btn");

function setTopbarExpanded(expanded) {
  appswitcherBar.style.display = expanded ? "flex" : "none";
  toggleExpandedBtn.style.display = expanded ? "flex" : "none";
  toggleCollapsedBtn.style.display = expanded ? "none" : "flex";
}
toggleExpandedBtn.addEventListener("click", () => setTopbarExpanded(false));
toggleCollapsedBtn.addEventListener("click", () => setTopbarExpanded(true));

document.querySelectorAll(".sidebar-item[href]").forEach((link) => {
  link.addEventListener("click", (e) => {
    e.preventDefault();
    document.querySelector(link.getAttribute("href")).scrollIntoView({ behavior: "smooth" });
  });
});

// Nút "+" trong sidebar = làm dự án mới: dọn sạch mọi ô đã gõ, quay lại Bước 1.
// Không đụng tới API key đã lưu — key là cài đặt của máy, không phải của 1 dự án.
document.getElementById("sidebar-new-btn").addEventListener("click", () => {
  // Nút "Dự án trước đó": dự án cũ đã lưu xong (autosave) — "+ " chỉ dọn sạch
  // MÀN HÌNH, không được tiếp tục tự lưu đè lên snapshot của dự án đó bằng
  // các ô vừa xoá trắng, nên phải bỏ projectId ngay tại đây.
  state.projectId = null;
  document.getElementById("idea").value = "";
  document.getElementById("story-text").value = "";
  document.getElementById("script-text").value = "";
  // Bước 4-10 giờ LUÔN hiện sẵn trên trang (2026-09-14) — dự án mới chỉ
  // cần dọn sạch nội dung đã gõ, KHÔNG ẩn các khối/nút đi nữa.
  currentProductionJobId = null;
  const productionUrl = new URL(window.location.href);
  productionUrl.searchParams.delete("production_job");
  window.history.replaceState(null, "", productionUrl);
  stopProductionPolling();
  sceneReviewBanner.classList.add("section-hidden");
  delete sceneReviewBanner.dataset.jobId;
  delete approveSceneBtn.dataset.sceneN;
  closeSceneRestoreBanner();
  closeSceneFailedBanner();
  resetPreviewPanel();
  hideFieldWarning("idea-warning");
  hideFieldWarning("lang-warning");
  hideNotice();
  setCurrentStep(1);
  document.getElementById("top").scrollIntoView({ behavior: "smooth" });
});

// --- Nhóm icon bên phải thanh menu (giống Adobe: tìm kiếm/trial/feedback/help/thông báo/avatar) ---
// Mỗi nút map sang đúng 1 việc THẬT app này làm được — không có nút bấm vào mà không xảy ra gì.

// Tìm kiếm: gõ tên 1 bước (VD "kịch bản"), Enter để cuộn thẳng tới đúng thẻ đó.
const searchInput = document.getElementById("search-input");
const stepSectionByKeyword = [
  { keywords: ["ý tưởng", "cau chuyen goc", "y tuong"], id: "idea" },
  { keywords: ["định dạng", "dinh dang"], id: "long-durations" },
  { keywords: ["ngôn ngữ", "ngon ngu"], id: "lang-grid" },
  { keywords: ["câu chuyện", "cau chuyen", "story"], id: "story-section" },
  { keywords: ["kịch bản", "kich ban", "script"], id: "script-section" },
];
document.getElementById("search-btn").addEventListener("click", () => {
  const isOpen = searchInput.classList.toggle("open");
  if (isOpen) searchInput.focus();
});
searchInput.addEventListener("keydown", (e) => {
  if (e.key !== "Enter") return;
  const q = searchInput.value.trim().toLowerCase();
  const match = stepSectionByKeyword.find((s) => s.keywords.some((k) => q.includes(k)));
  const target = match && document.getElementById(match.id);
  if (target && target.offsetParent !== null) {
    target.scrollIntoView({ behavior: "smooth", block: "center" });
  } else {
    showNotice(i18n.t("notice_search_not_found"), null);
  }
});

// "Chạy thử nhanh": điền sẵn ví dụ có thật (đúng placeholder app đã gợi ý), để người
// mới xem ngay app trông thế nào — KHÔNG tự bấm Tạo dự án giúp, vì bước đó tốn API
// key thật của người dùng, phải để chính người dùng bấm mới đúng.
document.getElementById("trial-btn").addEventListener("click", () => {
  const ideaInput = document.getElementById("idea");
  if (!ideaInput.value.trim()) {
    ideaInput.value = "Kể lại truyền thuyết Thánh Gióng theo phong cách sử thi điện ảnh, nhân vật chính là một cậu bé làng Gióng lớn nhanh như thổi để đánh giặc Ân.";
  }
  document.getElementById("top").scrollIntoView({ behavior: "smooth" });
  ideaInput.focus();
});

// Feedback: xổ xuống 1 panel nhỏ (giống Adobe Express) cho chọn đúng loại góp ý,
// mỗi lựa chọn mở thẳng đúng trang Issues thật trên GitHub của repo này (có sẵn
// nhãn bug/enhancement) — không phải form giả, bấm xong panel tự đóng lại.
const feedbackPanel = document.getElementById("feedback-panel");

// Help / Feedback / Notifications / Ngôn ngữ / Hồ sơ: các panel nhỏ xổ xuống, đóng lẫn nhau khi mở cái kia.
const helpPanel = document.getElementById("help-panel");
const notifPanel = document.getElementById("notif-panel");
const langPanel = document.getElementById("lang-panel");
const profilePanel = document.getElementById("profile-panel");
const allPanels = [helpPanel, feedbackPanel, notifPanel, langPanel, profilePanel];
function togglePanel(panel) {
  const willOpen = !panel.classList.contains("open");
  allPanels.forEach((p) => p.classList.remove("open"));
  if (willOpen) panel.classList.add("open");
}
document.getElementById("help-btn").addEventListener("click", () => togglePanel(helpPanel));
document.getElementById("feedback-btn").addEventListener("click", () => togglePanel(feedbackPanel));
document.querySelectorAll("#feedback-panel .feedback-option").forEach((el) => {
  el.addEventListener("click", () => togglePanel(feedbackPanel));
});
document.getElementById("notif-btn").addEventListener("click", () => togglePanel(notifPanel));
document.addEventListener("click", (e) => {
  if (!e.target.closest(".topbar-actions") && !e.target.closest(".topbar-panel")) {
    allPanels.forEach((p) => p.classList.remove("open"));
  }
});

// Đổi ngôn ngữ giao diện (🌐) — khác với ngôn ngữ giọng đọc video ở Bước 3.
// Chỉ những ngôn ngữ có bản dịch thật (ready:true trong i18n.js) mới bấm được;
// còn lại hiện đủ tên nhưng khoá lại + ghi "sắp có" — không giả vờ đã dịch xong.
const langOptionList = document.getElementById("lang-option-list");
function renderLangOptionList() {
  langOptionList.innerHTML = "";
  i18n.languages.forEach((lang) => {
    const opt = document.createElement("div");
    opt.className = "lang-option" + (lang.code === i18n.current ? " current" : "") + (lang.ready ? "" : " disabled");
    opt.textContent = lang.ready ? lang.name : `${lang.name} (${i18n.t("lang_coming_soon")})`;
    if (lang.ready) {
      opt.addEventListener("click", () => {
        i18n.apply(lang.code);
        loadKeyStatus();
        renderLangOptionList();
        togglePanel(langPanel);
      });
    }
    langOptionList.appendChild(opt);
  });
}
document.getElementById("lang-switch-btn").addEventListener("click", () => {
  renderLangOptionList();
  togglePanel(langPanel);
});

// Avatar: mở panel "Hồ sơ của tôi" — ảnh + tên + email lưu ngay trên máy này
// (localStorage của trình duyệt, không gửi lên đâu cả), kèm nút mời theo dõi
// Fanpage thật của founder.
const avatarFileInput = document.getElementById("avatar-file-input");
const profileAvatarBtn = document.getElementById("profile-avatar-btn");
const topbarAvatarBtn = document.getElementById("avatar-btn");
const profileNameInput = document.getElementById("profile-name-input");
const profileEmailInput = document.getElementById("profile-email-input");
const feedbackEmailInput = document.getElementById("feedback-email-input");

function setAvatarPhoto(dataUrl) {
  [profileAvatarBtn, topbarAvatarBtn].forEach((btn) => {
    if (dataUrl) {
      btn.style.backgroundImage = `url(${dataUrl})`;
      btn.textContent = "";
    } else {
      btn.style.backgroundImage = "";
      btn.textContent = "👤";
    }
  });
}

const heroGreeting = document.getElementById("hero-greeting");

// Câu chào đổi theo giờ CỦA MÁY đang mở app (new Date().getHours() luôn lấy
// giờ địa phương của máy, không phải giờ máy chủ) — 5-11h Sáng, 12-17h Chiều,
// còn lại (18h-4h sáng hôm sau) tính là buổi Tối.
function updateGreeting() {
  const hour = new Date().getHours();
  const key = hour >= 5 && hour < 12 ? "greeting_morning" : hour >= 12 && hour < 18 ? "greeting_afternoon" : "greeting_night";
  const name = localStorage.getItem("profile_name");
  heroGreeting.textContent = name ? `${i18n.t(key)}, ${name}` : `${i18n.t(key)}!`;
}

function loadProfile() {
  profileNameInput.value = localStorage.getItem("profile_name") || "";
  profileEmailInput.value = localStorage.getItem("profile_email") || "";
  feedbackEmailInput.value = localStorage.getItem("profile_email") || "";
  setAvatarPhoto(localStorage.getItem("profile_avatar") || "");
  updateGreeting();
}

document.getElementById("avatar-btn").addEventListener("click", () => togglePanel(profilePanel));
profileAvatarBtn.addEventListener("click", () => avatarFileInput.click());

avatarFileInput.addEventListener("change", () => {
  const file = avatarFileInput.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    const img = new Image();
    img.onload = () => {
      // Thu nhỏ ảnh về tối đa 160x160 trước khi lưu — ảnh gốc từ điện thoại/máy
      // ảnh có thể rất nặng, localStorage chỉ chứa được vài MB cho cả trang.
      const size = 160;
      const canvas = document.createElement("canvas");
      canvas.width = size;
      canvas.height = size;
      const ctx = canvas.getContext("2d");
      const scale = Math.max(size / img.width, size / img.height);
      const w = img.width * scale;
      const h = img.height * scale;
      ctx.drawImage(img, (size - w) / 2, (size - h) / 2, w, h);
      const dataUrl = canvas.toDataURL("image/jpeg", 0.85);
      localStorage.setItem("profile_avatar", dataUrl);
      setAvatarPhoto(dataUrl);
    };
    img.src = reader.result;
  };
  reader.readAsDataURL(file);
});

profileNameInput.addEventListener("input", () => {
  localStorage.setItem("profile_name", profileNameInput.value);
  updateGreeting();
});
profileEmailInput.addEventListener("input", () => {
  localStorage.setItem("profile_email", profileEmailInput.value);
  feedbackEmailInput.value = profileEmailInput.value;
});
// Email trong panel Feedback dùng chung 1 nguồn với email trong Hồ sơ (profile_email)
// — gõ ở đâu cũng lưu chung, không phải 2 ô tách biệt gây lẫn lộn.
feedbackEmailInput.addEventListener("input", () => {
  localStorage.setItem("profile_email", feedbackEmailInput.value);
  profileEmailInput.value = feedbackEmailInput.value;
});
document.addEventListener("i18n-changed", updateGreeting);

// Bước 1, đính kèm câu chuyện gốc từ file (Word/PDF/văn bản thuần) hoặc
// link 1 bài viết — thay cho việc chỉ dán/gõ tay vào ô "Ý tưởng". Kết quả
// (đã qua LLM xử lý theo đúng chế độ chọn) được điền thẳng vào ô Ý tưởng,
// người dùng tự xem/sửa tiếp trước khi bấm "Tạo dự án" như bình thường.
// CHƯA hỗ trợ link video (mp4) — xem app/services/story_import.py.
const attachModal = document.getElementById("attach-modal");
const attachBtn = document.getElementById("attach-btn");
const attachModalClose = document.getElementById("attach-modal-close");
const attachFileInput = document.getElementById("attach-file-input");
const attachFileChooseBtn = document.getElementById("attach-file-choose-btn");
const attachFileChosenName = document.getElementById("attach-file-chosen-name");
attachFileChooseBtn.addEventListener("click", () => attachFileInput.click());
attachFileInput.addEventListener("change", () => {
  attachFileChosenName.textContent = attachFileInput.files[0]?.name || "";
});
const attachUrlInput = document.getElementById("attach-url-input");
const attachSourceFile = document.getElementById("attach-source-file");
const attachSourceUrl = document.getElementById("attach-source-url");
const attachWarning = document.getElementById("attach-warning");
const attachSubmitBtn = document.getElementById("attach-submit-btn");
let attachSource = "file";

function openAttachModal() {
  attachModal.classList.remove("section-hidden");
  attachWarning.classList.add("section-hidden");
}
function closeAttachModal() {
  attachModal.classList.add("section-hidden");
}
attachBtn.addEventListener("click", openAttachModal);

// Cài đặt đăng bài mạng xã hội (2026-09-14): gỡ khỏi luồng chính, chuyển
// vào modal mở từ nút riêng dưới "Cài đặt" ở sidebar — nội dung/logic bên
// trong #publishing-settings-list KHÔNG đổi (vẫn nạp qua loadPublishingSettings()).
const publishingModal = document.getElementById("publishing-modal");
const publishingModalClose = document.getElementById("publishing-modal-close");
const sidebarPublishingBtn = document.getElementById("sidebar-publishing-btn");
sidebarPublishingBtn.addEventListener("click", () => {
  // Bấm lại đúng nút này lần nữa = đóng luôn (toggle), không bắt phải bấm
  // đúng nút ✕ mới đóng được.
  const nowHidden = publishingModal.classList.toggle("section-hidden");
  sidebarPublishingBtn.classList.toggle("active", !nowHidden);
});
publishingModalClose.addEventListener("click", () => {
  publishingModal.classList.add("section-hidden");
  sidebarPublishingBtn.classList.remove("active");
});
publishingModal.addEventListener("click", (e) => {
  if (e.target === publishingModal) {
    publishingModal.classList.add("section-hidden");
    sidebarPublishingBtn.classList.remove("active");
  }
});
attachModalClose.addEventListener("click", closeAttachModal);
attachModal.addEventListener("click", (e) => {
  if (e.target === attachModal) closeAttachModal(); // bấm ra ngoài hộp thoại để đóng
});

document.querySelectorAll(".attach-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    attachSource = tab.dataset.source;
    document.querySelectorAll(".attach-tab").forEach((t) => t.classList.toggle("selected", t === tab));
    attachSourceFile.classList.toggle("section-hidden", attachSource !== "file");
    attachSourceUrl.classList.toggle("section-hidden", attachSource !== "url");
  });
});

const attachCustomInstructionWrap = document.getElementById("attach-custom-instruction-wrap");
const attachCustomInstruction = document.getElementById("attach-custom-instruction");
document.querySelectorAll('input[name="attach-mode"]').forEach((radio) => {
  radio.addEventListener("change", () => {
    document.querySelectorAll("#attach-mode-choice .format-choice").forEach((el) => {
      el.classList.toggle("selected", el.dataset.mode === radio.value);
    });
    attachCustomInstructionWrap.classList.toggle("section-hidden", radio.value !== "custom");
  });
});

function showAttachWarning(text) {
  attachWarning.textContent = text;
  attachWarning.classList.remove("section-hidden");
}

attachSubmitBtn.addEventListener("click", async () => {
  const mode = document.querySelector('input[name="attach-mode"]:checked')?.value || "follow";
  const customInstruction = attachCustomInstruction.value.trim();
  attachWarning.classList.add("section-hidden");

  if (mode === "custom" && !customInstruction) {
    showAttachWarning(i18n.t("attach_no_instruction_warning"));
    return;
  }

  let res;
  attachSubmitBtn.disabled = true;
  const originalLabel = attachSubmitBtn.textContent;
  attachSubmitBtn.textContent = i18n.t("attach_processing");
  try {
    if (attachSource === "file") {
      const file = attachFileInput.files[0];
      if (!file) {
        showAttachWarning(i18n.t("attach_no_source_warning"));
        return;
      }
      const formData = new FormData();
      formData.append("mode", mode);
      if (mode === "custom") formData.append("custom_instruction", customInstruction);
      formData.append("file", file);
      res = await fetch("/api/story/import-file", { method: "POST", body: formData });
    } else {
      const url = attachUrlInput.value.trim();
      if (!url) {
        showAttachWarning(i18n.t("attach_no_source_warning"));
        return;
      }
      const isVideo = url.includes("tiktok.com") || url.includes("youtube.com") || url.includes("youtu.be");
      const endpoint = isVideo ? "/api/story/import-video-url" : "/api/story/import-url";
      res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, mode, custom_instruction: mode === "custom" ? customInstruction : null }),
      });
    }
    const data = await res.json();
    if (!res.ok) {
      showAttachWarning(data.detail || "Lỗi không rõ.");
      return;
    }
    document.getElementById("idea").value = data.story;
    closeAttachModal();
    showNotice(i18n.t("attach_success_notice"), null);
  } finally {
    attachSubmitBtn.disabled = false;
    attachSubmitBtn.textContent = originalLabel;
  }
});

// Nút phóng to/thu nhỏ cho 3 ô: Ý tưởng / Câu chuyện đầy đủ / Kịch bản đầy
// đủ — kiểu nút maximize cửa sổ Windows. Kích thước lúc phóng to tính
// hoàn toàn bằng CSS (.expandable-wrap textarea.maximized trong style.css),
// JS ở đây chỉ lo toggle class + đổi icon + đóng khi bấm ra ngoài/Esc.
const maximizeBackdrop = document.getElementById("textarea-maximize-backdrop");
let currentMaximizedTextarea = null;

function restoreMaximizedTextarea() {
  if (!currentMaximizedTextarea) return;
  currentMaximizedTextarea.classList.remove("maximized");
  const btn = document.querySelector(`.expand-toggle-btn[data-target="${currentMaximizedTextarea.id}"]`);
  if (btn) {
    btn.textContent = "⛶";
    btn.title = i18n.t("expand_btn_title");
    btn.classList.remove("floating");
  }
  maximizeBackdrop.classList.remove("open");
  currentMaximizedTextarea = null;
}

document.querySelectorAll(".expand-toggle-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const target = document.getElementById(btn.dataset.target);
    if (!target) return;
    if (currentMaximizedTextarea === target) {
      restoreMaximizedTextarea();
      return;
    }
    restoreMaximizedTextarea(); // chỉ 1 ô được phóng to cùng lúc
    target.classList.add("maximized");
    target.focus();
    btn.textContent = "🗗";
    btn.title = i18n.t("restore_btn_title");
    btn.classList.add("floating");
    maximizeBackdrop.classList.add("open");
    currentMaximizedTextarea = target;
  });
});
maximizeBackdrop.addEventListener("click", restoreMaximizedTextarea);
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && currentMaximizedTextarea) restoreMaximizedTextarea();
});

// Lỗi thật đã gặp (2026-09-14): 3 ô Ý tưởng/Câu chuyện/Kịch bản khi chứa
// NHIỀU chữ (VD dán cả 1 truyện dài) tự có thanh cuộn riêng bên trong —
// cuộn chuột hết nội dung của ô đó thì KHÔNG tự "chain" sang cuộn trang
// ngoài (.page-scroll) như mong đợi, làm người dùng tưởng bị KẸT không
// cuộn xuống được các nút "Tạo dự án"/"Viết kịch bản" phía dưới nữa. Tự
// chuyển tiếp phần cuộn còn dư ra ngoài khi textarea đã cuộn hết cỡ.
document.querySelectorAll(".page-scroll textarea").forEach((ta) => {
  ta.addEventListener(
    "wheel",
    (e) => {
      const atTop = ta.scrollTop <= 0;
      const atBottom = Math.ceil(ta.scrollTop + ta.clientHeight) >= ta.scrollHeight;
      if ((e.deltaY < 0 && atTop) || (e.deltaY > 0 && atBottom)) {
        e.preventDefault();
        document.querySelector(".page-scroll").scrollTop += e.deltaY;
      }
    },
    { passive: false }
  );
});

// Nút "Dự án trước đó" (sidebar, giữa Cài đặt và Đăng bài): lưu lại TOÀN BỘ
// hiện trạng dự án (mọi ô đã gõ + danh sách cảnh/prompt + tiến độ sản xuất)
// ra server (app/api/projects_registry.py), tối đa 8 dự án gần nhất — bấm
// vào 1 dự án trong danh sách xổ xuống là mở lại ĐÚNG như lúc rời đi, kể cả
// sau khi server đã khởi động lại (khi đó _JOBS trong bộ nhớ đã mất, xem
// production_pipeline.py — job không còn "sống" nữa thì chỉ hiển thị lại
// tiến độ đã lưu, không thao tác tiếp được, xem renderReadOnlyProductionFallback).
function computeProjectTitle() {
  const source = (document.getElementById("story-text").value || document.getElementById("idea").value || "").trim();
  if (!source) return "Dự án chưa đặt tên";
  const oneLine = source.replace(/\s+/g, " ");
  return oneLine.length > 60 ? oneLine.slice(0, 60) + "…" : oneLine;
}

const STEP_WORD_BY_LANG = { vi: "Bước", en: "Step", ru: "Шаг" };
function computeProjectStageLabel() {
  if (currentProductionJobId && lastProductionStatus) {
    const job = lastProductionStatus;
    if (job.status === "done") return "✅ Đã sản xuất xong";
    return `Đang sản xuất — ${job.scenes_done}/${job.scenes_total} cảnh xong`;
  }
  const word = STEP_WORD_BY_LANG[i18n.current] || STEP_WORD_BY_LANG.vi;
  return `${word} ${currentStepNumber} — ${i18n.t("step_" + currentStepNumber)}`;
}

function collectProjectState() {
  return {
    step: currentStepNumber,
    idea: document.getElementById("idea").value,
    story: document.getElementById("story-text").value,
    script: document.getElementById("script-text").value,
    format: state.format,
    duration_minutes: state.duration_minutes,
    duration_seconds: state.duration_seconds,
    selectedLanguages: Array.from(state.selectedLanguages),
    characters: state.characters,
    characterMax: state.characterMax,
    pipelineMode: state.pipelineMode,
    theme: currentTheme(),
    themeVisible: !document.getElementById("theme-result").classList.contains("section-hidden"),
    hooksData: lastHooksData,
    chosenHookText: document.getElementById("chosen-hook-text").value,
    narrationVolume: narrationVolumeSlider.value,
    sfxVolumeDb: sfxVolumeSlider.value,
    posterChoice: document.querySelector('input[name="poster-choice"]:checked')?.value || "yes",
    runMode: currentRunMode(),
    exportMode: document.querySelector('input[name="export-mode"]:checked')?.value || "all",
    exportSingleLangCode: exportSingleLangSelect.value || null,
    downloadMode: currentDownloadMode(),
    storyboardCache: storyboardCache,
    productionJobId: currentProductionJobId,
    productionStatus: lastProductionStatus,
  };
}

let saveSnapshotTimer = null;

async function saveProjectSnapshot() {
  if (!state.projectId) return; // chưa "Tạo dự án" lần nào, chưa có gì để lưu
  const payload = {
    title: computeProjectTitle(),
    stage_label: computeProjectStageLabel(),
    data: collectProjectState(),
  };
  try {
    await fetch(`/api/projects/${state.projectId}/snapshot`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (e) {
    console.warn("Không lưu được snapshot dự án:", e);
  }
}

function scheduleSaveProjectSnapshot() {
  if (!state.projectId) return;
  clearTimeout(saveSnapshotTimer);
  saveSnapshotTimer = setTimeout(saveProjectSnapshot, 1500);
}

// Gõ tay vào 3 ô lớn (Ý tưởng/Câu chuyện/Kịch bản) + ô hook đã chọn cũng phải
// tự lưu (debounce 1.5s) — không đợi tới lúc bấm nút mới lưu, vì người dùng
// có thể tự sửa tay rất nhiều rồi đóng app mà không bấm nút nào tiếp theo.
["idea", "story-text", "script-text", "chosen-hook-text"].forEach((id) => {
  document.getElementById(id).addEventListener("input", scheduleSaveProjectSnapshot);
});

// Bấm ⊞ trong khung "Xem trước" hoặc nút thao tác cảnh (duyệt/tạo lại/bỏ
// qua/khôi phục) đều đã tự gọi pollProductionJob() -> tự lưu khi tiến độ đổi
// (xem pollProductionJob), không cần thêm gì ở đây.

// Sau khi server khởi động lại, job cũ đã mất khỏi _JOBS (production_pipeline.py)
// — không còn thao tác được (duyệt/tạo lại/bỏ qua cảnh...) nữa, chỉ còn xem lại
// ĐÚNG tiến độ đã lưu lần cuối, và tự tìm video đã dựng xong (nếu có) thẳng từ
// đĩa qua /api/projects/{id}/production-files — KHÔNG phụ thuộc job có sống hay
// không (xem app/api/projects_registry.py).
async function renderReadOnlyProductionFallback(job) {
  renderProductionScenes(job);
  renderQualityWarnings(job);
  sceneRowBoxes.querySelectorAll("button").forEach((b) => { b.disabled = true; });
  sceneReviewBanner.classList.add("section-hidden");
  closeSceneRestoreBanner();
  closeSceneFailedBanner();
  productionStageText.textContent =
    `${STAGE_LABELS[job.status] || job.status} (${job.scenes_done}/${job.scenes_total} cảnh xong) — ${i18n.t("recent_project_server_restarted_hint")}`;
  previewVideoEl.classList.add("section-hidden");
  previewEmptyHint.classList.remove("section-hidden");
  document.querySelectorAll(".preview-tab").forEach((btn) => { btn.disabled = true; });

  try {
    const res = await fetch(`/api/projects/${state.projectId}/production-files`);
    const filesData = await res.json();
    const files = filesData.files || [];
    productionLanguagesEl.innerHTML = files.length
      ? files
          .map(
            (f) => `<div class="production-language-card">
        <h4>${f.language_code} — ✅ Xong</h4>
        <a class="btn-primary" href="/api/projects/${state.projectId}/production-files/${f.language_code}/download" target="_blank" style="display:inline-block;text-decoration:none;text-align:center">Xem / Tải video</a>
      </div>`
          )
          .join("")
      : "";
  } catch {
    /* im lặng — không chặn phần còn lại của trang chỉ vì danh sách file lỗi */
  }
}

// Nạp lại 1 dự án đã lưu — điền lại từng ô, phát lại kết quả đã lưu qua ĐÚNG
// các hàm render() thật đang dùng ở luồng bình thường (không tự dựng lại HTML
// ở chỗ khác), rồi nhảy tới đúng bước xa nhất đã làm.
async function restoreProjectFromSnapshot(snapshot) {
  const data = snapshot.data || {};
  state.projectId = snapshot.project_id;

  document.getElementById("idea").value = data.idea || "";
  document.getElementById("story-text").value = data.story || "";
  document.getElementById("script-text").value = data.script || "";

  if (data.format) {
    state.format = data.format;
    document.querySelectorAll(".format-grid .format-choice").forEach((el) => {
      el.classList.toggle("selected", el.dataset.format === data.format);
    });
    longDurations.style.display = data.format === "long" ? "flex" : "none";
    shortDurations.style.display = data.format === "short" ? "flex" : "none";
    longDurationSlider.style.display = data.format === "long" ? "flex" : "none";
    shortDurationSlider.style.display = data.format === "short" ? "flex" : "none";
  }
  if (typeof data.duration_minutes === "number") {
    state.duration_minutes = data.duration_minutes;
    longDurationSlider.sliderApi.setValue(data.duration_minutes);
    longDurations.querySelectorAll(".pill").forEach((el) => {
      el.classList.toggle("selected", Number(el.dataset.duration) === data.duration_minutes);
    });
  }
  if (typeof data.duration_seconds === "number") {
    state.duration_seconds = data.duration_seconds;
    shortDurationSlider.sliderApi.setValue(data.duration_seconds);
    shortDurations.querySelectorAll(".pill").forEach((el) => {
      el.classList.toggle("selected", Number(el.dataset.duration) === data.duration_seconds);
    });
  }

  if (Array.isArray(data.selectedLanguages)) {
    state.selectedLanguages = new Set(data.selectedLanguages);
    langGrid.querySelectorAll(".pill").forEach((pill) => {
      pill.classList.toggle("selected", state.selectedLanguages.has(pill.dataset.code));
    });
    revealProductionConfigSteps();
  }

  state.characters = Array.isArray(data.characters) ? data.characters : [];
  renderCharacterList();
  if (typeof data.characterMax === "number") {
    state.characterMax = data.characterMax;
    characterMaxLowApi.setValue(data.characterMax <= 10 ? data.characterMax : 10, { silent: true });
    characterMaxHighApi.setValue(data.characterMax > 10 ? data.characterMax : 11, { silent: true });
    characterMaxLowRow.classList.toggle("inactive", data.characterMax > 10);
    characterMaxHighRow.classList.toggle("inactive", data.characterMax <= 10);
  }

  if (data.pipelineMode) {
    state.pipelineMode = data.pipelineMode;
    document.querySelectorAll('#pipeline-mode-choice input[name="pipeline-mode"]').forEach((r) => {
      r.checked = r.value === data.pipelineMode;
    });
    document.querySelectorAll("#pipeline-mode-choice .format-choice").forEach((el) => {
      el.classList.toggle("selected", el.dataset.mode === data.pipelineMode);
    });
  }

  if (data.theme) {
    document.getElementById("theme-audience").value = data.theme.target_audience || "";
    document.getElementById("theme-pain-point").value = data.theme.audience_pain_point || "";
    document.getElementById("theme-core-message").value = data.theme.core_message || "";
    document.getElementById("theme-best-angle").value = data.theme.best_angle || "";
  }
  document.getElementById("theme-result").classList.toggle("section-hidden", !data.themeVisible);

  if (data.hooksData) {
    renderHooks(data.hooksData);
    document.getElementById("hooks-result").classList.remove("section-hidden");
  }
  if (data.chosenHookText != null) {
    document.getElementById("chosen-hook-text").value = data.chosenHookText;
    document.querySelectorAll("#hooks-result .hook-pick").forEach((el) => {
      el.classList.toggle("selected", el.dataset.hookText === data.chosenHookText);
    });
  }

  if (typeof data.narrationVolume !== "undefined") {
    narrationVolumeSlider.value = data.narrationVolume;
    narrationVolumeValue.textContent = `${Number(data.narrationVolume).toFixed(1)}×`;
  }
  if (typeof data.sfxVolumeDb !== "undefined") {
    sfxVolumeSlider.value = data.sfxVolumeDb;
    const v = Number(data.sfxVolumeDb);
    sfxVolumeValue.textContent = `${v >= 0 ? "+" : ""}${v.toFixed(1)} dB`;
  }
  if (data.posterChoice) {
    document.querySelectorAll('input[name="poster-choice"]').forEach((r) => { r.checked = r.value === data.posterChoice; });
    document.querySelectorAll("#poster-choice .format-choice").forEach((el) => {
      el.classList.toggle("selected", el.dataset.poster === data.posterChoice);
    });
  }
  if (data.runMode) applyRunModeUi(data.runMode);
  if (data.exportMode) {
    document.querySelectorAll('input[name="export-mode"]').forEach((r) => { r.checked = r.value === data.exportMode; });
    document.querySelectorAll("#export-mode-choice .format-choice").forEach((el) => {
      el.classList.toggle("selected", el.dataset.export === data.exportMode);
    });
    exportSingleLangSelect.classList.toggle("section-hidden", data.exportMode !== "single");
  }
  if (data.exportSingleLangCode) exportSingleLangSelect.value = data.exportSingleLangCode;
  if (data.downloadMode) {
    document.querySelectorAll('input[name="download-mode"]').forEach((r) => { r.checked = r.value === data.downloadMode; });
    document.querySelectorAll("#download-mode-choice .format-choice").forEach((el) => {
      el.classList.toggle("selected", el.dataset.download === data.downloadMode);
    });
  }

  storyboardCache = data.storyboardCache || null;
  if (storyboardCache && storyboardCache.promptsData) {
    renderStoryboardList(storyboardCache);
  }

  currentProductionJobId = data.productionJobId || null;
  lastProductionStatus = data.productionStatus || null;
  const productionUrl = new URL(window.location.href);
  if (currentProductionJobId) productionUrl.searchParams.set("production_job", currentProductionJobId);
  else productionUrl.searchParams.delete("production_job");
  window.history.replaceState(null, "", productionUrl);

  if (currentProductionJobId) {
    let isLive = false;
    try {
      const res = await fetch(`/api/production/${currentProductionJobId}`, { cache: "no-store" });
      isLive = res.ok;
    } catch {
      isLive = false;
    }
    if (isLive) {
      startProductionPolling(currentProductionJobId);
    } else if (lastProductionStatus) {
      await renderReadOnlyProductionFallback(lastProductionStatus);
    }
  }

  setCurrentStep(data.step || 1);
  document.getElementById("top").scrollIntoView({ behavior: "smooth" });
}

// Dropdown "Dự án trước đó" ở sidebar.
const sidebarRecentBtn = document.getElementById("sidebar-recent-btn");
const sidebarRecentPanel = document.getElementById("sidebar-recent-panel");
const recentProjectsList = document.getElementById("recent-projects-list");
const recentProjectsEmptyHint = document.getElementById("recent-projects-empty-hint");

function closeRecentProjectsPanel() {
  sidebarRecentPanel.hidden = true;
  sidebarRecentPanel.classList.remove("open");
  sidebarRecentBtn.setAttribute("aria-expanded", "false");
}

function formatRelativeTime(isoString) {
  const diffMin = Math.max(0, Math.round((Date.now() - new Date(isoString).getTime()) / 60000));
  const lang = i18n.current;
  if (diffMin < 1) return lang === "en" ? "just now" : lang === "ru" ? "только что" : "vừa xong";
  if (diffMin < 60) return `${diffMin} ${lang === "en" ? "min ago" : lang === "ru" ? "мин. назад" : "phút trước"}`;
  const diffHour = Math.round(diffMin / 60);
  if (diffHour < 24) return `${diffHour} ${lang === "en" ? "h ago" : lang === "ru" ? "ч. назад" : "giờ trước"}`;
  const diffDay = Math.round(diffHour / 24);
  return `${diffDay} ${lang === "en" ? "d ago" : lang === "ru" ? "дн. назад" : "ngày trước"}`;
}

async function loadRecentProjectsList() {
  try {
    const res = await fetch("/api/projects/recent");
    const data = await res.json();
    const projects = data.projects || [];
    recentProjectsEmptyHint.classList.toggle("section-hidden", projects.length > 0);
    const esc = (s) => (s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;");
    recentProjectsList.innerHTML = projects
      .map(
        (p) => `<div class="recent-project-item" data-project-id="${esc(p.project_id)}">
        <span class="recent-project-title">${esc(p.title)}</span>
        <span class="recent-project-meta">${esc(p.stage_label)} · ${formatRelativeTime(p.updated_at)}</span>
      </div>`
      )
      .join("");
    recentProjectsList.querySelectorAll(".recent-project-item").forEach((item) => {
      item.addEventListener("click", async () => {
        closeRecentProjectsPanel();
        try {
          const snapRes = await fetch(`/api/projects/${item.dataset.projectId}/snapshot`);
          if (!snapRes.ok) throw new Error("not found");
          const snapshot = await snapRes.json();
          await restoreProjectFromSnapshot(snapshot);
          showNotice(i18n.t("recent_project_restored_notice"), null);
        } catch {
          showNotice(i18n.t("recent_project_restore_failed"), null);
        }
      });
    });
  } catch {
    /* im lặng — panel chỉ hiện trống, không chặn phần còn lại của trang */
  }
}

sidebarRecentBtn.addEventListener("click", (e) => {
  e.stopPropagation();
  const willOpen = sidebarRecentPanel.hidden;
  if (willOpen) {
    loadRecentProjectsList();
    sidebarRecentPanel.hidden = false;
    sidebarRecentPanel.classList.add("open");
  } else {
    closeRecentProjectsPanel();
  }
  sidebarRecentBtn.setAttribute("aria-expanded", String(willOpen));
});
document.addEventListener("click", (e) => {
  if (!e.target.closest("#sidebar-recent-wrap")) closeRecentProjectsPanel();
});

// Nút "Giao diện" ở sidebar (2026-09-17): 4 lựa chọn — Mặc định / Dark /
// Mặc định + ảnh KOL mẫu bên trái / Mặc định + ảnh người dùng tự chọn bên
// trái. Lưu lựa chọn + ảnh tự chọn (nếu có) vào localStorage — giống hệt
// cách app đã lưu ảnh đại diện (setAvatarPhoto/profile_avatar phía dưới):
// không gửi lên server, chỉ ảnh hưởng trình duyệt hiện tại.
const sidebarThemeBtn = document.getElementById("sidebar-theme-btn");
const sidebarThemePanel = document.getElementById("sidebar-theme-panel");
const themeCustomBgInput = document.getElementById("theme-custom-bg-input");
const themeChangeImageBtn = document.getElementById("theme-change-image-btn");
const THEME_SAMPLE_BG_URL = "/theme-bg-sample.jpg";
// 6 giá trị theme (2026-09-17, mở rộng theo yêu cầu người dùng): Dark giờ
// KẾT HỢP ĐƯỢC với 2 lựa chọn ảnh nền bên trái, không còn 4 lựa chọn tách
// biệt loại trừ nhau như bản đầu — "dark_sample_bg"/"dark_custom_bg" vừa
// bật nền tối vừa bật ảnh bên trái cùng lúc. Bảng tra cứu dưới đây tách
// riêng 2 khía cạnh (màu sắc / ảnh bên trái) khỏi 1 chuỗi giá trị duy nhất,
// để applyTheme() không phải if/else lặp lại cho từng tổ hợp.
const THEME_DARK_SET = new Set(["dark", "dark_sample_bg", "dark_custom_bg"]);
const THEME_IMAGE_KIND = {
  sample_bg: "sample", custom_bg: "custom",
  dark_sample_bg: "sample", dark_custom_bg: "custom",
};
let pendingCustomBgDark = false; // nhớ đang chọn biến thể Dark hay không lúc mở hộp chọn file

function closeThemePanel() {
  sidebarThemePanel.hidden = true;
  sidebarThemePanel.classList.remove("open");
  sidebarThemeBtn.setAttribute("aria-expanded", "false");
}

function applyTheme(theme) {
  const html = document.documentElement;
  html.dataset.theme = THEME_DARK_SET.has(theme) ? "dark" : "";
  const imageKind = THEME_IMAGE_KIND[theme] || null;
  html.classList.toggle("has-left-bg-image", !!imageKind);
  if (imageKind === "sample") {
    html.style.setProperty("--left-bg-image", `url(${THEME_SAMPLE_BG_URL})`);
  } else if (imageKind === "custom") {
    const saved = localStorage.getItem("theme_custom_bg");
    if (saved) html.style.setProperty("--left-bg-image", `url(${saved})`);
  } else {
    html.style.removeProperty("--left-bg-image");
  }
  themeChangeImageBtn.classList.toggle("section-hidden", imageKind !== "custom");
  document.querySelectorAll('input[name="ui-theme"]').forEach((r) => { r.checked = r.value === theme; });
}

function pickCustomBgFile() {
  themeCustomBgInput.click();
}

themeCustomBgInput.addEventListener("change", () => {
  const file = themeCustomBgInput.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    const img = new Image();
    img.onload = () => {
      // Ảnh nền bên trái cần rộng/cao hơn ảnh đại diện nhiều — giới hạn
      // 480x900 (giữ tỉ lệ), đủ nét trên màn hình thường mà vẫn nhẹ cho
      // localStorage (chỉ vài trăm KB thay vì vài MB của ảnh gốc điện thoại).
      const maxW = 480, maxH = 900;
      const scale = Math.min(maxW / img.width, maxH / img.height, 1);
      const w = Math.round(img.width * scale);
      const h = Math.round(img.height * scale);
      const canvas = document.createElement("canvas");
      canvas.width = w;
      canvas.height = h;
      canvas.getContext("2d").drawImage(img, 0, 0, w, h);
      const dataUrl = canvas.toDataURL("image/jpeg", 0.85);
      localStorage.setItem("theme_custom_bg", dataUrl);
      const theme = pendingCustomBgDark ? "dark_custom_bg" : "custom_bg";
      localStorage.setItem("ui_theme", theme);
      applyTheme(theme);
    };
    img.src = reader.result;
  };
  reader.readAsDataURL(file);
});

themeChangeImageBtn.addEventListener("click", () => {
  pendingCustomBgDark = THEME_DARK_SET.has(localStorage.getItem("ui_theme") || "default");
  pickCustomBgFile();
});

document.querySelectorAll('input[name="ui-theme"]').forEach((radio) => {
  radio.addEventListener("change", () => {
    const theme = radio.value;
    // Lần đầu chọn 1 trong 2 "ảnh tự chọn" (thường hoặc kèm Dark) mà chưa có
    // ảnh nào lưu sẵn — mở hộp chọn file NGAY, chỉ thực sự áp dụng theme sau
    // khi chọn xong (xem sự kiện "change" của themeCustomBgInput ở trên) —
    // bấm Huỷ thì giữ theme cũ.
    if (THEME_IMAGE_KIND[theme] === "custom" && !localStorage.getItem("theme_custom_bg")) {
      pendingCustomBgDark = THEME_DARK_SET.has(theme);
      pickCustomBgFile();
      return;
    }
    localStorage.setItem("ui_theme", theme);
    applyTheme(theme);
  });
});

sidebarThemeBtn.addEventListener("click", (e) => {
  e.stopPropagation();
  const willOpen = sidebarThemePanel.hidden;
  if (willOpen) {
    sidebarThemePanel.hidden = false;
    sidebarThemePanel.classList.add("open");
  } else {
    closeThemePanel();
  }
  sidebarThemeBtn.setAttribute("aria-expanded", String(willOpen));
});
document.addEventListener("click", (e) => {
  if (!e.target.closest("#sidebar-theme-wrap")) closeThemePanel();
});

applyTheme(localStorage.getItem("ui_theme") || "default");

// Đóng tab/trình duyệt mà không kịp trigger 1 trong các mốc lưu ở trên (VD
// vừa gõ xong 1 chữ rồi đóng ngay trong lúc debounce 1.5s chưa kịp chạy) —
// cố lưu 1 lần cuối bằng sendBeacon (không chờ phản hồi, không bị trình
// duyệt huỷ ngang như fetch() thường khi trang đang đóng).
window.addEventListener("beforeunload", () => {
  if (!state.projectId) return;
  const payload = {
    title: computeProjectTitle(),
    stage_label: computeProjectStageLabel(),
    data: collectProjectState(),
  };
  navigator.sendBeacon(
    `/api/projects/${state.projectId}/snapshot`,
    new Blob([JSON.stringify(payload)], { type: "application/json" })
  );
});

loadProfile();

loadKeyStatus();
loadLanguages();

function restoreProductionFromUrl() {
  const jobId = new URL(window.location.href).searchParams.get("production_job");
  if (!jobId || !/^[a-zA-Z0-9_-]{1,80}$/.test(jobId)) return;
  currentProductionJobId = jobId;
  startProductionPolling(jobId);
  step6Section.scrollIntoView({ behavior: "smooth" });
}

restoreProductionFromUrl();


document.querySelectorAll('#pipeline-mode-choice input[name="pipeline-mode"]').forEach((radio) => {
  radio.addEventListener("change", (e) => {
    const isAuto = e.target.value === "auto";
    const calSection = document.getElementById("automation-calendar-section");
    if(calSection) {
      calSection.classList.toggle("section-hidden", !isAuto);
    }
  });
});

const genCalBtn = document.getElementById("generate-calendar-btn");
if (genCalBtn) {
  genCalBtn.addEventListener("click", async () => {
    const strategy = document.getElementById("calendar-strategy").value.trim();
    const platforms = document.getElementById("calendar-platforms").value.split(",").map(s => s.trim()).filter(Boolean);
    const videos_per_day = parseInt(document.getElementById("calendar-videos-per-day").value, 10);
    const days = parseInt(document.getElementById("calendar-days").value, 10);
    const duration_seconds = parseInt(document.getElementById("calendar-duration").value, 10);

    if (!strategy || !platforms.length) return alert("Vui lòng nhập chiến lược và nền tảng");

    genCalBtn.disabled = true;
    genCalBtn.textContent = "Đang lập thực đơn...";
    
    try {
      const res = await fetch("/api/calendar/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ strategy, platforms, videos_per_day, days, duration_seconds })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Lỗi API");
      
      let html = `<p><strong>Tổng số video:</strong> ` + data.total_videos + `</p>`;
      html += `<div style="max-height: 400px; overflow-y: auto;"><table style="width:100%; border-collapse: collapse;" border="1">`;
      html += `<tr><th>Ngày</th><th>Giờ</th><th>Nền tảng</th><th>Chủ đề</th><th>Hook</th></tr>`;
      data.slots.forEach(s => {
        html += `<tr><td>`+s.day+`</td><td>`+s.publish_time+`</td><td>`+s.platform+`</td><td>`+s.topic+`</td><td>`+s.hook_idea+`</td></tr>`;
      });
      html += `</table></div>`;
      document.getElementById("calendar-results").innerHTML = html;
    } catch(err) {
      alert(err.message);
    } finally {
      genCalBtn.disabled = false;
      genCalBtn.textContent = "Lập thực đơn";
    }
  });
}
