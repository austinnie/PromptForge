# handlers/multimedia_handler.py
from .base import BaseHandler
from multimedia.workflow import MultimediaWorkflow

class MultimediaHandler(BaseHandler):
    def handle(self, intent: Dict[str, Any]) -> None:
        theme = intent.get("prompt") or intent.get("original_text", "")
        if not theme:
            self._reply("❌ 请提供创作主题")
            return

        self._reply("🎬 开始全自动创作，请耐心等待...")
        self._update_status("🎬 创作中...")
        try:
            workflow = MultimediaWorkflow(self.app)
            result = workflow.execute(theme)
            if result["status"] == "success":
                self._reply(f"✅ 创作完成！视频已保存至：{result['final_video']}")
                self._reply(f"📊 包含 {len(result['video_segments'])} 个片段，音乐与旁白已合成")
                self._update_status("✅ 创作完成")
                # 可添加打开文件夹功能
            else:
                self._reply(f"❌ 创作失败：{result.get('error', '未知错误')}")
                self._update_status("❌ 创作失败")
        except Exception as e:
            self._reply(f"❌ 创作异常：{str(e)}")
            self._update_status("❌ 异常")
            import traceback
            traceback.print_exc()