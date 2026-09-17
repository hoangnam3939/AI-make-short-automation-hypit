---
name: sfx-mixing-safety
description: BẮT BUỘC khi thực hiện Bước 13 (lồng hiệu ứng âm thanh nền vào video hoàn chỉnh) cho MỌI video app làm ra — không riêng phim sử thi. Phòng 4 lỗi thật đã gặp: (1) file SFX tải về có thể dài hơn nhiều phút, nếu không cắt ngắn đúng bằng độ dài đoạn sẽ kêu tràn sang các đoạn sau; (2) hiệu ứng âm thanh nền được nhân âm lượng lên mà không tăng giọng đọc tương ứng sẽ làm giọng đọc bị nuốt mất; (3) so khớp từ khoá đơn giản có thể chọn nhầm hiệu ứng không phù hợp ngữ cảnh (VD tiếng chim cho cảnh tiệc pháo hoa) chỉ vì trùng 1 từ khoá phụ; (4) chọn SFX theo cả ĐOẠN LỜI DẪN thay vì theo TỪNG CẢNH storyboard khiến hành động cụ thể (ngựa phi, đoàn quân hành quân, vượt sông...) không có đúng tiếng động của nó. Dùng khi viết hoặc rà soát code Bước 13 cho bất kỳ video nào.
---

# An toàn khi lồng hiệu ứng âm thanh nền (Bước 13)

Rút ra từ phản hồi thật của người dùng (2026-09-13) khi nghe thử video hoàn chỉnh "Quang Trung đại phá quân Thanh": "tiếng chim kêu khắp video cho buồn cười quá" và "âm thanh người dẫn chuyện... từ 25s trở đi thì nhỏ xíu, chỉ còn nghe âm thanh hiệu ứng nền".

## Lỗi 1 — File SFX tải về có thể dài hơn rất nhiều so với đoạn cần dùng

File hiệu ứng âm thanh tải từ nguồn ngoài (VD tiengdong.com) không có độ dài cố định — có file chỉ 0.5 giây, có file dài tới **377 giây (hơn 6 phút)**. Nếu chỉ đặt `adelay` (thời điểm bắt đầu) mà KHÔNG cắt ngắn (`atrim`) về đúng độ dài của đoạn lời dẫn tương ứng, hiệu ứng sẽ kêu liên tục xuyên suốt nhiều đoạn phía sau, không phải chỉ đúng đoạn được gán cho.

**Bắt buộc**: mỗi SFX phải được `atrim=0:<độ_dài_đoạn>` (dùng đúng độ dài của đoạn/beat mà nó được gán, không phải độ dài gốc của file), kèm `afade=t=out:st=<độ_dài_đoạn-0.4>:d=0.4` để tránh bị cắt cụt nghe giật.

## Lỗi 2 — Tăng âm lượng SFX mà không tăng giọng đọc tương ứng sẽ nuốt mất giọng đọc

Bộ lọc `amix` của ffmpeg mặc định (`normalize=1`) tự động chia đều âm lượng giữa các nguồn đầu vào để tránh vỡ tiếng. Nếu SFX được nhân âm lượng lên (VD gấp đôi theo yêu cầu người dùng) mà giọng đọc gốc không được tăng theo, giọng đọc sẽ bị lấn át hoàn toàn ở những đoạn SFX to.

**Bắt buộc**: (1) luôn nhân thêm âm lượng cho chính giọng đọc trước khi mix (không chỉ tăng SFX một chiều); (2) tắt `normalize` của `amix` (để 2 mức âm lượng đã chủ động đặt không bị tự động san bằng lại), nhưng phải thêm `alimiter` ngay sau để chặn vỡ tiếng khi cộng dồn nhiều nguồn cùng lúc.

## Lỗi 3 — So khớp từ khoá đơn giản dễ chọn nhầm hiệu ứng lạc quẻ ngữ cảnh

Thuật toán chọn SFX theo số từ khoá trùng tên bài (không dùng AI) có thể chọn nhầm 1 hiệu ứng chỉ trùng đúng 1 từ khoá phụ, dù toàn bộ nội dung hiệu ứng đó hoàn toàn lạc chủ đề. Ví dụ thật: câu hỏi "tiệc rượu pháo hoa đêm giao thừa" khớp với hiệu ứng tên "Tiếng chim Hút Mật Xác Pháo" (chỉ trùng từ "pháo"), khiến tiếng CHIM được dùng cho cảnh TIỆC MỪNG NĂM MỚI.

**Bắt buộc**: mặc định LOẠI HẲN các hiệu ứng "tiếng chim/chim chóc" khỏi kết quả so khớp (`allow_birds=False` mặc định trong `find_best_sfx`), CHỈ cho phép khi câu hỏi/ngữ cảnh thực sự là cảnh rừng núi/thiên nhiên hoang dã (`allow_birds=True`) — người dùng xác nhận rõ: "tiếng chim thì cũng có thể có nhưng chỉ những lúc ở những cảnh rừng núi thôi còn những chỗ khác thì không nên có". Cân nhắc áp dụng nguyên tắc tương tự (loại trừ mặc định, chỉ cho phép đúng ngữ cảnh) cho các loại âm thanh "dễ lạc quẻ" khác nếu phát hiện thêm qua thực tế sử dụng.

## Lỗi 4 — Chọn SFX theo cả đoạn lời dẫn thay vì theo từng cảnh storyboard

Rút ra từ phản hồi thật của người dùng (2026-09-13) khi xem lại video "Quang Trung đại phá quân Thanh": "ngựa phi thì tôi không thấy tiếng vó ngựa", "đoàn quân đi thì phải nghe tiếng bước chân rầm rập". Kiểm tra thật: bản đầu tiên của `apply_step13_sfx()` chỉ nhận vào **1 hiệu ứng cho CẢ MỘT ĐOẠN LỜI DẪN** (VD đoạn "HƯỚNG DẪN" dài 42 giây gồm 5 cảnh storyboard khác nội dung nhau: hành quân, vượt sông, kỵ binh+voi xung phong...) — dù trong đoạn đó có cảnh ngựa phi rõ ràng, SFX chung của cả đoạn không hề nhắc tới tiếng vó ngựa vì câu tìm kiếm chỉ mô tả chung chung cho cả đoạn.

**Bắt buộc**: chọn SFX theo **ĐÚNG TỪNG CẢNH storyboard** (đơn vị ~8 giây, không phải đơn vị đoạn lời dẫn dài hơn), và cho phép **NHIỀU LỚP** âm thanh chồng nhau trong cùng 1 cảnh (`ScenePlan.layers: list[SfxLayer]`) — 1 cảnh có ngựa+voi+bộ binh cùng xung trận cần cả tiếng vó ngựa, tiếng chân voi, tiếng hò hét cùng lúc, không chỉ 1 file duy nhất. Dùng `llm.suggest_sfx_layers()` để Claude tự đọc prompt hình ảnh của từng cảnh và đề xuất đúng các lớp cần thiết, thay vì 1 người tự gõ tay 1 câu tìm kiếm chung cho cả đoạn (xem `app/services/sfx_sourcing.py`).

**Lưu ý quan trọng liên quan (chưa sửa, thuộc phạm vi Bước 6-10 chứ không phải Bước 13)**: vì Bước 10 hiện ghép video theo ĐÚNG ĐỘ DÀI GIỌNG ĐỌC của cả đoạn (không phải theo từng cảnh), có trường hợp thật một phần cảnh storyboard **bị cắt mất hoàn toàn, không hề xuất hiện trên màn hình** (giọng đọc đoạn đó ngắn hơn nhiều so với tổng thời lượng các cảnh Flow đã tạo cho đoạn đó). Khi tính offset/độ dài hiển thị thật của mỗi cảnh để gán SFX (Bước 13), PHẢI tính theo đúng thời lượng ĐÃ BỊ CẮT/LẶP thật sự trong video cuối (đo bằng ffprobe trên file đã dựng), KHÔNG dùng thẳng start/end gốc trong dữ liệu storyboard — nếu không, SFX sẽ được gán cho cả những cảnh người xem không bao giờ thấy.

## Lỗi 5 — Trùng 1 âm tiết trong từ láy có thể khớp nhầm sang chủ đề hoàn toàn khác

Rút ra từ phản hồi thật của người dùng (2026-09-13): video Quang Trung bị lẫn tiếng "Nam Mô A Di Đà Phật" (tụng niệm Phật giáo) vào giữa cảnh chiến trận/hành quân. Nguyên nhân: câu tìm kiếm "cờ phần phật trong gió" (mô tả tiếng cờ bay, từ láy "phần phật" không liên quan tôn giáo) bị tách thành 2 từ riêng theo đúng chính tả tiếng Việt (cách nhau dấu cách) — từ "phật" trong đó trùng khớp với chữ "Phật" trong tên hiệu ứng "Tiếng Niệm Phật 6 chữ", khiến thuật toán so khớp từ khoá đơn giản (không hiểu ngữ nghĩa) chọn nhầm.

**Bắt buộc**: loại trừ mặc định các hiệu ứng có "niệm phật" trong tên khỏi kết quả so khớp (`find_best_sfx`) — cùng nguyên tắc với Lỗi 3 (tiếng chim). Tổng quát hơn: bất kỳ khi nào phát hiện qua thực tế sử dụng 1 từ/âm tiết dùng chung giữa 2 chủ đề hoàn toàn khác nhau (VD từ láy tiếng Việt trùng âm với danh từ riêng/tôn giáo), nên thêm vào danh sách loại trừ mặc định thay vì cố sửa thuật toán so khớp cho từng trường hợp.

## Áp dụng thực tế

Sau khi lồng SFX vào bất kỳ video nào, LUÔN nghe thử toàn bộ (không chỉ xem qua) trước khi coi là hoàn tất — hầu hết các lỗi trên (SFX kêu tràn lan, giọng đọc bị nuốt, SFX lạc cảnh) chỉ phát hiện được khi nghe/xem hết cả video, không thấy được qua đọc code.
