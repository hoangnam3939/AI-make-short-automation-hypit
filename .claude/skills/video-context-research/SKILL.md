---
name: video-context-research
description: BẮT BUỘC cho MỌI video app tạo ra (lịch sử, huyền thoại HOẶC hiện đại/đời thường) — trước khi viết kịch bản/prompt cảnh, phải xác định rõ bối cảnh thời đại + trang phục (lễ nghi, đời thường, võ phục, vui chơi...) của nội dung đó; nếu chưa đủ thông tin, ĐƯỢC PHÉP hỏi lại người dùng. Đây là skill tổng quát, áp dụng TRƯỚC các skill chuyên biệt hơn (historical-accuracy-research cho sử thi Việt, world-epic-historical-accuracy cho sử thi thế giới).
---

# Xác định bối cảnh trước khi viết kịch bản (mọi loại video)

Skill này **tổng quát hơn** 2 skill kia — áp dụng cho TẤT CẢ video app tạo ra, không chỉ phim lịch sử/sử thi. Kể cả video hiện đại, đời thường, quảng cáo, giải trí... đều cần xác định rõ bối cảnh trước khi viết kịch bản, nếu không mô hình sinh video sẽ tự suy đoán ngẫu nhiên về thời gian/không gian/trang phục.

**Ghi chú (2026-09-13):** đây là bản khởi đầu — người dùng sẽ tiếp tục cùng hoàn thiện skill này về sau, chưa phải bản cuối cùng.

## Bước bắt buộc: xác định bối cảnh TRƯỚC khi viết kịch bản

Với MỌI yêu cầu làm video, trước khi viết kịch bản/scene prompt, phải tự hỏi và trả lời (tra cứu hoặc hỏi người dùng nếu chưa rõ):

1. **Thời đại/bối cảnh thời gian**: Hiện đại? Quá khứ (thời điểm cụ thể nào)? Tương lai? Giả tưởng?
2. **Bối cảnh lịch sử/xã hội của thời đại đó** (nếu không phải hiện đại): thể chế, tầng lớp xã hội, khu vực địa lý — những yếu tố ảnh hưởng tới cách người trong bối cảnh đó ăn mặc/sinh hoạt.
3. **Trang phục theo TỪNG HOÀN CẢNH xuất hiện trong kịch bản** — không chỉ 1 kiểu trang phục chung cho cả phim:
   - Trang phục lễ nghi/trang trọng (triều đình, đám cưới, nghi lễ tôn giáo...)
   - Trang phục đời thường/lao động
   - Võ phục/trang phục chiến đấu (nếu có yếu tố xung đột/quân sự)
   - Trang phục vui chơi/giải trí/lễ hội (nếu có)
4. Nếu nội dung có yếu tố lịch sử/huyền thoại có thật → **chuyển tiếp sang skill chuyên biệt** [[historical-accuracy-research]] (sử thi Việt) hoặc [[world-epic-historical-accuracy]] (sử thi thế giới) để tra cứu sâu kiến trúc/vũ khí/cờ hiệu/nhân vật.

## Được phép hỏi lại người dùng

Nếu sau khi tự tra cứu (hoặc với nội dung hiện đại/hư cấu không có gì để tra cứu) mà vẫn CHƯA đủ thông tin để xác định rõ bối cảnh — ĐƯỢC PHÉP và NÊN hỏi lại người dùng (dùng AskUserQuestion hoặc hỏi trực tiếp trong hội thoại) thay vì tự suy đoán liều. Ví dụ câu hỏi cần làm rõ: bối cảnh diễn ra ở đâu/thời nào, nhân vật thuộc tầng lớp nào, có cảnh lễ nghi/chiến đấu/vui chơi nào cần trang phục riêng không.

## Sau khi có đủ thông tin

Áp dụng đầy đủ vào toàn bộ kịch bản: mỗi cảnh phải nhất quán với bối cảnh thời đại + đúng loại trang phục cho đúng hoàn cảnh cảnh đó (không dùng lẫn trang phục lễ nghi cho cảnh chiến đấu hay ngược lại). Nếu là nội dung lịch sử/huyền thoại có thật, tiếp tục áp dụng skill chuyên biệt tương ứng để tra cứu chi tiết sâu hơn (kiến trúc, vũ khí, cờ hiệu, nhân vật...).
