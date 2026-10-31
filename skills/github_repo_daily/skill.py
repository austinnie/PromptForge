"""
github_repo_daily - 每天推荐一个 GitHub 仓库 Skill（P2 补齐版）

流程：
  1. 抓 GitHub Trending（HTML 解析）
  2. 从历史中排除已推荐的，挑一个新仓库
  3. GitHub API 拿仓库详情 + README
  4. LLM 写介绍文章（800-1500 字）
  5. LLM 提炼配图 prompt → image_generator 生成插图
  6. 插入插图（均匀分布）
  7. 下载 og:image 做封面
  8. wechat_formatter 排版 + 推送（可选）

历史文件：~/.promptforge/github_daily_history.json
"""

from __future__ import annotations

import json
import logging
import os
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class GitHubRepoDaily:
    name = "github_repo_daily"
    version = "2.0.0"

    TRENDING_URL = "https://github.com/trending"
    GITHUB_API = "https://api.github.com"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._setup_logging()
        self._setup_config()
        self._setup_history()
        self._image_provider = None
        self._init_image_provider()

    # ---------- 初始化 ----------

    def _setup_logging(self):
        level = self.config.get("log_level", "INFO")
        logging.basicConfig(
            level=getattr(logging, level.upper()),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

    def _setup_config(self):
        defaults = {
            "output_dir": "./output/github_daily",
            "wechat_theme": "newspaper",
            "wechat_publish": True,        # 默认开（github daily 就是要发）
            "image_engine": "agnes",
            "max_history": 100,            # 历史保留上限
            "article_words": 1200,
            "illustration_count": 3,
        }
        for k, v in defaults.items():
            self.config.setdefault(k, v)
        Path(self.config["output_dir"]).mkdir(parents=True, exist_ok=True)

    def _setup_history(self):
        history_dir = Path.home() / ".promptforge"
        history_dir.mkdir(parents=True, exist_ok=True)
        self._history_file = history_dir / "github_daily_history.json"

    def _init_image_provider(self):
        try:
            from providers import list_providers, create
            from config.settings import settings

            image_providers = list_providers("image")
            if not image_providers:
                return
            engine = self.config["image_engine"]
            if engine not in image_providers:
                engine = image_providers[0]
            cfg = settings.get_provider_config(engine)
            self._image_provider = create(engine, cfg)
            logger.info(f"✅ 图像引擎: {engine}")
        except Exception as e:
            logger.warning(f"图像引擎初始化失败: {e}")
            self._image_provider = None

    # ---------- 主入口 ----------

    def execute(self, **kwargs) -> Dict[str, Any]:
        """主流程。

        关键 kwargs：
          force_repo:       指定仓库 "owner/repo"（跳过 Trending）
          force_publish:    强制推送公众号（True/False）
          skip_illustration: 不生成配图
          skip_publish:     不推送（只排版）
        """
        start = time.time()

        try:
            force_repo = (kwargs.get("force_repo") or "").strip()
            force_publish = kwargs.get("force_publish")
            skip_illustration = bool(kwargs.get("skip_illustration", False))
            skip_publish = bool(kwargs.get("skip_publish", False))
            words = int(kwargs.get("words", self.config["article_words"]))

            # ---- 阶段 1：选仓库 ----
            repo_info = None
            if force_repo:
                if "/" not in force_repo:
                    return {"status": "error", "error": "force_repo 格式应为 owner/repo"}
                owner, repo = force_repo.split("/", 1)
                logger.info(f"🎯 指定仓库: {owner}/{repo}")
                repo_info = self._get_repo_details(owner.strip(), repo.strip())
                if not repo_info:
                    return {"status": "error", "error": f"无法获取仓库详情: {force_repo}"}
            else:
                logger.info("🔍 抓取 GitHub Trending...")
                repos = self._fetch_trending()
                if not repos:
                    return {"status": "error", "error": "Trending 抓取失败"}

                logger.info(f"   抓到 {len(repos)} 个 Trending 仓库")
                picked = self._pick_repo(repos)
                if not picked:
                    return {
                        "status": "error",
                        "error": "所有 Trending 仓库都已推荐过（清空历史后可重试）",
                    }

                logger.info(f"   选中: {picked['owner']}/{picked['repo']}")
                repo_info = self._get_repo_details(picked["owner"], picked["repo"])
                if not repo_info:
                    return {"status": "error", "error": "无法获取仓库详情"}

            full_name = f"{repo_info['owner']}/{repo_info['repo']}"
            logger.info(f"📦 仓库: {full_name} (⭐{repo_info['stars']} 🍴{repo_info['forks']})")

            # ---- 阶段 2：写文章 ----
            logger.info(f"✍️ LLM 撰写文章（约 {words} 字）...")
            article = self._generate_article(repo_info, words)
            if not article:
                return {"status": "error", "error": "文章生成失败"}

            logger.info(f"✅ 文章完成: {article['title']} ({len(article['body'])} 字)")

            # ---- 阶段 3：配图 ----
            images: List[Path] = []
            if not skip_illustration and self._image_provider:
                logger.info(f"🎨 生成 {self.config['illustration_count']} 张配图...")
                prompts = self._generate_illustration_prompts(
                    repo_info, article["body"], self.config["illustration_count"]
                )
                images = self._generate_illustrations(prompts)
                logger.info(f"✅ 配图: {len(images)} 张")
                if images:
                    article["body"] = self._insert_illustrations(
                        article["body"], images
                    )

            # ---- 阶段 4：保存 ----
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = repo_info["repo"].replace(".", "_")[:30]
            out_dir = Path(self.config["output_dir"]) / f"{ts}_{safe_name}"
            out_dir.mkdir(parents=True, exist_ok=True)

            md_path = out_dir / "article.md"
            md_content = self._compose_markdown(article, repo_info)
            md_path.write_text(md_content, encoding="utf-8")
            logger.info(f"📄 Markdown: {md_path}")

            # ---- 阶段 5：封面 ----
            cover = self._fetch_cover_image(repo_info, out_dir)
            if cover:
                logger.info(f"🖼️ 封面: {cover}")

            result: Dict[str, Any] = {
                "repo": full_name,
                "repo_url": repo_info["url"],
                "repo_stars": repo_info["stars"],
                "repo_forks": repo_info["forks"],
                "article_md": str(md_path),
                "article_title": article["title"],
                "article_words": len(article["body"]),
                "images": [str(p) for p in images],
                "cover": str(cover) if cover else None,
                "output_dir": str(out_dir),
            }

            # ---- 阶段 6：排版 + 推送 ----
            should_publish = (
                self.config["wechat_publish"] if force_publish is None else bool(force_publish)
            )
            should_publish = should_publish and not skip_publish

            wechat_result = self._format_and_publish(
                md_path=md_path,
                cover=cover,
                publish=should_publish,
            )
            if wechat_result:
                result.update({
                    "wechat_preview": wechat_result.get("preview_path"),
                    "wechat_article_dir": wechat_result.get("article_dir"),
                    "published": wechat_result.get("published", False),
                })

            # ---- 记录历史 ----
            self._append_history(full_name)

            elapsed = f"{time.time() - start:.1f}s"
            result["elapsed"] = elapsed
            logger.info(f"🎉 完成: {full_name} ({elapsed})")

            return {
                "status": "success",
                "result": result,
                "metadata": {"skill": self.name, "version": self.version},
            }

        except Exception as e:
            logger.exception("github_repo_daily 失败")
            return {"status": "error", "error": str(e)}

    # ---------- 阶段 1：抓 Trending ----------

    def _fetch_trending(self) -> List[Dict[str, str]]:
        """抓取 GitHub Trending 页面（HTML 解析）。"""
        try:
            r = requests.get(
                self.TRENDING_URL,
                timeout=15,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
                    ),
                    "Accept": "text/html",
                },
            )
            r.raise_for_status()
        except Exception as e:
            logger.error(f"HTTP 抓取失败: {e}")
            return []

        html = r.text
        repos: List[Dict[str, str]] = []

        # 每条 trending 仓库在 <article class="Box-row"> 里
        # 找 <h2 ...><a href="/owner/repo" ...>owner / repo</a></h2>
        article_pattern = re.compile(
            r'<article[^>]*class="[^"]*Box-row[^"]*"[^>]*>(.*?)</article>',
            re.DOTALL,
        )
        repo_pattern = re.compile(
            r'<h2[^>]*>.*?<a[^>]*href="/([^/"]+)/([^/"]+)"',
            re.DOTALL,
        )
        desc_pattern = re.compile(
            r'<p[^>]*class="[^"]*color-fg-muted[^"]*"[^>]*>(.*?)</p>',
            re.DOTALL,
        )
        star_pattern = re.compile(
            r'<span[^>]*class="[^"]*d-inline-block[^"]*float-sm-right[^"]*"[^>]*>.*?</span>',
            re.DOTALL,
        )

        for art in article_pattern.finditer(html):
            art_html = art.group(1)
            repo_m = repo_pattern.search(art_html)
            if not repo_m:
                continue
            owner, repo = repo_m.group(1), repo_m.group(2)

            desc_m = desc_pattern.search(art_html)
            desc = desc_m.group(1).strip() if desc_m else ""
            desc = re.sub(r"<[^>]+>", "", desc).strip()[:300]

            repos.append({
                "owner": owner,
                "repo": repo,
                "full_name": f"{owner}/{repo}",
                "description": desc,
            })

        return repos

    # ---------- 阶段 1.5：选未推荐过的 ----------

    def _pick_repo(self, repos: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
        """挑一个历史里没有的仓库。"""
        history = set(self._load_history())
        # 优先挑未推荐过的
        fresh = [r for r in repos if r["full_name"] not in history]
        if not fresh:
            return None
        # 随机从 fresh 里挑（避免每次都是同一个）
        return random.choice(fresh[:15])   # 只在前 15 个里挑，热度高

    def _load_history(self) -> List[str]:
        if not self._history_file.exists():
            return []
        try:
            return json.loads(self._history_file.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _append_history(self, full_name: str) -> None:
        history = self._load_history()
        history.append(full_name)
        # 只保留最近 max_history 条
        history = history[-self.config["max_history"]:]
        try:
            self._history_file.write_text(
                json.dumps(history, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"保存历史失败: {e}")

    # ---------- 阶段 2：拿仓库详情 ----------

    def _get_repo_details(self, owner: str, repo: str) -> Optional[Dict[str, Any]]:
        """GitHub API 拿详情 + README。"""
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "PromptForge/1.0",
        }
        token = os.getenv("GITHUB_TOKEN", "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        # 1. 仓库元数据
        try:
            r = requests.get(
                f"{self.GITHUB_API}/repos/{owner}/{repo}",
                headers=headers,
                timeout=15,
            )
            r.raise_for_status()
            meta = r.json()
        except Exception as e:
            logger.warning(f"获取仓库元数据失败: {e}")
            return None

        # 2. README（可能 404，忽略）
        readme = ""
        try:
            r2 = requests.get(
                f"{self.GITHUB_API}/repos/{owner}/{repo}/readme",
                headers={**headers, "Accept": "application/vnd.github.raw+json"},
                timeout=15,
            )
            if r2.status_code == 200:
                readme = r2.text
        except Exception as e:
            logger.debug(f"README 获取失败（忽略）: {e}")

        # README 太长截断（LLM token 限制）
        if len(readme) > 6000:
            readme = readme[:6000] + "\n\n...(truncated)"

        # 3. 语言统计
        languages = {}
        try:
            r3 = requests.get(
                f"{self.GITHUB_API}/repos/{owner}/{repo}/languages",
                headers=headers,
                timeout=15,
            )
            if r3.status_code == 200:
                languages = r3.json()
        except Exception:
            pass

        return {
            "owner": owner,
            "repo": repo,
            "full_name": meta.get("full_name", f"{owner}/{repo}"),
            "description": meta.get("description", "") or "",
            "url": meta.get("html_url", ""),
            "stars": meta.get("stargazers_count", 0),
            "forks": meta.get("forks_count", 0),
            "language": meta.get("language", ""),
            "languages": languages,
            "topics": meta.get("topics", []),
            "license": (meta.get("license") or {}).get("name", ""),
            "homepage": meta.get("homepage", ""),
            "created_at": meta.get("created_at", ""),
            "updated_at": meta.get("updated_at", ""),
            "readme": readme,
        }

    # ---------- 阶段 3：写文章 ----------

    def _generate_article(
        self, repo_info: Dict[str, Any], words: int,
    ) -> Optional[Dict[str, Any]]:
        """用 LLM 写仓库介绍文章。"""
        from core.llm_client import get_default_client

        readme_snippet = repo_info["readme"][:4000]
        lang_summary = ", ".join(
            f"{k}({v})" for k, v in
            sorted(repo_info["languages"].items(), key=lambda x: -x[1])[:5]
        )
        topics = ", ".join(repo_info["topics"]) if repo_info["topics"] else "(无)"

        prompt = f"""你是资深技术编辑，请为下面这个 GitHub 仓库写一篇介绍文章。

【仓库信息】
名称：{repo_info['full_name']}
描述：{repo_info['description']}
Star：{repo_info['stars']}
Fork：{repo_info['forks']}
主要语言：{repo_info['language']}
语言分布：{lang_summary}
Topics：{topics}
License：{repo_info['license']}
项目主页：{repo_info['homepage']}

【README 摘要】
{readme_snippet}

【写作要求】
1. 字数：约 {words} 字
2. 风格：专业但易懂，面向中文技术读者
3. 结构：
   - 吸引人的标题（30 字以内，突出项目亮点）
   - 导语（100 字，为什么这个项目值得关注）
   - ## 是什么（150-200 字，介绍项目定位）
   - ## 能解决什么问题（200-300 字，核心价值）
   - ## 核心特性（分点，每点 50-80 字，3-5 个特性）
   - ## 上手门槛（100 字，依赖/安装/学习曲线）
   - ## 适用场景（150 字，谁该用它）
   - ## 结语（80 字，展望或建议）
4. 用 Markdown 格式（标题 # / ##，代码用 ` `）
5. 不要编造 README 里没有的事实；不确定的地方模糊表述

【输出格式】
直接输出完整的 Markdown 文章（第一行是 # 标题）。
不要写"以下是文章"之类的话。"""

        try:
            llm = get_default_client(temperature=0.75, max_tokens=4096, timeout=180)
            raw = llm.generate(prompt)
        except Exception as e:
            logger.error(f"LLM 生成失败: {e}")
            return None

        if not raw or len(raw) < 300:
            logger.warning("LLM 返回内容过短")
            return None

        # 解析标题
        title = ""
        body = raw.strip()
        m = re.search(r"^#\s+(.+?)$", body, re.MULTILINE)
        if m:
            title = m.group(1).strip()
            body = body[m.end():].lstrip()

        if not title:
            title = f"{repo_info['repo']}：值得关注的开源项目"

        return {"title": title, "body": body}

    # ---------- 阶段 4：配图 ----------

    def _generate_illustration_prompts(
        self, repo_info: Dict[str, Any], article: str, count: int,
    ) -> List[str]:
        """让 LLM 从文章里提炼 N 个英文画图 prompt。"""
        from core.llm_client import get_default_client

        prompt = f"""你是 AI 画图提示词专家。下面这篇文章介绍 GitHub 仓库 {repo_info['full_name']}。

请提炼 {count} 个适合配图的英文 prompt，每个描述一个抽象概念的视觉表达。

要求：
1. 风格统一：modern tech illustration, clean vector style, blue and purple gradient, minimalist
2. 每个 prompt 描述不同方面（架构/流程/使用场景/概念）
3. 输出格式：每行一个 prompt，不要编号，不要解释，不要 markdown

文章：
{article[:2500]}

直接输出 {count} 行英文 prompt："""

        try:
            llm = get_default_client(temperature=0.7, max_tokens=400, timeout=60)
            raw = llm.generate(prompt) or ""
            lines = [l.strip() for l in raw.splitlines() if l.strip()]
            prompts = [l for l in lines if len(l) > 20][:count]

            suffix = ", modern tech illustration, clean vector, minimalist, blue purple gradient"
            return [p + suffix for p in prompts] if prompts else [
                f"abstract concept art for {repo_info['repo']} open source project" + suffix
            ]
        except Exception as e:
            logger.warning(f"prompt 生成失败: {e}")
            return [
                f"abstract tech illustration for {repo_info['repo']} project" +
                ", modern, minimal, blue purple gradient"
            ]

    def _generate_illustrations(self, prompts: List[str]) -> List[Path]:
        """用 image_provider 生成配图。"""
        if not prompts or not self._image_provider:
            return []

        from providers.base import ImageRequest

        images: List[Path] = []
        for i, p in enumerate(prompts):
            try:
                logger.info(f"  🎨 [{i+1}/{len(prompts)}] {p[:60]}...")
                req = ImageRequest(
                    prompt=p,
                    width=1024,
                    height=576,       # 16:9
                    steps=25,
                    cfg=7.5,
                )
                img = self._image_provider.text_to_image(req)
                # 临时存到 output 里
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                out_dir = Path(self.config["output_dir"]) / f"_imgs_{ts}"
                out_dir.mkdir(parents=True, exist_ok=True)
                p_path = out_dir / f"illustration_{i+1:02d}.png"
                img.save(p_path)
                images.append(p_path)
            except Exception as e:
                logger.warning(f"  ⚠️ 配图 {i+1} 失败: {e}")
        return images

    def _insert_illustrations(self, article: str, images: List[Path]) -> str:
        """把图片均匀插入到段落之间。"""
        if not images:
            return article

        lines = article.split("\n")
        # 找所有二级标题行（## xxx）
        h2_indices = [i for i, l in enumerate(lines) if l.startswith("## ")]
        if not h2_indices:
            # 没有 h2，追加到末尾
            tail = "\n\n" + "\n\n".join(f"![配图]({p.as_posix()})" for p in images)
            return article + tail

        # 均匀插入到 h2 之间（每个 h2 之前插一张图，从第 2 个开始）
        # 例：3 张图 + 4 个 h2 → 在第 2、3、4 个 h2 之前各插一张
        insert_points = h2_indices[1:1 + len(images)]

        # 从后往前插（避免索引错位）
        for img, idx in zip(reversed(images), reversed(insert_points)):
            lines.insert(idx, f"![配图]({img.as_posix()})")
            lines.insert(idx, "")

        return "\n".join(lines)

    # ---------- 阶段 5：封面 ----------

    def _fetch_cover_image(
        self, repo_info: Dict[str, Any], save_dir: Path,
    ) -> Optional[Path]:
        """尝试从仓库页拿 og:image 做封面。"""
        try:
            r = requests.get(
                repo_info["url"],
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            r.raise_for_status()
            # 找 <meta property="og:image" content="...">
            m = re.search(
                r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"',
                r.text,
            )
            if not m:
                m = re.search(
                    r'<meta[^>]+content="([^"]+)"[^>]+property="og:image"',
                    r.text,
                )
            if not m:
                return None

            img_url = m.group(1)
            # 下载
            r2 = requests.get(img_url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            r2.raise_for_status()

            ext = ".png" if "png" in img_url.lower() else ".jpg"
            cover_path = save_dir / f"cover{ext}"
            cover_path.write_bytes(r2.content)
            return cover_path
        except Exception as e:
            logger.debug(f"封面获取失败: {e}")
            return None

    # ---------- 阶段 6：排版 + 推送 ----------

    def _format_and_publish(
        self,
        md_path: Path,
        cover: Optional[Path],
        publish: bool,
    ) -> Optional[Dict[str, Any]]:
        """调用 wechat_formatter skill。"""
        try:
            from skills.registry import get_meta, import_skill_class
            meta = get_meta("wechat_formatter")
            if not meta:
                logger.warning("wechat_formatter 未注册，跳过排版")
                return None

            WechatFormatter = import_skill_class(meta)
            fmt = WechatFormatter({
                "log_level": "INFO",
                "output_dir": str(Path(self.config["output_dir"]) / "wechat"),
                "auto_open_browser": False,
            })

            # 排版
            r = fmt.format(
                md_path=str(md_path),
                theme=self.config["wechat_theme"],
                gallery=False,
                enhance=False,
                open=False,
            )
            if r.get("status") != "success":
                logger.warning(f"排版失败: {r.get('error')}")
                return None

            result = r.get("result", {})

            # 推送（可选）
            if publish:
                article_dir = result.get("article_dir")
                if article_dir:
                    pub = fmt.publish(
                        article_dir=article_dir,
                        cover_path=str(cover) if cover else None,
                        dry_run=False,
                    )
                    result["published"] = pub.get("status") == "success"
                    if not result["published"]:
                        logger.warning(f"推送失败: {pub.get('error')}")
                else:
                    result["published"] = False
            else:
                result["published"] = False

            return result
        except Exception as e:
            logger.exception(f"wechat 阶段异常: {e}")
            return None

    # ---------- Markdown 合成 ----------

    def _compose_markdown(
        self, article: Dict[str, Any], repo_info: Dict[str, Any],
    ) -> str:
        """最终 Markdown：标题 + 元信息卡片 + 正文 + 页脚。"""
        lines = [
            f"# {article['title']}",
            "",
            f"> 📦 **[{repo_info['full_name']}]({repo_info['url']})**",
            f"> ⭐ {repo_info['stars']} · 🍴 {repo_info['forks']} · "
            f"🔤 {repo_info['language'] or 'N/A'} · "
            f"📄 {repo_info['license'] or 'N/A'}",
        ]

        if repo_info["description"]:
            lines.append(f"> 💡 {repo_info['description']}")

        if repo_info["topics"]:
            topics_str = " ".join(f"`{t}`" for t in repo_info["topics"][:6])
            lines.append(f"> 🏷️ {topics_str}")

        lines.extend(["", "---", "", article["body"], ""])

        # 页脚
        lines.extend([
            "",
            "---",
            "",
            f"*本文由 PromptForge 自动生成 · "
            f"{datetime.now().strftime('%Y-%m-%d')}*",
        ])

        return "\n".join(lines)

    # ---------- 展示 ----------

    def get_name(self) -> str:
        return "GitHubRepoDaily"

    def __repr__(self):
        return "<GitHubRepoDaily>"