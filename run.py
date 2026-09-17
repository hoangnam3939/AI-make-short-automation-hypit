"""Launcher: chạy server local rồi tự mở trình duyệt — giống cách Google Flow mở.
Xem README.md."""
import threading
import time
import webbrowser

import uvicorn

HOST = "127.0.0.1"
PORT = 8787


def _open_browser():
    time.sleep(1.2)
    webbrowser.open(f"http://{HOST}:{PORT}")


if __name__ == "__main__":
    threading.Thread(target=_open_browser, daemon=True).start()
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=False)
