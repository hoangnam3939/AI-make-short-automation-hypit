---
name: narration-scene-alignment
description: BẮT BUỘC cho MỌI video app làm ra — (1) KHÔNG BAO GIỜ được để video bị cắt ngắn mất cảnh chỉ vì giọng đọc ngắn hơn tổng độ dài các cảnh Flow đã tạo (đã sửa tận gốc trong `video_builder.py`, xem cơ chế bên dưới — bắt buộc giữ nguyên cách sửa này, không được quay lại công thức cũ); (2) lời dẫn chuyện nên khớp đúng với cảnh hình ảnh đang chiếu khi có thể, và HOÀN TOÀN CHẤP NHẬN ĐƯỢC nếu 1 cảnh không có câu văn nào nhắc tới (chỉ cần hiệu ứng âm thanh nền, xem skill `sfx-mixing-safety`) — không được cố nhồi thêm lời dẫn cho đủ mọi cảnh, và không được cắt bớt lời dẫn theo cách làm MẤT CẢNH. Dùng khi viết kịch bản, soát lại kịch bản, hoặc khi build video hoàn chỉnh cho bất kỳ ngôn ngữ nào.
---

# Không được để giọng đọc ngắn làm mất cảnh — lời dẫn khớp cảnh là ưu tiên phụ, giữ đủ cảnh là ưu tiên chính

Rút ra từ phản hồi thật của người dùng (2026-09-13, video "Quang Trung đại phá quân Thanh"): ban đầu phát hiện câu nói "lên ngôi Hoàng đế" phát SỚM hơn cảnh lễ lên ngôi thật xuất hiện. Lần sửa ĐẦU TIÊN (cắt bớt câu văn cho lời dẫn ngắn lại, khớp đúng phần cảnh còn hiển thị) tưởng đúng nhưng lại gây ra lỗi NẶNG HƠN: giọng đọc ngắn hơn nữa khiến cảnh "Quang Trung + Bùi Thị Xuân cưỡi voi lên đàn tế lên ngôi" — vốn dĩ đang hiển thị ĐỦ — bị cắt mất gần hết. Người dùng chỉ rõ: **"giữ nguyên đủ tất cả các cảnh, chỉ tác động vào giọng đọc thôi"**. Đây mới là thứ tự ưu tiên đúng.

## Cơ chế lỗi gốc (đã sửa tận gốc trong code, không phải chỉ né tránh bằng nội dung)

App ghép video theo đoạn lời dẫn (beat), mỗi đoạn gồm nhiều cảnh storyboard ~8s/cảnh nối lại. Bản lỗi cũ của `build_scene()` (`app/services/video_builder.py`) tính:

```python
target_dur = audio_dur + 0.25   # SAI: chỉ tính theo giọng đọc
```

→ giọng đọc ngắn hơn tổng độ dài cảnh Flow đã tạo cho đoạn đó → phần video thừa bị **CẮT MẤT HẲN** (mất cảnh thật, dù đã tốn phí tạo qua Google Flow) — hoàn toàn không phụ thuộc lời dẫn có khớp nội dung hay không, chỉ đơn thuần là ĐỘ DÀI giọng đọc quá ngắn.

**Đã sửa đúng** (bắt buộc giữ nguyên cách sửa này cho mọi video sau này):

```python
video_dur = độ dài video gốc (đã ghép các cảnh Flow, TRƯỚC khi khớp giọng đọc)
target_dur = max(audio_dur + 0.25, video_dur)   # ĐÚNG: không bao giờ ngắn hơn video gốc
```

Giọng đọc ngắn hơn video → `apad` tự lấp phần còn lại bằng im lặng, TOÀN BỘ video gốc vẫn hiện đủ (chỉ đoạn cuối không có giọng đọc, vẫn có hiệu ứng âm thanh nền). Giọng đọc dài hơn video → video tự lặp lại (`-stream_loop -1`) như cũ, không đổi.

## Quy tắc bắt buộc

1. **Không bao giờ để `target_dur` của 1 cảnh/đoạn nhỏ hơn độ dài video gốc của chính nó.** Đây là bất biến (invariant) bắt buộc giữ đúng ở mọi nơi trong code có ghép giọng đọc với video — không chỉ riêng `build_scene()`.
2. Lời dẫn NÊN cố gắng khớp đúng cảnh đang chiếu khi viết/soát kịch bản (đối chiếu văn bản với prompt hình ảnh từng cảnh), nhưng đây là ưu tiên PHỤ — KHÔNG được đánh đổi bằng cách cắt ngắn lời dẫn nếu việc đó khiến video mất cảnh (xem lỗi thật ở trên).
3. **1 cảnh không có lời dẫn riêng là hoàn toàn bình thường** — không phải lỗi, không cần cố nhồi thêm câu văn để "lấp đầy". Cảnh đó vẫn chiếu đủ, chỉ có hiệu ứng âm thanh nền.
4. Nếu phát hiện 1 câu lời dẫn phát sai thời điểm so với cảnh nó mô tả (như ví dụ "lên ngôi" ở trên), ưu tiên sửa bằng cách ĐIỀU CHỈNH THỨ TỰ/NỘI DUNG câu văn (hoặc chấp nhận sai lệch nhỏ) — KHÔNG sửa bằng cách cắt ngắn khiến tổng giọng đọc đoạn đó ngắn hơn độ dài video gốc.
5. Sau khi sửa `video_builder.py` theo đúng công thức trên, hãy kiểm tra lại bằng cách đo tổng số cảnh storyboard thực sự hiển thị trong video cuối (so với tổng số cảnh đã tạo qua Flow) — phải ra ĐỦ 100%, không còn cảnh nào bị cắt mất chỉ vì lý do độ dài giọng đọc.
