"""Tự động hoá Google Flow (Pro) qua Playwright — dùng làm 1 lựa chọn ở
Bước 9 (chọn AI dựng video ngoài), thay thế cho việc tự tay mở Flow.

QUY TẮC AN TOÀN BẮT BUỘC, không được sửa:
- Không bao giờ tự mở/điều khiển trình duyệt để ĐĂNG NHẬP Google. Google chủ
  động chặn đăng nhập ("Không thể đăng nhập cho bạn") khi phát hiện trình
  duyệt bị điều khiển tự động ngay từ đầu — đã thử và bị chặn thật.
- Cách AN TOÀN đã chứng minh chạy được: người dùng tự tay mở Chrome thật
  (hồ sơ riêng, xem hướng dẫn ở HeloTitle "Dùng tài khoản Google Flow" trong
  app) với cờ --remote-debugging-port=9222, tự tay đăng nhập — module này
  CHỈ "nối vào" (connect_over_cdp) sau khi việc đăng nhập đã xong bằng tay
  người thật, không bao giờ tự động hoá bước đăng nhập.
- Trong Flow, mục Settings -> Agent phải để "Never" (agent tự tạo & tự tốn
  credit, không hỏi lại) để generate() dưới đây chạy không dừng giữa chừng.

Đã kiểm chứng thật (12/09/2026): gõ prompt "Generate a video: ..." rồi bấm
Start generation ra đúng video thật (không phải ảnh), tải về được file mp4
đầy đủ dung lượng qua download.path() + copy thủ công (save_as() trực tiếp
từng cho ra file 0 byte — có ghi lại trong lịch sử phát triển, không dùng
save_as() nữa). Mỗi lần generate_video() LUÔN tạo 1 dự án Flow mới (Home ->
New project) để tránh lẫn kết quả cũ/mới — đã thử tái sử dụng dự án cũ và
bị lỗi thật (driver cứ tải nhầm video cũ dù đổi prompt khác hẳn).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

import httpx
from playwright.sync_api import Page, sync_playwright

CDP_URL = "http://localhost:9222"
CDP_PORT = 9222
FLOW_URL = "https://labs.google/flow"
# Hồ sơ Chrome RIÊNG cho Flow — cố định 1 đường dẫn duy nhất để nút bấm dưới
# đây VÀ hướng dẫn chạy tay trong màn hình Help (index.html) luôn mở đúng
# CÙNG 1 hồ sơ đã đăng nhập, không tạo ra 2 hồ sơ trống khác nhau.
FLOW_PROFILE_DIR = os.path.expandvars(r"%LOCALAPPDATA%\AIVideoStudio\FlowProfile")

_CHROME_PATH_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
]


class ChromeNotFoundError(RuntimeError):
    pass


def _find_chrome_exe() -> str:
    for path in _CHROME_PATH_CANDIDATES:
        if os.path.exists(path):
            return path
    which = shutil.which("chrome") or shutil.which("google-chrome")
    if which:
        return which
    raise ChromeNotFoundError(
        "Không tìm thấy Google Chrome trên máy này (đã thử các đường dẫn cài đặt "
        "mặc định). Cài Google Chrome rồi thử lại."
    )


class FlowBrowserStartTimeout(RuntimeError):
    pass


def _cdp_alive() -> bool:
    """Cổng remote-debugging đã trả lời chưa — cách DUY NHẤT xác nhận Chrome
    thật sự đã khởi động xong với cờ debug bật, thay vì chỉ tin `Popen()`
    không ném lỗi (Popen chỉ báo lỗi khi *yêu cầu* tạo tiến trình thất bại,
    không xác nhận cửa sổ có thật sự hiện ra hay không)."""
    try:
        httpx.get(f"{CDP_URL}/json/version", timeout=1.0)
        return True
    except httpx.HTTPError:
        return False


def _flow_profile_pids() -> list[int]:
    """PID của mọi tiến trình chrome.exe TIẾN TRÌNH GỐC (không phải renderer/
    gpu/utility con) đang chạy với đúng FLOW_PROFILE_DIR — dò qua PowerShell
    vì Windows không có cách thuần Python nhẹ để đọc command-line tiến trình
    khác. Dùng để đưa cửa sổ ĐÃ CÓ SẴN lên trước mặt người dùng."""
    try:
        result = subprocess.run(
            [
                "powershell", "-NoProfile", "-Command",
                "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" "
                "| Where-Object { $_.CommandLine -like '*AIVideoStudio\\FlowProfile*' } "
                "| Select-Object -ExpandProperty ProcessId",
            ],
            capture_output=True, text=True, timeout=10,
        )
        return [int(pid) for pid in result.stdout.split() if pid.strip().isdigit()]
    except (subprocess.SubprocessError, OSError):
        return []


def _bring_windows_to_front(pids: list[int]) -> bool:
    """Best-effort đưa cửa sổ Chrome Flow lên TRƯỚC MẶT người dùng.

    Lý do cần hàm này (lỗi thật gặp phải 2026-09-15): nếu Chrome hồ sơ Flow
    ĐÃ CHẠY SẴN từ trước (VD người dùng bấm nút này 2 lần), gọi lại
    subprocess.Popen() một cửa sổ Chrome mới KHÔNG mở thêm cửa sổ nào cả —
    do cơ chế single-instance-per-profile của Chrome, nó chỉ âm thầm mở
    thêm 1 tab trong cửa sổ đang chạy nền, và cửa sổ đó KHÔNG tự nhảy lên
    trước mặt, người dùng thấy app báo thành công nhưng không thấy gì cả.

    LỖI THẬT LẦN 2 (2026-09-15, sau khi thử sửa bằng Win32 SetForegroundWindow
    trực tiếp qua ctypes): người dùng vẫn không tìm thấy cửa sổ dù app báo
    "đã đưa lên trước mặt". Nguyên nhân: Windows chủ động CHẶN một tiến
    trình KHÔNG có hoạt động bàn phím/chuột gần đây tự ý gọi
    SetForegroundWindow để cướp focus người dùng (cơ chế chống ứng dụng nền
    tự nhảy lên phá người dùng đang làm việc khác) — server Python chạy
    nền của app này chắc chắn rơi vào diện bị chặn, khiến lệnh gọi thất bại
    ÂM THẦM (trả về 0, không ném lỗi) mà code cũ không kiểm tra kết quả trả
    về, nên vẫn báo "thành công" dù thực chất không có gì xảy ra.

    Cách sửa: dùng `WScript.Shell.AppActivate` qua PowerShell (COM
    automation) thay vì gọi thẳng Win32 API — cơ chế này được Windows đối
    xử khoan dung hơn hẳn (tương đương người dùng tự bấm Alt+Tab chọn cửa
    sổ), khớp theo TIÊU ĐỀ cửa sổ ("Google Flow" luôn xuất hiện trong tiêu
    đề tab/cửa sổ Chrome khi ở đúng trang Flow). Thất bại của hàm này không
    chặn gì (best-effort) — bản thân Chrome vẫn đang chạy đúng, chỉ là
    không đưa lên trước mặt được, frontend sẽ báo rõ cho người dùng tự tìm
    trong taskbar."""
    del pids  # không còn cần khớp theo PID — khớp theo tiêu đề cửa sổ đáng tin cậy hơn
    try:
        result = subprocess.run(
            [
                "powershell", "-NoProfile", "-Command",
                "$w = New-Object -ComObject WScript.Shell; "
                "[Console]::Out.Write($w.AppActivate('Google Flow'))",
            ],
            capture_output=True, text=True, timeout=10,
        )
        return result.stdout.strip().lower() == "true"
    except (subprocess.SubprocessError, OSError):
        return False


def launch_flow_browser() -> dict:
    """Mở 1 cửa sổ Chrome THẬT (không qua Playwright/tự động hoá) với cổng
    remote-debugging bật sẵn, y hệt lệnh dòng lệnh trong màn hình Help —
    chỉ để người dùng TỰ TAY đăng nhập tài khoản Google Flow (Gemini Pro
    hoặc tài khoản Flow riêng). Không đụng gì tới trang đăng nhập, không vi
    phạm quy tắc an toàn ở đầu file này (Playwright chỉ connect_over_cdp
    SAU KHI người dùng đã đăng nhập xong bằng tay, ở generate_video()).

    Trả về dict {"already_running": bool, "brought_to_front": bool} để
    frontend hiển thị đúng thông báo — KHÔNG còn báo "đã mở cửa sổ mới" một
    cách vô điều kiện như trước (lỗi thật đã gặp, xem _bring_windows_to_front).
    Nếu Chrome hồ sơ Flow đã chạy sẵn, chỉ cố đưa cửa sổ đó lên trước mặt,
    KHÔNG spawn thêm 1 tiến trình Chrome mới (chỉ gây thêm tab thừa vô ích).
    Nếu chưa chạy, spawn mới rồi CHỜ TỐI ĐA 10 GIÂY xác nhận cổng debug đã
    trả lời trước khi coi là thành công — Popen không ném lỗi không có nghĩa
    là cửa sổ đã thật sự hiện ra."""
    existing_pids = _flow_profile_pids()
    if existing_pids and _cdp_alive():
        brought_to_front = _bring_windows_to_front(existing_pids)
        return {"already_running": True, "brought_to_front": brought_to_front}

    chrome_path = _find_chrome_exe()
    os.makedirs(FLOW_PROFILE_DIR, exist_ok=True)
    subprocess.Popen([
        chrome_path,
        f"--remote-debugging-port={CDP_PORT}",
        f"--user-data-dir={FLOW_PROFILE_DIR}",
        FLOW_URL,
    ])

    for _ in range(20):
        if _cdp_alive():
            return {"already_running": False, "brought_to_front": False}
        time.sleep(0.5)
    raise FlowBrowserStartTimeout(
        "Đã yêu cầu mở Chrome nhưng không xác nhận được cửa sổ khởi động thành "
        "công sau 10 giây. Kiểm tra lại trên máy xem có cửa sổ Chrome nào vừa "
        "mở không (kể cả trong thanh taskbar), hoặc tự mở bằng lệnh trong mục "
        "Help (❓)."
    )


HOME_BUTTON_SELECTOR = "button[aria-label='Home']"
PROMPT_BOX_SELECTOR = "div.ProseMirror[contenteditable='true']"
GENERATE_BUTTON_SELECTOR = "button[aria-label='Start generation']"
VIDEO_RESULT_SELECTOR = "div.video-container.clickable"
DOWNLOAD_BUTTON_SELECTOR = "button[aria-label*='ownload' i]"
RETRY_BUTTON_SELECTOR = "button.try-again-button"
# Phát hiện thật 13/09/2026: có 1 dạng lỗi KHÁC "The agent failed" — thẻ báo lỗi
# với class ".error-title" chứa chữ "Failed", thường kèm "This prompt might
# violate our policies about generating prominent people" (chưa bị trừ credit).
# Selector này KHÔNG trùng RETRY_BUTTON_SELECTOR (thẻ này không có nút "Try
# again" dạng chữ, chỉ có icon) — code cũ không nhận diện được nên cứ chờ hết
# giờ (30-120s) vô ích rồi báo nhầm thành TimeoutError chung chung.
ERROR_CARD_SELECTOR = ".error-title"

# Phát hiện thật 13/09/2026: Flow giờ có thêm bước xác nhận chi phí trước khi
# tạo video ("Would you like me to kick off this 1 video generation, costing
# N credits?" kèm 3 lựa chọn Approve / Always approve / Reject — đều là <span>
# trong <div>, KHÔNG phải <button>, nhưng Playwright click() vẫn bấm được vì
# giả lập chuột thật). Bấm "Always approve" 1 lần để các cảnh sau không phải
# dừng lại chờ nữa (khớp đúng ý "Settings -> Agent để Never" trong docstring
# gốc — đây là đúng chỗ bật nó lên qua hộp thoại thay vì vào Settings).
ALWAYS_APPROVE_TEXT = "Always approve"
APPROVE_TEXT = "Approve"


class FlowNotConnected(RuntimeError):
    """Không nối được vào Chrome ở cổng debug, hoặc không thấy tab Flow nào
    đang mở — người dùng cần tự mở Chrome + đăng nhập trước (xem help_flow_*
    trong app)."""


class FlowGenerationFailed(RuntimeError):
    """Chính Google Flow báo lỗi tạo video ("The agent failed. Please try
    again.") — lỗi tạm thời phía máy chủ Google, không phải lỗi driver. Gọi
    lại generate_video() (project mới) thường sẽ qua được."""


class FlowContentPolicyViolation(RuntimeError):
    """Google Flow từ chối vì nội dung prompt có thể vi phạm chính sách (VD:
    "generating prominent people") — KHÔNG phải lỗi tạm thời, gọi lại y hệt
    prompt cũ sẽ khó qua được. Không tự động thử lại — cần SỬA LẠI nội dung
    prompt (đổi bố cục cảnh, bỏ Character Consistency thừa nếu nhân vật không
    thực sự xuất hiện trong cảnh, v.v. — xem historical-accuracy-research
    SKILL.md). Xác nhận thật: Flow KHÔNG trừ credit khi báo lỗi này."""


def _raise_for_error_card(error_card) -> None:
    """Thẻ lỗi `.error-title` với chữ "Failed" có 2 dạng KHÁC NHAU đã gặp
    thật, dễ nhầm nhau nếu chỉ nhìn tiêu đề:
    1. Có lý do chính sách CỤ THỂ ("This prompt might violate our policies
       about generating prominent people/harmful content...") -> đúng là
       FlowContentPolicyViolation, thử lại y hệt prompt vô ích.
    2. CHỈ có câu chung chung "Sorry, this video failed to generate. You have
       not been charged for this generation." KHÔNG kèm lý do chính sách nào
       -> xác nhận thật 2026-09-13 (cảnh 29, lặp lại giống hệt 5 lần liên
       tiếp dù đã đổi prompt khác hẳn mỗi lần): đây là lỗi kỹ thuật tạm thời
       phía Google, không phải do nội dung prompt -- coi như
       FlowGenerationFailed (được tự thử lại), KHÔNG phải chính sách.
    Phân biệt bằng cách tìm cụm "violate our policies" trong nội dung chi
    tiết của thẻ lỗi (không phân biệt hoa/thường)."""
    detail = error_card.first.locator("xpath=..").inner_text()
    if "violate our policies" in detail.lower():
        raise FlowContentPolicyViolation(
            f"Google Flow từ chối tạo video (không phải lỗi tạm thời, không tự thử lại): {detail}"
        )
    raise FlowGenerationFailed(
        f"Google Flow báo lỗi chung chung không rõ lý do chính sách (coi là lỗi tạm thời, sẽ tự thử lại): {detail}"
    )


def _find_flow_page(browser) -> Page | None:
    for context in browser.contexts:
        for page in context.pages:
            if "flow.google.com" in page.url or "labs.google" in page.url:
                return page
    return None


def generate_video(
    prompt: str,
    output_dir: Path,
    quality_label: str = "720p",
    wait_timeout_seconds: int = 240,
) -> Path:
    """Gõ prompt, bấm tạo, chờ ra video thật, tải về output_dir. Trả về
    đường dẫn file đã tải. Ném FlowNotConnected nếu chưa có Chrome debug port
    + tab Flow đã đăng nhập sẵn (người dùng phải tự làm bước đó trước)."""
    output_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(CDP_URL)
        except Exception as exc:
            raise FlowNotConnected(
                "Chưa nối được vào Chrome (cổng 9222). Người dùng cần tự mở "
                "Chrome bằng lệnh trong mục Help của app rồi đăng nhập Flow trước."
            ) from exc

        page = _find_flow_page(browser)
        if page is None:
            raise FlowNotConnected(
                "Đã nối được Chrome nhưng không thấy tab labs.google/flow nào "
                "đang mở. Mở tab đó lên trước."
            )

        # LUÔN tạo 1 DỰ ÁN MỚI cho mỗi lần gọi — đây là cách chắc chắn duy nhất
        # tránh lẫn kết quả cũ/mới đã kiểm chứng thật. Từng thử "quay về gốc
        # dự án cũ + Start new session" nhưng page.goto() làm SPA tự nhảy về
        # đúng phiên chỉnh sửa (edit) cuối cùng, khiến driver cứ tải đi tải
        # lại đúng 1 video CŨ dù đã đổi prompt khác hẳn (lỗi thật 12/09/2026).
        # Điều hướng trong app (click Home rồi New project) — không dùng
        # page.goto() — mới giữ đúng trạng thái SPA và luôn ra dự án trống.
        #
        # Phát hiện thật 13/09/2026: sau khi generate_video() tải xong 1 video,
        # trang ở lại màn hình "edit" của video đó — màn này KHÔNG có nút Home
        # (chỉ có "Back button to go to previous page" + "Done editing"). Nếu
        # lần gọi kế tiếp gặp đúng màn này, đợi Home 15s vô ích. Nên: thử tìm
        # Home trước; không thấy trong 3s thì bấm "Done editing" (hoặc back
        # nếu không có Done) để thoát ra màn có Home trước đã.
        # Lỗi thật 13/09/2026 (cảnh 29, sau khi 1 project bị đóng đột ngột giữa
        # chừng): trang có thể đang ở ĐÚNG TRANG CHỦ flow.google.com (không có
        # project nào đang mở) — ở trạng thái này KHÔNG có nút Home (vì đã ở
        # nhà rồi, không cần nút "về nhà") NHƯNG CŨNG KHÔNG có nút Back/Done
        # editing (vì không đang ở màn edit nào để thoát ra). Code cũ cứ mặc
        # định bấm "Back button" trong trường hợp này -> không tìm thấy ->
        # treo 30s rồi lỗi. Giờ kiểm tra "New project" có sẵn trực tiếp trước
        # (nghĩa là đã ở trang chủ) — chỉ mới thử Done editing/Back khi thực
        # sự đang kẹt trong màn edit (không thấy cả Home lẫn New project).
        if page.locator(HOME_BUTTON_SELECTOR).count() == 0 and page.get_by_text("New project", exact=False).count() == 0:
            done_btn = page.get_by_role("button", name="Done editing")
            if done_btn.count() > 0:
                done_btn.first.click()
                page.wait_for_timeout(1000)
            else:
                back_btn = page.locator("button[aria-label*='Back button' i]")
                if back_btn.count() > 0:
                    back_btn.first.click()
                    page.wait_for_timeout(1000)

        if page.locator(HOME_BUTTON_SELECTOR).count() > 0:
            page.locator(HOME_BUTTON_SELECTOR).first.click()
            page.wait_for_timeout(1000)
        page.get_by_text("New project", exact=False).first.click()

        # Dự án mới cần vài giây để hiện ô nhập prompt — chờ chủ động thay vì
        # 1 mốc thời gian cố định có thể chưa đủ (gặp lỗi thật: 2s chưa đủ,
        # 3s thì được).
        prompt_ready_deadline = time.monotonic() + 15
        while page.locator(PROMPT_BOX_SELECTOR).count() == 0 and time.monotonic() < prompt_ready_deadline:
            page.wait_for_timeout(500)
        if page.locator(PROMPT_BOX_SELECTOR).count() == 0:
            raise TimeoutError("Dự án mới không hiện ô nhập prompt sau 15s — kiểm tra lại giao diện Flow.")

        # Đảm bảo prompt luôn được diễn giải thành VIDEO — nếu chỉ mô tả cảnh
        # chung chung, agent của Flow có thể tự hiểu là "vẽ ảnh" thay vì
        # "dựng video" (đã gặp thật khi thử nghiệm).
        video_prompt = prompt if prompt.strip().lower().startswith("generate a video") else f"Generate a video: {prompt}"
        # QUAN TRỌNG: bỏ hết xuống dòng thật trong prompt trước khi gõ. Đã gặp
        # lỗi thật 13/09/2026: gõ ký tự "\n" bằng press_sequentially bị ô nhập
        # hiểu là bấm Enter -> gửi luôn phần mới gõ được (cắt cụt prompt giữa
        # chừng, mất hẳn đoạn "Character consistency" phía sau). Gộp thành 1
        # dòng để Enter không bị kích hoạt lúc đang gõ.
        video_prompt = " ".join(video_prompt.split("\n"))

        # Lỗi thật 13/09/2026: prompt càng ngày càng dài (mô tả trang phục/
        # kiến trúc/vũ khí đầy đủ theo skill lịch sử) — có prompt dài hơn
        # 1400 ký tự, gõ với delay=15ms/ký tự mất hơn 20s, cộng thời gian
        # tính toán lại bố cục khi xuống dòng khiến vượt quá 30s mặc định
        # của Playwright. Giảm delay + đặt timeout riêng đủ dài cho thao
        # tác gõ (không dùng timeout mặc định của action).
        #
        # Góp ý thật hữu ích 13/09/2026: gõ từng ký tự (press_sequentially)
        # chậm và dễ timeout với prompt dài (>1000 ký tự). Ô nhập là
        # ProseMirror (rich text) nên fill() thường không tương thích, nhưng
        # DÁN qua clipboard (Ctrl+V) vẫn kích hoạt đúng sự kiện "paste" mà
        # ProseMirror xử lý được — nhanh hơn nhiều (dán tức thì thay vì
        # gõ mất 10-20s). Thử dán trước; nếu ô nhập vẫn trống sau khi dán
        # (trường hợp hiếm, VD trang chưa cấp quyền clipboard) thì rơi về
        # cách gõ từng ký tự cũ để không mất tính năng đã chứng minh chạy được.
        # Lỗi thật 2026-09-13 (lần đầu dùng 1 tài khoản Google mới trên Flow):
        # 1 lớp overlay "cdk-overlay-backdrop" (khung gợi ý/chào mừng đầu
        # phiên, có nút "Close" riêng) che kín trang, khiến prompt_box.click()
        # timeout 30s dù ô nhập đã tồn tại trong DOM (element is not
        # "stable"/bị overlay chặn pointer event). Chủ động đóng overlay này
        # trước nếu có, để không phải đợi hết giờ vô ích.
        if page.locator(".cdk-overlay-backdrop").count() > 0:
            close_btn = page.get_by_role("button", name="Close")
            if close_btn.count() > 0:
                close_btn.first.click(timeout=5000)
                page.wait_for_timeout(500)

        def _generate_button_enabled() -> bool:
            btn = page.locator(GENERATE_BUTTON_SELECTOR).first
            return btn.count() > 0 and btn.is_enabled()

        def _wait_button_enabled(timeout_seconds: float) -> bool:
            deadline = time.monotonic() + timeout_seconds
            while time.monotonic() < deadline:
                if _generate_button_enabled():
                    return True
                page.wait_for_timeout(200)
            return _generate_button_enabled()

        prompt_box = page.locator(PROMPT_BOX_SELECTOR).first
        prompt_box.click()
        page.keyboard.press("Control+A")
        page.keyboard.press("Delete")
        pasted_ok = False
        try:
            page.evaluate("t => navigator.clipboard.writeText(t)", video_prompt)
            page.keyboard.press("Control+V")
            page.wait_for_timeout(300)
            if not prompt_box.inner_text().strip():
                raise RuntimeError("paste không có chữ trong ô nhập")
            # Lỗi thật 2026-09-15 (cảnh 1+2, 2 job liên tiếp): dán qua clipboard
            # có thể khiến CHỮ đã hiện trong ô nhập (inner_text() không rỗng)
            # nhưng Flow (ứng dụng Angular) không nhận ra đây là 1 sự kiện input
            # hợp lệ để MỞ KHOÁ nút "Start generation" — nút vẫn bị disabled dù
            # ô nhập trông như đã có chữ. Code cũ bấm thẳng luôn không kiểm tra
            # gì, khiến Playwright chờ hết 30s mặc định rồi lỗi Timeout (log xác
            # nhận đúng: "element is not enabled" lặp lại tới hết giờ). PHẢI xác
            # nhận nút đã bật thật trước khi coi việc dán là thành công — nếu
            # không, rơi xuống phương án gõ từng ký tự (đáng tin hơn vì kích
            # hoạt đúng sự kiện bàn phím thật mà framework luôn lắng nghe).
            if not _wait_button_enabled(3):
                raise RuntimeError("dán xong nhưng nút Start generation vẫn khoá")
            pasted_ok = True
        except Exception:
            pass

        if not pasted_ok:
            # Chỉ còn là phương án dự phòng hiếm khi chạy tới (dán đã lỗi) —
            # ưu tiên chắc chắn hơn tốc độ, delay 25ms/ký tự (chậm hơn nhưng
            # ổn định hơn 8ms cũ), timeout 120s đủ rộng cho prompt rất dài.
            prompt_box.click()
            page.keyboard.press("Control+A")
            page.keyboard.press("Delete")
            prompt_box.press_sequentially(video_prompt, delay=30, timeout=120000)
            if not _wait_button_enabled(5):
                raise RuntimeError(
                    "Đã gõ prompt vào ô nhập bằng cả 2 cách (dán + gõ từng ký "
                    "tự) nhưng nút 'Start generation' vẫn bị khoá — kiểm tra "
                    "lại giao diện Flow xem có thay đổi gì không (VD: cần chọn "
                    "thêm model/tỉ lệ khung hình trước khi tạo được)."
                )

        page.locator(GENERATE_BUTTON_SELECTOR).first.click()

        # Flow đôi khi hiện kết quả ngay trong khung chat (có 1
        # div.video-container.clickable phải bấm vào trước), đôi khi tự
        # nhảy thẳng vào màn hình edit đã có sẵn nút Download — chờ CẢ HAI
        # khả năng, cái nào xuất hiện trước thì đi theo đường đó.
        #
        # Phát hiện thật 13/09/2026: sau khi bấm Start generation, Flow có thể
        # hiện hộp xác nhận chi phí ("... costing N credits? Approve / Always
        # approve / Reject") BẤT KỲ LÚC NÀO trong lúc chờ (không phải luôn
        # luôn ngay lập tức — có lần vài giây, có lần chậm hơn) — nếu không
        # bấm, Flow tự huỷ sau một lúc và báo "The agent failed" (đã gặp thật,
        # từng tưởng nhầm là lỗi server). Nên phải kiểm tra hộp này ở MỌI vòng
        # lặp của bước chờ chính, không phải chỉ 1 lần đầu cố định. Ưu tiên
        # "Always approve" (để các cảnh sau không phải hỏi lại nữa).
        deadline = time.monotonic() + wait_timeout_seconds
        found_video_container = False
        found_download_button = False
        while time.monotonic() < deadline:
            # Nút này có lúc xuất hiện nhưng bị khoá (đã ở đúng trạng thái
            # "luôn duyệt" từ trước rồi, chỉ hiện cho biết, không cần bấm nữa)
            # — gặp lỗi thật: cố click khi bị khoá làm Playwright chờ mãi tới
            # hết thời gian chờ mà nút không bao giờ "enabled". Dùng timeout
            # ngắn (2s) cho riêng cú click này + bắt lỗi, để lỡ có bị khoá mà
            # is_enabled() không phát hiện ra thì cũng không treo cả vòng chờ.
            for locator_text in (ALWAYS_APPROVE_TEXT, APPROVE_TEXT):
                el = page.get_by_text(locator_text, exact=True)
                if el.count() > 0 and el.first.is_enabled():
                    try:
                        el.first.click(timeout=2000)
                        page.wait_for_timeout(300)
                    except Exception:  # noqa: BLE001 - nút bị khoá theo cách is_enabled() không thấy được, bỏ qua
                        pass
                    break
            if page.locator(VIDEO_RESULT_SELECTOR).count() > 0:
                found_video_container = True
                break
            # Nút Download luôn có mặt từ đầu nhưng bị khoá (disabled) cho
            # tới khi video xong — phải kiểm tra is_enabled(), không chỉ
            # count() (gặp lỗi thật: count() > 0 ngay cả khi chưa xong gì).
            download_btn = page.locator(DOWNLOAD_BUTTON_SELECTOR).first
            if download_btn.count() > 0 and download_btn.is_enabled():
                found_download_button = True
                break
            # Chính Google Flow báo lỗi ("The agent failed. Please try
            # again.") — gặp thật, không phải hiếm: dừng chờ ngay, đừng để
            # timeout 240s vô nghĩa khi Flow đã báo thất bại từ sớm.
            if page.locator(RETRY_BUTTON_SELECTOR).count() > 0:
                raise FlowGenerationFailed(
                    "Google Flow báo 'The agent failed. Please try again.' — "
                    "lỗi tạm thời phía máy chủ Google, không phải lỗi driver. "
                    "Thử gọi lại generate_video() (sẽ tự tạo project mới)."
                )
            # Thẻ lỗi khác (VD "This prompt might violate our policies about
            # generating prominent people") — dừng chờ ngay, không đợi hết
            # 30-120s vô ích. Đọc kèm nội dung thật của thẻ lỗi để biết chính
            # xác lý do (mỗi lần khác nhau), không hardcode 1 câu duy nhất.
            error_card = page.locator(ERROR_CARD_SELECTOR)
            if error_card.count() > 0 and error_card.first.inner_text().strip() == "Failed":
                _raise_for_error_card(error_card)
            time.sleep(5)
        if not found_video_container and not found_download_button:
            raise TimeoutError(
                f"Chờ quá {wait_timeout_seconds}s vẫn chưa thấy video ra — "
                "kiểm tra lại trên cửa sổ Chrome xem Flow có báo lỗi gì không."
            )

        if found_video_container:
            page.locator(VIDEO_RESULT_SELECTOR).last.click()
            page.wait_for_timeout(500)

        # Nút Download vẫn có thể ở trạng thái khoá (disabled) ngay sau khi
        # vừa bấm vào video-container — cần đợi nó thật sự bật lên. Gặp lỗi
        # thật 13/09/2026: trang có thể có NHIỀU nút khớp DOWNLOAD_BUTTON_SELECTOR
        # cùng lúc (vd nút của cảnh trước đó vẫn còn trong DOM), nên ".first"
        # có lúc trỏ nhầm vào 1 nút đang khoá dù nút đúng đã bật — phải quét
        # HẾT các nút khớp mỗi lần kiểm tra, chọn đúng nút nào đang bật.
        # 120s (không phải 30s): video đôi khi cần thêm thời gian mã hoá phía
        # Google sau khi đã thấy khung xem trước, trước khi nút Download thật
        # sự bật lên — gặp lỗi thật (cảnh 3, 4): 30s không đủ.
        download_btn = None
        enable_deadline = time.monotonic() + 120
        while time.monotonic() < enable_deadline:
            for cand in page.locator(DOWNLOAD_BUTTON_SELECTOR).all():
                if cand.is_enabled():
                    download_btn = cand
                    break
            if download_btn is not None:
                break
            # Lỗi thật 2026-09-13 (cảnh 19, sau khi thêm 2 nhân vật có tên vào
            # Character Consistency): video-container xuất hiện trước (khiến
            # vòng chờ chính ở trên thoát ra bình thường), nhưng ngay sau đó
            # Flow mới hiện thẻ lỗi chính sách — vòng chờ nút Download này lại
            # KHÔNG kiểm tra thẻ lỗi, nên chỉ báo nhầm thành TimeoutError
            # chung chung thay vì đúng nguyên nhân. Phải kiểm tra lại thẻ lỗi
            # ở đây nữa, không chỉ ở vòng chờ phía trên.
            error_card = page.locator(ERROR_CARD_SELECTOR)
            if error_card.count() > 0 and error_card.first.inner_text().strip() == "Failed":
                _raise_for_error_card(error_card)
            page.wait_for_timeout(500)
        if download_btn is None:
            raise TimeoutError("Không tìm thấy nút Download nào đang bật sau 120s.")
        download_btn.click(timeout=5000)
        page.wait_for_timeout(500)

        with page.expect_download(timeout=30000) as dl_info:
            page.get_by_text(quality_label, exact=False).first.click()
        download = dl_info.value

        # Lỗi thật 13/09/2026 (cảnh 6, cảnh 1 sau khi sửa): download.path()
        # đôi khi trả về đường dẫn nhưng file chưa kịp ghi xong ra đĩa (race
        # condition hiếm gặp) -> shutil.copy báo FileNotFoundError ngay cả
        # khi download đã "xong" theo Playwright. Thử lại vài lần có chờ
        # thay vì để cả cảnh lỗi luôn.
        tmp_path = None
        for attempt in range(5):
            candidate = download.path()
            if candidate is not None and candidate.exists():
                tmp_path = candidate
                break
            time.sleep(1)
        if tmp_path is None:
            raise RuntimeError("Playwright không trả về file tải hợp lệ sau 5 lần thử — thử lại.")
        final_path = output_dir / download.suggested_filename
        shutil.copy(tmp_path, final_path)
        return final_path


def generate_video_with_retry(
    prompt: str,
    output_dir: Path,
    quality_label: str = "720p",
    wait_timeout_seconds: int = 240,
    max_attempts: int = 3,
    auto_fix_policy_violations: bool = True,
    max_policy_fix_rounds: int = 2,
) -> Path:
    """Giống generate_video(), nhưng tự thử lại tối đa max_attempts lần nếu
    Google Flow báo FlowGenerationFailed (lỗi tạm thời phía máy chủ — đã gặp
    thật, không hiếm). Không tự thử lại khi lỗi là FlowNotConnected (đăng
    nhập/kết nối) vì thử lại không giải quyết được gì, cần người dùng tự mở
    lại Chrome.

    Với FlowContentPolicyViolation: KHÔNG còn dừng lại ngay như trước — nếu
    auto_fix_policy_violations=True (mặc định) và app đã cấu hình Claude (API
    key hoặc tài khoản Pro/Max qua Claude CLI, xem app/services/llm.py), tự
    gọi llm.fix_flow_rejected_prompt() để Claude phân tích lý do Flow từ chối
    và viết lại prompt, rồi thử tạo lại — lặp tối đa max_policy_fix_rounds
    lần. Đây là cơ chế tự động hoàn toàn (Bước 9b, 2026-09-13): người dùng
    KHÔNG cần tự sửa prompt hay chờ ai phân tích thủ công nữa. Nếu Claude
    chưa được cấu hình, hoặc đã thử hết số lần cho phép mà vẫn bị chặn, mới
    ném lại lỗi gốc để người dùng biết và tự xử lý."""
    current_prompt = prompt
    policy_round = 0
    while True:
        last_error: Exception | None = None
        try:
            for attempt in range(1, max_attempts + 1):
                try:
                    return generate_video(current_prompt, output_dir, quality_label, wait_timeout_seconds)
                except FlowGenerationFailed as exc:
                    last_error = exc
                    continue
            assert last_error is not None
            raise last_error
        except FlowContentPolicyViolation as exc:
            if not auto_fix_policy_violations or policy_round >= max_policy_fix_rounds:
                raise
            from app.services import llm  # import trễ để tránh phụ thuộc vòng, và cho phép chạy khi chưa cấu hình LLM

            if not llm.is_configured():
                raise
            policy_round += 1
            print(
                f"[auto-fix] Google Flow từ chối (lần {policy_round}/{max_policy_fix_rounds}): {exc}\n"
                "[auto-fix] Đang nhờ Claude phân tích và tự viết lại prompt, không cần người dùng can thiệp..."
            )
            try:
                fixed_prompt = llm.fix_flow_rejected_prompt(current_prompt, str(exc))
            except Exception as fix_exc:  # noqa: BLE001 - Claude tự sửa thất bại thì báo lỗi gốc, không giấu đi
                print(f"[auto-fix] Gọi Claude để sửa prompt thất bại: {fix_exc}")
                raise exc
            if fixed_prompt.strip() == current_prompt.strip():
                print("[auto-fix] Claude cho rằng đây là báo nhầm ngẫu nhiên, thử lại nguyên văn prompt cũ.")
            else:
                print(f"[auto-fix] Claude đã viết lại prompt:\n{fixed_prompt}")
            current_prompt = fixed_prompt
            continue
