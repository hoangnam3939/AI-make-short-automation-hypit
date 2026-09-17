# AI Video Studio (tên tạm — đổi lại được)

App AI làm video dài tự động — từ 1 ý tưởng hoặc 1 câu chuyện gốc, ra
video hoàn chỉnh (dài 5-30 phút hoặc Short 15-60s), giữ nhân vật đồng
nhất, xuất được nhiều ngôn ngữ. App không tự tạo video AI — nó viết
kịch bản + prompt, rồi đưa link cho người dùng tự bấm qua Google Flow
hoặc AI làm video khác (tự trả tiền), sau đó App tự ghép thành video
cuối cùng.

**Tài liệu đặc tả gốc (nguồn sự thật duy nhất):**
`Nhiem_Vu_Goc_App_Video_AI_V3.docx` (thư mục cha `TINHHOA FACEBOOK/`).
Mọi quyết định thiết kế trong repo này bám theo đúng file đó.

**Nền tảng kỹ thuật đã chứng minh** (xem thêm
`../.claude/skills/run-video-pipeline/SKILL.md`): edge-tts (giọng đọc
miễn phí, 140+ ngôn ngữ) + ffmpeg (dựng/ghép video) + quy ước thư mục
`scenes/ → audio/ → build/ → output/`, đúc kết từ 4 video thật đã làm
(Troy, Thánh Gióng, Sơn Tinh Thủy Tinh, Salamis).

## Skills đã có (Claude tự áp dụng khi viết kịch bản/cảnh)

App/Claude dùng 11 skill sau khi viết kịch bản và prompt cảnh cho bất kỳ video nào — người dùng nên biết các skill này tồn tại và công dụng của chúng để hiểu vì sao đôi khi Claude sẽ hỏi lại thông tin trước khi viết kịch bản. **Toàn bộ 11 skill này áp dụng cho MỌI loại video app làm ra — sử thi/huyền thoại Đại Việt, sử thi/huyền thoại thế giới, VÀ mọi video bình thường khác (hiện đại, đời thường...) — không riêng phim sử thi:**

1. **`video-context-research`** (bắt buộc, áp dụng cho MỌI video kể cả hiện đại/đời thường) — trước khi viết kịch bản, xác định rõ bối cảnh thời đại + đúng loại trang phục cho từng hoàn cảnh (lễ nghi, đời thường, võ phục, vui chơi...); nếu thiếu thông tin, được phép hỏi lại người dùng thay vì tự suy đoán.
2. **`historical-accuracy-research`** (cho phim sử thi/huyền thoại **Đại Việt**) — tra cứu kiến trúc, đồn luỹ, trang phục-vũ khí-cờ hiệu theo phe/cấp bậc, nhân vật lịch sử có tên, tượng đài/di tích hiện tại, trước khi viết prompt cảnh.
3. **`world-epic-historical-accuracy`** (cho phim sử thi/huyền thoại **thế giới** — Troy, Salamis...) — song song với skill 2 nhưng cho các nền văn minh/giai đoạn thế giới, có lưu ý phân biệt các giai đoạn dễ nhầm (VD: Hy Lạp Mycenaean vs Hy Lạp cổ điển).
4. **`present-day-and-action-logic`** (bắt buộc, MỌI video) — (a) mọi bối cảnh/công trình phải mô tả như đang ở HIỆN TẠI của câu chuyện (mới, sống động), không phải phế tích cổ; (b) mọi hành động nhân vật phải logic đúng với việc họ đang làm (VD: sứ giả phi ngựa đưa tin không rút vũ khí; ăn mừng thì nâng ly, không vung kiếm).
5. **`script-grounded-scene-accuracy`** (bắt buộc, MỌI video) — mọi chi tiết cảnh (chiến thuật, đội hình, hành vi) phải bám đúng kịch bản/sự kiện thật, không để Veo3 tự thay bằng mô-típ điện ảnh quen thuộc nhưng sai (VD: trận đánh úp bất ngờ bị vẽ nhầm thành "hai đội quân dàn trận đối mặt" kiểu phim cổ trang) — phải phủ định tường minh mô-típ sai, không chỉ mô tả đúng là đủ.
6. **`character-emotion-accuracy`** (bắt buộc, MỌI video) — biểu cảm/tâm lý nhân vật trong mỗi cảnh phải đúng tính cách + bối cảnh (do kịch bản/lịch sử quy định), không để Veo3 tự suy diễn (VD: tướng anh hùng đang thắng thế bị vẽ nhầm thành lo âu, đăm chiêu) — phải khẳng định tích cực VÀ phủ định tường minh biểu cảm sai.
7. **`battle-scene-pacing`** (bắt buộc, MỌI video có cảnh chiến trận/hành động — lịch sử hay hiện đại, áp dụng song song với CẢ skill 2 sử thi Đại Việt LẪN skill 3 sử thi thế giới) — mọi cảnh chiến trận/hành động phải dồn dập, kịch tính, cao trào, tốc độ nhanh nhất có thể; phải sửa CẢ phần mô tả hành động chính LẪN phần Visual style (chỉ sửa Visual style là chưa đủ), áp dụng đồng loạt cho cả cụm cảnh cao trào — nhưng có ngoại lệ hợp lý cho khoảnh khắc lắng đọng có chủ đích ngay sau cao trào (không tự động tăng tốc, cần hỏi lại người dùng).
8. **`veo3-prominent-people-policy`** (bắt buộc, MỌI video app làm có nhân vật thật/có tên — không riêng phim sử thi) — Veo3 có 2 bộ lọc riêng biệt: "prominent people" (chặn khi có tên thật+chức danh, đặc biệt từ 2 nhân vật nổi bật trở lên cùng lúc, kể cả voi chiến/bố cục nghi lễ dễ bị bắt nhầm) và "harmful content" (chặn khi cộng dồn mô tả giết chóc cụ thể nhắm vào 1 người có tên + thuật ngữ vũ khí nghe hiện đại/hoá học). Quy tắc mặc định: KHÔNG gửi tên riêng nhân vật thật vào prompt gửi Flow, chỉ mô tả ngoại hình, giữ tên ở Character Bible nội bộ.
9. **`sfx-mixing-safety`** (bắt buộc khi thực hiện Bước 13 — lồng hiệu ứng âm thanh nền, MỌI video) — phòng 5 lỗi thật: (a) file SFX tải về có thể dài hơn nhiều phút, phải `atrim` cắt ngắn đúng bằng độ dài đoạn tương ứng, không để kêu tràn sang các đoạn sau; (b) phải tăng âm lượng giọng đọc tương ứng khi tăng âm lượng SFX, không để giọng đọc bị nuốt mất; (c) mặc định loại các hiệu ứng "tiếng chim" khỏi kết quả so khớp, chỉ cho phép ở đúng cảnh rừng núi; (d) phải chọn SFX theo ĐÚNG TỪNG CẢNH storyboard (cho phép nhiều lớp chồng nhau), không gộp theo cả đoạn lời dẫn; (e) loại trừ các hiệu ứng dễ trùng âm tiết sai chủ đề (VD "Niệm Phật" khớp nhầm với từ láy "phần phật").
10. **`narration-scene-alignment`** (bắt buộc, MỌI video) — lời dẫn chuyện phải khớp đúng với cảnh THỰC SỰ HIỂN THỊ trên video cuối (không phải cảnh dự kiến trong storyboard) — vì cách app ghép video theo độ dài giọng đọc có thể khiến 1 số cảnh cuối đoạn bị cắt mất hoàn toàn hoặc gần hết mà giọng đọc vẫn nói về nội dung cảnh đó; câu văn nào rơi vào trường hợp này phải bị BỎ, và 1 cảnh hoàn toàn có thể không cần lời dẫn riêng (chỉ cần hiệu ứng âm thanh nền) mà không sao.
11. **`narration-length-budget`** (bắt buộc khi viết/soát kịch bản Bước 5, MỌI video, thêm 2026-09-15) — (a) kịch bản CHỈ được là lời đọc thuần tuý, TUYỆT ĐỐI KHÔNG lẫn mô tả hình ảnh kiểu "(Hình ảnh: ...)" hay bất kỳ chỉ dẫn sản xuất nào khác — app đưa thẳng văn bản sau mỗi timestamp vào TTS, lẫn vào sẽ bị đọc to ra tiếng; (b) tổng độ dài lời đọc phải vừa khít thời lượng video mục tiêu ở tốc độ đọc tự nhiên (~150 từ/phút), dư ra 10-15% làm khoảng lặng cho hiệu ứng âm thanh nền — đã code hoá thành `script_writer.target_narration_word_count()` (tính ngân sách từ) + `count_narration_words()` (đếm ngược để cảnh báo `over_budget`, hiển thị ngay dưới ô Kịch bản trên giao diện).

Xem chi tiết từng skill tại `.claude/skills/<tên skill>/SKILL.md`.

## Tự động sửa lỗi khi Google Flow từ chối tạo video (Bước 9b, 2026-09-13)

Khi Google Flow từ chối tạo 1 cảnh vì chính sách nội dung (`FlowContentPolicyViolation` —
xem `app/services/google_flow_driver.py`), app KHÔNG dừng lại chờ người dùng tự sửa prompt
nữa. `generate_video_with_retry()` tự gọi `llm.fix_flow_rejected_prompt()` — gửi lý do Flow
từ chối + prompt đang lỗi cho Claude phân tích (dựa trên skill 8 `veo3-prominent-people-policy`)
— Claude viết lại prompt (hoặc trả nguyên văn nếu nghi ngờ đây chỉ là báo nhầm ngẫu nhiên của
Flow), app tự nộp lại và thử tạo video, lặp tối đa `max_policy_fix_rounds` (mặc định 2) lần
trước khi mới báo lỗi cho người dùng. Đây là điều kiện bắt buộc để app đạt được tính tự động
hoàn toàn (không cần người dùng ngồi canh từng cảnh).

App gọi Claude theo 1 trong 2 cách, người dùng tự chọn ở màn hình Cài đặt (`app/services/llm.py`):
1. **`api`** (mặc định) — API key riêng của người dùng, tính phí theo lượt gọi.
2. **`claude_cli`** — dùng chung tài khoản Claude Pro/Max người dùng đã đăng nhập sẵn qua
   Claude Code CLI trên máy (gọi qua `claude -p`), không cần API key riêng, không phát sinh phí
   thêm ngoài gói Pro/Max đang có. Cần cài Claude Code CLI + đăng nhập trước; app tự kiểm tra
   `shutil.which("claude")` để biết CLI có sẵn không.

Nếu Claude chưa được cấu hình theo cả 2 cách trên, app quay lại hành vi cũ: dừng lại và báo lỗi
cho người dùng tự xử lý.

## Tài khoản Gemini / Google AI Pro qua Antigravity CLI (2026-09-16)

Google đã ngừng phục vụ tài khoản cá nhân (miễn phí, Google AI Pro/Ultra)
qua Gemini CLI từ 18/06/2026. Lỗi `IneligibleTierError / UNSUPPORTED_CLIENT`
là thay đổi phía dịch vụ; cập nhật `gemini` hoặc thêm trusted directory
không khôi phục quyền sử dụng này. Nguồn:
[thông báo Google](https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/).

Lựa chọn **Dùng tài khoản Gemini** giữ mã cấu hình `gemini_cli`, nhưng nay
gọi Antigravity CLI chính thức (`agy`). App không thay đổi lựa chọn đã lưu,
không tự chuyển sang API key khi lỗi, không sửa cấu hình Codex.

1. Cài CLI theo [Installation & Auth](https://antigravity.google/docs/cli/install/)
   nếu chưa có lệnh `agy` trên PATH, rồi mở lại terminal và app.
2. Mở terminal tại thư mục gốc project, chạy `agy`, đăng nhập đúng tài khoản
   Google đang có AI Pro. Xác nhận tin cậy đúng thư mục project nếu CLI hỏi.
   Phiên Antigravity dùng kho thông tin xác thực hệ điều hành; file OAuth
   cũ của Gemini CLI không đủ để chứng minh Antigravity đã đăng nhập.
3. Có thể chạy `agy models` để kiểm tra quyền truy cập. Trong app, chọn
   **Dùng tài khoản Gemini**; không cần nhập API key.

App gọi `agy --input-format stream-json --output-format stream-json
--model gemini-3.1-pro-high --disable-slash-commands --print-timeout 180s`,
với `shell=False`, thư mục chạy cố định ở gốc project. System/user prompt
được ghép rồi gửi thành một sự kiện JSON `user` qua stdin, tránh giới hạn
độ dài lệnh Windows. App chỉ nhận `response` từ sự kiện `result` có trạng
thái `SUCCESS`; lỗi, timeout, kết quả thiếu hoặc đang sinh dở đều bị báo lỗi.
Cú pháp đã đối chiếu với `agy --help` trên máy và
[tài liệu headless](https://antigravity.google/docs/cli/headless).

Lỗi trusted directory của Gemini cũ không còn nằm trên luồng gọi này.
App không tắt cơ chế trust toàn máy và không bật tự động duyệt mọi quyền.
Nếu Antigravity báo cần đăng nhập/trust, chạy tương tác `agy` tại cùng
thư mục như bước 2. Nếu bản CLI quá cũ không nhận `stream-json`, dùng
`agy update` rồi thử lại.

Google AI Pro được dùng theo hạn mức Antigravity. Nếu chỉ muốn dùng phần
hạn mức có sẵn, kiểm tra **AI Credit Overages = Never** trong Antigravity;
app không thay đổi cài đặt này hoặc mua thêm credit. Xem
[hạn mức và overages chính thức](https://antigravity.google/docs/plans/).

Kiểm thử adapter và bộ định tuyến hiện có:
`.venv\Scripts\python.exe -m pytest tests/test_llm.py tests/test_settings_api.py -q`.

## Chạy thử (local, giống cách Google Flow mở bằng trình duyệt)

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
python run.py
```

Trình duyệt tự mở `http://127.0.0.1:8787`. Không cần đưa lên mạng,
không cần server — chạy hoàn toàn trên máy.

## Trạng thái hiện tại (2026-09-14, đã đối chiếu lại với code thật)

Khung sườn đã chạy được xuyên suốt: nhập ý tưởng → viết lại câu chuyện
(Claude) → viết kịch bản có timestamp → chia storyboard theo pacing
~8s/cảnh → sinh prompt AI từng cảnh (luôn chèn lại mô tả nhân vật) →
**tự tạo cảnh qua Google Flow + tự dựng video + tự lồng SFX theo từng
cảnh, nối liền thành 1 job chạy nền** (Bước 9+10+13, mới xong
2026-09-14) → kiểm tra lỗi kỹ thuật. 87 test tự động trong `tests/`,
chạy thật ra **82 PASS / 5 FAIL** (không mock phần ffmpeg/edge-tts/tải
hiệu ứng âm thanh; chỉ mock Google Flow + Claude ở test pipeline vì 2
thứ đó cần trình duyệt/tài khoản thật). 5 fail hiện tại KHÔNG phải lỗi
chức năng của app: fixture `isolated_env` trong
`test_llm.py`/`test_settings_api.py` viết từ trước khi có backend
`claude_cli`, chưa giả lập `shutil.which("claude")` — trên máy đã đăng
nhập sẵn Claude Code CLI thì `is_configured()` đúng ra phải trả `True`,
khiến test cũ (giả định luôn `False` lúc đầu) bị sai theo — cần sửa lại
test, không phải sửa app.

**⚠️ Rất quan trọng — chưa lưu vào git:** khi kiểm tra `git status`,
rất nhiều phần dưới đây (toàn bộ `google_flow_driver.py`,
`sfx_sourcing.py`, `multilang_export.py`, `app/static/i18n.js`, thư mục
`automation/`, cùng các sửa đổi trong `llm.py`/`video_builder.py`/giao
diện) đang ở dạng "Untracked" hoặc "Changes not staged" — CHƯA từng
được `git add`/`git commit`. Repo trên GitHub (3 commit) mới chỉ có tới
Bước 1-10; nếu máy gặp sự cố trước khi commit, toàn bộ phần việc mới
này sẽ mất. Nên commit sớm.

### Đã xong — có API, có UI, có test PASS thật

- [x] Backend FastAPI + frontend tĩnh, chạy local, tự mở trình duyệt
- [x] Màn hình 1-5 (đúng 5 bước hiện trong thanh tiến trình
      `#step-progress` của `index.html`): cài đặt key/CLI → nhập ý
      tưởng/câu chuyện → chọn định dạng (Dài 16:9 / Short 9:16) + thời
      lượng → chọn ngôn ngữ (20 ngôn ngữ, chọn nhiều được) → xem câu
      chuyện đã viết lại + kịch bản — giao diện Adobe-Express-style
- [x] Cài đặt API key Claude ngay trong app (lưu cục bộ `.env`, không
      commit, không bao giờ trả lại nguyên key cho frontend); ngoài ra
      còn có lựa chọn dùng `claude_cli` (dùng chung Claude Pro/Max qua
      Claude Code CLI, không cần API key riêng) — đã xác nhận hoạt động
      thật trên máy này (`/api/settings` trả `claude_cli_available: true`)
- [x] Bước 1: Sổ Tay Nhân Vật (Character Bible) — mặc định 10, mở rộng
      tới 20; `inject_character_descriptions()` tự động chèn lại nguyên
      văn mô tả nhân vật vào mọi prompt cảnh có nhắc tên
- [x] Bước 2: gọi Claude viết lại câu chuyện đầy đủ (`services/script_writer.py::rewrite_story`)
- [x] Bước 3 (thêm 2026-09-15): xác định chủ đề & mục tiêu — đối tượng
      xem, vấn đề họ quan tâm, thông điệp chính, góc triển khai
      (`script_writer.py::determine_theme_and_goals`, `POST /api/story/theme`,
      card riêng trên giao diện, kết quả được CHÈN vào prompt Bước 5 để
      kịch bản thực sự bám sát, không chỉ hiển thị cho có)
- [x] Bước 4 (thêm 2026-09-15): tạo 20 câu hook mở đầu chia 5 nhóm (tò
      mò/bất ngờ/đánh vào nỗi đau/lợi ích rõ/cách làm mới), tự chấm chọn
      3 câu mạnh nhất (`script_writer.py::generate_hooks`,
      `POST /api/story/hooks`) — câu hook người dùng chọn được chèn
      NGUYÊN VĂN làm câu mở đầu kịch bản ở Bước 5
- [x] Bước 5: viết kịch bản theo đúng thời lượng, cấu trúc
      Hook→Vấn đề→Bối cảnh→Giải pháp→Hướng dẫn→Ví dụ→Kết quả→CTA cho
      video dài, rút gọn Hook→Nội dung chính→CTA cho Short
      (`script_writer.py::generate_script`)
- [x] Bước 6-7: chia storyboard theo pacing ~8s/cảnh + sinh prompt AI
      tiếng Anh từng cảnh
- [x] Bước 8 (thêm 2026-09-15): quyết định loại hình cho từng cảnh —
      video AI/ảnh tĩnh/b-roll/chữ động/biểu đồ, Claude tự phân loại
      NGAY trong lượt gọi sinh prompt (không tốn thêm lượt gọi nào,
      `storyboard.py::generate_scene_prompts` trả thêm `scene_type` +
      `chart_data`). Dựng THẬT cả 5 loại (`app/services/scene_renderers.py`):
      ai_video/b_roll gọi Flow như cũ (b_roll bỏ qua chèn nhân vật);
      static_image gọi Flow rồi giữ đứng 1 khung hình; motion_text/chart
      THUẦN ffmpeg/matplotlib, không gọi Flow. Mọi loại đều trả về đúng 1
      file video cùng chuẩn — `_build_beat_clips`/`_apply_sfx`/ghép đa
      ngôn ngữ phía sau không cần biết/sửa gì. **Giới hạn đã biết**:
      chữ trên màn hình của motion_text/chart hiện luôn tiếng Anh (dùng
      chung được mọi ngôn ngữ xuất video, giống quy ước prompt Bước 7) —
      chưa hỗ trợ chữ theo đúng ngôn ngữ từng video xuất ra.
- [x] Bước 9 (danh sách AI ngoài): Vidu, Higgsfield, Runway, Kling,
      Google Flow, LTX Studio, Vadoo + máy tính ngân sách kèm dự phòng
      làm lại 30-50%, từ chối ước tính khi giá không rõ ràng
- [x] Bước 10: ghép video thật bằng edge-tts + ffmpeg (`video_builder.py`)
- [x] Mục 8, phần kỹ thuật (không cần AI): kiểm tra lỗi kỹ thuật — lệch
      độ phân giải/fps giữa các cảnh, lệch thời lượng audio/video, khung
      hình đen/đứng hình bất thường (`error_checker.py`, dùng ffprobe/
      ffmpeg).
- [x] Mục 8, phần CỐT LÕI/ĐỘC QUYỀN (thêm 2026-09-15) — 3 kiểm tra chạy
      NGẦM trong lúc sản xuất, gộp chung vào 1 khung cảnh báo
      "quality_warnings" trên giao diện (CHỈ cảnh báo, không tự sửa gì):
        1. **Nhân vật đổi hình dạng giữa các cảnh** — cốt lõi thật sự của
           Mục 8, đặc tả gốc nói "không có app nào trong 25 app thương mại
           lẫn ~29 dự án GitHub làm sẵn việc này". Vì app không lưu ảnh
           tham chiếu riêng cho Sổ Tay Nhân Vật (chỉ có mô tả văn bản),
           cách làm: trích 1 khung hình đại diện mỗi cảnh (ffmpeg), gom
           cảnh theo nhân vật bằng `CharacterBible.find_mentioned()` đã
           có sẵn, so embedding **CLIP** (mô hình mở, chạy CỤC BỘ trên
           máy — `torch` + `open-clip-torch`, KHÔNG gửi ảnh ra ngoài,
           dependency NẶNG NHẤT app từng thêm, ~350MB tải lần đầu) giữa
           các cặp cảnh liên tiếp cùng 1 nhân vật, dưới ngưỡng 0.75 thì
           cảnh báo (`app/services/character_consistency.py`). **Hiện tại
           không có tác dụng thật trên giao diện** vì app CHƯA có màn
           hình nhập Sổ Tay Nhân Vật (Bước 1) — logic đã đúng và có test
           đầy đủ, chỉ cần nối thêm màn hình nhập nhân vật (ngoài phạm vi
           đợt này) là chạy được ngay, không cần sửa gì thêm ở đây.
        2. **Giọng đọc lệch thời gian** — không dùng `ffsubsync` như gợi ý
           gốc (cần phụ đề .srt mà app chưa xuất), thay bằng so thời
           lượng thực tế/dự kiến từng đoạn đã dựng, kế thừa tinh thần
           skill `narration-scene-alignment`
           (`error_checker.check_narration_scene_drift`).
        3. **Chữ trên poster mở đầu bị lỗi** — OCR bằng Tesseract-OCR
           (cần cài binary hệ thống riêng, xem `requirements.txt`), so
           khớp mờ với tiêu đề/phụ đề dự kiến
           (`error_checker.check_poster_text`) — máy chưa cài Tesseract
           thì tự trả 1 cảnh báo rõ ràng thay vì lỗi, không chặn 2 kiểm
           tra còn lại.

### Đã VIẾT CODE và ĐÃ NỐI vào app chạy thật (2026-09-14)

Mục này (Bước 9, 9b, 3, 13) từng bị liệt vào "viết code nhưng chưa nối API"
— nay đã nối xong hết, xem chi tiết ở mục "Bước 9+10+13 nối liền qua API"
và "Bước 3 — xuất nhiều ngôn ngữ" phía trên. `app/static/i18n.js` (đa ngôn
ngữ GIAO DIỆN, không phải giọng đọc video) đã kiểm tra mức độ hoàn thiện
bằng test tự động `tests/test_i18n_completeness.py` — đối chiếu từng chữ
giữa 3 khối vi/en/ru, xác nhận **0 chữ thiếu bản dịch** (188/188 chữ khớp
đủ ở cả 3 ngôn ngữ) và không có key nào bị khai báo trùng lặp (trùng sẽ âm
thầm đè mất 1 bản dịch mà không ai để ý). Chạy lại bất cứ lúc nào bằng
`pytest tests/test_i18n_completeness.py -v`.

### Hoàn toàn chưa làm

- [x] **Bước 11 (chấm điểm kịch bản) + Bước 12 (tiêu đề/thumbnail/mô
      tả/CTA)** (2026-09-14): `app/services/quality_review.py` +
      `app/api/quality.py` (`POST /api/quality/score`,
      `POST /api/quality/metadata`) + nút "Chấm điểm kịch bản" trên giao
      diện. Bước 12 đã tự động chạy trong production pipeline (tự sinh
      tiêu đề + ghép poster mở đầu vào video, xem
      `production_pipeline.py::_add_title_card`). **Lưu ý quan trọng**:
      file đặc tả gốc không còn tìm thấy trên máy nên KHÔNG có được đúng
      "8 tiêu chí" gốc — 8 tiêu chí đang dùng
      (`quality_review.SCORING_CRITERIA`) là Claude tự đề xuất hợp lý dựa
      trên các skill đã có, cần người dùng xác nhận lại hoặc chỉnh sửa nếu
      tìm lại được file đặc tả V3. Chấm điểm dựa trên VĂN BẢN kịch bản,
      chưa phân tích hình ảnh/âm thanh thật của video đã dựng (cần thị
      giác máy tính, chưa làm).
- [x] **Bước 12 mở rộng — SEO riêng cho từng nền tảng + tự đăng bài**
      (2026-09-14): `quality_review.generate_seo_metadata(script, platform)`
      sinh tiêu đề/caption/hashtag CHUẨN RIÊNG cho 6 nền tảng (YouTube,
      TikTok, Facebook & Instagram, Threads, Twitter/X, Zalo — mỗi nơi 1
      bộ quy tắc khác hẳn nhau, xem `quality_review._PLATFORM_RULES`), có
      6 nút SEO trên giao diện. Thêm `app/services/publishing.py` +
      `app/api/publishing.py`: khung đăng video trực tiếp lên 7 nơi
      (tách riêng Facebook/Instagram vì cần thông tin đăng nhập khác
      nhau) — màn hình "Cài đặt đăng bài mạng xã hội" để nhập API
      key/token, nút "Đăng lên các nền tảng đã chọn" (chọn nhiều được)
      ngay dưới mỗi video đã sản xuất xong.
      **⚠️ CẢNH BÁO QUAN TRỌNG**: KHÁC với mọi phần khác của app trong
      README này, phần "tự đăng bài" (`publish_youtube`, `publish_facebook`,
      `publish_instagram`, `publish_tiktok`, `publish_threads`,
      `publish_twitter_x`, `publish_zalo`) viết theo tài liệu API chính
      thức nhưng **CHƯA ĐƯỢC KIỂM THỬ VỚI TÀI KHOẢN THẬT** — người dùng
      chưa có API key/token cho nền tảng nào tại thời điểm viết. Test tự
      động chỉ giả lập (mock) lệnh gọi mạng để kiểm tra logic xây dựng
      request đúng cấu trúc, KHÔNG xác nhận được các nền tảng có thật sự
      chấp nhận request đó không. PHẢI tự thử với 1 video test nhỏ trên
      từng nền tảng trước khi tin dùng cho video thật. Lưu ý riêng từng
      nơi: Instagram và Threads đòi video phải ở 1 URL công khai (app
      chạy local, không tự host được — người dùng phải tự host video ở
      nơi khác rồi dán URL vào); TikTok Content Posting API cần app được
      TikTok duyệt quyền `video.publish` trước; đăng bài kèm media qua
      Twitter/X API hiện cần gói trả phí (từ "Basic" trở lên); API Zalo
      OA ít tài liệu công khai nhất, nhiều khả năng cần chỉnh lại khi thử
      thật.
- [ ] Tra cứu lịch sử bắt buộc trước khi sinh prompt cảnh (kiến trúc,
      trang phục, vũ khí, cờ hiệu, nhân vật có tên, di tích hiện tại)
      cho video dựa trên sự kiện/nhân vật lịch sử có thật — quy trình
      đã có ở `.claude/skills/historical-accuracy-research/SKILL.md`
      nhưng CHƯA tự động hoá trong code, còn cần Claude/người dùng chủ
      động làm khi viết kịch bản.
- [ ] Nút "Tự động / Xem trước" ngay sau Bước 4/5/6 (mới chỉ là đặc tả
      trong README, chưa code).
- [x] Bước 9 — 2 chế độ chạy "Tự động hoàn toàn" / "Duyệt từng cảnh" —
      ĐÃ CODE, xem chi tiết đầy đủ ở mục "Bước 9 (tạo 37+ cảnh qua Flow)
      cần 2 lựa chọn chế độ chạy" bên dưới.
- [ ] Đa ngôn ngữ giao diện App đầy đủ (ưu tiên Anh/Nga, 17 ngôn ngữ
      còn lại thêm dần).
- [ ] Mở rộng giao diện cho đủ Bước 6-13 (hiện UI chỉ có 5 bước hiển
      thị; Bước 6 trở đi chỉ có API, chưa có màn hình riêng).
- [ ] **Thêm nút "Tự động / Xem trước" ngay sau Bước 4, Bước 5, và
      ngay sau Bước 6** (thêm 2026-09-13, ghi chú cho tương lai — chỉ
      đặc tả, CHƯA code, làm sau khi xong 2 video test hiện tại):
        - Ngay sau **Bước 4 (Câu chuyện)**: hiện 2 lựa chọn —
          1. **"Tự động"** (mặc định) — app tự chạy tiếp sang Bước 5,
             không dừng lại.
          2. **"Xem & sửa câu chuyện"** — app xuất câu chuyện (đã viết
             lại) ra 1 file Word, người dùng đọc/sửa trực tiếp, gửi
             ngược lại cho app rồi mới tiếp tục sang Bước 5.
        - Ngay sau **Bước 5 (Kịch bản)**: hiện 2 lựa chọn —
          1. **"Tự động"** (mặc định) — app tự chạy tiếp sang Bước 6,
             không dừng lại.
          2. **"Xem & sửa kịch bản"** — app xuất kịch bản ra 1 file Word,
             người dùng đọc/sửa trực tiếp trong Word, gửi ngược lại cho
             app (app đọc lại file đã sửa) rồi mới tiếp tục.
        - Ngay sau **Bước 6 (chia cảnh — VD phim Quang Trung có 37
          cảnh)**: hiện lại đúng 2 lựa chọn y hệt, áp dụng cho danh sách
          cảnh/scene prompts thay vì kịch bản.
      Mẫu quy trình này đã áp dụng thật (thủ công, qua chat) khi làm 2
      video test Quang Trung tiếng Việt/English — mục tiêu là đưa hẳn
      vào giao diện app để người dùng tự làm được, không cần chat với
      Claude nữa.
- [ ] Đa ngôn ngữ giao diện App (hiện toàn bộ UI tiếng Việt; ưu tiên
      thêm Anh/Nga theo đúng yêu cầu, 17 ngôn ngữ còn lại thêm dần)
- [x] **Bước 9+10+13 nối liền qua API** (2026-09-14): thêm
      `app/services/production_pipeline.py` + `app/api/production.py` +
      màn hình "Bước 6: Sản xuất video" trên giao diện — bấm 1 nút chạy từ
      kịch bản có timestamp tới video hoàn chỉnh có SFX: tự sinh prompt
      cảnh → tự tạo qua Google Flow (`google_flow_driver.py`, cần người
      dùng tự mở Chrome debug + đăng nhập tay trước, xem mục Help trong
      app) → tự dựng giọng đọc + video từng đoạn → tự lồng SFX theo từng
      cảnh (Bước 13). Chạy NỀN (thread), theo dõi qua `GET
      /api/production/{job_id}`. 1 cảnh lỗi không chặn cả video. Có test
      đầu-cuối giả lập Flow+Claude, thật ffmpeg/edge-tts/tiengdong.com
      (`tests/test_production_pipeline.py`, `tests/test_production_api.py`).
      **Đã bổ sung thêm (cùng ngày 2026-09-14)**:
      (a) tự động ghép tiêu đề mở đầu vào video (xem Bước 12 bên dưới —
      `_add_title_card` tự sinh title/subtitle qua Claude rồi ghép poster
      4s vào đầu video);
      (b) **Bước 3 — xuất nhiều ngôn ngữ trong CÙNG 1 job, cảnh Flow chỉ
      tạo ĐÚNG 1 LẦN dùng chung cho mọi ngôn ngữ** (trước đó mỗi ngôn ngữ
      sẽ tạo cảnh Flow riêng, rất tốn credit — đã sửa: `start_job` nhận
      `language_codes: list[str]`, ngôn ngữ khác ngôn ngữ gốc được tự dịch
      qua `llm.translate_text()` trước khi dựng giọng đọc riêng; có test
      xác nhận `generate_video_with_retry` chỉ được gọi đúng 1 lần/cảnh dù
      xuất bao nhiêu ngôn ngữ). API trả kết quả riêng từng ngôn ngữ qua
      `job.languages[lang_code]`, tải video qua
      `GET /api/production/{job_id}/video?language_code=...`.
      **Cập nhật 2026-09-14**: chế độ "duyệt từng cảnh" đã code xong (xem
      mục "Bước 9 (tạo 37+ cảnh qua Flow) cần 2 lựa chọn chế độ chạy" bên
      dưới). **Vẫn chưa làm**: chưa có 2 lựa chọn "xuất tuần tự hỏi từng
      ngôn ngữ / xuất luôn tất cả" trên giao diện (hiện LUÔN xuất hết mọi
      ngôn ngữ đã chọn ở Bước 1 cùng lúc, kiểu "xuất luôn tất cả").
- [x] **Bước 9 (tạo 37+ cảnh qua Flow) — 2 chế độ chạy** (đặc tả
      2026-09-13, **ĐÃ CODE xong 2026-09-14**, cả API lẫn giao diện):
        1. **"Tự động hoàn toàn"** (`run_mode="auto"`, mặc định) — app tự
           tạo hết tất cả các cảnh, tự ghép thành 1 video hoàn chỉnh,
           gửi thẳng cho người dùng, không dừng lại hỏi gì giữa chừng.
        2. **"Duyệt từng cảnh"** (`run_mode="review"`) — mỗi cảnh tạo
           xong, app dừng lại (`job.awaiting_review_scene`), cho người
           dùng xem thử qua `GET /api/production/{job_id}/scenes/{n}/video`
           rồi chọn 1 trong 3 nút trên giao diện (banner "Duyệt từng
           cảnh"): ✅ **Đồng ý** (giữ cảnh, sang cảnh tiếp theo), 🔄 **Tạo
           lại cảnh này** (bỏ cảnh vừa tạo, nhờ Flow tạo lại đúng cảnh đó,
           chưa sang cảnh kế), ⏭️ **Bỏ qua cảnh này** (đánh dấu
           `status="skipped"`, KHÔNG đưa vào video cuối, sang cảnh tiếp
           theo luôn). Gọi qua
           `POST /api/production/{job_id}/scenes/{n}/approve?action=approve|retry|skip`
           (`production_pipeline.approve_scene()`,
           `SCENE_REVIEW_ACTIONS`).
      Đổi qua lại giữa 2 chế độ được BẤT CỨ LÚC NÀO trong lúc job đang
      chạy — kể cả đang dừng chờ duyệt 1 cảnh — qua
      `POST /api/production/{job_id}/mode` (`set_run_mode()`), không cần
      dừng job/chạy lại từ đầu. Có test đầu-cuối giả lập Flow xác nhận cả
      3 hành động (`tests/test_production_pipeline.py`:
      `test_review_mode_pauses_after_each_scene_and_mode_switch_takes_effect_live`,
      `test_review_mode_retry_regenerates_same_scene`,
      `test_review_mode_skip_excludes_scene_from_final_video`) và test API
      (`tests/test_production_api.py`). Định hướng sản phẩm: khi các
      skill lịch sử (xem mục Skills phía trên) đã đủ tốt và ổn định, kỳ
      vọng phần lớn (mục tiêu ~99%) người dùng sẽ chọn "Tự động hoàn
      toàn" — số liệu chọn lựa thực tế của người dùng dùng để đánh giá
      tiếp cần hoàn thiện skill/app tới đâu.

**Lưu ý (cập nhật 2026-09-13):** đã xác nhận được thật trên máy có cài
Claude Code CLI — chạy `python run.py`, gọi `/api/settings` trả về
`{"llm_configured": true, "llm_backend": "claude_cli", "claude_cli_available": true}`,
tức backend `claude_cli` (dùng chung Claude Pro/Max, không cần API key
riêng) hoạt động thật. Vẫn chưa live-test đầu-cuối với API key riêng
(`api` backend) trong môi trường phát triển này, nhưng logic gọi API,
xử lý lỗi thiếu key, và xử lý từ chối (refusal) đã có unit test đầy đủ.

## Cấu trúc thư mục

```
APP_VIDEO_AI_STUDIO/
  app/
    main.py                entrypoint FastAPI
    api/
      project.py            /api/project, /api/languages
      settings.py            /api/settings, /api/settings/api-key
      story.py                /api/story/rewrite, /theme, /hooks, /script
      character_bible.py       /api/characters/validate, /api/characters/inject
      storyboard.py             /api/storyboard/beats, /scenes, /prompts
      ai_tools.py                /api/ai-tools, /api/ai-tools/budget
      error_check.py              /api/error-check/scenes, /black-frozen
      production.py                 /api/production/start, /{job_id}, /{job_id}/video
      quality.py                     /api/quality/score, /metadata, /seo
      publishing.py                   /api/publishing/status, /settings/{p}, /publish
    services/
      llm.py                 kết nối Claude (model claude-opus-5), lưu API key
      script_writer.py        Bước 1-5: viết lại câu chuyện + chủ đề/mục tiêu + hook + kịch bản
      character_bible.py       Sổ Tay Nhân Vật + cơ chế chèn mô tả
      storyboard.py             chia cảnh ~8s/cảnh + sinh prompt AI + Bước 8 (loại hình cảnh)
      scene_renderers.py         Bước 8: dựng 5 loại hình cảnh (ai_video/static_image/b_roll/motion_text/chart)
      chart_renderer.py           Bước 8: vẽ biểu đồ (matplotlib) cho loại hình "chart"
      ai_tools.py                danh sách AI ngoài + máy tính ngân sách
      video_builder.py            edge-tts + ffmpeg, dựng video thật
      error_checker.py             kiểm tra lỗi kỹ thuật + Mục 8 phần 2-3 (giọng đọc lệch/chữ poster lỗi)
      character_consistency.py      Mục 8 phần 1 (cốt lõi): nhân vật đổi hình dạng, dùng CLIP
      google_flow_driver.py          Bước 9: tự động hoá Google Flow qua Playwright
      sfx_sourcing.py                 Bước 13: SFX theo từng cảnh, nhiều lớp
      multilang_export.py              Bước 3: xuất đa ngôn ngữ (tuần tự/batch)
      production_pipeline.py            Bước 9+10+13 nối liền, chạy nền theo job_id
      quality_review.py                  Bước 11-12: chấm điểm, tiêu đề, SEO từng nền tảng
      publishing.py                       Đăng video lên 7 nền tảng (CHƯA test tài khoản thật)
    static/
      index.html        giao diện (ý tưởng → cài đặt key → câu chuyện → kịch bản → sản xuất)
      style.css          hệ thống thiết kế Adobe-Express-style
      app.js             logic phía trình duyệt
      i18n.js              đa ngôn ngữ giao diện (Việt/Anh/Nga)
  tests/                 87 test, phần ffmpeg/edge-tts/tiengdong.com chạy THẬT không mock
  requirements.txt
  run.py                 launcher: chạy server + tự mở trình duyệt
  README.md               file này
```

## Mã nguồn đóng

Repo này ở chế độ **riêng tư (private)** — chỉ chủ tài khoản GitHub có
quyền xem/sửa. Không public, không mở PR từ bên ngoài.
