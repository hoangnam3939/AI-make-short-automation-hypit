"""Mục 8 (Nhiem_Vu_Goc_App_Video_AI_V3.docx), phần cốt lõi/độc quyền: "so
sánh ảnh Sổ Tay Nhân Vật với từng khung hình cảnh (kỹ thuật tương tự
StoryDiffusion/InstantID) để phát hiện đổi hình" — nhân vật đổi hình dạng
giữa các cảnh (VD lỗi thật đã gặp: Thánh Gióng cảnh 25, người gầy bỗng
thành lực sĩ, đổi trang phục).

App hiện KHÔNG lưu ảnh tham chiếu riêng cho Sổ Tay Nhân Vật (chỉ có mô tả
văn bản, xem character_bible.py) — nên so sánh ẢNH VỚI ẢNH giữa CÁC CẢNH
có cùng 1 nhân vật (dùng CharacterBible.find_mentioned() đã có sẵn để gom
nhóm, không viết lại logic match tên), thay vì so với 1 ảnh gốc cố định.
Dùng embedding CLIP (mô hình mở, chạy CỤC BỘ trên máy, KHÔNG gửi ảnh ra
ngoài) đo độ giống TOÀN CẢNH (không chỉ khuôn mặt) — khớp đúng ví dụ lỗi
thật trong đặc tả gốc vì đó là thay đổi VÓC DÁNG/TRANG PHỤC, không chỉ mặt.

Dependency MỚI, NẶNG NHẤT app từng thêm (torch + open-clip-torch, tải
model CLIP ~350MB lần chạy đầu, cache lại các lần sau) — xem requirements.txt.
CHỈ CẢNH BÁO, không tự chặn/tự sửa gì, đúng tinh thần error_checker.py và
"1 cảnh lỗi không chặn cả video" xuyên suốt app.

Tách phần I/O nặng (build_scene_embeddings — gọi ffmpeg + CLIP thật) khỏi
phần LOGIC thuần (check_character_consistency — chỉ gom nhóm + so ngưỡng)
để test được logic mà không cần tải model CLIP thật (xem tests/test_character_consistency.py)."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.services.character_bible import CharacterBible
from app.services.video_builder import FFMPEG

CLIP_MODEL_NAME = "ViT-B-32-quickgelu"
CLIP_PRETRAINED = "openai"
# Dưới ngưỡng này (cosine similarity, 0-1) giữa 2 cảnh cùng 1 nhân vật ->
# cảnh báo khả năng đổi hình dạng. Hằng số dễ chỉnh nếu thực tế báo sai
# nhiều/ít quá.
DEFAULT_SIMILARITY_THRESHOLD = 0.75

_model = None
_preprocess = None


def _load_model():
    """Lazy-load model CLIP — chỉ tải khi thực sự gọi compute_embedding(),
    không chậm mọi lần import module này (VD khi production_pipeline.py
    import ở top-level). Cache lại cho các lần gọi sau trong cùng process."""
    global _model, _preprocess
    if _model is None:
        import open_clip

        _model, _, _preprocess = open_clip.create_model_and_transforms(CLIP_MODEL_NAME, pretrained=CLIP_PRETRAINED)
        _model.eval()
    return _model, _preprocess


def extract_representative_frame(video_path: Path, out_png: Path) -> Path:
    """Trích 1 khung hình ở GIỮA video ra PNG — dùng làm ảnh đại diện cho
    cảnh khi so sánh nhân vật (tái dùng đúng FFMPEG đã xác nhận hoạt động
    ở video_builder.py)."""
    from app.services.error_checker import probe_video_stream

    duration = probe_video_stream(video_path).duration
    mid = max(0.0, duration / 2)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [FFMPEG, "-y", "-ss", f"{mid:.2f}", "-i", str(video_path), "-frames:v", "1", str(out_png)],
        check=True, capture_output=True,
    )
    return out_png


def compute_embedding(image_path: Path):
    """Trả về vector embedding CLIP (đã chuẩn hoá L2) của 1 ảnh — numpy array."""
    import torch
    from PIL import Image

    model, preprocess = _load_model()
    image = preprocess(Image.open(image_path).convert("RGB")).unsqueeze(0)
    with torch.no_grad():
        features = model.encode_image(image)
        features = features / features.norm(dim=-1, keepdim=True)
    return features.squeeze(0).numpy()


def cosine_similarity(a, b) -> float:
    import numpy as np

    return float(np.dot(a, b))


def build_scene_embeddings(scene_video_paths: dict[int, str], workdir: Path) -> dict[int, object]:
    """I/O THẬT: trích khung hình (ffmpeg) + tính embedding (CLIP) cho từng
    cảnh đã tạo xong. Gọi riêng, KHÔNG gộp vào check_character_consistency()
    để phần logic thuần (gom nhóm/so ngưỡng) test được độc lập, không cần
    tải model CLIP thật."""
    embeddings: dict[int, object] = {}
    for sn, path in scene_video_paths.items():
        frame_png = workdir / f"consistency_frame_{sn:02d}.png"
        extract_representative_frame(Path(path), frame_png)
        embeddings[sn] = compute_embedding(frame_png)
    return embeddings


@dataclass
class ConsistencyWarning:
    character_name: str
    scene_a: int
    scene_b: int
    similarity: float

    def message(self) -> str:
        return (
            f"Cảnh {self.scene_a} và {self.scene_b}: nhân vật '{self.character_name}' "
            f"có thể đã đổi hình dạng (độ giống {self.similarity:.2f}, ngưỡng cảnh báo "
            f"{DEFAULT_SIMILARITY_THRESHOLD})"
        )


def check_character_consistency(
    scene_source_texts: dict[int, str],
    scene_embeddings: dict[int, object],
    bible: CharacterBible,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> list[ConsistencyWarning]:
    """LOGIC THUẦN (không I/O): với mỗi nhân vật trong Sổ Tay, gom các cảnh
    có nhắc tên nhân vật đó (CharacterBible.find_mentioned() đã có, không
    viết lại logic match tên) và ĐÃ CÓ embedding, rồi so từng CẶP cảnh LIÊN
    TIẾP trong nhóm (theo đúng thứ tự scene_n) — cặp nào dưới ngưỡng thì
    cảnh báo khả năng đổi hình dạng."""
    warnings: list[ConsistencyWarning] = []
    for character in bible.characters:
        scene_ns = sorted(
            sn for sn, text in scene_source_texts.items()
            if sn in scene_embeddings and character in bible.find_mentioned(text)
        )
        for a, b in zip(scene_ns, scene_ns[1:]):
            sim = cosine_similarity(scene_embeddings[a], scene_embeddings[b])
            if sim < similarity_threshold:
                warnings.append(ConsistencyWarning(character.name, a, b, sim))
    return warnings
