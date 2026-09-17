---
name: battle-scene-pacing
description: BẮT BUỘC cho MỌI video có cảnh chiến trận/hành động (lịch sử cổ xưa hay hiện đại) — mọi cảnh quay và hành động trong đoạn chiến trận phải dồn dập, kịch tính, mang cao trào điện ảnh, tốc độ nhanh nhất có thể; áp dụng cho cả phần mô tả hành động chính LẪN phần "Visual style", không chỉ một trong hai. Áp dụng song song với cả skill `historical-accuracy-research` (sử thi Đại Việt) và `world-epic-historical-accuracy` (sử thi huyền thoại thế giới) — bất kỳ phim sử thi nào (Việt hay thế giới) có cảnh chiến trận đều phải qua skill này. Dùng khi viết hoặc rà soát prompt cho bất kỳ cảnh chiến đấu/hành động nào.
---

# Nhịp độ cảnh chiến trận phải dồn dập, kịch tính, cao trào (mọi video)

Rút ra từ phiên làm việc thật 2026-09-13 khi làm phim "Quang Trung đại phá quân Thanh" (trận Ngọc Hồi - Đống Đa): người dùng nhiều lần phải nhắc lại yêu cầu "mọi hành động phải nhanh, kịch tính, dồn dập, cao trào" cho cùng một cụm cảnh chiến trận — vì lần sửa đầu tiên chỉ đổi phần "Visual style" (câu mô tả phong cách quay ở cuối prompt: "MAXIMUM adrenaline pacing, rapid cuts...") mà **để nguyên phần mô tả hành động chính** vẫn dùng động từ "hiền", chậm rãi (VD: "advancing toward...", "leading the charge" thay vì "sprinting at full speed toward...", "tearing through at full gallop..."). Kết quả: dù Visual style đã ghi "MAXIMUM", video vẫn có thể ra chậm vì nội dung hành động chính không truyền tải tốc độ.

## Nguyên tắc 1 — Sửa CẢ hành động chính, không chỉ Visual style

Khi một cảnh cần "dồn dập, kịch tính, cao trào", phải rà soát và viết lại CẢ HAI phần:
1. **Phần mô tả hành động chính** (câu đầu prompt, mô tả nhân vật đang làm gì) — thay động từ/trạng từ chậm/trung tính bằng động từ mạnh, khẩn cấp: "advancing" → "sprinting/charging at full speed"; "leading" → "tearing through at full gallop"; "collapsing" → "collapsing in an instant"; "fleeing in disarray" → "fleeing in frantic disarray at full sprint".
2. **Phần "Visual style"** (câu cuối, mô tả kỹ thuật quay) — dùng ngôn ngữ điện ảnh: rapid-fire cuts, whip-fast camera, no slow-motion, breakneck momentum.

Chỉ sửa 1 trong 2 phần là CHƯA ĐỦ — mô hình sinh video đọc toàn bộ prompt, nếu phần hành động chính vẫn "chậm" thì phong cách quay nhanh cũng không cứu được cảm giác tổng thể.

## Nguyên tắc 2 — Áp dụng cho toàn bộ cụm cảnh cao trào, không phải từng cảnh lẻ

Khi người dùng xác định một cụm cảnh là "cao trào của bộ phim" (VD: toàn bộ đoạn tấn công/giao tranh chính), phải rà và sửa ĐỒNG LOẠT tất cả các cảnh trong cụm đó cùng lúc, không sửa từng cảnh một rồi để người dùng phải lặp lại yêu cầu cho từng cảnh kế tiếp — vừa tốn thời gian vừa dễ tốn credit sinh video sai.

## Nguyên tắc 3 — Có NGOẠI LỆ hợp lý: khoảnh khắc lắng đọng sau cao trào

Không phải mọi cảnh trong "vùng cao trào" đều cần tăng tốc. Một cảnh tĩnh lặng, bi tráng ngay SAU cao trào hành động (VD: nhân vật đứng một mình nhìn lại chiến trường, khoảnh khắc trước cái chết/thất bại) là một lựa chọn dựng phim hợp lý — "sau bão là lặng gió" — không nên tự ý tăng tốc cảnh này chỉ vì nó nằm gần các cảnh hành động. Khi gặp trường hợp này, nêu rõ với người dùng đây là lựa chọn có chủ đích (tương phản cảm xúc) và hỏi lại nếu người dùng vẫn muốn tăng tốc luôn, thay vì tự động áp dụng nguyên tắc "mọi hành động phải nhanh" một cách máy móc.

## Nguyên tắc 4 — Áp dụng cho cả sử thi Đại Việt lẫn sử thi thế giới

Skill này KHÔNG tách riêng theo nền văn hoá — nó áp dụng song song với `historical-accuracy-research` (phim sử thi/huyền thoại **Đại Việt** — VD: Quang Trung đại phá quân Thanh) và `world-epic-historical-accuracy` (phim sử thi/huyền thoại **thế giới** — VD: Troy, Salamis). Hai skill kia lo phần tra cứu kiến trúc/trang phục/vũ khí đúng thời đại-nền văn minh; skill này lo riêng phần NHỊP ĐỘ của các cảnh chiến trận trong phim đó — cả hai phải làm cùng lúc, không phải chọn một trong hai.

## Áp dụng thực tế

Khi viết hoặc rà soát prompt cho MỘT cảnh có tính chất chiến trận/hành động (không giới hạn thời cổ xưa — áp dụng cả phim hiện đại, hành động, hậu tận thế...):
1. Đọc lại câu mô tả hành động chính: động từ có truyền tải được tốc độ/sự khẩn cấp thực sự của cảnh không, hay vẫn "hiền" (advancing, moving, standing)?
2. Đọc lại câu Visual style: có dùng ngôn ngữ điện ảnh nhấn mạnh tốc độ tối đa, không có slow-motion, cắt cảnh nhanh không?
3. Nếu cảnh này là một phần của cụm cao trào lớn hơn, kiểm tra TOÀN BỘ cụm cùng lúc, không sửa lẻ từng cảnh.
4. Nếu cảnh là khoảnh khắc lắng đọng có chủ đích sau cao trào, giữ nguyên nhịp chậm và nói rõ lý do với người dùng thay vì tự động tăng tốc.
