---
name: character-emotion-accuracy
description: BẮT BUỘC cho MỌI video (sử thi Việt Nam, sử thi thế giới, hay bất kỳ loại phim nào) — biểu cảm/tâm lý của nhân vật trong mỗi cảnh phải ĐÚNG với tính cách nhân vật và bối cảnh/hoàn cảnh của cảnh đó (được xác định trước, dựa trên kịch bản/lịch sử), KHÔNG được để Veo3 tự suy diễn ra biểu cảm sai (VD: nhân vật anh hùng quả cảm bị vẽ thành lo âu, đăm chiêu). Dùng khi viết prompt cảnh hoặc Character Bible cho bất kỳ video nào.
---

# Biểu cảm nhân vật phải đúng bối cảnh, không để Veo3 tự suy diễn

Rút ra từ lỗi thật 2026-09-13: nhiều cảnh liên tiếp có nhân vật Nguyễn Huệ (Quang Trung) — một vị tướng anh hùng, quyết đoán, đang trên đà thắng lợi — nhưng Veo3 tự vẽ khuôn mặt ông với vẻ lo âu, đăm chiêu, như đang thở dài, dù mô tả trong Character Bible chỉ ghi chung chung "gương mặt cương nghị dày dạn phong trần" (không đủ cụ thể để loại trừ biểu cảm sai). Kết quả làm giảm hẳn khí chất "bản hùng ca lịch sử" mà bộ phim cần truyền tải.

## Nguyên tắc bắt buộc

1. **Xác định rõ trạng thái tâm lý ĐÚNG của nhân vật trong TỪNG cảnh cụ thể** trước khi viết prompt — không dùng 1 mô tả biểu cảm chung chung áp dụng cho mọi cảnh của cùng 1 nhân vật xuyên suốt phim. Một nhân vật có thể trải qua nhiều trạng thái khác nhau ở các thời điểm khác nhau (VD: quyết đoán lúc ra lệnh, trầm tĩnh lúc suy tính chiến lược, đau đớn lúc chứng kiến mất mát) — NHƯNG trạng thái đó phải do kịch bản/lịch sử quy định, không phải Veo3 tự chọn.
2. **Với nhân vật anh hùng/chính diện đang ở thế thắng hoặc quyết đoán** — phải mô tả rõ ràng, tích cực: tự tin, quả cảm, uy quyền, kiên định — và **phủ định tường minh** các biểu cảm sai thường gặp mà mô hình hay tự thêm vào (lo âu, đăm chiêu, sợ hãi, chán nản) — chỉ mô tả "cương nghị" hay "quyết đoán" suông là CHƯA ĐỦ để loại trừ biểu cảm sai, phải viết rõ "KHÔNG lo âu, KHÔNG đăm chiêu, KHÔNG sợ hãi" kèm mô tả tích cực cụ thể.
3. Ngay cả trong cảnh tĩnh lặng/suy tư (VD: đang nghiên cứu bản đồ, ngắm trời đêm) — nếu nhân vật đó có tính cách quả cảm/tự tin, biểu cảm trầm tĩnh suy tính vẫn phải giữ được sự tự tin, KHÔNG biến thành lo âu/mệt mỏi.
4. Áp dụng cho MỌI nhân vật có tên trong Character Bible, không chỉ nhân vật chính — mỗi nhân vật cần 1 "tông" biểu cảm mặc định phù hợp tính cách của họ (VD: vua bù nhìn nhu nhược thì đúng là nên lo sợ/khiếp nhược — đó là phù hợp bối cảnh; nhưng tướng anh hùng đang thắng thế thì không được lo sợ).
5. Dùng chung nguyên tắc này cho MỌI thể loại phim (sử thi Việt Nam, sử thi thế giới, phim hiện đại...) — không giới hạn riêng phim lịch sử.

## Áp dụng thực tế

Khi viết/soát Character Bible cho 1 nhân vật, xác định rõ "tông biểu cảm mặc định" của nhân vật đó xuyên suốt phim (phù hợp tính cách + vai trò trong câu chuyện), viết vào mô tả nhân vật với cả phần khẳng định VÀ phủ định tường minh các biểu cảm sai dễ bị mô hình tự thêm vào. Nếu 1 cảnh cụ thể cần trạng thái tâm lý khác với tông mặc định (VD: nhân vật anh hùng hiếm hoi có khoảnh khắc yếu lòng), ghi rõ trong PROMPT CỦA CẢNH ĐÓ là ngoại lệ có chủ đích, không để mặc định áp dụng nhầm.
