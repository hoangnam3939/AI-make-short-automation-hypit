"""Bước 11-12 (Mục 3, V3): chấm điểm kịch bản theo tiêu chí + tự sinh tiêu
đề/thumbnail/mô tả/CTA cho video hoàn chỉnh.

8 tiêu chí chấm điểm (`SCORING_CRITERIA`) lấy ĐÚNG nguyên văn Mục 3, Bước 12
của `Nhiem_Vu_Goc_App_Video_AI_V3.docx` (đã tìm lại được, xem thư mục gốc
dự án): "Chấm theo 8 tiêu chí (Hook/Nội dung/Storytelling/Retention/Nhịp
dựng/Hình ảnh/Âm thanh/CTA)". Bản trước đó (2026-09-14) dùng 1 bộ tiêu chí
khác do tưởng nhầm file gốc đã mất — đã sửa lại đúng ở đây.

Chấm điểm ở đây dựa trên VĂN BẢN kịch bản (không phân tích hình ảnh/âm
thanh thật của video đã dựng — việc đó cần chấm điểm bằng thị giác máy
tính, chưa làm trong bản này)."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.services.llm import generate_json

SCORING_CRITERIA = [
    "hook",           # Hook mở đầu có đủ mạnh để giữ chân người xem không
    "noi_dung",       # Nội dung có đúng trọng tâm, đầy đủ, đáng xem không
    "storytelling",   # Cách kể chuyện có mạch lạc, cuốn hút không
    "retention",      # Khả năng giữ chân người xem tới cuối (không bị chán/bỏ giữa chừng)
    "nhip_dung",      # Nhịp dựng (pacing giữa các cảnh/đoạn) có hợp lý không
    "hinh_anh",       # Hình ảnh/bối cảnh có phù hợp, chất lượng, đúng mô tả không
    "am_thanh",       # Âm thanh (giọng đọc, SFX, nhạc nền) có phù hợp, rõ ràng không
    "cta",            # Lời kêu gọi hành động cuối video có rõ ràng, tự nhiên không
]


@dataclass
class CriterionScore:
    key: str
    score: int  # 1-10
    comment: str


@dataclass
class ScriptScore:
    criteria: list[CriterionScore] = field(default_factory=list)
    total_score: float = 0.0
    summary: str = ""


TITLE_OPTIONS_COUNT = 10
THUMBNAIL_OPTIONS_COUNT = 5
DESCRIPTION_OPTIONS_COUNT = 3
CTA_OPTIONS_COUNT = 5


@dataclass
class VideoMetadata:
    """Bước 12 (Mục 3, V3): "tạo 10 tiêu đề, 5 câu chữ thumbnail, 3 mô tả,
    5 CTA để chọn" — nhiều PHƯƠNG ÁN cho người dùng chọn, không phải 1 kết
    quả cố định. `subtitle` không nằm trong danh sách đếm số lượng của bản
    gốc nên vẫn giữ 1 giá trị (dùng cho poster mở đầu video)."""
    titles: list[str] = field(default_factory=list)
    subtitle: str = ""
    descriptions: list[str] = field(default_factory=list)
    cta_texts: list[str] = field(default_factory=list)
    thumbnail_texts: list[str] = field(default_factory=list)


@dataclass
class SeoMetadata:
    platform: str
    title: str
    caption_or_description: str
    hashtags: list[str] = field(default_factory=list)
    tip: str = ""


PLATFORM_NAMES = {
    "youtube": "YouTube",
    "tiktok": "TikTok",
    "facebook_instagram": "Facebook và Instagram",
    "threads": "Threads",
    "twitter_x": "Twitter/X",
    "zalo": "Zalo",
}
SUPPORTED_PLATFORMS = sorted(PLATFORM_NAMES)

_PLATFORM_RULES = {
    "youtube": (
        "- title: tối đa 60-70 ký tự, chứa từ khoá chính NGAY ĐẦU tiêu đề để "
        "tối ưu tìm kiếm, gây tò mò nhưng KHÔNG giật tít sai sự thật, không "
        "lạm dụng viết hoa/emoji.\n"
        "- caption_or_description: 3-5 đoạn — đoạn ĐẦU TIÊN (khoảng 150 ký tự "
        "đầu, phần hiện ra trong kết quả tìm kiếm trước khi bấm 'xem thêm') "
        "phải chứa từ khoá chính + tóm tắt hấp dẫn nội dung; các đoạn sau kể "
        "thêm ngữ cảnh, chèn từ khoá liên quan một cách tự nhiên (không nhồi "
        "nhét từ khoá); kết thúc bằng lời mời like/comment/subscribe + nhắc "
        "bật chuông thông báo.\n"
        "- hashtags: 3-5 hashtag liên quan (YouTube nên dùng ít hashtag hơn "
        "TikTok/Instagram, tập trung đúng từ khoá).\n"
        "- tip: 1 câu mẹo cụ thể về thumbnail hoặc thời điểm đăng phù hợp với "
        "chính nội dung video này."
    ),
    "tiktok": (
        "- title: đúng 3-6 TỪ ĐẦU của caption (TikTok cắt ngắn caption khi "
        "hiển thị trên feed) — phải là phần hấp dẫn/gây tò mò nhất, không "
        "phải tiêu đề tách riêng.\n"
        "- caption_or_description: ngắn gọn (dưới 150 ký tự), giọng văn trẻ "
        "trung, bắt trend, có 1 câu hỏi hoặc lời thách thức ở cuối để khuyến "
        "khích người xem để lại comment.\n"
        "- hashtags: 4-8 hashtag, TRỘN 1-2 hashtag rộng (VD #lichsu "
        "#vietnam) với 2-3 hashtag ngách cụ thể theo đúng nội dung + 1-2 "
        "hashtag xu hướng chung (VD #hoctrentiktok #kienthucmoingay).\n"
        "- tip: 1 câu mẹo cụ thể về đoạn mở đầu 3 giây đầu hoặc loại nhạc "
        "nền/trend phù hợp với nội dung này."
    ),
    "facebook_instagram": (
        "- title: KHÔNG cần thiết cho Facebook/Instagram (dùng caption thay "
        "tiêu đề) — để trống chuỗi rỗng.\n"
        "- caption_or_description: mở đầu bằng 1 CÂU HOOK thật mạnh đứng "
        "riêng 1 dòng, sau đó kể lại câu chuyện ngắn gọn theo phong cách tự "
        "nhiên gần gũi (không giống mô tả YouTube), kết thúc bằng 1 câu hỏi "
        "mời tương tác + lời kêu gọi like/share/follow; nếu phù hợp có thể "
        "thêm 1 dòng nhắc 'xem thêm ở link trong bio' (dành cho Instagram).\n"
        "- hashtags: 5-10 hashtag (Instagram chấp nhận nhiều hashtag hơn "
        "Facebook), trộn hashtag phổ biến + hashtag ngách theo đúng nội dung.\n"
        "- tip: 1 câu mẹo cụ thể về khung giờ đăng hoặc cách khuyến khích "
        "chia sẻ phù hợp với nội dung này."
    ),
    "threads": (
        "- title: KHÔNG cần thiết cho Threads — để trống chuỗi rỗng.\n"
        "- caption_or_description: giọng văn TRÒ CHUYỆN, thoải mái như đang "
        "kể cho bạn bè nghe (Threads là nền tảng thảo luận, không phải nơi "
        "đăng bài trang trọng), tối đa khoảng 400-500 ký tự, kết thúc bằng "
        "1 câu hỏi mở để khơi gợi người khác reply/thảo luận bên dưới.\n"
        "- hashtags: 0-2 hashtag (Threads hầu như không dùng hashtag để tìm "
        "kiếm, thêm nhiều hashtag sẽ trông thừa/kém tự nhiên).\n"
        "- tip: 1 câu mẹo về cách trả lời bình luận để tăng tương tác trên "
        "Threads (thuật toán ưu tiên bài có nhiều reply qua lại)."
    ),
    "twitter_x": (
        "- title: KHÔNG cần thiết — để trống chuỗi rỗng.\n"
        "- caption_or_description: RẤT NGẮN GỌN, toàn bộ (kể cả hashtag) "
        "phải nằm dưới khoảng 280 ký tự — 1 câu hook thật mạnh, đi thẳng "
        "vào trọng tâm, không lan man; nếu câu chuyện dài, gợi ý viết dạng "
        "thread (đánh số 1/, 2/...) thay vì nhồi hết vào 1 dòng.\n"
        "- hashtags: tối đa 1-2 hashtag (dùng nhiều hashtag trên X bị coi "
        "là spam, làm giảm tương tác).\n"
        "- tip: 1 câu mẹo nhắc rõ nên đính kèm video/gif ngắn trực tiếp vào "
        "bài đăng (không dùng link ngoài) vì X ưu tiên hiển thị bài có "
        "media gắn kèm native hơn."
    ),
    "zalo": (
        "- title: KHÔNG cần thiết cho bài đăng Nhật ký/Feed Zalo — để trống "
        "chuỗi rỗng.\n"
        "- caption_or_description: văn phong GẦN GŨI, đời thường, giống "
        "đang chia sẻ với người thân/bạn bè (khán giả Zalo phần lớn là "
        "người quen biết nhau, không phải người lạ như Facebook/TikTok) — "
        "kể chuyện tự nhiên, ít dùng tiếng Anh/thuật ngữ, kết thúc bằng lời "
        "mời để lại cảm nghĩ hoặc chia sẻ cho người thân cùng xem.\n"
        "- hashtags: 0-2 hashtag tiếng Việt đơn giản (Zalo không có văn hoá "
        "dùng nhiều hashtag như các nền tảng khác).\n"
        "- tip: 1 câu mẹo về việc chia sẻ vào đúng nhóm/cộng đồng Zalo phù "
        "hợp chủ đề để tăng lượt xem."
    ),
}

_SEO_SYSTEM_PROMPT_TEMPLATE = """Bạn là chuyên gia SEO/marketing video cho nền tảng {platform_name}. Dựa
trên kịch bản đầy đủ được cung cấp, viết nội dung đăng bài chuẩn SEO ĐÚNG
ĐẶC THÙ của nền tảng {platform_name} (khác hẳn cách viết cho các nền tảng
khác), theo đúng các quy tắc sau:

{platform_rules}

Viết bằng CHÍNH ngôn ngữ của kịch bản được cung cấp.

Trả lời CHỈ 1 object JSON đúng dạng:
{{"title": "...", "caption_or_description": "...", "hashtags": ["...", "..."], "tip": "..."}}

QUAN TRỌNG VỀ ĐỊNH DẠNG TRẢ LỜI: bọc đúng 1 object JSON giữa 2 dòng đánh dấu:
===SEO_BAT_DAU===
(object JSON ở đây)
===SEO_KET_THUC==="""


_SCORE_SYSTEM_PROMPT = """Bạn là biên tập viên video chấm điểm chất lượng kịch bản trước khi sản
xuất, theo đúng 8 tiêu chí sau (mỗi tiêu chí chấm điểm nguyên từ 1 đến 10,
kèm 1 câu nhận xét ngắn bằng tiếng Việt):

1. hook — Hook mở đầu có đủ mạnh để giữ chân người xem không.
2. noi_dung — Nội dung có đúng trọng tâm, đầy đủ, đáng xem không.
3. storytelling — Cách kể chuyện có mạch lạc, cuốn hút không.
4. retention — Khả năng giữ chân người xem tới cuối, không bị chán/bỏ giữa chừng.
5. nhip_dung — Nhịp dựng (pacing) giữa các cảnh/đoạn có hợp lý không.
6. hinh_anh — Hình ảnh/bối cảnh mô tả trong kịch bản có phù hợp, chất lượng không.
7. am_thanh — Âm thanh (giọng đọc, SFX, nhạc nền) có phù hợp, rõ ràng không.
8. cta — Lời kêu gọi hành động cuối video có rõ ràng, tự nhiên không.

Trả lời CHỈ 1 object JSON đúng dạng:
{"criteria": [{"key": "hook", "score": 8, "comment": "..."}, ...
  đủ 8 tiêu chí theo đúng thứ tự trên], "summary": "1-2 câu tổng kết"}

QUAN TRỌNG VỀ ĐỊNH DẠNG TRẢ LỜI: bọc đúng 1 object JSON giữa 2 dòng đánh dấu:
===SCORE_BAT_DAU===
(object JSON ở đây)
===SCORE_KET_THUC==="""

_METADATA_SYSTEM_PROMPT = """Bạn là chuyên viên marketing video, viết tiêu đề/thumbnail/mô tả/CTA cho
1 video sắp đăng lên Facebook/YouTube, dựa trên kịch bản đầy đủ được cung cấp.
Sinh NHIỀU PHƯƠNG ÁN khác nhau thật sự (không lặp lại ý/cấu trúc câu giữa
các phương án) để người dùng tự chọn ra phương án ưng ý nhất — đúng số
lượng bắt buộc sau, không hơn không kém:

- titles: đúng 10 tiêu đề, mỗi cái ngắn gọn/hấp dẫn, tối đa ~8 từ (1 cái sẽ
  được dùng in lên poster mở đầu video — chữ HOA hoặc thường tuỳ ngữ cảnh,
  không thêm dấu ngoặc kép).
- subtitle: 1 dòng phụ đề ngắn duy nhất, đi kèm poster mở đầu (VD bối cảnh
  thời gian/địa điểm) — chỉ cần 1, không phải nhiều phương án.
- descriptions: đúng 3 đoạn mô tả (mỗi đoạn 3-6 câu) để đăng kèm video lên
  mạng xã hội, mỗi đoạn có hook mở đầu gây tò mò riêng, kết thúc bằng lời
  mời tương tác (like/comment/follow) và vài hashtag liên quan.
- cta_texts: đúng 5 câu kêu gọi hành động ngắn gọn cho cuối video.
- thumbnail_texts: đúng 5 cụm chữ RẤT NGẮN (tối đa 5 từ mỗi cụm) để đè lên
  ảnh thumbnail.

Viết bằng CHÍNH ngôn ngữ của kịch bản được cung cấp.

Trả lời CHỈ 1 object JSON đúng dạng:
{"titles": ["...", ... đủ 10 cái], "subtitle": "...",
 "descriptions": ["...", ... đủ 3 cái], "cta_texts": ["...", ... đủ 5 cái],
 "thumbnail_texts": ["...", ... đủ 5 cái]}

QUAN TRỌNG VỀ ĐỊNH DẠNG TRẢ LỜI: bọc đúng 1 object JSON giữa 2 dòng đánh dấu:
===META_BAT_DAU===
(object JSON ở đây)
===META_KET_THUC==="""


def score_script(script_text: str) -> ScriptScore:
    """Bước 11 (chấm điểm trước khi sản xuất, giúp người dùng biết kịch bản
    có đáng bỏ công dựng thật hay nên sửa lại trước). Trả về điểm 0 cho mọi
    tiêu chí nếu Claude lỗi/chưa cấu hình — không ném exception để không
    chặn luồng chính."""
    data = generate_json(
        _SCORE_SYSTEM_PROMPT,
        f"Kịch bản cần chấm điểm:\n\n{script_text}",
        "===SCORE_BAT_DAU===", "===SCORE_KET_THUC===",
        max_tokens=1500, effort="medium",
        default={"criteria": [], "summary": "Không chấm được điểm (Claude lỗi hoặc chưa cấu hình)."},
    )
    criteria = [
        CriterionScore(key=c.get("key", "?"), score=int(c.get("score", 0)), comment=str(c.get("comment", "")))
        for c in data.get("criteria", [])
        if isinstance(c, dict)
    ]
    total = round(sum(c.score for c in criteria) / len(criteria), 1) if criteria else 0.0
    return ScriptScore(criteria=criteria, total_score=total, summary=str(data.get("summary", "")))


def _str_list(data: dict, key: str) -> list[str]:
    return [str(v).strip() for v in data.get(key, []) if str(v).strip()]


def generate_metadata(script_text: str) -> VideoMetadata:
    """Bước 12 (Mục 3, V3): tự sinh 10 tiêu đề/5 thumbnail/3 mô tả/5 CTA để
    người dùng CHỌN — không phải 1 kết quả cố định. `titles[0]` được dùng
    làm mặc định in lên poster mở đầu video khi chạy tự động hoàn toàn
    (xem production_pipeline.py); phần còn lại để người dùng copy thẳng
    vào phần đăng bài Facebook/YouTube."""
    data = generate_json(
        _METADATA_SYSTEM_PROMPT,
        f"Kịch bản đầy đủ:\n\n{script_text}",
        "===META_BAT_DAU===", "===META_KET_THUC===",
        max_tokens=2000, effort="medium", default={},
    )
    return VideoMetadata(
        titles=_str_list(data, "titles"),
        subtitle=str(data.get("subtitle", "")).strip(),
        descriptions=_str_list(data, "descriptions"),
        cta_texts=_str_list(data, "cta_texts"),
        thumbnail_texts=_str_list(data, "thumbnail_texts"),
    )


def generate_seo_metadata(script_text: str, platform: str) -> SeoMetadata:
    """Bước 12 (mở rộng, 2026-09-14): sinh tiêu đề/caption/hashtag CHUẨN SEO
    riêng cho từng nền tảng — 3 nền tảng có quy tắc rất khác nhau (YouTube
    cần từ khoá ngay đầu tiêu đề để tối ưu tìm kiếm; TikTok cần caption cực
    ngắn vì bị cắt chữ; Facebook/Instagram cần hook mở đầu kiểu kể chuyện),
    nên KHÔNG dùng chung 1 bản mô tả cho cả 3 nơi như `generate_metadata()`
    (dùng cho poster mở đầu video)."""
    if platform not in _PLATFORM_RULES:
        raise ValueError(f"platform phải là 1 trong {sorted(_PLATFORM_RULES)}, nhận '{platform}'")

    system = _SEO_SYSTEM_PROMPT_TEMPLATE.format(
        platform_name=PLATFORM_NAMES[platform], platform_rules=_PLATFORM_RULES[platform]
    )
    data = generate_json(
        system, f"Kịch bản đầy đủ:\n\n{script_text}",
        "===SEO_BAT_DAU===", "===SEO_KET_THUC===",
        max_tokens=1200, effort="medium", default={},
    )
    return SeoMetadata(
        platform=platform,
        title=str(data.get("title", "")).strip(),
        caption_or_description=str(data.get("caption_or_description", "")).strip(),
        hashtags=[str(h).strip() for h in data.get("hashtags", []) if str(h).strip()],
        tip=str(data.get("tip", "")).strip(),
    )
