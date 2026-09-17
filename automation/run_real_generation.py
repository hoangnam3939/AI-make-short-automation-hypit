"""Chạy THẬT 37 cảnh qua Google Flow (tốn credit Pro thật) — Bước 6 trong kế
hoạch tối 2026-09-13. Đọc scene_prompts_final.json, gọi
google_flow_driver.generate_video_with_retry() cho từng cảnh, lưu progress ra
generation_progress.json để có thể xem tiến độ / chạy tiếp nếu giữa chừng lỗi
(không chạy lại từ đầu các cảnh đã xong).
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from app.services.google_flow_driver import (  # noqa: E402
    FlowGenerationFailed,
    FlowNotConnected,
    generate_video_with_retry,
)

AUTOMATION_DIR = Path(__file__).resolve().parent
DOWNLOADS_DIR = AUTOMATION_DIR / "downloads"
PROGRESS_PATH = AUTOMATION_DIR / "generation_progress.json"
PROMPTS_PATH = AUTOMATION_DIR / "scene_prompts_final.json"


def _load_progress() -> dict:
    if PROGRESS_PATH.exists():
        return json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))
    return {}


def _save_progress(progress: dict) -> None:
    PROGRESS_PATH.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    scenes = json.loads(PROMPTS_PATH.read_text(encoding="utf-8"))
    progress = _load_progress()
    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

    total = len(scenes)
    done = sum(1 for s in scenes if progress.get(str(s["scene_n"]), {}).get("status") == "done")
    print(f"[run_real_generation] Tổng {total} cảnh, đã xong sẵn {done} cảnh trước đó.")

    for scene in scenes:
        key = str(scene["scene_n"])
        entry = progress.get(key, {})
        if entry.get("status") == "done" and entry.get("path") and Path(entry["path"]).exists():
            print(f"[scene {key}] đã xong trước đó, bỏ qua: {entry['path']}")
            continue

        scene_dir = DOWNLOADS_DIR / f"scene_{scene['scene_n']:02d}"
        print(f"[scene {key}] bắt đầu tạo... ({scene['start']}s-{scene['end']}s)")
        t0 = time.monotonic()
        try:
            path = generate_video_with_retry(
                scene["prompt"], scene_dir, quality_label="720p",
                wait_timeout_seconds=240, max_attempts=3,
            )
            elapsed = round(time.monotonic() - t0, 1)
            print(f"[scene {key}] XONG sau {elapsed}s -> {path}")
            progress[key] = {"status": "done", "path": str(path), "elapsed_sec": elapsed}
        except FlowNotConnected as exc:
            print(f"[scene {key}] MẤT KẾT NỐI CHROME: {exc}")
            progress[key] = {"status": "error", "error": "FlowNotConnected", "message": str(exc)}
            _save_progress(progress)
            print("[run_real_generation] Dừng lại vì mất kết nối Chrome — cần người dùng mở lại Chrome debug port 9222.")
            return
        except FlowGenerationFailed as exc:
            print(f"[scene {key}] LỖI (đã thử lại 3 lần vẫn fail): {exc}")
            progress[key] = {"status": "error", "error": "FlowGenerationFailed", "message": str(exc)}
        except Exception as exc:  # noqa: BLE001 - không để 1 cảnh lỗi chặn cả 37 cảnh
            print(f"[scene {key}] LỖI KHÔNG XÁC ĐỊNH: {exc}")
            traceback.print_exc()
            progress[key] = {"status": "error", "error": type(exc).__name__, "message": str(exc)}

        _save_progress(progress)

    done_final = sum(1 for s in scenes if progress.get(str(s["scene_n"]), {}).get("status") == "done")
    failed = [k for k, v in progress.items() if v.get("status") == "error"]
    print(f"[run_real_generation] HOÀN TẤT: {done_final}/{total} cảnh thành công.")
    if failed:
        print(f"[run_real_generation] Các cảnh LỖI cần chạy lại: {sorted(failed, key=int)}")


if __name__ == "__main__":
    main()
