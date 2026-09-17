"""Danh sách AI làm video đề xuất + máy tính ngân sách — Mục 7, Nhiem_Vu_Goc_App_Video_AI_V3.docx.

Không cần LLM. Dữ liệu tĩnh (từ báo cáo nghiên cứu thị trường) + công thức tính toán thuần túy.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class AiTool:
    id: str
    name: str
    pros: str
    cons: str
    price_note: str
    link: str
    commercial_license_clear: bool  # Mục 4 (V2): hiển thị rõ giấy phép cá nhân/thương mại
    price_clarity: str  # "clear" | "opaque" — Mục 7 (V3): ưu tiên AI giá rõ ràng
    price_per_second_usd_low: float | None  # None nếu không công bố rõ (giống LTX/Katalist/Novi/Vadoo)
    price_per_second_usd_high: float | None
    default_recommended: bool


AI_TOOLS: list[AiTool] = [
    AiTool(
        id="vidu",
        name="Vidu AI",
        pros="Hồ sơ nhân vật đặt tên, dùng lại nhiều lần không cần tải ảnh — hợp video nhiều cảnh",
        cons="Ít nổi tiếng hơn Runway/Kling về độ chân thực",
        price_note="Miễn phí 80 credit; 10 đô/tháng; 35 đô/tháng",
        link="https://www.vidu.com/",
        commercial_license_clear=True,
        price_clarity="clear",
        price_per_second_usd_low=0.03,
        price_per_second_usd_high=0.08,
        default_recommended=True,
    ),
    AiTool(
        id="higgsfield",
        name="Higgsfield AI (Soul ID)",
        pros="Huấn luyện nhận diện riêng từ 20-80 ảnh — giữ nhân vật chắc chắn nhất",
        cons="Cần nhiều ảnh mẫu hơn",
        price_note="15-19 đô; 39-47 đô; 99 đô/tháng",
        link="https://higgsfield.ai/",
        commercial_license_clear=True,
        price_clarity="clear",
        price_per_second_usd_low=0.05,
        price_per_second_usd_high=0.12,
        default_recommended=True,
    ),
    AiTool(
        id="runway",
        name="Runway Gen-4",
        pros="Giữ nhân vật tốt chỉ từ 1 ảnh tham chiếu (quảng cáo 95%+)",
        cons="Giá cao hơn nếu dùng nhiều",
        price_note="Từ 12 đô/tháng; ~1 đô/10 giây 4K",
        link="https://runwayml.com/",
        commercial_license_clear=True,
        price_clarity="clear",
        price_per_second_usd_low=0.08,
        price_per_second_usd_high=0.10,
        default_recommended=True,
    ),
    AiTool(
        id="kling",
        name="Kling AI",
        pros="Gói miễn phí hào phóng để thử; giữ mặt khá tốt",
        cons="Hết credit miễn phí nhanh",
        price_note="Miễn phí 66 credit/ngày; 10-40 đô/tháng",
        link="https://klingai.com/",
        commercial_license_clear=True,
        price_clarity="clear",
        price_per_second_usd_low=0.02,
        price_per_second_usd_high=0.06,
        default_recommended=False,
    ),
    AiTool(
        id="google_flow",
        name="Google Flow (Veo 3.1)",
        pros="Âm thanh + hình đồng bộ tốt nhất; giữ nhân vật qua 3 ảnh tham chiếu (Ingredients)",
        cons="Mỗi lần tạo chỉ ~8 giây; giá tăng nhanh nếu chọn chất lượng cao",
        price_note="0.03-0.40 đô/giây tùy chất lượng, hoặc gói AI Pro/Ultra",
        link="https://flow.google.com/",
        commercial_license_clear=True,
        price_clarity="clear",
        price_per_second_usd_low=0.03,
        price_per_second_usd_high=0.40,
        default_recommended=True,
    ),
    AiTool(
        id="ltx_studio",
        name="LTX Studio",
        pros="Giữ nhân vật tốt nhất trong nhóm app thương mại, tự vẽ storyboard",
        cons="Gói rẻ nhất ($15) CHỈ dùng cá nhân, không được thương mại. Hệ thống credit không công bố tỷ lệ cố định.",
        price_note="Miễn phí (ít credit); trả phí ~15-60 đô/tháng — KHÔNG rõ số phút/giá",
        link="https://ltx.studio/",
        commercial_license_clear=False,
        price_clarity="opaque",
        price_per_second_usd_low=None,
        price_per_second_usd_high=None,
        default_recommended=False,
    ),
    AiTool(
        id="vadoo",
        name="Vadoo AI",
        pros="Gom 26+ AI làm video dưới 1 hệ thống điểm",
        cons="Không công bố bảng giá theo từng AI model — KHÔNG rõ số phút thật",
        price_note="Miễn phí (10 video); 19-79 đô/tháng",
        link="https://vadoo.tv/",
        commercial_license_clear=True,
        price_clarity="opaque",
        price_per_second_usd_low=None,
        price_per_second_usd_high=None,
        default_recommended=False,
    ),
]


def get_recommended_tools() -> list[AiTool]:
    return [t for t in AI_TOOLS if t.default_recommended]


def estimate_budget(tool_id: str, video_seconds: int, retry_buffer_pct: int = 40) -> dict:
    """Ước tính ngân sách cho 1 dự án — Mục 5-6 (V2): 'máy tính ngân sách' + dự phòng 30-50%.

    Trả về khoảng USD thấp/cao, có cộng thêm % dự phòng cho việc làm lại cảnh lỗi
    (mặc định 40%, nằm giữa khoảng 30-50% đã ghi trong đặc tả).
    """
    tool = next((t for t in AI_TOOLS if t.id == tool_id), None)
    if tool is None:
        raise ValueError(f"Không tìm thấy AI tool: {tool_id}")

    if tool.price_per_second_usd_low is None:
        return {
            "tool_id": tool.id,
            "tool_name": tool.name,
            "known": False,
            "message": (
                f"{tool.name} không công bố tỷ lệ giá/giây rõ ràng — "
                "không thể tính ngân sách chính xác. Khuyến nghị thử gói miễn phí trước "
                "để đo mức tiêu hao thật, hoặc chọn 1 AI khác có giá rõ ràng."
            ),
        }

    buffer_mult = 1 + (retry_buffer_pct / 100)
    low = round(video_seconds * tool.price_per_second_usd_low * buffer_mult, 2)
    high = round(video_seconds * tool.price_per_second_usd_high * buffer_mult, 2)
    return {
        "tool_id": tool.id,
        "tool_name": tool.name,
        "known": True,
        "video_seconds": video_seconds,
        "retry_buffer_pct": retry_buffer_pct,
        "estimated_usd_low": low,
        "estimated_usd_high": high,
        "message": f"Ước tính {low}-{high} đô cho {video_seconds} giây video (đã cộng {retry_buffer_pct}% dự phòng làm lại cảnh lỗi).",
    }
