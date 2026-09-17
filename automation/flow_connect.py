"""Nối Playwright vào 1 cửa sổ Chrome THẬT đã mở sẵn (đã đăng nhập bằng tay
người dùng từ trước) — KHÔNG bao giờ tự mở/tự đăng nhập trình duyệt.

Vì sao làm kiểu này: Google chủ động chặn đăng nhập ("Không thể đăng nhập
cho bạn") khi thấy trình duyệt do Playwright TỰ MỞ và điều khiển ngay từ đầu
— dù dùng Chrome thật hay Chrome giả lập, kết quả vẫn bị chặn (đã thử cả 2,
cùng 1 lỗi). Cách khác hẳn: người dùng tự tay mở Chrome, tự tay đăng nhập
Google Flow như bình thường KHÔNG có Playwright nào động vào — sau đó
script này mới "nối vào" (connect_over_cdp) đúng cửa sổ đã đăng nhập sẵn đó
để tự động hoá các bước TIẾP THEO (gõ prompt, bấm nút tạo video, tải video
về). Bước đăng nhập không bao giờ đi qua tay Playwright.

Cách chạy (2 bước, phải làm ĐÚNG THỨ TỰ):

  Bước 1 — KHÔNG cần đóng Chrome đang dùng. Dán lệnh này vào cmd/PowerShell
  để mở 1 hồ sơ Chrome RIÊNG, mới toanh (không đụng gì tới Chrome hàng ngày):

      "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" ^
        --remote-debugging-port=9222 ^
        --user-data-dir="%LOCALAPPDATA%\\AIVideoStudio\\FlowProfile"

  Vào https://labs.google/flow, tự tay đăng nhập (khuyên dùng tài khoản
  Google phụ, không phải Gmail chính — vì đây là hồ sơ mới nên sẽ trống,
  chưa đăng nhập gì), vào tới màn hình tạo video.

  Bước 2 — chạy script này:
      .venv/Scripts/python.exe automation/flow_connect.py
"""

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

DUMP_FILE = Path(__file__).resolve().parent / "flow_page_dump.json"
CDP_URL = "http://localhost:9222"


def dump_page_structure(page) -> dict:
    elements = page.eval_on_selector_all(
        "textarea, button, input, a, [role='button'], [role='textbox'], [contenteditable='true'], [contenteditable='']",
        """(els) => els.map((el) => ({
            tag: el.tagName.toLowerCase(),
            text: (el.innerText || el.value || "").trim().slice(0, 80),
            aria_label: el.getAttribute("aria-label"),
            placeholder: el.getAttribute("placeholder") || el.getAttribute("aria-placeholder") || el.getAttribute("data-placeholder"),
            role: el.getAttribute("role"),
            contenteditable: el.getAttribute("contenteditable"),
            id: el.id || null,
            class_name: (el.className && typeof el.className === "string") ? el.className.slice(0, 120) : null,
            visible: !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length),
        })).filter((e) => e.visible)""",
    )
    return {"url": page.url, "title": page.title(), "elements": elements}


def main() -> None:
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(CDP_URL)
        except Exception as exc:  # noqa: BLE001 - report plainly, this is a CLI tool
            print(
                "Không nối được vào Chrome ở cổng 9222.\n"
                "Kiểm tra lại: Chrome đã được đóng hết và mở lại đúng bằng lệnh "
                "--remote-debugging-port=9222 chưa? Xem hướng dẫn ở đầu file này.\n"
                f"Lỗi gốc: {exc}",
                flush=True,
            )
            sys.exit(1)

        flow_page = None
        for context in browser.contexts:
            for page in context.pages:
                if "labs.google" in page.url or "flow" in page.url:
                    flow_page = page
                    break
            if flow_page:
                break

        if flow_page is None:
            print(
                "Đã nối được vào Chrome, nhưng không thấy tab nào đang mở "
                "labs.google/flow. Mở tab đó lên rồi chạy lại script này.",
                flush=True,
            )
            sys.exit(1)

        print(f"Đã nối vào đúng tab Flow: {flow_page.url}", flush=True)
        dump = dump_page_structure(flow_page)
        DUMP_FILE.write_text(json.dumps(dump, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Đã lưu cấu trúc trang vào {DUMP_FILE}", flush=True)
        # Không đóng browser — đây là cửa sổ Chrome thật của người dùng,
        # Playwright chỉ "mượn xem", không được tự ý đóng lại.


if __name__ == "__main__":
    main()
