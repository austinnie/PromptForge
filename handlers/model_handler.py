# handlers/model_handler.py
import logging
from typing import Dict, Any
from providers.registry import clear_cache
from model_manager import list_checkpoints

logger = logging.getLogger(__name__)

class ModelHandler:
    """处理本地模型切换、列出模型（作为标准 Skill 被 SkillHandler 调用）"""

    def __init__(self, config: dict = None):
        self.config = config or {}
        # 如果 SkillHandler 没有传 app，这里留空
        self.app = self.config.get("app") 

    def execute(self, action: str = "list", model_id: str = None) -> dict:
        """统一入口"""
        try:
            if action == "list":
                return self._list_models()
            elif action == "switch":
                return self._switch_model(model_id)
            else:
                return {"status": "error", "error": "未识别的模型管理操作"}
        except Exception as e:
            logger.error(f"ModelHandler 执行失败: {e}")
            return {"status": "error", "error": str(e)}

    def _list_models(self) -> dict:
        models = list_checkpoints()
        if not models:
            return {"status": "error", "error": "⚠️ 当前没有可用的本地模型。"}

        lines = ["📦 当前可用的本地模型："]
        for m in models:
            lines.append(f"- `{m['id']}` ({m['name']})")
        lines.append("\n💡 回复“切换模型 [ID]”即可切换。")
        
        return {"status": "success", "message": "\n".join(lines)}

    def _switch_model(self, model_id: str) -> dict:
        if not model_id:
            return {"status": "error", "error": "❌ 请提供要切换的模型 ID。"}

        models = list_checkpoints()
        if not any(m["id"] == model_id for m in models):
            return {"status": "error", "error": f"❌ 未找到模型: {model_id}"}

        # 1. 更新配置
        from config.settings import settings
        if hasattr(settings, "set_local_model_id"):
            settings.set_local_model_id(model_id)
        else:
            settings.default_local_model_id = model_id
            
        # 2. 清空缓存
        clear_cache()
        
        return {"status": "success", "message": f"✅ 已成功切换本地模型至: {model_id}\n(首次生成时会重新加载模型，请稍候)"}