from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from app.api.ai_tools import router as ai_tools_router
from app.api.character_bible import router as character_bible_router
from app.api.error_check import router as error_check_router
from app.api.production import router as production_router
from app.api.project import router as project_router
from app.api.projects_registry import router as projects_registry_router
from app.api.publishing import router as publishing_router
from app.api.quality import router as quality_router
from app.api.settings import router as settings_router
from app.api.story import router as story_router
from app.api.storyboard import router as storyboard_router

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="AI Video Studio")

app.include_router(project_router, prefix="/api")
app.include_router(projects_registry_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(story_router, prefix="/api")
app.include_router(character_bible_router, prefix="/api")
app.include_router(storyboard_router, prefix="/api")
app.include_router(ai_tools_router, prefix="/api")
app.include_router(error_check_router, prefix="/api")
app.include_router(production_router, prefix="/api")
app.include_router(quality_router, prefix="/api")
app.include_router(publishing_router, prefix="/api")


@app.middleware("http")
async def _no_cache_static(request: Request, call_next):
    """App đang phát triển liên tục — nếu không ép "no-cache", trình duyệt
    có thể tự ý phục vụ bản app.js/index.html/style.css CŨ từ cache đĩa mà
    không hỏi lại server (F5 thường không đủ, phải Ctrl+Shift+R), khiến
    người dùng thấy lỗi ĐÃ SỬA vẫn còn y nguyên. `no-cache` (khác
    `no-store`) vẫn cho trình duyệt lưu file nhưng LUÔN phải hỏi lại server
    trước — server trả 304 rất nhanh nếu file chưa đổi, không tốn băng
    thông, chỉ đảm bảo không bao giờ dùng bản cũ mà không kiểm tra."""
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache"
    return response


app.mount("/", StaticFiles(directory=BASE_DIR / "static", html=True), name="static")
