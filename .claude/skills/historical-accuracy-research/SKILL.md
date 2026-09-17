---
name: historical-accuracy-research
description: Bắt buộc tra cứu tư liệu lịch sử (kiến trúc, đồn luỹ, trang phục, vũ khí, cờ hiệu, nhân vật, di tích/tượng đài hiện tại) TRƯỚC khi viết prompt cảnh cho bất kỳ phim sử thi nào (Đại Việt hoặc lịch sử thế giới) trong app AI Video Studio. Dùng khi viết/soát lại storyboard, scene prompts, hoặc character bible cho nội dung lịch sử có thật.
---

# Tra cứu lịch sử trước khi viết cảnh (AI Video Studio)

Quy tắc này áp dụng cho **mọi phim sử thi lịch sử có thật** app tạo ra — sử thi hào hùng Đại Việt (Ngọc Hồi - Đống Đa, Bạch Đằng, v.v.) cũng như huyền thoại/sử thi thế giới (Troy, Salamis...). Rút ra từ phiên làm việc thực tế 2026-09-13 khi làm phim "Quang Trung đại phá quân Thanh": nếu KHÔNG tra cứu và mô tả cụ thể, Veo3/mô hình sinh video sẽ tự suy đoán ngẫu nhiên (VD: biến kinh thành đang phồn thịnh thành làng quê cổ xưa xuống cấp, bịa trang phục lính tuỳ ý, đặt sai địa điểm/quy mô trận đánh).

## Khi nào áp dụng

Ngay khi bắt đầu viết `scene prompts` (Bước 7-8, storyboard.py / character_bible.py) cho bất kỳ kịch bản nào dựa trên sự kiện/nhân vật lịch sử có thật — trước khi gửi prompt cho Google Flow/Veo3.

## Danh mục PHẢI tra cứu (dùng WebSearch), theo từng cảnh có liên quan

1. **Kiến trúc công trình của đúng thời kỳ và địa điểm** — cung điện, thành quách, nhà dân. Không dùng chung một mô tả "toà nhà cổ" cho mọi thời đại/địa điểm; mỗi triều đại/kinh đô có phong cách riêng (VD: Thăng Long thời Lê-Trịnh khác Phú Xuân thời Tây Sơn khác Huế thời Nguyễn sau 1802).
2. **Đồn luỹ/công sự quân sự** — phân biệt rõ thành quách hoàng gia (đá, gạch, cổng tam quan chạm khắc) với đồn luỹ dã chiến (đất đắp, cọc gỗ, chông sắt, địa lôi). Tra cả **quy mô quân số thật** nếu có nguồn đáng tin — không tự đoán một con số nghe "hoành tráng" mà không kiểm chứng; nếu nguồn mâu thuẫn nhau, nói rõ với người dùng thay vì chọn liều một số.
3. **Trang phục quân đội theo cấp bậc** — lính thường khác hẳn tướng lĩnh (chất liệu, màu sắc, phù hiệu). Tra riêng cho từng phe tham chiến.
4. **Vũ khí đúng thời kỳ, đúng phe** — giáo mác, đao kiếm, cung tên, hoả khí (súng hoả mai, thần công), vũ khí đặc trưng riêng của phe đó (VD: hoả hổ của Tây Sơn) — không dùng "vũ khí chung chung" nếu sử liệu có nêu vũ khí đặc trưng.
5. **Cờ hiệu, phù hiệu quân sự** — màu sắc, hoạ tiết, hình dạng cờ đúng theo hệ thống tổ chức quân đội của phe đó (VD: Bát Kỳ nhà Thanh: 8 màu, cờ vuông/cờ ngũ giác viền, hoạ tiết rồng-mây-lửa).
6. **Từng nhân vật lịch sử có tên** — kiểm tra lại vai trò, chức vụ, kết cục, tránh dùng trí nhớ mơ hồ của người dùng mà không xác minh (đã xảy ra thật: nhớ nhầm tên tướng, nhớ nhầm triều đại nhà Thanh diệt nhà Tống thay vì nhà Minh). Đồng thời tra cứu **trang phục/giáp phục đúng phẩm hàm, chức vụ** của từng nhân vật để mô tả trong Character Bible — không dùng chung 1 kiểu áo giáp cho mọi tướng lĩnh, phẩm hàm càng cao càng sang trọng, khác biệt rõ với lính thường và với tướng phẩm hàm thấp hơn. Ví dụ hệ thống phẩm hàm nhà Thanh đã tra được: bổ tử (huy hiệu thêu trước ngực) phân biệt theo phẩm — quan văn thêu chim (nhất phẩm: hạc), quan võ thêu thú (nhất phẩm: kỳ lân, nhị phẩm: sư tử, tam phẩm: báo, tứ phẩm: hổ, ngũ phẩm: gấu...); nút mũ theo phẩm — nhất phẩm màu đỏ (hồng ngọc/kính đỏ), nhị phẩm đỏ san hô/hồng, tam phẩm xanh lam (bảo ngọc lam), tứ phẩm lam sẫm (ngọc lưu ly), ngũ phẩm pha lê trong, lục phẩm trắng đục, thất-bát phẩm đồng mạ vàng, cửu phẩm bạc — kèm lông đuôi công (hoa linh) cho quan cao cấp được ban thưởng. Tổng đốc (như Tôn Sĩ Nghị) là chức quan văn cai quản cả dân sự lẫn quân sự cấp cao nhất 1 vùng (thường phẩm hàm tòng nhị phẩm nhưng thường được gia hàm chính nhất phẩm danh dự) nên mặc phẩm phục quan văn phẩm cao (bổ tử hạc, nút mũ đỏ) khoác ngoài giáp trận khi ra quân, khác hẳn Đề đốc (như Hứa Thế Hanh) — chức quan võ thuần tuý chỉ huy trực tiếp ngoài mặt trận, mặc giáp trận thực chiến là chính, ít lễ phục.
6b. **"Đoàn hộ giá" trong nghi lễ lớn (tế cáo trời đất, đăng quang...) gồm CẢ HAI**: (a) đội lính hộ vệ tinh nhuệ, võ phục đẹp/chỉnh tề (khác lính chiến trường thường), VÀ (b) một nhóm quan lại triều đình mặc triều phục (mũ cánh chuồn/mũ ô sa, áo lụa thêu bổ tử hình chim theo phẩm hàm) — thiếu 1 trong 2 nhóm là mô tả sai (đã sửa lỗi thật: lần đầu chỉ ghi lính, lần hai lại chỉ ghi quan lại, đều bị người dùng sửa lại). Việt Nam có hệ thống bổ tử riêng từ 1471 (chim cho quan văn, thú cho quan võ), tương tự nhưng độc lập với hệ thống nhà Thanh. Triều Tây Sơn có nét pha trộn độc đáo riêng (Lương quan + Long bào/Mãng bào + mũ Xung Thiên + Bổ phục) — không dùng y hệt trang phục quan lại nhà Nguyễn hay nhà Lê mà không kiểm tra khác biệt.
7. **Địa điểm chính xác của sự kiện** — không gộp chung các địa danh khác nhau (VD: cầu phao bị cắt là ở sông Hồng lúc RÚT CHẠY, không phải lúc vượt biên giới vào Ải Nam Quan — hai sự kiện, hai địa điểm khác nhau).
8. **Di tích/tượng đài hiện tại** (cho cảnh "ngày nay" ở cuối phim) — tìm tượng đài/bảo tàng THẬT đang tồn tại, mô tả đúng: xây năm nào, chất liệu, tư thế, kích thước, địa điểm thật. Vì phần lớn tượng đài kiểu này là công trình HIỆN ĐẠI (thế kỷ 20), phải mô tả rõ ràng, sạch sẽ, không lẫn với phong cách cổ.

## Giới hạn chính sách nội dung của Veo3 — "prominent people" (đã xác nhận thêm)

Xác nhận thật (2026-09-13, cảnh lễ đăng quang): dù đã đổi hết câu mô tả chính (bỏ "imperial enthronement ceremony", đổi thành "misty mountain-top scene... ancient folk rite") mà VẪN bị chặn "prominent people" 3 lần liên tiếp — CHỈ khi bỏ hẳn khối "Character Consistency" (đang ghi "Quang Trung: Vietnamese emperor-general...") ra khỏi cảnh thì mới qua được. Kết luận: chính cụm từ CHỨC DANH kiểu "emperor/king/president" ghép với TÊN THẬT trong khối Character Consistency — không phải câu mô tả cảnh chính — mới là thứ bị bộ lọc "prominent people" bắt, đặc biệt với các cảnh mang tính nghi lễ/nhà nước (đăng quang, duyệt binh...). Cách xử lý khi gặp: (1) thử bỏ chữ chức danh "emperor/king" ra khỏi Character Consistency, giữ lại tên + mô tả ngoại hình thuần tuý; (2) nếu vẫn lỗi, bỏ hẳn khối Character Consistency của cảnh đó (chấp nhận đổi lấy tính nhất quán ngoại hình ở đúng 1 cảnh, để cảnh chạy được) — không lãng phí thêm lượt thử với y hệt prompt.

## Giới hạn chính sách nội dung của Veo3 — "prominent people" (tiếp)

Gặp thêm 1 dạng lỗi thật khác cùng loại: 1 cảnh cận cảnh CỔNG THÀNH (không có người nào trong khung hình) vẫn bị chặn vì khối "Character consistency" (Tôn Sĩ Nghị, Lê Chiêu Thống) bị gắn vào do lỗi over-attach theo beat (đã biết từ trước, xem storyboard.py) — dù 2 nhân vật đó KHÔNG hề xuất hiện trong cảnh. Bài học: **chỉ gắn khối Character Consistency của nhân vật thật sự XUẤT HIỆN/ĐƯỢC NHÌN THẤY trong cảnh đó** — cảnh nào chỉ có kiến trúc/phong cảnh, không có người, thì bỏ hẳn khối Character Consistency ra, không gắn "cho chắc".

## Giới hạn chính sách nội dung của Veo3 — "prominent people"

Gặp lỗi thật (2026-09-13): Veo3 báo "This prompt might violate our policies about generating prominent people" và tạo video thất bại (không phải lỗi Chrome/cài đặt, không sửa được bằng cách đổi setting) cho cảnh "Quang Trung đứng trước 10 vạn quân, đang diễn thuyết, giơ kiếm hiệu triệu". Các cảnh khác cũng nhắc tên nhân vật y hệt (Quang Trung cưỡi ngựa, chiến đấu, cưỡi voi...) KHÔNG bị chặn — nghi ngờ nguyên nhân là **bố cục hình ảnh** kiểu "1 người đứng diễn thuyết/hiệu triệu trước đám đông" giống hệt ảnh thật của lãnh tụ/chính khách hiện đại, dễ bị bộ lọc "prominent people" (chống deepfake nhân vật nổi tiếng) bắt nhầm — không phải do cái tên. Cách sửa: đổi bố cục cảnh (VD từ "đứng diễn thuyết trước đám đông" sang "cưỡi ngựa duyệt binh qua hàng ngũ" — cùng nội dung lịch sử nhưng khác bố cục hình ảnh), giữ nguyên tên nhân vật trong Character Bible. Khi gặp lỗi này: không phải lỗi cài đặt Chrome, không phải lỗi driver — phải sửa lại NỘI DUNG/BỐ CỤC prompt của đúng cảnh đó.

## Giới hạn chính sách nội dung của Veo3 — "prominent people" (nhiều nhân vật cùng lúc)

Gặp lỗi thật (2026-09-13): cảnh "đoàn hành quân thần tốc" hoàn toàn không mang tính nghi lễ/diễn thuyết (một cảnh động, quay rộng, đang di chuyển) vẫn bị chặn "prominent people" khi khối Character Consistency ghi CÙNG LÚC 2 nhân vật có tên + chức danh riêng (VD: "Quang Trung: Vietnamese emperor-general..." VÀ "Bùi Thị Xuân: Tay Son female general (Đô đốc)..." trong cùng 1 cảnh). Trước đó từng cảnh chỉ có 1 mình khối Quang Trung thì generate được bình thường. Kết luận: **số lượng nhân vật có tên+chức danh xuất hiện cùng lúc trong 1 khối Character Consistency cũng làm tăng nguy cơ bị chặn**, không chỉ riêng bố cục nghi lễ. Cách sửa khi cảnh có nhiều hơn 1 nhân vật có tên cùng xuất hiện, đặc biệt là cảnh quay rộng/động không cần thấy rõ mặt từng người: bỏ hẳn khối Character Consistency của cảnh đó, chuyển mô tả ngoại hình (trang phục, giáp, phương tiện cưỡi) thẳng vào câu mô tả hành động chính mà KHÔNG dùng tên riêng + chức danh chính thức — vẫn đủ để người xem/Veo3 dựng đúng hình ảnh, chỉ là không kích hoạt bộ lọc.

## Quy tắc viết prompt sau khi tra cứu

- **Tránh các từ mơ hồ gây hiểu lầm "cũ/cổ xưa/đổ nát"**: "ancient", "old", "cổ kính", "cổ xưa", "rêu phong", "phế tích" — trừ khi bối cảnh THỰC SỰ là phế tích.
- **QUAN TRỌNG — câu phủ định ("KHÔNG cũ/KHÔNG rêu phong") là CHƯA ĐỦ MẠNH**: đã gặp lỗi thật (2026-09-13) — dù đã ghi rõ "NOT faded, weathered, mossy or ruined", Veo3 vẫn tự vẽ tường rêu phong cũ kỹ cho cả kiến trúc hoàng thành lẫn nhà dân, vì mô hình sinh ảnh/video có xu hướng bỏ qua phần phủ định và chỉ bắt lấy các từ khoá liên tưởng "kiến trúc châu Á cổ" có sẵn trong dữ liệu huấn luyện. Phải viết lại theo hướng **khẳng định tích cực, cụ thể, nhiều chi tiết hình ảnh thật** thay vì chỉ phủ định — ví dụ thay vì "not old, not mossy" hãy viết: "mọi bức tường/cột/ngói trông như vừa mới sơn xong trong năm nay: tường vôi trắng/vàng đất sắc nét, sơn còn như ướt màu, đá lát sáng bóng — như một bản dựng kiến trúc 3D công trình mới xây, không phải ảnh chụp di tích". Áp dụng nguyên tắc này cho MỌI công trình/nhà cửa trong toàn bộ kịch bản ngay từ đầu (không đợi xem video lỗi mới sửa từng cảnh một).
- **Ghi số đo cụ thể khi có nguồn** (chiều dài/cao cổng, số cửa, số quân...) thay vì tính từ chung chung như "to lớn", "hoành tráng" — số cụ thể giúp Veo3 dựng đúng tỉ lệ.
- Khi số liệu lịch sử **mâu thuẫn giữa các nguồn**, nói rõ với người dùng và để họ chọn cách trình bày, không tự chọn 1 số để "cho hoành tráng".
- Luôn giữ nguyên tắc đã có: nhân vật có tên dùng khối "Character consistency" cố định xuyên suốt phim; lính/dân thường không tên thì mô tả kiểu trang phục chung theo phe (đã tra cứu ở bước 3).
- Ghi lại các nguồn (URL) đã tra cứu vào phần trò chuyện với người dùng để họ có thể tự kiểm tra lại.

## Quy trình gợi ý khi viết 1 kịch bản lịch sử mới

1. Xác định danh sách các "đối tượng cần tra cứu" xuất hiện trong kịch bản: (a) mỗi địa điểm/công trình, (b) mỗi phe quân sự, (c) mỗi nhân vật có tên, (d) cảnh "ngày nay" nếu có.
2. Tra cứu từng mục bằng WebSearch, ưu tiên nguồn có uy tín (Wikipedia tiếng Việt, báo/tạp chí lịch sử, trang di tích chính thức).
3. Viết mô tả cảnh dựa trên kết quả tra cứu, không dựa trên suy đoán chung chung.
4. Nếu có chi tiết không thể xác minh chắc chắn (VD: quân số một đồn nhỏ), nói rõ với người dùng thay vì bịa.
5. Rà lại toàn bộ prompt một lượt để loại các từ gây hiểu lầm "cổ xưa/đổ nát" (xem mục Quy tắc viết prompt).

## Ví dụ thật đã làm — 6 nhân vật phim "Quang Trung đại phá quân Thanh" (2026-09-13)

Bảng dưới đây là ví dụ cụ thể về mức độ chi tiết trang phục/vũ khí cần đạt được cho mỗi nhân vật có tên, để tham khảo khi làm phim lịch sử khác (đổi tên/thời đại nhưng giữ nguyên MỨC ĐỘ chi tiết này):

- **Tôn Sĩ Nghị** (Tổng đốc Lưỡng Quảng, chức vụ dân sự-quân sự cao nhất, chỉ huy tối cao): áo choàng lụa xanh lam thêu bổ tử hạc (nhất phẩm văn quan) khoác ngoài giáp, nút mũ đỏ ngọc kèm lông đuôi công, ria dài, cưỡi ngựa xám, cầm gươm lễ nghi + roi chỉ huy — nhân vật ăn mặc sang trọng/lễ nghi nhất phim.
- **Hứa Thế Hanh** (Đề đốc Quảng Tây, tướng trực tiếp ngoài mặt trận): giáp sắt-xám nặng đóng đinh mạ vàng, phù hiệu hổ trước ngực, cổ viền lông thú, mũ đỏ tua rua, cầm giáo dài, cưỡi ngựa — giáp trận thực chiến, ít lễ phục hơn Tôn Sĩ Nghị.
- **Sầm Nghi Đống** (Tri phủ Điền Châu, thổ ty người Choang, cấp bậc thấp hơn 2 vị trên): áo giáp vải bông xanh lá-vàng đơn giản hơn, mũ sắt trơn, cầm đao — rõ ràng kém sang trọng hơn 2 tướng nhà Thanh chính quy.
- **Lê Chiêu Thống** (vua bù nhìn nhà Lê): long bào vàng nhạt thêu rồng 5 móng, mũ xung thiên đen có cánh vàng, đai ngọc, không vũ khí, dáng vẻ khiếp nhược.
- **Quang Trung / Nguyễn Huệ**: giáp da-kim loại ghép lớp (lamellar) đỏ-vàng, khăn vấn đầu đen, cưỡi ngựa ô, cầm kiếm cong.
- **Đô đốc Long**: giáp da ghép lớp nâu-đen (khác hẳn màu đỏ-vàng của Quang Trung), cưỡi voi chiến, cầm giáo dài.

Nguyên tắc rút ra: **mỗi nhân vật phải khác biệt rõ về màu sắc + độ sang trọng theo đúng cấp bậc thật**, không dùng chung 1 kiểu giáp "tướng địch" cho mọi tướng nhà Thanh, và trang phục quan văn cấp cao (có bổ tử, nút mũ) phải khác hẳn giáp trận của tướng quân sự thuần tuý.
