"""Bước 13 (README) — sau khi có video hoàn chỉnh, tự động lấy hiệu ứng âm thanh
theo TỪNG CẢNH storyboard từ tiengdong.com rồi hòa vào video.

Cách lấy dữ liệu: tiengdong.com không có API tìm kiếm public (đã kiểm tra
/wp-json/ trả 404, ô tìm kiếm trên trang là widget Google CSE chạy JS nên
request thường không thấy kết quả). Nhưng mỗi trang danh mục
(vd /danh-nhau-vu-khi) liệt kê hàng chục hiệu ứng kèm link mp3 trực tiếp ngay
trong HTML server-render (đã xác nhận bằng request thật, không cần trình duyệt).
Nên chiến lược ở đây là: tải vài trang danh mục liên quan tới nội dung phim
lịch sử/chiến trận, gom thành 1 danh sách, rồi so khớp từ khóa đơn giản.

LỖI THẬT đã gặp và đã sửa (2026-09-13, xem thêm
.claude/skills/sfx-mixing-safety/SKILL.md) — bản đầu tiên của module này chỉ
chọn ĐÚNG 1 hiệu ứng cho CẢ MỘT ĐOẠN LỜI DẪN lớn (7-48 giây, gộp chung nhiều
cảnh storyboard khác nội dung nhau), khiến VD cảnh "ngựa phi cấp báo" không hề
có tiếng vó ngựa vì phải dùng chung SFX với cả đoạn kịch bản chứa nó. Sửa:
chọn SFX theo ĐÚNG TỪNG CẢNH storyboard (không phải từng đoạn lời dẫn), và
cho phép NHIỀU LỚP âm thanh chồng nhau trong cùng 1 cảnh (`SfxLayer`) — đúng
kỹ thuật đã chứng minh hiệu quả ở 5 video làm tay trước đó (xem
`SFX_Salamis/scenes_plan.py`, `SFX_SonTinhThuyTinh/scenes_plan.py`), nay
được tự động hoá bằng cách nhờ Claude (`llm.suggest_sfx_layers`) đọc prompt
hình ảnh của từng cảnh để đề xuất lớp âm thanh, thay vì con người tự gõ tay.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from app.services.video_builder import FFMPEG

# Các trang danh mục trên tiengdong.com phù hợp với nội dung phim lịch sử/chiến trận.
# Lấy từ menu chính của site (mục "Danh mục âm thanh") + 1 trang con phát hiện được
# lúc khảo sát (am-thanh-tien-giang-tran, riêng cho âm thanh hành quân/xung trận).
SFX_CATEGORY_PAGES: list[str] = [
    "https://tiengdong.com/danh-nhau-vu-khi",
    "https://tiengdong.com/danh-nhau-vu-khi/page/2",
    "https://tiengdong.com/am-thanh-tien-giang-tran",
    "https://tiengdong.com/tieng-dong-vat",
    "https://tiengdong.com/tieng-thien-nhien",
    "https://tiengdong.com/tieng-con-nguoi",
    "https://tiengdong.com/am-thanh-hung-du-ghe-so",
]

_ITEM_RE = re.compile(r'<li class="audio-play-item">(.*?)</li>', re.S)
_MP3_RE = re.compile(r"playPauseAudio\('[^']*',\s*'([^']+\.mp3[^']*)'\)")
_TITLE_RE = re.compile(r'class="title-link-col">\s*<a href="[^"]*">\s*(.*?)\s*</a>', re.S)

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TinhHoaAIVideoStudio/1.0"}

# Nhân với 2 (SFX_BOOST_DB ~ +6.02dB) theo đúng yêu cầu founder: âm lượng hiệu
# ứng nền phải to gấp đôi bản gốc để tạo cảm giác hoành tráng. Mỗi lớp
# (SfxLayer.gain_db) tự đặt mức TƯƠNG ĐỐI của riêng nó (thường âm, để nhiều
# lớp chồng nhau không vỡ tiếng), rồi cộng thêm SFX_BOOST_DB này.
SFX_BOOST_DB = 6.02


@dataclass
class SfxEntry:
    title: str
    mp3_url: str


@dataclass
class SfxLayer:
    """1 lớp âm thanh nền cho 1 cảnh — 1 cảnh có thể cần nhiều lớp cùng lúc
    (VD: vó ngựa + chân voi + tiếng hò hét trong cùng 1 cảnh xung trận)."""

    query_vi: str
    gain_db: float = -8.0
    start_offset: float = 0.0
    duration: float | None = None
    allow_birds: bool = False


@dataclass
class ScenePlan:
    """Kế hoạch SFX cho đúng 1 cảnh storyboard (không phải 1 đoạn lời dẫn)."""

    scene_n: int
    start_sec: float
    duration_sec: float
    layers: list[SfxLayer] = field(default_factory=list)


@dataclass
class _ResolvedLayer:
    abs_start: float
    max_duration: float
    gain_db: float
    file_path: Path


def _fetch(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="ignore")


def build_sfx_index(pages: list[str] | None = None) -> list[SfxEntry]:
    """Tải các trang danh mục và gom thành danh sách (tên, link mp3), bỏ trùng."""
    index: list[SfxEntry] = []
    seen: set[str] = set()
    for url in (pages or SFX_CATEGORY_PAGES):
        try:
            html = _fetch(url)
        except Exception:  # noqa: BLE001 - 1 trang lỗi không nên chặn cả danh sách
            continue
        for block in _ITEM_RE.findall(html):
            mp3_m = _MP3_RE.search(block)
            title_m = _TITLE_RE.search(block)
            if not mp3_m or not title_m:
                continue
            mp3_url = mp3_m.group(1)
            if mp3_url in seen:
                continue
            seen.add(mp3_url)
            title = re.sub(r"\s+", " ", title_m.group(1)).strip()
            index.append(SfxEntry(title=title, mp3_url=mp3_url))
    return index


_STOPWORDS = {
    "tiếng", "âm", "thanh", "của", "và", "trong", "một", "là", "the", "a", "of", "in", "on",
    "các", "những", "cho", "khi", "được", "ra", "bị", "này", "từ", "với", "tại", "đã",
}


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-zà-ỹ]+", text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 1}


def find_best_sfx(query_vi: str, index: list[SfxEntry], allow_birds: bool = False) -> SfxEntry | None:
    """Chọn hiệu ứng khớp nhất theo số từ khóa trùng với tên bài — đơn giản,
    thuần logic, không cần AI. Trả None nếu không có từ khóa nào trùng.

    Mặc định LOẠI hẳn các hiệu ứng có "chim"/"chim chóc" trong tên (trừ khi
    allow_birds=True, dành riêng cho các cảnh thật sự ở rừng núi) — lỗi thật
    2026-09-13: câu hỏi "tiệc rượu pháo hoa đêm giao thừa" khớp nhầm với
    "Tiếng chim Hút Mật Xác Pháo" (chỉ trùng mỗi từ "pháo"), khiến tiếng chim
    kêu bị dùng cho cảnh tiệc năm mới, nghe rất lạc quẻ. Người dùng xác nhận:
    tiếng chim chỉ hợp lý ở cảnh rừng núi, không phải mặc định chung."""
    q_tokens = _tokenize(query_vi)
    best: SfxEntry | None = None
    best_score = 0
    for entry in index:
        title_lower = entry.title.lower()
        if not allow_birds and "chim" in title_lower:
            continue
        if "niệm phật" in title_lower:
            # Lỗi thật 2026-09-13: câu tìm "cờ phần phật trong gió" (tiếng cờ
            # bay, không liên quan tôn giáo) khớp nhầm với "Tiếng Niệm Phật 6
            # chữ" (tức "Nam Mô A Di Đà Phật") chỉ vì trùng đúng 1 âm tiết
            # "phật" giữa từ láy "phần phật" và từ "Phật" — khiến tiếng tụng
            # niệm bị chèn lạc quẻ vào cảnh chiến trận. Loại hẳn khỏi kết quả
            # so khớp mặc định, không có cờ `allow_...` riêng vì hầu như
            # không video lịch sử/hành động nào của app thật sự cần hiệu ứng
            # tụng niệm làm âm thanh nền.
            continue
        score = len(q_tokens & _tokenize(entry.title))
        if score > best_score:
            best, best_score = entry, score
    return best


def download_sfx(entry: SfxEntry, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(entry.mp3_url, headers=_UA)
    with urllib.request.urlopen(req, timeout=30) as r, open(out_path, "wb") as f:
        f.write(r.read())
    return out_path


def build_scene_plans_from_llm(
    scenes: list[tuple[int, float, float, str]],
) -> list[ScenePlan]:
    """Với MỖI CẢNH storyboard thật (không phải đoạn lời dẫn), nhờ Claude đọc
    prompt hình ảnh (tiếng Anh, đã có sẵn từ bước sinh prompt cảnh) để đề
    xuất danh sách lớp âm thanh nền phù hợp.

    `scenes`: list (scene_n, start_sec, duration_sec, visual_prompt_en) —
    MỖI PHẦN TỬ LÀ 1 CẢNH ~8 GIÂY, không phải 1 đoạn HOOK/VẤN ĐỀ/... gộp
    nhiều cảnh. Đây chính là điểm khác biệt cốt lõi so với bản cũ."""
    from app.services.llm import suggest_sfx_layers

    plans: list[ScenePlan] = []
    for scene_n, start_sec, duration_sec, prompt_en in scenes:
        raw_layers = suggest_sfx_layers(prompt_en)
        layers = [
            SfxLayer(
                query_vi=str(rl.get("query_vi", "")).strip(),
                gain_db=float(rl.get("gain_db", -8.0)),
                start_offset=float(rl.get("start_offset", 0.0) or 0.0),
                duration=(float(rl["duration"]) if rl.get("duration") is not None else None),
                allow_birds=bool(rl.get("allow_birds", False)),
            )
            for rl in raw_layers
            if rl.get("query_vi")
        ]
        plans.append(ScenePlan(scene_n=scene_n, start_sec=start_sec, duration_sec=duration_sec, layers=layers))
    return plans


# Số lớp SFX tối đa mở cùng lúc trong 1 lệnh ffmpeg — xem lỗi thật đã gặp
# 2026-09-13 (video Quang Trung, 106 lớp cho 30 cảnh): mở hết >100 file audio
# cùng lúc trong 1 filter_complex làm ffmpeg SẬP (hết bộ nhớ, nhất là trên máy
# RAM thấp/đang chạy nhiều việc khác). Sửa: trộn theo TỪNG NHÓM nhỏ trước
# (mỗi nhóm ra 1 file audio trung gian), rồi mới gộp các nhóm lại ở bước cuối
# — số file mở cùng lúc không bao giờ vượt quá con số này.
_MAX_LAYERS_PER_BATCH = 16


def _mix_layer_batch(batch: list[_ResolvedLayer], out_path: Path, sfx_boost_db: float = SFX_BOOST_DB) -> Path:
    """Trộn 1 nhóm nhỏ lớp SFX (tối đa `_MAX_LAYERS_PER_BATCH` lớp) thành 1
    file audio duy nhất, giữ nguyên đúng thời điểm tuyệt đối của từng lớp
    (`adelay` tính theo `abs_start` thật, không tính lại từ 0) để khi gộp các
    nhóm lại ở bước cuối, mọi lớp vẫn đúng vị trí trên toàn bộ video.
    `sfx_boost_db`: nút chỉnh âm lượng nền tổng (Bước 8) — cộng thêm vào gain
    riêng (`gain_db`) của từng lớp, mặc định `SFX_BOOST_DB`."""
    cmd = [FFMPEG, "-y"]
    for layer in batch:
        cmd += ["-i", str(layer.file_path)]
    filter_parts = []
    mix_labels = []
    for i, layer in enumerate(batch):
        delay_ms = max(0, int(round(layer.abs_start * 1000)))
        max_dur = max(0.1, layer.max_duration)
        fade_start = max(0.0, max_dur - 0.4)
        total_gain_db = layer.gain_db + sfx_boost_db
        filter_parts.append(
            f"[{i}:a]atrim=0:{max_dur:.2f},afade=t=out:st={fade_start:.2f}:d=0.4,"
            f"volume={total_gain_db:.2f}dB,adelay={delay_ms}|{delay_ms}[l{i}]"
        )
        mix_labels.append(f"[l{i}]")
    filter_parts.append(
        f"{''.join(mix_labels)}amix=inputs={len(mix_labels)}:duration=longest:"
        f"dropout_transition=0:normalize=0[mixed]"
    )
    cmd += ["-filter_complex", ";".join(filter_parts), "-map", "[mixed]", str(out_path)]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path


def mix_layers_into_video(
    video_path: Path,
    resolved_layers: list[_ResolvedLayer],
    out_path: Path,
    narration_volume_multiplier: float = 1.8,
    sfx_boost_db: float = SFX_BOOST_DB,
    tmp_dir: Path | None = None,
) -> Path:
    """Hòa NHIỀU LỚP hiệu ứng âm thanh (mỗi lớp có gain riêng, thời điểm
    riêng) vào video ĐÃ ghép hoàn chỉnh (Bước 13 chạy sau Bước 10-11).

    Mỗi lớp được `atrim` cắt ngắn đúng `max_duration` (xem lỗi thật: file
    SFX tải về có thể dài hơn nhiều phút, không cắt sẽ kêu tràn sang các
    cảnh sau) kèm `afade` mờ dần cuối lớp, đặt đúng thời điểm bằng `adelay`,
    và nhân âm lượng riêng theo `gain_db` của chính lớp đó.

    Với video nhiều cảnh (VD 30+ cảnh x 3-4 lớp = hàng trăm lớp), việc trộn
    được chia thành TỪNG NHÓM nhỏ trước (xem `_mix_layer_batch`) để tránh
    sập ffmpeg do mở quá nhiều file cùng lúc.

    Giọng đọc gốc ([0:a]) được nhân thêm `narration_volume_multiplier`
    TRƯỚC khi mix (nếu không, khi nhiều lớp SFX cộng dồn, giọng đọc dễ bị
    nuốt mất — xem lỗi thật đã gặp). `amix` tắt `normalize` (để các mức âm
    lượng đã chủ động đặt không bị tự động san bằng lại) nhưng có
    `alimiter` ngay sau để chặn vỡ tiếng khi cộng dồn nhiều nguồn."""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not resolved_layers:
        shutil.copy(video_path, out_path)
        return out_path

    tmp_dir = tmp_dir or out_path.parent
    tmp_dir.mkdir(parents=True, exist_ok=True)

    premix_paths: list[Path] = []
    for batch_start in range(0, len(resolved_layers), _MAX_LAYERS_PER_BATCH):
        batch = resolved_layers[batch_start : batch_start + _MAX_LAYERS_PER_BATCH]
        premix_path = tmp_dir / f"_premix_batch_{batch_start // _MAX_LAYERS_PER_BATCH:03d}.wav"
        if not (premix_path.exists() and premix_path.stat().st_size > 0):
            # Máy có thể hết bộ nhớ tạm thời giữa chừng khi trộn hàng trăm lớp
            # (lỗi thật đã gặp 2026-09-13) — nhóm nào đã trộn xong (còn file)
            # thì bỏ qua, để chạy lại kịch bản không phải làm lại từ đầu.
            _mix_layer_batch(batch, premix_path, sfx_boost_db=sfx_boost_db)
        premix_paths.append(premix_path)

    cmd = [FFMPEG, "-y", "-i", str(video_path)]
    for p in premix_paths:
        cmd += ["-i", str(p)]

    filter_parts = [f"[0:a]volume={narration_volume_multiplier}[narr]"]
    mix_labels = ["[narr]"] + [f"[{i}:a]" for i in range(1, len(premix_paths) + 1)]
    filter_parts.append(
        f"{''.join(mix_labels)}amix=inputs={len(mix_labels)}:duration=first:"
        f"dropout_transition=0:normalize=0[mixed]"
    )
    filter_parts.append("[mixed]alimiter=limit=0.95[aout]")
    filter_complex = ";".join(filter_parts)

    cmd += [
        "-filter_complex", filter_complex,
        "-map", "0:v:0", "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        str(out_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)

    for p in premix_paths:
        p.unlink(missing_ok=True)
    return out_path


def apply_step13_sfx(
    final_video_path: Path,
    scene_plans: list[ScenePlan],
    out_path: Path,
    workdir: Path,
    index: list[SfxEntry] | None = None,
    narration_volume_multiplier: float = 1.8,
    sfx_boost_db: float = SFX_BOOST_DB,
) -> Path:
    """Orchestrator Bước 13 đầy đủ: `scene_plans` là danh sách kế hoạch SFX
    theo ĐÚNG TỪNG CẢNH storyboard (xem `build_scene_plans_from_llm` để tự
    sinh kế hoạch này bằng Claude, hoặc tự tay tạo `ScenePlan`/`SfxLayer`
    nếu muốn kiểm soát thủ công như cách làm ở 5 video trước).

    Với mỗi lớp trong mỗi cảnh: tìm hiệu ứng khớp nhất trên tiengdong.com,
    tải về, rồi hòa hết vào video cuối theo đúng thời điểm tuyệt đối
    (`scene.start_sec + layer.start_offset`)."""
    sfx_index = index if index is not None else build_sfx_index()
    resolved: list[_ResolvedLayer] = []
    for plan in scene_plans:
        for li, layer in enumerate(plan.layers):
            if not layer.query_vi:
                continue
            entry = find_best_sfx(layer.query_vi, sfx_index, allow_birds=layer.allow_birds)
            if entry is None:
                continue
            dest = workdir / f"sfx_scene_{plan.scene_n:02d}_layer{li}.mp3"
            try:
                download_sfx(entry, dest)
            except Exception:  # noqa: BLE001 - 1 hiệu ứng lỗi không nên chặn cả video
                continue
            abs_start = plan.start_sec + layer.start_offset
            room_left = max(0.1, plan.duration_sec - layer.start_offset)
            max_duration = min(layer.duration, room_left) if layer.duration is not None else room_left
            resolved.append(
                _ResolvedLayer(
                    abs_start=abs_start, max_duration=max_duration,
                    gain_db=layer.gain_db, file_path=dest,
                )
            )
    return mix_layers_into_video(
        final_video_path, resolved, out_path,
        narration_volume_multiplier=narration_volume_multiplier,
        sfx_boost_db=sfx_boost_db,
    )
