# api_server.py
"""
PromptForge 多端 API 服务端
通过 FastAPI 暴露核心能力，供手机端、Web 端或小程序调用。
"""

import logging
from typing import Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

# 导入你的核心组件
from config.settings import settings
from core.intent_analyzer import IntentAnalyzer
from providers.base import ImageRequest
from providers.fallback import FallbackImageProvider
from providers import list_providers, get_meta
from model_manager import list_checkpoints

try:
    from preset_bridge import preset_bridge
    from presets_meta import get_display_name, get_category, CATEGORY_ORDER
except ImportError:
    preset_bridge = None


from providers.base import TextRequest
from providers.base import ImageRequest
from providers.registry import create

from fastapi.responses import StreamingResponse

import os
import time
from datetime import datetime

from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import base64
import io
from PIL import Image

from fastapi.staticfiles import StaticFiles
    
# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="PromptForge API", description="多端 AI 任务调度中心")

# 允许跨域（方便手机网页或前端调试）
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
import os
import hmac
from fastapi import Request
from fastapi.responses import JSONResponse

# .env 里设 PF_WEB_TOKEN=<长随机串>；为空 = 不校验（仅限本地）
_WEB_TOKEN = os.getenv("PF_WEB_TOKEN", "").strip()

# 公开路径（无需 token）
_PUBLIC_PATHS = {"/", "/favicon.ico"}
_PUBLIC_PREFIXES = ("/static/",)   # 前端资源


def _extract_token(request: Request) -> str:
    return (
        request.headers.get("x-pf-token")
        or request.query_params.get("token")
        or ""
    )


def _check_token(candidate: str) -> bool:
    if not _WEB_TOKEN:
        return True                      # 未配置 → 放行（本地开发）
    if not candidate:
        return False
    return hmac.compare_digest(candidate, _WEB_TOKEN)


@app.middleware("http")
async def _auth_middleware(request: Request, call_next):
    path = request.url.path

    # 首页 + 静态资源放行（前端自己会带 token 请求 API）
    if path in _PUBLIC_PATHS:
        return await call_next(request)
    if any(path.startswith(p) for p in _PUBLIC_PREFIXES):
        return await call_next(request)

    # ⚠️ /output/* 和所有 API 一律要求 token
    if not _check_token(_extract_token(request)):
        return JSONResponse(
            {"error": "unauthorized", "hint": "URL 加 ?token=xxx"},
            status_code=401,
        )

    return await call_next(request)
    
from fastapi import Request
from fastapi.responses import JSONResponse

@app.post("/api/skill/image_curator")
async def run_image_curator(req: dict = Body(...)):
    """图片鉴赏任务"""
    try:
        from skills.image_curator import ImageCurator
        payload = req.get("payload") or {}
        folder = payload.get("folder", "output")
        curator = ImageCurator({})
        result = await run_in_threadpool(curator.curate, folder, "鉴赏报告")
        return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/skill/video_generator")
async def run_video_generator(req: dict = Body(...)):
    """视频生成任务"""
    try:
        from skills.video_generator import VideoGenerator
        payload = req.get("payload") or {}
        topic = payload.get("topic", "默认主题")
        gen = VideoGenerator({"output_dir": "output/videos"})
        result = await run_in_threadpool(gen.generate, prompt=topic, duration=15)
        return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat_llm")
async def chat_llm(req: ChatLLMRequest):
    try:
        provider = create("ollama_local", config={"model": req.model}) # ★ 使用前端传来的模型
        text_req = TextRequest(prompt=req.text, system_prompt=req.system_prompt)
        
        response_text = await run_in_threadpool(provider.chat, text_req)
        return {"status": "success", "response": response_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 新增一个路由（保留原来的 /api/chat_llm 作为非流式备用）
@app.post("/api/chat_llm_stream")
async def chat_llm_stream(req: ChatLLMRequest):
    provider = create("ollama_local", config={"model": req.model})
    text_req = TextRequest(prompt=req.text, system_prompt=req.system_prompt)
    
    # 用一个生成器包装流式输出
    def event_generator():
        try:
            for chunk in provider.chat_stream(text_req):
                # SSE 标准格式： "data: 你的内容\n\n"
                yield f"data: {chunk}\n\n"
        except Exception as e:
            yield f"data: [Error: {str(e)}]\n\n"
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")
    
@app.get("/api/llm_models")
def get_llm_models():
    """获取本地 Ollama 可用模型列表"""
    try:
        import requests
        # 禁用代理
        res = requests.get("http://127.0.0.1:11434/api/tags", timeout=5, proxies={"http": None, "https": None})
        res.raise_for_status()
        models = [m["name"] for m in res.json().get("models", [])]
        return {"status": "success", "data": models}
    except Exception as e:
        return {"status": "error", "message": f"获取 Ollama 模型失败: {e}"}
        
@app.get("/api/models")
def get_models():
    """获取所有本地模型列表（供手机端下拉框使用）"""
    models = list_checkpoints()
    return {"status": "success", "data": models}

@app.get("/api/providers")
def get_providers():
    """获取所有可用的图像生成提供商（本地/云端）"""
    all_providers = list_providers("image")
    result = []
    for p in all_providers:
        meta = get_meta(p)
        result.append({"id": p, "name": meta.get("description", p), "free": meta.get("free", False)})
    return {"status": "success", "data": result}


@app.get("/api/presets")
def get_presets():
    """获取所有预设列表"""
    if not preset_bridge:
        return {"status": "error", "message": "Preset bridge 不可用"}
    
    try:
        all_presets = preset_bridge.list_presets()
        # 按分类排序
        sorted_presets = sorted(
            all_presets,
            key=lambda p: (
                CATEGORY_ORDER.index(get_category(p)) if get_category(p) in CATEGORY_ORDER else 999,
                p,
            )
        )
        
        data = []
        for p in sorted_presets:
            data.append({
                "id": p,
                "name": get_display_name(p),
                "category": get_category(p)
            })
            
        return {"status": "success", "data": data}
    except Exception as e:
        return {"status": "error", "message": str(e)}
        
@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    """
    统一聊天入口（未来可以集成 Ollama 本地文本大模型）
    目前先返回意图识别结果，验证路由是否通畅。
    """
    intent = analyzer.analyze(req.text, has_image=req.has_image)
    return {
        "status": "success",
        "intent_type": intent.type,
        "params": intent.params,
        "system_hint": intent.system_hint
    }

@app.post("/api/generate_image")
async def generate_image(req: GenerateImageRequest):
    logger.info(f"📥 收到生图请求: {req.prompt[:20]}... (模型: {req.model_id}, 引擎: {req.primary_provider})")
    
    primary = req.primary_provider or "local_sd"
    all_image_providers = list_providers("image")
    
    if primary not in all_image_providers:
        primary = all_image_providers[0] if all_image_providers else "agnes"

    pool = [p for p in all_image_providers if p != primary]
    
    # 2. 组装配置
    configs = {}
    for p in [primary] + pool:
        if p == "local_sd":
            # ★ 将前端传过来的模型 ID 注入给适配器
            configs[p] = {"device": "CPU"}
            if req.model_id:
                configs[p]["model_id"] = req.model_id
        else:
            configs[p] = settings.get_provider_config(p)

    # 3. 构建 Provider
    provider = FallbackImageProvider(
        primary=primary,
        fallback=pool,
        configs=configs,
        on_fallback=lambda frm, to, err: logger.warning(f"⚠️ {frm} 失败，切换到 {to}")
    )

    final_prompt = req.prompt
    if req.preset:
        try:
            from preset_bridge import preset_bridge
            # ★ 核心：如果你的 preset_bridge 有获取完整 6 层 prompt 的方法，在这里调用
            # 这里写一个兼容逻辑，如果没提供 prompt，就给它一个默认主体
            base_subject = req.prompt if req.prompt else "masterpiece, best quality"
            
            # 假设你的 bridge 提供了类似 build_full_prompt 的方法：
            if hasattr(preset_bridge, "build_full_prompt"):
                final_prompt = preset_bridge.build_full_prompt(req.preset, base_subject)
            else:
                # 如果没这个方法，退而求其次，直接使用预设名作为风格词
                final_prompt = f"{base_subject}, {req.preset} style"
                
            logger.info(f"🎨 预设 {req.preset} 解析完成，最终 Prompt: {final_prompt[:100]}...")
        except Exception as e:
            logger.error(f"❌ 预设解析失败: {e}")
            if not final_prompt:
                final_prompt = "masterpiece, best quality"

    # 如果依然为空，给个最终兜底
    if not final_prompt or final_prompt.strip() == "":
        final_prompt = "masterpiece, best quality, highly detailed"
            
    # 4. 组装请求
    image_req = ImageRequest(
        prompt=final_prompt,
        width=req.width,
        height=req.height,
        steps=req.steps
    )

    # 5. 执行推理（用线程池防止阻塞 FastAPI 事件循环）
    try:
        image = await run_in_threadpool(provider.text_to_image, image_req)
        
        # 6. 保存图片（建议保存到 output/api/ 目录，然后返回 URL）
        import os
        import time
        os.makedirs("output/api", exist_ok=True)
        filename = f"api_{int(time.time())}.png"
        filepath = os.path.join("output/api", filename)
        image.save(filepath)
        
        return {
            "status": "success",
            "message": "生成成功",
            "image_url": f"/output/api/{filename}",  # 前端拿到这个链接去展示
            "provider": provider.get_name()
        }
    except Exception as e:
        logger.error(f"❌ 生成失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/gallery")
def get_gallery():
    """获取已生成的图片列表"""
    gallery_dir = "output/api"
    if not os.path.exists(gallery_dir):
        return {"status": "success", "data": []}
    
    files = []
    for f in os.listdir(gallery_dir):
        if f.endswith((".png", ".jpg", ".jpeg")):
            path = os.path.join(gallery_dir, f)
            # 提取生成时间（根据文件名中的时间戳或文件修改时间）
            mtime = os.path.getmtime(path)
            files.append({
                "filename": f,
                "url": f"/output/api/{f}",
                "time": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
            })
            
    # 按时间倒序排
    files.sort(key=lambda x: x["time"], reverse=True)
    return {"status": "success", "data": files[:50]} # 返回最近 50 张


@app.post("/api/generate_video")
async def generate_video(req: VideoRequest):
    try:
        from skills.video_generator import VideoGenerator
        logger.info(f"🎬 收到视频请求: {req.topic}")
        gen = VideoGenerator()
        result = await run_in_threadpool(gen.generate, prompt=req.topic, duration=req.duration)
        
        video_path = result.get("video_path", "")
        if video_path and os.path.exists(video_path):
            import shutil
            filename = os.path.basename(video_path)
            dest = os.path.join("output/api", filename)
            shutil.copy(video_path, dest)
            return {"status": "success", "video_url": f"/output/api/{filename}"}
        return {"status": "error", "message": "未返回视频路径"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ================= 图生图接口 =================
@app.post("/api/image_to_image")
async def image_to_image(
    prompt: str = Form(""),
    provider: str = Form("local_sd"),
    image: UploadFile = File(...)
):
    try:
        # 1. 读取上传的图片
        contents = await image.read()
        init_img = Image.open(io.BytesIO(contents)).convert("RGB")
        
        # 2. 组装 Provider
        from providers.fallback import FallbackImageProvider
        primary = provider
        pool = [p for p in list_providers("image") if p != primary]
        
        configs = {p: ({"device": "CPU"} if p == "local_sd" else settings.get_provider_config(p)) for p in [primary] + pool}
        prov = FallbackImageProvider(primary=primary, fallback=pool, configs=configs)
        
        # 3. 构建图生图请求
        req = ImageRequest(
            prompt=prompt if prompt else "masterpiece, high quality",
            reference=init_img,
            strength=0.7,
            width=768, height=768, steps=25
        )
        
        # 4. 执行
        result_img = await run_in_threadpool(prov.image_to_image, req)
        
        # 5. 保存
        filename = f"img2img_{int(time.time())}.png"
        filepath = os.path.join("output/api", filename)
        result_img.save(filepath)
        
        return {"status": "success", "image_url": f"/output/api/{filename}", "provider": prov.get_name()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ================= 通用技能执行接口 =================
class SkillRequest(BaseModel):
    skill_name: str
    kwargs: dict = {}

@app.post("/api/run_skill")
async def run_skill(req: SkillRequest):
    """运行指定的 Skill（支持 skills.registry 里的全部 18 个）。

    请求体：{"skill_name": "xxx", "kwargs": {...}}
    """
    skill_name = req.skill_name
    req_kwargs = req.kwargs or {}

    try:
        from skills.registry import get_meta, import_skill_class

        meta = get_meta(skill_name)

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
        # 1. 合并默认参数（kwargs_builder）+ 用户传入
        merged = dict(req_kwargs)
        if meta.kwargs_builder:
            try:
                defaults = meta.kwargs_builder({"prompt": "", "original_text": ""}) or {}
                merged = {**defaults, **merged}
                logger.info(f"skill={skill_name} kwargs: defaults={defaults} user={req_kwargs} merged={merged}")
            except Exception as e:
                logger.warning(f"kwargs_builder 失败 (skill={skill_name}): {e}")

        # 2. 动态导入 + 构造
        skill_cls = import_skill_class(meta)
        config = {
            "output_dir": str(settings.output_dir),
            "log_level": "INFO",
        }
        skill = skill_cls(config)

        # 3. 执行
        result = await run_in_threadpool(skill.execute, **merged)

        # 4. 统一返回形态
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
        
# ================= 静态文件挂载 =================

# 1. 确保目录存在
os.makedirs("output/api", exist_ok=True)
os.makedirs("static", exist_ok=True)

# 2. 挂载生成的图片目录（供前端读取）
app.mount("/output", StaticFiles(directory="output"), name="output")

# 3. 挂载 PWA 所需的静态文件（manifest.json, sw.js, 图标）
app.mount("/static", StaticFiles(directory="static"), name="static_files")



# ============================================================
# Skills 列表（P5 新增）
# ============================================================

@app.get("/api/skills")
def get_skills():
    """列出所有已注册的 skill（来自 skills.registry，共 18 个）。

    返回形态：
      {status: "success", count: N, data: [{name, source, keywords, ...}]}
    """
    from skills.registry import list_skills, get_meta

    result = []
    for name in list_skills():
        m = get_meta(name)
        if not m:
            continue
        result.append({
            "name": m.name,
            "source": m.source,                # meta / routes / both
            "keywords": list(m.keywords),
            "system_hint": m.system_hint,
            "category": m.category,
            "outputs": list(m.outputs),
            "class_path": m.class_path,
        })

    return {"status": "success", "count": len(result), "data": result}



# 4. 挂载前端首页（注意：必须放在所有 /api/ 和 /static/ 路由之后）
# 这样当用户访问根路径 / 时，自动返回 static/index.html
@app.get("/")
async def read_index():
    from fastapi.responses import FileResponse
    return FileResponse("static/index.html")

# 5. （可选）兼容未匹配到路由的 404 情况，或者 SPA 路由
@app.get("/{full_path:path}")
async def catch_all(full_path: str):
    from fastapi.responses import FileResponse
    import os
    base = os.path.abspath("static")
    target = os.path.abspath(os.path.join(base, full_path))
    if not target.startswith(base):
        return FileResponse("static/index.html")   # 拒绝越界
    if os.path.isfile(target):
        return FileResponse(target)
    return FileResponse("static/index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)