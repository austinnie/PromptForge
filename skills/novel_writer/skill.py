"""
novel_writer_ollama - 使用本地 Ollama 大模型自动写小说（支持断点续写和连载）

功能：
  - 自动保存小说到文件
  - 断点续写：中断后可以从上次进度继续
  - 连载：基于已有内容生成后续章节
  - 多语言支持：支持 17 种语言小说生成
"""

import requests
import json
import logging
import time
import re
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


# ============================================================
# 多语言配置 - 所有语言相关配置集中管理
# ============================================================
LANG_CONFIG = {
    "zh": {
        "name": "中文",
        "system_prompt": "你是一位优秀的小说作家，擅长创作引人入胜的{genre}小说。请用中文创作。",
        "chapter_format": "第{chapter}章",
        "summary_prefix": "小说简介",
        "writing_style": "细腻生动",
        "language_instruction": "请用中文写作，语言流畅，描写生动。",
        "labels": {
            "title": "标题",
            "genre": "类型",
            "language": "语言",
            "model": "模型",
            "generated_at": "生成时间",
            "total_words": "总字数",
            "summary": "小说简介",
        }
    },
    "en": {
        "name": "English",
        "system_prompt": "You are an excellent novelist, skilled at creating compelling {genre} novels. Please write in English.",
        "chapter_format": "Chapter {chapter}",
        "summary_prefix": "Synopsis",
        "writing_style": "vivid and engaging",
        "language_instruction": "Please write in English, with fluent language and vivid descriptions.",
        "labels": {
            "title": "Title",
            "genre": "Genre",
            "language": "Language",
            "model": "Model",
            "generated_at": "Generated At",
            "total_words": "Total Words",
            "summary": "Synopsis",
        }
    },
    "ja": {
        "name": "日本語",
        "system_prompt": "あなたは優秀な小説作家で、魅力的な{genre}小説を書くのが得意です。日本語で創作してください。",
        "chapter_format": "第{chapter}章",
        "summary_prefix": "あらすじ",
        "writing_style": "繊細で生き生きとした",
        "language_instruction": "日本語で書いてください。流暢な言語と生き生きとした描写で。",
        "labels": {
            "title": "タイトル",
            "genre": "ジャンル",
            "language": "言語",
            "model": "モデル",
            "generated_at": "生成時間",
            "total_words": "総文字数",
            "summary": "あらすじ",
        }
    },
    "es": {
        "name": "Español",
        "system_prompt": "Eres un excelente novelista, experto en crear novelas cautivadoras de {genre}. Por favor escribe en español.",
        "chapter_format": "Capítulo {chapter}",
        "summary_prefix": "Sinopsis",
        "writing_style": "vívido y atractivo",
        "language_instruction": "Por favor escribe en español, con lenguaje fluido y descripciones vívidas.",
        "labels": {
            "title": "Título",
            "genre": "Género",
            "language": "Idioma",
            "model": "Modelo",
            "generated_at": "Generado el",
            "total_words": "Palabras totales",
            "summary": "Sinopsis",
        }
    },
    "fr": {
        "name": "Français",
        "system_prompt": "Vous êtes un excellent romancier, spécialisé dans l'écriture de romans de {genre} captivants. Veuillez écrire en français.",
        "chapter_format": "Chapitre {chapter}",
        "summary_prefix": "Résumé",
        "writing_style": "vivant et engageant",
        "language_instruction": "Veuillez écrire en français, avec un langage fluide et des descriptions vivantes.",
        "labels": {
            "title": "Titre",
            "genre": "Genre",
            "language": "Langue",
            "model": "Modèle",
            "generated_at": "Généré le",
            "total_words": "Mots totaux",
            "summary": "Résumé",
        }
    },
    "de": {
        "name": "Deutsch",
        "system_prompt": "Du bist ein ausgezeichneter Romanautor, der sich auf fesselnde {genre}-Romane spezialisiert hat. Bitte schreibe auf Deutsch.",
        "chapter_format": "Kapitel {chapter}",
        "summary_prefix": "Zusammenfassung",
        "writing_style": "lebendig und fesselnd",
        "language_instruction": "Bitte schreibe auf Deutsch, mit fließender Sprache und lebendigen Beschreibungen.",
        "labels": {
            "title": "Titel",
            "genre": "Genre",
            "language": "Sprache",
            "model": "Modell",
            "generated_at": "Erstellt am",
            "total_words": "Wörter insgesamt",
            "summary": "Zusammenfassung",
        }
    },
    "it": {
        "name": "Italiano",
        "system_prompt": "Sei un eccellente romanziere, esperto nella scrittura di avvincenti romanzi di {genre}. Per favore scrivi in italiano.",
        "chapter_format": "Capitolo {chapter}",
        "summary_prefix": "Sinossi",
        "writing_style": "vivido e coinvolgente",
        "language_instruction": "Per favore scrivi in italiano, con linguaggio fluente e descrizioni vivide.",
        "labels": {
            "title": "Titolo",
            "genre": "Genere",
            "language": "Lingua",
            "model": "Modello",
            "generated_at": "Generato il",
            "total_words": "Parole totali",
            "summary": "Sinossi",
        }
    },
    "pt": {
        "name": "Português",
        "system_prompt": "Você é um excelente romancista, especializado em escrever romances de {genre} cativantes. Por favor, escreva em português.",
        "chapter_format": "Capítulo {chapter}",
        "summary_prefix": "Sinopse",
        "writing_style": "vívido e envolvente",
        "language_instruction": "Por favor, escreva em português, com linguagem fluente e descrições vívidas.",
        "labels": {
            "title": "Título",
            "genre": "Gênero",
            "language": "Idioma",
            "model": "Modelo",
            "generated_at": "Gerado em",
            "total_words": "Palavras totais",
            "summary": "Sinopse",
        }
    },
    "ko": {
        "name": "한국어",
        "system_prompt": "당신은 훌륭한 소설가이며, 매력적인 {genre} 소설을 쓰는 데 능숙합니다. 한국어로 창작해 주세요.",
        "chapter_format": "제{chapter}장",
        "summary_prefix": "줄거리",
        "writing_style": "생생하고 매력적인",
        "language_instruction": "한국어로 작성해 주세요. 유창한 언어와 생생한 묘사로.",
        "labels": {
            "title": "제목",
            "genre": "장르",
            "language": "언어",
            "model": "모델",
            "generated_at": "생성 시간",
            "total_words": "총 글자수",
            "summary": "줄거리",
        }
    },
    "ar": {
        "name": "العربية",
        "system_prompt": "أنت روائي ممتاز، ماهر في كتابة روايات {genre} الآسرة. يرجى الكتابة باللغة العربية.",
        "chapter_format": "الفصل {chapter}",
        "summary_prefix": "ملخص",
        "writing_style": "حيوي وجذاب",
        "language_instruction": "يرجى الكتابة باللغة العربية، بلغة سلسة ووصف حيوي.",
        "labels": {
            "title": "العنوان",
            "genre": "النوع",
            "language": "اللغة",
            "model": "النموذج",
            "generated_at": "تاريخ الإنشاء",
            "total_words": "إجمالي الكلمات",
            "summary": "ملخص",
        }
    },
    "th": {
        "name": "ภาษาไทย",
        "system_prompt": "คุณเป็นนักเขียนนวนิยายที่ยอดเยี่ยม เชี่ยวชาญในการเขียนนวนิยายแนว {genre} ที่น่าดึงดูด กรุณาเขียนเป็นภาษาไทย",
        "chapter_format": "บทที่ {chapter}",
        "summary_prefix": "เรื่องย่อ",
        "writing_style": "มีชีวิตชีวาและน่าดึงดูด",
        "language_instruction": "กรุณาเขียนเป็นภาษาไทย ด้วยภาษาที่ไหลลื่นและคำอธิบายที่มีชีวิตชีวา",
        "labels": {
            "title": "ชื่อเรื่อง",
            "genre": "ประเภท",
            "language": "ภาษา",
            "model": "โมเดล",
            "generated_at": "สร้างเมื่อ",
            "total_words": "จำนวนคำทั้งหมด",
            "summary": "เรื่องย่อ",
        }
    },
    "nl": {
        "name": "Nederlands",
        "system_prompt": "Je bent een uitstekende romanschrijver, bedreven in het schrijven van meeslepende {genre} romans. Schrijf alsjeblieft in het Nederlands.",
        "chapter_format": "Hoofdstuk {chapter}",
        "summary_prefix": "Samenvatting",
        "writing_style": "levendig en boeiend",
        "language_instruction": "Schrijf alsjeblieft in het Nederlands, met vloeiende taal en levendige beschrijvingen.",
        "labels": {
            "title": "Titel",
            "genre": "Genre",
            "language": "Taal",
            "model": "Model",
            "generated_at": "Gegenereerd op",
            "total_words": "Totaal woorden",
            "summary": "Samenvatting",
        }
    },
    "pl": {
        "name": "Polski",
        "system_prompt": "Jesteś znakomitym powieściopisarzem, specjalizującym się w pisaniu wciągających powieści z gatunku {genre}. Proszę pisać po polsku.",
        "chapter_format": "Rozdział {chapter}",
        "summary_prefix": "Streszczenie",
        "writing_style": "żywy i wciągający",
        "language_instruction": "Proszę pisać po polsku, płynnym językiem i żywymi opisami.",
        "labels": {
            "title": "Tytuł",
            "genre": "Gatunek",
            "language": "Język",
            "model": "Model",
            "generated_at": "Wygenerowano",
            "total_words": "Całkowita liczba słów",
            "summary": "Streszczenie",
        }
    },
    "sv": {
        "name": "Svenska",
        "system_prompt": "Du är en utmärkt romanförfattare, skicklig på att skriva fängslande {genre}-romaner. Vänligen skriv på svenska.",
        "chapter_format": "Kapitel {chapter}",
        "summary_prefix": "Sammanfattning",
        "writing_style": "livfull och engagerande",
        "language_instruction": "Vänligen skriv på svenska, med flytande språk och livfulla beskrivningar.",
        "labels": {
            "title": "Titel",
            "genre": "Genre",
            "language": "Språk",
            "model": "Modell",
            "generated_at": "Genererad",
            "total_words": "Totalt antal ord",
            "summary": "Sammanfattning",
        }
    },
    "fi": {
        "name": "Suomi",
        "system_prompt": "Olet erinomainen romaanikirjailija, joka on taitava kirjoittamaan vangitsevia {genre}-romaaneja. Kirjoita suomeksi.",
        "chapter_format": "Luku {chapter}",
        "summary_prefix": "Yhteenveto",
        "writing_style": "elävä ja mukaansatempaava",
        "language_instruction": "Kirjoita suomeksi, sujuvalla kielellä ja elävillä kuvauksilla.",
        "labels": {
            "title": "Otsikko",
            "genre": "Laji",
            "language": "Kieli",
            "model": "Malli",
            "generated_at": "Luotu",
            "total_words": "Sanat yhteensä",
            "summary": "Yhteenveto",
        }
    },
    "el": {
        "name": "Ελληνικά",
        "system_prompt": "Είστε ένας εξαιρετικός μυθιστοριογράφος, ικανός στη συγγραφή συναρπαστικών μυθιστορημάτων {genre}. Παρακαλώ γράψτε στα ελληνικά.",
        "chapter_format": "Κεφάλαιο {chapter}",
        "summary_prefix": "Περίληψη",
        "writing_style": "ζωντανό και συναρπαστικό",
        "language_instruction": "Παρακαλώ γράψτε στα ελληνικά, με ευχάριστη γλώσσα και ζωντανές περιγραφές.",
        "labels": {
            "title": "Τίτλος",
            "genre": "Είδος",
            "language": "Γλώσσα",
            "model": "Μοντέλο",
            "generated_at": "Δημιουργήθηκε",
            "total_words": "Σύνολο λέξεων",
            "summary": "Περίληψη",
        }
    },
    "he": {
        "name": "עברית",
        "system_prompt": "אתה סופר מצוין, מיומן בכתיבת רומני {genre} מרתקים. אנא כתוב בעברית.",
        "chapter_format": "פרק {chapter}",
        "summary_prefix": "תקציר",
        "writing_style": "חי ומרתק",
        "language_instruction": "אנא כתוב בעברית, בשפה רהוטה ותיאורים חיים.",
        "labels": {
            "title": "כותרת",
            "genre": "ז'אנר",
            "language": "שפה",
            "model": "מודל",
            "generated_at": "תאריך יצירה",
            "total_words": "סה\"כ מילים",
            "summary": "תקציר",
        }
    },
    "hi": {
        "name": "हिन्दी",
        "system_prompt": "आप एक उत्कृष्ट उपन्यासकार हैं, {genre} उपन्यास लिखने में कुशल हैं। कृपया हिंदी में लिखें।",
        "chapter_format": "अध्याय {chapter}",
        "summary_prefix": "सारांश",
        "writing_style": "जीवंत और आकर्षक",
        "language_instruction": "कृपया हिंदी में लिखें, सरल भाषा और जीवंत वर्णन के साथ।",
        "labels": {
            "title": "शीर्षक",
            "genre": "शैली",
            "language": "भाषा",
            "model": "मॉडल",
            "generated_at": "निर्माण तिथि",
            "total_words": "कुल शब्द",
            "summary": "सारांश",
        }
    },
}


class NovelWriterOllama:
    """
    使用本地 Ollama 大模型自动写小说（支持断点续写和连载）
    """

    def __init__(self, config: Dict[str, Any] = None):
        """初始化技能"""
        self.config = config or {}
        self.name = "novel_writer_ollama"
        self.version = "1.0.0"
        self._setup_logging()
        self._setup_config()
        
        logger.info("NovelWriterOllama 初始化完成")

    def _setup_logging(self):
        log_level = self.config.get('log_level', 'INFO')
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    def _setup_config(self):
        defaults = {
            'default_model': 'qwen2.5:7b',
            'ollama_url': 'http://localhost:11434',
            'default_temperature': 0.85,
            'default_chapter_count': 3,
            'default_words_per_chapter': 500,
            'default_language': 'zh',
            'output_dir': './skills/novel_writer/output/novels',
        }
        for key, value in defaults.items():
            if key not in self.config:
                self.config[key] = value

    def _validate_inputs(self, **kwargs) -> bool:
        """验证输入参数"""
        required = ['genre', 'title', 'outline', 'characters']
        for param in required:
            if param not in kwargs or not kwargs[param]:
                raise ValueError(f"缺少必需参数: {param}")

        chapter_count = kwargs.get('chapter_count', self.config.get('default_chapter_count', 3))
        words_per_chapter = kwargs.get('words_per_chapter', self.config.get('default_words_per_chapter', 500))
        temperature = kwargs.get('temperature', self.config.get('default_temperature', 0.85))

        if not (1 <= chapter_count <= 20):
            raise ValueError(f"chapter_count 必须在 1-20 之间，当前值: {chapter_count}")
        if not (200 <= words_per_chapter <= 2000):
            raise ValueError(f"words_per_chapter 必须在 200-2000 之间，当前值: {words_per_chapter}")
        if not (0 <= temperature <= 1):
            raise ValueError(f"temperature 必须在 0-1 之间，当前值: {temperature}")

        lang = kwargs.get('language', self.config.get('default_language', 'zh'))
        if lang not in LANG_CONFIG:
            logger.warning(f"不支持的语言: {lang}，将使用中文")

        return True

    def _get_lang_config(self, lang: str) -> Dict:
        """获取语言配置"""
        if lang in LANG_CONFIG:
            return LANG_CONFIG[lang]
        logger.warning(f"不支持的语言: {lang}，使用中文")
        return LANG_CONFIG["zh"]

    def _check_ollama(self, ollama_url: str) -> bool:
        """检查 Ollama 服务是否可用"""
        try:
            response = requests.get(f"{ollama_url}/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                models = [m['name'] for m in data.get('models', [])]
                logger.info(f"Ollama 服务可用，已安装模型: {', '.join(models)}")
                return True
        except Exception as e:
            logger.error(f"Ollama 服务连接失败: {e}")
            return False
        return False

    def _call_ollama(self, ollama_url: str, model: str, prompt: str, temperature: float = 0.85) -> str:
        """调用 Ollama API"""
        url = f"{ollama_url}/api/generate"

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": 2048
            }
        }

        try:
            response = requests.post(url, json=payload, timeout=300)
            response.raise_for_status()
            data = response.json()
            return data.get('response', '').strip()
        except requests.exceptions.Timeout:
            logger.error("Ollama 请求超时")
            return ""
        except Exception as e:
            logger.error(f"Ollama API 调用失败: {e}")
            return ""

    def _load_existing_novel(self, filepath: str) -> Dict:
        """加载已有小说内容"""
        path = Path(filepath)
        if not path.exists():
            return None

        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 1. 解析标题 - 支持多语言
        title_match = re.search(
            r'(?:标题|タイトル|Title|Título|Titre|Titel|Titolo|제목|العنوان|ชื่อเรื่อง|शीर्षक)[：:]\s*(.+?)(?:\n|$)',
            content
        )
        title = title_match.group(1).strip() if title_match else None

        # 2. 解析类型 - 支持多语言
        genre_match = re.search(
            r'(?:类型|ジャンル|Genre|Género|Genre|Genere|장르|النوع|ประเภท|शैली)[：:]\s*(.+?)(?:\n|$)',
            content
        )
        genre = genre_match.group(1).strip() if genre_match else None

        # 3. 解析总字数 - 支持多语言
        words_match = re.search(
            r'(?:总字数|総文字数|Total Words|Palabras totales|Mots totaux|Wörter insgesamt|Parole totali|Palavras totais|총 글자수|إجمالي الكلمات|จำนวนคำทั้งหมด|कुल शब्द)[：:]\s*(\d+)',
            content
        )
        total_words = int(words_match.group(1)) if words_match else 0

        # 4. 解析语言 - 支持多语言标签
        lang_patterns = [
            r'语言[：:]\s*(.+)',
            r'言語[：:]\s*(.+)',
            r'Language[：:]\s*(.+)',
            r'Lingua[：:]\s*(.+)',
            r'Idioma[：:]\s*(.+)',
            r'Langue[：:]\s*(.+)',
            r'Sprache[：:]\s*(.+)',
            r'Język[：:]\s*(.+)',
            r'Språk[：:]\s*(.+)',
            r'Kieli[：:]\s*(.+)',
            r'Γλώσσα[：:]\s*(.+)',
            r'שפה[：:]\s*(.+)',
            r'भाषा[：:]\s*(.+)',
        ]
        lang_match = None
        for pattern in lang_patterns:
            lang_match = re.search(pattern, content)
            if lang_match:
                break
        language = lang_match.group(1).strip() if lang_match else "zh"

        # 如果语言是 zh 但内容包含其他语言特征，自动修正
        if language == "zh":
            if "日本語" in content or "あらすじ" in content or "タイトル" in content:
                language = "ja"
            elif "English" in content or "Synopsis" in content:
                language = "en"
            elif "Español" in content or "Sinopsis" in content:
                language = "es"

        # ✅ 解析章节内容
        chapters = self._parse_chapters_from_file(filepath)
        
        # ✅ 使用 len(chapters) 作为章节数，而不是正则统计
        chapter_count = len(chapters)

        return {
            "title": title,
            "genre": genre,
            "language": language,
            "chapters": chapters,
            "chapter_count": chapter_count,  # ✅ 与 chapters 数量一致
            "total_words": total_words,
            "filepath": str(path)
        }
    
    def _parse_chapters_from_file(self, filepath: str) -> List[Dict]:
        """从文件解析章节内容"""
        path = Path(filepath)
        if not path.exists():
            return []
        
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        chapters = []
        
        # 使用更精确的分割：匹配行首的章节标记
        parts = re.split(r'\n(?=第\d+章[：:]|Chapter \d+[:：]|Capítulo \d+[:：]|Chapitre \d+[:：]|Kapitel \d+[:：]|Capitolo \d+[:：]|제\d+장[：:]|الفصل \d+[:：]|บทที่ \d+[:：]|Hoofdstuk \d+[:：]|Rozdział \d+[:：]|Luku \d+[:：]|Κεφάλαιο \d+[:：]|פרק \d+[:：])', content)
        
        # 多语言章节匹配模式
        patterns = [
            (r'第(\d+)章[：:]\s*(.+?)(?:\n|$)', 'zh/ja'),
            (r'Chapter (\d+)[：:]\s*(.+?)(?:\n|$)', 'en'),
            (r'Capítulo (\d+)[：:]\s*(.+?)(?:\n|$)', 'es'),
            (r'Chapitre (\d+)[：:]\s*(.+?)(?:\n|$)', 'fr'),
            (r'Kapitel (\d+)[：:]\s*(.+?)(?:\n|$)', 'de'),
            (r'Capitolo (\d+)[：:]\s*(.+?)(?:\n|$)', 'it'),
            (r'제(\d+)장[：:]\s*(.+?)(?:\n|$)', 'ko'),
            (r'الفصل (\d+)[：:]\s*(.+?)(?:\n|$)', 'ar'),
            (r'บทที่ (\d+)[：:]\s*(.+?)(?:\n|$)', 'th'),
            (r'Hoofdstuk (\d+)[：:]\s*(.+?)(?:\n|$)', 'nl'),
            (r'Rozdział (\d+)[：:]\s*(.+?)(?:\n|$)', 'pl'),
            (r'Luku (\d+)[：:]\s*(.+?)(?:\n|$)', 'fi'),
            (r'Κεφάλαιο (\d+)[：:]\s*(.+?)(?:\n|$)', 'el'),
            (r'פרק (\d+)[：:]\s*(.+?)(?:\n|$)', 'he'),
        ]
        
        for part in parts:
            # 跳过空内容
            if not part.strip():
                continue
            
            # 尝试匹配所有模式
            matched = False
            for pattern, _ in patterns:
                match = re.search(pattern, part)
                if match:
                    idx = int(match.group(1))
                    title_text = match.group(2).strip()
                    
                    # 提取内容：移除章节标题行和分隔线
                    content_part = part
                    # 移除标题行
                    content_part = re.sub(r'^第\d+章[：:]\s*.+?\n', '', content_part, flags=re.MULTILINE)
                    content_part = re.sub(r'^Chapter \d+[：:]\s*.+?\n', '', content_part, flags=re.MULTILINE)
                    content_part = re.sub(r'^Capítulo \d+[：:]\s*.+?\n', '', content_part, flags=re.MULTILINE)
                    content_part = re.sub(r'^Chapitre \d+[：:]\s*.+?\n', '', content_part, flags=re.MULTILINE)
                    content_part = re.sub(r'^Kapitel \d+[：:]\s*.+?\n', '', content_part, flags=re.MULTILINE)
                    content_part = re.sub(r'^Capitolo \d+[：:]\s*.+?\n', '', content_part, flags=re.MULTILINE)
                    content_part = re.sub(r'^제\d+장[：:]\s*.+?\n', '', content_part, flags=re.MULTILINE)
                    content_part = re.sub(r'^الفصل \d+[：:]\s*.+?\n', '', content_part, flags=re.MULTILINE)
                    content_part = re.sub(r'^บทที่ \d+[：:]\s*.+?\n', '', content_part, flags=re.MULTILINE)
                    content_part = re.sub(r'^Hoofdstuk \d+[：:]\s*.+?\n', '', content_part, flags=re.MULTILINE)
                    content_part = re.sub(r'^Rozdzia\u0142 \d+[：:]\s*.+?\n', '', content_part, flags=re.MULTILINE)
                    content_part = re.sub(r'^Luku \d+[：:]\s*.+?\n', '', content_part, flags=re.MULTILINE)
                    content_part = re.sub(r'^Κεφάλαιο \d+[：:]\s*.+?\n', '', content_part, flags=re.MULTILINE)
                    content_part = re.sub(r'^פרק \d+[：:]\s*.+?\n', '', content_part, flags=re.MULTILINE)
                    
                    # 移除分隔线
                    content_part = re.sub(r'^-{40,}\n', '', content_part, flags=re.MULTILINE)
                    
                    content_part = content_part.strip()
                    if content_part:
                        chapters.append({
                            "index": idx,
                            "title": title_text,
                            "content": content_part
                        })
                    matched = True
                    break
            
            # 如果没有匹配到任何模式，继续下一个
            if not matched:
                continue
        
        return chapters
    
    def _save_novel(self, result_data: Dict, is_continue: bool = False) -> str:
        """保存小说到文件 - 使用目标语言的标签"""
        output_dir = Path(self.config.get('output_dir', './generated_novels'))
        output_dir.mkdir(parents=True, exist_ok=True)

        title = result_data.get('title', 'untitled')
        lang = result_data.get('language', 'zh')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # ✅ 获取目标语言的标签
        lang_config = self._get_lang_config(lang)
        labels = lang_config.get('labels', {})

        safe_title = re.sub(r'[<>:"/\\|?*]', '', title)
        safe_title = safe_title.replace(' ', '_')
        safe_title = safe_title.strip('_')

        if is_continue and result_data.get('filepath'):
            filepath = Path(result_data['filepath'])
        else:
            filename = f"{lang}_{safe_title}_{timestamp}.txt"
            filepath = output_dir / filename

        content_lines = []
        content_lines.append("=" * 60)
        # ✅ 使用目标语言标签
        content_lines.append(f"  {labels.get('title', '标题')}：{result_data.get('title', '')}")
        content_lines.append(f"  {labels.get('genre', '类型')}：{result_data.get('genre', '')}")
        content_lines.append(f"  {labels.get('language', '语言')}：{result_data.get('language', 'zh')}")
        content_lines.append(f"  {labels.get('model', '模型')}：{result_data.get('model_used', '')}")
        content_lines.append(f"  {labels.get('generated_at', '生成时间')}：{result_data.get('generated_at', '')}")
        content_lines.append(f"  {labels.get('total_words', '总字数')}：{result_data.get('total_words', 0)}")
        content_lines.append("=" * 60)
        content_lines.append("")

        # ✅ 简介标签使用目标语言
        content_lines.append(f"【{labels.get('summary', '小说简介')}】")
        content_lines.append(result_data.get('summary', ''))
        content_lines.append("")
        content_lines.append("=" * 60)
        content_lines.append("")

        for chapter in result_data.get('chapters', []):
            # ✅ 章节格式使用目标语言
            chapter_label = lang_config.get('chapter_format', '第{chapter}章')
            content_lines.append(f"{chapter_label.format(chapter=chapter['index'])}：{chapter['title']}")
            content_lines.append("-" * 40)
            content_lines.append(chapter['content'])
            content_lines.append("")
            content_lines.append("-" * 40)
            content_lines.append("")

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(content_lines))

        return str(filepath)

    def _generate_chapter(self, ollama_url: str, model: str, genre: str, title: str,
                          outline: str, characters: str, chapter_index: int,
                          total_chapters: int, style: str, temperature: float,
                          lang_config: Dict, prev_chapters: List[Dict] = None) -> Dict[str, str]:
        """生成单个章节（多语言）"""

        system_template = lang_config.get('system_prompt', '你是一位专业的小说作家')
        language_instruction = lang_config.get('language_instruction', '')

        # 构建系统提示词
        system_prompt = system_template.format(genre=genre)
        system_prompt += f"\n\n小说标题：{title}\n"
        system_prompt += f"小说类型：{genre}\n"
        system_prompt += f"故事大纲：{outline}\n"
        system_prompt += f"角色设定：{characters}\n"
        system_prompt += f"写作风格：{style}\n"
        system_prompt += f"当前正在写第 {chapter_index}/{total_chapters} 章\n\n"
        system_prompt += language_instruction

        context = ""
        if prev_chapters:
            recent = prev_chapters[-2:]
            context = "\n\n前面章节内容：\n"
            for c in recent:
                context += f"第{c['index']}章：{c['title']}\n"
                context += c['content'][:300] + "...\n\n"

        # 生成章节标题
        title_prompt = f"{system_prompt}\n{context}\n\n请为第{chapter_index}章生成一个吸引人的章节标题（仅输出标题，不要其他内容）："
        chapter_title = self._call_ollama(ollama_url, model, title_prompt, temperature)
        chapter_title = chapter_title.strip().strip('"').strip('「').strip('」')
        if not chapter_title:
            chapter_title = f"第{chapter_index}章"

        # 生成章节内容
        content_prompt = f"{system_prompt}\n{context}\n\n章节标题：{chapter_title}\n\n请写出第{chapter_index}章的完整内容："
        chapter_content = self._call_ollama(ollama_url, model, content_prompt, temperature)

        return {
            "index": chapter_index,
            "title": chapter_title,
            "content": chapter_content
        }

    def _generate_summary(self, ollama_url: str, model: str, genre: str, title: str,
                          outline: str, characters: str, chapters: List[Dict],
                          lang_config: Dict) -> str:
        """生成小说简介（多语言）"""
        if not chapters:
            return f"《{title}》是一部{genre}小说，讲述了{outline}的故事。"

        chapter_summaries = "\n".join([f"第{c['index']}章：{c['title']}" for c in chapters])

        prompt_templates = {
            "zh": f"你是一位小说编辑，请为以下小说撰写一段吸引人的简介（200字以内）：\n\n小说标题：{title}\n小说类型：{genre}\n故事大纲：{outline}\n角色设定：{characters}\n章节概览：{chapter_summaries}\n\n请写出小说简介：",
            "en": f"You are a novel editor. Please write an engaging synopsis for the following novel (within 200 words):\n\nTitle: {title}\nGenre: {genre}\nOutline: {outline}\nCharacters: {characters}\nChapter Overview: {chapter_summaries}\n\nPlease write the synopsis:",
            "ja": f"あなたは小説編集者です。以下の小説の魅力的なあらすじを書いてください（200字以内）：\n\n小説タイトル：{title}\nジャンル：{genre}\nあらすじ：{outline}\nキャラクター設定：{characters}\n章の概要：{chapter_summaries}\n\nあらすじを書いてください：",
            "es": f"Eres un editor de novelas. Por favor, escribe una sinopsis atractiva para la siguiente novela (dentro de 200 palabras):\n\nTítulo: {title}\nGénero: {genre}\nEsquema: {outline}\nPersonajes: {characters}\nResumen de capítulos: {chapter_summaries}\n\nPor favor, escribe la sinopsis:",
            "fr": f"Vous êtes un éditeur de romans. Veuillez écrire un résumé attrayant pour le roman suivant (dans la limite de 200 mots) :\n\nTitre : {title}\nGenre : {genre}\nPlan : {outline}\nPersonnages : {characters}\nAperçu des chapitres : {chapter_summaries}\n\nVeuillez écrire le résumé :",
            "de": f"Du bist ein Romanredakteur. Bitte schreibe eine ansprechende Zusammenfassung für den folgenden Roman (innerhalb von 200 Wörtern):\n\nTitel: {title}\nGenre: {genre}\nHandlung: {outline}\nCharaktere: {characters}\nKapitelübersicht: {chapter_summaries}\n\nBitte schreibe die Zusammenfassung:",
            "it": f"Sei un editor di romanzi. Per favore scrivi una sinossi accattivante per il seguente romanzo (entro 200 parole):\n\nTitolo: {title}\nGenere: {genre}\nTrama: {outline}\nPersonaggi: {characters}\nPanoramica dei capitoli: {chapter_summaries}\n\nPer favore scrivi la sinossi:",
            "pt": f"Você é um editor de romances. Por favor, escreva uma sinopse atraente para o seguinte romance (dentro de 200 palavras):\n\nTítulo: {title}\nGênero: {genre}\nEnredo: {outline}\nPersonagens: {characters}\nVisão geral dos capítulos: {chapter_summaries}\n\nPor favor, escreva a sinopse:",
            "ko": f"당신은 소설 편집자입니다. 다음 소설의 매력적인 줄거리를 작성해 주세요 (200자 이내):\n\n제목: {title}\n장르: {genre}\n개요: {outline}\n등장인물: {characters}\n장 개요: {chapter_summaries}\n\n줄거리를 작성해 주세요:",
        }

        lang_code = lang_config.get('lang', 'zh')
        # 尝试从 LANG_CONFIG 中获取语言代码
        for code, config in LANG_CONFIG.items():
            if config.get('name') == lang_config.get('name'):
                lang_code = code
                break

        prompt = prompt_templates.get(lang_code, prompt_templates['zh'])

        summary = self._call_ollama(ollama_url, model, prompt, 0.7)
        if not summary:
            summary = f"《{title}》是一部{genre}小说，讲述了{outline}的故事。"
        return summary

    def execute(self, **kwargs) -> Dict[str, Any]:
        """执行小说生成（支持断点续写和多语言）"""
        start_time = time.time()
        logger.info(f"执行技能: {self.name} (v{self.version})")

        try:
            self._validate_inputs(**kwargs)

            genre = kwargs.get('genre')
            title = kwargs.get('title')
            outline = kwargs.get('outline')
            characters = kwargs.get('characters')
            chapter_count = kwargs.get('chapter_count', self.config.get('default_chapter_count', 3))
            words_per_chapter = kwargs.get('words_per_chapter', self.config.get('default_words_per_chapter', 500))
            style = kwargs.get('style', '细腻')
            temperature = kwargs.get('temperature', self.config.get('default_temperature', 0.85))
            model = kwargs.get('model', self.config.get('default_model', 'qwen2.5:7b'))
            ollama_url = kwargs.get('ollama_url', self.config.get('ollama_url', 'http://localhost:11434'))
            continue_from = kwargs.get('continue_from', None)
            language = kwargs.get('language', self.config.get('default_language', 'zh'))

            # 获取语言配置
            lang_config = self._get_lang_config(language)
            lang_name = lang_config.get('name', '中文')
            logger.info(f"  语言: {lang_name} ({language})")

            logger.info(f"检查 Ollama 服务: {ollama_url}")
            if not self._check_ollama(ollama_url):
                return {
                    "status": "error",
                    "error": f"Ollama 服务不可用: {ollama_url}"
                }

            # 检查是否是续写模式
            existing_data = None
            existing_chapters = []
            start_index = 1
            chapters_to_generate = chapter_count
            target_total = chapter_count  # ✅ 默认为 chapter_count（首次生成时）

            if continue_from:
                existing_data = self._load_existing_novel(continue_from)
                if existing_data:
                    logger.info(f"📖 加载已有小说: {existing_data['title']}")
                    existing_chapter_count = existing_data.get('chapter_count', 0)
                    existing_chapters = existing_data.get('chapters', [])
                    logger.info(f"   已有 {existing_chapter_count} 章，{existing_data['total_words']} 字")
                    genre = existing_data.get('genre', genre)
                    title = existing_data.get('title', title)
                    language = existing_data.get('language', language)
                    lang_config = self._get_lang_config(language)
                    
                    start_index = existing_chapter_count + 1
                    chapters_to_generate = chapter_count  # ✅ chapter_count 是追加的章数
                    target_total = existing_chapter_count + chapter_count  # ✅ 计算目标总章数
                    
                    if chapters_to_generate <= 0:
                        return {
                            "status": "success",
                            "result": existing_data,
                            "message": f"已有 {existing_chapter_count} 章，已达到目标章节数 {chapter_count}"
                        }
                    logger.info(f"  续写 {chapters_to_generate} 章 (从第 {start_index} 章到 {target_total} 章)")
                else:
                    logger.warning(f"未找到续写文件: {continue_from}，将从头开始生成")
                    existing_chapters = []
                    start_index = 1
                    chapters_to_generate = chapter_count
                    target_total = chapter_count

            logger.info(f"开始生成小说: {title} (语言: {lang_name})")
            logger.info(f"  模型: {model}")
            logger.info(f"  类型: {genre}")
            logger.info(f"  总章节数: {target_total}")  # ✅ 显示目标总章数
            logger.info(f"  已有章节: {len(existing_chapters)}")
            logger.info(f"  需生成: {chapters_to_generate}")

            all_chapters = existing_chapters.copy()
            prev_chapters = all_chapters.copy()

            for i in range(chapters_to_generate):
                chapter_idx = start_index + i
                logger.info(f"  生成第 {chapter_idx}/{target_total} 章...")  # ✅ 显示正确的总章数
                chapter = self._generate_chapter(
                    ollama_url, model, genre, title, outline, characters,
                    chapter_idx, target_total, style, temperature,  # ✅ 传入 target_total
                    lang_config, prev_chapters
                )
                all_chapters.append(chapter)
                prev_chapters.append(chapter)
                time.sleep(0.5)

            logger.info("  生成小说简介...")
            summary = self._generate_summary(
                ollama_url, model, genre, title, outline, characters,
                all_chapters, lang_config
            )

            total_words = sum(len(c['content']) for c in all_chapters)

            result_data = {
                "title": title,
                "genre": genre,
                "language": language,
                "summary": summary,
                "chapters": all_chapters,
                "total_words": total_words,
                "model_used": model,
                "generated_at": datetime.now().isoformat(),
                "generation_time": f"{time.time() - start_time:.2f}s"
            }

            if existing_data and existing_data.get('filepath'):
                result_data['filepath'] = existing_data['filepath']

            saved_path = self._save_novel(result_data, is_continue=bool(existing_data))
            result_data['saved_to'] = saved_path

            generation_time = time.time() - start_time

            logger.info(f"✅ 小说生成完成! 共 {len(all_chapters)} 章，{total_words} 字")
            logger.info(f"  耗时: {generation_time:.2f}s")
            logger.info(f"  保存位置: {saved_path}")

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
        return f"<NovelWriterOllama(name={self.name}, version={self.version})>"