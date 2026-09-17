import json
import os
import subprocess
from types import SimpleNamespace

import pytest

from app.services import llm


@pytest.fixture()
def isolated_env(tmp_path, monkeypatch):
    """Cô lập ENV_PATH + biến môi trường ANTHROPIC_API_KEY/LLM_BACKEND, và
    giả lập cả 3 CLI (Claude/Codex/Gemini) là CHƯA cài, để test không đụng
    tới file .env thật hay trạng thái LLM thật của máy đang chạy test (VD
    máy dev đã có sẵn Claude CLI + LLM_BACKEND=claude_cli sẽ khiến test
    "chưa cấu hình gì" sai theo nếu không cô lập đủ)."""
    fake_env = tmp_path / ".env"
    monkeypatch.setattr(llm, "ENV_PATH", fake_env)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BACKEND", raising=False)
    monkeypatch.setattr(llm, "claude_cli_available", lambda: False)
    monkeypatch.setattr(llm, "codex_cli_available", lambda: False)
    monkeypatch.setattr(llm, "gemini_cli_available", lambda: False)
    yield fake_env


def test_not_configured_by_default(isolated_env):
    assert llm.is_configured() is False


def test_save_api_key_persists_to_env_file_and_process_env(isolated_env):
    llm.save_api_key("sk-ant-fake-123")
    assert llm.is_configured() is True
    assert os.environ["ANTHROPIC_API_KEY"] == "sk-ant-fake-123"
    assert "ANTHROPIC_API_KEY=sk-ant-fake-123" in isolated_env.read_text(encoding="utf-8")


def test_save_api_key_overwrites_previous_value(isolated_env):
    llm.save_api_key("sk-ant-old")
    llm.save_api_key("sk-ant-new")
    content = isolated_env.read_text(encoding="utf-8")
    assert content.count("ANTHROPIC_API_KEY=") == 1
    assert "sk-ant-new" in content
    assert "sk-ant-old" not in content


def test_save_empty_api_key_rejected(isolated_env):
    with pytest.raises(ValueError):
        llm.save_api_key("   ")


def test_clear_api_key_removes_from_file_and_env(isolated_env):
    llm.save_api_key("sk-ant-fake-123")
    llm.clear_api_key()
    assert llm.is_configured() is False
    assert "ANTHROPIC_API_KEY" not in isolated_env.read_text(encoding="utf-8")


def test_get_client_raises_when_not_configured(isolated_env):
    with pytest.raises(llm.LlmNotConfiguredError):
        llm.get_client()


def test_generate_text_raises_not_configured_without_key(isolated_env):
    with pytest.raises(llm.LlmNotConfiguredError):
        llm.generate_text(system="test", user_prompt="test")


# ---------------------------------------------------------------------------
# save_backend() — nay nhận 4 giá trị: api, claude_cli, codex_cli, gemini_cli
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mode", llm.BACKENDS)
def test_save_backend_accepts_every_valid_mode(isolated_env, mode):
    llm.save_backend(mode)
    assert llm.get_backend() == mode


def test_save_backend_rejects_unknown_mode(isolated_env):
    with pytest.raises(ValueError):
        llm.save_backend("chatgpt-nhung-khong-phai-the")


# ---------------------------------------------------------------------------
# 3 CLI (Claude/Codex/Gemini) — cùng 1 khuôn mẫu: kiểm tra có cài (shutil.which),
# gọi subprocess đọc prompt qua stdin, xử lý lỗi giống hệt nhau. Test riêng
# từng cái để chắc KHÔNG có cái nào bị copy-paste sai tên lệnh/timeout.
# ---------------------------------------------------------------------------

_CLI_CASES = [
    ("claude", "claude_cli_available", llm._generate_text_via_cli, "claude", ["claude", "-p"]),
    ("codex", "codex_cli_available", llm._generate_text_via_codex_cli, "codex", ["codex", "exec"]),
]


@pytest.mark.parametrize("cli_name, available_fn_name, generate_fn, which_name, expected_argv", _CLI_CASES)
def test_cli_available_checks_shutil_which(monkeypatch, cli_name, available_fn_name, generate_fn, which_name, expected_argv):
    monkeypatch.setattr(llm.shutil, "which", lambda name: "/usr/bin/x" if name == which_name else None)
    assert getattr(llm, available_fn_name)() is True
    monkeypatch.setattr(llm.shutil, "which", lambda name: None)
    assert getattr(llm, available_fn_name)() is False


@pytest.mark.parametrize("cli_name, available_fn_name, generate_fn, which_name, expected_argv", _CLI_CASES)
def test_cli_generate_raises_not_configured_when_missing(monkeypatch, cli_name, available_fn_name, generate_fn, which_name, expected_argv):
    monkeypatch.setattr(llm, available_fn_name, lambda: False)
    with pytest.raises(llm.LlmNotConfiguredError):
        generate_fn("system", "user")


@pytest.mark.parametrize("cli_name, available_fn_name, generate_fn, which_name, expected_argv", _CLI_CASES)
def test_cli_generate_success_passes_combined_prompt_via_stdin(monkeypatch, cli_name, available_fn_name, generate_fn, which_name, expected_argv):
    captured = {}

    def fake_run(argv, input, capture_output, text, encoding, timeout, shell):
        captured["argv"] = argv
        captured["input"] = input
        captured["shell"] = shell

        class FakeResult:
            returncode = 0
            stdout = "kết quả từ CLI"
            stderr = ""

        return FakeResult()

    monkeypatch.setattr(llm, available_fn_name, lambda: True)
    monkeypatch.setattr(llm.subprocess, "run", fake_run)

    result = generate_fn("system prompt", "user prompt")

    assert result == "kết quả từ CLI"
    assert captured["argv"] == expected_argv
    assert captured["shell"] is True
    assert "system prompt" in captured["input"]
    assert "user prompt" in captured["input"]


@pytest.mark.parametrize("cli_name, available_fn_name, generate_fn, which_name, expected_argv", _CLI_CASES)
def test_cli_generate_raises_cli_error_on_nonzero_exit(monkeypatch, cli_name, available_fn_name, generate_fn, which_name, expected_argv):
    def fake_run(*a, **k):
        class FakeResult:
            returncode = 1
            stdout = ""
            stderr = "lỗi đăng nhập"

        return FakeResult()

    monkeypatch.setattr(llm, available_fn_name, lambda: True)
    monkeypatch.setattr(llm.subprocess, "run", fake_run)
    with pytest.raises(llm.LlmCliError, match="lỗi đăng nhập"):
        generate_fn("system", "user")


@pytest.mark.parametrize("cli_name, available_fn_name, generate_fn, which_name, expected_argv", _CLI_CASES)
def test_cli_generate_raises_cli_error_on_empty_output(monkeypatch, cli_name, available_fn_name, generate_fn, which_name, expected_argv):
    def fake_run(*a, **k):
        class FakeResult:
            returncode = 0
            stdout = "   "
            stderr = ""

        return FakeResult()

    monkeypatch.setattr(llm, available_fn_name, lambda: True)
    monkeypatch.setattr(llm.subprocess, "run", fake_run)
    with pytest.raises(llm.LlmCliError, match="không trả về nội dung"):
        generate_fn("system", "user")


@pytest.mark.parametrize("cli_name, available_fn_name, generate_fn, which_name, expected_argv", _CLI_CASES)
def test_cli_generate_raises_cli_error_on_timeout(monkeypatch, cli_name, available_fn_name, generate_fn, which_name, expected_argv):
    import subprocess as subprocess_module

    def fake_run(*a, **k):
        raise subprocess_module.TimeoutExpired(cmd=expected_argv, timeout=180)

    monkeypatch.setattr(llm, available_fn_name, lambda: True)
    monkeypatch.setattr(llm.subprocess, "run", fake_run)
    with pytest.raises(llm.LlmCliError, match="quá"):
        generate_fn("system", "user")


# ---------------------------------------------------------------------------
# generate_text() — phải gọi ĐÚNG hàm sinh văn bản theo backend đang chọn
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "backend, patched_fn_name",
    [
        ("claude_cli", "_generate_text_via_cli"),
        ("codex_cli", "_generate_text_via_codex_cli"),
        ("gemini_cli", "_generate_text_via_gemini_cli"),
    ],
)
def test_generate_text_dispatches_to_correct_cli_backend(isolated_env, monkeypatch, backend, patched_fn_name):
    llm.save_backend(backend)
    called = {}

    def fake(system, user_prompt):
        called["system"] = system
        called["user_prompt"] = user_prompt
        return f"kết quả từ {backend}"

    monkeypatch.setattr(llm, patched_fn_name, fake)
    # _CLI_GENERATORS được lập từ tham chiếu hàm lúc import module — patch lại
    # dict để generate_text() thực sự gọi bản fake vừa gán ở trên.
    monkeypatch.setitem(llm._CLI_GENERATORS, backend, fake)

    result = llm.generate_text(system="hệ thống", user_prompt="người dùng")

    assert result == f"kết quả từ {backend}"
    assert called == {"system": "hệ thống", "user_prompt": "người dùng"}


@pytest.fixture()
def antigravity_run(monkeypatch):
    captured = {}
    result = SimpleNamespace(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(llm.shutil, "which", lambda name: "C:/CLI/agy.exe" if name == "agy" else None)

    def fake_run(argv, **kwargs):
        captured.update(argv=argv, **kwargs)
        return result

    monkeypatch.setattr(llm.subprocess, "run", fake_run)
    return captured, result


def test_gemini_availability_requires_antigravity(monkeypatch):
    monkeypatch.setattr(llm.shutil, "which", lambda name: "gemini.cmd" if name == "gemini" else None)
    assert llm.gemini_cli_available() is False
    with pytest.raises(llm.LlmNotConfiguredError, match="Antigravity CLI"):
        llm._generate_text_via_gemini_cli("system", "user")
    monkeypatch.setattr(llm.shutil, "which", lambda name: "agy.exe" if name == "agy" else None)
    assert llm.gemini_cli_available() is True


def test_antigravity_long_unicode_prompt_and_final_response(antigravity_run):
    captured, result = antigravity_run
    prompt = 'Truyện tiếng Việt "& %PATH% | < >"\n' * 3000
    result.stdout = "\n".join(json.dumps(event) for event in [
        {"event": "init", "init": {}},
        {"event": "step_update", "step_update": {"text_delta": "nội dung dở dang"}},
        {"event": "result", "result": {"status": "SUCCESS", "response": "  Kết quả cuối cùng\n"}},
    ])
    assert llm._generate_text_via_gemini_cli("system", prompt) == "Kết quả cuối cùng"
    assert captured["argv"] == [
        "C:/CLI/agy.exe", "--input-format", "stream-json", "--output-format", "stream-json",
        "--model", "gemini-3.1-pro-high",
        "--disable-slash-commands", "--print-timeout", "180s",
    ]
    assert captured["shell"] is False
    assert captured["cwd"] == llm.ENV_PATH.parent
    assert captured["encoding"] == "utf-8"
    assert captured["timeout"] == llm.GEMINI_CLI_TIMEOUT_SECONDS
    assert len(captured["input"].splitlines()) == 1
    assert captured["input"].endswith("\n")
    assert json.loads(captured["input"]) == {
        "event": "user", "message": {"content": f"system\n\n---\n\n{prompt}"},
    }


@pytest.mark.parametrize("stdout, expected", [
    ("", "không trả về sự kiện result"),
    ('{"event":"step_update"}', "không trả về sự kiện result"),
    ("invalid json", "stream-json không hợp lệ"),
    ("[]", "stream-json không hợp lệ"),
    ('{"event":"result","result":null}', "stream-json không hợp lệ"),
    ('{"event":"result","result":{"status":"SUCCESS","response":null}}', "stream-json không hợp lệ"),
    ('{"event":"result","result":{"status":"SUCCESS","response":"  "}}', "không trả về nội dung"),
    ('{"event":"result","result":{"status":"ERROR","error":"quota exceeded"}}', "quota exceeded"),
    ('{"event":"result","result":{"status":"WAITING","response":"partial"}}', "chưa hoàn tất"),
])
def test_antigravity_rejects_incomplete_or_invalid_result(antigravity_run, stdout, expected):
    captured, result = antigravity_run
    result.stdout = stdout
    with pytest.raises(llm.LlmCliError, match=expected):
        llm._generate_text_via_gemini_cli("system", "user")


def test_antigravity_rejects_multiple_results(antigravity_run):
    captured, result = antigravity_run
    event = json.dumps({"event": "result", "result": {"status": "SUCCESS", "response": "answer"}})
    result.stdout = event + "\n" + event
    with pytest.raises(llm.LlmCliError, match="nhiều kết quả"):
        llm._generate_text_via_gemini_cli("system", "user")


def test_antigravity_auth_error_does_not_fall_back_to_api(isolated_env, antigravity_run, monkeypatch):
    captured, result = antigravity_run
    result.returncode = 1
    result.stderr = "authentication required"
    llm.save_backend("gemini_cli")

    def unexpected_api(*args, **kwargs):
        pytest.fail("Must not fall back to a paid API")

    monkeypatch.setattr(llm, "_generate_text_via_api", unexpected_api)
    with pytest.raises(llm.LlmCliError, match="authentication required") as error:
        llm.generate_text("system", "user")
    assert "chạy 'agy'" in str(error.value)
    assert llm.get_backend() == "gemini_cli"


@pytest.mark.parametrize("exception, expected", [
    (subprocess.TimeoutExpired("agy", 180), "quá 180s"),
    (FileNotFoundError("agy.exe missing"), "Không chạy được Antigravity CLI"),
])
def test_antigravity_process_errors(antigravity_run, monkeypatch, exception, expected):
    def fail_run(*args, **kwargs):
        raise exception

    monkeypatch.setattr(llm.subprocess, "run", fail_run)
    with pytest.raises(llm.LlmCliError, match=expected):
        llm._generate_text_via_gemini_cli("system", "user")


def test_generate_text_dispatches_to_api_by_default(isolated_env, monkeypatch):
    called = {}

    def fake_api(system, user_prompt, max_tokens, effort):
        called["args"] = (system, user_prompt, max_tokens, effort)
        return "kết quả từ API"

    monkeypatch.setattr(llm, "_generate_text_via_api", fake_api)
    result = llm.generate_text(system="s", user_prompt="u", max_tokens=999, effort="low")

    assert result == "kết quả từ API"
    assert called["args"] == ("s", "u", 999, "low")


# ---------------------------------------------------------------------------
# is_configured() — phải phản ánh đúng trạng thái CLI theo backend đang chọn
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "backend, available_fn_name",
    [("claude_cli", "claude_cli_available"), ("codex_cli", "codex_cli_available"), ("gemini_cli", "gemini_cli_available")],
)
def test_is_configured_reflects_cli_availability(isolated_env, monkeypatch, backend, available_fn_name):
    llm.save_backend(backend)
    monkeypatch.setattr(llm, available_fn_name, lambda: True)
    assert llm.is_configured() is True
    monkeypatch.setattr(llm, available_fn_name, lambda: False)
    assert llm.is_configured() is False


# ---------------------------------------------------------------------------
# generate_json(raise_on_error=...) — Skill/lỗi thật 2026-09-15: storyboard
# sinh prompt cảnh KHÔNG được nuốt lỗi im lặng như các chỗ gọi JSON khác
# (SFX/theme/hook), vì thiếu prompt = không thể tạo được cảnh đó, không phải
# 1 gợi ý phụ có cũng được không có cũng được.
# ---------------------------------------------------------------------------

def test_generate_json_default_behavior_still_swallows_errors(monkeypatch):
    """Hành vi MẶC ĐỊNH (raise_on_error=False, dùng cho SFX/theme/hook...)
    phải giữ nguyên như trước — không được đổi hành vi của các chỗ gọi khác."""
    def boom(*a, **k):
        raise llm.LlmCliError("phiên CLI bị gián đoạn")

    monkeypatch.setattr(llm, "generate_text", boom)
    result = llm.generate_json("sys", "user", "===A===", "===B===", default={"fallback": True})
    assert result == {"fallback": True}


def test_generate_json_raise_on_error_propagates_llm_error(monkeypatch):
    def boom(*a, **k):
        raise llm.LlmCliError("phiên CLI bị gián đoạn")

    monkeypatch.setattr(llm, "generate_text", boom)
    with pytest.raises(llm.LlmCliError):
        llm.generate_json("sys", "user", "===A===", "===B===", raise_on_error=True)


def test_generate_json_raise_on_error_wraps_parse_failure(monkeypatch):
    """Khi LLM trả về nhưng không tách/parse được JSON hợp lệ (không phải
    lỗi gọi LLM) -> bọc thành LlmJsonParseError riêng biệt để phân loại đúng
    (khác lỗi cấu hình/từ chối/CLI)."""
    monkeypatch.setattr(llm, "generate_text", lambda *a, **k: "không có markers hợp lệ ở đây")
    with pytest.raises(llm.LlmJsonParseError):
        llm.generate_json("sys", "user", "===A===", "===B===", raise_on_error=True)


def test_generate_json_raise_on_error_succeeds_normally_when_valid(monkeypatch):
    monkeypatch.setattr(llm, "generate_text", lambda *a, **k: '===A===\n{"ok": true}\n===B===')
    result = llm.generate_json("sys", "user", "===A===", "===B===", raise_on_error=True)
    assert result == {"ok": True}
