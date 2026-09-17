"""Kết nối LLM — dùng cho Bước 1-4, 7, 11-12 (Mục 3, V3): viết lại câu
chuyện, kịch bản, storyboard, prompt cảnh, các gợi ý biên tập/tối ưu, VÀ
(Bước 9b) tự động phân tích + viết lại prompt khi Google Flow từ chối tạo
video vì chính sách nội dung.

Hỗ trợ 4 CÁCH gọi LLM, người dùng tự chọn ở màn hình Cài đặt — 2 cách đầu
dùng Claude (Anthropic), 2 cách sau dùng CLI chính thức của 2 hãng khác,
đúng tinh thần "tài khoản đã đăng nhập sẵn, không cần API key riêng" như
Claude Code CLI. MẶC ĐỊNH khi chưa từng chọn: ưu tiên tài khoản CLI đã đăng
nhập sẵn (claude_cli → codex_cli → gemini_cli theo thứ tự, xem
get_backend()) — "api" chỉ là 1 PHƯƠNG ÁN THÊM chứ không phải lựa chọn mặc
định, vì đa số người dùng có sẵn tài khoản Pro/Plus hơn là có API key riêng:
1. "api" — API key Anthropic do CHÍNH người dùng cung cấp, lưu
   cục bộ ở file .env tại thư mục gốc dự án. Tính phí theo lượt gọi.
2. "claude_cli" — tài khoản Claude Pro/Max đã đăng nhập sẵn qua Claude Code
   CLI (`claude` đã cài trên máy, `claude setup-token`/đăng nhập từ trước)
   — gọi qua subprocess ở chế độ in-ra-rồi-thoát (`claude -p`).
3. "codex_cli" — tài khoản ChatGPT Plus/Pro/Team/Business/Enterprise đã
   đăng nhập sẵn qua Codex CLI của OpenAI (`codex` đã cài trên máy, `codex
   login` từ trước) — gọi qua subprocess ở chế độ tự động không hỏi lại
   (`codex exec`, đọc prompt qua stdin).
4. "gemini_cli" — giữ mã cấu hình cũ, dùng tài khoản Google đã đăng nhập
   qua Antigravity CLI (`agy`). Gemini CLI ngừng phục vụ tài khoản cá nhân,
   gồm Google AI Pro/Ultra, từ 18/06/2026. Gửi prompt bằng stream-json qua
   stdin; chỉ lấy response của sự kiện result thành công. Không tự chuyển
   sang API key khi CLI gặp lỗi. Xem hướng dẫn trong README.md.

.env KHÔNG BAO GIỜ commit lên git (đã có trong .gitignore) và API key KHÔNG
BAO GIỜ trả nguyên về cho frontend sau khi lưu.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import httpx
from anthropic import Anthropic
from dotenv import load_dotenv

MODEL = "claude-opus-5"
# "openai_api"/"gemini_api" (2026-09-17): API key riêng KHÔNG chỉ có Anthropic
# — người dùng có thể có sẵn API key OpenAI hoặc Google AI thay vì Anthropic,
# nên thẻ "Dùng API key riêng" giờ có menu xổ xuống chọn 1 trong 3 hãng,
# giống hệt menu xổ xuống của thẻ tài khoản CLI bên cạnh.
BACKENDS = ("api", "openai_api", "gemini_api", "claude_cli", "codex_cli", "gemini_cli")
# Model mặc định cho 2 API mới — có thể cần cập nhật lên bản mới hơn nếu hãng
# phát hành flagship mới sau thời điểm viết code này.
OPENAI_API_MODEL = "gpt-4.1"
GEMINI_API_MODEL = "gemini-2.5-pro"
API_KEY_ENV_VARS = {
    "api": "ANTHROPIC_API_KEY",
    "openai_api": "OPENAI_API_KEY",
    "gemini_api": "GEMINI_API_KEY",
}
CLAUDE_CLI_TIMEOUT_SECONDS = 180
CODEX_CLI_TIMEOUT_SECONDS = 180
GEMINI_CLI_TIMEOUT_SECONDS = 180
API_TIMEOUT_SECONDS = 180
ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"

load_dotenv(ENV_PATH)


class LlmNotConfiguredError(RuntimeError):
    pass


class LlmRefusalError(RuntimeError):
    pass


class LlmCliError(RuntimeError):
    pass


class LlmJsonParseError(RuntimeError):
    """`generate_json()` gọi thành công nhưng không tách/parse được JSON hợp
    lệ từ kết quả trả về — chỉ ném ra khi `raise_on_error=True` (xem
    generate_json())."""


def get_backend() -> str:
    """1 trong BACKENDS. Nếu người dùng CHƯA từng chọn (biến môi trường
    LLM_BACKEND chưa lưu), ưu tiên tài khoản đã đăng nhập sẵn (Claude Pro/Max
    -> ChatGPT Plus/Pro -> Gemini) thay vì API key — API key chỉ nên là 1
    PHƯƠNG ÁN THÊM cho ai muốn trả phí theo lượt gọi, không phải mặc định,
    vì phần lớn người dùng có sẵn 1 trong 3 tài khoản CLI hơn là có sẵn API
    key riêng. Chỉ rơi về 'api' khi máy không có CLI nào đã đăng nhập."""
    saved = os.environ.get("LLM_BACKEND", "").strip()
    if saved:
        return saved
    if claude_cli_available():
        return "claude_cli"
    if codex_cli_available():
        return "codex_cli"
    if gemini_cli_available():
        return "gemini_cli"
    return "api"


def _write_env_line(key: str, value: str | None) -> None:
    lines: list[str] = []
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            if not line.startswith(f"{key}="):
                lines.append(line)
    if value is not None:
        lines.append(f"{key}={value}")
    ENV_PATH.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    if value is not None:
        os.environ[key] = value
    else:
        os.environ.pop(key, None)


def save_backend(mode: str) -> None:
    mode = mode.strip()
    if mode not in BACKENDS:
        raise ValueError(f"Cách gọi LLM không hợp lệ (chỉ nhận 1 trong {BACKENDS})")
    _write_env_line("LLM_BACKEND", mode)


def claude_cli_available() -> bool:
    return shutil.which("claude") is not None


def codex_cli_available() -> bool:
    return shutil.which("codex") is not None


def gemini_cli_available() -> bool:
    return shutil.which("agy") is not None


def is_configured() -> bool:
    backend = get_backend()
    if backend == "claude_cli":
        return claude_cli_available()
    if backend == "codex_cli":
        return codex_cli_available()
    if backend == "gemini_cli":
        return gemini_cli_available()
    return has_api_key(backend)


def has_api_key(backend: str = "api") -> bool:
    """True nếu backend API key đó (Anthropic/OpenAI/Google) đã có key lưu
    sẵn — dùng cho cả `is_configured()` (backend đang active) lẫn cho màn
    hình Cài đặt hiển thị trạng thái từng thẻ trong menu xổ xuống dù thẻ đó
    có đang được chọn làm backend active hay không."""
    env_var = API_KEY_ENV_VARS.get(backend)
    return bool(env_var and os.environ.get(env_var))


def save_api_key(api_key: str, backend: str = "api") -> None:
    api_key = api_key.strip()
    if not api_key:
        raise ValueError("API key rỗng")
    env_var = API_KEY_ENV_VARS.get(backend)
    if env_var is None:
        raise ValueError(f"Backend '{backend}' không dùng API key riêng")
    _write_env_line(env_var, api_key)


def clear_api_key(backend: str = "api") -> None:
    env_var = API_KEY_ENV_VARS.get(backend)
    if env_var is None:
        raise ValueError(f"Backend '{backend}' không dùng API key riêng")
    _write_env_line(env_var, None)


def get_client() -> Anthropic:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise LlmNotConfiguredError(
            "Chưa cấu hình ANTHROPIC_API_KEY. Vào màn hình Cài đặt để nhập API key của bạn."
        )
    return Anthropic()


def _generate_text_via_api(system: str, user_prompt: str, max_tokens: int, effort: str) -> str:
    client = get_client()
    with client.messages.stream(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        thinking={"type": "adaptive"},
        output_config={"effort": effort},
        messages=[{"role": "user", "content": user_prompt}],
    ) as stream:
        final = stream.get_final_message()

    if final.stop_reason == "refusal":
        raise LlmRefusalError(
            "Claude từ chối yêu cầu này vì lý do an toàn. Hãy điều chỉnh nội dung đầu vào."
        )
    return next((b.text for b in final.content if b.type == "text"), "")


def _generate_text_via_openai_api(system: str, user_prompt: str, max_tokens: int) -> str:
    """API key OpenAI riêng của người dùng (khác với 'codex_cli' — tài khoản
    ChatGPT Plus/Pro đăng nhập sẵn qua Codex CLI, không cần API key). Gọi
    thẳng REST Chat Completions bằng httpx (đã là dependency sẵn có), không
    thêm SDK `openai` nặng chỉ để gọi 1 endpoint đơn giản."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise LlmNotConfiguredError(
            "Chưa cấu hình OPENAI_API_KEY. Vào màn hình Cài đặt để nhập API key OpenAI của bạn."
        )
    try:
        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": OPENAI_API_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_prompt},
                ],
                "max_completion_tokens": max_tokens,
            },
            timeout=API_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        raise LlmCliError(f"Không gọi được OpenAI API: {exc}") from exc
    if resp.status_code != 200:
        raise LlmCliError(f"OpenAI API báo lỗi (mã {resp.status_code}): {resp.text[:500]}")
    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, AttributeError) as exc:
        raise LlmCliError(f"OpenAI API trả về dữ liệu không hợp lệ: {data}") from exc


def _generate_text_via_gemini_api(system: str, user_prompt: str, max_tokens: int) -> str:
    """API key Google AI (Gemini) riêng của người dùng (khác với 'gemini_cli'
    — tài khoản Google AI Pro/Ultra đăng nhập sẵn qua Antigravity CLI). Gọi
    thẳng REST generateContent bằng httpx, không thêm SDK `google-genai`."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise LlmNotConfiguredError(
            "Chưa cấu hình GEMINI_API_KEY. Vào màn hình Cài đặt để nhập API key Google AI (Gemini) của bạn."
        )
    try:
        resp = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_API_MODEL}:generateContent",
            params={"key": api_key},
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                "systemInstruction": {"parts": [{"text": system}]},
                "generationConfig": {"maxOutputTokens": max_tokens},
            },
            timeout=API_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        raise LlmCliError(f"Không gọi được Gemini API: {exc}") from exc
    if resp.status_code != 200:
        raise LlmCliError(f"Gemini API báo lỗi (mã {resp.status_code}): {resp.text[:500]}")
    data = resp.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError, AttributeError) as exc:
        raise LlmCliError(f"Gemini API trả về dữ liệu không hợp lệ: {data}") from exc


def _generate_text_via_cli(system: str, user_prompt: str) -> str:
    """Gọi Claude Code CLI ở chế độ in-ra-rồi-thoát (`claude -p`), dùng tài
    khoản Pro/Max đã đăng nhập sẵn trên máy thay vì API key. Ghép system +
    user thành 1 prompt vì `-p` chỉ nhận 1 khối văn bản qua stdin."""
    if not claude_cli_available():
        raise LlmNotConfiguredError(
            "Chưa tìm thấy lệnh 'claude' trên máy này. Cài Claude Code CLI và đăng nhập "
            "tài khoản Pro/Max trước, hoặc chuyển sang cách 'API key' trong Cài đặt."
        )
    combined = f"{system}\n\n---\n\n{user_prompt}"
    try:
        # shell=True vì trên Windows, npm cài 'claude' thành file '.CMD' (script
        # shell, không phải .exe) — CreateProcess không tự chạy được .CMD nếu
        # không qua cmd.exe. An toàn vì nội dung động (combined) chỉ truyền qua
        # stdin (input=...), KHÔNG nằm trong dòng lệnh, nên không có rủi ro
        # command injection dù dùng shell=True.
        result = subprocess.run(
            ["claude", "-p"],
            input=combined,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=CLAUDE_CLI_TIMEOUT_SECONDS,
            shell=True,
        )
    except subprocess.TimeoutExpired as exc:
        raise LlmCliError(
            f"Gọi Claude CLI quá {CLAUDE_CLI_TIMEOUT_SECONDS}s không có phản hồi."
        ) from exc
    if result.returncode != 0:
        raise LlmCliError(
            f"Claude CLI báo lỗi (mã {result.returncode}): {result.stderr.strip() or result.stdout.strip()}"
        )
    output = result.stdout.strip()
    if not output:
        raise LlmCliError("Claude CLI không trả về nội dung gì.")
    return output


def _generate_text_via_codex_cli(system: str, user_prompt: str) -> str:
    """Gọi Codex CLI (OpenAI) ở chế độ tự động (`codex exec`), dùng tài
    khoản ChatGPT Plus/Pro/Team/Business/Enterprise đã đăng nhập sẵn trên
    máy (`codex login`) thay vì API key riêng. Đọc prompt qua stdin —
    giống hệt lý do dùng stdin ở `_generate_text_via_cli` (Claude): tránh
    giới hạn độ dài dòng lệnh của Windows và không có rủi ro command
    injection dù dùng shell=True."""
    if not codex_cli_available():
        raise LlmNotConfiguredError(
            "Chưa tìm thấy lệnh 'codex' trên máy này. Cài Codex CLI (OpenAI) và đăng nhập "
            "tài khoản ChatGPT Plus/Pro trước, hoặc chuyển sang cách khác trong Cài đặt."
        )
    combined = f"{system}\n\n---\n\n{user_prompt}"
    try:
        result = subprocess.run(
            ["codex", "exec"],
            input=combined,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=CODEX_CLI_TIMEOUT_SECONDS,
            shell=True,
        )
    except subprocess.TimeoutExpired as exc:
        raise LlmCliError(
            f"Gọi Codex CLI quá {CODEX_CLI_TIMEOUT_SECONDS}s không có phản hồi."
        ) from exc
    if result.returncode != 0:
        raise LlmCliError(
            f"Codex CLI báo lỗi (mã {result.returncode}): {result.stderr.strip() or result.stdout.strip()}"
        )
    output = result.stdout.strip()
    if not output:
        raise LlmCliError("Codex CLI không trả về nội dung gì.")
    return output


def _generate_text_via_gemini_cli(system: str, user_prompt: str) -> str:
    """Dùng phiên Google của Antigravity CLI, giữ tên backend để tương thích."""
    executable = shutil.which("agy")
    if not executable:
        raise LlmNotConfiguredError(
            "Chưa tìm thấy Antigravity CLI ('agy'). Gemini CLI cũ không còn hỗ trợ "
            "tài khoản cá nhân (UNSUPPORTED_CLIENT). Cài từ https://antigravity.google/docs/cli/install/ "
            "rồi chạy 'agy' để đăng nhập tài khoản Google AI Pro/Ultra và khởi động lại app."
        )
    combined = f"{system}\n\n---\n\n{user_prompt}"
    payload = json.dumps({"event": "user", "message": {"content": combined}}, ensure_ascii=False) + "\n"
    try:
        result = subprocess.run(
            [executable, "--input-format", "stream-json", "--output-format", "stream-json",
             "--model", "gemini-3.1-pro-high",
             "--disable-slash-commands", "--print-timeout", f"{GEMINI_CLI_TIMEOUT_SECONDS}s"],
            input=payload,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=GEMINI_CLI_TIMEOUT_SECONDS,
            shell=False,
            cwd=ENV_PATH.parent,
        )
    except subprocess.TimeoutExpired as exc:
        raise LlmCliError(
            f"Gọi Antigravity CLI quá {GEMINI_CLI_TIMEOUT_SECONDS}s không có phản hồi."
        ) from exc
    except OSError as exc:
        raise LlmCliError(f"Không chạy được Antigravity CLI: {exc}") from exc
    if result.returncode != 0:
        raise LlmCliError(
            f"Antigravity CLI báo lỗi (mã {result.returncode}): "
            f"{result.stderr.strip() or result.stdout.strip()}\n"
            f"Nếu chưa đăng nhập hoặc thư mục chưa được tin cậy, mở terminal tại {ENV_PATH.parent}, "
            "chạy 'agy', đăng nhập Google và xác nhận tin cậy đúng thư mục này. "
            "Nếu CLI không nhận stream-json, cập nhật bằng 'agy update'. "
            "App không tự chuyển sang API trả tiền."
        )
    response = None
    try:
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            if not isinstance(event, dict):
                raise ValueError("Sự kiện không phải JSON object")
            if event.get("event") != "result":
                continue
            if response is not None:
                raise ValueError("Nhận nhiều kết quả cho một prompt")
            final = event.get("result")
            if not isinstance(final, dict):
                raise ValueError("Thiếu đối tượng result")
            if final.get("status") != "SUCCESS":
                raise LlmCliError(
                    f"Antigravity CLI chưa hoàn tất ({final.get('status', 'UNKNOWN')}): "
                    f"{final.get('error') or result.stderr.strip() or 'Không có kết quả hoàn chỉnh.'}"
                )
            response = final.get("response")
            if not isinstance(response, str):
                raise ValueError("response không phải chuỗi văn bản")
    except ValueError as exc:
        raise LlmCliError(f"Antigravity CLI trả stream-json không hợp lệ: {exc}") from exc
    if response is None:
        raise LlmCliError("Antigravity CLI không trả về sự kiện result; không dùng nội dung đang sinh dở.")
    if not response.strip():
        raise LlmCliError("Antigravity CLI không trả về nội dung gì.")
    return response.strip()


_CLI_GENERATORS = {
    "claude_cli": _generate_text_via_cli,
    "codex_cli": _generate_text_via_codex_cli,
    "gemini_cli": _generate_text_via_gemini_cli,
}


def generate_text(system: str, user_prompt: str, max_tokens: int = 16000, effort: str = "high") -> str:
    """Gọi LLM 1 lần theo đúng cách người dùng đã chọn ở Cài đặt: API key
    riêng (Anthropic/OpenAI/Google), hoặc 1 trong 3 tài khoản CLI đã đăng
    nhập sẵn (Claude/ChatGPT/Gemini). Với API Anthropic: luôn dùng streaming
    (tránh timeout với output dài) + adaptive thinking; 2 API key kia gọi
    REST đơn giản (không cần streaming, không hỗ trợ "effort"). Trả về text
    cuối cùng; ném LlmRefusalError (API Anthropic) hoặc LlmCliError (CLI/API
    khác) nếu có vấn đề."""
    backend = get_backend()
    cli_fn = _CLI_GENERATORS.get(backend)
    if cli_fn is not None:
        return cli_fn(system, user_prompt)
    if backend == "openai_api":
        return _generate_text_via_openai_api(system, user_prompt, max_tokens)
    if backend == "gemini_api":
        return _generate_text_via_gemini_api(system, user_prompt, max_tokens)
    return _generate_text_via_api(system, user_prompt, max_tokens, effort)


# ---------------------------------------------------------------------------
# Bước 9b: tự động phân tích + viết lại prompt khi Google Flow từ chối video
# ---------------------------------------------------------------------------

FLOW_POLICY_FIXER_SYSTEM_PROMPT = """Bạn là trợ lý sửa prompt cho Google Flow (Veo3) khi bị từ chối tạo video vì
chính sách nội dung. Dựa trên các bài học thật đã tích luỹ được (skill
veo3-prominent-people-policy):

1. Chính sách "prominent people" (chống deepfake người nổi tiếng) có thể bị kích hoạt bởi:
   - Tên thật ghép chức danh kiểu lãnh đạo (emperor/general/king/president...) trong prompt,
     đặc biệt trong khối "Character consistency".
   - Bố cục nghi lễ/chân dung/diễn thuyết trước đám đông.
   - Từ 2 nhân vật nổi bật/có vai trò chỉ huy xuất hiện cùng lúc trong 1 cảnh — DÙ ĐÃ bỏ tên,
     bố cục "2 người chỉ huy nổi bật ngang nhau" vẫn có thể bị bắt.
   - Nhân vật có tên cưỡi voi dẫn đầu đoàn voi khác (giống ảnh nghi lễ/vương quyền) dễ bị bắt
     hơn cưỡi ngựa dù cùng bố cục.
   - Character Consistency bị gắn vào cảnh mà nhân vật đó KHÔNG thực sự xuất hiện (chỉ được
     nhắc tên để chỉ vị trí/liên quan).
2. Chính sách "harmful content" có thể bị kích hoạt bởi: mô tả giết chóc cụ thể nhắm vào 1
   người có tên (VD "cut down", "killed") CỘNG DỒN với thuật ngữ vũ khí nghe hiện đại/hoá học
   (VD "shrapnel", "phosphorus").
3. QUAN TRỌNG: bộ lọc của Flow có tính NGẪU NHIÊN — cùng 1 prompt có lúc qua, có lúc bị chặn.
   Nếu prompt gốc không có gì thật sự sai theo 2 mục trên, có thể đây chỉ là báo nhầm ngẫu
   nhiên — trong trường hợp đó, trả lại NGUYÊN VĂN prompt gốc không đổi gì cả (để hệ thống thử
   lại y hệt), thay vì cắt bớt chi tiết một cách không cần thiết.

Nhiệm vụ: nhận 1 prompt tiếng Anh đã bị Google Flow từ chối kèm lý do Flow đưa ra, xác định
đúng nguyên nhân theo các mẫu trên, rồi viết lại. Quy tắc bắt buộc:
- CHỈ sửa đúng phần gây vi phạm chính sách, GIỮ NGUYÊN mọi nội dung/hành động khác của cảnh.
- Nếu phải bỏ tên riêng: chuyển mô tả ngoại hình (giáp, vũ khí, phương tiện di chuyển) thẳng
  vào câu mô tả chính, không dùng tên riêng + chức danh chính thức nữa.
- Nếu có 2 nhân vật nổi bật cùng lúc: giữ 1 nhân vật nổi bật chính, nhân vật/đoàn quân còn lại
  chỉ mô tả như chi tiết nền, không gán vai trò "chỉ huy" riêng.
- Nếu nghi ngờ báo nhầm ngẫu nhiên (không thấy vi phạm rõ ràng theo các mẫu trên): trả lại
  đúng nguyên văn prompt gốc.

QUAN TRỌNG VỀ ĐỊNH DẠNG TRẢ LỜI: bất kể có thêm lời giải thích/chào hỏi nào khác trước hay
sau không (một số môi trường chạy có thể tự chèn thêm), PHẢI luôn bọc đúng 1 bản prompt cuối
cùng (đã sửa, hoặc nguyên văn nếu nghi ngờ báo nhầm) giữa 2 dòng đánh dấu chính xác như sau,
không thêm gì khác vào giữa 2 dòng đó ngoài chính prompt:
===PROMPT_BAT_DAU===
(nội dung prompt ở đây)
===PROMPT_KET_THUC==="""


def fix_flow_rejected_prompt(original_prompt: str, error_message: str) -> str:
    """Nhờ Claude (API hoặc CLI, theo cấu hình người dùng đã chọn) phân tích
    lý do Google Flow từ chối 1 prompt, rồi trả về prompt đã viết lại (hoặc
    nguyên văn prompt cũ nếu Claude nghi ngờ đây chỉ là báo nhầm ngẫu
    nhiên). Dùng trong app/services/google_flow_driver.py khi gặp
    FlowContentPolicyViolation, để app có thể tự sửa và thử lại mà KHÔNG cần
    người dùng can thiệp."""
    user_prompt = (
        "Prompt gốc bị Google Flow (Veo3) từ chối:\n\n"
        f"{original_prompt}\n\n"
        "Lý do Flow báo:\n\n"
        f"{error_message}\n\n"
        "Hãy viết lại prompt theo đúng quy tắc đã nêu."
    )
    result = generate_text(
        FLOW_POLICY_FIXER_SYSTEM_PROMPT, user_prompt, max_tokens=2000, effort="medium"
    )
    return _extract_marked_prompt(result)


def _extract_marked(raw_text: str, start_marker: str, end_marker: str) -> str:
    """Tách phần nội dung nằm giữa 2 dòng đánh dấu. Cần thiết vì backend
    'claude_cli' chạy trong môi trường CÓ THỂ tự chèn thêm lời chào/giải
    thích trước câu trả lời (VD do CLAUDE.md riêng của người dùng trên máy
    đó) — nếu không tách riêng, phần chèn thêm này sẽ lẫn vào kết quả dùng
    tiếp trong code. Nếu không tìm thấy 2 dòng đánh dấu (VD backend 'api'
    vốn không bị chèn gì thêm), dùng nguyên văn kết quả làm phương án dự
    phòng."""
    start_idx = raw_text.find(start_marker)
    end_idx = raw_text.find(end_marker)
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        return raw_text[start_idx + len(start_marker) : end_idx].strip()
    return raw_text.strip()


def _extract_marked_prompt(raw_text: str) -> str:
    return _extract_marked(raw_text, "===PROMPT_BAT_DAU===", "===PROMPT_KET_THUC===")


# ---------------------------------------------------------------------------
# Bước 13: đề xuất lớp hiệu ứng âm thanh nền cho TỪNG CẢNH storyboard
# ---------------------------------------------------------------------------

SFX_LAYER_SUGGESTER_SYSTEM_PROMPT = """Bạn là chuyên viên âm thanh phim, chọn hiệu ứng âm thanh nền (SFX) cho
TỪNG CẢNH storyboard của 1 phim ngắn, để tìm trên trang tiengdong.com (thư
viện hiệu ứng âm thanh tiếng Việt, KHÔNG PHẢI nhạc nền có giai điệu — chỉ
có tiếng động thật: vó ngựa, bước chân, gió, sóng, gươm giáo, đại bác,
đám đông, sấm sét, gỗ vỡ...).

Rút kinh nghiệm THẬT đã gặp (bắt buộc tuân theo):
1. Phải bám ĐÚNG hành động vật lý đang diễn ra trong cảnh — cảnh có ngựa
   phi PHẢI có lớp tiếng vó ngựa; cảnh đoàn quân/voi/kỵ binh cùng di
   chuyển PHẢI có lớp tiếng bước chân/vó ngựa/chân voi rầm rập; cảnh vượt
   sông PHẢI có tiếng nước; cảnh bắn đại bác PHẢI có tiếng nổ; cảnh chặt
   phá công sự gỗ PHẢI có tiếng gỗ vỡ. KHÔNG dùng 1 câu tìm kiếm chung
   chung cho nhiều cảnh khác nội dung nhau.
2. 1 cảnh có thể cần NHIỀU LỚP âm thanh chồng lên nhau cùng lúc (ví dụ:
   vó ngựa + tiếng voi + tiếng hò hét cùng 1 cảnh xung trận) — trả về tối
   đa 4 lớp, tối thiểu 0 lớp (cảnh tĩnh lặng, đối thoại nội tâm, chân
   dung cận cảnh không cần thêm hiệu ứng gì cả thì trả về mảng rỗng []).
3. KHÔNG dùng hiệu ứng "tiếng chim/chim chóc" (allow_birds=false) TRỪ KHI
   cảnh thật sự diễn ra ở rừng núi/thiên nhiên hoang dã (allow_birds=true)
   — tiếng chim ở sai cảnh (VD cảnh tiệc trong thành) nghe rất lạc quẻ.
4. Đúng tông cảm xúc của cảnh: cảnh chiến thắng/mừng vui KHÔNG dùng câu
   tìm kiếm mang nghĩa hoảng loạn/chạy trốn; cảnh tĩnh lặng/buồn bã KHÔNG
   dùng câu tìm kiếm ồn ào/dồn dập.
5. Mỗi `query_vi` là 1 CỤM TỪ TIẾNG VIỆT NGẮN (3-8 từ) mô tả ĐÚNG 1 LOẠI
   tiếng động cụ thể (không mô tả cả cảnh, không tính từ cảm xúc mơ hồ).
6. `gain_db`: lớp âm thanh CHÍNH của hành động nên gần 0 (khoảng -2 đến
   -6), lớp phụ/nền (gió, không khí xa) nên nhỏ hơn (khoảng -10 đến -16).

Trả lời CHỈ 1 mảng JSON hợp lệ, mỗi phần tử có đúng các trường:
{"query_vi": str, "gain_db": số (âm), "start_offset": số giây (thường 0),
"duration": số giây hoặc null (null = kéo dài hết cảnh), "allow_birds": bool}

QUAN TRỌNG VỀ ĐỊNH DẠNG TRẢ LỜI: bất kể có thêm lời giải thích/chào hỏi
nào khác trước hay sau không, PHẢI luôn bọc đúng 1 mảng JSON giữa 2 dòng
đánh dấu chính xác như sau, không thêm gì khác vào giữa 2 dòng đó ngoài
chính mảng JSON:
===SFX_LAYERS_BAT_DAU===
(mảng JSON ở đây)
===SFX_LAYERS_KET_THUC==="""


def suggest_sfx_layers(scene_prompt_en: str) -> list[dict]:
    """Nhờ Claude đọc prompt hình ảnh (tiếng Anh, dùng để sinh video AI) của
    1 cảnh storyboard, rồi đề xuất danh sách lớp âm thanh nền phù hợp
    (query tiếng Việt tìm trên tiengdong.com + gain/offset/duration mỗi
    lớp). Đây là bước thay thế cho việc gộp SFX theo cả đoạn lời dẫn —
    xem lỗi thật đã gặp (2026-09-13, phản hồi người dùng): ngựa phi không
    nghe tiếng vó ngựa, đoàn quân đi không nghe tiếng bước chân, vì SFX cũ
    được gán chung cho cả đoạn kịch bản thay vì riêng từng cảnh.

    Trả về [] nếu Claude từ chối/lỗi/không parse được — 1 cảnh thiếu gợi ý
    không nên chặn cả video (giữ đúng tinh thần xử lý lỗi đã có trong
    module này)."""
    import json

    user_prompt = (
        "Prompt hình ảnh (tiếng Anh) của cảnh storyboard này:\n\n"
        f"{scene_prompt_en}\n\n"
        "Hãy đề xuất danh sách lớp âm thanh nền phù hợp theo đúng quy tắc đã nêu."
    )
    layers = generate_json(
        SFX_LAYER_SUGGESTER_SYSTEM_PROMPT, user_prompt,
        "===SFX_LAYERS_BAT_DAU===", "===SFX_LAYERS_KET_THUC===",
        max_tokens=1000, effort="low", default=[],
    )
    return layers if isinstance(layers, list) else []


def generate_json(
    system: str, user_prompt: str, start_marker: str, end_marker: str,
    max_tokens: int = 1500, effort: str = "medium", default=None, raise_on_error: bool = False,
):
    """Gọi Claude rồi tách + parse đúng 1 khối JSON được bọc giữa 2 dòng
    đánh dấu (xem `_extract_marked` — cần thiết vì backend `claude_cli` có
    thể tự chèn thêm lời chào/giải thích).

    Mặc định (`raise_on_error=False`): trả về `default` nếu Claude từ chối/
    lỗi/không parse được — dùng cho mọi chỗ có gợi ý THÊM, thiếu không sao
    (SFX layers, hook, chủ đề...), tránh lặp lại logic try/except/parse ở
    từng nơi gọi.

    `raise_on_error=True`: dùng cho các chỗ kết quả là BẮT BUỘC, thiếu thì
    không thể tiếp tục (VD sinh prompt cảnh AI ở storyboard.py — lỗi thật đã
    gặp 2026-09-15: khi phiên Claude CLI bị gián đoạn giữa chừng, hành vi
    nuốt lỗi mặc định khiến cả 37 cảnh lặng lẽ trả về prompt RỖNG không một
    lời cảnh báo, người dùng tưởng app chạy xong nhưng thực ra mọi cảnh đều
    thất bại). Lỗi LLM thật (chưa cấu hình/bị từ chối/lỗi CLI) được ném lại
    NGUYÊN VẸN để lớp gọi phía trên (API) phân loại đúng mã lỗi; lỗi tách/
    parse JSON được bọc thành LlmJsonParseError để phân biệt với lỗi gọi
    LLM."""
    import json

    try:
        result = generate_text(system, user_prompt, max_tokens=max_tokens, effort=effort)
    except (LlmNotConfiguredError, LlmRefusalError, LlmCliError):
        if raise_on_error:
            raise
        return default
    try:
        raw_json = _extract_marked(result, start_marker, end_marker)
        return json.loads(raw_json)
    except Exception as exc:  # noqa: BLE001 - phải bắt mọi lỗi parse JSON không rõ trước để phân loại lại
        if raise_on_error:
            raise LlmJsonParseError(f"Không phân tích được JSON hợp lệ từ phản hồi LLM: {exc}") from exc
        return default


_TRANSLATE_SYSTEM_PROMPT = """Bạn là dịch giả video chuyên nghiệp. Dịch đúng nguyên văn lời dẫn/giọng đọc
(voice-over) sang ngôn ngữ đích, giữ đúng văn phong tự nhiên khi ĐỌC THÀNH
TIẾNG (không dịch máy móc từng từ), giữ đúng số liệu/tên riêng/địa danh,
giữ đúng số câu và ý nghĩa — không thêm bớt nội dung, không thêm chú thích.

QUAN TRỌNG VỀ ĐỊNH DẠNG TRẢ LỜI: chỉ trả về đúng phần văn bản đã dịch, bọc
giữa 2 dòng đánh dấu:
===DICH_BAT_DAU===
(văn bản đã dịch ở đây)
===DICH_KET_THUC==="""


def translate_text(text: str, target_language_name: str) -> str:
    """Dịch 1 đoạn lời dẫn sang ngôn ngữ đích — dùng cho Bước 3 (xuất đa
    ngôn ngữ): viết kịch bản 1 lần bằng ngôn ngữ gốc, rồi dịch lại cho từng
    ngôn ngữ xuất thêm, thay vì gọi Claude viết lại kịch bản từ đầu cho mỗi
    ngôn ngữ (tốn công + có thể lệch nội dung giữa các bản).

    Trả về nguyên văn `text` nếu Claude lỗi/chưa cấu hình — thà xuất video
    với văn bản gốc (sai ngôn ngữ giọng đọc) còn hơn chặn cả job vì 1 lỗi
    dịch thuật."""
    user_prompt = f"Dịch đoạn lời dẫn sau sang {target_language_name}:\n\n{text}"
    try:
        result = generate_text(_TRANSLATE_SYSTEM_PROMPT, user_prompt, max_tokens=2000, effort="low")
        translated = _extract_marked(result, "===DICH_BAT_DAU===", "===DICH_KET_THUC===")
        return translated if translated.strip() else text
    except Exception:  # noqa: BLE001 - lỗi dịch 1 đoạn không nên chặn cả job xuất video
        return text
