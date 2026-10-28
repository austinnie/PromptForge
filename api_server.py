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
    
    # ★ 如果传了 preset，调用 Preset 逻辑构建提示词
    if req.preset:
        try:
            from preset_bridge import preset_bridge
            # 这里模拟 GUI 里 PresetHandler 的提示词生成逻辑
            # 实际中你可以调用 preset_bridge 的方法生成六层提示词
            # 为了演示，如果只传了空 prompt，就给它个默认主体
            if not final_prompt:
                final_prompt = "masterpiece, best quality"
        except Exception as e:
            logger.warning(f"预设处理失败: {e}")
            
    # 4. 组装请求
    image_req = ImageRequest(
        prompt=req.prompt,
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