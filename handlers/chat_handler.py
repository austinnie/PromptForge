# handlers/chat_handler.py
"""对话处理器 - 普通对话和简单问答"""

from typing import Dict, Any
from .base import BaseHandler


class ChatHandler(BaseHandler):
    """对话处理器"""
    
    def __init__(self, app):
        super().__init__(app)
        self._quick_responses = {
            "你好": "你好！有什么可以帮你的吗？",
            "你是谁": "我是智能生图助手，可以帮助你生成图片。试试说「生成一张...」！",
            "功能": "我可以：\n• 📝 文生图 - 输入描述生成图片\n• 💬 自由对话 - 回答你的问题\n• 🧠 LLM增强 - 更智能的理解",
            "帮助": "💡 使用提示：\n• 说「生成一张...」来生成图片\n• 直接聊天也可以\n• 说「清除上下文」重置对话",
            "谢谢": "不客气！还有需要帮忙的吗？",
            "再见": "再见！随时回来找我生成图片 😊",
        }
    
    def handle(self, intent: Dict[str, Any]) -> None:
        """处理对话"""
        text = intent.get("original_text", "")
        text_lower = text.lower()
        
        # 1. 检查上下文查询
        if '上下文' in text_lower or 'context' in text_lower:
            self._show_context()
            return
        
        # 2. 检查偏好查询
        if '偏好' in text_lower or 'preference' in text_lower:
            self._show_preferences()
            return
        
        # 3. 检查清除上下文
        if any(k in text_lower for k in ['清除上下文', '清除历史', '重置', 'clear']):
            self.context.clear()
            self._reply("🗑️ 对话上下文已清除")
            return
        
        # 4. 快速回复
        for key, value in self._quick_responses.items():
            if key in text_lower:
                self._reply(value)
                return
        
        # 5. 使用LLM
        if self.llm and self.app.settings.llm_enabled and self.llm.is_available():
            self._reply_with_llm(text)
            return
        
        # 6. 默认回复
        self._reply(
            f"🤔 我理解你想说：\"{text}\"\n\n"
            f"如果你想生成图片，可以试试说：\n"
            f"• 「生成一张日落风景」\n"
            f"• 「画一个美丽的女孩」\n"
            f"• 「帮我生成赛博朋克城市」\n\n"
            f"或者直接告诉我你的需求！"
        )
    
    def _show_context(self):
        """显示上下文摘要"""
        summary = self.context.get_summary()
        if summary:
            self._reply(f"📊 当前上下文:\n{summary}")
        else:
            self._reply("📊 暂无上下文信息")
    
    def _show_preferences(self):
        """显示用户偏好"""
        prefs = self.context.preferences
        pref_list = []
        
        if prefs.get("style"):
            pref_list.append(f"风格: {prefs['style']}")
        if prefs.get("scene"):
            pref_list.append(f"场景: {prefs['scene']}")
        if prefs.get("gender"):
            pref_list.append(f"性别: {prefs['gender']}")
        
        if pref_list:
            self._reply("📌 你的偏好:\n• " + "\n• ".join(pref_list))
        else:
            self._reply("📌 还没有记录你的偏好。生成图片时我会自动学习！")
    
    def _reply_with_llm(self, text: str):
        """使用LLM回复"""
        self._update_status("🧠 思考中...")
        
        # 构建上下文
        context = self.context.get_summary()
        context_prompt = f"\n对话上下文：\n{context}\n" if context else ""
        
        prompt = f"""你是一个友好的AI助手，专门帮助用户生成AI图片。请简短、友好地回复用户。

{context_prompt}
用户说：{text}

请用中文回复，保持简短（1-2句话），如果用户有生成图片的意图，引导他们说出具体描述。"""
        
        result = self.llm.generate(prompt, timeout=15, max_tokens=150)
        
        if result:
            self._reply(result)
            self._update_status("✅ 回复完成")
        else:
            self._reply(
                f"💡 你想说：\"{text}\"\n\n"
                f"试试说「生成一张...」来开始创作！"
            )
            self._update_status("就绪")