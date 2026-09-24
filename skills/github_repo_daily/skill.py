"""
github_repo_daily - 每天推荐一个 GitHub 仓库并生成介绍文章发布到微信公众号

流程：
  1. 抓取 GitHub Trending 每日榜单
  2. 挑选一个未推荐过的仓库
  3. 调用 GitHub API 获取仓库详情与 README
  4. 使用 LLMClient 生成介绍文章（Agnes / Ollama，由 LLM_BACKENDS 决定）
  5. 调用 wechat_formatter 排版并发布到公众号草稿箱
"""

import os
import re
import json
import time
import base64
import random
import shutil
import logging
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class GitHubRepoDaily:
    name = "github_repo_daily"
    version = "1.1.0"   # ✅ 版本 +0.1，标记走 LLMClient

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._setup_logging()
        self._setup_config()

    def _setup_logging(self):
        level = self.config.get("log_level", "INFO")
        logging.basicConfig(
            level=getattr(logging, level.upper()),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

    def _setup_config(self):
        defaults = {
            "output_dir": str(PROJECT_ROOT / "output" / "github_repo_daily"),
            "history_file": "history.json",
            "github_token": os.environ.get("GITHUB_TOKEN", ""),
            "wechat_theme": "newspaper",
            "wechat_publish": True,
            "max_trending": 25,
            "log_level": "INFO",

            # 插图与文末二维码
            "illustration_count": 3,
            "illustration_engine": "agnes",
            "illustration_width": 1024,
            "illustration_height": 1024,
            "footer_image": "assets/qr/公众号结束处.png",
            "footer_alt": "关注公众号",

            # ✅ 不再声明 llm_backends / llm_timeout / llm_temperature /
            #    llm_max_tokens / ollama_url / ollama_model —— 全部交给
            #    config.settings + core.llm_client 统一管理。
            #    如需 GitHub 日报走独立后端，在 .env 里配
            #    GH_DAILY_LLM_BACKENDS=xxx,yyy，由 LLMClient 读取。
        }
        for k, v in defaults.items():
            self.config.setdefault(k, v)
        Path(self.config["output_dir"]).mkdir(parents=True, exist_ok=True)

    # ---------- LLM 统一入口 ----------

    def _get_llm_backends(self) -> Optional[List[str]]:
        """读取 GitHub 日报专属后端。

        优先级：
          1. config["llm_backends"]（构造时显式传入）
          2. settings.gh_daily_llm_backends（.env 里 GH_DAILY_LLM_BACKENDS）
          3. None（让 LLMClient 用全局 LLM_BACKENDS）
        """
        if self.config.get("llm_backends"):
            return list(self.config["llm_backends"])
        try:
            from config.settings import settings
            gh_backends = getattr(settings, "gh_daily_llm_backends", None)
            if gh_backends:
                return list(gh_backends)
        except Exception:
            pass
        return None

    def _llm_generate(
        self,
        prompt: str,
        *,
        temperature: float = None,
        max_tokens: int = None,
        timeout: int = None,
    ) -> str:
        """统一的 LLM 调用入口。

        走 core.llm_client.LLMClient，后端顺序由下列配置决定（就近优先）：
          1. 构造 config["llm_backends"]
          2. .env 的 GH_DAILY_LLM_BACKENDS
          3. .env 的 LLM_BACKENDS（全局）

        全部后端失败返回 ""（strict=False，不抛异常）。
        """
        from core.llm_client import get_default_client

        llm = get_default_client(
            backends=self._get_llm_backends(),
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            strict=False,
        )
        text = llm.generate(prompt)

        if text:
            logger.info(f"✅ LLM 返回 {len(text)} 字")
        else:
            logger.error("❌ 所有 LLM 后端均失败")
        return text

    # ---------- 历史记录 ----------

    def _load_history(self) -> List[str]:
        hist_file = Path(self.config["output_dir"]) / self.config["history_file"]
        if hist_file.exists():
            try:
                return json.loads(hist_file.read_text(encoding="utf-8"))
            except Exception:
                return []
        return []

    def _save_history(self, history: List[str]):
        hist_file = Path(self.config["output_dir"]) / self.config["history_file"]
        hist_file.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------- GitHub 相关 ----------

    def _github_headers(self):
        headers = {"Accept": "application/vnd.github.v3+json"}
        token = self.config.get("github_token")
        if token:
            headers["Authorization"] = f"token {token}"
        return headers

    def fetch_trending_repos(self) -> List[Dict[str, str]]:
        """抓取 GitHub Trending 每日榜单。

        策略：
          1. 优先用 article.Box-row 切块（GitHub 多年来结构稳定）
          2. 兜底用宽松正则直接抓 /owner/repo 链接
          3. 再失败用内置候选仓库
        """
        url = "https://github.com/trending?since=daily"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }

        html = ""
        try:
            resp = requests.get(url, headers=headers, timeout=20)
            resp.raise_for_status()
            html = resp.text
            logger.info(f"Trending 页面大小: {len(html)} 字符")
        except Exception as e:
            logger.error(f"抓取 trending 页面失败: {e}")

        repos: List[Dict[str, str]] = []
        seen = set()

        # ── 方案 1：按 article.Box-row 切块（主选）──
        if html:
            blocks = re.findall(
                r'<article[^>]*class="[^"]*Box-row[^"]*"[^>]*>(.*?)</article>',
                html,
                re.DOTALL,
            )
            logger.info(f"匹配到 {len(blocks)} 个 Box-row 块")

            for block in blocks:
                m = re.search(r'<a\s+[^>]*href="/([^/"\s]+)/([^/"\s]+)"', block)
                if not m:
                    continue
                owner, repo = m.group(1), m.group(2)
                if owner in ("trending", "topics", "collections", "sponsors",
                             "login", "signup", "features", "marketplace"):
                    continue
                key = f"{owner}/{repo}"
                if key in seen:
                    continue
                seen.add(key)
                repos.append({
                    "owner": owner,
                    "repo": repo,
                    "url": f"https://github.com/{key}",
                })
                if len(repos) >= self.config["max_trending"]:
                    break

        # ── 方案 2：Box-row 抓不到，兜底用宽松正则 ──
        if not repos and html:
            logger.warning("Box-row 解析为空，改用宽松正则兜底")
            pattern = r'<h2[^>]*>\s*<a\s+[^>]*href="/([^/"\s]+)/([^/"\s]+)"'
            matches = re.findall(pattern, html, re.DOTALL)
            for owner, repo in matches[: self.config["max_trending"]]:
                if owner in ("trending", "topics", "collections"):
                    continue
                key = f"{owner}/{repo}"
                if key in seen:
                    continue
                seen.add(key)
                repos.append({
                    "owner": owner,
                    "repo": repo,
                    "url": f"https://github.com/{key}",
                })

        # ── 方案 3：全都失败 → 内置候选（保底不崩）──
        if not repos:
            logger.warning("Trending 抓取失败，使用内置候选仓库")
            repos = [
                {"owner": "ollama", "repo": "ollama",
                 "url": "https://github.com/ollama/ollama"},
                {"owner": "microsoft", "repo": "vscode",
                 "url": "https://github.com/microsoft/vscode"},
                {"owner": "torvalds", "repo": "linux",
                 "url": "https://github.com/torvalds/linux"},
                {"owner": "huggingface", "repo": "transformers",
                 "url": "https://github.com/huggingface/transformers"},
                {"owner": "comfyanonymous", "repo": "ComfyUI",
                 "url": "https://github.com/comfyanonymous/ComfyUI"},
            ]

        logger.info(f"获取到 {len(repos)} 个 trending 仓库")
        return repos

    def pick_repo(self, repos: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
        """挑选一个未推荐过的仓库"""
        history = self._load_history()
        random.shuffle(repos)
        for r in repos:
            key = f"{r['owner']}/{r['repo']}"
            if key not in history:
                return r
        return random.choice(repos) if repos else None

    def get_repo_details(self, owner: str, repo: str) -> Dict[str, Any]:
        """获取仓库详情与 README"""
        api_base = "https://api.github.com"
        headers = self._github_headers()
        details = {}
        try:
            resp = requests.get(f"{api_base}/repos/{owner}/{repo}", headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                details.update({
                    "full_name": data.get("full_name"),
                    "description": data.get("description"),
                    "stars": data.get("stargazers_count"),
                    "forks": data.get("forks_count"),
                    "language": data.get("language"),
                    "topics": data.get("topics", []),
                    "html_url": data.get("html_url"),
                    "homepage": data.get("homepage"),
                })
            resp = requests.get(f"{api_base}/repos/{owner}/{repo}/readme", headers=headers, timeout=10)
            if resp.status_code == 200:
                readme_data = resp.json()
                content = readme_data.get("content", "")
                readme_text = base64.b64decode(content).decode("utf-8", errors="replace")
                details["readme"] = readme_text
            else:
                details["readme"] = ""
        except Exception as e:
            logger.error(f"获取仓库详情失败: {e}")
        return details

    # ---------- 文章生成 ----------

    def generate_article(self, repo_info: Dict[str, Any]) -> str:
        """生成介绍文章：走 LLMClient（Agnes / Ollama 由 LLM_BACKENDS 决定）。"""
        full_name = repo_info.get("full_name", "未知仓库")
        description = repo_info.get("description", "")
        stars = repo_info.get("stars", 0)
        language = repo_info.get("language", "")
        topics = ", ".join(repo_info.get("topics", []))
        readme = repo_info.get("readme", "")[:4000]

        prompt = f"""你是一个技术博主，请根据以下 GitHub 仓库信息，写一篇介绍文章。
要求：
1. 标题吸引人，包含仓库名。
2. 介绍仓库的主要功能、用途、亮点。
3. 语言通俗易懂，适合公众号读者。
4. 可以包含使用场景、技术栈等。
5. 文章长度 800-1200 字。
6. 输出 Markdown 格式，包含标题。
7. 只输出文章正文，不要任何前言/解释/代码块围栏。

仓库名称：{full_name}
仓库描述：{description}
Star 数：{stars}
主要语言：{language}
标签：{topics}

README 内容（节选）：
{readme}

请开始写文章："""

        article = self._llm_generate(prompt, temperature=0.7, max_tokens=2048)

        if article:
            article = re.sub(r"^```(?:markdown|md)?\s*\n", "", article)
            article = re.sub(r"\n```\s*$", "", article)
            return article.strip()

        logger.warning("⚠️ 所有 LLM 均失败，使用基础模板")
        return f"""# {full_name}

{description}

- Star: {stars}
- 语言: {language}
- 标签: {topics}

更多详情请访问：{repo_info.get('html_url', '')}
"""

    # ---------- 插图 prompt 提炼 ----------

    def _generate_illustration_prompts(
        self,
        repo_info: Dict[str, Any],
        article: str,
        count: int = 3,
    ) -> List[str]:
        """让 LLM 从文章里提炼 N 个适合 AI 画图的英文 prompt。"""
        if count <= 0:
            logger.info("配图数量为 0，跳过 prompt 提炼")
            return []

        full_name = repo_info.get("full_name", "")
        description = repo_info.get("description", "")
        language = repo_info.get("language", "")
        topics = ", ".join(repo_info.get("topics", []))
        article_excerpt = article[:800].replace("\n", " ")

        prompt = f"""You are an illustrator. Based on the following GitHub repository, write {count} English prompts for AI image generation (Midjourney / DALL-E style).

Requirements:
1. Each prompt <= 30 English words
2. Describe a CONCRETE visual scene — do NOT include code, UI, text, logos
3. Theme should relate to the repo's purpose, tech, or use case
4. Style: techy, modern, clean, cinematic
5. Output ONLY a JSON array, e.g.: ["prompt 1", "prompt 2", "prompt 3"]

Repo: {full_name}
Description: {description}
Language: {language}
Topics: {topics}
Article excerpt: {article_excerpt}

JSON array:"""

        raw = self._llm_generate(prompt, temperature=0.8, max_tokens=500)

        if raw:
            m = re.search(r"\[.*\]", raw, re.DOTALL)
            if m:
                try:
                    arr = json.loads(m.group())
                    arr = [str(x).strip() for x in arr if str(x).strip()]
                    if arr:
                        picked = arr[:count]
                        logger.info(f"✅ 提炼出 {len(picked)} 个配图 prompt（原始 {len(arr)}）")
                        return picked
                except json.JSONDecodeError as e:
                    logger.warning(f"⚠️ 配图 prompt JSON 解析失败: {e}")

        logger.warning("使用兜底配图 prompt")
        return [
            f"abstract tech illustration inspired by {full_name}, "
            f"modern minimal, cinematic lighting, digital art"
        ]

    # ---------- 插图生成 ----------

    def _generate_illustrations(
        self,
        prompts: List[str],
        save_dir: Path,
    ) -> List[Path]:
        """用指定引擎生成插图，返回本地路径列表。

        引擎：默认 agnes（免费），也支持 pollinations / siliconflow 等。
        失败时返回已成功的部分（不中断主流程）。
        """
        if not prompts:
            return []

        save_dir.mkdir(parents=True, exist_ok=True)
        paths: List[Path] = []

        try:
            from api_engines import create_engine
            from config.settings import settings

            engine_name = self.config.get("illustration_engine", "agnes")

            if engine_name == "agnes":
                engine_cfg = {
                    "AGNES_API_KEY": settings.agnes_api_key,
                    "AGNES_BASE_URL": settings.agnes_base_url,
                    "AGNES_IMAGE_MODEL": settings.agnes_image_model,
                }
            elif engine_name == "pollinations":
                engine_cfg = {"POLLINATIONS_MODEL": settings.pollinations_model}
            elif engine_name == "siliconflow":
                engine_cfg = {
                    "SILICONFLOW_API_KEY": settings.siliconflow_api_key,
                    "SILICONFLOW_MODEL": settings.siliconflow_model,
                }
            else:
                logger.warning(f"不支持的插图引擎: {engine_name}")
                return []

            engine = create_engine(engine_name, engine_cfg)
            if engine is None:
                logger.warning(f"插图引擎初始化失败: {engine_name}")
                return []

            w = self.config["illustration_width"]
            h = self.config["illustration_height"]

            for i, prompt in enumerate(prompts, 1):
                try:
                    logger.info(f"🎨 生成插图 [{i}/{len(prompts)}]: {prompt[:60]}...")
                    img = engine.generate_single(
                        prompt=prompt,
                        negative="text, watermark, signature, ui, code, blurry",
                        width=w,
                        height=h,
                        steps=20,
                        cfg=7.5,
                    )
                    path = save_dir / f"illustration_{i:02d}.png"
                    img.save(path, "PNG", optimize=True)
                    paths.append(path)
                    logger.info(f"✅ 插图已保存: {path.name}")
                    time.sleep(1)
                except Exception as e:
                    logger.warning(f"⚠️ 插图 {i} 生成失败: {e}")
                    continue

        except Exception as e:
            logger.error(f"❌ 插图生成失败: {e}")
            import traceback
            traceback.print_exc()

        return paths

    # ---------- 插图插入 ----------

    def _insert_illustrations(
        self,
        article: str,
        image_paths: List[Path],
    ) -> str:
        """把插图按"段落间均匀分布"的规则插入到 Markdown 文章里。"""
        if not image_paths:
            return article

        lines = article.split("\n")
        result: List[str] = []
        img_idx = 0
        n_images = len(image_paths)

        head_seen = False

        for line in lines:
            if (not head_seen) and line.startswith("# ") and not line.startswith("## "):
                result.append(line)
                if img_idx < n_images:
                    result.append("")
                    result.append(f"![illustration](assets/{image_paths[img_idx].name})")
                    result.append("")
                    img_idx += 1
                head_seen = True
                continue

            if line.startswith("## ") and img_idx < n_images:
                result.append("")
                result.append(f"![illustration](assets/{image_paths[img_idx].name})")
                result.append("")
                img_idx += 1

            result.append(line)

        if img_idx < n_images:
            result.append("")
            for p in image_paths[img_idx:]:
                result.append(f"![illustration](assets/{p.name})")
                result.append("")

        return "\n".join(result)

    # ---------- 封面 ----------

    def _fetch_cover_image(
        self,
        repo_info: Dict[str, Any],
        save_dir: Path,
    ) -> Optional[Path]:
        """下载 GitHub Open Graph 图作为封面。"""
        full_name = repo_info.get("full_name") or ""
        if "/" not in full_name:
            logger.warning(f"封面：仓库名格式异常 {full_name}")
            return None

        owner, repo = full_name.split("/", 1)
        og_url = f"https://opengraph.githubassets.com/1/{owner}/{repo}"

        save_dir.mkdir(parents=True, exist_ok=True)
        cover_path = save_dir / "cover.png"

        try:
            from PIL import Image
            import io as _io

            resp = requests.get(
                og_url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=20,
            )
            resp.raise_for_status()

            img = Image.open(_io.BytesIO(resp.content)).convert("RGB")

            w, h = img.size
            target_ratio = 2.35
            if w / h > target_ratio:
                new_w = int(h * target_ratio)
                left = (w - new_w) // 2
                img = img.crop((left, 0, left + new_w, h))
            else:
                new_h = int(w / target_ratio)
                top = (h - new_h) // 2
                img = img.crop((0, top, w, top + new_h))

            img = img.resize((900, 383), Image.Resampling.LANCZOS)
            img.save(cover_path, "PNG", optimize=True)

            logger.info(f"✅ 封面已保存: {cover_path}")
            return cover_path

        except Exception as e:
            logger.warning(f"⚠️ 封面下载/处理失败: {e}")
            return None

    # ---------- 发布到微信 ----------

    def publish_to_wechat(
        self,
        article_md: str,
        repo_info: Optional[Dict[str, Any]] = None,
        cover_image: Optional[Path] = None,
        work_dir: Optional[Path] = None,
    ) -> bool:
        """调用 wechat_formatter 排版并发布。"""
        try:
            from skills.wechat_formatter import WechatFormatter

            if work_dir is None:
                work_dir = Path(self.config["output_dir"]) / "tmp" \
                           / datetime.now().strftime("%Y%m%d_%H%M%S")
            work_dir = Path(work_dir)
            assets_dir = work_dir / "assets"
            assets_dir.mkdir(parents=True, exist_ok=True)

            if cover_image and cover_image.exists():
                target = assets_dir / cover_image.name
                if cover_image != target and not target.exists():
                    shutil.copy2(cover_image, target)

            md_file = work_dir / "article.md"
            if not md_file.exists():
                md_file.write_text(article_md, encoding="utf-8")

            cover_path = None
            if cover_image and cover_image.exists():
                cover_path = cover_image
            elif repo_info:
                cover_path = self._fetch_cover_image(repo_info, assets_dir)

            footer_path = self._get_footer_image()

            fmt = WechatFormatter()
            fmt_kwargs = {
                "theme": self.config["wechat_theme"],
                "open": False,
            }
            if footer_path and footer_path.exists():
                fmt_kwargs["footer_image"] = str(footer_path)
                fmt_kwargs["footer_alt"] = self.config["footer_alt"]

            result = fmt.format(str(md_file), **fmt_kwargs)
            if result.get("status") != "success":
                logger.error(f"排版失败: {result.get('error')}")
                return False

            article_dir = Path(result["result"]["article_dir"])

            if self.config.get("wechat_publish", True):
                if cover_path and cover_path.exists():
                    images_dir = article_dir / "images"
                    images_dir.mkdir(parents=True, exist_ok=True)
                    target = images_dir / cover_path.name
                    if not target.exists():
                        shutil.copy2(cover_path, target)

                pub_result = fmt.publish(str(article_dir))
                if pub_result.get("status") == "success":
                    logger.info("✅ 已发布到公众号草稿箱")
                    return True
                else:
                    logger.error(f"❌ 发布失败: {pub_result.get('error')}")
                    return False
            else:
                logger.info(f"排版完成，未发布。输出目录: {article_dir}")
                return True

        except Exception as e:
            logger.error(f"发布到微信失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    # ---------- 文末二维码 ----------

    def _get_footer_image(self) -> Optional[Path]:
        """定位文末二维码图片（assets/qr/公众号结束处.png）"""
        rel = self.config.get("footer_image")
        if not rel:
            return None
        p = Path(rel)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        if p.exists():
            logger.info(f"✅ 文末二维码: {p}")
            return p
        logger.warning(f"⚠️ 文末二维码不存在: {p}")
        return None

    # ---------- 主入口 ----------

    def execute(self, **kwargs) -> Dict[str, Any]:
        start_time = time.time()
        logger.info(f"执行技能: {self.name}")

        work_dir: Optional[Path] = None

        try:
            repos = self.fetch_trending_repos()
            if not repos:
                return {"status": "error", "error": "未获取到任何仓库"}

            repo = self.pick_repo(repos)
            if not repo:
                return {"status": "error", "error": "没有可用仓库"}

            owner, repo_name = repo["owner"], repo["repo"]
            full_name = f"{owner}/{repo_name}"
            logger.info(f"今日推荐: {full_name}")

            details = self.get_repo_details(owner, repo_name)
            if not details.get("full_name"):
                return {"status": "error", "error": f"无法获取仓库详情: {full_name}"}

            article = self.generate_article(details)
            if not article:
                return {"status": "error", "error": "文章生成失败"}

            work_dir = Path(self.config["output_dir"]) / "tmp" \
                       / datetime.now().strftime("%Y%m%d_%H%M%S")
            assets_dir = work_dir / "assets"
            assets_dir.mkdir(parents=True, exist_ok=True)

            illustration_paths: List[Path] = []
            try:
                prompts = self._generate_illustration_prompts(
                    details, article, count=self.config["illustration_count"],
                )
                if prompts:
                    illustration_paths = self._generate_illustrations(prompts, assets_dir)
            except Exception as e:
                logger.warning(f"⚠️ 插图流程失败，继续无图文章: {e}")

            if illustration_paths:
                article = self._insert_illustrations(article, illustration_paths)

            md_file = work_dir / "article.md"
            md_file.write_text(article, encoding="utf-8")

            illustration_str_paths = [str(p) for p in illustration_paths]

            cover = illustration_paths[0] if illustration_paths else None
            published = self.publish_to_wechat(
                article_md=article,
                repo_info=details,
                cover_image=cover,
                work_dir=work_dir,
            )

            history = self._load_history()
            if full_name not in history:
                history.append(full_name)
                self._save_history(history)

            elapsed = time.time() - start_time
            return {
                "status": "success" if published else "partial_success",
                "result": {
                    "repo": full_name,
                    "repo_url": details.get("html_url"),
                    "article_path": str(md_file),
                    "illustrations": illustration_str_paths,
                    "published": published,
                    "elapsed": f"{elapsed:.2f}s",
                },
                "metadata": {"skill": self.name, "version": self.version},
            }

        except Exception as e:
            logger.error(f"执行失败: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "error": str(e), "skill": self.name}

        finally:
            if work_dir is not None:
                try:
                    if work_dir.exists():
                        shutil.rmtree(work_dir, ignore_errors=True)
                        logger.info(f"🧹 已清理临时目录: {work_dir}")
                except Exception as e:
                    logger.warning(f"⚠️ 清理临时目录失败: {e}")