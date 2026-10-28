# providers/_impl/__init__.py
"""Provider 引擎实现层。

⚠️ 迁移状态（决策 A：逐步迁移，下个大版本删除 api_engines/）

已迁移（providers/adapters/ 有对应 adapter，可直接用）：
  - agnes        → providers/_impl/agnes.py       ← 从 api_engines/agnes.py 搬来
  - pollinations → providers/_impl/pollinations.py ← 从 api_engines/pollinations.py 搬来

待迁移（目前仍在 api_engines/，无 adapter，无法被 list_providers() 看到）：
  - tongyi / yige / hunyuan / huggingface / replicate / stability /
    freeapi / freellmapi / free_multimodal_proxy / openrouter / siliconflow

迁移步骤（每个 provider 一轮）：
  1. 把 api_engines/{name}.py 复制到 providers/_impl/{name}.py
  2. 在 providers/adapters/{name}.py 写 adapter（参考 agnes.py）
  3. 跑 smoke test 验证 list_providers("image") 能列出
  4. 从 api_engines/ 删除源文件

下个大版本（2.0）：
  - 全部迁移完成后，直接删除 api_engines/ 目录
  - 修改 gather_code.py 的 EXCLUDE_TOP_DIRS 无需处理（本来就不扫）
"""