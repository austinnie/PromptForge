# core/intent_analyzer.py
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class IntentResult:
    """意图分析结果"""
    type: str  # text_to_image, image_to_image, couple, chat
    prompt: str = ""
    negative: str = ""
    keywords: Dict = field(default_factory=dict)
    original_text: str = ""
    is_continuation: bool = False
    llm_enhanced: bool = False
    params: Dict = field(default_factory=dict)
    confidence: float = 0.5


class IntentAnalyzer:
    """意图分析器"""
    
    # 双人合成关键词
    COUPLE_KEYWORDS = ['和', '与', '一起', '两人', '双人', '情侣', 'couple', 'together', 'two']
    
    # 图生图修改关键词
    EDIT_KEYWORDS = ['变成', '改为', '换成', '改成', '换', '改', '修改', '调整', '风格', 'edit', 'change', 'modify']
    
    # ✅ 扩展：对图片内容的操作词
    IMAGE_ACTION_KEYWORDS = ['加上', '添加', '增加', '加入', '放入', '加个', '加一只', '加一个', '加', '放', '去掉', '删除', '移除', '消除', '去除', '删掉', '拿掉']
    
    # 文生图关键词
    GEN_KEYWORDS = ['生成', '画', '创建', 'create', 'generate', '画一张', '帮我画', 
                    'make', 'render', 'produce', 'draw', 'paint',
                    '加上', '添加', '增加', '加入', '放入']  # 也包含一些动作词
    
    # 场景词
    SCENE_KEYWORDS = ['风景', '美女', '帅哥', '人像', '动漫', 
                      'portrait', 'landscape', 'woman', 'man', 'girl', 'boy',
                      'beautiful', 'gorgeous', 'scenery', 'nature', 'ocean',
                      'sunset', 'city', 'forest', 'mountain', 'river',
                      'flower', 'cat', 'dog', 'animal', 'vehicle']

    # 对话意图关键词
    CHAT_KEYWORDS = [
        '是什么', '什么是', '怎么回事', '如何', '怎样', '怎么', 
        '为什么', '介绍', '描述', '解释', '说明', '告诉我',
        'what', 'how', 'why', 'explain', 'describe', 'introduce'
    ]

    # 参考图关键词
    REFERENCE_KEYWORDS = [
        '类似', '相似', '参考', '参照', '一样风格', '相同风格', '像这样',
        'like this', 'similar', 'reference', 'same style'
    ]    
    
    def __init__(self):
        self._safety = None
    
    def analyze(self, text: str, has_image: bool = False, 
                has_multiple: bool = False) -> IntentResult:
        """分析用户输入意图"""
        text_lower = text.lower()
        
        # 1. 安全检查
        if self._is_unsafe(text):
            return self._safe_fallback(text)
        
        # 2. ✅ 图生图优先（有图片时优先判断）
        if has_image:
            # 2.1 显式修改关键词
            if any(k in text_lower for k in self.EDIT_KEYWORDS):
                return self._analyze_img2img(text)
            
            # 2.2 基于参考图生成
            if any(k in text_lower for k in self.REFERENCE_KEYWORDS):
                return self._analyze_img2img_reference(text)
            
            # 2.3 ✅ 对图片内容的操作（加猫、去背景等）
            if any(k in text_lower for k in self.IMAGE_ACTION_KEYWORDS):
                return self._analyze_img2img(text)
            
            # 2.4 有图片且有生成意图，走图生图
            if len(text) > 3 and self._is_gen_intent(text):
                return self._analyze_img2img_reference(text)
        
        # 3. 双人合成
        if has_multiple and any(k in text_lower for k in self.COUPLE_KEYWORDS):
            return self._analyze_couple(text)
        
        # 4. 对话意图（放在图生图之后，避免误判）
        if any(k in text_lower for k in self.CHAT_KEYWORDS):
            return IntentResult(
                type="chat",
                original_text=text,
                confidence=0.9
            )
        
        # 5. 文生图
        if self._is_gen_intent(text):
            return self._analyze_txt2img(text)
        
        # 6. 普通对话
        return IntentResult(
            type="chat",
            original_text=text,
            confidence=0.3
        )

    def _analyze_img2img_reference(self, text: str) -> IntentResult:
        """基于参考图的图生图"""
        prompt = text
        # 移除引导词
        for kw in ['基于', '根据', '参考', '以这张', '用这张', '按照', 'based on', 'reference']:
            prompt = prompt.replace(kw, '')
        # ✅ 移除操作词
        for kw in ['加上', '添加', '增加', '加入', '放入', '加个', '加一只', '加一个', '加']:
            prompt = prompt.replace(kw, '')
        prompt = prompt.strip().strip('，').strip(',')
        
        keywords = self._extract_keywords(text)
        
        return IntentResult(
            type="image_to_image",
            prompt=prompt if prompt else text,
            keywords=keywords,
            original_text=text,
            params={"mode": "reference"},
            confidence=0.85
        )
    
    def _is_gen_intent(self, text: str) -> bool:
        """判断是否为图像生成意图"""
        text_lower = text.lower()
        has_gen_keyword = any(k in text_lower for k in self.GEN_KEYWORDS)
        has_scene_keyword = any(k in text_lower for k in self.SCENE_KEYWORDS)
        return has_gen_keyword or has_scene_keyword
    
    def _analyze_txt2img(self, text: str) -> IntentResult:
        keywords = self._extract_keywords(text)
        prompt = text
        for kw in ['生成', '画', '帮我画', 'create', 'generate', 'make', 'render', 'produce', 'draw', 'paint']:
            prompt = prompt.replace(kw, '')
        prompt = prompt.strip().strip('，').strip(',')
        
        return IntentResult(
            type="text_to_image",
            prompt=prompt if prompt else text,
            keywords=keywords,
            original_text=text,
            confidence=0.8
        )   

    def _analyze_img2img(self, text: str) -> IntentResult:
        keywords = self._extract_keywords(text)
        return IntentResult(
            type="image_to_image",
            prompt=text,
            keywords=keywords,
            original_text=text,
            confidence=0.9
        )
    
    def _analyze_couple(self, text: str) -> IntentResult:
        action = "standing together"
        action_map = {
            '拥抱': 'hugging',
            '牵手': 'holding hands',
            '接吻': 'kissing',
            '依偎': 'cuddling',
            '并肩': 'standing side by side',
            '背靠背': 'back to back',
        }
        for cn, en in action_map.items():
            if cn in text:
                action = en
                break
        
        return IntentResult(
            type="couple",
            prompt=f"1girl and 1boy, {action}, couple, romantic, masterpiece",
            params={"action": action},
            original_text=text,
            confidence=0.9
        )
    
    def _extract_keywords(self, text: str) -> Dict:
        text_lower = text.lower()
        return {
            "styles": self._match_keywords(text_lower, {
                '动漫': 'anime style', '油画': 'oil painting', 
                '水彩': 'watercolor', '写实': 'photorealistic',
                '赛博朋克': 'cyberpunk', '暗黑': 'dark style',
                '古风': 'traditional Chinese', '唯美': 'aesthetic',
            }),
            "scenes": self._match_keywords(text_lower, {
                '沙滩': 'beach', '海边': 'ocean', '森林': 'forest',
                '城市': 'city', '花园': 'garden', '卧室': 'bedroom',
                '日落': 'sunset', '星空': 'starry sky',
            }),
            "genders": self._match_keywords(text_lower, {
                '女': '1girl', '美女': '1girl', '女生': '1girl',
                '男': '1boy', '帅哥': '1boy', '男生': '1boy',
            }),
            "colors": self._match_keywords(text_lower, {
                '白色': 'white', '黑色': 'black', '红色': 'red',
                '蓝色': 'blue', '粉色': 'pink', '金色': 'golden',
            }),
        }
    
    def _match_keywords(self, text: str, mapping: Dict) -> List[str]:
        return [en for cn, en in mapping.items() if cn in text]
    
    def _is_unsafe(self, text: str) -> bool:
        unsafe = ['性交', '做爱', '裸体', '色情', '阴茎', '阴道', 
                  'sex', 'nude', 'porn', 'explicit', 'fuck']
        return any(k in text.lower() for k in unsafe)
    
    def _safe_fallback(self, text: str) -> IntentResult:
        return IntentResult(
            type="chat",
            prompt="请使用安全词汇描述您的需求",
            original_text=text,
            confidence=0.1
        )