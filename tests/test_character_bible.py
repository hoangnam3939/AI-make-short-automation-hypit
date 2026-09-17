import pytest

from app.services.character_bible import (
    Character,
    CharacterBible,
    inject_character_descriptions,
    ABSOLUTE_MAX_CHARACTERS,
)


def make_thanh_giong_bible() -> CharacterBible:
    bible = CharacterBible()
    bible.add(Character(
        name="Gióng",
        description="towering armored warrior, wearing heavy gleaming iron armor, "
                    "riding a massive iron horse, NOT an oversized bare-chested bodybuilder",
    ))
    return bible


def test_default_max_is_10_and_extendable_to_20():
    bible = CharacterBible()
    assert bible.max_characters == 10
    bible.max_characters = 20
    for i in range(20):
        bible.add(Character(name=f"NV{i}", description="mo ta"))
    assert len(bible.characters) == 20
    with pytest.raises(ValueError):
        bible.add(Character(name="NV20", description="qua gioi han"))


def test_max_characters_hard_cap_20():
    bible = CharacterBible(max_characters=25)
    with pytest.raises(ValueError):
        bible.add(Character(name="X", description="y"))


def test_duplicate_character_name_rejected():
    bible = make_thanh_giong_bible()
    with pytest.raises(ValueError):
        bible.add(Character(name="Gióng", description="mo ta khac"))


def test_scene_25_regression_character_injected_when_mentioned():
    """Tái hiện đúng lỗi thật: prompt cảnh 25 Thánh Gióng ban đầu KHÔNG nhắc lại
    mô tả áo giáp -> AI vẽ sai thành người cởi trần lực sĩ. Cơ chế inject phải
    tự động chèn lại mô tả để lỗi này không tái diễn."""
    bible = make_thanh_giong_bible()

    scene_text_vi = "Gióng nhổ bật cả bụi tre đằng ngà bên đường, quật thẳng vào quân giặc."
    raw_prompt = (
        "Medium shot of the legendary warrior Gióng, now without his iron whip, "
        "reaching out to uproot a large cluster of golden bamboo by the roadside."
    )

    final_prompt = inject_character_descriptions(raw_prompt, scene_text_vi, bible)

    assert "gleaming iron armor" in final_prompt
    assert "NOT an oversized bare-chested bodybuilder" in final_prompt
    assert raw_prompt in final_prompt  # prompt gốc không bị mất, chỉ được bổ sung thêm


def test_character_not_mentioned_in_scene_is_not_injected():
    bible = make_thanh_giong_bible()
    bible.add(Character(name="Sứ giả", description="royal messenger in court attire"))

    scene_text_vi = "Sứ giả phi ngựa trở về tâu lại với nhà vua."
    final_prompt = inject_character_descriptions("A messenger riding fast.", scene_text_vi, bible)

    assert "royal messenger in court attire" in final_prompt
    assert "gleaming iron armor" not in final_prompt  # Gióng không xuất hiện cảnh này -> không chèn


def test_update_description_applies_to_future_scenes():
    bible = make_thanh_giong_bible()
    bible.update_description("Gióng", "updated: silver armor, calm expression")

    scene_text_vi = "Gióng đứng trên đỉnh núi Sóc."
    final_prompt = inject_character_descriptions("Wide shot on a mountain peak.", scene_text_vi, bible)

    assert "updated: silver armor" in final_prompt
    assert "gleaming iron armor" not in final_prompt  # mô tả cũ không còn được dùng
