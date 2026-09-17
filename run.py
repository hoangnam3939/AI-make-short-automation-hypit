"""Launcher: cháº¡y server local rá»“i tá»± má»Ÿ trĂ¬nh duyá»‡t â€” giá»‘ng cĂ¡ch Google Flow má»Ÿ.
Xem README.md."""
import threading
import time
import webbrowser

import uvicorn

HOST = "127.0.0.1"
PORT = 8789


def _open_browser():
    time.sleep(1.2)
    webbrowser.open(f"http://{HOST}:{PORT}")


if __name__ == "__main__":
    threading.Thread(target=_open_browser, daemon=True).start()
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=False)
