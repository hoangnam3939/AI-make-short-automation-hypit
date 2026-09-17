---
name: present-day-and-action-logic
description: BẮT BUỘC cho MỌI video (lịch sử hay hiện đại) — (1) mọi bối cảnh/công trình phải được mô tả như đang diễn ra ở HIỆN TẠI của câu chuyện (mới, sống động, được coi sóc), không phải như đang xem lại phế tích/phim cổ; (2) mọi hành động của nhân vật phải LOGIC, phù hợp đúng với việc nhân vật đang làm trong bối cảnh đó (không rút vũ khí khi không chiến đấu, không làm động tác thừa/sai ngữ cảnh). Dùng khi viết prompt cảnh cho bất kỳ video nào.
---

# Hiện tại hoá bối cảnh + Logic hành động nhân vật (mọi video)

Rút ra từ phiên làm việc thật 2026-09-13 khi làm phim "Quang Trung đại phá quân Thanh": Veo3 liên tục mắc 2 lỗi lặp lại dù đã có 3 skill khác — (1) tự vẽ kiến trúc/nhà cửa thành "phế tích cổ xưa, rêu phong" dù bối cảnh là kinh đô đang phồn thịnh; (2) tự thêm hành động vô lý không phù hợp bối cảnh (VD: sứ giả đang phi ngựa đưa tin lại rút đao vung lên như đang chiến đấu; quân lính đang ăn mừng liên hoan lại rút kiếm giơ lên trời như sắp giao chiến). Đây là 2 lỗi khác nhau nhưng cùng gốc: mô hình sinh video tự chèn các mô-típ "mặc định" quen thuộc (kiến trúc châu Á cổ = rêu phong; nhân vật cầm vũ khí = phải vung lên) thay vì bám đúng logic của cảnh.

## Nguyên tắc 1 — Hiện tại hoá bối cảnh (Present-day-ization)

Mọi cảnh phim tái hiện lịch sử phải được mô tả **NHƯ ĐANG QUAY MỘT BỘ PHIM VỚI BỐI CẢNH/PHIM TRƯỜNG MỚI DỰNG**, không phải như đang tham quan một di tích/phế tích. Với người xem trong câu chuyện, thời điểm đó CHÍNH LÀ hiện tại của họ — không ai trong thời đó nhìn thấy công trình của chính mình là "cổ".

- Câu phủ định ("KHÔNG cũ", "not ancient") LÀ CHƯA ĐỦ — phải viết khẳng định tích cực, cụ thể, nhiều chi tiết hình ảnh: "mọi bức tường/cột/ngói trông như vừa mới sơn xong trong năm nay", "đây là một bản dựng phim trường mới, không phải ảnh chụp di tích".
- Ngoại lệ HỢP LÝ (không cần "hiện tại hoá"): (a) cảnh phế tích/hoang tàn NGAY SAU một trận đánh — đây là hư hại MỚI do chiến sự, không phải "phong cách cổ xưa" — cần nói rõ "hư hại chiến tranh mới, khói còn bốc, mảnh vỡ mới gãy" chứ không phải "rêu phong lâu năm"; (b) cảnh "ngày nay" ở cuối phim nếu là di chỉ khảo cổ thật (khác với tượng đài hiện đại xây riêng).
- Áp dụng cho MỌI công trình xuất hiện trong cảnh: cung điện, đồn luỹ, nhà dân, cổng thành, tường thành — không chỉ công trình chính.

## Nguyên tắc 2 — Logic hành động theo đúng bối cảnh (Action-context consistency)

Trước khi chốt mô tả hành động của bất kỳ nhân vật nào trong 1 cảnh, tự hỏi: **"Việc nhân vật này đang làm trong cảnh này là gì? Hành động/tư thế nào hợp lý với việc đó?"**

- Đang di chuyển/đưa tin/không chiến đấu → vũ khí (nếu có mang theo) phải ở trạng thái đeo/giắt bên hông hoặc sau lưng, KHÔNG rút ra, KHÔNG vung lên — phải ghi rõ trong prompt: "vũ khí vẫn đeo im, không rút ra, không phải cảnh chiến đấu".
- Đang ăn mừng/liên hoan/dự tiệc → hành động hợp lý là nâng ly, cười nói, ôm vai — KHÔNG rút vũ khí, KHÔNG vung kiếm/đao lên trời (đó là hành động của lúc giao chiến, không phải lúc ăn mừng).
- Đang làm nghi lễ trang trọng → hành động chậm rãi, trang nghiêm, không hớt hải.
- Nguyên tắc chung: liệt kê rõ trong prompt vũ khí/đạo cụ nhân vật đang cầm Ở TRẠNG THÁI NÀO (rút ra hay đeo im) nếu cảnh đó không phải cảnh chiến đấu, đừng để mô hình tự suy đoán.
- Cũng tránh chèn chữ/phụ đề/lời thoại không cần thiết lên hình khi không có trong kịch bản gốc — nếu cảnh chỉ cần hình ảnh thuần, ghi rõ "no on-screen text, no dialogue, no captions".

## Nguyên tắc 3 — Tránh mô-típ điện ảnh có sẵn không đúng với sự kiện thật

Rút ra từ lỗi thật 2026-09-13: cảnh "so sánh quy mô 2 đội quân" (chỉ nhằm mục đích minh hoạ chênh lệch quân số) bị Veo3 tự vẽ thành "hai đội quân dàn trận đối mặt nhau, tướng cưỡi ngựa ra giữa" — một mô-típ rất quen thuộc trong phim cổ trang Trung Hoa nhưng SAI HOÀN TOÀN với sự kiện thật (trận Ngọc Hồi-Đống Đa là một cuộc **đánh úp thần tốc bất ngờ trong đêm**, không hề có cảnh 2 bên dàn trận đối mặt nói chuyện/khiêu chiến trước khi đánh). Bài học: khi mô tả 1 cảnh có ý nghĩa biểu tượng/minh hoạ (không phải cảnh giao tranh thật), phải nói RÕ đây không phải cảnh đối đầu, và liệt kê CỤ THỂ các mô-típ điện ảnh quen thuộc cần tránh (VD: "không phải 2 đội quân dàn hàng đối mặt nhau", "không có tướng cưỡi ngựa ra giữa khiêu chiến") — nếu không mô hình sẽ tự lấy mô-típ phổ biến nhất trong dữ liệu huấn luyện, dù nó không đúng với sự kiện lịch sử đang tái hiện.

## Nguyên tắc 4 — Cảnh phải "động", không được như tượng đứng yên

Rút ra từ lỗi thật 2026-09-13: cảnh lính gác đứng canh dễ bị Veo3 dựng thành tư thế cứng đờ như tượng, mất hẳn cảm giác video sống động. Với BẤT KỲ nhân vật nào đứng yên/canh gác/chờ đợi trong 1 cảnh, phải ghi rõ các chuyển động tự nhiên nhỏ để cảnh có sức sống: tóc/tua/vải bay nhẹ trong gió, mắt chớp, hơi đổi trọng tâm, nhịp thở, lửa đuốc lập loè, cờ phất... — không chỉ mô tả tư thế tĩnh rồi để mặc định, phải nói rõ "đây là cảnh quay động, không phải ảnh tĩnh/tượng đứng yên".

## Áp dụng thực tế

Khi rà soát 1 kịch bản/scene prompt đã viết xong, đọc lại TỪNG cảnh và tự hỏi 2 câu:
1. Công trình/bối cảnh trong cảnh này có được mô tả là "hiện tại, mới, sống động" chưa hay vẫn có nguy cơ bị hiểu là "cổ/phế tích"?
2. Hành động của từng nhân vật có hợp lý với việc họ đang làm không, hay có nguy cơ mô hình tự thêm hành động dư thừa (rút vũ khí, chiến đấu) không phù hợp bối cảnh?

Sửa NGAY TỪ ĐẦU cho toàn bộ kịch bản một lượt, không đợi xem video lỗi mới sửa từng cảnh một — mỗi lần tạo lại video tốn credit thật.
