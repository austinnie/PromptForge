"""
news_aggregator - 新闻聚合器

RSS 新闻抓取 + AI 摘要生成

功能:
  - RSS 源抓取
  - AI 智能摘要
  - 分类聚合
  - 每日简报生成
  - 多源新闻去重
"""

import os
import time
import json
import logging
import re
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

# RSS 依赖
try:
    import feedparser
    FEEDPARSER_AVAILABLE = True
except ImportError:
    FEEDPARSER_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class NewsAggregator:
    """
    新闻聚合器 - RSS 抓取 + AI 摘要
    """
    
    DEFAULT_FEEDS = {
        # ==================== 日本 ====================
        "japan": [
            "https://www3.nhk.or.jp/rss/news/cat0.xml",
            "https://www.nikkei.com/feed/rss",
            "https://www.japantimes.co.jp/rss/news.xml",
            "https://www.asahi.com/rss/asahi/newsheadlines.rdf",
            "https://mainichi.jp/rss/news/headlines.rss",
            "https://rsshub.app/nhk/news",
            "https://rsshub.app/nikkei/news",
            "https://rsshub.app/yomiuri/1",
            "https://rsshub.app/itmedia/news",
            "https://rsshub.app/ascii/1",
        ],
        
        # ==================== 中国 ====================
        "china": [
            "https://feeds.bbci.co.uk/zhongwen/simp/rss.xml",
            "https://rsshub.app/zaobao/realtime/china",
            "https://rsshub.app/ithome/1",
            "https://rsshub.app/36kr/newsflashes",
            "https://rsshub.app/sspai/series",
            "https://rsshub.app/xinhuanet/1",
            "https://rsshub.app/people/1",
            "https://rsshub.app/zaobao/finance",
            "https://rsshub.app/caijing/1",
        ],
        
        # ==================== 韩国 ====================
        "korea": [
            "http://www.koreatimes.co.kr/rss/",
            "https://www.koreaherald.com/rss/herald.xml",
            "https://rsshub.app/yonhap/news",
            "https://rsshub.app/hani/1",
            "https://rsshub.app/koreaherald/news",
            "https://rsshub.app/zdnetkorea/news",
            "https://rsshub.app/etnews/1",
        ],
        
        # ==================== 科技 ====================
        "tech": [
            "https://feeds.feedburner.com/TechCrunch",
            "https://www.theverge.com/rss/index.xml",
            "https://hnrss.org/frontpage",
            "https://arstechnica.com/feed/",
            "https://techcrunch.com/feed/",
            "https://www.wired.com/feed/rss",
            "https://www.cnet.com/rss/news/",
            "https://www.zdnet.com/news/rss.xml",
            "https://www.theguardian.com/uk/technology/rss",
            "https://feeds.feedburner.com/venturebeat/SZYF",
            "https://www.engadget.com/rss.xml",
        ],
        
        # ==================== 财经 ====================
        "business": [
            "https://www.bloomberg.com/feed/podcast",
            "https://www.ft.com/?format=rss",
            "https://www.wsj.com/xml/rss/3_7085.xml",
            "https://www.economist.com/feeds/print-sections/77/finance-and-economics.xml",
            "https://www.reuters.com/business/rss",
            "https://www.cnbc.com/id/100003114/device/rss/rss.html",
            "https://www.marketwatch.com/rss/topstories",
            "https://www.barrons.com/feed",
        ],
        
        # ==================== 国际新闻 ====================
        "world": [
            "https://feeds.bbci.co.uk/news/world/rss.xml",
            "https://www.npr.org/rss/rss.php?id=1001",
            "https://feeds.reuters.com/reuters/worldNews",
            "https://apnews.com/world-news.rss",
            "https://www.aljazeera.com/xml/rss.xml",
            "https://www.dw.com/en/rss.xml",
            "https://www.france24.com/en/rss",
        ],
        
        # ==================== 美国 ====================
        "usa": [
            "https://feeds.feedburner.com/TechCrunch",
            "https://www.theverge.com/rss/index.xml",
            "https://www.wired.com/feed/rss",
            "https://www.wsj.com/xml/rss/3_7085.xml",
            "https://www.bloomberg.com/feed/podcast",
            "https://www.npr.org/rss/rss.php?id=1001",
            "https://www.cnet.com/rss/news/",
            "https://www.zdnet.com/news/rss.xml",
            "https://apnews.com/world-news.rss",
        ],
    }
    
    # 分类名称映射
    CATEGORY_NAMES = {
        "tech": "科技",
        "business": "财经",
        "world": "国际",
        "china": "中国",
        "usa": "美国",
        "japan": "日本",
        "korea": "韩国",
    }
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.name = "news_aggregator"
        self.version = "1.0.0"
        self._setup_logging()
        self._setup_config()
        
        if not FEEDPARSER_AVAILABLE:
            logger.warning("feedparser 未安装，请运行: pip install feedparser")
        
        logger.info("新闻聚合器 初始化完成")
    
    def _setup_logging(self):
        log_level = self.config.get("log_level", "INFO")
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    
    def _setup_config(self):
        defaults = {
            # ===== 输出配置 =====
            "output_dir": "./skills/news_aggregator/output",
            "save_report": True,
            "report_name_template": "news_{category}_{timestamp}.txt",
            
            # ===== RSS 抓取配置 =====
            "feed_timeout": 10,
            "max_workers": 10,
            
            # ===== AI 摘要配置 =====
            "ai_model": "qwen2.5:3b",
            "ollama_url": "http://localhost:11434",
            "ai_temperature": 0.3,
            "ai_timeout": 120,
            "ai_summary_max_articles": 50,
            
            # ===== 新闻处理配置 =====
            "top_n": 50,
            "summary_length": 500,
            "dedup_key_length": 30,
            
            # ===== 缓存配置 =====
            "cache_ttl": 1800,
            "cache_enabled": True,
            "cache_dir": ".feed_cache",
            
            # ===== 源验证配置 =====
            "validate_feeds": True,
            
            # ===== 报告配置 =====
            "report_date_format": "%Y-%m-%d %H:%M:%S",
            "report_separator_length": 60,
            
            # ===== 日志配置 =====
            "log_level": "INFO",
        }
        for key, value in defaults.items():
            if key not in self.config:
                self.config[key] = value
        
        Path(self.config["output_dir"]).mkdir(parents=True, exist_ok=True)
        self._init_cache_dir()
    
    def _init_cache_dir(self):
        """初始化缓存目录"""
        cache_dir_name = self.config.get("cache_dir", ".feed_cache")
        self.cache_dir = Path(self.config["output_dir"]) / cache_dir_name
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _validate_feeds(self, feeds: List[str]) -> List[str]:
        """验证 RSS 源是否可用"""
        if not feeds:
            return []
        
        valid_feeds = []
        total = len(feeds)
        timeout = self.config.get("feed_timeout", 10)
        max_workers = self.config.get("max_workers", 10)
        
        logger.info(f"正在验证 {total} 个 RSS 源...")
        
        def check_feed(feed_url):
            try:
                import feedparser
                feed = feedparser.parse(feed_url)
                if feed.entries and len(feed.entries) > 0:
                    return feed_url
                return None
            except Exception:
                return None
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(check_feed, url): url for url in feeds}
            for future in as_completed(futures):
                url = futures[future]
                result = future.result()
                if result:
                    valid_feeds.append(result)
                    logger.debug(f"   ✅ {url[:60]}...")
                else:
                    logger.debug(f"   ❌ {url[:60]}...")
        
        logger.info(f"验证完成: {len(valid_feeds)}/{total} 个源可用")
        return valid_feeds
    
    def _get_cached_feeds(self, category: str) -> Optional[List[str]]:
        """获取缓存的可用源"""
        if not self.config.get("cache_enabled", True):
            return None
        
        cache_file = self.cache_dir / f"{category}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    cache_ttl = self.config.get("cache_ttl", 1800)
                    if time.time() - data.get("timestamp", 0) < cache_ttl:
                        return data.get("feeds", [])
            except:
                pass
        return None
    
    def _save_feed_cache(self, category: str, feeds: List[str]):
        """保存缓存的可用源"""
        if not self.config.get("cache_enabled", True):
            return
        
        cache_file = self.cache_dir / f"{category}.json"
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "timestamp": time.time(),
                    "feeds": feeds
                }, f, ensure_ascii=False, indent=2)
        except:
            pass
    
    def _validate_inputs(self, **kwargs) -> bool:
        sources = kwargs.get("sources")
        category = kwargs.get("category")
        if not sources and not category:
            raise ValueError("请指定 sources 或 category 参数")
        return True
    
    def _load_feeds(self, category: str = None, sources: str = None, validate: bool = True) -> List[str]:
        """加载 RSS 源（带验证和缓存）"""
        feeds = []
        
        # 从分类加载
        if category:
            if category in self.DEFAULT_FEEDS:
                feeds = self.DEFAULT_FEEDS[category].copy()
            else:
                logger.warning(f"未知分类: {category}")
                return []
        
        # 从自定义源加载
        if sources:
            source_list = [s.strip() for s in sources.split(',')]
            for feed_list in self.DEFAULT_FEEDS.values():
                for feed in feed_list:
                    for src in source_list:
                        if src.lower() in feed.lower():
                            feeds.append(feed)
        
        # 如果没有指定分类和源，返回所有
        if not feeds and not sources:
            for feed_list in self.DEFAULT_FEEDS.values():
                feeds.extend(feed_list)
        
        # 去重
        feeds = list(set(feeds))
        
        # 验证源
        if validate and self.config.get("validate_feeds", True):
            # 尝试从缓存加载
            if category:
                cached = self._get_cached_feeds(category)
                if cached:
                    logger.info(f"使用缓存: {len(cached)} 个源")
                    return cached
            
            feeds = self._validate_feeds(feeds)
            
            # 保存缓存
            if category:
                self._save_feed_cache(category, feeds)
        
        logger.info(f"加载 {len(feeds)} 个 RSS 源")
        return feeds
    
    def _fetch_feed(self, feed_url: str) -> List[Dict]:
        """抓取单个 RSS 源 - 抓取全部"""
        try:
            if not FEEDPARSER_AVAILABLE:
                return []
            
            feed = feedparser.parse(feed_url)
            items = []
            
            # 不限制，全部抓取
            for entry in feed.entries:
                summary = entry.get("summary", "")
                if summary:
                    summary = re.sub(r'<[^>]+>', '', summary)
                    # 不截断，保留完整
                
                published = entry.get("published") or entry.get("updated", "")
                author = entry.get("author", "")
                
                items.append({
                    "title": entry.get("title", "无标题"),
                    "link": entry.get("link", ""),
                    "summary": summary or "无摘要",
                    "published": published,
                    "author": author or "未知",
                    "source": feed.feed.get("title", feed_url.split("/")[2] if "//" in feed_url else "未知"),
                    "feed_url": feed_url,
                })
            
            return items
            
        except Exception as e:
            logger.warning(f"抓取 {feed_url} 失败: {e}")
            return []
    
    def _fetch_all_feeds(self, feeds: List[str]) -> List[Dict]:
        """抓取所有 RSS 源"""
        all_items = []
        for feed_url in feeds:
            items = self._fetch_feed(feed_url)
            all_items.extend(items)
        return all_items
    
    def _deduplicate(self, items: List[Dict]) -> List[Dict]:
        """去重"""
        seen = set()
        unique = []
        dedup_key_length = self.config.get("dedup_key_length", 30)
        
        for item in items:
            key = item.get("title", "")[:dedup_key_length].lower().strip()
            if key and key not in seen:
                seen.add(key)
                unique.append(item)
        return unique
    
    def _generate_ai_summary(self, articles: List[Dict]) -> str:
        """使用 Ollama 生成 AI 摘要"""
        if not articles:
            return "暂无新闻"
        
        try:
            import requests
            
            max_articles = self.config.get("ai_summary_max_articles", 50)
            temperature = self.config.get("ai_temperature", 0.3)
            timeout = self.config.get("ai_timeout", 120)
            model = self.config.get("ai_model", "qwen2.5:3b")
            ollama_url = self.config.get("ollama_url", "http://localhost:11434")
            
            news_text = ""
            for i, article in enumerate(articles[:max_articles]):
                summary = article.get("summary", "")
                if len(summary) > 200:
                    summary = summary[:200] + "..."
                news_text += f"{i+1}. {article['title']}\n"
                news_text += f"   {summary}\n"
                news_text += f"   来源: {article['source']}\n\n"
            
            prompt = f"""请根据以下新闻内容，生成一份每日新闻简报摘要。

要求：
1. 按主题/类别整理
2. 列出最重要的新闻
3. 每条新闻用一句话概括核心内容
4. 格式简洁清晰

新闻列表：
{news_text}

请生成每日新闻简报摘要："""
            
            response = requests.post(
                f"{ollama_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": temperature}
                },
                timeout=timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("response", "生成摘要失败")
            else:
                return f"AI 服务异常: {response.status_code}"
                
        except Exception as e:
            logger.warning(f"AI 摘要生成失败: {e}")
            return f"AI 摘要生成失败: {str(e)}"
    
    def _generate_report(self, articles: List[Dict], category: str = None, full: bool = True) -> str:
        """生成新闻报告"""
        sep_len = self.config.get("report_separator_length", 60)
        sep = "=" * sep_len
        date_format = self.config.get("report_date_format", "%Y-%m-%d %H:%M:%S")
        
        lines = []
        lines.append(sep)
        lines.append("   📰 每日新闻简报")
        lines.append(sep)
        lines.append(f"   生成时间: {datetime.now().strftime(date_format)}")
        if category:
            category_name = self.CATEGORY_NAMES.get(category, category)
            lines.append(f"   分类: {category_name}")
        lines.append(f"   新闻数: {len(articles)} 条")
        lines.append(sep)
        lines.append("")
        
        if not articles:
            lines.append("暂无新闻")
            return "\n".join(lines)
        
        # AI 摘要
        lines.append("【AI 智能摘要】")
        lines.append("-" * 40)
        try:
            summary = self._generate_ai_summary(articles)
            lines.append(summary)
        except Exception as e:
            logger.warning(f"AI 摘要生成失败，跳过: {e}")
            lines.append("（AI 摘要暂时不可用，请检查 Ollama 服务）")
        
        lines.append("")
        lines.append("-" * 60)
        lines.append("")
        
        # 完整显示所有新闻
        for i, article in enumerate(articles, 1):
            title = article.get("title", "无标题")
            summary = article.get("summary", "")
            source = article.get("source", "未知")
            link = article.get("link", "")
            published = article.get("published", "")
            
            lines.append(f"【{i}】{title}")
            if published:
                lines.append(f"  时间: {published}")
            lines.append(f"  来源: {source}")
            if summary:
                lines.append(f"  摘要: {summary}")
            if link:
                lines.append(f"  链接: {link}")
            lines.append("")
        
        lines.append(sep)
        lines.append("   简报结束")
        lines.append(sep)
        
        return "\n".join(lines)
    
    def _save_report(self, content: str, category: str = None) -> Path:
        """保存报告"""
        if not self.config.get("save_report", True):
            return None
        
        output_dir = Path(self.config["output_dir"])
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        template = self.config.get("report_name_template", "news_{category}_{timestamp}.txt")
        name = template.format(category=category if category else "all", timestamp=timestamp)
        file_path = output_dir / name
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return file_path
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """执行新闻聚合"""
        start_time = time.time()
        logger.info(f"执行技能: {self.name} (v{self.version})")
        
        try:
            self._validate_inputs(**kwargs)
            
            sources = kwargs.get("sources", "")
            category = kwargs.get("category", "")
            top_n = kwargs.get("top_n", self.config.get("top_n", 50))
            validate = kwargs.get("validate", self.config.get("validate_feeds", True))
            
            # 加载 RSS 源（带验证）
            feeds = self._load_feeds(category, sources, validate)
            
            if not feeds:
                return {"status": "error", "error": "未找到可用的 RSS 源"}
            
            # 抓取新闻
            logger.info("抓取新闻...")
            all_items = self._fetch_all_feeds(feeds)
            
            if not all_items:
                return {"status": "error", "error": "未抓取到任何新闻"}
            
            logger.info(f"抓取到 {len(all_items)} 条新闻")
            
            # 去重
            unique_items = self._deduplicate(all_items)
            logger.info(f"去重后 {len(unique_items)} 条")
            
            # 限制数量（语音播报用前 top_n 条）
            top_n = min(top_n, len(unique_items))
            top_items = unique_items[:top_n]
            
            # 生成完整报告（全部新闻）
            report_content = self._generate_report(unique_items, category, full=True)
            report_file = self._save_report(report_content, category)
            
            result_data = {
                "total_fetched": len(all_items),
                "unique_count": len(unique_items),
                "display_count": len(top_items),
                "feeds_count": len(feeds),
                "articles": top_items,           # 语音播报用前 top_n 条
                "all_articles": unique_items,    # 全部新闻
                "report": report_content,
                "category": category or "all",
                "generated_at": datetime.now().isoformat()
            }
            
            if report_file:
                result_data["report_file"] = str(report_file)
                logger.info(f"报告已保存: {report_file}")
            
            return {
                "status": "success",
                "result": result_data,
                "metadata": {
                    "skill": self.name,
                    "version": self.version,
                    "executed_at": datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"执行失败: {e}")
            return {
                "status": "error",
                "error": str(e),
                "skill": self.name,
                "timestamp": datetime.now().isoformat()
            }
    
    def __repr__(self):
        return f"<NewsAggregator(name={self.name}, version={self.version})>"