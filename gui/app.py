# gui/app.py
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import os
import re
import glob
import json
import logging
import webbrowser
import subprocess
from pathlib import Path
from PIL import Image, ImageTk

from config.settings import settings
from core.intent_analyzer import IntentAnalyzer
from core.context_manager import ContextManager
from services.llm_service import LLMService
from handlers import TextToImageHandler, ImageToImageHandler, CoupleHandler,ChatHandler, VideoHandler,PresetHandler

class _DailyLogHandler(logging.Handler):
    """把 DailyPipeline 的日志转发到聊天区。

    - 只转发来自 skills.daily_pipeline.* 的记录
    - 带 emoji 的进度日志原样显示，其他 INFO 过滤掉，避免刷屏
    """

    KEEP_HINTS = ("✅", "❌", "⚠️", "🎯", "🎨", "📄", "📤", "🎉",
                  "📁", "🖼️", "⬇️", "🔄", "😴")

    def __init__(self, app):
        super().__init__()
        self.app = app

    def emit(self, record):
        try:
            if not record.name.startswith("skills.daily_pipeline"):
                return
            if record.levelno < logging.INFO:
                return

            msg = self.format(record).strip()
            if not msg:
                return

            if record.levelno >= logging.WARNING:
                # 已带 emoji 就不再叠加，避免 "⚠️ ❌ xxx"
                if msg.startswith(("✅", "❌", "⚠️", "🎉", "🚫", "⏹️")):
                    text = msg
                else:
                    text = f"⚠️ {msg}"
            else:
                if not any(h in msg for h in self.KEEP_HINTS):
                    return
                text = msg

            self.app.root.after(0, lambda t=text: self.app._append_message("system", t))
        except Exception:
            pass



    
class ChatApp:
    """智能生图主应用"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.publish_wechat_var = tk.BooleanVar(value=True)
        self.count_var = tk.IntVar(value=6) 
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

        # 网络广播播放器（懒加载）
        self._radio_player = None
        
        self._setup_ui()
        self._build_menubar()
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
            values=[
            "pollinations", 
            "huggingface", 
            "tongyi", 
            "yige", 
            "hunyuan", 
            "agnes", 
            "freeapi", 
            "replicate", 
            "stability",
            "free_multimodal_proxy",   # 新增
            "freellmapi",               # 新增
            "siliconflow",              # 新增
            "openrouter",               # 新增            
            ],
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

        # ✅ 每日任务：一键生图 → 鉴赏 → 排版 → 推送

        ttk.Button(
            toolbar_row2,
            text="📅 每日任务",
            command=self._run_daily_task
        ).pack(side=tk.LEFT, padx=2)

        # ✅ 每周任务：技术热点文章（脚本：scripts/weekly_tech_task.py）
        ttk.Button(
            toolbar_row2,
            text="📆 每周任务",
            command=self._run_weekly_tech_task
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
        
        # ============================================================
        # 第三行：预设控制
        # ============================================================
        toolbar_row3 = ttk.Frame(parent)
        toolbar_row3.pack(fill=tk.X, pady=2)

        ttk.Label(toolbar_row3, text="🎨 预设:").pack(side=tk.LEFT, padx=2)

        # 下拉框（延迟加载，避免启动变慢）
        self.preset_var = tk.StringVar()
        self.preset_combo = ttk.Combobox(
            toolbar_row3,
            textvariable=self.preset_var,
            values=[],
            width=30,
            state="readonly",
        )
        self.preset_combo.pack(side=tk.LEFT, padx=2)
        self.preset_combo.bind('<<ComboboxSelected>>', self._on_preset_selected)

        # 🎲 换一张
        ttk.Button(
            toolbar_row3, text="🎲 换一张",
            command=self._preset_reroll,
        ).pack(side=tk.LEFT, padx=2)

        # N 张
        ttk.Label(toolbar_row3, text="张数:").pack(side=tk.LEFT, padx=5)
        ttk.Spinbox(
            toolbar_row3, from_=1, to=10, width=3,
            textvariable=self.count_var,
        ).pack(side=tk.LEFT)

        # ✅ 放在最后，靠右
        ttk.Checkbutton(
            toolbar_row3,
            text="📤 自动推公众号草稿箱",
            variable=self.publish_wechat_var,
        ).pack(side=tk.RIGHT, padx=8)

        # 加载预设列表（同步，很快）
        self._load_presets()        


    def _load_presets(self):
        """同步加载预设列表（99 个 glob 很快，不开线程）"""
        try:
            from presets_meta import get_display_name, get_category, CATEGORY_ORDER
            from preset_bridge import preset_bridge

            all_presets = preset_bridge.list_presets()
            sorted_presets = sorted(
                all_presets,
                key=lambda p: (
                    CATEGORY_ORDER.index(get_category(p)) if get_category(p) in CATEGORY_ORDER else 999,
                    p,
                )
            )
            display = [get_display_name(p) for p in sorted_presets]

            # ✅ 在最前面加一个"不使用预设"占位项
            EMPTY_LABEL = "（不使用预设）"
            display = [EMPTY_LABEL] + display

            self.preset_combo.config(values=display)
            self.preset_var.set(EMPTY_LABEL)
            self._empty_preset_label = EMPTY_LABEL
            print(f"✅ 预设列表已加载: {len(display) - 1} 个（+1 空项）")
         
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"⚠️ 预设列表加载失败: {e}")
        
    def _get_selected_preset(self) -> str:
        """从下拉框解析出预设名；选中空项时返回 None"""
        val = self.preset_var.get()
        if not val:
            return None
        # ✅ 命中"不使用预设"占位项 → 视为未选
        if val == getattr(self, '_empty_preset_label', None):
            return None
        # "mecha_glow — 机甲发光" → "mecha_glow"
        return val.split(" — ")[0].strip() if " — " in val else val.strip()

    def _on_preset_selected(self, event=None):
        preset = self._get_selected_preset()
        if not preset:
            # ✅ 选的是"不使用预设" → 提示并清掉去重记录
            self._last_shown_preset = None
            self._append_message("system", "🎨 已清除预设选择（后续发送将走正常意图分析）")
            return
        if getattr(self, '_last_shown_preset', None) == preset:
            return
        self._last_shown_preset = preset
        self._append_message("system", f"🎨 已选择预设: {preset}（输入框留空点「发送」可直接生成，或用「🎨 用预设」按钮）")


    def _process_with_preset(self, text: str, preset: str):
        """用指定预设处理输入（下拉框选择时触发）"""
        if hasattr(self, '_is_processing') and self._is_processing:
            return
        
        self._last_preset_input = text
        self.input_text.delete("1.0", tk.END)
        self._append_message("user", text)
        
        self._is_processing = True
        self.send_btn.config(state=tk.DISABLED)
        self.cancel_btn.config(state=tk.NORMAL)
        
        threading.Thread(
            target=self._preset_thread,
            args=(text, preset),
            daemon=True,
        ).start()

    def _preset_reroll(self):
        """🎲 换一张：同一预设 + 同一主体，6 层全重抽"""
        preset = self._get_selected_preset()
        if not preset:
            self._append_message("system", "⚠️ 请先选一个预设")
            return

        # 从上一次用户输入里取
        last_input = getattr(self, '_last_preset_input', None)
        if not last_input:
            last_input = self.input_text.get("1.0", tk.END).strip()
        if not last_input:
            self._append_message("system", "⚠️ 请先在输入框写下主体描述，例如：画一个机甲少女")
            return

        self._process_with_preset(last_input, preset)
    
    
    def _update_toolbar_status(self, text, color="gray"):
        """更新工具栏右侧状态"""
        try:
            self.status_label.config(text=text, foreground=color)
        except:
            pass

    # ============================================================
    # ✅ 第一批：菜单栏
    # ============================================================
    def _build_menubar(self):
        """构建菜单栏。工具栏只留高频操作，长尾功能收进菜单。"""
        menubar = tk.Menu(self.root)

        # ── 生成 ──
        gen_menu = tk.Menu(menubar, tearoff=0)
        gen_menu.add_command(label="🎨 图像（预设）", command=self._on_send_with_preset)
        gen_menu.add_command(label="🎬 视频生成", command=self._run_video_generator)
        gen_menu.add_command(label="🎵 音乐生成", command=self._run_music_generator)
        gen_menu.add_command(label="📝 小说生成", command=self._run_novel_writer)
        gen_menu.add_command(label="🎙️ 语音合成（TTS）", command=self._run_voice_tts)
        gen_menu.add_separator()
        gen_menu.add_command(label="🎞️ 多媒体成片", state="disabled")
        menubar.add_cascade(label="生成", menu=gen_menu)

        # ── 排版 ──
        fmt_menu = tk.Menu(menubar, tearoff=0)
        fmt_menu.add_command(label="🖼️ 图片鉴赏文章", command=self._run_image_curator)
        fmt_menu.add_command(label="📰 微信排版", command=self._run_wechat_formatter)
        menubar.add_cascade(label="排版", menu=fmt_menu)

        # ── 发布 ──
        pub_menu = tk.Menu(menubar, tearoff=0)
        pub_menu.add_command(label="🚀 一键多平台分发", command=self._run_multi_publish)
        pub_menu.add_command(label="🔑 平台登录", command=self._run_platform_login)
        menubar.add_cascade(label="发布", menu=pub_menu)

        # ── 搜索 ──
        search_menu = tk.Menu(menubar, tearoff=0)
        search_menu.add_command(label="🖼️ 图片搜索", command=self._run_search_images)
        search_menu.add_command(label="🎬 视频搜索", command=self._run_search_videos)
        search_menu.add_command(label="📰 网页搜索", command=self._run_search_text)
        menubar.add_cascade(label="搜索", menu=search_menu)

        # ── 媒体 ──
        media_menu = tk.Menu(menubar, tearoff=0)
        media_menu.add_command(label="📺 视频播放器", command=self._run_video_player)         
        media_menu.add_command(label="🎵 音乐播放器", command=self._run_music_player)         
        media_menu.add_command(label="📻 网络广播", command=self._run_radio_player)

        media_menu.add_separator()
        media_menu.add_command(label="⏸️ 暂停/继续", command=self._toggle_pause_media)
        media_menu.add_command(label="▶️ 重播上一个", command=self._replay_media)
        media_menu.add_command(label="⏹️ 停止广播", command=self._stop_radio)        
        
        media_menu.add_separator()
        media_menu.add_command(label="📋 收藏电台", command=self._show_radio_favorites)
        menubar.add_cascade(label="媒体", menu=media_menu)
        
        # ── 自动化 ──
        auto_menu = tk.Menu(menubar, tearoff=0)
        auto_menu.add_command(label="📅 每日任务", command=self._run_daily_task)
        auto_menu.add_command(label="🔥 每周技术热点", command=self._run_weekly_tech_task)
        auto_menu.add_command(label="📰 新闻简报", command=self._fetch_news)
        auto_menu.add_command(label="📄 技术文章", command=self._generate_tech_article)
        menubar.add_cascade(label="自动化", menu=auto_menu)

        self.root.config(menu=menubar)

    # ============================================================
    # ✅ 第一批：通用 Skill 执行框架
    # ============================================================
    def _run_skill(self, title: str, worker, on_success=None):
        """通用 skill 执行器。

        Args:
            title: 状态栏标题，如 "🖼️ 图片鉴赏"
            worker: 无参函数，返回 result dict：{"status", "result", "error"}
            on_success: 可选。result["result"] 处理回调（在主线程）

        并发策略：同一时刻只允许一个 skill 运行。
        若已有任务在跑，本次请求**不入队、直接拒绝**，
        并在聊天区明确告知"当前在跑什么 + 本次没跑"，避免误以为已开始。
        """
        if getattr(self, "_skill_running", False):
            current = getattr(self, "_skill_current", "另一个任务")
            self._append_message(
                "system",
                f"⏳ 有任务正在执行（当前：{current}）\n"
                f"   请等待完成后再点「{title}」——本次请求未入队。"
            )
            return

        self._skill_running = True
        self._skill_current = title   # ✅ 记住当前跑的是谁
        self._append_message("system", f"{title} 开始...")
        self.status_var.set(f"{title} 执行中...")

        def thread_func():
            try:
                result = worker()
                if result.get("status") != "success":
                    err = result.get("error", "未知错误")
                    self.root.after(0, lambda e=err: self._append_message(
                        "assistant", f"❌ {title} 失败：{e}"
                    ))
                    return

                data = result.get("result") or {}
                if on_success:
                    self.root.after(0, lambda d=data: on_success(d))
                else:
                    preview = json.dumps(data, ensure_ascii=False, indent=2)[:800]
                    self.root.after(0, lambda p=preview: self._append_message(
                        "assistant", f"✅ {title} 完成\n{p}"
                    ))
            except Exception as e:
                import traceback
                traceback.print_exc()
                err = str(e)
                self.root.after(0, lambda m=err: self._append_message(
                    "assistant", f"❌ {title} 异常：{m}"
                ))
            finally:
                self._skill_running = False
                self._skill_current = None
                self.root.after(0, lambda: self.status_var.set("就绪"))

        threading.Thread(target=thread_func, daemon=True).start()

    # ── 弹窗小工具 ──
    def _ask_string(self, title, prompt, default=""):
        """单行文本输入。取消返回 None。"""
        from tkinter import simpledialog
        return simpledialog.askstring(title, prompt, initialvalue=default, parent=self.root)

    def _ask_int(self, title, prompt, default, min_v, max_v):
        """整数输入（带范围）。取消返回 None。"""
        from tkinter import simpledialog
        return simpledialog.askinteger(
            title, prompt, initialvalue=default,
            minvalue=min_v, maxvalue=max_v, parent=self.root,
        )

    def _ask_choice(self, title, prompt, options, default=None):
        """下拉选择对话框。取消返回 None。"""
        from tkinter import simpledialog
        top = tk.Toplevel(self.root)
        top.title(title)
        top.transient(self.root)
        top.grab_set()
        top.geometry("360x130")

        ttk.Label(top, text=prompt, wraplength=330).pack(padx=15, pady=(15, 8), anchor="w")
        var = tk.StringVar(value=default or (options[0] if options else ""))
        combo = ttk.Combobox(top, textvariable=var, values=options, state="readonly", width=40)
        combo.pack(padx=15, fill=tk.X)

        result = {"value": None}
        def on_ok():
            result["value"] = var.get()
            top.destroy()
        def on_cancel():
            top.destroy()

        btn = ttk.Frame(top)
        btn.pack(pady=12)
        ttk.Button(btn, text="确定", command=on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn, text="取消", command=on_cancel).pack(side=tk.LEFT, padx=5)
        top.wait_window()
        return result["value"]

    # ============================================================
    # ✅ 第一批：图片鉴赏文章
    # ============================================================
    def _run_image_curator(self):
        """选目录 → 鉴赏 → 生成多格式文章。"""
        from tkinter import filedialog
        folder = filedialog.askdirectory(title="选择图片目录", parent=self.root)
        if not folder:
            return

        default_title = Path(folder).name
        title = self._ask_string("图片鉴赏文章", "文章标题：", default_title)
        if title is None:
            return  # 用户取消

        def worker():
            from skills.image_curator import ImageCurator
            curator = ImageCurator({
                "generate_html": True,
                "generate_docx": True,
                "generate_pdf": True,
                "generate_clipboard": True,
            })
            return curator.curate(folder, title=title)

        self._run_skill("🖼️ 图片鉴赏", worker, on_success=self._show_curator_result)

    def _show_curator_result(self, data):
        """图片鉴赏结果：聊天区汇总 + 首图缩略 + 自动打开预览页。"""
        lines = ["✅ 图片鉴赏文章生成完成！", ""]
        lines.append(f"📝 标题：{data.get('title', '-')}")
        lines.append(f"🖼️ 张数：{data.get('image_count', 0)}")
        lines.append(f"⏱️ 耗时：{data.get('elapsed', '-')}")
        lines.append("")
        for key, label in [
            ("article_path",   "📄 Markdown"),
            ("html_path",      "🌐 HTML"),
            ("docx_path",      "📘 Word"),
            ("pdf_path",       "📄 PDF"),
            ("clipboard_path", "📋 富文本"),
        ]:
            p = data.get(key)
            if p:
                lines.append(f"{label}：{p}")
        self._append_message("assistant", "\n".join(lines))

        # 首图缩略
        article_dir = data.get("article_dir")
        if article_dir and os.path.isdir(article_dir):
            assets = os.path.join(article_dir, "assets")
            if os.path.isdir(assets):
                imgs = []
                for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
                    imgs.extend(glob.glob(os.path.join(assets, ext)))
                if imgs:
                    self._append_image(sorted(imgs)[0], f"文章首图（共 {len(imgs)} 张）")

        # 自动打开富文本（优先）或 HTML
        open_target = data.get("clipboard_path") or data.get("html_path")
        if open_target and os.path.exists(open_target):
            try:
                webbrowser.open(Path(open_target).as_uri())
            except Exception:
                pass

    # ============================================================
    # ✅ 第一批：微信排版
    # ============================================================
    def _run_wechat_formatter(self):
        """选 md 文件 → 选主题 → 排版。"""
        from tkinter import filedialog
        md = filedialog.askopenfilename(
            title="选择 Markdown 文件",
            filetypes=[("Markdown", "*.md"), ("所有文件", "*.*")],
            parent=self.root,
        )
        if not md:
            return

        # 主题下拉。列几个常用的，用户也可以手输（简化：用 askstring）
        common_themes = [
            "newspaper", "terracotta", "magazine", "ink",
            "bytedance", "github", "sspai", "midnight",
            "minimal-gold", "warm-card", "fresh-card", "ocean-card",
        ]
        theme = self._ask_choice(
            "微信排版", "选择主题：", common_themes, default="newspaper",
        )
        if not theme:
            return

        def worker():
            from skills.wechat_formatter import WechatFormatter
            fmt = WechatFormatter()
            return fmt.format(md, theme=theme, open=False)

        self._run_skill("📰 微信排版", worker, on_success=self._show_formatter_result)

    def _show_formatter_result(self, data):
        """微信排版结果：汇总 + 自动打开 preview.html。"""
        lines = ["✅ 微信排版完成！", ""]
        lines.append(f"📂 输出目录：{data.get('article_dir', '-')}")
        if data.get("preview_path"):
            lines.append(f"🌐 浏览器预览：{data['preview_path']}")
        if data.get("article_path"):
            lines.append(f"📄 微信 HTML：{data['article_path']}")
        lines.append("")
        lines.append("💡 在浏览器里点「复制到微信」按钮，粘到公众号后台即可。")
        self._append_message("assistant", "\n".join(lines))

        preview = data.get("preview_path")
        if preview and os.path.exists(preview):
            try:
                webbrowser.open(Path(preview).as_uri())
            except Exception:
                pass      



                
    # ============================================================
    # ✅ 第二批：视频生成
    # ============================================================
    def _run_video_generator(self):
        """视频生成：主题 + 时长。"""
        topic = self._ask_string("视频生成", "视频主题：", "月光下的森林，镜头缓缓推进")
        if not topic:
            return

        duration = self._ask_int("视频生成", "目标时长（秒，5-120）：", 30, 5, 120)
        if duration is None:
            return

        # 短任务不需要额外提示；超过 30s 会分段生成，提醒一下
        if duration > 30:
            self._append_message("system",
                f"⏳ 时长 {duration}s 会拆成多段生成，可能耗时几分钟，请耐心等待...")

        def worker():
            from skills.video_generator import VideoGenerator
            gen = VideoGenerator()
            return gen.generate(prompt=topic, duration=duration)

        self._run_skill("🎬 视频生成", worker, on_success=self._show_video_result)

    def _show_video_result(self, data):
        """视频生成结果：汇总 + 打开所在目录（视频不内嵌预览）。"""
        lines = ["✅ 视频生成完成！", ""]
        lines.append(f"📁 文件：{data.get('video_path', '-')}")
        lines.append(f"⏱️ 时长：{data.get('duration', '-')}s")
        lines.append(f"📹 片段：{data.get('segments', 1)}")
        lines.append(f"⏱️ 耗时：{data.get('elapsed', '-')}")
        self._append_message("assistant", "\n".join(lines))

        path = data.get("video_path")
        if path and os.path.exists(path):
            self._open_file_location(path)

    # ============================================================
    # ✅ 第二批：音乐生成
    # ============================================================
    def _run_music_generator(self):
        """音乐生成：主题 + 情绪 + 时长。"""
        topic = self._ask_string("音乐生成", "主题：", "星辰大海")
        if not topic:
            return

        emotions = [
            "peaceful   — 宁静",
            "melancholic— 深情",
            "joyful     — 欢乐",
            "epic       — 壮丽",
            "mysterious — 神秘",
            "romantic   — 浪漫",
            "energetic  — 活力",
        ]
        choice = self._ask_choice(
            "音乐生成", "情绪：", emotions, default=emotions[0],
        )
        if not choice:
            return
        emotion = choice.split("—")[0].strip()

        duration = self._ask_int("音乐生成", "时长（秒，10-120）：", 30, 10, 120)
        if duration is None:
            return

        def worker():
            from skills.music_generator.skill import MusicMaestro
            maestro = MusicMaestro()
            return maestro.execute(
                topic=topic, emotion=emotion, duration=duration,
            )

        self._run_skill("🎵 音乐生成", worker, on_success=self._show_audio_result)

    def _show_audio_result(self, data):
        """音频生成结果（音乐/语音共用）：汇总 + 打开文件所在目录。"""
        lines = ["✅ 音频生成完成！", ""]
        audio = data.get("audio_file") or data.get("audio_path")
        lines.append(f"📁 文件：{audio or '-'}")
        if data.get("mode_used"):
            lines.append(f"🎛️ 引擎：{data['mode_used']}")
        if data.get("duration"):
            lines.append(f"⏱️ 时长：{data['duration']}s")
        if data.get("size_kb"):
            lines.append(f"📊 大小：{data['size_kb']:.1f} KB")
        lyrics = data.get("lyrics")
        if isinstance(lyrics, dict) and lyrics.get("title"):
            lines.append(f"📝 歌词：{lyrics['title']}")
        self._append_message("assistant", "\n".join(lines))

        if audio and os.path.exists(audio):
            try:
                import sys
                if sys.platform == "win32":
                    os.startfile(audio)
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", audio])
                else:
                    subprocess.Popen(["xdg-open", audio])
            except Exception as e:
                self._append_message("system", f"⚠️ 自动播放失败：{e}")
                self._open_file_location(audio)

    # ============================================================
    # ✅ 第二批：小说生成
    # ============================================================
    def _run_novel_writer(self):
        """小说生成：标题 + 大纲 + 章数。"""
        title = self._ask_string("小说生成", "标题：", "星际行者")
        if not title:
            return

        outline = self._ask_string("小说生成", "故事大纲（一句话即可）：", "探索未知宇宙，寻找失落文明")
        if not outline:
            return

        genres = ["科幻", "奇幻", "言情", "悬疑", "武侠", "都市"]
        genre = self._ask_choice("小说生成", "类型：", genres, default="科幻")
        if not genre:
            return

        chapters = self._ask_int("小说生成", "章数（1-10）：", 3, 1, 10)
        if chapters is None:
            return

        def worker():
            from skills.novel_writer.skill import NovelWriterOllama
            writer = NovelWriterOllama()
            return writer.execute(
                genre=genre,
                title=title,
                outline=outline,
                characters="主角：一位勇敢的探索者",
                chapter_count=chapters,
                words_per_chapter=600,
                language="zh",
            )

        self._run_skill("📝 小说生成", worker, on_success=self._show_novel_result)

    def _show_novel_result(self, data):
        """小说生成结果：汇总 + 打开文件所在目录。"""
        lines = ["✅ 小说生成完成！", ""]
        lines.append(f"📖 标题：{data.get('title', '-')}")
        lines.append(f"🎭 类型：{data.get('genre', '-')}")
        lines.append(f"📚 章节：{len(data.get('chapters', []))} 章")
        lines.append(f"📝 字数：{data.get('total_words', 0)} 字")
        lines.append(f"⏱️ 耗时：{data.get('generation_time', '-')}")
        lines.append("")
        lines.append(f"📁 文件：{data.get('saved_to', '-')}")
        self._append_message("assistant", "\n".join(lines))

        saved = data.get("saved_to")
        if saved and os.path.exists(saved):
            self._open_file_location(saved)

    # ============================================================
    # ✅ 第二批：语音合成（TTS）
    # ============================================================
    def _run_voice_tts(self):
        """语音合成：多行文本 → mp3。"""
        # 优先取输入框内容，方便"先写好文本，再点菜单"
        default_text = self.input_text.get("1.0", tk.END).strip()
        if default_text:
            self._append_message("system",
                f"💡 检测到输入框有 {len(default_text)} 字，可直接使用（留空则使用输入框内容）")

        text = self._ask_string("语音合成", "要朗读的文本：", default_text[:200])
        if not text:
            return

        # 音色选择
        voices = [
            "zh-CN-XiaoxiaoNeural — 晓晓（女·中文）",
            "zh-CN-YunxiNeural    — 云希（男·中文）",
            "zh-CN-XiaoyiNeural   — 晓伊（女·中文）",
            "en-US-JennyNeural    — Jenny（女·英文）",
            "en-US-GuyNeural      — Guy（男·英文）",
            "ja-JP-NanamiNeural   — Nanami（女·日文）",
        ]
        choice = self._ask_choice(
            "语音合成", "音色：", voices, default=voices[0],
        )
        if not choice:
            return
        voice = choice.split("—")[0].strip()

        # 语速（0.5-2.0），用整数百分比对话框凑合：100 = 1.0 倍速
        speed_pct = self._ask_int("语音合成", "语速（50-200，100 为正常语速）：", 100, 50, 200)
        if speed_pct is None:
            return
        speed = speed_pct / 100.0

        def worker():
            from skills.voice_assistant.skill import VoiceAssistant
            va = VoiceAssistant()
            return va.execute(
                action="tts",
                text=text,
                voice=voice,
                speed=speed,
            )

        self._run_skill("🎙️ 语音合成", worker, on_success=self._show_audio_result)

    # ============================================================
    # ✅ 第三批：多媒体全自动成片
    # ============================================================
    def _run_multimedia(self):
        """多媒体成片：小说 → 场景 → 视频 → 配音 → 音乐 → 字幕 → 合成。"""
        ok = messagebox.askyesno(
            "多媒体成片",
            "将自动执行以下流程：\n\n"
            "  小说生成 → 场景拆分 → 视频片段\n"
            "  → 语音旁白 → 背景音乐 → 字幕 → 最终合成\n\n"
            "预计耗时 5~15 分钟（取决于视频段数和 API 速度），\n"
            "期间请勿关闭窗口。\n\n是否继续？",
            parent=self.root,
        )
        if not ok:
            return

        theme = self._ask_string(
            "多媒体成片", "主题：", "月光下的森林，镜头缓缓推进"
        )
        if not theme:
            return

        self._append_message(
            "system",
            f"🎞️ 主题：{theme}\n"
            f"   流水线：小说 → 视频 → 配音 → 音乐 → 字幕 → 合成\n"
            f"   长任务，可去喝茶 ☕",
        )

        def worker():
            from multimedia.workflow import MultimediaWorkflow
            wf = MultimediaWorkflow(self)   # 传 app 进去，内部会推消息到聊天区
            result = wf.execute(theme)
            # execute 失败会 raise，_run_skill 已捕获
            return {"status": "success", "result": result}

        self._run_skill("🎞️ 多媒体成片", worker, on_success=self._show_multimedia_result)

    def _show_multimedia_result(self, data):
        """多媒体成片结果：汇总 + 打开视频所在目录。"""
        lines = ["✅ 多媒体成片完成！", ""]
        final = data.get("final_video", "-")
        lines.append(f"📁 最终视频：{final}")

        scenes = data.get("scenes") or []
        segments = data.get("video_segments") or []
        if scenes:
            lines.append(f"🎬 场景数：{len(scenes)}")
        if segments:
            lines.append(f"📹 片段数：{len(segments)}")

        novel = data.get("novel") or {}
        if novel.get("title"):
            lines.append(f"📖 小说：{novel['title']}（{novel.get('total_words', 0)} 字）")

        self._append_message("assistant", "\n".join(lines))

        if final and os.path.exists(final):
            self._open_file_location(final)

    # ============================================================
    # ✅ 第三批：一键多平台分发
    # ============================================================
    def _run_multi_publish(self):
        """选目录 → 选平台 → 跑 multi_publish.py。

        内部会调 skills/image_curator + skills/wechat_formatter +
        skills/social_auto_upload，由 multi_publish.py 编排。
        """
        from tkinter import filedialog
        folder = filedialog.askdirectory(
            title="选择图片目录或文章目录",
            parent=self.root,
        )
        if not folder:
            return

        self._append_message(
            "system",
            "💡 平台列表可选：\n"
            "   wechat, xiaohongshu, douyin, kuaishou\n"
            "   或输入 all（全部支持的平台）",
        )
        platforms = self._ask_string(
            "一键多平台分发",
            "平台（逗号分隔，或 all）：",
            "wechat,xiaohongshu",
        )
        if not platforms:
            return

        def worker():
            import sys
            root = Path(__file__).resolve().parents[1]
            script = root / "scripts" / "multi_publish.py"
            if not script.exists():
                return {"status": "error", "error": f"找不到 {script}"}

            cmd = [
                sys.executable, str(script), folder,
                "--platforms", platforms,
            ]
            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True, text=True, encoding="utf-8",
                    cwd=str(root), timeout=1800,  # 30 分钟上限
                )
            except subprocess.TimeoutExpired:
                return {"status": "error", "error": "分发超时（>30 分钟）"}

            ok = proc.returncode == 0
            return {
                "status": "success" if ok else "error",
                "result": {
                    "stdout": (proc.stdout or "")[-4000:],
                    "stderr": (proc.stderr or "")[-1000:],
                    "returncode": proc.returncode,
                },
                "error": (proc.stderr or proc.stdout or "")[-500:] if not ok else None,
            }

        self._run_skill("🚀 多平台分发", worker, on_success=self._show_publish_result)

    def _show_publish_result(self, data):
        """多平台分发结果：提取关键行（✅/❌/📊）展示。"""
        stdout = data.get("stdout", "")
        lines = ["✅ 多平台分发完成！", ""]

        key_lines = []
        for line in stdout.splitlines():
            s = line.strip()
            if not s:
                continue
            if s.startswith(("✅", "❌", "📊", "💡")):
                key_lines.append(s)
            elif "个平台，成功" in s:
                key_lines.append(s)

        if key_lines:
            lines.extend(key_lines[-20:])
        else:
            # 没识别到关键行，展示尾部原始日志
            lines.append("（未识别到结果行，以下为原始输出尾部）")
            lines.append(stdout[-1500:])

        self._append_message("assistant", "\n".join(lines))

    # ============================================================
    # ✅ 第三批：平台登录
    # ============================================================
    def _run_platform_login(self):
        """平台登录：选平台 + 账号名 → 调 SocialAutoUpload.login。

        ⚠️ 二维码打印在**终端**（不是 GUI）。请从命令行启动本程序，
        或在弹出的浏览器窗口中直接扫码。
        """
        platforms = [
            "douyin", "kuaishou", "xiaohongshu", "bilibili",
            "tencent", "weibo", "hupu", "youtube",
            "baijiahao", "alipay",
        ]
        platform = self._ask_choice(
            "平台登录", "选择平台：", platforms, default="xiaohongshu",
        )
        if not platform:
            return

        account = self._ask_string("平台登录", "账号名（自定义标识）：", "default")
        if not account:
            return

        self._append_message(
            "system",
            f"🔑 准备登录 {platform} / {account}\n"
            f"   ⚠️ 二维码会打印在**终端**；若没有终端，请在弹出的浏览器窗口里直接扫码。\n"
            f"   扫码完成后会自动保存 cookie。",
        )

        def worker():
            from skills.social_auto_upload import SocialAutoUpload
            sau = SocialAutoUpload()
            result = sau.login(platform, account=account)
            # login 返回 {"status": "success"/"error", ...}
            return result

        self._run_skill(f"🔑 {platform} 登录", worker)


    # ============================================================
    # 网络广播
    # ============================================================
    def _get_radio_player(self):
        """懒加载 RadioPlayer（保留播放状态）"""
        if not hasattr(self, "_radio_player") or self._radio_player is None:
            from skills.radio_player import RadioPlayer
            self._radio_player = RadioPlayer()
        return self._radio_player

    def _run_radio_player(self):
        """📻 选分类 → 选电台 → 播放"""
        player = self._get_radio_player()

        categories = player.get_categories()
        cat_labels = [player.CATEGORY_NAMES.get(c, c) for c in categories]

        cat_choice = self._ask_choice(
            "📻 网络广播", "选择分类：", cat_labels, default=cat_labels[0],
        )
        if not cat_choice:
            return
        category = categories[cat_labels.index(cat_choice)]

        stations = list(player.get_stations(category).keys())
        if not stations:
            self._append_message("system", f"⚠️ {cat_choice} 下没有电台")
            return

        # 收藏置顶
        favs = [s for s in stations if s in player.favorites]
        others = [s for s in stations if s not in player.favorites]
        ordered = favs + others
        labels = [("⭐ " + s) if s in player.favorites else s for s in ordered]

        choice = self._ask_choice(
            "📻 网络广播",
            f"选择电台（{cat_choice}）：",
            labels,
            default=labels[0],
        )
        if not choice:
            return
        station = choice.replace("⭐ ", "", 1)

        self._append_message("system", f"📻 正在启动：{station} ...")
        ok = player.play(station_name=station, category=category)

        if not ok:
            self._append_message("assistant", f"❌ 播放失败：{station}")
            return

        cur = player.current_station or {}
        kind = player._player_kind or "?"
        hint = {
            "mpv":    "💡 mpv 播放中，支持菜单「停止广播」",
            "ffplay": "💡 ffplay 播放中，支持菜单「停止广播」",
            "vlc":    "💡 VLC 播放中，支持菜单「停止广播」",
            "system": "⚠️ 系统默认程序打开，无法通过菜单停止",
            "browser": "⚠️ 已在浏览器打开，无法通过菜单停止",
        }.get(kind, "")

        self._append_message(
            "assistant",
            f"✅ 播放中：{station}\n"
            f"   播放器：{kind}\n"
            f"   流地址：{cur.get('url', '-')}\n"
            f"   {hint}",
        )

    def _stop_radio(self):
        """⏹️ 停止所有媒体（视频 + 音乐 + 广播）"""
        stopped = False
        for player in (
            getattr(self, "_video_player", None),
            getattr(self, "_music_player", None),
            getattr(self, "_radio_player", None),
        ):
            if player is None:
                continue
            try:
                if player.stop():
                    stopped = True
            except Exception:
                pass

        if stopped:
            self._append_message("assistant", "⏹️ 已停止媒体播放")
        else:
            self._append_message(
                "system",
                "⏹️ 无可停止的播放器（可能是系统程序或浏览器打开，请手动关闭）",
            )
            
    def _replay_media(self):
        """▶️ 重播上一次停止的媒体（视频 > 音乐 > 广播）"""
        # 1) 视频
        if getattr(self, "_video_player", None):
            r = self._video_player.replay()
            if r.get("status") == "playing":
                info = r.get("result") or r
                self._append_message(
                    "assistant",
                    f"▶️ 重播：{info.get('title', '未知')}\n"
                    f"   播放器：{info.get('player', '?')}\n"
                    + (f"   📁 {info['record_path']}" if info.get("record_path") else ""),
                )
                return

        # 2) 音乐
        if getattr(self, "_music_player", None):
            r = self._music_player.replay()
            if r.get("status") == "playing":
                info = r.get("track") or {}
                self._append_message(
                    "assistant",
                    f"▶️ 重播：{info.get('title', '未知')} — {info.get('artist', '')}\n"
                    f"   播放器：{r.get('player', '?')}",
                )
                return

        # 3) 广播
        if getattr(self, "_radio_player", None):
            if self._radio_player.replay():
                s = self._radio_player.current_station or {}
                self._append_message(
                    "assistant",
                    f"▶️ 重播：{s.get('name', '未知')}\n"
                    f"   播放器：{self._radio_player._player_kind or '?'}",
                )
                return

        self._append_message("system", "▶️ 没有可重播的内容")
        
        
    def _show_radio_favorites(self):
        """📋 查看/管理收藏"""
        player = self._get_radio_player()
        favs = player.get_favorites()
        if not favs:
            self._append_message("system", "📋 收藏列表为空")
            return

        lines = [f"📋 收藏电台（{len(favs)} 个）", ""]
        for i, name in enumerate(favs, 1):
            lines.append(f"  {i}. {name}")
        self._append_message("assistant", "\n".join(lines))


    # ============================================================
    # 匿名搜索（DuckDuckGo）
    # ============================================================
    def _get_search_engine(self):
        if not hasattr(self, "_search_engine") or self._search_engine is None:
            from skills.search_engine import SearchEngine
            self._search_engine = SearchEngine()
        return self._search_engine

    def _run_search_images(self):
        self._run_search("images")

    def _run_search_videos(self):
        self._run_search("videos")

    def _run_search_text(self):
        self._run_search("text")

    def _run_search(self, kind: str):
        se = self._get_search_engine()
        label = {"images": "图片", "videos": "视频", "text": "网页"}[kind]

        query = self._ask_string(f"🔍 {label}搜索（匿名）", "关键词：", "")
        if not query:
            return
        query = query.strip()
        if not query:
            return

        limit = self._ask_int(f"🔍 {label}搜索",
                              "结果数量（5-50）：", 20, 5, 50)
        if limit is None:
            return

        self._append_message("system", f"🔍 匿名搜索「{query}」（{label}）...")

        def worker():
            return se.execute(action="search", query=query,
                              kind=kind, limit=limit)

        self._run_skill(
            f"🔍 {label}搜索", worker,
            on_success=lambda d, k=kind: self._show_search_result(d, k),
        )

    def _show_search_result(self, data, kind: str):
        hits = data.get("results", [])
        if not hits:
            self._append_message("assistant", "❌ 没有找到结果")
            return

        # 摘要
        lines = [f"✅ 找到 {len(hits)} 条结果（匿名，未记录）", ""]
        for h in hits[:5]:
            lines.append(f"  • {(h.get('title') or '')[:70]}")
        if len(hits) > 5:
            lines.append(f"  ... 共 {len(hits)} 条")
        self._append_message("assistant", "\n".join(lines))

        labels = []
        for i, h in enumerate(hits, 1):
            title = (h.get("title") or "无标题")[:55]
            if kind == "images":
                w, hh = h.get("width", 0), h.get("height", 0)
                extra = f"  [{w}×{hh}]" if w and hh else ""
            elif kind == "videos":
                extra = f"  [{h.get('duration','')}]" if h.get("duration") else ""
            else:
                extra = ""
            labels.append(f"{i}. {title}{extra}")

        choice = self._ask_choice(
            "🔍 选择一条",
            f"共 {len(hits)} 条，选择：",
            labels,
            default=labels[0],
        )
        if not choice:
            return
        idx = int(choice.split(".", 1)[0]) - 1
        item = hits[idx]

        if kind == "images":
            self._handle_image_item(item, hits)
        elif kind == "videos":
            self._handle_video_item(item)
        else:
            url = item.get("url", "")
            if url:
                webbrowser.open(url)
                self._append_message("assistant", f"🌐 已打开：{url}")

    def _handle_image_item(self, item, all_hits):
        action = self._ask_choice(
            "🖼️ 图片操作",
            f"「{(item.get('title') or '')[:50]}」",
            ["⬇️ 下载这一张",
             "📦 下载前 10 张",
             "🌐 浏览器打开原图",
             "📄 打开来源页面"],
            default="⬇️ 下载这一张",
        )
        if not action:
            return

        se = self._get_search_engine()

        if action.startswith("⬇️"):
            def w():
                return se.execute(
                    action="download_image",
                    url=item["url"],
                    referer=item.get("source") or item.get("page"),
                )
            self._run_skill("⬇️ 下载图片", w,
                            on_success=self._show_download_result)

        elif action.startswith("📦"):
            items = [
                {"url": h["url"], "referer": h.get("source") or h.get("page")}
                for h in all_hits[:10] if h.get("url")
            ]
            if not items:
                self._append_message("system", "⚠️ 没有可下载的图片")
                return
            def w():
                return se.execute(action="download_batch_items", items=items)
            self._run_skill(f"📦 批量下载 {len(items)} 张", w,
                            on_success=self._show_batch_download_result)

        elif action.startswith("🌐"):
            webbrowser.open(item.get("url", ""))
            self._append_message("assistant", "🌐 已打开原图")

        else:
            webbrowser.open(item.get("page", ""))
            self._append_message("assistant", "📄 已打开来源页")

    def _handle_video_item(self, item):
        action = self._ask_choice(
            "🎬 视频操作",
            f"「{(item.get('title') or '')[:50]}」",
            ["▶️ 播放（边播边存）",
             "🌊 流播（不录制）",
             "🌐 浏览器打开"],
            default="▶️ 播放（边播边存）",
        )
        if not action:
            return

        vp = self._get_video_player()
        url = item.get("url", "")
        if not url:
            self._append_message("system", "⚠️ 该结果没有可播放的链接")
            return

        if action.startswith("▶️"):
            self._append_message("system", f"▶️ 播放：{item.get('title', '')}")
            def w():
                return vp.execute(action="play", url=url, record=True)
            self._run_skill("▶️ 播放视频", w,
                            on_success=lambda d: self._show_video_play_result(
                                {"status": "success", "result": d}, item))

        elif action.startswith("🌊"):
            self._append_message("system", f"🌊 流播：{item.get('title', '')}")
            def w():
                return vp.execute(action="play", url=url, record=False)
            self._run_skill("🌊 流播视频", w,
                            on_success=lambda d: self._show_video_play_result(
                                {"status": "success", "result": d}, item))

        else:
            webbrowser.open(url)
            self._append_message("assistant", f"🌐 已打开：{url}")

    def _show_download_result(self, data):
        if data.get("status") != "success":
            self._append_message("assistant",
                f"❌ 下载失败：{data.get('error', '未知')}")
            return
        size_kb = data.get("size", 0) / 1024
        self._append_message("assistant",
            f"✅ 下载完成\n"
            f"📁 {data.get('path', '')}\n"
            f"📊 {size_kb:.1f} KB")

    def _show_batch_download_result(self, data):
        ok = data.get("downloaded", [])
        fail = data.get("failed", [])
        lines = [f"✅ 批量下载完成：{len(ok)} 成功 / {len(fail)} 失败", ""]
        for p in ok[:5]:
            lines.append(f"  📁 {Path(p).name}")
        if len(ok) > 5:
            lines.append(f"  ... 共 {len(ok)} 张")
        if fail:
            lines.append(f"\n⚠️ {len(fail)} 张失败：")
            # 归类错误原因
            reasons = {}
            for f in fail[:20]:
                err = (f.get("error") or "未知")[:50]
                reasons[err] = reasons.get(err, 0) + 1
            for reason, cnt in list(reasons.items())[:3]:
                lines.append(f"   • {reason} × {cnt}")
        self._append_message("assistant", "\n".join(lines))

    # ============================================================
    # 音乐播放器
    # ============================================================
    def _get_music_player(self):
        if not hasattr(self, "_music_player") or self._music_player is None:
            from skills.music_player import MusicPlayer
            self._music_player = MusicPlayer()
        return self._music_player

    def _run_music_player(self):
        """🎵 音乐播放器：搜索 → 播放 / 下载"""
        player = self._get_music_player()

        # 1) 输入搜索词
        query = self._ask_string(
            "🎵 音乐播放器",
            "输入歌名 / 歌手（留空则扫描本地）：",
            "",
        )
        if query is None:
            return

        # 2) 空输入 → 只扫描本地
        if not query.strip():
            def worker_scan():
                return player.execute(action="scan")
            self._run_skill("🎵 扫描本地音乐", worker_scan,
                            on_success=self._show_music_scan_result)
            return

        # 3) 有输入 → 先搜本地，命中就本地，否则在线
        self._append_message("system", f"🔍 搜索：{query} ...")
        local = player.search_local(query)
        if local:
            hits = local
            source = "local"
        else:
            hits = player.search_online(
                query, limit=int(player.config["max_search_results"]),
            )
            source = "online"

        if not hits:
            self._append_message("assistant", f"❌ 未找到：{query}")
            return

        # 4) 结果列表
        labels = []
        for i, t in enumerate(hits, 1):
            title = t.get("title", "未知")
            artist = t.get("artist", "未知")
            labels.append(f"{i}. {title} — {artist}")

        choice = self._ask_choice(
            "🎵 搜索结果",
            f"找到 {len(hits)} 条（{source}）。选择一条：",
            labels,
            default=labels[0],
        )
        if not choice:
            return
        idx = int(choice.split(".", 1)[0]) - 1
        track = hits[idx]

        # 5) 选择动作
        action = self._ask_choice(
            "🎵 音乐播放器",
            f"对「{track.get('title', '')}」：",
            ["▶️ 播放", "⬇️ 下载到本地", "📄 查看详情"],
            default="▶️ 播放",
        )
        if not action:
            return

        if action.startswith("▶️"):
            self._append_message("system",
                f"▶️ 播放：{track.get('title', '')} — {track.get('artist', '')}")
            r = player.execute(action="play", track=track)
            if r.get("status") == "success":
                info = r["result"]
                hint = {
                    "vlc":    "💡 VLC 播放中，可从菜单「⏹️ 停止广播」停止",
                    "mpv":    "💡 mpv 播放中，可从菜单「⏹️ 停止广播」停止",
                    "system": "⚠️ 系统默认程序打开，无法从菜单停止",
                }.get(info.get("player"), "")
                self._append_message("assistant",
                    f"✅ 播放中：{track.get('title', '')}\n"
                    f"   播放器：{info.get('player', '?')}\n"
                    f"   {hint}")
            else:
                self._append_message("assistant",
                    f"❌ 播放失败：{r.get('error', '未知')}")

        elif action.startswith("⬇️"):
            self._append_message("system",
                f"⬇️ 下载中（可能需要 30~60 秒）：{track.get('title', '')}")

            def worker_dl():
                return player.execute(
                    action="download",
                    url=track.get("url") or track.get("path"),
                )
            self._run_skill("⬇️ 下载音乐", worker_dl,
                            on_success=self._show_music_download_result)

        else:
            lines = [f"📄 {track.get('title', '')}", ""]
            for k, lab in [("artist", "🎤 艺术家"),
                           ("album", "💿 专辑"),
                           ("duration", "⏱️ 时长"),
                           ("format", "🎵 格式"),
                           ("url", "🌐 URL"),
                           ("path", "📁 路径")]:
                v = track.get(k)
                if v:
                    lines.append(f"{lab}：{v}")
            self._append_message("assistant", "\n".join(lines))

    def _show_music_scan_result(self, data):
        total = data.get("total", 0)
        tracks = data.get("tracks", [])
        lines = [f"✅ 本地扫描完成：{total} 首", ""]
        for i, t in enumerate(tracks[:15], 1):
            lines.append(f"  {i}. {t.get('title', '')} — {t.get('artist', '')}")
        if total > 15:
            lines.append(f"  ... 共 {total} 首")
        self._append_message("assistant", "\n".join(lines))

    def _show_music_download_result(self, data):
        if data.get("status") != "success":
            self._append_message("assistant",
                f"❌ 下载失败：{data.get('error', '未知')}")
            return
        saved = data.get("saved", "")
        lines = [f"✅ 下载完成：{data.get('title', '')}", ""]
        if saved:
            lines.append(f"📁 {saved}")
        if not data.get("converted"):
            lines.append("💡 未检测到 ffmpeg，已保留原始音频格式")
        self._append_message("assistant", "\n".join(lines))


    # ============================================================
    # 视频播放器
    # ============================================================
    def _get_video_player(self):
        if not hasattr(self, "_video_player") or self._video_player is None:
            from skills.video_player import VideoPlayer
            self._video_player = VideoPlayer()
        return self._video_player

    def _run_video_player(self):
        """📺 视频播放器：搜索 → 播放（边播边存）/ 下载 / 浏览器打开"""
        player = self._get_video_player()

        query = self._ask_string(
            "📺 视频播放器",
            "搜索关键词（如：仙逆 动漫 / 大明王朝 历史剧）：",
            "",
        )
        if query is None:
            return
        query = query.strip()
        if not query:
            return

        source_label = self._ask_choice(
            "📺 视频播放器", "选择来源：",
            ["🇨🇳 B站（bilibili）", "🌐 YouTube", "🌍 全部"],
            default="🇨🇳 B站（bilibili）",
        )
        if not source_label:
            return
        source_map = {
            "🇨🇳 B站（bilibili）": "bilibili",
            "🌐 YouTube":          "youtube",
            "🌍 全部":             "all",
        }
        source = source_map[source_label]

        self._append_message("system", f"🔍 搜索：{query}（{source_label}）...")

        def worker_search():
            return player.execute(action="search", query=query,
                                  source=source, limit=15)

        def show_search(data):
            hits = data.get("results", [])
            if not hits:
                self._append_message("assistant", f"❌ 未找到：{query}")
                return

            labels = []
            for i, t in enumerate(hits, 1):
                dur = f"  [{t['duration_str']}]" if t.get("duration_str") else ""
                labels.append(f"{i}. {t['title']}{dur}")

            choice = self._ask_choice(
                "📺 搜索结果",
                f"找到 {len(hits)} 条，选择一条：",
                labels,
                default=labels[0],
            )
            if not choice:
                return
            idx = int(choice.split(".", 1)[0]) - 1
            track = hits[idx]

            action = self._ask_choice(
                "📺 视频播放器",
                f"对「{track['title']}」：",
                ["▶️ 播放（边播边存）", "🌊 流播（不录制）",
                 "⬇️ 下载到本地", "🌐 浏览器打开"],
                default="▶️ 播放（边播边存）",
            )
            if not action:
                return

            if action.startswith("▶️"):
                self._append_message("system",
                    f"▶️ 启动播放（边播边存）：{track['title']}")
                r = player.execute(action="play", url=track["url"], record=True)
                self._show_video_play_result(r, track)

            elif action.startswith("🌊"):
                self._append_message("system",
                    f"🌊 流播（不录制）：{track['title']}")
                r = player.execute(action="play", url=track["url"], record=False)
                self._show_video_play_result(r, track)

            elif action.startswith("⬇️"):
                self._append_message("system",
                    f"⬇️ 下载中（可能几分钟）：{track['title']}")
                def worker_dl():
                    return player.execute(action="play",
                                          url=track["url"], record=True)
                self._run_skill("⬇️ 下载视频", worker_dl,
                                on_success=lambda d: self._show_video_play_result(
                                    {"status": "success", "result": d}, track))

            else:
                webbrowser.open(track["url"])
                self._append_message("assistant",
                    f"🌐 已在浏览器打开：{track['title']}")

        self._run_skill("📺 搜索视频", worker_search, on_success=show_search)

    def _show_video_play_result(self, r, track):
        """视频播放/下载结果汇总"""
        if r.get("status") != "success":
            self._append_message("assistant",
                f"❌ 失败：{r.get('error', '未知')}")
            return
        info = r.get("result") or {}
        lines = [f"✅ {info.get('message', '已启动')}", ""]
        lines.append(f"🎬 标题：{info.get('title', track.get('title', '-'))}")
        lines.append(f"🎞️ 播放器：{info.get('player', '?')}")
        if info.get("record_path"):
            lines.append(f"📁 保存到：{info['record_path']}")
        lines.append("")
        lines.append("💡 菜单「媒体」→「⏸️ 暂停/继续」控制播放")
        self._append_message("assistant", "\n".join(lines))

    def _toggle_pause_media(self):
        """⏸️ 暂停/继续：遍历所有媒体，谁在播就切谁"""
        toggled = []
        for label, player in (
            ("视频", getattr(self, "_video_player", None)),
            ("音乐", getattr(self, "_music_player", None)),
            ("广播", getattr(self, "_radio_player", None)),
        ):
            if player is None:
                continue
            try:
                st = player.get_status()
            except Exception:
                continue
            if not st.get("is_playing"):
                continue

            if st.get("is_paused"):
                if hasattr(player, "resume") and player.resume():
                    toggled.append(f"▶️ {label}：继续")
            else:
                if hasattr(player, "pause") and player.pause():
                    toggled.append(f"⏸️ {label}：暂停")

        if toggled:
            self._append_message("assistant", "\n".join(toggled))
        else:
            self._append_message("system", "⏸️ 没有正在播放的媒体")
            
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
        
        self.preset_btn = ttk.Button(
            btn_frame,
            text="🎨 用预设",
            command=self._on_send_with_preset
        )
        self.preset_btn.pack(side=tk.TOP, pady=2)        
        
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

    def _on_send_with_preset(self):
        """显式用预设生成（不受输入框内容影响）"""
        if hasattr(self, '_is_processing') and self._is_processing:
            return

        preset = self._get_selected_preset()
        if not preset:
            self._append_message("system", "⚠️ 请先在下拉框选择一个预设")
            return

        user_input = self.input_text.get("1.0", tk.END).strip()
        self.input_text.delete("1.0", tk.END)

        display_text = f"【用预设：{preset}】{user_input or '(默认主体)'}"
        self._append_message("user", display_text)

        self._is_processing = True
        self.send_btn.config(state=tk.DISABLED)
        self.cancel_btn.config(state=tk.NORMAL)
        
        self._last_preset_input = user_input   # ← 加这一行
        
        threading.Thread(
            target=self._preset_thread,
            args=(user_input, preset),
            daemon=True,
        ).start()
        
    def _on_send(self):
        if hasattr(self, '_is_processing') and self._is_processing:
            return

        user_input = self.input_text.get("1.0", tk.END).strip()
        preset = self._get_selected_preset()

        # 两个都空 → 不能发
        if not user_input and not preset:
            return

        self.input_text.delete("1.0", tk.END)

        # 决定走哪条路
        use_preset = self._should_use_preset(user_input, preset)

        if use_preset:
            display_text = user_input if user_input else f"（用预设：{preset}）"
            self._append_message("user", display_text)
            self._is_processing = True
            self.send_btn.config(state=tk.DISABLED)
            self.cancel_btn.config(state=tk.NORMAL)
            threading.Thread(
                target=self._preset_thread,
                args=(user_input, preset),
                daemon=True,
            ).start()
        else:
            self._append_message("user", user_input)
            self._is_processing = True
            self.send_btn.config(state=tk.DISABLED)
            self.cancel_btn.config(state=tk.NORMAL)
            threading.Thread(target=self._process, args=(user_input,), daemon=True).start()


    def _should_use_preset(self, user_input: str, preset: str) -> bool:
        """判断本次发送是否应该使用下拉框里的预设。

        规则：
          1. 下拉框为空 → 不用预设
          2. 输入框为空 + 下拉框有值 → 用预设（触发默认主体）
          3. 输入框有值 + 显式提到"预设/preset/用...风格" → 用预设
          4. 其余情况 → 走正常 intent（忽略下拉框）
        """
        if not preset:
            return False

        # 情况 2：输入框为空，下拉框有预设
        if not user_input:
            return True

        text_lower = user_input.lower()

        # 情况 3：显式要求用预设
        if "预设" in text_lower or "preset" in text_lower:
            return True
        if "用" in text_lower and ("风格" in text_lower or "画" in text_lower):
            return True


        # 情况 4：有具体描述，走正常 intent
        return False

    def _preset_thread(self, text: str, preset: str):
        """预设流程的线程体"""
        self._last_preset_input = text
        try:
            from handlers.preset_handler import PresetHandler
            handler = PresetHandler(self)
            count = self.count_var.get()
            handler.handle({
                "type": "preset_image",
                "original_text": text,
                "params": {"preset": preset, "count": count, "mode": "random"},
            })
        except Exception as e:
            self._append_message("assistant", f"❌ 处理失败: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._is_processing = False
            self.root.after(0, self._reset_ui)
            
    def _process(self, text: str):
        try:
            intent = self.intent_analyzer.analyze(
                text,
                has_image=bool(self.uploaded_images),
                has_multiple=len(self.uploaded_images) >= 2,
                image_count=len(self.uploaded_images),  # ✅ 关键修复
            )
            
            self._append_log(f"🔍 意图: {intent.type}")
            
            if self.llm.is_available() and self.settings.llm_enabled:
                if intent.type in ["text_to_image"]:
                    self._enhance_with_llm(intent)
            
            from handlers import (
                TextToImageHandler, 
                ImageToImageHandler,
                CoupleHandler, 
                MultiPersonHandler,  # ✅ 新增
                ChatHandler, 
                VideoHandler,
            )
            
            handlers = {
                "text_to_image": TextToImageHandler(self),
                "image_to_image": ImageToImageHandler(self),
                "couple": CoupleHandler(self),
                "multi_person": MultiPersonHandler(self),   # ✅ 新增
                "chat": ChatHandler(self),
                "video": VideoHandler(self),  # ✅ 新增
                "preset_image": PresetHandler(self), 
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
        """生成技术热点文章（支持多图配图）"""
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
                    msg += f"📡 热点: {data['hot_topic']}\n"
                    msg += f"🎨 风格: {data['style']}\n"
                    msg += f"📁 Word文档: {data['word_file']}\n"
                    
                    # ✅ 显示所有配图
                    image_files = data.get('image_files', [])
                    if image_files:
                        msg += f"🖼️ 配图 ({len(image_files)} 张):\n"
                        for i, img in enumerate(image_files, 1):
                            msg += f"     {i}. {os.path.basename(img)}\n"
                    else:
                        msg += f"🖼️ 配图: 无\n"
                    
                    self.root.after(0, lambda: self._append_message("assistant", msg))
                    
                    # ✅ 在聊天区展示第一张配图缩略图
                    if image_files:
                        self.root.after(0, lambda: self._append_image(image_files[0], "文章配图"))
                        
                else:
                    self.root.after(0, lambda: self._append_message("system", f"❌ 生成失败: {result.get('error')}"))
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.root.after(0, lambda: self._append_message("system", f"❌ 错误: {str(e)}"))
            finally:
                self.root.after(0, lambda: self.status_var.set("就绪"))
        
        threading.Thread(target=thread_func, daemon=True).start()


    # ============================================================
    # 每日任务：一键生图 → 鉴赏 → 排版 → 推送草稿箱
    # ============================================================
    def _run_daily_task(self):
        """一键执行每日任务。

        参数全部走 GUI：
          - 张数：复用工具栏「张数」spinner（self.count_var）
          - 主题：随机
          - 预设：随机；每张换预设
          - 是否推公众号草稿箱：工具栏「📤 自动推公众号草稿箱」复选框
        """
        # 防止重复触发
        if getattr(self, "_daily_running", False):
            self._append_message("system", "⏳ 每日任务正在执行中，请稍候...")
            return

        count = 6
        theme = "newspaper"
        vary_preset = True
        publish = bool(self.publish_wechat_var.get())

        self._daily_running = True
        self._append_message(
            "system",
            f"📅 开始执行每日任务...\n"
            f"   流程：🎨 生图 → 📝 鉴赏 → 🎨 排版 → 📤 推送草稿箱\n"
            f"   参数：{count} 张 / {theme} 主题 / "
            f"{'换预设' if vary_preset else '固定预设'} / "
            f"{'推送公众号草稿箱' if publish else '不推送公众号'}",
        )
        self.status_var.set("📅 每日任务执行中...")

        # ── 把 daily_pipeline 的日志转发到聊天区 ──
        handler = _DailyLogHandler(self)
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter("%(message)s"))

        plog = logging.getLogger("skills.daily_pipeline")
        plog.setLevel(logging.INFO)
        plog.addHandler(handler)
        plog.propagate = False  # 不往 root 冒泡，避免刷屏

        def thread_func():
            try:
                from skills.daily_pipeline import DailyPipeline

                pipeline = DailyPipeline()
                result = pipeline.execute(
                    topic=None,
                    preset=None,
                    preset_category=None,
                    count=count,
                    theme=theme,
                    vary_preset=vary_preset,
                    publish=publish,
                    open_browser=False,   # GUI 里我们自己打开
                )

                if result.get("status") != "success":
                    err = result.get("error", "未知错误")
                    self.root.after(0, lambda e=err: self._append_message(
                        "assistant", f"❌ 每日任务失败：{e}"
                    ))
                    return

                r = result["result"]

                # ── 汇总消息 ──
                lines = ["✅ 每日任务全部完成！", ""]
                lines.append(f"🎯 主题：{r.get('topic', '-')}")
                lines.append(f"🎨 预设：{r.get('preset', '-')}")
                lines.append(f"📁 图片目录：{r.get('image_dir', '-')}")

                if r.get("md_path"):
                    lines.append(f"📄 文章：{r['md_path']}")
                if r.get("article_dir"):
                    lines.append(f"🎨 排版输出：{r['article_dir']}")
                if r.get("preview_path"):
                    lines.append(f"🌐 浏览器预览：{r['preview_path']}")
                if r.get("clipboard_path"):
                    lines.append(f"📋 富文本：{r['clipboard_path']}")

                if r.get("published"):
                    lines.append("📤 公众号草稿箱：✅ 已推送")
                else:
                    err = r.get("publish_error") or "未推送或推送失败"
                    lines.append(f"📤 公众号草稿箱：❌ {err}")

                msg = "\n".join(lines)
                self.root.after(0, lambda m=msg: self._append_message("assistant", m))

                # ── 在聊天区展示第一张图片 ──
                image_dir = r.get("image_dir")
                if image_dir and os.path.isdir(image_dir):
                    exts = ("*.png", "*.jpg", "*.jpeg", "*.webp")
                    imgs = []
                    for ext in exts:
                        imgs.extend(glob.glob(os.path.join(image_dir, ext)))
                    imgs = sorted(imgs)
                    if imgs:
                        self.root.after(0, lambda p=imgs[0], n=len(imgs): self._append_image(
                            p, f"今日首图（共 {n} 张）"
                        ))

                # ── 打开浏览器预览 ──
                preview = r.get("preview_path")
                if preview and os.path.exists(preview):
                    self.root.after(0, lambda p=preview: webbrowser.open(
                        Path(p).resolve().as_uri()
                    ))

            except Exception as e:
                import traceback
                traceback.print_exc()
                err = str(e)
                self.root.after(0, lambda m=err: self._append_message(
                    "assistant", f"❌ 每日任务异常：{m}"
                ))
            finally:
                # 移除 handler，避免下次重复
                try:
                    plog.removeHandler(handler)
                except Exception:
                    pass
                self._daily_running = False
                self.root.after(0, lambda: self.status_var.set("就绪"))

        threading.Thread(target=thread_func, daemon=True).start()

    def _show_daily_result(self, r):
        """每日任务结果：汇总 + 首图缩略 + 打开浏览器预览。

        参数 r 是 DailyPipeline.execute() 里的 result["result"]。
        """
        lines = ["✅ 每日任务全部完成！", ""]
        lines.append(f"🎯 主题：{r.get('topic', '-')}")
        lines.append(f"🎨 预设：{r.get('preset', '-')}")
        lines.append(f"📁 图片目录：{r.get('image_dir', '-')}")

        if r.get("md_path"):
            lines.append(f"📄 文章：{r['md_path']}")
        if r.get("article_dir"):
            lines.append(f"🎨 排版输出：{r['article_dir']}")
        if r.get("preview_path"):
            lines.append(f"🌐 浏览器预览：{r['preview_path']}")
        if r.get("clipboard_path"):
            lines.append(f"📋 富文本：{r['clipboard_path']}")

        if r.get("published"):
            lines.append("📤 公众号草稿箱：✅ 已推送")
        else:
            err = r.get("publish_error") or "未推送或推送失败"
            lines.append(f"📤 公众号草稿箱：❌ {err}")

        self._append_message("assistant", "\n".join(lines))

        # ── 首图缩略 ──
        image_dir = r.get("image_dir")
        if image_dir and os.path.isdir(image_dir):
            exts = ("*.png", "*.jpg", "*.jpeg", "*.webp")
            imgs = []
            for ext in exts:
                imgs.extend(glob.glob(os.path.join(image_dir, ext)))
            imgs = sorted(imgs)
            if imgs:
                self._append_image(imgs[0], f"今日首图（共 {len(imgs)} 张）")

        # ── 打开浏览器预览 ──
        preview = r.get("preview_path")
        if preview and os.path.exists(preview):
            try:
                webbrowser.open(Path(preview).resolve().as_uri())
            except Exception:
                pass
                

    # ============================================================
    # 每周任务：调 scripts/weekly_tech_task.py
    # ============================================================
    def _run_weekly_tech_task(self):
        """📆 每周任务：技术热点 → 文章 → 排版 → 封面 → 推草稿箱。

        实际逻辑在 scripts/weekly_tech_task.py。
        这里只负责：拼参数 → subprocess → 把关键行展示到聊天区。
        """
        def worker():
            import sys as _sys
            root = Path(__file__).resolve().parents[1]
            script = root / "scripts" / "weekly_tech_task.py"
            if not script.exists():
                return {"status": "error", "error": f"找不到 {script}"}

            cmd = [_sys.executable, str(script)]

            # 不推草稿箱时，把 GUI 上那个复选框透传过去
            if not self.publish_wechat_var.get():
                cmd.append("--no-publish")

            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True, text=True, encoding="utf-8",
                    cwd=str(root), timeout=1800,   # 30 分钟上限
                )
            except subprocess.TimeoutExpired:
                return {"status": "error", "error": "每周任务超时（>30 分钟）"}

            ok = proc.returncode == 0
            return {
                "status": "success" if ok else "error",
                "result": {
                    "stdout": (proc.stdout or "")[-5000:],
                    "stderr": (proc.stderr or "")[-1000:],
                    "returncode": proc.returncode,
                },
                "error": (proc.stderr or proc.stdout or "")[-500:] if not ok else None,
            }

        self._run_skill(
            "🔥 每周技术热点",
            worker,
            on_success=self._show_weekly_tech_result,
        )

    def _show_weekly_tech_result(self, data):
        """从 weekly_tech_task.py 的 stdout 里抽关键行展示。"""
        stdout = data.get("stdout", "")

        # 这些是脚本里固定的收尾行，直接抓
        keep_prefixes = (
            "📄 标题", "📁 Markdown", "🎨 排版目录",
            "🌐 预览页面", "🖼️  封面", "📤 已推送", "⏱️  耗时",
        )
        # 中间过程行，有就带一条
        stage_lines = ("✅ 已推送到公众号草稿箱",
                       "❌ 推送失败", "⚠️  封面生成失败")

        lines = ["✅ 每周技术热点完成！", ""]
        for line in stdout.splitlines():
            s = line.strip()
            if not s:
                continue
            if s.startswith(keep_prefixes) or s.startswith(stage_lines):
                lines.append(s)

        if len(lines) == 2:
            # 没识别到关键行，退而显示尾部日志
            lines.append("（未识别到结果行，以下为原始输出尾部）")
            lines.append(stdout[-2000:])

        self._append_message("assistant", "\n".join(lines))

        # 尝试打开预览
        for line in stdout.splitlines():
            if line.strip().startswith("🌐 预览页面"):
                path = line.split(":", 1)[-1].strip()
                if path and os.path.exists(path):
                    try:
                        webbrowser.open(Path(path).resolve().as_uri())
                    except Exception:
                        pass
                break
                
    # ============================================================
    # 消息添加（文本）
    # ============================================================
    def _append_message(self, role: str, content: str):
        """添加消息到聊天区（线程安全）。

        主线程直接写入；子线程通过 root.after 派发到主线程。
        Tk 的 Text.insert 只能在主线程调用，否则会随机崩。
        """
        def _do():
            self.chat_text.config(state=tk.NORMAL)
            timestamps = {"user": "👤 你", "assistant": "🤖 助手", "system": "📌 系统"}
            prefix = timestamps.get(role, "📝")
            self.chat_text.insert(tk.END, f"{prefix}: {content}\n\n")
            self.chat_text.see(tk.END)
            self.chat_text.config(state=tk.DISABLED)

        if threading.current_thread() is threading.main_thread():
            _do()
        else:
            self.root.after(0, _do)
    
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