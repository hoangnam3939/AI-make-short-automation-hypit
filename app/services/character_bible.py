"""Sổ Tay Nhân Vật (Character Bible) — Mục 5 + Bước 1, Nhiem_Vu_Goc_App_Video_AI_V3.docx.

Cơ chế giữ đồng nhất nhân vật (yêu cầu cốt lõi, được nhấn mạnh nhiều lần):
1. Mỗi nhân vật chính có 1 hồ sơ mô tả cố định (tuổi/ngoại hình/khuôn mặt/tóc/trang phục/vật dụng).
2. Mặc định tối đa 10 nhân vật/dự án, người dùng chọn tăng được tới 20.
3. Mọi prompt cảnh có nhân vật PHẢI tự động chèn lại NGUYÊN VĂN mô tả — không để AI tự nhớ.

Hàm inject_character_descriptions() là phần LÕI, KHÔNG cần gọi AI — kiểm tra
được bằng unit test thuần túy (tests/test_character_bible.py). Đây chính là
kỹ thuật đã dùng thành công để sửa lỗi cảnh 25 video Thánh Gióng.
"""
from __future__ import annotations

import re
from pydantic import BaseModel, Field

DEFAULT_MAX_CHARACTERS = 10
ABSOLUTE_MAX_CHARACTERS = 20


class Character(BaseModel):
    name: str
    description: str = Field(
        ..., description="Mô tả cố định: tuổi, ngoại hình, khuôn mặt, tóc, trang phục, vật dụng đặc trưng"
    )


class CharacterBible(BaseModel):
    characters: list[Character] = Field(default_factory=list)
    max_characters: int = DEFAULT_MAX_CHARACTERS

    def add(self, character: Character) -> None:
        if self.max_characters > ABSOLUTE_MAX_CHARACTERS:
            raise ValueError(f"max_characters không được vượt quá {ABSOLUTE_MAX_CHARACTERS}")
        if len(self.characters) >= self.max_characters:
            raise ValueError(
                f"Đã đạt giới hạn {self.max_characters} nhân vật. "
                f"Tăng max_characters (tối đa {ABSOLUTE_MAX_CHARACTERS}) nếu cần thêm."
            )
        if any(c.name.lower() == character.name.lower() for c in self.characters):
            raise ValueError(f"Nhân vật '{character.name}' đã tồn tại trong Sổ Tay")
        self.characters.append(character)

    def update_description(self, name: str, new_description: str) -> None:
        """Sửa 1 nhân vật -> tự động áp dụng cho mọi cảnh dùng lại Sổ Tay này
        (vì scene prompt luôn tra cứu Sổ Tay tại thời điểm build, không cache riêng)."""
        for c in self.characters:
            if c.name.lower() == name.lower():
                c.description = new_description
                return
        raise ValueError(f"Không tìm thấy nhân vật '{name}' để sửa")

    def find_mentioned(self, scene_text: str) -> list[Character]:
        """Tìm các nhân vật được nhắc tên trong nội dung 1 cảnh (không phân biệt hoa/thường,
        khớp theo từ nguyên vẹn để tránh khớp nhầm chuỗi con)."""
        found = []
        for c in self.characters:
            pattern = r"\b" + re.escape(c.name) + r"\b"
            if re.search(pattern, scene_text, flags=re.IGNORECASE):
                found.append(c)
        return found


def inject_character_descriptions(scene_prompt: str, scene_text_for_matching: str, bible: CharacterBible) -> str:
    """QUY TẮC BẮT BUỘC (Bước 6, V3): mọi prompt cảnh có nhân vật chính PHẢI tự động
    chèn lại nguyên văn mô tả nhân vật — không dựa vào AI tự nhớ từ cảnh trước.

    scene_text_for_matching: nội dung cảnh gốc (lời thoại + hành động, tiếng Việt) dùng để
        DÒ xem nhân vật nào xuất hiện trong cảnh này.
    scene_prompt: prompt tiếng Anh đã soạn cho cảnh (chưa có mô tả nhân vật).

    Trả về prompt đã chèn thêm 1 dòng "Character consistency:" liệt kê đúng mô tả
    của từng nhân vật xuất hiện trong cảnh — luôn nguyên văn, không diễn giải lại.
    """
    mentioned = bible.find_mentioned(scene_text_for_matching)
    if not mentioned:
        return scene_prompt

    lines = [f"{c.name}: {c.description}" for c in mentioned]
    consistency_block = "Character consistency (dùng nguyên văn, không thay đổi): " + " | ".join(lines)
    return f"{scene_prompt}\n{consistency_block}"
