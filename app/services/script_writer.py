"""Bước 1-4 (Mục 3, V3): viết lại câu chuyện đầy đủ, rồi viết kịch bản theo
đúng thời lượng người dùng chọn.

Video dài (16:9): cấu trúc Hook → Vấn đề → Bối cảnh → Giải pháp → Hướng dẫn
    → Ví dụ → Kết quả → CTA, chia theo timestamp.
Video ngắn (9:16, dạng short): rút gọn còn Hook → Nội dung chính → CTA.

Các hàm ở đây chỉ lắp ráp system/user prompt rồi gọi app.services.llm —
không tự gọi API trực tiếp (đúng skill claude-api: luôn qua SDK, không hand-roll).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services import llm

LONG_STRUCTURE = ["Hook", "Vấn đề", "Bối cảnh", "Giải pháp", "Hướng dẫn", "Ví dụ", "Kết quả", "CTA"]
SHORT_STRUCTURE = ["Hook", "Nội dung chính", "CTA"]

# Skill 11 (narration-length-budget, 2026-09-15): tốc độ đọc tự nhiên trung
# bình dùng để tính ngân sách từ cho lời đọc — khớp với hệ số đã dùng sẵn ở
# _estimate_max_tokens() bên dưới (150 từ/phút), để 2 nơi không lệch nhau.
NARRATION_WORDS_PER_MINUTE = 150
# Dư ra 12.5% (giữa khoảng 10-15% người dùng yêu cầu) làm khoảng lặng cho
# hiệu ứng âm thanh nền/hành động không lời chen vào — đúng tinh thần skill
# narration-scene-alignment: không phải cảnh nào cũng cần lời.
NARRATION_SILENCE_MARGIN = 0.125
# Vượt ngân sách bao nhiêu % mới thật sự coi là "quá dài" và cảnh báo người
# dùng — LLM không đếm từ chính xác tuyệt đối, vượt nhẹ vài % là bình
# thường, không nên báo động vặt.
NARRATION_OVER_BUDGET_TOLERANCE = 1.15

_TIMESTAMP_ONLY_RE = re.compile(r"\[\d{1,3}:\d{2}\s*-\s*\d{1,3}:\d{2}\]")


def target_narration_word_count(duration_minutes: int | None, duration_seconds: int | None) -> int:
    """Skill 11: số từ TỐI ĐA nên có trong toàn bộ lời đọc để khi đọc ở tốc
    độ tự nhiên (~150 từ/phút) không dài hơn thời lượng video mục tiêu, mà
    còn dư ra ~12.5% làm khoảng lặng cho hiệu ứng âm thanh nền chen vào."""
    total_seconds = duration_seconds if duration_seconds is not None else (duration_minutes or 0) * 60
    words_per_second = NARRATION_WORDS_PER_MINUTE / 60
    return max(1, round(total_seconds * words_per_second * (1 - NARRATION_SILENCE_MARGIN)))


def count_narration_words(script_text: str) -> int:
    """Đếm số từ PHẦN LỜI ĐỌC thật sự — bỏ các mốc timestamp [MM:SS-MM:SS]
    trước khi đếm. Dùng để kiểm tra ngược kịch bản Claude vừa viết có vượt
    ngân sách từ hay không (xem generate_script(), Skill 11)."""
    text_only = _TIMESTAMP_ONLY_RE.sub(" ", script_text)
    return len(re.findall(r"\S+", text_only))


@dataclass
class ScriptResult:
    """Kết quả Bước 5 kèm số liệu kiểm tra ngân sách từ (Skill 11) — cho
    phép giao diện cảnh báo NGAY nếu Claude lỡ viết dài hơn dự kiến, thay vì
    chỉ phát hiện lúc lồng giọng đọc thật (quá muộn, đã tốn công dựng cảnh)."""
    text: str
    target_word_count: int
    actual_word_count: int
    over_budget: bool

HOOK_GROUPS = {
    "to_mo": "Tò mò",
    "bat_ngo": "Bất ngờ",
    "noi_dau": "Đánh vào nỗi đau",
    "loi_ich": "Lợi ích rõ ràng",
    "cach_lam_moi": "Cách làm mới",
}


def rewrite_story(idea_or_story: str, effort: str = "high") -> str:
    """Bước 1: viết lại ý tưởng/câu chuyện gốc (có thể còn sơ sài) thành 1
    câu chuyện đầy đủ, mạch lạc — làm nền cho Bước 2-4."""
    system = (
        "Bạn là biên kịch chuyên viết lại ý tưởng thô thành câu chuyện đầy đủ, "
        "mạch lạc, có mở đầu - diễn biến - cao trào - kết thúc rõ ràng. "
        "Giữ đúng tinh thần và các chi tiết cốt lõi người dùng đã cho, chỉ bổ sung "
        "mạch truyện và chi tiết cho liền lạc, không bịa thêm nhân vật/tình tiết "
        "trái với ý gốc."
    )
    prompt = f"Ý tưởng hoặc câu chuyện gốc:\n\n{idea_or_story}\n\nViết lại thành 1 câu chuyện đầy đủ."
    return llm.generate_text(system=system, user_prompt=prompt, max_tokens=8000, effort=effort)


@dataclass
class ThemeAndGoals:
    target_audience: str = ""
    audience_pain_point: str = ""
    core_message: str = ""
    best_angle: str = ""


def determine_theme_and_goals(story: str, effort: str = "medium") -> ThemeAndGoals:
    """Bước 3: xác định đối tượng xem, vấn đề họ quan tâm, thông điệp chính,
    và góc triển khai hấp dẫn nhất — làm căn cứ cho Bước 4 (hook) và Bước 5
    (kịch bản) bám sát đúng mục tiêu, không viết chung chung."""
    system = (
        "Bạn là chiến lược gia nội dung video. Đọc câu chuyện sau và xác định "
        "rõ 4 điều: đối tượng xem cụ thể là ai, vấn đề/điều họ đang quan tâm "
        "liên quan tới câu chuyện này là gì, thông điệp chính video muốn "
        "truyền tải là gì, và góc triển khai nào sẽ khiến video này hấp dẫn "
        "nhất so với cách kể chuyện thông thường. Trả lời ngắn gọn, cụ thể, "
        "mỗi mục 1-2 câu.\n\n"
        "QUAN TRỌNG VỀ ĐỊNH DẠNG: chỉ trả về đúng 1 khối JSON bọc giữa 2 dòng "
        "đánh dấu:\n===THEME_BAT_DAU===\n"
        '{"target_audience": "...", "audience_pain_point": "...", '
        '"core_message": "...", "best_angle": "..."}\n===THEME_KET_THUC==='
    )
    data = llm.generate_json(
        system, f"Câu chuyện:\n\n{story}",
        "===THEME_BAT_DAU===", "===THEME_KET_THUC===",
        max_tokens=1000, effort=effort, default={},
    )
    return ThemeAndGoals(
        target_audience=str(data.get("target_audience", "")).strip(),
        audience_pain_point=str(data.get("audience_pain_point", "")).strip(),
        core_message=str(data.get("core_message", "")).strip(),
        best_angle=str(data.get("best_angle", "")).strip(),
    )


@dataclass
class HookCandidate:
    group: str
    text: str


@dataclass
class HookResult:
    candidates: list[HookCandidate] = field(default_factory=list)
    top_3: list[str] = field(default_factory=list)


def generate_hooks(story: str, theme: ThemeAndGoals | None = None, effort: str = "medium") -> HookResult:
    """Bước 4: tạo 20 câu hook mở đầu chia 5 nhóm (4 câu/nhóm: tò mò/bất
    ngờ/đánh vào nỗi đau/lợi ích rõ/cách làm mới), rồi tự chấm chọn ra 3 câu
    mạnh nhất. Nếu đã có kết quả Bước 3, hook phải bám đúng đối tượng/thông
    điệp/góc triển khai đã xác định — không viết hook chung chung."""
    theme_context = ""
    if theme is not None and any([theme.target_audience, theme.core_message, theme.best_angle]):
        theme_context = (
            f"\n\nBối cảnh Bước 3 đã xác định — đối tượng xem: {theme.target_audience}; "
            f"thông điệp chính: {theme.core_message}; góc triển khai: {theme.best_angle}. "
            "Viết hook bám sát đúng đối tượng/thông điệp/góc triển khai này."
        )
    group_keys = ", ".join(f'"{k}"' for k in HOOK_GROUPS)
    group_names = ", ".join(HOOK_GROUPS.values())
    system = (
        "Bạn là biên kịch chuyên viết hook mở đầu video gây chú ý ngay trong "
        "3 giây đầu. Viết ĐÚNG 20 câu hook mở đầu cho câu chuyện sau, chia "
        f"đều 5 nhóm (4 câu/nhóm): {group_names}. Sau đó tự chấm chọn ra 3 "
        "câu MẠNH NHẤT trong số 20 câu vừa viết.\n\n"
        "QUAN TRỌNG VỀ ĐỊNH DẠNG: chỉ trả về đúng 1 khối JSON bọc giữa 2 dòng "
        "đánh dấu:\n===HOOKS_BAT_DAU===\n"
        '{"candidates": [{"group": "to_mo", "text": "..."}, ...], '
        '"top_3": ["...", "...", "..."]}\n===HOOKS_KET_THUC===\n'
        f"`group` của mỗi câu PHẢI là đúng 1 trong: {group_keys}."
    )
    user_prompt = f"Câu chuyện:\n\n{story}{theme_context}"
    data = llm.generate_json(
        system, user_prompt,
        "===HOOKS_BAT_DAU===", "===HOOKS_KET_THUC===",
        max_tokens=2500, effort=effort, default={},
    )
    candidates = [
        HookCandidate(group=str(c.get("group", "")), text=str(c.get("text", "")).strip())
        for c in data.get("candidates", [])
        if isinstance(c, dict) and str(c.get("text", "")).strip()
    ]
    top_3 = [str(t).strip() for t in data.get("top_3", []) if str(t).strip()]
    return HookResult(candidates=candidates, top_3=top_3)


def suggest_characters(story: str, max_characters: int = 10, effort: str = "medium") -> list[dict]:
    """Bước 1: gợi ý danh sách nhân vật chính từ câu chuyện đã có cho Sổ Tay
    Nhân Vật (character_bible.py), mỗi nhân vật kèm mô tả cố định (tuổi,
    ngoại hình, khuôn mặt, tóc, trang phục, vật dụng đặc trưng) — CHỈ gợi ý
    để người dùng xem lại/sửa trên giao diện trước khi dùng, không tự động
    ghi thẳng vào dự án (giữ đúng nguyên tắc "App tự quyết còn người dùng
    xác nhận lại" đã áp dụng ở Bước 3/4)."""
    system = (
        "Bạn là biên kịch phụ trách Sổ Tay Nhân Vật (Character Bible) cho video. "
        f"Đọc câu chuyện sau, xác định tối đa {max_characters} nhân vật CHÍNH (bỏ "
        "qua nhân vật phụ/quần chúng không quan trọng tới mạch truyện), mỗi nhân "
        "vật viết 1 mô tả cố định gồm: tuổi, ngoại hình, khuôn mặt, tóc, trang "
        "phục, vật dụng đặc trưng — đủ chi tiết cụ thể để AI vẽ ra đúng cùng 1 "
        "người ở mọi cảnh khác nhau trong phim, không mô tả chung chung.\n\n"
        "QUAN TRỌNG VỀ ĐỊNH DẠNG: chỉ trả về đúng 1 mảng JSON bọc giữa 2 dòng "
        "đánh dấu:\n===CHARACTERS_BAT_DAU===\n"
        '[{"name": "...", "description": "..."}, ...]\n===CHARACTERS_KET_THUC==='
    )
    data = llm.generate_json(
        system, f"Câu chuyện:\n\n{story}",
        "===CHARACTERS_BAT_DAU===", "===CHARACTERS_KET_THUC===",
        max_tokens=2000, effort=effort, default=[],
    )
    if not isinstance(data, list):
        return []
    result = []
    for item in data[:max_characters]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        description = str(item.get("description", "")).strip()
        if name and description:
            result.append({"name": name, "description": description})
    return result


def _estimate_max_tokens(duration_minutes: int | None, duration_seconds: int | None) -> int:
    """Ước lượng token cần cho kịch bản, dựa trên tốc độ đọc trung bình
    ~150 từ/phút; luôn có sàn 16000 để đủ chỗ cho cấu trúc + timestamp."""
    total_seconds = duration_seconds if duration_seconds is not None else (duration_minutes or 0) * 60
    words_estimate = (total_seconds / 60) * 150
    tokens_estimate = int(words_estimate * 2.2) + 2000  # hệ số từ -> token dư dả cho tiếng Việt/Anh
    return max(6000, tokens_estimate)


def generate_script(
    story: str,
    is_long_format: bool,
    duration_minutes: int | None,
    duration_seconds: int | None,
    language_name: str = "Tiếng Việt",
    effort: str = "high",
    theme: ThemeAndGoals | None = None,
    chosen_hook: str | None = None,
) -> ScriptResult:
    """Bước 2-5: viết kịch bản đầy đủ theo đúng thời lượng đã chọn, chia theo
    timestamp, bằng đúng ngôn ngữ giọng đọc (language_name). `theme` (Bước 3)
    và `chosen_hook` (Bước 4) là tuỳ chọn — có thì kịch bản PHẢI bám sát, để
    2 bước đó không chỉ hiển thị cho có mà thực sự ảnh hưởng nội dung.

    Skill 11 (narration-length-budget, 2026-09-15): kịch bản trả về CHỈ được
    là lời đọc thuần tuý (không mô tả hình ảnh/chỉ dẫn quay phim dưới bất kỳ
    hình thức nào — việc đó thuộc Bước 6-7 storyboard, xem
    generate_scene_prompts() vốn đã tự suy ra hình ảnh từ CHÍNH văn bản lời
    đọc, không cần lời đọc mô tả sẵn hình ảnh), và tổng độ dài phải vừa khít
    thời lượng video mục tiêu ở tốc độ đọc tự nhiên, dư ra 10-15% làm khoảng
    lặng cho hiệu ứng âm thanh nền."""
    structure = LONG_STRUCTURE if is_long_format else SHORT_STRUCTURE
    duration_desc = f"{duration_minutes} phút" if is_long_format else f"{duration_seconds} giây"
    structure_desc = " → ".join(structure)
    target_words = target_narration_word_count(duration_minutes, duration_seconds)

    theme_instruction = ""
    if theme is not None and any([theme.target_audience, theme.core_message, theme.best_angle]):
        theme_instruction = (
            f" Bám sát đúng đối tượng xem: {theme.target_audience}; nhấn mạnh "
            f"thông điệp chính: {theme.core_message}; triển khai theo góc: {theme.best_angle}."
        )
    hook_instruction = ""
    if chosen_hook:
        hook_instruction = (
            f' Câu ĐẦU TIÊN của phần Hook mở đầu PHẢI giữ NGUYÊN VĂN: "{chosen_hook}" '
            "(có thể viết thêm 1-2 câu ngay sau để dẫn dắt tiếp, nhưng câu mở đầu này "
            "không được đổi khác)."
        )

    system = (
        "Bạn là biên kịch video chuyên nghiệp. Viết kịch bản lời thoại/giọng đọc "
        f"đầy đủ theo đúng cấu trúc: {structure_desc}. Chia kịch bản theo timestamp "
        "(ví dụ [00:00-00:15]) khớp với thời lượng mục tiêu. Viết bằng "
        f"{language_name}.\n\n"
        "QUAN TRỌNG VỀ NỘI DUNG (Skill 11): mỗi dòng ngay sau timestamp CHỈ được "
        "là LỜI ĐỌC THẬT SỰ (voice-over) — TUYỆT ĐỐI KHÔNG được viết mô tả hình "
        "ảnh, hành động quay phim, góc máy, hay bất kỳ chỉ dẫn sản xuất nào dưới "
        "bất kỳ hình thức nào (không dùng dấu ngoặc đơn, không dùng dấu *, không "
        "viết kiểu \"(Hình ảnh: ...)\" hay tương tự). Toàn bộ hệ thống đưa THẲNG "
        "văn bản sau mỗi timestamp vào máy đọc giọng nói (TTS), nên bất kỳ chữ "
        "nào không phải lời thoại thật sẽ bị ĐỌC TO RA TIẾNG (lỗi thật đã gặp: cả "
        "tên đoạn 'Hook' lẫn mô tả '(Hình ảnh: ...)' từng bị đọc to nếu lẫn vào). "
        "Mô tả hình ảnh cho từng cảnh là việc của bước sau (storyboard), tự suy "
        "ra được từ chính lời đọc, không cần kịch bản này viết sẵn.\n\n"
        "QUAN TRỌNG VỀ ĐỘ DÀI (Skill 11): tổng số từ TOÀN BỘ phần lời đọc KHÔNG "
        f"ĐƯỢC VƯỢT QUÁ khoảng {target_words} từ. Ngân sách này đã tính sẵn tốc độ "
        "đọc tự nhiên ~150 từ/phút và CHỪA SẴN khoảng 10-15% thời lượng làm "
        "khoảng lặng cho hiệu ứng âm thanh nền/hình ảnh hành động — không phải "
        "đoạn nào cũng cần nói liên tục, đặc biệt đoạn cao trào/hành động nên để "
        "hình ảnh và âm thanh tự kể chuyện, lời đọc thưa hơn. Viết dài hơn ngân "
        "sách này, khi lồng giọng đọc thật sẽ dài hơn cả video đã dựng, khiến "
        "hình ảnh phải đứng hình/lặp lại chờ trong lúc lời đọc vẫn tiếp tục, làm "
        "mất nhịp điện ảnh.\n\n"
        "QUAN TRỌNG VỀ ĐỊNH DẠNG: mỗi dòng timestamp CHỈ chứa đúng cụm "
        "[MM:SS-MM:SS], KHÔNG được viết thêm tên đoạn (Hook, Vấn đề...) hay bất "
        "kỳ chữ nào khác ngay sau cụm timestamp đó hoặc ở đầu dòng lời thoại."
        f"{theme_instruction}{hook_instruction}"
    )
    prompt = (
        f"Câu chuyện làm nền:\n\n{story}\n\n"
        f"Thời lượng mục tiêu: {duration_desc}.\n"
        f"Viết kịch bản đầy đủ theo cấu trúc {structure_desc}, chia timestamp khớp "
        f"{duration_desc}, tổng lời đọc không vượt quá {target_words} từ."
    )
    max_tokens = _estimate_max_tokens(duration_minutes, duration_seconds)
    text = llm.generate_text(system=system, user_prompt=prompt, max_tokens=max_tokens, effort=effort)
    actual_words = count_narration_words(text)
    return ScriptResult(
        text=text,
        target_word_count=target_words,
        actual_word_count=actual_words,
        over_budget=actual_words > target_words * NARRATION_OVER_BUDGET_TOLERANCE,
    )
