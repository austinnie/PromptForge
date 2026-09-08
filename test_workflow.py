# test_workflow.py
from config.settings import settings
from multimedia.workflow import MultimediaWorkflow

# 模拟 app 对象（提供 _append_message 等方法）
class DummyApp:
    def __init__(self):
        self.settings = settings
        self.status_var = None  # 添加
    def _append_message(self, role, content):
        print(f"[{role}] {content}")
    def _update_status(self, msg):
        # 基类会调用 status_var.set，所以无需重复定义
        pass
    settings = settings

app = DummyApp()
wf = MultimediaWorkflow(app)

# 执行全自动创作
result = wf.execute("月光下的森林")
print("最终视频:", result['final_video'])