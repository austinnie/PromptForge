# handlers/preset_handler.py
"""预设风格处理器 - 使用 LayerForge 的 6 层提示词"""

from typing import Dict, Any
from .base import BaseHandler
from core.safety import SafetyChecker


class PresetHandler(BaseHandler):
    """预设处理器：调用 LayerForge 生成提示词，复用文生图逻辑出图"""

    def handle(self, intent: Dict[str, Any]) -> None:
        from preset_bridge import preset_bridge

        if not preset_bridge.is_ready():
            self._reply("❌ 预设系统未就绪，请检查 LayerForge 路径")
            return

        original = intent.get("original_text", "")
        preset_name = intent.get("params", {}).get("preset")

        # 没匹配到预设 → 让用户选
        if not preset_name:
            presets = preset_bridge.list_presets()[:20]
            self._reply("🎨 请指定预设名，例如：")
            for p in presets:
                self._reply(f"   - {p}")
            return

        # 安全检测
        if self.app.settings.safe_mode:
            is_unsafe, _ = SafetyChecker.check(original)
            if is_unsafe:
                cleaned = SafetyChecker.sanitize(original)
                if not cleaned:
                    self._reply("🛡️ 内容被安全过滤")
                    return
                original = cleaned

        # 提取用户主体（去掉"用xx风格画"这类引导词）
        subject = self._extract_subject(original)

        # ✅ 核心：调 LayerForge 生成 6 层提示词
        prompt = preset_bridge.build_prompt(
            preset=preset_name,
            subject_override=subject,
            max_tokens=77,
        )

        self._reply(f"🎨 预设: {preset_name}")
        self._reply(f"📝 提示词: {prompt[:120]}...")

        if "视频" in original or "video" in original.lower():
            from handlers.video_handler import VideoHandler
            vh = VideoHandler(self.app)
            vh.handle({
                "type": "video",
                "prompt": prompt,          # ← 6 层提示词直接给视频用
                "original_text": original,
            })
            return
    
    
        # ✅ 复用现有文生图逻辑（把 prompt 塞回 intent）
        from handlers.text_to_image import TextToImageHandler
        t2i = TextToImageHandler(self.app)
        t2i.handle({
            "type": "text_to_image",
            "prompt": prompt,
            "original_text": original,
        })

    def _extract_subject(self, text: str) -> str:
        """从'用机甲风格画一个赛博朋克少女'里抽出'赛博朋克少女'"""
        import re
        patterns = [
            r'用.{0,10}风格(?:画|生成|做)(.+)',
            r'(?:画|生成|做)(?:一个|一张)?(.+)',
            r'预设[：: ]*(\S+)',
        ]
        for p in patterns:
            m = re.search(p, text)
            if m:
                return m.group(1).strip().strip('，。,.')
        return None