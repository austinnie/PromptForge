# test_dual_path.py
import logging
from providers.fallback import FallbackImageProvider
from providers.base import ImageRequest
from config.settings import settings
from model_manager import list_checkpoints, scan_models

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_dual_path():
    print("🚀 开始测试 本地/API 双路生成...")
    
    # 1. 强制刷新一次模型清单，确保是最新的
    scan_models(force_refresh=True)
    models = list_checkpoints()
    if not models:
        print("⚠️ 没有找到任何本地模型，将直接测试 API 路径。")
        target_model = None
    else:
        target_model = models[0]["id"]
        print(f"📦 选用本地模型: {target_model} ({models[0]['name']})")

    # 2. 获取所有支持的图像 Provider
    from providers import list_providers
    all_image_providers = list_providers("image")
    print(f"📋 当前注册的 Provider: {all_image_providers}")
    
    # 3. 组装配置（这里统一处理，不要被覆盖）
    primary = "local_sd" if target_model else "agnes"
    pool = [p for p in all_image_providers if p != primary]
    
    configs = {}
    for p in [primary] + pool:
        if p == "local_sd":
            # 强制注入我们选好的本地模型 ID
            configs[p] = {
                "device": "CPU",
                "model_id": target_model,
                "engine_type": "auto"
            }
        else:
            configs[p] = settings.get_provider_config(p)

    # 4. 构建降级链
    provider = FallbackImageProvider(
        primary=primary,
        fallback=pool,
        configs=configs,
        on_fallback=lambda frm, to, err: print(f"⚠️ 降级触发: {frm} 失败 ({str(err)[:50]}), 切换到 {to}")
    )

    # 5. 发起生成请求
    req = ImageRequest(
        prompt="a cute cat sitting on a windowsill, sunny day, masterpiece",
        width=512,
        height=512,
        steps=20
    )
    
    try:
        print(f"\n🎨 正在使用 {primary} 生成图片...")
        if primary == "local_sd":
            print("⏳ 提示: 加载本地大模型可能需要 1~3 分钟，请耐心等待...")
            
        
        img = provider.text_to_image(req)
        img.save("test_output.png")
        print(f"✅ 成功！图片已保存至 test_output.png (尺寸: {img.size})")
    except Exception as e:
        print(f"\n❌ 全部路径均失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_dual_path()