# api_server.py
"""
PromptForge 多端 API 服务端（P5.5b 改造版）

通过 FastAPI 暴露核心能力，供手机端 / Web 端 / 小程序调用。
所有生成接口统一走 skills.registry，与 GUI/CLI/WS 共享同一套 skill 实现。

改造要点（vs 上一版）：
  ✅ 修复 /api/chat_llm / /api/chat_llm_stream / /api/chat 依赖未定义对象（会 500）
  ✅ /api/generate_image / /api/image_to_image / /api/generate_video 全部走 skill
  ✅ 所有未知 Request 模型改为 dict = Body(...)，避免 NameError
  ✅ 修复 preset_bridge.build_full_prompt 不存在 → 改用 build_prompt
  ✅ catch_all 路径遍历防护（startswith(base + os.sep)）
  ✅ 清理冗余 import，简化文件结构
  ✅ 保留 /api/run_skill / /api/skill/* / /api/skills
  ✅ 保留 token 认证
"""

import logging
import os
import hmac
import io
import time
import shutil
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool
from PIL import Image

from config.settings import settings
from core.intent_analyzer import IntentAnalyzer
from providers import list_providers, get_meta
from model_manager import list_checkpoints

try:
    from preset_bridge import preset_bridge
    from presets_meta import get_display_name, get_category, CATEGORY_ORDER
except ImportError:
    preset_bridge = None


# ============================================================
# 日志 & App
# ============================================================

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="PromptForge API", description="多端 AI 任务调度中心")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# 🔒 Token 认证
# ============================================================

_WEB_TOKEN = os.getenv("PF_WEB_TOKEN", "").strip()
_PUBLIC_PATHS = {"/", "/favicon.ico"}
_PUBLIC_PREFIXES = ("/static/",)


def _extract_token(request: Request) -> str:
    return (
        request.headers.get("x-pf-token")
        or request.query_params.get("token")
        or ""
    )


def _check_token(candidate: str) -> bool:
    if not _WEB_TOKEN:
        return True
    if not candidate:
        return False
    return hmac.compare_digest(candidate, _WEB_TOKEN)


@app.middleware("http")
async def _auth_middleware(request: Request, call_next):
    path = request.url.path
    if path in _PUBLIC_PATHS:
        return await call_next(request)
    if any(path.startswith(p) for p in _PUBLIC_PREFIXES):
        return await call_next(request)
    if not _check_token(_extract_token(request)):
        return JSONResponse(
            {"error": "unauthorized", "hint": "URL 加 ?token=xxx"},
            status_code=401,
        )
    return await call_next(request)


# ============================================================
# 共享实例 / 辅助
# ============================================================

_analyzer = IntentAnalyzer()
_API_OUTPUT = settings.output_dir / "api"
_API_OUTPUT.mkdir(parents=True, exist_ok=True)


def _get_skill(name: str, **config_overrides):
    """按名字拿 skill 实例（统一构造逻辑）。"""
    from skills.registry import get_meta as _gm, import_skill_class
    meta = _gm(name)
    if meta is None:
        raise ValueError(f"未知 skill: {name}")
    cls = import_skill_class(meta)
    config = {"output_dir": str(_API_OUTPUT), "log_level": "INFO"}
    config.update(config_overrides)
    return cls(config)


class SkillRequest(BaseModel):
    skill_name: str
    kwargs: dict = {}


# ============================================================
# 图像生成
# ============================================================

@app.post("/api/generate_image")
async def generate_image(req: dict = Body(...)):
    """文生图（走 image_generator skill）。

    请求体：{prompt, primary_provider?, model_id?, width?, height?, steps?, preset?}
    """
    prompt = (req.get("prompt") or "").strip()
    if not prompt:
        return {"status": "error", "message": "prompt 不能为空"}

    final_prompt = prompt
    preset = req.get("preset")
    if preset and preset_bridge:
        try:
            if hasattr(preset_bridge, "build_prompt"):
                final_prompt = preset_bridge.build_prompt(
                    preset=preset,
                    subject_override=prompt,
                )
            else:
                final_prompt = f"{prompt}, {preset} style"
            logger.info(f"🎨 预设 {preset} → {final_prompt[:100]}...")
        except Exception as e:
            logger.warning(f"预设解析失败: {e}")

    try:
        skill = _get_skill(
            "image_generator",
            output_dir=str(_API_OUTPUT),
            image_width=int(req.get("width", 1024)),
            image_height=int(req.get("height", 1024)),
            steps=int(req.get("steps", 25)),
            engine=req.get("primary_provider") or None,
        )
        result = await run_in_threadpool(skill.generate, final_prompt)

        if result.get("status") != "success":
            return result

        r = result["result"]
        filename = os.path.basename(r["image_path"])
        return {
            "status": "success",
            "message": "生成成功",
            "image_url": f"/output/api/{filename}",
            "provider": r.get("engine"),
            "width": r.get("width"),
            "height": r.get("height"),
            "seed": r.get("seed"),
        }
    except Exception as e:
        logger.exception("generate_image 失败")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/image_to_image")
async def image_to_image(
    prompt: str = Form(""),
    provider: str = Form(""),
    image: UploadFile = File(...),
):
    """图生图（走 image_generator skill）。"""
    try:
        contents = await image.read()
        init_img = Image.open(io.BytesIO(contents)).convert("RGB")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"图片解析失败: {e}")

    try:
        skill = _get_skill(
            "image_generator",
            output_dir=str(_API_OUTPUT),
            engine=provider or None,
        )
        result = await run_in_threadpool(
            skill.generate_from_image,
            prompt=prompt if prompt else "masterpiece, high quality",
            image=init_img,
            strength=0.7,
        )

        if result.get("status") != "success":
            return result

        r = result["result"]
        filename = os.path.basename(r["image_path"])
        return {
            "status": "success",
            "image_url": f"/output/api/{filename}",
            "provider": r.get("engine"),
        }
    except Exception as e:
        logger.exception("image_to_image 失败")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# 视频生成
# ============================================================

@app.post("/api/generate_video")
async def generate_video(req: dict = Body(...)):
    """视频生成（走 video_generator skill）。

    请求体：{topic, duration?}
    """
    topic = (req.get("topic") or "").strip()
    if not topic:
        return {"status": "error", "message": "topic 不能为空"}

    duration = int(req.get("duration", 15))

    try:
        skill = _get_skill("video_generator", output_dir=str(_API_OUTPUT))
        result = await run_in_threadpool(skill.generate, prompt=topic, duration=duration)

        if result.get("status") != "success":
            return result

        r = result["result"]
        video_path = r.get("video_path", "")
        if not video_path or not os.path.exists(video_path):
            return {"status": "error", "message": "未返回视频路径"}

        filename = os.path.basename(video_path)
        return {
            "status": "success",
            "video_url": f"/output/api/{filename}",
            "duration": r.get("duration"),
        }
    except Exception as e:
        logger.exception("generate_video 失败")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# LLM 对话
# ============================================================

@app.post("/api/chat_llm")
async def chat_llm(req: dict = Body(...)):
    """LLM 对话（Agnes 优先，Ollama 兜底）。"""
    text = (req.get("text") or "").strip()
    if not text:
        return {"status": "error", "message": "text 不能为空"}

    system = req.get("system_prompt") or None

    try:
        from core.llm_client import get_default_client
        llm = get_default_client()
        response = await run_in_threadpool(llm.generate, text, system=system)
        if not response:
            return {"status": "error", "message": "LLM 无响应"}
        return {"status": "success", "response": response}
    except Exception as e:
        logger.exception("chat_llm 失败")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat_llm_stream")
async def chat_llm_stream(req: dict = Body(...)):
    """LLM 对话（伪流式：一次性生成，按句切 SSE）。

    LLMClient 暂不支持 token 级流式。前端接口形态不变，
    只是会一次性收到完整回复（分句 SSE）。
    """
    text = (req.get("text") or "").strip()
    system = req.get("system_prompt") or None

    async def err_gen(msg: str):
        yield f"data: [Error: {msg}]\n\n"

    if not text:
        return StreamingResponse(err_gen("text 不能为空"), media_type="text/event-stream")

    async def gen():
        try:
            from core.llm_client import get_default_client
            llm = get_default_client()
            response = await run_in_threadpool(llm.generate, text, system=system)
            if not response:
                yield "data: [Error: LLM 无响应]\n\n"
                return
            buf = ""
            for ch in response:
                buf += ch
                if ch in "。！？\n" and buf.strip():
                    yield f"data: {buf}\n\n"
                    buf = ""
            if buf.strip():
                yield f"data: {buf}\n\n"
        except Exception as e:
            yield f"data: [Error: {str(e)}]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/api/chat")
async def chat_endpoint(req: dict = Body(...)):
    """意图分析（不生成，只返回意图类型）。"""
    text = (req.get("text") or "").strip()
    has_image = bool(req.get("has_image", False))

    if not text:
        return {"status": "error", "message": "text 不能为空"}

    try:
        intent = _analyzer.analyze(text, has_image=has_image)
        return {
            "status": "success",
            "intent_type": intent.type,
            "params": intent.params,
            "system_hint": intent.system_hint,
        }
    except Exception as e:
        logger.exception("chat_endpoint 失败")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# 元数据 / 列表接口
# ============================================================

@app.get("/api/llm_models")
def get_llm_models():
    """获取本地 Ollama 可用模型列表。"""
    try:
        import requests
        res = requests.get(
            "http://127.0.0.1:11434/api/tags",
            timeout=5,
            proxies={"http": None, "https": None},
        )
        res.raise_for_status()
        models = [m["name"] for m in res.json().get("models", [])]
        return {"status": "success", "data": models}
    except Exception as e:
        return {"status": "error", "message": f"获取 Ollama 模型失败: {e}"}


@app.get("/api/models")
def get_models():
    """获取所有本地模型列表。"""
    try:
        return {"status": "success", "data": list_checkpoints()}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/providers")
def get_providers():
    """获取所有可用的图像生成提供商。"""
    try:
        result = []
        for p in list_providers("image"):
            meta = get_meta(p)
            result.append({
                "id": p,
                "name": meta.get("description", p),
                "free": meta.get("free", False),
            })
        return {"status": "success", "data": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/presets")
def get_presets():
    """获取所有预设列表。"""
    if not preset_bridge:
        return {"status": "error", "message": "Preset bridge 不可用"}
    try:
        all_presets = preset_bridge.list_presets()
        sorted_presets = sorted(
            all_presets,
            key=lambda p: (
                CATEGORY_ORDER.index(get_category(p))
                if get_category(p) in CATEGORY_ORDER else 999,
                p,
            ),
        )
        data = [
            {"id": p, "name": get_display_name(p), "category": get_category(p)}
            for p in sorted_presets
        ]
        return {"status": "success", "data": data}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/gallery")
def get_gallery():
    """获取已生成的图片列表（最多 50 张）。"""
    if not _API_OUTPUT.exists():
        return {"status": "success", "data": []}

    files = []
    for f in _API_OUTPUT.iterdir():
        if not f.is_file() or f.suffix.lower() not in (".png", ".jpg", ".jpeg"):
            continue
        mtime = f.stat().st_mtime
        files.append({
            "filename": f.name,
            "url": f"/output/api/{f.name}",
            "time": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S"),
            "_mtime": mtime,
        })

    files.sort(key=lambda x: x["_mtime"], reverse=True)
    for f in files:
        del f["_mtime"]
    return {"status": "success", "data": files[:50]}


# ============================================================
# Skill 接口
# ============================================================

@app.get("/api/skills")
def get_skills():
    """列出所有已注册的 skill（18 个）。"""
    try:
        from skills.registry import list_skills, get_meta as _gm
        result = []
        for name in list_skills():
            m = _gm(name)
            if not m:
                continue
            result.append({
                "name": m.name,
                "source": m.source,
                "keywords": list(m.keywords),
                "system_hint": m.system_hint,
                "category": m.category,
                "outputs": list(m.outputs),
                "class_path": m.class_path,
            })
        return {"status": "success", "count": len(result), "data": result}
    except Exception as e:
        logger.exception("get_skills 失败")
        return {"status": "error", "message": str(e)}


@app.post("/api/run_skill")
async def run_skill(req: SkillRequest):
    """运行指定的 Skill（支持 skills.registry 里的全部 18 个）。"""
    skill_name = req.skill_name
    req_kwargs = req.kwargs or {}

    try:
        from skills.registry import get_meta as _gm, import_skill_class

        meta = _gm(skill_name)

        # 情况 A：registry 里没有 → 回退旧 SKILL_ROUTES
        if meta is None:
            from core.skill_routes import SKILL_ROUTES
            if skill_name not in SKILL_ROUTES:
                return {"status": "error", "message": f"未知的技能: {skill_name}"}
            cfg = SKILL_ROUTES[skill_name]
            import importlib
            mod = importlib.import_module(cfg["module"])
            skill_cls = getattr(mod, cfg["class"])
            skill = skill_cls()
            result = await run_in_threadpool(skill.execute, **req_kwargs)
            return {"status": "success", "result": result}

        # 情况 B：走 registry
        merged = dict(req_kwargs)
        if meta.kwargs_builder:
            try:
                defaults = meta.kwargs_builder({"prompt": "", "original_text": ""}) or {}
                merged = {**defaults, **merged}
                logger.info(
                    f"skill={skill_name} kwargs: defaults={defaults} "
                    f"user={req_kwargs} merged={merged}"
                )
            except Exception as e:
                logger.warning(f"kwargs_builder 失败 (skill={skill_name}): {e}")

        skill_cls = import_skill_class(meta)
        config = {"output_dir": str(settings.output_dir), "log_level": "INFO"}
        skill = skill_cls(config)
        result = await run_in_threadpool(skill.execute, **merged)

        if isinstance(result, dict) and result.get("status") == "error":
            return {
                "status": "error",
                "message": result.get("error", "未知错误"),
                "result": result,
            }
        return {"status": "success", "result": result}

    except Exception as e:
        logger.error(f"技能 {skill_name} 执行失败: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}


@app.post("/api/skill/image_curator")
async def run_image_curator(req: dict = Body(...)):
    """图片鉴赏任务（老接口兼容）。"""
    try:
        payload = req.get("payload") or {}
        folder = payload.get("folder", "output")
        skill = _get_skill("image_curator")
        result = await run_in_threadpool(skill.curate, folder)
        return {"status": "success", "result": result}
    except Exception as e:
        logger.exception("image_curator 失败")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/skill/video_generator")
async def run_video_generator(req: dict = Body(...)):
    """视频生成任务（老接口兼容）。"""
    try:
        payload = req.get("payload") or {}
        topic = payload.get("topic", "默认主题")
        skill = _get_skill("video_generator", output_dir=str(_API_OUTPUT))
        result = await run_in_threadpool(skill.generate, prompt=topic, duration=15)
        return {"status": "success", "result": result}
    except Exception as e:
        logger.exception("video_generator 失败")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# 静态挂载 / 首页 / catch-all
# ============================================================

os.makedirs("static", exist_ok=True)
app.mount("/output", StaticFiles(directory=str(settings.output_dir)), name="output")
app.mount("/static", StaticFiles(directory="static"), name="static_files")


@app.get("/")
async def read_index():
    return FileResponse("static/index.html")


@app.get("/{full_path:path}")
async def catch_all(full_path: str):
    """SPA 兜底（带路径遍历防护）。"""
    base = os.path.abspath("static")
    target = os.path.abspath(os.path.join(base, full_path))
    if not (target == base or target.startswith(base + os.sep)):
        return FileResponse("static/index.html")
    if os.path.isfile(target):
        return FileResponse(target)
    return FileResponse("static/index.html")


# ============================================================
# main
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)