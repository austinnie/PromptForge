# core/intent_analyzer.py
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from core.safety import SafetyChecker
from config.settings import settings  # ✅ 新增导入
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
    system_hint: str = ""  # ✅ 新增


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
    
    # ✅ 保留原有 VIDEO_KEYWORDS（用于直接命中判断）
    VIDEO_KEYWORDS = [
        # === 核心词 ===
        '视频', '生成视频', '制作视频', '视频生成', 'video', 'animate', '动图', '动画',
        
        # === 动作类（人物） ===
        '走路', '跑步', '奔跑', '跳跃', '跳', '飞', '飞翔', '游泳', '游', '潜水',
        '跳舞', '舞蹈', '旋转', '转身', '挥手', '招手', '点头', '摇头', '弯腰',
        '蹲下', '站立', '坐下', '躺下', '睡觉', '醒来', '打哈欠', '伸懒腰',
        '说话', '唱歌', '演奏', '弹琴', '打鼓', '吹奏',
        '开车', '骑行', '骑马', '划船', '滑冰', '滑雪', '冲浪',
        '做饭', '烹饪', '吃饭', '喝水', '喝咖啡', '饮茶',
        '工作', '学习', '阅读', '写作', '绘画', '设计',
        '打扫', '洗衣', '购物', '散步',
        
        # === 动作类（自然/物体） ===
        '日出', '日落', '升起', '落下', '流动', '流淌', '瀑布', '喷发',
        '飘动', '摇曳', '摆动', '旋转', '转动', '爆炸', '燃烧',
        '下雨', '下雪', '风暴', '闪电', '波浪', '潮汐', '涨潮', '退潮',
        
        # === 场景/主题 ===
        '海滩', '海边', '沙滩', '海洋', '大海', '湖泊', '河流', '溪流',
        '森林', '树林', '花园', '草原', '沙漠', '雪山', '火山', '洞穴',
        '城市', '街道', '大楼', '夜景', '星空', '银河', '极光',
        '演唱会', '音乐会', '庆典', '节日', '派对', '婚礼', '宴会',
        '体育比赛', '足球', '篮球', '网球', '跑步比赛',
        '动物', '宠物', '猫', '狗', '鸟', '马', '狮子', '老虎', '大象',
        '花朵', '植物', '树木',
        
        # === 视频类型 ===
        '短视频', '长视频', '微电影', '纪录片', '动画片', '宣传片',
        '广告', 'MV', '音乐视频', '教程', 'vlog', '直播',
        
        # === 风格/效果 ===
        '慢动作', '快进', '延时摄影', '慢镜头', '特效', 'CGI', '3D',
        '卡通风格', '写实风格', '水彩风格', '油画风格', '动漫风格',
        '复古', '黑白', '彩色', '高清', '4K', '8K',
        
        # === 英文补充 ===
        'walk', 'run', 'jump', 'fly', 'swim', 'dance', 'sing', 'drive',
        'ride', 'cook', 'eat', 'drink', 'work', 'study', 'read',
        'sunrise', 'sunset', 'flow', 'wave', 'rain', 'snow', 'storm',
        'beach', 'ocean', 'forest', 'city', 'night', 'stars',
        'animal', 'bird', 'cat', 'dog', 'horse', 'flower',
        'short video', 'long video', 'movie', 'documentary', 'animation',
        'slow motion', 'time-lapse', 'timelapse', 'special effect',
        'cartoon', 'realistic', 'watercolor', 'oil painting', 'anime',
        'HD', '4K', '8K',
    ]
    
    def __init__(self):
        self._safety = None
    
    def analyze(self, text: str, has_image: bool = False, 
                has_multiple: bool = False) -> IntentResult:
        """分析用户输入意图"""
        text_lower = text.lower()       

        # 1. 安全检查（最优先）
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
        
        # 4. 对话意图（放在视频之前，减少误触）
        if any(k in text_lower for k in self.CHAT_KEYWORDS):
            return IntentResult(
                type="chat",
                original_text=text,
                confidence=0.9
            )

        # 5. 视频意图检测（移到后面，条件更严格）
        if self._is_video_intent(text):
            return IntentResult(
                type="video",
                prompt=text,
                original_text=text,
                confidence=0.9,
                system_hint="⚠️ 视频生成受 API 政策限制，请合理使用内容"
            )
        
        # 6. 全自动视频创作
        if any(k in text_lower for k in ['创作视频', '全自动', '生成故事', '自动生成']):
            return IntentResult(
                type="multimedia",
                prompt=text,
                original_text=text,
                confidence=0.9
            )
            
        # 7. 文生图
        if self._is_gen_intent(text):
            return self._analyze_txt2img(text)
        
        # 8. 普通对话
        return IntentResult(
            type="chat",
            original_text=text,
            confidence=0.3
        )

    def _is_video_intent(self, text: str) -> bool:
        """
        判断是否为视频生成意图（严格模式）
        - 直接命中 VIDEO_KEYWORDS（明确视频相关词）
        - 或组合条件：动作词 + 场景词 同时出现
        """
        text_lower = text.lower()
        
        # 1. 直接命中关键词（包括"视频"、动作词等）
        # 但为了提高准确性，增加一个过滤：如果命中的是日常动作词但没有场景词，不触发
        for kw in self.VIDEO_KEYWORDS:
            if kw in text_lower:
                # 如果是常见的日常词，需要检查是否有场景词辅助
                daily_words = ['走路', '跑步', '吃饭', '喝水', '工作', '学习', '阅读', '散步', '睡觉', '醒来']
                if kw in daily_words:
                    # 必须有场景词才触发
                    scene_words = ['海滩', '森林', '城市', '星空', '草原', '沙漠', '雪山', '花园', '公园', '街道', '夜景', '大海', '湖泊']
                    if any(s in text_lower for s in scene_words):
                        return True
                    # 没有场景词，不触发
                    continue
                return True
        
        # 2. 组合匹配：动作 + 场景（更严格的补充）
        action_words = ['走路', '跑步', '跳', '飞', '游泳', '跳舞', '开车', '做饭', '唱歌', '演奏', '奔跑', '飞翔', '骑行']
        scene_words = ['海滩', '森林', '城市', '星空', '草原', '沙漠', '雪山', '花园', '公园', '街道', '夜景']
        has_action = any(k in text_lower for k in action_words)
        has_scene = any(k in text_lower for k in scene_words)
        
        if has_action and has_scene:
            return True
        
        return False
    
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
        """检查是否包含不安全内容（使用完整 SafetyChecker，受开关控制）"""
        # ✅ 如果安全检测被禁用，直接返回 False
        if not settings.enable_safety_check:
            return False
        
        is_unsafe, matched = SafetyChecker.check(text)
        if is_unsafe and matched:
            print(f"⚠️ 安全检测触发: {matched[:5]}")
        return is_unsafe
    
    def _safe_fallback(self, text: str) -> IntentResult:
        return IntentResult(
            type="chat",
            prompt="请使用安全词汇描述您的需求",
            original_text=text,
            confidence=0.1
        )