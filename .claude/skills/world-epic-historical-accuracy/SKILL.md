---
name: world-epic-historical-accuracy
description: Bắt buộc tra cứu tư liệu lịch sử/khảo cổ (kiến trúc, thành luỹ, trang phục-giáp trụ theo cấp bậc, vũ khí, cờ hiệu/huy hiệu, nhân vật, di tích/tượng đài hiện tại) TRƯỚC khi viết prompt cảnh cho phim sử thi/huyền thoại THẾ GIỚI (Hy Lạp, La Mã, Ba Tư, Ai Cập, Bắc Âu...) trong app AI Video Studio. Song song với historical-accuracy-research (dành cho sử thi Đại Việt) — dùng khi viết/soát storyboard, scene prompts, character bible cho nội dung lịch sử/huyền thoại thế giới.
---

# Tra cứu lịch sử trước khi viết cảnh — Sử thi/huyền thoại thế giới (AI Video Studio)

Đây là bản song song của [[historical-accuracy-research]] (dành riêng cho sử thi Đại Việt), áp dụng cho **sử thi và huyền thoại thế giới** — Troy, Salamis, Sparta/Ba Tư, La Mã, Ai Cập, Bắc Âu (Viking), Tam Quốc, v.v. Cùng một bài học rút ra 2026-09-13: nếu KHÔNG tra cứu và mô tả cụ thể theo đúng nền văn minh/thời kỳ, Veo3 sẽ tự suy đoán ngẫu nhiên hoặc trộn lẫn phong cách sai thời đại (VD: giáp La Mã lẫn vào cảnh Hy Lạp cổ đại, kiến trúc Ai Cập bị vẽ thành phế tích dù đang là kinh đô đương thời phồn thịnh).

## Khi nào áp dụng

Ngay khi bắt đầu viết `scene prompts` (Bước 7-8, storyboard.py / character_bible.py) cho bất kỳ kịch bản nào dựa trên sự kiện/nhân vật lịch sử hoặc huyền thoại có nguồn gốc thế giới (đã dùng ở 2 trong 4 pipeline nền tảng của app: Troy, Salamis — xem run-video-pipeline skill) — trước khi gửi prompt cho Google Flow/Veo3.

## Khác biệt quan trọng so với sử thi Việt Nam

- **Xác định đúng NỀN VĂN MINH + GIAI ĐOẠN cụ thể trước tiên**, không dùng chung "phong cách cổ đại" mơ hồ: Hy Lạp Mycenaean (thời Troy, ~1200 TCN) khác hẳn Hy Lạp cổ điển (thời Salamis, 480 TCN); La Mã Cộng hoà khác La Mã Đế chế; Ai Cập Cổ vương quốc khác Tân vương quốc. Mỗi giai đoạn có kiến trúc, giáp trụ, vũ khí riêng — tra đúng giai đoạn, không gộp chung.
- Với các sự kiện **bán huyền thoại/sử thi truyền miệng** (Troy, thần thoại Bắc Âu...), sử liệu khảo cổ thật có thể ít hoặc mâu thuẫn với mô tả trong sử thi gốc (Iliad, saga...) — nói rõ với người dùng: đây là dựng theo khảo cổ học thật hay theo hình dung của sử thi gốc, không tự ý trộn lẫn hai nguồn mà không báo trước.
- Một số nền văn minh có hệ thống ghi chép tốt (La Mã, Ai Cập — có tranh tường, tượng, văn bản) trong khi số khác gần như chỉ có suy luận khảo cổ (Troy thời đại đồ đồng) — mức độ chắc chắn của tra cứu sẽ khác nhau, cần nói rõ mức độ tin cậy.

## Danh mục PHẢI tra cứu (dùng WebSearch), theo từng cảnh có liên quan

1. **Kiến trúc đúng nền văn minh + giai đoạn + địa điểm** — cung điện, thành luỹ, đền đài, nhà dân. Không dùng phong cách "cổ đại chung chung"; mỗi nền văn minh/giai đoạn có vật liệu, hoạ tiết, tỉ lệ riêng (đá vôi Mycenaean khác đá cẩm thạch Hy Lạp cổ điển khác gạch nung Lưỡng Hà).
2. **Thành luỹ/công sự quân sự** — phân biệt thành đá kiên cố (VD: tường thành Troy nhiều lớp) với trại lính dã chiến; tra quy mô quân số nếu có nguồn, nói rõ khi các nguồn/sử thi mâu thuẫn nhau thay vì tự chọn số "cho hoành tráng".
3. **Trang phục/giáp trụ quân đội theo cấp bậc VÀ theo phe/nền văn minh** — lính thường khác hẳn tướng lĩnh/quý tộc; mỗi nền văn minh có kiểu giáp đặc trưng (VD: giáp đồng "bell cuirass" Hy Lạp cổ điển, khiên tròn hoplite; giáp lamellar/vảy cá Ba Tư Immortals; giáp lorica La Mã). Tra riêng cho từng phe tham chiến, không dùng chung 1 kiểu giáp.
4. **Vũ khí đúng thời kỳ, đúng nền văn minh** — giáo dài (dory Hy Lạp, sarissa Macedonia), kiếm ngắn (xiphos, gladius), cung tên (cung hỗn hợp Ba Tư/Scythia), khiên (aspis/hoplon tròn, scutum chữ nhật La Mã) — không dùng "kiếm giáo chung chung" nếu nền văn minh đó có vũ khí đặc trưng đã biết rõ.
5. **Cờ hiệu, huy hiệu, biểu tượng quân sự/hoàng gia** — La Mã có "aquila" (đại bàng quân đoàn) và "vexillum"; Ba Tư có cờ hiệu hoàng gia riêng; mỗi thành bang Hy Lạp có biểu tượng khiên riêng (Sparta: chữ Lambda Λ). Tra đúng biểu tượng của phe/thành bang cụ thể, không bịa hoạ tiết.
6. **Từng nhân vật lịch sử/huyền thoại có tên** — kiểm tra vai trò, địa vị, kết cục theo cả nguồn sử liệu VÀ nguồn sử thi gốc (nếu khác nhau, nói rõ đang theo nguồn nào). Tra trang phục/giáp trụ đúng địa vị (vua/tướng quân/chiến binh thường) để đưa vào Character Bible — địa vị càng cao, giáp trụ/trang sức càng cầu kỳ, khác biệt rõ với chiến binh thường.
7. **Địa điểm địa lý chính xác của sự kiện** — không gộp chung các địa danh/trận đánh khác nhau trong cùng cuộc chiến (VD: trận trên bộ khác trận hải chiến, diễn ra ở toạ độ khác nhau, cách nhau về thời gian).
8. **Di tích/tượng đài/bảo tàng hiện tại** (cho cảnh "ngày nay" ở cuối phim, nếu có) — tìm địa điểm khảo cổ/tượng đài/bảo tàng THẬT đang tồn tại (VD: di chỉ khảo cổ Troy ở Hisarlik Thổ Nhĩ Kỳ, bảo tàng Acropolis Athens), mô tả đúng hiện trạng thật (di tích khảo cổ thật SẼ có dấu vết thời gian — khác với tượng đài hiện đại xây riêng để tưởng niệm, cần phân biệt rõ 2 loại này khi mô tả).

## Quy tắc viết prompt sau khi tra cứu

- **Tránh từ mơ hồ gây hiểu lầm "cổ xưa/đổ nát"** khi mô tả một thành phố/cung điện ĐANG hoạt động, phồn thịnh trong câu chuyện (thời điểm diễn ra sự kiện) — mặc định ghi rõ "màu sắc sống động, công trình đang được sử dụng/bảo trì, KHÔNG phải phế tích" trừ khi bối cảnh thật sự là phế tích/di chỉ khảo cổ (như cảnh "ngày nay").
- **Ghi số đo/quy mô cụ thể khi có nguồn** (chiều cao tường thành, số quân, số tàu chiến...) thay vì tính từ chung chung.
- Khi số liệu giữa các nguồn **mâu thuẫn** (thường gặp với sự kiện bán huyền thoại), nói rõ với người dùng, để họ chọn cách trình bày.
- Nhân vật có tên dùng khối "Character consistency" cố định xuyên suốt phim (giữ nguyên quy ước đã có); chiến binh/dân thường không tên mô tả kiểu trang phục chung theo phe/nền văn minh (đã tra cứu ở mục 3).
- Ghi lại nguồn (URL) đã tra cứu vào phần trò chuyện với người dùng.

## Quy trình gợi ý khi viết 1 kịch bản sử thi thế giới mới

1. Xác định: (a) nền văn minh + giai đoạn chính xác, (b) mỗi địa điểm/công trình xuất hiện, (c) mỗi phe quân sự/thành bang, (d) mỗi nhân vật có tên, (e) cảnh "ngày nay" nếu có (di chỉ khảo cổ hay tượng đài hiện đại).
2. Tra cứu từng mục bằng WebSearch, ưu tiên nguồn uy tín (Wikipedia, bảo tàng khảo cổ, đại học/viện nghiên cứu lịch sử).
3. Với nội dung bán huyền thoại, xác định rõ đang dựng theo khảo cổ học hay theo sử thi gốc — báo người dùng nếu hai nguồn khác nhau.
4. Viết mô tả cảnh dựa trên kết quả tra cứu, không suy đoán chung chung kiểu "cổ đại".
5. Rà lại toàn bộ prompt để loại từ gây hiểu lầm "cổ xưa/đổ nát" cho các công trình đang hoạt động trong câu chuyện.

## Ví dụ tham khảo nhanh (không thay thế việc tra cứu thật cho từng dự án)

- **Troy (thời đại đồ đồng Mycenaean, ~1200 TCN)**: giáp đồng tấm lớn kiểu "Dendra panoply", mũ trụ răng lợn rừng (boar's tusk helmet), khiên hình số 8 hoặc khiên tháp lớn, giáo dài, kiếm đồng ngắn — KHÁC hẳn giáp Hy Lạp cổ điển (bell cuirass, khiên tròn hoplon) ra đời gần 1000 năm sau.
- **Salamis (Hy Lạp cổ điển, 480 TCN)**: hoplite Hy Lạp — giáp ngực đồng/lanh nhiều lớp (linothorax), khiên tròn hoplon, giáo dory, kiếm ngắn xiphos; đối lập là quân Ba Tư — giáp vảy, khiên liễu gai (wicker), cung phức hợp, đội "Bất tử" (Immortals) mặc lễ phục sặc sỡ đặc trưng.
- Nguyên tắc chung: **không dùng cùng 1 kiểu giáp-vũ khí cho hai nền văn minh/giai đoạn khác nhau trong cùng 1 phim**, mỗi phe phải tra riêng.
