"""Agent "lập thực đơn tháng" (KH App new AI-make-short-automation.docx,
Nhánh 2 automation, Bước 1c): nhận 1 câu chiến lược (VD "3 video 24s/ngày
x 3 quầy x 30 ngày = 90 video") + danh sách quầy hàng (TikTok/Facebook/
YouTube...) rồi tự chia ra thành 1 LỊCH cụ thể: mỗi video ngày mấy, đăng
quầy nào, giờ nào, chủ đề gì.

Bếp hiện tại (app/services/script_writer.py) chỉ biết viết 1 kịch bản cho
1 video — KHÔNG biết cách chia 1 chiến lược lớn ra N video theo lịch.
Module này lấp đúng lỗ hổng đó (Mục 03 phiếu đánh giá), tách làm 2 việc RÕ
RÀNG khác nhau — KHÔNG giao cả 2 cho LLM cùng lúc:

1. build_schedule_grid() — THUẦN PYTHON, không qua LLM: chia N video vào
   đúng ngày/quầy/giờ theo round-robin. Lịch/giờ/quầy là TOÁN đơn giản,
   giao LLM tính dễ sai số (lệch ngày, đếm nhầm tổng) không cần thiết.
2. generate_topics() — GIAO LLM: chỉ sinh chủ đề/góc triển khai/hook cho
   từng ô lịch đã có sẵn, theo đúng 1 chiến lược chung — LLM không cần lo
   phần lịch, chỉ lo sáng tạo nội dung (đúng việc LLM làm tốt)."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.services import llm

# Cùng bộ khoá nền tảng với app/services/quality_review.py (PLATFORM_NAMES)
# — dùng chung 1 tên gọi cho 1 nền tảng xuyên suốt cả app.
# Giờ vàng mặc định (giờ Việt Nam, UTC+7) theo khảo sát phổ biến từng nền
# tảng — người dùng ghi đè qua tham số `golden_hours` nếu có số liệu riêng
# của kênh mình (VD từ Insight thật).
DEFAULT_GOLDEN_HOURS = {
    "youtube": "20:00",
    "tiktok": "19:00",
    "facebook_instagram": "20:30",
    "threads": "12:00",
    "twitter_x": "13:00",
    "zalo": "08:00",
}

# Chặn 1 chiến lược phi thực tế (VD gõ nhầm số 0, hoặc thật sự muốn hàng
# nghìn video/lần) khiến 1 lần gọi LLM sinh chủ đề quá tải/vượt ngân sách
# token — chia nhỏ chiến lược ra nhiều lần lập lịch hơn thay vì 1 lần khổng lồ.
MAX_CALENDAR_VIDEOS = 500


@dataclass
class ScheduleSlot:
    day: int  # 1-based: 1..days
    platform: str
    publish_time: str  # "HH:MM"
    duration_seconds: int
    topic: str = ""
    angle: str = ""
    hook_idea: str = ""


@dataclass
class ContentCalendar:
    slots: list[ScheduleSlot] = field(default_factory=list)
    total_videos: int = 0
    strategy_summary: str = ""


def build_schedule_grid(
    platforms: list[str],
    videos_per_day: int,
    days: int,
    duration_seconds: int,
    golden_hours: dict[str, str] | None = None,
) -> list[ScheduleSlot]:
    """Chia `videos_per_day` video MỖI NGÀY, trong `days` ngày, xoay vòng
    (round-robin) qua danh sách `platforms` — ngày nào cũng đăng đủ
    `videos_per_day` video, rải đều qua các quầy đã chọn. Ví dụ đúng câu
    chiến lược mẫu trong KH App new: 3 video/ngày x 3 quầy (TikTok/FB/
    YouTube) x 30 ngày = đúng 90 video, mỗi quầy nhận đúng 1 video/ngày.

    TOÁN THUẦN, không qua LLM — không bao giờ tính sai số lượng/lịch."""
    if not platforms:
        raise ValueError("Cần chọn ít nhất 1 quầy hàng (nền tảng) để đăng.")
    if videos_per_day < 1:
        raise ValueError("videos_per_day phải >= 1")
    if days < 1:
        raise ValueError("days phải >= 1")
    total = videos_per_day * days
    if total > MAX_CALENDAR_VIDEOS:
        raise ValueError(
            f"Tổng {total} video vượt giới hạn {MAX_CALENDAR_VIDEOS} video/lần lập lịch — "
            "chia nhỏ chiến lược ra nhiều lần lập lịch hơn."
        )

    hours = {**DEFAULT_GOLDEN_HOURS, **(golden_hours or {})}
    slots: list[ScheduleSlot] = []
    for day in range(1, days + 1):
        for i in range(videos_per_day):
            platform = platforms[i % len(platforms)]
            slots.append(ScheduleSlot(
                day=day,
                platform=platform,
                publish_time=hours.get(platform, "20:00"),
                duration_seconds=duration_seconds,
            ))
    return slots


def _slot_summary_lines(slots: list[ScheduleSlot]) -> str:
    return "\n".join(
        f"{i + 1}. Ngày {s.day} - quầy {s.platform} - {s.publish_time} - {s.duration_seconds}s"
        for i, s in enumerate(slots)
    )


def _estimate_topics_max_tokens(count: int) -> int:
    """Mỗi chủ đề ước lượng ~80 token (topic+angle+hook ngắn) + đệm — cho
    lịch lớn (VD 90 video) cần ngân sách token đủ lớn để LLM không bị cắt
    giữa mảng JSON (tránh lỗi parse vì JSON dở dang giữa đường)."""
    return min(32000, max(2000, count * 80 + 1000))


_TOPICS_SYSTEM_PROMPT_TEMPLATE = """Bạn là chiến lược gia nội dung video ngắn, phụ trách lập Ý TƯỞNG/chủ đề cho
1 LỊCH ĐĂNG đã có sẵn ngày/quầy/giờ (không cần bạn lo phần lịch) — chỉ cần
điền ĐÚNG {count} chủ đề, mỗi chủ đề gồm 3 phần: "topic" (chủ đề video),
"angle" (góc triển khai/khác biệt so với các video khác trong lịch, tránh
lặp ý giữa các video), "hook_idea" (1 câu hook mở đầu).

Chiến lược chung (do người dùng cung cấp):
{strategy}
{reference_block}
Bám ĐÚNG chiến lược trên. {count} chủ đề PHẢI khác nhau, không lặp ý,
không đánh số lại từ đầu giữa các ngày — coi như 1 kênh thật đang lên kế
hoạch nội dung liền mạch cho cả giai đoạn.

QUAN TRỌNG VỀ ĐỊNH DẠNG: trả lời CHỈ 1 mảng JSON có ĐÚNG {count} phần tử
theo thứ tự tương ứng lịch đã cho, bọc giữa 2 dòng đánh dấu:
===CALENDAR_BAT_DAU===
[{{"topic": "...", "angle": "...", "hook_idea": "..."}}, ...]
===CALENDAR_KET_THUC==="""


def _reference_block(reference_formula) -> str:
    if reference_formula is None:
        return ""
    return (
        "\n\nCÔNG THỨC tham khảo từ 1 video/kênh đang viral (áp dụng cấu trúc "
        "này cho chủ đề mới, KHÔNG chép lại nội dung gốc):\n"
        f"- Kiểu hook: {reference_formula.hook_pattern}\n"
        f"- Các nhịp chính: {', '.join(reference_formula.structure_beats)}\n"
        f"- Nhịp dựng: {reference_formula.pacing_style}\n"
        f"- Kiểu CTA: {reference_formula.cta_type}\n"
        f"- Giọng điệu: {reference_formula.tone}\n"
    )


def _apply_topics(slots: list[ScheduleSlot], data: list) -> list[ScheduleSlot]:
    if not isinstance(data, list) or len(data) != len(slots):
        got = len(data) if isinstance(data, list) else "không phải mảng"
        raise llm.LlmJsonParseError(
            f"LLM trả về {got} chủ đề, cần đúng {len(slots)} — thử lại hoặc chia nhỏ lịch."
        )
    for slot, item in zip(slots, data):
        slot.topic = str(item.get("topic", "")).strip()
        slot.angle = str(item.get("angle", "")).strip()
        slot.hook_idea = str(item.get("hook_idea", "")).strip()
    return slots


def generate_topics(
    strategy: str,
    slots: list[ScheduleSlot],
    reference_formula=None,
    effort: str = "high",
) -> list[ScheduleSlot]:
    """Sinh chủ đề/góc triển khai/hook cho TỪNG Ô lịch đã có sẵn (từ
    build_schedule_grid) — LLM chỉ lo sáng tạo nội dung, không đụng tới
    lịch/giờ/quầy đã tính sẵn bằng code. `reference_formula` (tuỳ chọn):
    kết quả app/services/video_source_import.py::analyze_viral_formula()
    nếu chiến lược muốn "shu theo 1 kênh/video đang viral" (KH App new,
    Bước 1c nhánh 2)."""
    if not strategy.strip():
        raise ValueError("Cần nhập câu chiến lược trước khi lập thực đơn.")
    if not slots:
        raise ValueError("Chưa có lịch nào để sinh chủ đề — gọi build_schedule_grid() trước.")

    system = _TOPICS_SYSTEM_PROMPT_TEMPLATE.format(
        count=len(slots), strategy=strategy.strip(), reference_block=_reference_block(reference_formula),
    )
    data = llm.generate_json(
        system, f"Lịch đăng (thứ tự cần điền chủ đề đúng theo thứ tự này):\n{_slot_summary_lines(slots)}",
        "===CALENDAR_BAT_DAU===", "===CALENDAR_KET_THUC===",
        max_tokens=_estimate_topics_max_tokens(len(slots)), effort=effort, default=[], raise_on_error=True,
    )
    return _apply_topics(slots, data)


_REVISE_SYSTEM_PROMPT_TEMPLATE = """Bạn đang chỉnh sửa lại 1 THỰC ĐƠN NỘI DUNG (lịch chủ đề video) đã lập trước
đó, theo đúng yêu cầu chỉnh sửa của người dùng dưới đây. Giữ nguyên số
lượng {count} mục và ĐÚNG THỨ TỰ ngày/quầy đã có (chỉ đổi topic/angle/
hook_idea, không đổi số lượng).

Yêu cầu chỉnh sửa:
{instruction}

QUAN TRỌNG VỀ ĐỊNH DẠNG: trả lời CHỈ 1 mảng JSON có ĐÚNG {count} phần tử,
bọc giữa 2 dòng đánh dấu:
===CALENDAR_BAT_DAU===
[{{"topic": "...", "angle": "...", "hook_idea": "..."}}, ...]
===CALENDAR_KET_THUC==="""


def revise_calendar_topics(
    slots: list[ScheduleSlot], instruction: str, effort: str = "medium"
) -> list[ScheduleSlot]:
    """"Chỉnh sửa do Agent" (KH App new, Bước 1c nhánh 2): áp dụng 1 yêu
    cầu sửa của người dùng (VD "chủ đề ngày 5-10 phải liên quan tới mùa
    Tết") lên TOÀN BỘ thực đơn đã lập, giữ nguyên lịch ngày/quầy/giờ — chỉ
    đổi nội dung."""
    if not instruction.strip():
        raise ValueError("Cần nhập yêu cầu chỉnh sửa cụ thể.")
    if not slots:
        raise ValueError("Chưa có thực đơn nào để chỉnh sửa.")

    current = "\n".join(
        f"{i + 1}. Ngày {s.day} - quầy {s.platform} - chủ đề hiện tại: {s.topic} | "
        f"góc: {s.angle} | hook: {s.hook_idea}"
        for i, s in enumerate(slots)
    )
    system = _REVISE_SYSTEM_PROMPT_TEMPLATE.format(count=len(slots), instruction=instruction.strip())
    data = llm.generate_json(
        system, f"Thực đơn hiện tại:\n{current}",
        "===CALENDAR_BAT_DAU===", "===CALENDAR_KET_THUC===",
        max_tokens=_estimate_topics_max_tokens(len(slots)), effort=effort, default=[], raise_on_error=True,
    )
    return _apply_topics(slots, data)


def generate_content_calendar(
    strategy: str,
    platforms: list[str],
    videos_per_day: int,
    days: int,
    duration_seconds: int,
    golden_hours: dict[str, str] | None = None,
    reference_formula=None,
    effort: str = "high",
) -> ContentCalendar:
    """Đầu-cuối: lập lịch (toán thuần) rồi sinh chủ đề (LLM) — dùng khi
    muốn gọi 1 hàm duy nhất; gọi riêng build_schedule_grid()/generate_topics()
    nếu cần kiểm tra/hiển thị lịch trước khi tốn 1 lần gọi LLM."""
    slots = build_schedule_grid(platforms, videos_per_day, days, duration_seconds, golden_hours)
    slots = generate_topics(strategy, slots, reference_formula, effort=effort)
    return ContentCalendar(slots=slots, total_videos=len(slots), strategy_summary=strategy.strip())
