# apps/web_server/main.py
"""FastAPI + WebSocket 服务端。

架构：
  [Browser] <-- WebSocket --> [FastAPI async loop]
                                    |
                                    | asyncio.run_coroutine_threadsafe
                                    v
                        [EventBus 同步] <--> [Orchestrator 同步]
                                    ^
                                    |
                              [ThreadPoolExecutor]

每个 WebSocket 连接拥有独立的 Orchestrator（独立会话），
共享 providers / pipeline_pool / settings。
"""

from __future__ import annotations

import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# 项目根加入 sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from application.events import EventBus
from application.context import AppContext
from application.orchestrator import Orchestrator
from config.settings import settings

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"
ALLOWED_FILE_ROOTS = [
    Path(settings.output_dir).resolve(),
    (PROJECT_ROOT / "assets").resolve(),
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"🚀 Web server starting | mode={getattr(settings, 'generation_mode', '?')}")
    yield
    logger.info("👋 Web server stopped")


app = FastAPI(title="PromptForge Web", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ============================================================
# HTTP
# ============================================================

@app.get("/")
async def index():
    idx = STATIC_DIR / "index.html"
    if not idx.exists():
        return JSONResponse({"error": "index.html not found"}, status_code=500)
    return FileResponse(str(idx))


@app.get("/health")
async def health():
    return {
        "ok": True,
        "mode": getattr(settings, "generation_mode", "?"),
        "provider": getattr(settings, "api_provider", "?"),
    }


@app.get("/api/file")
async def serve_file(path: str = Query(..., description="文件绝对路径")):
    """提供 output_dir / assets 下的文件（图片、文章、视频等）。"""
    p = Path(path)
    if not p.exists() or not p.is_file():
        return JSONResponse({"error": "not found"}, status_code=404)

    p_resolved = p.resolve()
    if not any(str(p_resolved).startswith(str(root)) for root in ALLOWED_FILE_ROOTS):
        return JSONResponse({"error": "forbidden"}, status_code=403)

    return FileResponse(str(p_resolved))


# ============================================================
# WebSocket
# ============================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    loop = asyncio.get_running_loop()

    bus = EventBus()
    ctx = AppContext.headless(settings, bus=bus)
    orch = Orchestrator(bus, ctx)

    def push(event):
        payload = {"type": event.type, **event.payload}
        try:
            asyncio.run_coroutine_threadsafe(
                websocket.send_json(payload),
                loop,
            )
        except Exception as e:
            logger.warning(f"push 失败: {e}")

    bus.on("*", push)

    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action", "text")

            if action == "text":
                text = (data.get("text") or "").strip()
                if text:
                    loop.run_in_executor(None, orch.handle_text, text)

            elif action == "skill":
                name = data.get("name")
                kwargs = data.get("kwargs") or {}
                if name:
                    loop.run_in_executor(
                        None,
                        lambda n=name, k=kwargs: orch.run_skill(n, **k),
                    )

            elif action == "cancel":
                try:
                    orch.cancel()
                except Exception as e:
                    logger.warning(f"cancel 失败: {e}")

            elif action == "list_skills":
                from skills.registry import list_skills, get_meta
                skills = []
                for n in list_skills():
                    m = get_meta(n)
                    skills.append({
                        "name": n,
                        "source": m.source if m else "?",
                        "keywords": list(m.keywords) if m else [],
                        "system_hint": m.system_hint if m else "",
                    })
                await websocket.send_json({"type": "skills_list", "skills": skills})

            elif action == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        logger.info("WebSocket 断开")
    except Exception:
        logger.exception("WebSocket 异常")
    finally:
        bus.clear()
        try:
            await websocket.close()
        except Exception:
            pass


# ============================================================
# 启动
# ============================================================

def run(host: str = "0.0.0.0", port: int = 8000):
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    run(host=args.host, port=args.port)