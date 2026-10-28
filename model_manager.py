# model_manager.py
"""本地模型管理器：扫描目录，生成模型清单，供 Provider 调用"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

MANIFEST_FILE = Path(__file__).parent / "models_manifest.json"
DEFAULT_MODEL_DIR = os.environ.get("SD_MODEL_DIR", "E:/SD_OpenVINO/models")


def scan_models(force_refresh: bool = False) -> Dict[str, Any]:
    """扫描模型目录，生成模型清单"""
    if MANIFEST_FILE.exists() and not force_refresh:
        try:
            return json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass  # 解析失败则重新扫描

    print(f"🔍 正在扫描模型目录: {DEFAULT_MODEL_DIR}")
    models_dir = Path(DEFAULT_MODEL_DIR)
    manifest = {"checkpoints": {}, "lora": {}, "vae": {}, "controlnet": {}}

    if not models_dir.exists():
        print("⚠️ 模型目录不存在，生成空清单")
        MANIFEST_FILE.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return manifest

    # 1. 扫描大模型 Checkpoints
    # 根目录下 sd-v1-5, sdxl, sd-v1-5-ov-int8 文件夹
    for folder in ["sd-v1-5", "sdxl", "sd-v1-5-ov-int8"]:
        p = models_dir / folder
        if not p.exists(): continue
        
        # OpenVINO 模型是文件夹
        if folder == "sd-v1-5-ov-int8":
            manifest["checkpoints"]["ov_int8_sd15"] = {
                "id": "ov_int8_sd15",
                "name": "OpenVINO 加速版 SD1.5",
                "path": str(p),
                "type": "openvino",
                "base": "sd15"
            }
            continue
            
        # 其他是 safetensors 文件
        for f in p.rglob("*.safetensors"):
            model_id = f"{folder}_{f.stem}".replace("-", "_").lower()
            base_type = "sdxl" if "sdxl" in folder.lower() or "xl" in f.stem.lower() else "sd15"
            
            # 简单美化显示名
            display_name = f.stem.replace("_", " ").title()
            if "realistic" in display_name.lower():
                display_name += " (写实)"
            elif "anime" in display_name.lower():
                display_name += " (二次元)"
                
            manifest["checkpoints"][model_id] = {
                "id": model_id,
                "name": display_name,  # ★ 使用美化后的名字
                "path": str(f),
                "type": "diffusers",
                "base": base_type
            }

    # 2. 扫描 LoRA (简略扫描，供以后使用)
    lora_dir = models_dir / "sd15-lora"
    if lora_dir.exists():
        for f in lora_dir.glob("*.safetensors"):
            manifest["lora"][f.stem] = {"name": f.stem, "path": str(f)}

    # 保存清单
    MANIFEST_FILE.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✅ 扫描完成，共找到 {len(manifest['checkpoints'])} 个大模型。清单已保存至 {MANIFEST_FILE.name}")
    return manifest


def get_checkpoint(model_id: str) -> dict:
    """获取指定 ID 的模型信息"""
    data = scan_models()
    return data["checkpoints"].get(model_id)


def list_checkpoints() -> List[dict]:
    """列出所有大模型，供 GUI 使用"""
    data = scan_models()
    return list(data["checkpoints"].values())