"""Đối chiếu 3 khối dịch thật (vi/en/ru) trong app/static/i18n.js — xác nhận
KHÔNG có chữ nào bị quên chưa dịch ở 1 trong 3 ngôn ngữ (key có ở ngôn ngữ
này nhưng thiếu ở ngôn ngữ khác). README từng ghi "vẫn CHƯA kiểm tra kỹ mức
độ hoàn thiện" — test này thay cho việc dò tay, tự động chạy lại mỗi khi có
người thêm/sửa chữ trong app.

Không dùng Node/trình duyệt thật — chỉ đọc file .js bằng regex, vì cấu trúc
3 khối `vi: {...}`, `en: {...}`, `ru: {...}` hiện tại chỉ gồm các dòng
`key: "chuỗi ký tự"` phẳng (không object/mảng lồng nhau, không dùng nháy đơn
hay template literal — xem docstring đầu file i18n.js)."""
from __future__ import annotations

import re
from pathlib import Path

I18N_PATH = Path(__file__).resolve().parent.parent / "app" / "static" / "i18n.js"
LANGUAGES = ("vi", "en", "ru")

# 1 dòng "key: "giá trị có thể chứa \" đã escape""" — không khớp xuống dòng khác.
_KEY_VALUE_RE = re.compile(r'^\s*(\w+):\s*"(?:[^"\\]|\\.)*",?\s*$', re.MULTILINE)


def _extract_top_level_block(text: str, start_marker: str) -> str:
    """Trả về nội dung bên trong dấu { } đầu tiên ngay sau `start_marker`,
    đếm độ sâu ngoặc để lấy đúng khối (không bị cắt sớm bởi dấu } lồng bên
    trong, dù hiện tại các khối ngôn ngữ không có ngoặc lồng)."""
    start = text.index(start_marker) + len(start_marker)
    brace_start = text.index("{", start)
    depth = 0
    for i in range(brace_start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[brace_start + 1 : i]
    raise ValueError(f"Không tìm thấy dấu }} đóng khối cho '{start_marker}'")


def _keys_in_block(block_text: str) -> list[str]:
    return _KEY_VALUE_RE.findall(block_text)


def _load_language_keys() -> dict[str, list[str]]:
    text = I18N_PATH.read_text(encoding="utf-8")
    translations_block = _extract_top_level_block(text, "const TRANSLATIONS = ")
    return {
        lang: _keys_in_block(_extract_top_level_block(translations_block, f"{lang}: "))
        for lang in LANGUAGES
    }


def test_i18n_file_has_exactly_the_3_ready_languages():
    text = I18N_PATH.read_text(encoding="utf-8")
    translations_block = _extract_top_level_block(text, "const TRANSLATIONS = ")
    for lang in LANGUAGES:
        assert f"{lang}: " in translations_block, f"Thiếu hẳn khối ngôn ngữ '{lang}' trong TRANSLATIONS"


def test_no_missing_translation_keys_across_vi_en_ru():
    keys_by_lang = _load_language_keys()
    for lang, keys in keys_by_lang.items():
        assert keys, f"Khối '{lang}' đọc ra 0 key — có thể regex sai hoặc file bị đổi cấu trúc"

    all_keys = set().union(*keys_by_lang.values())
    missing_report = {}
    for lang, keys in keys_by_lang.items():
        missing = sorted(all_keys - set(keys))
        if missing:
            missing_report[lang] = missing

    assert not missing_report, (
        "Có chữ dùng ở ngôn ngữ này nhưng THIẾU bản dịch ở ngôn ngữ khác:\n"
        + "\n".join(f"  - thiếu ở '{lang}': {keys}" for lang, keys in missing_report.items())
    )


def test_no_duplicate_keys_within_each_language():
    """Key bị khai báo 2 lần trong CÙNG 1 khối ngôn ngữ: JS không báo lỗi, chỉ
    âm thầm lấy giá trị khai báo SAU CÙNG — dễ khiến 1 bản dịch bị đè mất mà
    không ai để ý, nên coi là 1 dạng "thiếu bản dịch" cần bắt riêng."""
    keys_by_lang = _load_language_keys()
    dup_report = {}
    for lang, keys in keys_by_lang.items():
        seen = set()
        dups = set()
        for k in keys:
            if k in seen:
                dups.add(k)
            seen.add(k)
        if dups:
            dup_report[lang] = sorted(dups)

    assert not dup_report, (
        "Có key bị khai báo trùng lặp trong cùng 1 khối ngôn ngữ (bản dịch sau đè mất bản trước):\n"
        + "\n".join(f"  - trùng ở '{lang}': {keys}" for lang, keys in dup_report.items())
    )
