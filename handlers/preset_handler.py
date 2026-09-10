# handlers/preset_handler.py
"""预设风格处理器 - 使用 LayerForge 的 6 层提示词"""

import re
from typing import Dict, Any
from .base import BaseHandler
from core.safety import SafetyChecker


class PresetHandler(BaseHandler):
    """预设处理器：调用 LayerForge 生成提示词，复用文生图逻辑出图"""

    # ==================== 中→英 词典兜底 ====================
    # 只覆盖高频词，命中即可，不追求完整
    ZH_EN_DICT = {
        # 主题
        "赛博朋克": "cyberpunk",
        "蒸汽朋克": "steampunk",
        "机甲": "mecha",
        "机器人": "robot",
        "战士": "warrior",
        "武士": "samurai",
        "骑士": "knight",
        "魔法师": "wizard",
        "侦探": "detective",
        "少女": "girl",
        "女孩": "girl",
        "男孩": "boy",
        "女人": "woman",
        "男人": "man",
        "猫": "cat",
        "猫咪": "cat",
        "狗": "dog",
        "小狗": "puppy",
        "龙": "dragon",
        "老虎": "tiger",
        "狮子": "lion",
        "马": "horse",
        "鸟": "bird",
        "鹤": "crane",
        "凤凰": "phoenix",
        "狐狸": "fox",
        "狼": "wolf",
        "鹿": "deer",
        # 场景
        "城市": "city",
        "都市": "city",
        "街道": "street",
        "森林": "forest",
        "海洋": "ocean",
        "大海": "ocean",
        "海滩": "beach",
        "沙滩": "beach",
        "沙漠": "desert",
        "雪山": "snow mountain",
        "星空": "starry sky",
        "夜空": "night sky",
        "日落": "sunset",
        "日出": "sunrise",
        "黄昏": "dusk",
        "风景": "landscape",
        "花园": "garden",
        "竹林": "bamboo forest",
        "山": "mountain",
        "河流": "river",
        "湖泊": "lake",
        # 修饰
        "一个": "",
        "一只": "",
        "一张": "",
        "一位": "",
        "的": " ",
        "可爱": "cute",
        "美丽": "beautiful",
        "帅气": "handsome",
        "梦幻": "dreamy",
        "复古": "vintage",
        "未来": "futuristic",
        "极简": "minimalist",
        "夜景": "night view",
        "黎明": "dawn",
        "清晨": "morning",
        "正午": "noon",
        "傍晚": "evening",
        "雨天": "rainy day",
        "雪景": "snowy scene",
        "废墟": "ruins",
        "未来都市": "futuristic city",
        "霓虹灯": "neon lights",        
    }

    def handle(self, intent: Dict[str, Any]) -> None:
        from preset_bridge import preset_bridge
        from presets_meta import get_display_name

        if not preset_bridge.is_ready():
            self._reply("❌ 预设系统未就绪")
            return

        original = intent.get("original_text", "")
        preset_name = intent.get("params", {}).get("preset")
        mode = intent.get("params", {}).get("mode", "random")  # random / first
        count = intent.get("params", {}).get("count", 1)

        if not preset_name:
            # 没指定预设 → 显示分类列表
            from presets_meta import get_presets_by_category
            self._reply("🎨 请选择一个预设（按分类）：")
            for cat, plist in get_presets_by_category().items():
                self._reply(f"\n【{cat}】")
                for p in plist[:8]:
                    self._reply(f"   {get_display_name(p)}")
                if len(plist) > 8:
                    self._reply(f"   ... 共 {len(plist)} 个")
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

        subject_cn = self._extract_subject(original)
        subject_en = self._translate_subject(subject_cn) if subject_cn else None

        if subject_cn and subject_en and subject_cn != subject_en:
            self._reply(f"🌐 主体: {subject_cn} → {subject_en}")

        # ✅ 生成 count 张
        for i in range(count):
            prompt, detail = preset_bridge.build_prompt(
                preset=preset_name,
                mode=mode,
                subject_override=subject_en,
                max_tokens=77,
                return_detail=True,
            )

            if count > 1:
                self._reply(f"\n--- 第 {i+1}/{count} 张 ---")

            self._reply(f"🎨 预设: {get_display_name(preset_name)}")
            self._reply(f"📝 提示词: {prompt[:100]}...")

            # ✅ 显示 6 层详情
            self._reply("📋 6 层组合:")
            labels = {
                "subject": "主体", "scene": "场景", "style": "风格",
                "lighting": "光影", "view": "视角", "quality": "画质",
            }
            for key, val in detail.items():
                self._reply(f"   {labels.get(key, key)}: {val[:60]}")

            # 出图
            from handlers.text_to_image import TextToImageHandler
            t2i = TextToImageHandler(self.app)
            t2i.handle({
                "type": "text_to_image",
                "prompt": prompt,
                "original_text": original,
            })


            # ✅ 加在这里：记住本次预设 + 6 层组合，供后续"换成猫"用
            if self.context:
                self.context.last_preset_name = preset_name
                self.context.last_preset_detail = detail
                self.context.last_preset_subject = subject_en
                
    # ==================== 主体抽取 ====================

    def _extract_subject(self, text: str) -> str:
        """从'用机甲风格画一个赛博朋克少女'里抽出'赛博朋克少女'"""
        patterns = [
            r'用.{0,10}风格(?:画|生成|做|绘制)(?:一个|一只|一张|一位)?(.+)',
            r'(?:画|生成|做|绘制)(?:一个|一只|一张|一位)?(.+)',
            r'预设[：: ]*(\S+)',
        ]
        for p in patterns:
            m = re.search(p, text)
            if m:
                subject = m.group(1).strip().strip('，。,.!?！？')
                # 去掉尾部可能残留的"图片/图像/照片"等词
                subject = re.sub(r'(图片|图像|照片|图像|一张图)$', '', subject).strip()
                if subject:
                    return subject
        return None

    # ==================== 三级翻译 ====================

    def _translate_subject(self, subject: str) -> str:
        """把中文主体翻成英文（三级降级）"""
        if not subject:
            return subject

        # 已经全英文，直接返回
        if not any('\u4e00' <= c <= '\u9fff' for c in subject):
            return subject

        # 一级：Ollama
        result = self._translate_with_ollama(subject)
        if result:
            return result

        # 二级：词典
        result = self._translate_with_dict(subject)
        if result and result != subject:
            return result

        # 三级：原样返回
        return subject

    def _translate_with_ollama(self, subject: str) -> str:
        """用 Ollama 翻译（不可用则返回 None）"""
        try:
            import requests
            from config.settings import settings

            # 先探活
            try:
                r = requests.get(f"{settings.ollama_url}/api/tags", timeout=3)
                if r.status_code != 200:
                    return None
            except Exception:
                return None

            resp = requests.post(
                f"{settings.ollama_url}/api/generate",
                json={
                    "model": settings.ollama_model,
                    "prompt": (
                        "Translate the following Chinese phrase into concise English "
                        "for use in a Stable Diffusion prompt. "
                        "Output ONLY the English translation, no quotes, no explanation, "
                        "no period at the end.\n\n"
                        f"Chinese: {subject}\nEnglish:"
                    ),
                    "stream": False,
                    "options": {"temperature": 0.2, "num_predict": 60},
                },
                timeout=20,
            )
            if resp.status_code != 200:
                return None

            text = resp.json().get("response", "").strip()
            # 清理：引号、前缀、换行
            text = text.splitlines()[0].strip() if text else ""
            text = text.strip('"\'').strip()
            text = re.sub(r'^(English|Translation)[：:]\s*', '', text, flags=re.IGNORECASE)
            text = text.rstrip('.,;:')

            # 必须包含英文字母，且不能太长（防止 LLM 胡说）
            if not text:
                return None
            if not re.search(r'[a-zA-Z]', text):
                return None
            if len(text) > 80:
                return None

            return text
        except Exception as e:
            print(f"⚠️ Ollama 翻译失败: {e}")
            return None

    def _translate_with_dict(self, subject: str) -> str:
        """用内置词典翻译（按最长匹配优先，词间补空格）"""
        keys = sorted(self.ZH_EN_DICT.keys(), key=len, reverse=True)

        result = subject
        for cn in keys:
            if cn in result:
                en = self.ZH_EN_DICT[cn]
                # ✅ 关键：英文替换前后补空格，防止粘连
                if en:
                    result = result.replace(cn, f" {en} ")
                else:
                    result = result.replace(cn, " ")

        # ✅ 清理多余空格和标点
        result = re.sub(r'\s+', ' ', result)
        result = re.sub(r'\s+([,.])', r'\1', result)
        result = result.strip(' ,，。.')

        return result
    
