# gui/app.py
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import os
import re
from PIL import Image, ImageTk

from config.settings import settings
from core.intent_analyzer import IntentAnalyzer
from core.context_manager import ContextManager
from services.llm_service import LLMService
from handlers import TextToImageHandler, ImageToImageHandler, CoupleHandler,ChatHandler, VideoHandler


class ChatApp:
    """智能生图主应用"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("💬 智能生图")
        self.root.geometry("850x650")
        
        self.settings = settings
        self.intent_analyzer = IntentAnalyzer()
        self.context = ContextManager()
        self.llm = LLMService()
        
        # 模型状态
        self.is_model_loaded = False
        self.pipe = None
        
        # API 引擎缓存
        self._api_engine = None
        
        # 图片上传状态
        self.uploaded_images = []
        self.uploaded_image = None
        
        # ---------- 新增：图片显示相关 ----------
        self.image_refs = []          # 保存 PhotoImage 引用，防止被GC
        self._bound_double_click = False  # 标记是否已绑定双击事件
        
        self._setup_ui()
        self._check_llm()
    
    def _setup_ui(self):
        """设置UI"""
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self._build_toolbar(main_frame)
        self._build_chat_area(main_frame)
        self._build_input_area(main_frame)
        self._build_status_bar()
    
    # ============================================================
    # 工具栏
    # ============================================================
    def _build_toolbar(self, parent):
        """构建工具栏 - 分两行布局"""
        # ============================================================
        # 第一行：模型 + 图片 + 模式
        # ============================================================
        toolbar_row1 = ttk.Frame(parent)
        toolbar_row1.pack(fill=tk.X, pady=2)
        
        # --- 模型组 ---
        self.model_status = ttk.Label(toolbar_row1, text="🔴 未加载", foreground="red")
        self.model_status.pack(side=tk.LEFT, padx=5)
        
        self.select_model_btn = ttk.Button(
            toolbar_row1,
            text="📂 选择模型",
            command=self._select_model_file
        )
        self.select_model_btn.pack(side=tk.LEFT, padx=2)
        
        self.load_btn = ttk.Button(toolbar_row1, text="📦 加载模型", command=self._load_model)
        self.load_btn.pack(side=tk.LEFT, padx=2)
        
        ttk.Separator(toolbar_row1, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
        
        # --- 图片组 ---
        self.upload_btn = ttk.Button(
            toolbar_row1,
            text="📎 上传图片",
            command=self._upload_image
        )
        self.upload_btn.pack(side=tk.LEFT, padx=2)
        
        self.clear_upload_btn = ttk.Button(
            toolbar_row1,
            text="🗑️ 清除图片",
            command=self._clear_upload
        )
        self.clear_upload_btn.pack(side=tk.LEFT, padx=2)
        
        self.upload_status = ttk.Label(toolbar_row1, text="", foreground="green")
        self.upload_status.pack(side=tk.LEFT, padx=5)
        
        ttk.Separator(toolbar_row1, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
        
        # --- 模式组 ---
        ttk.Label(toolbar_row1, text="模式:").pack(side=tk.LEFT, padx=2)
        
        self.mode_var = tk.StringVar(value=self.settings.generation_mode)
        self.mode_combo = ttk.Combobox(
            toolbar_row1,
            textvariable=self.mode_var,
            values=["local", "api"],
            width=8,
            state="readonly"
        )
        self.mode_combo.pack(side=tk.LEFT, padx=2)
        self.mode_combo.bind('<<ComboboxSelected>>', self._on_mode_changed)
        
        ttk.Label(toolbar_row1, text="API:").pack(side=tk.LEFT, padx=5)
        
        self.provider_var = tk.StringVar(value=self.settings.api_provider)
        self.provider_combo = ttk.Combobox(
            toolbar_row1,
            textvariable=self.provider_var,
            values=["pollinations", "huggingface", "tongyi", "yige", "hunyuan", "agnes", "freeapi", "replicate", "stability"],
            width=12,
            state="readonly"
        )
        self.provider_combo.pack(side=tk.LEFT, padx=2)
        self.provider_combo.bind('<<ComboboxSelected>>', self._on_provider_changed)
        
        self.mode_hint = ttk.Label(
            toolbar_row1,
            text="🖥️ 本地模式",
            foreground="blue",
            font=("", 8)
        )
        self.mode_hint.pack(side=tk.LEFT, padx=10)
        
        # ============================================================
        # 第二行：工具按钮
        # ============================================================
        toolbar_row2 = ttk.Frame(parent)
        toolbar_row2.pack(fill=tk.X, pady=2)
        
        # --- 左侧：LLM状态 ---
        self.llm_status = ttk.Label(toolbar_row2, text="●", foreground="gray")
        self.llm_status.pack(side=tk.LEFT, padx=5)
        
        ttk.Separator(toolbar_row2, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
        
        # --- 功能按钮组 ---
        # 创作工具组
        ttk.Label(toolbar_row2, text="🎬 创作:").pack(side=tk.LEFT, padx=2)
        
        ttk.Button(
            toolbar_row2,
            text="📄 技术文章",
            command=self._generate_tech_article
        ).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(
            toolbar_row2,
            text="📰 新闻简报",
            command=self._fetch_news
        ).pack(side=tk.LEFT, padx=2)
        
        ttk.Separator(toolbar_row2, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
        
        # 管理工具组
        ttk.Label(toolbar_row2, text="📁 管理:").pack(side=tk.LEFT, padx=2)
        
        ttk.Button(
            toolbar_row2,
            text="📁 输出目录",
            command=self._open_output
        ).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(
            toolbar_row2,
            text="🗑️ 清除对话",
            command=self._clear_chat
        ).pack(side=tk.LEFT, padx=2)
        
        # --- 右侧：状态信息 ---
        ttk.Separator(toolbar_row2, orient=tk.VERTICAL).pack(side=tk.RIGHT, fill=tk.Y, padx=8)
        self.status_label = ttk.Label(toolbar_row2, text="就绪", foreground="gray")
        self.status_label.pack(side=tk.RIGHT, padx=5)
        
        self._update_mode_ui()

    def _update_toolbar_status(self, text, color="gray"):
        """更新工具栏右侧状态"""
        try:
            self.status_label.config(text=text, foreground=color)
        except:
            pass
            
    # ============================================================
    # 模式切换
    # ============================================================
    def _on_mode_changed(self, event=None):
        mode = self.mode_var.get()
        self.settings.generation_mode = mode
        
        if mode == "api":
            self.mode_hint.config(
                text=f"☁️ API: {self.provider_var.get()}",
                foreground="green"
            )
            self.provider_combo.config(state="readonly")
            self._append_message("system", f"☁️ 切换到 API 模式 ({self.provider_var.get()})")
            
            provider = self.provider_var.get()
            config = self.settings.get_api_config().get(provider, {})
            no_key_providers = ["pollinations", "freeapi"]
            if provider in no_key_providers:
                self._append_message("system", f"✅ {provider} 无需 API Key，可直接使用")
                return
            
            has_token = False
            if provider == "huggingface":
                has_token = bool(config.get("HF_API_TOKEN"))
            elif provider == "tongyi":
                has_token = bool(config.get("TONGYI_API_KEY"))
            elif provider == "yige":
                has_token = bool(config.get("YIGE_API_KEY") and config.get("YIGE_SECRET_KEY"))
            elif provider == "hunyuan":
                has_token = bool(config.get("HUNYUAN_SECRET_ID") and config.get("HUNYUAN_SECRET_KEY"))
            elif provider == "agnes":
                has_token = bool(config.get("AGNES_API_KEY"))

            # ✅ 新增 Replicate
            elif provider == "replicate":
                has_token = bool(config.get("REPLICATE_API_TOKEN"))
            # ✅ 新增 Stability
            elif provider == "stability":
                has_token = bool(config.get("STABILITY_API_KEY"))
            
            
            if not has_token:
                self._append_message("system", f"⚠️ {provider} API 密钥未配置，请检查 .env 文件")
            else:
                self._append_message("system", f"✅ {provider} API 密钥已配置")
        else:
            self.mode_hint.config(text="🖥️ 本地模式", foreground="blue")
            self.provider_combo.config(state="disabled")
            self._append_message("system", "🖥️ 切换到本地模式")
            if not self.settings.get_model_path():
                self._append_message("system", "⚠️ 本地模型路径未配置，请选择模型文件")
    
    def _on_provider_changed(self, event=None):
        provider = self.provider_var.get()
        self.settings.api_provider = provider
        self._api_engine = None
        
        if self.settings.generation_mode == "api":
            self.mode_hint.config(text=f"☁️ API: {provider}", foreground="green")
            self._append_message("system", f"☁️ 切换到 {provider} API")
            
            config = self.settings.get_api_config().get(provider, {})
            no_key_providers = ["pollinations", "freeapi"]
            if provider in no_key_providers:
                self._append_message("system", f"✅ {provider} 无需 API Key，可直接使用")
                return
            
            has_token = False
            if provider == "huggingface":
                has_token = bool(config.get("HF_API_TOKEN"))
            elif provider == "tongyi":
                has_token = bool(config.get("TONGYI_API_KEY"))
            elif provider == "yige":
                has_token = bool(config.get("YIGE_API_KEY") and config.get("YIGE_SECRET_KEY"))
            elif provider == "hunyuan":
                has_token = bool(config.get("HUNYUAN_SECRET_ID") and config.get("HUNYUAN_SECRET_KEY"))
            elif provider == "agnes":
                has_token = bool(config.get("AGNES_API_KEY"))
            
            if not has_token:
                self._append_message("system", f"⚠️ {provider} API 密钥未配置，请检查 .env 文件")
            else:
                self._append_message("system", f"✅ {provider} API 密钥已配置")
    
    def _update_mode_ui(self):
        mode = self.settings.generation_mode
        if mode == "api":
            self.mode_hint.config(text=f"☁️ API: {self.provider_var.get()}", foreground="green")
            self.provider_combo.config(state="readonly")
        else:
            self.mode_hint.config(text="🖥️ 本地模式", foreground="blue")
            self.provider_combo.config(state="disabled")
    
    # ============================================================
    # 选择模型
    # ============================================================
    def _select_model_file(self):
        from tkinter import filedialog
        filepath = filedialog.askopenfilename(
            title="选择 SD 模型文件",
            filetypes=[("模型文件", "*.safetensors *.ckpt"), ("所有文件", "*.*")]
        )
        if filepath:
            self.settings.model_path = filepath
            self._append_message("system", f"📦 已选择模型: {os.path.basename(filepath)}")
            self._load_model()
    
    # ============================================================
    # 聊天区域
    # ============================================================
    def _build_chat_area(self, parent):
        container = ttk.Frame(parent)
        container.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.chat_text = tk.Text(
            container,
            wrap=tk.WORD,
            font=("微软雅黑", 10),
            bg="#f5f5f5",
            relief="flat",
            padx=10,
            pady=10
        )
        scrollbar = ttk.Scrollbar(container, orient=tk.VERTICAL, command=self.chat_text.yview)
        self.chat_text.configure(yscrollcommand=scrollbar.set)
        
        self.chat_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.chat_text.config(state=tk.DISABLED)
        
        # ---------- 绑定双击事件（用于图片预览） ----------
        self.chat_text.bind("<Double-Button-1>", self._on_image_double_click)
        self._bound_double_click = True
        
        self._append_message("system", "👋 欢迎！输入描述即可生成图片")
        self._append_message("system", "💡 试试说：生成一张美丽的日落风景")
        self._append_message("system", f"🔄 当前模式: {self.settings.generation_mode}")
    
    # ============================================================
    # 输入区域
    # ============================================================
    def _build_input_area(self, parent):
        input_frame = ttk.Frame(parent)
        input_frame.pack(fill=tk.X, pady=5)
        
        self.input_text = tk.Text(
            input_frame,
            height=3,
            wrap=tk.WORD,
            font=("微软雅黑", 10),
            relief="sunken",
            borderwidth=1
        )
        self.input_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        btn_frame = ttk.Frame(input_frame)
        btn_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=5)
        
        self.send_btn = ttk.Button(
            btn_frame,
            text="🚀 发送",
            command=self._on_send
        )
        self.send_btn.pack(side=tk.TOP, pady=2)
        
        self.cancel_btn = ttk.Button(
            btn_frame,
            text="⏹️ 取消",
            command=self._cancel_generation,
            state=tk.DISABLED
        )
        self.cancel_btn.pack(side=tk.TOP, pady=2)
        
        self.input_text.bind("<Control-Return>", lambda e: self._on_send())
    
    # ============================================================
    # 状态栏
    # ============================================================
    def _build_status_bar(self):
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(status_frame, textvariable=self.status_var, foreground="blue").pack(side=tk.LEFT)
        
        self.progress_bar = ttk.Progressbar(status_frame, length=200, mode='determinate')
        self.progress_bar.pack(side=tk.RIGHT, padx=5)
    
    # ============================================================
    # 模型加载
    # ============================================================
    def _load_model(self):
        if self.is_model_loaded:
            return
        
        model_path = self.settings.get_model_path()
        if not model_path:
            messagebox.showerror("错误", "未配置模型路径，请在 settings.py 中设置")
            return
        
        self.load_btn.config(state=tk.DISABLED)
        self.status_var.set("📦 正在加载模型...")
        
        def load_thread():
            try:
                from diffusers import StableDiffusionPipeline
                import torch
                
                self._update_status_progress(0.1, "加载中...")
                print(f"📦 加载模型: {model_path}")
                
                pipe = StableDiffusionPipeline.from_single_file(
                    model_path,
                    torch_dtype=torch.float32,
                    safety_checker=None,
                    requires_safety_checker=False,
                    use_safetensors=True,
                    low_cpu_mem_usage=True
                )
                pipe.to("cpu")
                
                try:
                    if hasattr(pipe.vae, 'enable_slicing'):
                        pipe.vae.enable_slicing()
                    elif hasattr(pipe, 'enable_vae_slicing'):
                        pipe.enable_vae_slicing()
                except Exception as e:
                    print(f"⚠️ VAE slicing 设置失败: {e}")
                
                try:
                    if hasattr(pipe, 'enable_attention_slicing'):
                        pipe.enable_attention_slicing()
                except Exception as e:
                    print(f"⚠️ Attention slicing 设置失败: {e}")
                
                self.pipe = pipe
                self.is_model_loaded = True
                self.root.after(0, self._on_load_complete)
            except Exception as err:
                error_msg = str(err)
                print(f"❌ 加载失败: {error_msg}")
                import traceback
                traceback.print_exc()
                self.root.after(0, lambda msg=error_msg: self._on_load_error(msg))
        
        threading.Thread(target=load_thread, daemon=True).start()
    
    def _on_load_complete(self):
        self.load_btn.config(state=tk.NORMAL)
        self.model_status.config(text="🟢 已加载", foreground="green")
        self.status_var.set("✅ 模型加载完成")
        self._append_message("system", "✅ 模型已就绪，可以开始生图了！")
    
    def _on_load_error(self, error):
        self.load_btn.config(state=tk.NORMAL)
        self.model_status.config(text="🔴 加载失败", foreground="red")
        self.status_var.set(f"❌ 加载失败")
        self._append_message("system", f"❌ 模型加载失败: {error}")
        messagebox.showerror("错误", f"模型加载失败:\n{error}")
    
    def _update_status_progress(self, value, msg):
        self.root.after(0, lambda: self.progress_bar.config(value=value * 100))
        self.root.after(0, lambda: self.status_var.set(msg))
    
    # ============================================================
    # 图片上传
    # ============================================================
    def _upload_image(self):
        from tkinter import filedialog
        from PIL import Image
        
        files = filedialog.askopenfilenames(
            title="选择图片",
            filetypes=[("图片文件", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"), ("所有文件", "*.*")]
        )
        
        if not files:
            return
        
        for f in files:
            try:
                img = Image.open(f)
                self.uploaded_images.append(img)
                if self.uploaded_image is None:
                    self.uploaded_image = img
            except Exception as e:
                self._append_message("system", f"⚠️ 无法加载 {os.path.basename(f)}: {e}")
        
        count = len(self.uploaded_images)
        self.upload_status.config(text=f"📎 {count} 张")
        self._append_message("system", f"📎 已上传 {count} 张图片")
        
        if count >= 2:
            self._append_message("system", "✅ 已上传2张图片！输入指令可生成双人图")
    
    def _clear_upload(self):
        self.uploaded_images = []
        self.uploaded_image = None
        self.upload_status.config(text="")
        self._append_message("system", "🗑️ 已清除所有图片")
    
    # ============================================================
    # 发送消息
    # ============================================================
    def _on_send(self):
        if hasattr(self, '_is_processing') and self._is_processing:
            return
        
        user_input = self.input_text.get("1.0", tk.END).strip()
        if not user_input:
            return
        
        self.input_text.delete("1.0", tk.END)
        self._append_message("user", user_input)
        
        self._is_processing = True
        self.send_btn.config(state=tk.DISABLED)
        self.cancel_btn.config(state=tk.NORMAL)
        
        threading.Thread(target=self._process, args=(user_input,), daemon=True).start()
    
    def _process(self, text: str):
        try:
            intent = self.intent_analyzer.analyze(
                text,
                has_image=bool(self.uploaded_images),
                has_multiple=len(self.uploaded_images) >= 2
            )
            
            self._append_log(f"🔍 意图: {intent.type}")
            
            if self.llm.is_available() and self.settings.llm_enabled:
                if intent.type in ["text_to_image"]:
                    self._enhance_with_llm(intent)
            
            from handlers import TextToImageHandler, ImageToImageHandler, CoupleHandler, ChatHandler
            
            handlers = {
                "text_to_image": TextToImageHandler(self),
                "image_to_image": ImageToImageHandler(self),
                "couple": CoupleHandler(self),
                "chat": ChatHandler(self),
                "video": VideoHandler(self),  # ✅ 新增
            }
            
            handler = handlers.get(intent.type)
            if handler:
                handler.handle(vars(intent))
            else:
                self._append_message("assistant", f"⚠️ 暂不支持 {intent.type} 模式")
            
            self.context.update(vars(intent))
            
        except Exception as e:
            self._append_message("assistant", f"❌ 处理失败: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            self._is_processing = False
            self.root.after(0, self._reset_ui)
    
    def _enhance_with_llm(self, intent):
        self._append_log("🧠 LLM 增强中...")
        prompt = f"""请将以下描述转换为Stable Diffusion英文提示词（用逗号分隔），添加质量词：
        
用户需求：{intent.original_text}

只输出英文提示词："""
        result = self.llm.generate(prompt, timeout=20, max_tokens=200)
        if result:
            intent.prompt = result
            intent.llm_enhanced = True
            self._append_log("✅ LLM 增强完成")
    
    def _reset_ui(self):
        self.send_btn.config(state=tk.NORMAL)
        self.cancel_btn.config(state=tk.DISABLED)
        self.progress_bar.config(value=0)
    
    def _cancel_generation(self):
        if hasattr(self, 'cancel_flag'):
            self.cancel_flag = True
        self.status_var.set("⏹️ 已取消")
        self._append_message("system", "⏹️ 已取消")
        self._reset_ui()
    
    # ============================================================
    # LLM 检查
    # ============================================================
    def _check_llm(self):
        status = self.llm.get_status_message()
        color = "green" if "✅" in status else "gray" if "⚠️" in status else "red"
        self.llm_status.config(text="●", foreground=color)
        if "⚠️" in status:
            self._append_message("system", status)
    
    # ============================================================
    # 清空对话 & 打开目录
    # ============================================================
    def _clear_chat(self):
        self.chat_text.config(state=tk.NORMAL)
        self.chat_text.delete("1.0", tk.END)
        self.chat_text.config(state=tk.DISABLED)
        self.context.clear()
        self._append_message("system", "🗑️ 对话已清空")
    
    def _open_output(self):
        output_dir = str(self.settings.output_dir)
        if os.path.exists(output_dir):
            import sys
            if sys.platform == 'win32':
                os.startfile(output_dir)
            else:
                os.system(f'open "{output_dir}"')

    def _fetch_news(self):
        """抓取新闻并显示摘要"""
        import threading
        from skills import NewsAggregator
        
        self._append_message("system", "📰 正在抓取新闻...")
        self.status_var.set("📰 抓取中...")
        
        def fetch_thread():
            try:
                aggregator = NewsAggregator({
                    "output_dir": "./output/news",
                    "ai_model": self.settings.ollama_model,
                    "ollama_url": self.settings.ollama_url,
                    "validate_feeds": True,
                    "top_n": 15,
                })
                
                result = aggregator.execute(category="world", top_n=15)
                
                if result["status"] == "success":
                    data = result["result"]
                    report = data.get("report", "")
                    
                    # 精简显示（只显示 AI 摘要 + 新闻标题列表）
                    lines = report.split("\n")
                    # 提取 AI 摘要部分（在 【AI 智能摘要】 和 分隔线之间）
                    ai_summary = ""
                    in_summary = False
                    for line in lines:
                        if "【AI 智能摘要】" in line:
                            in_summary = True
                            continue
                        if in_summary and "---" in line:
                            break
                        if in_summary and line.strip():
                            ai_summary += line + "\n"
                    
                    # 显示
                    display_text = f"📰 新闻简报（共 {len(data['articles'])} 条）\n"
                    display_text += "─" * 40 + "\n"
                    display_text += ai_summary or "（AI 摘要生成中）\n"
                    display_text += "─" * 40 + "\n"
                    # 显示新闻标题列表
                    for i, article in enumerate(data['articles'][:10], 1):
                        display_text += f"{i}. {article.get('title', '无标题')}\n"
                    if len(data['articles']) > 10:
                        display_text += f"... 共 {len(data['articles'])} 条，查看完整报告请打开输出目录"
                    
                    self.root.after(0, lambda: self._append_message("assistant", display_text))
                    
                    if data.get("report_file"):
                        self.root.after(0, lambda: self._append_message(
                            "system", f"📁 完整报告: {data['report_file']}"
                        ))
                else:
                    self.root.after(0, lambda: self._append_message(
                        "system", f"❌ 新闻抓取失败: {result.get('error', '未知错误')}"
                    ))
                    
            except Exception as e:
                self.root.after(0, lambda: self._append_message(
                    "system", f"❌ 错误: {str(e)}"
                ))
            finally:
                self.root.after(0, lambda: self.status_var.set("就绪"))
        
        threading.Thread(target=fetch_thread, daemon=True).start()


    def _generate_tech_article(self):
        """生成技术热点文章"""
        import threading
        from skills.tech_hot_article import TechHotArticle
        
        self._append_message("system", "📰 正在获取技术热点并生成文章...")
        self.status_var.set("📰 生成文章中...")
        
        def thread_func():
            try:
                generator = TechHotArticle({
                    "model": self.settings.ollama_model,
                    "ollama_url": self.settings.ollama_url,
                })
                result = generator.execute()
                
                if result["status"] == "success":
                    data = result["result"]
                    msg = f"✅ 文章生成完成！\n"
                    msg += f"📄 标题: {data['title']}\n"
                    msg += f"📁 Word文档: {data['word_file']}\n"
                    msg += f"🖼️ 配图: {data['image_file']}"
                    self.root.after(0, lambda: self._append_message("assistant", msg))
                else:
                    self.root.after(0, lambda: self._append_message("system", f"❌ 生成失败: {result.get('error')}"))
            except Exception as e:
                self.root.after(0, lambda: self._append_message("system", f"❌ 错误: {str(e)}"))
            finally:
                self.root.after(0, lambda: self.status_var.set("就绪"))
        
        threading.Thread(target=thread_func, daemon=True).start()
    
    # ============================================================
    # 消息添加（文本）
    # ============================================================
    def _append_message(self, role: str, content: str):
        self.chat_text.config(state=tk.NORMAL)
        timestamps = {"user": "👤 你", "assistant": "🤖 助手", "system": "📌 系统"}
        prefix = timestamps.get(role, "📝")
        self.chat_text.insert(tk.END, f"{prefix}: {content}\n\n")
        self.chat_text.see(tk.END)
        self.chat_text.config(state=tk.DISABLED)
    
    def _append_log(self, msg: str):
        self.root.after(0, lambda: self.status_var.set(msg))
    
    # ============================================================
    # ---------- 新增：图片预览功能 ----------
    # ============================================================
    def _append_image(self, image_path: str, caption: str = ""):
        """
        在聊天框中插入图片缩略图，并绑定双击事件
        """
        if not os.path.exists(image_path):
            self._append_message("system", f"⚠️ 图片文件不存在: {image_path}")
            return
        
        try:
            img = Image.open(image_path)
            img.thumbnail((200, 200))   # 缩略图大小
            photo = ImageTk.PhotoImage(img)
            self.image_refs.append(photo)  # 保持引用
        except Exception as e:
            self._append_message("system", f"⚠️ 图片加载失败: {e}")
            return
        
        self.chat_text.config(state=tk.NORMAL)
        
        if caption:
            self.chat_text.insert(tk.END, f"📷 {caption}\n")
        
        # 插入图片
        self.chat_text.image_create(tk.END, image=photo, padx=5, pady=5)
        
        # 插入隐藏标记（用于双击时定位图片路径）
        marker = f"__IMG__{image_path}__"
        self.chat_text.insert(tk.END, marker)
        # 将标记隐藏（设置极小字体或与背景同色）
        self.chat_text.tag_add("hidden", tk.END + "-" + f"{len(marker)}c", tk.END)
        self.chat_text.tag_config("hidden", foreground="#f5f5f5", font=("", 1))
        
        self.chat_text.insert(tk.END, "\n\n")
        self.chat_text.see(tk.END)
        self.chat_text.config(state=tk.DISABLED)
    
    def _on_image_double_click(self, event):
        """双击检测图片路径，打开大图预览窗口"""
        # 获取点击位置的索引
        index = self.chat_text.index(f"@%d,%d" % (event.x, event.y))
        # 获取该行文本
        line_start = self.chat_text.index(f"{index} linestart")
        line_end = self.chat_text.index(f"{index} lineend")
        line_text = self.chat_text.get(line_start, line_end)
        
        # 查找隐藏标记 __IMG__...__
        match = re.search(r"__IMG__(.+?)__", line_text)
        if match:
            image_path = match.group(1)
            if os.path.exists(image_path):
                self._show_image_preview(image_path)
            else:
                self._append_message("system", f"⚠️ 图片已删除: {image_path}")
    
    def _show_image_preview(self, image_path: str):
        """显示大图预览窗口"""
        preview = tk.Toplevel(self.root)
        preview.title(f"图片预览 - {os.path.basename(image_path)}")
        preview.geometry("800x600")
        preview.grab_set()
        
        try:
            img = Image.open(image_path)
            # 适应窗口大小
            img.thumbnail((750, 550))
            photo = ImageTk.PhotoImage(img)
        except Exception as e:
            messagebox.showerror("错误", f"无法加载图片: {e}")
            preview.destroy()
            return
        
        label = tk.Label(preview, image=photo)
        label.image = photo
        label.pack(padx=20, pady=20, fill=tk.BOTH, expand=True)
        
        btn_frame = tk.Frame(preview)
        btn_frame.pack(pady=10)
        
        tk.Button(btn_frame, text="📁 打开文件位置",
                  command=lambda: self._open_file_location(image_path)).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="关闭", command=preview.destroy).pack(side=tk.LEFT, padx=5)
    
    def _open_file_location(self, file_path: str):
        """打开文件所在文件夹并选中文件"""
        import sys
        import subprocess
        path = os.path.normpath(file_path)
        if sys.platform == 'win32':
            subprocess.Popen(f'explorer /select,"{path}"')
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', '-R', path])
        else:
            subprocess.Popen(['xdg-open', os.path.dirname(path)])
    
    # ============================================================
    # 运行
    # ============================================================
    def run(self):
        self.root.mainloop()