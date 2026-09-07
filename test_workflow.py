# test_workflow.py
from config.settings import settings
from multimedia.workflow import MultimediaWorkflow

# 模拟 app 对象（提供 _append_message 等方法）
class DummyApp:
    def _append_message(self, role, content):
        print(f"[{role}] {content}")
    def _update_status(self, msg):
        print(f"[status] {msg}")
    settings = settings

app = DummyApp()
wf = MultimediaWorkflow(app)

# 执行全自动创作
result = wf.execute("月光下的森林", duration=10)
print("最终视频:", result['final_video'])