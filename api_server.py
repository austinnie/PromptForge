# api_server.py
"""
PromptForge 多端 API 服务端
通过 FastAPI 暴露核心能力，供手机端、Web 端或小程序调用。
"""

import logging
from typing import Optional
from fastapi import FastAPI, HTTPException
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

# 初始化意图分析器
analyzer = IntentAnalyzer()


class ChatLLMRequest(BaseModel):
    text: str
    system_prompt: str = "You are a helpful assistant."
    model: str = "qwen2.5:7b"   # ★ 新增：允许前端指定模型


class ActionRequest(BaseModel):
    action: str
    payload: dict = {}
    
# ==================== 请求模型定义 ====================

class ChatRequest(BaseModel):
    text: str
    has_image: bool = False

class GenerateImageRequest(BaseModel):
    prompt: str
    width: int = 1024
    height: int = 1024
    steps: int = 25
    primary_provider: Optional[str] = None  # 可以指定优先用本地还是云端
    # ★ 新增：允许前端指定本地模型 ID
    model_id: Optional[str] = None
    preset: Optional[str] = None
    
    
# ==================== API 路由 ====================

@app.post("/api/skill/image_curator")
async def run_image_curator(req: ActionRequest):
    """图片鉴赏任务"""
    try:
        from skills.image_curator import ImageCurator
        # 假设你传了目录路径
        folder = req.payload.get("folder", "output")
        curator = ImageCurator({})
        # 防止阻塞
        result = await run_in_threadpool(curator.curate, folder, "鉴赏报告")
        return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/skill/video_generator")
async def run_video_generator(req: ActionRequest):
    """视频生成任务"""
    try:
        from skills.video_generator import VideoGenerator
        topic = req.payload.get("topic", "默认主题")
        gen = VideoGenerator()
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

# （可选）挂载静态文件目录，让前端可以直接访问生成的图片
from fastapi.staticfiles import StaticFiles
import os
os.makedirs("output/api", exist_ok=True)
app.mount("/output", StaticFiles(directory="output"), name="output")

# ★ 新增：挂载前端页面目录
os.makedirs("static", exist_ok=True)
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    # 0.0.0.0 允许局域网内的手机访问
    uvicorn.run(app, host="0.0.0.0", port=8000)