---
name: narration-length-budget
description: BẮT BUỘC khi viết hoặc soát lại kịch bản lời đọc (Bước 5) cho MỌI video app làm ra — (1) kịch bản CHỈ được là lời đọc thuần tuý (voice-over), TUYỆT ĐỐI KHÔNG được lẫn mô tả hình ảnh/chỉ dẫn quay phim dưới bất kỳ hình thức nào (không dùng ngoặc đơn, không dùng dấu *, không viết kiểu "(Hình ảnh: ...)") — app đưa THẲNG văn bản sau mỗi timestamp vào máy đọc giọng nói (TTS), lẫn vào là bị đọc to ra tiếng; (2) tổng độ dài lời đọc phải vừa khít thời lượng video mục tiêu ở tốc độ đọc tự nhiên (~150 từ/phút), DƯ RA 10-15% làm khoảng lặng cho hiệu ứng âm thanh nền/hành động chen vào, không phải đoạn nào cũng cần lời — viết dài hơn khiến hình ảnh phải đứng hình/lặp lại chờ khi lồng giọng đọc thật. Dùng khi gọi `script_writer.generate_script()`, khi tự tay viết/sửa kịch bản qua chat, hoặc khi soát lại 1 kịch bản người dùng đã có sẵn trước khi đưa vào app.
---

# Kịch bản (Bước 5) chỉ là lời đọc, và phải vừa khít thời lượng video — không dài hơn, không lẫn chỉ dẫn hình ảnh

Rút ra từ phản hồi thật của người dùng (2026-09-15, kịch bản "Trận Kadesh" 35 cảnh/280 giây): người dùng tự nhận thấy "lời đọc quá dài cho video full dài 280 giây" và yêu cầu phân tích lại. Đếm thật bằng script cho thấy 2 lỗi:

1. **Tổng lời đọc dài hơn cả khung thời gian đã ghi.** 830 từ, ở tốc độ đọc phim tài liệu tự nhiên (2.8 từ/giây) cần tới 296 giây — vượt cả 300 giây khung kịch bản tự ghi lẫn 280 giây mục tiêu, không có chỗ dư nào cho hiệu ứng âm thanh.
2. **Kịch bản có lẫn dòng mô tả hình ảnh kiểu `*(Hình ảnh: ...)*` ngay trong khối lời đọc.** `parse_script_beats()` (`app/services/storyboard.py`) lấy NGUYÊN VĂN toàn bộ văn bản giữa 2 mốc `[MM:SS-MM:SS]` làm lời đọc — không tự lọc bỏ dòng mô tả hình ảnh. Nếu dán thẳng kịch bản có dòng này vào app, TTS sẽ đọc to luôn câu "Hình ảnh: đoàn quân Ai Cập..." ra tiếng, y hệt lỗi "đọc to luôn cả chữ Hook" đã từng gặp trước đây.

## Cơ chế lỗi gốc, và vì sao dễ tái diễn

Hệ thống prompt cũ của `generate_script()` (`app/services/script_writer.py`) từng viết: *"Chỉ viết phần lời đọc (voice-over) + **mô tả ngắn hành động hình ảnh cho mỗi đoạn**"* — tự mâu thuẫn với chính câu ngay sau đó dặn "chỉ được có lời thoại thật sự". Câu "mô tả ngắn hành động hình ảnh" này chính là kẽ hở khiến Claude (dù gọi qua API hay viết tay trong chat) tự nhiên thêm dòng `(Hình ảnh: ...)` vào — đúng như một biên kịch thật sẽ làm khi soạn kịch bản phim, nhưng SAI với cách app này xử lý văn bản.

Việc mô tả hình ảnh cho từng cảnh **đã có sẵn ở bước sau** — `generate_scene_prompts()` (Bước 6-7, cùng file `storyboard.py`) tự đọc `source_text` (chính đoạn lời đọc) rồi tự suy ra hình ảnh phù hợp qua Claude, không cần và không nên có sẵn mô tả hình ảnh nhồi trong lời đọc.

## Quy tắc bắt buộc

1. **Kịch bản Bước 5 CHỈ được chứa lời đọc thuần tuý.** Không dấu ngoặc đơn mô tả cảnh, không dấu `*`, không "(Hình ảnh: ...)", không chỉ dẫn góc máy/chuyển cảnh — bất kỳ hình thức chú thích sản xuất nào khác ngoài câu thoại thật sự đều SAI, vì sẽ bị TTS đọc to nguyên văn.
2. **Tính ngân sách từ TRƯỚC khi viết**, dùng `script_writer.target_narration_word_count(duration_minutes, duration_seconds)`: tốc độ đọc tự nhiên mặc định 150 từ/phút (`NARRATION_WORDS_PER_MINUTE`), trừ sẵn 12.5% (`NARRATION_SILENCE_MARGIN`, giữa khoảng 10-15% yêu cầu) làm khoảng lặng cho SFX. Tổng số từ lời đọc thật sự viết ra KHÔNG được vượt ngân sách này.
3. **Không cố nhồi lời cho đủ mọi khoảnh khắc** — đúng tinh thần [[narration-scene-alignment]]: đoạn cao trào/hành động nên để hình ảnh + âm thanh nền tự kể chuyện, lời đọc thưa hơn hẳn so với đoạn tường thuật/bối cảnh. Phân bổ ngân sách từ KHÔNG cần đều theo giây — đoạn nào cần lời nhiều hơn thì lấy nhiều hơn, miễn tổng không vượt ngân sách.
4. **Sau khi Claude viết xong, kiểm tra ngược bằng `script_writer.count_narration_words()`** (tự động bỏ qua các mốc timestamp trước khi đếm) — nếu vượt quá `NARRATION_OVER_BUDGET_TOLERANCE` (115% ngân sách), coi là "quá dài" và báo cho người dùng (xem `ScriptResult.over_budget`, hiển thị ở giao diện ngay dưới ô Kịch bản) — CHỈ cảnh báo, không tự động cắt bớt (người dùng tự quyết định sửa gì, giữ đúng nguyên tắc "App tự quyết, người dùng xác nhận lại" đã áp dụng ở Bước 3/4/8).
5. **Khi soát lại 1 kịch bản người dùng đưa sẵn** (dán qua chat hoặc file, không qua `generate_script()`): áp dụng đúng 2 quy tắc trên bằng tay — tách riêng phần lời đọc khỏi mọi ghi chú hình ảnh trước khi đưa vào app, và ước lượng độ dài bằng công thức tương tự (150 từ/phút, dư 10-15%) trước khi khẳng định kịch bản "vừa đúng" thời lượng.
