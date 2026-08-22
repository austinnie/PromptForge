# gui/app.py
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import os

from config.settings import settings
from core.intent_analyzer import IntentAnalyzer
from core.context_manager import ContextManager
from services.llm_service import LLMService
from handlers import TextToImageHandler, ChatHandler


class ChatApp:
    """智能生图主应用"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("💬 智能生图")
        self.root.geometry("750x650")
        
        self.settings = settings
        self.intent_analyzer = IntentAnalyzer()
        self.context = ContextManager()
        self.llm = LLMService()
        
        # 模型状态
        self.is_model_loaded = False
        self.pipe = None
        
        # 图片上传状态
        self.uploaded_images = []
        self.uploaded_image = None
        
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
    
    def _build_toolbar(self, parent):
        """构建工具栏"""
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill=tk.X, pady=5)
        
        # 模型状态
        self.model_status = ttk.Label(toolbar, text="🔴 未加载", foreground="red")
        self.model_status.pack(side=tk.LEFT, padx=5)
        
        # 选择模型按钮
        self.select_model_btn = ttk.Button(
            toolbar,
            text="📂 选择模型",
            command=self._select_model_file
        )
        self.select_model_btn.pack(side=tk.LEFT, padx=5)
        
        # 加载模型按钮
        self.load_btn = ttk.Button(toolbar, text="📦 加载模型", command=self._load_model)
        self.load_btn.pack(side=tk.LEFT, padx=5)
        
        # 上传图片按钮
        self.upload_btn = ttk.Button(
            toolbar,
            text="📎 上传图片",
            command=self._upload_image
        )
        self.upload_btn.pack(side=tk.LEFT, padx=5)
        
        # 清除图片按钮
        self.clear_upload_btn = ttk.Button(
            toolbar,
            text="🗑️ 清除图片",
            command=self._clear_upload
        )
        self.clear_upload_btn.pack(side=tk.LEFT, padx=5)
        
        # 图片状态
        self.upload_status = ttk.Label(toolbar, text="", foreground="green")
        self.upload_status.pack(side=tk.LEFT, padx=5)
        
        # LLM状态
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        self.llm_status = ttk.Label(toolbar, text="●", foreground="gray")
        self.llm_status.pack(side=tk.LEFT, padx=2)
        
        # 清除对话
        ttk.Button(toolbar, text="🗑️ 清除对话", command=self._clear_chat).pack(side=tk.RIGHT, padx=5)
        
        # 打开输出
        ttk.Button(toolbar, text="📁 输出目录", command=self._open_output).pack(side=tk.RIGHT, padx=5)
    
    def _select_model_file(self):
        """选择模型文件"""
        from tkinter import filedialog
        
        filepath = filedialog.askopenfilename(
            title="选择 SD 模型文件",
            filetypes=[
                ("模型文件", "*.safetensors *.ckpt"),
                ("所有文件", "*.*")
            ]
        )
        
        if filepath:
            self.settings.model_path = filepath
            self._append_message("system", f"📦 已选择模型: {os.path.basename(filepath)}")
            # 自动加载
            self._load_model()
    
    def _build_chat_area(self, parent):
        """构建对话区域"""
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
        
        self._append_message("system", "👋 欢迎！输入描述即可生成图片")
        self._append_message("system", "💡 试试说：生成一张美丽的日落风景")
    
    def _build_input_area(self, parent):
        """构建输入区域"""
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
    
    def _build_status_bar(self):
        """构建状态栏"""
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(status_frame, textvariable=self.status_var, foreground="blue").pack(side=tk.LEFT)
        
        self.progress_bar = ttk.Progressbar(status_frame, length=200, mode='determinate')
        self.progress_bar.pack(side=tk.RIGHT, padx=5)
    

    # gui/app.py - 修复 _load_model 方法

    def _load_model(self):
        """加载模型"""
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
                
                # ✅ 修复：新版本 Diffusers 的 API 变化
                # 旧版: pipe.enable_vae_slicing()
                # 新版: pipe.vae.enable_slicing()
                try:
                    # 尝试新版 API
                    if hasattr(pipe.vae, 'enable_slicing'):
                        pipe.vae.enable_slicing()
                    elif hasattr(pipe, 'enable_vae_slicing'):
                        pipe.enable_vae_slicing()
                except Exception as e:
                    print(f"⚠️ VAE slicing 设置失败: {e}")
                
                try:
                    # 尝试新版 API
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
        """加载完成"""
        self.load_btn.config(state=tk.NORMAL)
        self.model_status.config(text="🟢 已加载", foreground="green")
        self.status_var.set("✅ 模型加载完成")
        self._append_message("system", "✅ 模型已就绪，可以开始生图了！")
    
    def _on_load_error(self, error):
        """加载失败"""
        self.load_btn.config(state=tk.NORMAL)
        self.model_status.config(text="🔴 加载失败", foreground="red")
        self.status_var.set(f"❌ 加载失败")
        self._append_message("system", f"❌ 模型加载失败: {error}")
        messagebox.showerror("错误", f"模型加载失败:\n{error}")
    
    def _update_status_progress(self, value, msg):
        """更新进度"""
        self.root.after(0, lambda: self.progress_bar.config(value=value * 100))
        self.root.after(0, lambda: self.status_var.set(msg))
    
    def _upload_image(self):
        """上传图片"""
        from tkinter import filedialog
        from PIL import Image, ImageTk
        
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
        """清除上传的图片"""
        self.uploaded_images = []
        self.uploaded_image = None
        self.upload_status.config(text="")
        self._append_message("system", "🗑️ 已清除所有图片")
    
    def _on_send(self):
        """发送消息"""
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
        """处理用户输入"""
        try:
            intent = self.intent_analyzer.analyze(
                text,
                has_image=bool(self.uploaded_images),
                has_multiple=len(self.uploaded_images) >= 2
            )
            
            self._append_log(f"🔍 意图: {intent.type}")
            
            # LLM增强
            if self.llm.is_available() and self.settings.llm_enabled:
                if intent.type in ["text_to_image"]:
                    self._enhance_with_llm(intent)
            
            # 路由
            from handlers import TextToImageHandler, ImageToImageHandler, CoupleHandler, ChatHandler
            
            handlers = {
                "text_to_image": TextToImageHandler(self),
                "image_to_image": ImageToImageHandler(self),
                "couple": CoupleHandler(self),
                "chat": ChatHandler(self),
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
        """使用LLM增强提示词"""
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
        """重置UI状态"""
        self.send_btn.config(state=tk.NORMAL)
        self.cancel_btn.config(state=tk.DISABLED)
        self.progress_bar.config(value=0)
    
    def _cancel_generation(self):
        """取消生成"""
        if hasattr(self, 'cancel_flag'):
            self.cancel_flag = True
        self.status_var.set("⏹️ 已取消")
        self._append_message("system", "⏹️ 已取消")
        self._reset_ui()
    
    def _check_llm(self):
        """检查LLM状态"""
        status = self.llm.get_status_message()
        color = "green" if "✅" in status else "gray" if "⚠️" in status else "red"
        self.llm_status.config(text="●", foreground=color)
        
        if "⚠️" in status:
            self._append_message("system", status)
    
    def _clear_chat(self):
        """清除对话"""
        self.chat_text.config(state=tk.NORMAL)
        self.chat_text.delete("1.0", tk.END)
        self.chat_text.config(state=tk.DISABLED)
        self.context.clear()
        self._append_message("system", "🗑️ 对话已清空")
    
    def _open_output(self):
        """打开输出目录"""
        output_dir = str(self.settings.output_dir)
        if os.path.exists(output_dir):
            import sys
            if sys.platform == 'win32':
                os.startfile(output_dir)
            else:
                os.system(f'open "{output_dir}"')
    
    def _append_message(self, role: str, content: str):
        """添加消息"""
        self.chat_text.config(state=tk.NORMAL)
        
        timestamps = {"user": "👤 你", "assistant": "🤖 助手", "system": "📌 系统"}
        prefix = timestamps.get(role, "📝")
        
        self.chat_text.insert(tk.END, f"{prefix}: {content}\n\n")
        self.chat_text.see(tk.END)
        self.chat_text.config(state=tk.DISABLED)
    
    def _append_log(self, msg: str):
        """添加日志（仅状态栏）"""
        self.root.after(0, lambda: self.status_var.set(msg))
    
    def run(self):
        """运行应用"""
        self.root.mainloop()