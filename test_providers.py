# test_providers.py
from providers.fallback import FallbackImageProvider
from providers.base import ImageRequest
import logging

logging.basicConfig(level=logging.INFO)

# 1. 配置：优先用本地，本地失败用 Agnes 兜底
configs = {
    "local_sd": {"device": "CPU", "model_path": "你本地的某个模型路径"}, 
    "agnes": {"api_key": "你的agnes_key"}
}

provider = FallbackImageProvider(
    primary="local_sd",
    fallback=["agnes"],
    configs=configs
)

req = ImageRequest(prompt="a beautiful sunset over the mountains", width=512, height=512)

print("开始生成图片...")
try:
    img = provider.text_to_image(req)
    print(f"生成成功！尺寸: {img.size}")
except Exception as e:
    print(f"生成彻底失败: {e}")