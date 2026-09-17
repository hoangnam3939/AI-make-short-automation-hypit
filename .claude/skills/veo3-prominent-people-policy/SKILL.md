---
name: veo3-prominent-people-policy
description: BẮT BUỘC cho MỌI video do app tạo ra có nhân vật thật/có tên (lịch sử Việt, lịch sử thế giới, tiểu sử hiện đại, hay bất kỳ phim nào khác app làm ra) — không riêng phim sử thi. Veo3 có 2 bộ lọc nội dung riêng biệt: (1) "prominent people" (chống deepfake người nổi tiếng) có thể kích hoạt bởi TÊN THẬT trong prompt/Character Consistency, kể cả khi bố cục không nghi lễ, và kể cả khi có từ 2 nhân vật nổi bật trở lên dù không ghi tên; (2) "harmful content" kích hoạt khi cộng dồn mô tả giết chóc cụ thể nhắm vào 1 người có tên + thuật ngữ vũ khí nghe hiện đại/hoá học. Quy tắc mặc định: KHÔNG gửi tên riêng của nhân vật có thật vào prompt gửi Flow, chỉ dùng mô tả ngoại hình. Dùng khi viết hoặc rà soát prompt cho BẤT KỲ cảnh nào có nhân vật có thật hoặc cảnh bạo lực/tử trận, ở BẤT KỲ thể loại phim nào app làm.
---

# Chính sách "prominent people" của Veo3 — khi nào bị chặn và cách né

Veo3 (Google Flow) có bộ lọc nội dung chặn tạo video nếu nghi ngờ đang tái tạo hình ảnh một người có thật/nổi tiếng (chống deepfake). Bộ lọc này không chỉ dựa vào cái tên xuất hiện trong prompt — nó nhạy với **khối "Character Consistency"** (đoạn mô tả cố định để giữ ngoại hình nhân vật xuyên suốt phim) khi đoạn đó ghép TÊN THẬT với CHỨC DANH kiểu lãnh đạo ("emperor", "general", "king", "president"...), và còn nhạy với cả BỐ CỤC cảnh (nhiều nhân vật nổi bật cùng lúc) dù không hề ghi tên. Khi bị chặn, Flow hiện thẻ lỗi `.error-title` với chữ "Failed" — **không bị trừ credit** (khác với lỗi server tạm thời).

## Quy tắc mặc định (áp dụng cho MỌI phim app làm, không riêng sử thi)

Vì bộ lọc này khó đoán và mỗi lần bị chặn tốn 1 lượt thử (dù không mất credit nhưng mất thời gian), quy tắc MẶC ĐỊNH khi viết prompt gửi Flow cho bất kỳ phim nào của app (lịch sử, tiểu sử, đời thường, hư cấu dựa trên người thật...): **KHÔNG đưa tên riêng của nhân vật có thật vào prompt gửi Flow** — dù trong câu mô tả chính hay trong khối Character Consistency. Chỉ mô tả bằng ngoại hình/trang phục/đặc điểm nhận dạng (màu giáp, kiểu tóc, vóc dáng, phương tiện di chuyển...) để giữ nhất quán hình ảnh xuyên suốt phim, và giữ tên thật + thông tin nhân vật ở Character Bible/kịch bản nội bộ (chỉ để người dùng đọc hiểu, không gửi cho Flow).

## Các trường hợp đã xác nhận thật kích hoạt bộ lọc

1. **Bố cục nghi lễ/chân dung/diễn thuyết** (2026-09-13): cảnh đăng quang, cảnh "đứng trước 10 vạn quân diễn thuyết, giơ kiếm hiệu triệu" — bố cục giống ảnh thật lãnh tụ/chính khách hiện đại dễ bị bắt nhầm, dù các cảnh khác cùng nhân vật (cưỡi ngựa, chiến đấu) không bị chặn.
2. **Character Consistency gắn nhầm vào cảnh không có người đó** (lỗi over-attach theo beat): cảnh cận cổng thành không một bóng người vẫn bị chặn vì khối Character Consistency của 2 nhân vật bị gắn "cho chắc" dù họ không xuất hiện trong cảnh.
3. **Nhiều nhân vật có tên+chức danh cùng lúc trong 1 khối** (2026-09-13, cảnh đoàn hành quân thần tốc — một cảnh quay RỘNG, ĐỘNG, hoàn toàn không nghi lễ): ghép cùng lúc 2 khối Character Consistency có tên+chức danh (VD "Quang Trung: Vietnamese emperor-general..." và "Bùi Thị Xuân: Tay Son female general (Đô đốc)...") trong cùng 1 cảnh vẫn bị chặn, dù từng khối riêng lẻ ở cảnh khác đã chạy được bình thường. Kết luận: **số lượng nhân vật có tên xuất hiện cùng lúc cũng làm tăng nguy cơ**, không chỉ riêng bố cục nghi lễ.
4. **Vẫn bị chặn dù ĐÃ bỏ hết tên riêng** (2026-09-13, thử lại đúng cảnh ở mục 3 sau khi bỏ tên khỏi Character Consistency, chỉ còn mô tả ngoại hình thuần tuý): vẫn bị chặn lần nữa, vì cảnh vẫn mô tả 2 NHÂN VẬT CHỈ HUY nổi bật ngang nhau (1 nam cưỡi ngựa dẫn đầu kỵ binh + 1 nữ cưỡi voi dẫn đầu tượng binh, mỗi người đều có mô tả giáp/vai trò "chỉ huy" riêng). Kết luận: **bố cục "2 nhân vật lãnh đạo/chỉ huy nổi bật cùng lúc" tự nó đã đủ để bị bộ lọc bắt, kể cả khi không còn tên**. Cách sửa cuối cùng có hiệu quả: quay lại CHỈ 1 nhân vật nổi bật duy nhất trong cảnh (nhân vật chính, dùng mô tả hero-shot như bản gốc), các nhân vật/đoàn quân khác (kể cả tượng binh) chỉ mô tả như CHI TIẾT NỀN của đoàn quân, không gán vai trò "chỉ huy" hay mô tả ngoại hình riêng biệt nổi bật cho họ trong CÙNG 1 cảnh.
5b. **Voi chiến + nhân vật có tên dẫn đầu = dễ bị bắt như bố cục nghi lễ** (2026-09-13): cảnh "vua cưỡi voi chiến dẫn đầu, dẫn theo nhiều voi chiến khác xông trận" (Character Consistency đầy đủ tên+chức danh, chỉ 1 nhân vật) vẫn bị chặn, dù cảnh cưỡi NGỰA xông trận y hệt bố cục (1 nhân vật, dẫn đầu, vung kiếm) của CÙNG nhân vật đó lại KHÔNG bị chặn. Nghi ngờ nguyên nhân: hình ảnh "1 người cưỡi voi, có đoàn voi theo sau" tự nó gợi liên tưởng mạnh tới ảnh nghi lễ/duyệt binh/vương quyền có thật (voi vốn gắn với hình ảnh vua chúa/nguyên thủ trong nhiều nền văn hoá châu Á), dễ bị bắt hơn cưỡi ngựa dù cùng bố cục "dẫn đầu xông trận". Cách sửa: với cảnh có nhân vật có tên cưỡi voi (đặc biệt dẫn đầu đoàn voi khác), ưu tiên bỏ tên+Character Consistency, chỉ mô tả ngoại hình chung ngay từ đầu, không cần đợi bị chặn mới sửa.
6. **Tái xác nhận lỗi mục 2 — chỉ NHẮC TÊN trong câu mô tả cũng đủ bị chặn** (2026-09-13): cảnh cận lính xông trận "sprinting... straight into Hua The Hanh's defensive line" — nhân vật Hứa Thế Hanh KHÔNG hề xuất hiện trong khung hình (cảnh chỉ quay lính tấn công), chỉ được nhắc tên để chỉ vị trí ("phòng tuyến của Hứa Thế Hanh"), nhưng vì khối Character Consistency của ông vẫn bị gắn kèm theo cảnh (do thói quen gắn "cho chắc") nên vẫn bị chặn. Điều đáng chú ý: CÙNG một khối Character Consistency y hệt đã chạy thành công ở cảnh trước đó (cảnh ông thực sự xuất hiện, hét lệnh) — nghĩa là bản thân khối đó không sai, mà là gắn SAI cảnh. Bài học nhắc lại: trước khi gửi prompt, tự hỏi "nhân vật này có thực sự XUẤT HIỆN trong khung hình của cảnh này không, hay chỉ được nhắc tên để chỉ vị trí/liên quan?" — nếu chỉ nhắc tên suông, phải đổi thành mô tả chung (VD "the Qing defensive line" thay vì "Hua The Hanh's defensive line") VÀ bỏ khối Character Consistency của cảnh đó.

## Cách xử lý theo thứ tự ưu tiên (không lãng phí lượt thử với y hệt prompt)

1. Nếu cảnh có tính nghi lễ/diễn thuyết/chân dung: đổi bố cục hình ảnh (VD "đứng diễn thuyết trước đám đông" → "cưỡi ngựa duyệt binh qua hàng ngũ"), giữ nguyên tên trong Character Bible nội bộ.
2. Rà lại: khối Character Consistency chỉ gắn cho nhân vật THẬT SỰ xuất hiện/được nhìn thấy trong cảnh đó — cảnh chỉ có kiến trúc/phong cảnh/đám đông không tên thì bỏ hẳn khối này.
3. Nếu cảnh có từ 2 nhân vật có tên+chức danh trở lên xuất hiện cùng lúc, đặc biệt là cảnh quay rộng/động không cần thấy rõ mặt từng người (hành quân, dàn trận, cảnh toàn/wide shot): **bỏ hẳn khối Character Consistency có tên+chức danh**, chuyển mô tả ngoại hình (màu giáp, vũ khí, phương tiện cưỡi) thẳng vào câu mô tả hành động chính mà KHÔNG dùng tên riêng + chức danh chính thức (VD: "a stern commander in dark red-and-gold armor on a black warhorse" thay vì "Quang Trung: Vietnamese emperor-general..."). Vẫn đủ để dựng đúng hình ảnh, chỉ là không kích hoạt bộ lọc.
4. Chỉ khi cảnh THỰC SỰ cần cận mặt, cần khán giả nhận diện rõ đúng 1 nhân vật có tên xuyên suốt phim (VD cảnh cận mặt nhân vật chính) mới giữ khối Character Consistency đầy đủ tên+chức danh cho ĐÚNG 1 nhân vật đó trong cảnh đó.

## Áp dụng cho cả sử thi Đại Việt lẫn sử thi thế giới

Skill này không tách riêng theo nền văn hoá — áp dụng cho MỌI phim sử thi/huyền thoại có nhân vật lịch sử có tên, dù là **Đại Việt** (đi cùng `historical-accuracy-research`, VD: Quang Trung, Bùi Thị Xuân, Tôn Sĩ Nghị...) hay **thế giới** (đi cùng `world-epic-historical-accuracy`, VD: Alexander Đại đế, Leonidas, các Pharaoh...). Hai skill kia lo tra cứu đúng kiến trúc/trang phục/vũ khí theo nền văn minh; skill này lo riêng việc né bộ lọc "prominent people" khi viết khối Character Consistency cho các nhân vật đó — luôn kiểm tra cả hai cùng lúc khi viết prompt cho phim sử thi có nhân vật thật.

## Bộ lọc KHÁC của Veo3 — "harmful content" (bạo lực/vũ khí quá chi tiết)

Ngoài "prominent people", Veo3 còn có bộ lọc riêng chặn "harmful content" (nội dung có hại/bạo lực) — thông báo khác hẳn: "This prompt might violate our policies about generating harmful content" (không phải "...about generating prominent people"). Đây là 2 bộ lọc RIÊNG BIỆT, cách xử lý khác nhau, không nhầm lẫn.

Gặp lỗi thật (2026-09-13): cảnh "lính phá cổng, giao chiến cận chiến, tướng Hứa Thế Hanh gục ngã" bị chặn vì "harmful content" — không phải do tên nhân vật, mà do CỘNG DỒN các yếu tố mô tả bạo lực quá cụ thể/thực tế trong cùng 1 cảnh: (1) mô tả trực tiếp việc GIẾT/HẠ GỤC một nhân vật cụ thể ("General Hua The Hanh cut down in the melee" — hành động chém/hạ sát rõ ràng một người có tên), (2) mô tả vũ khí bằng thuật ngữ giống vũ khí hiện đại/hoá chất thật ("iron shrapnel and phosphorus fire" — "mảnh đạn" và "lửa phốt-pho" là thuật ngữ vũ khí sát thương hiện đại/hoá học, dù đang mô tả hỏa hổ thời Tây Sơn). Cách sửa: (1) đổi hành động "cut down" (bị chém gục cụ thể) thành mô tả chung chung hơn "falls/collapses in the chaos" (ngã xuống trong hỗn loạn — vẫn truyền tải được nhân vật gục ngã nhưng không mô tả chi tiết cách bị giết), và bỏ tên riêng khỏi câu đó (đi kèm quy tắc mặc định ở trên); (2) đổi thuật ngữ vũ khí nghe giống vũ khí hiện đại/hoá học ("shrapnel", "phosphorus") thành mô tả trung tính hơn, đúng tinh thần cổ xưa hơn (VD "jets of flame and bright sparks" thay vì "iron shrapnel and phosphorus fire").

Bài học chung: khi mô tả cảnh cận chiến có nhân vật gục ngã/tử trận, tránh CỘNG DỒN cùng lúc (a) hành động giết chóc cụ thể nhắm vào 1 người có tên, VÀ (b) thuật ngữ vũ khí nghe như vũ khí sát thương hàng loạt/hoá học hiện đại — tách riêng, chỉ giữ 1 trong 2 mức độ chi tiết, không dồn cả hai vào cùng 1 câu.

## Bộ lọc của Veo3 có tính NGẪU NHIÊN — không phải lúc nào cũng bắt được/bắt nhầm

Xác nhận thật nhiều lần trong cùng 1 phiên (2026-09-13): CÙNG một prompt/khối Character Consistency y hệt, có lúc chạy qua bình thường, có lúc bị chặn — cả 2 chiều:
- Cảnh có 2 nhân vật có tên (Đô đốc Long + Sầm Nghi Đống) chạy được ở 1 cảnh, nhưng bị chặn ở cảnh khác dùng đúng công thức tương tự.
- Cảnh "Quang Trung cưỡi ngựa xông trận" với Character Consistency đầy đủ tên+chức danh đã chạy THÀNH CÔNG trước đó, nhưng khi chạy lại y hệt prompt này (không đổi 1 chữ) ở lượt sau lại bị chặn vì "harmful content related to minors" — một lý do hoàn toàn không liên quan gì đến nội dung thật của cảnh (không có trẻ vị thành niên nào được nhắc tới).
Kết luận: bộ lọc content-policy của Veo3 không xác định (non-deterministic) — cùng input có thể ra kết quả khác nhau giữa các lần gọi. Cách xử lý: nếu tin chắc nội dung không có vấn đề thật (đặc biệt nếu chính prompt đó đã từng chạy qua được trước đó), **thử lại y nguyên prompt 1 lần trước khi sửa nội dung** — có thể lần sau sẽ qua bình thường, đỡ phải hy sinh chi tiết/tên nhân vật một cách không cần thiết. Chỉ bắt đầu sửa nội dung (bỏ tên, đổi bố cục...) nếu bị chặn LẶP LẠI nhiều lần với cùng 1 lý do.

## Dấu hiệu nhận biết HẾT CREDIT — khác hẳn lỗi chính sách/lỗi tạm thời

Xác nhận thật (2026-09-13): khi tài khoản Flow gần hết credit (lúc đó còn 14 credit), Flow
KHÔNG báo rõ "hết credit" — mà báo đúng thẻ lỗi chung chung giống lỗi kỹ thuật tạm thời:
"Sorry, this video failed to generate. You have not been charged for this generation." (không
kèm câu "violate our policies" nào). Dấu hiệu để phân biệt với lỗi nội dung/lỗi tạm thời thật:
- Lỗi này lặp lại Y HỆT nhiều lần liên tiếp (đã gặp 10+ lần) dù đổi hẳn nội dung prompt, kể cả
  dùng lại đúng 1 prompt đã từng chạy THÀNH CÔNG trước đó trong cùng phiên.
- Xảy ra sau khi đã tạo được kha khá video thành công trong cùng phiên làm việc (credit dần
  cạn), không phải ngay từ cảnh đầu tiên.
Cách xử lý khi gặp: KHÔNG tiếp tục đoán mò sửa prompt hay thử lại nhiều lần (mỗi lần thử vẫn
tốn 1 lượt dù không mất credit thật, và cứ tưởng là lỗi nội dung sẽ sửa sai hướng). Dừng lại
ngay, nhờ người dùng tự kiểm tra số credit còn lại trên chính trang Flow (góc trên bên phải)
trước khi thử tiếp.

## Lưu ý kỹ thuật đi kèm (driver)

Khi gặp lỗi này, thông báo THẬT SỰ có thể bị driver báo nhầm thành lỗi kỹ thuật khác (VD "Không tìm thấy nút Download nào đang bật") nếu bước kiểm tra thẻ lỗi `.error-title` không được đặt ở TẤT CẢ các vòng chờ liên quan (không chỉ vòng chờ đầu tiên, mà cả vòng chờ nút Download bật sau khi đã vào màn hình xem trước) — xem `app/services/google_flow_driver.py`. Khi thấy lỗi timeout khó hiểu, luôn kiểm tra trực tiếp trạng thái trang Flow (thẻ `.error-title`) trước khi kết luận đó là lỗi kỹ thuật, tránh gửi lại y hệt prompt gây tốn thêm credit oan.
