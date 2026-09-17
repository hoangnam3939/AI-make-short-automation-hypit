---
name: script-grounded-scene-accuracy
description: BẮT BUỘC cho MỌI video — mọi chi tiết hình ảnh trong 1 cảnh (chiến thuật, đội hình, hành vi nhân vật, trình tự sự kiện) phải bám ĐÚNG kịch bản/sự kiện thật của câu chuyện đang kể, KHÔNG được để Veo3 tự suy diễn theo mô-típ thể loại chung chung (VD phim cổ trang) nếu mô-típ đó không đúng với chính câu chuyện này. Dùng khi viết prompt cảnh cho bất kỳ video nào.
---

# Bám đúng kịch bản, không để Veo3 tự suy diễn theo mô-típ có sẵn

Rút ra từ phiên làm việc thật 2026-09-13: dù đã có 4 skill khác (bối cảnh, lịch sử Việt, lịch sử thế giới, hiện tại hoá + logic hành động), Veo3 vẫn 2 lần tự thay thế nội dung ĐÚNG của kịch bản bằng một **mô-típ điện ảnh quen thuộc nhưng SAI với chính câu chuyện đang kể**:
- Cảnh minh hoạ chênh lệch quân số → Veo3 tự vẽ thành "hai đội quân dàn trận đối mặt nhau, tướng cưỡi ngựa ra giữa" (mô-típ phim cổ trang Trung Hoa) — trong khi kịch bản THẬT của trận Ngọc Hồi-Đống Đa là một cuộc **đánh úp thần tốc, mật tập, hoàn toàn bất ngờ trong đêm**, không hề có màn dàn trận/khiêu chiến nào.
- Điều này có nguy cơ lặp lại ở BẤT KỲ cảnh nào có "khoảng trống" trong mô tả — Veo3 sẽ tự lấp bằng mô-típ phổ biến nhất trong dữ liệu huấn luyện của nó, dù mô-típ đó không khớp với sự kiện thật đang tái hiện.

## Nguyên tắc bắt buộc

1. **Trước khi viết prompt cho 1 cảnh, xác định rõ: sự kiện/hành vi/chiến thuật thật sự diễn ra trong kịch bản là gì?** — không suy đoán, tra lại kịch bản gốc hoặc sự kiện lịch sử đã xác nhận (dùng chung với historical-accuracy-research/world-epic-historical-accuracy khi là nội dung lịch sử có thật).
2. **Nếu cảnh đó dễ bị nhầm với 1 mô-típ điện ảnh phổ biến nhưng KHÔNG đúng với câu chuyện này** (VD: dàn trận đối đầu, quyết đấu tay đôi, diễn thuyết trước đám đông, đối thoại trước khi đánh...) → PHẢI viết rõ CẢ HAI: (a) sự kiện thật đang diễn ra, và (b) phủ định tường minh mô-típ sai ("KHÔNG phải cảnh dàn trận đối mặt", "KHÔNG có màn khiêu chiến trước khi đánh", "đây là đánh úp bất ngờ không báo trước").
3. Không tin tưởng rằng chỉ mô tả "đúng" là đủ — nếu có RỦI RO Veo3 hiểu nhầm sang mô-típ quen thuộc, phải NÓI RÕ RÀNG loại trừ mô-típ đó, không chỉ mô tả tích cực.
4. Áp dụng cho MỌI khía cạnh của cảnh, không chỉ chiến thuật quân sự: hành vi xã hội, nghi lễ, cách nhân vật tương tác — bất cứ chỗ nào có "khoảng trống" trong mô tả đều là chỗ Veo3 có thể tự suy diễn sai.

## Ví dụ: nhịp độ hình ảnh phải khớp nhịp độ thật của sự kiện

Rút ra từ phản hồi thật 2026-09-13: trận Ngọc Hồi - Đống Đa là một cuộc tấn công **thần tốc, dồn dập** — nhưng prompt ban đầu lại dùng nhiều "slow-motion" cho các cảnh chiến đấu (mô-típ điện ảnh phổ biến để tạo cảm giác hoành tráng), mâu thuẫn với chính tinh thần "thần tốc" của trận đánh đang kể. Bài học: khi kịch bản mô tả rõ tốc độ/nhịp độ của sự kiện (nhanh, chậm, dồn dập, chậm rãi trang nghiêm...), phần "Visual style" của TỪNG cảnh liên quan phải khớp đúng nhịp độ đó — không mặc định dùng "slow-motion" cho mọi cảnh chiến đấu chỉ vì đó là mô-típ quen thuộc.

## Áp dụng thực tế

Sau khi viết xong 1 kịch bản/scene prompt, đọc lại và tự hỏi: "Nếu tôi chỉ đọc mô tả này mà không biết trước sự kiện lịch sử thật, tôi có thể hiểu nhầm sang 1 mô-típ điện ảnh phổ biến khác không?" Nếu có, bổ sung ngay phần phủ định tường minh, không đợi xem video lỗi mới sửa (tốn credit thật mỗi lần tạo lại).
