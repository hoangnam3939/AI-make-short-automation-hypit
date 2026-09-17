"""Test character_consistency.py (Mục 8, V3) — CHỈ test phần LOGIC thuần
(check_character_consistency, cosine_similarity), KHÔNG tải model CLIP thật
(build_scene_embeddings/compute_embedding cần torch+open_clip nặng, không
phù hợp chạy trong unit test nhanh — xem docstring module)."""
import numpy as np

from app.services.character_bible import Character, CharacterBible
from app.services.character_consistency import (
    DEFAULT_SIMILARITY_THRESHOLD,
    ConsistencyWarning,
    check_character_consistency,
    cosine_similarity,
)


def _unit(vec):
    arr = np.array(vec, dtype=float)
    return arr / np.linalg.norm(arr)


def test_cosine_similarity_of_identical_vectors_is_1():
    a = _unit([1, 0, 0])
    assert abs(cosine_similarity(a, a) - 1.0) < 1e-6


def test_cosine_similarity_of_orthogonal_vectors_is_0():
    a = _unit([1, 0])
    b = _unit([0, 1])
    assert abs(cosine_similarity(a, b)) < 1e-6


def test_check_character_consistency_flags_low_similarity_pair():
    bible = CharacterBible()
    bible.add(Character(name="Gióng", description="áo giáp sắt"))
    scene_source_texts = {
        1: "Gióng vươn vai đứng dậy.",
        2: "Gióng khoác áo giáp sắt lên người.",
        3: "Gióng phi ngựa sắt xông ra trận.",
    }
    # cảnh 1-2 rất giống nhau (embedding gần như trùng), cảnh 2-3 lệch hẳn.
    embeddings = {
        1: _unit([1.0, 0.02, 0.0]),
        2: _unit([0.99, 0.05, 0.0]),
        3: _unit([0.0, 1.0, 0.0]),
    }
    warnings = check_character_consistency(scene_source_texts, embeddings, bible)
    assert len(warnings) == 1
    w = warnings[0]
    assert isinstance(w, ConsistencyWarning)
    assert w.character_name == "Gióng"
    assert (w.scene_a, w.scene_b) == (2, 3)
    assert w.similarity < DEFAULT_SIMILARITY_THRESHOLD


def test_check_character_consistency_no_warning_when_all_similar():
    bible = CharacterBible()
    bible.add(Character(name="Gióng", description="áo giáp sắt"))
    scene_source_texts = {1: "Gióng đứng dậy.", 2: "Gióng khoác áo giáp."}
    embeddings = {1: _unit([1.0, 0.01]), 2: _unit([0.99, 0.02])}
    warnings = check_character_consistency(scene_source_texts, embeddings, bible)
    assert warnings == []


def test_check_character_consistency_ignores_scenes_without_character_mention():
    bible = CharacterBible()
    bible.add(Character(name="Gióng", description="áo giáp sắt"))
    scene_source_texts = {
        1: "Gióng đứng dậy.",
        2: "Trời đêm yên tĩnh trên đỉnh núi.",  # không nhắc Gióng
        3: "Gióng phi ngựa xông trận.",
    }
    # embedding cảnh 2 rất khác cảnh 1/3, nhưng KHÔNG được so vì không nhắc nhân vật.
    embeddings = {1: _unit([1.0, 0.0]), 2: _unit([0.0, 1.0]), 3: _unit([0.98, 0.05])}
    warnings = check_character_consistency(scene_source_texts, embeddings, bible)
    assert warnings == []  # chỉ còn nhóm {1, 3} liên tiếp, và chúng giống nhau


def test_check_character_consistency_skips_scenes_missing_embedding():
    """Cảnh bị lỗi/skip (không có video) sẽ không có mặt trong embeddings —
    không được làm hàm này ném lỗi (1 cảnh lỗi không chặn cả kiểm tra)."""
    bible = CharacterBible()
    bible.add(Character(name="Gióng", description="áo giáp sắt"))
    scene_source_texts = {1: "Gióng đứng dậy.", 2: "Gióng khoác áo giáp.", 3: "Gióng ra trận."}
    embeddings = {1: _unit([1.0, 0.0]), 3: _unit([0.99, 0.02])}  # cảnh 2 thiếu (lỗi/bỏ qua)
    warnings = check_character_consistency(scene_source_texts, embeddings, bible)
    assert warnings == []


def test_check_character_consistency_multiple_characters_grouped_separately():
    """2 nhân vật KHÔNG trùng tên (tên trùng/lồng vào nhau là 1 giới hạn đã
    biết của CharacterBible.find_mentioned(), không phải phạm vi test này)
    phải được gom nhóm và so ngưỡng ĐỘC LẬP với nhau."""
    bible = CharacterBible()
    bible.add(Character(name="Gióng", description="áo giáp sắt"))
    bible.add(Character(name="Bà Tổ", description="áo nâu"))
    scene_source_texts = {
        1: "Gióng đứng dậy.",
        2: "Bà Tổ lo lắng nhìn theo.",
        3: "Gióng phi ngựa xông trận.",
    }
    embeddings = {1: _unit([1.0, 0.0]), 2: _unit([0.0, 1.0]), 3: _unit([0.0, 0.99])}
    warnings = check_character_consistency(scene_source_texts, embeddings, bible)
    # Gióng chỉ xuất hiện ở cảnh 1 và 3 (không liên tiếp về mặt "nhóm nhân
    # vật" -> vẫn được so vì đây là 2 cảnh DUY NHẤT của nhóm Gióng) và chúng
    # LỆCH hẳn nhau -> phải bị cảnh báo; Bà Tổ chỉ có 1 cảnh -> không so được gì.
    assert len(warnings) == 1
    assert warnings[0].character_name == "Gióng"
    assert (warnings[0].scene_a, warnings[0].scene_b) == (1, 3)


def test_consistency_warning_message_format():
    w = ConsistencyWarning(character_name="Gióng", scene_a=2, scene_b=3, similarity=0.5)
    msg = w.message()
    assert "Cảnh 2 và 3" in msg
    assert "Gióng" in msg
    assert "0.50" in msg
