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

    # ✅ 新增：预设触发词
    self.PRESET_KEYWORDS = [
        "预设", "风格", "画风", "用...风格",
        "mecha", "机甲", "水墨", "国风", "素描", "线稿",
        "动漫", "人像", "风景", "珠宝",
    ]
    
    # ✅ 新增：多人合成关键词
    MULTI_PERSON_KEYWORDS = [
        '三人', '三人行', '四个人', '四人', '五人', '多人', '群像',
        '一群人', '几个人', '三人合影', '多个人', '群照',
        'three', 'four', 'five', 'group', 'crowd',
    ]
    
    # 双人合成关键词
    COUPLE_KEYWORDS = ['和', '与', '一起', '两人', '双人', '情侣', 'couple', 'together', 'two']
    
    # 图生图修改关键词
    EDIT_KEYWORDS = ['变成', '改为', '换成', '改成', '换', '改', '修改', '调整', '风格', 'edit', 'change', 'modify']
    
    # ✅ 扩展：对图片内容的操作词
    IMAGE_ACTION_KEYWORDS = ['加上', '添加', '增加', '加入', '放入', '加个', '加一只', '加一个', '加', '放', '去掉', '删除', '移除', '消除', '去除', '删掉', '拿掉']
    
    # 文生图关键词
    GEN_KEYWORDS = ['生成', '画', '创建', 'create', 'generate', '画一张', '帮我画', 
                    'make', 'render', 'produce', 'draw', 'paint',
                    '加上', '添加', '增加', '加入', '放入',  # 也包含一些动作词
                    'create picture', 'make picture', 'create image']  # ✅ 新增
    
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
        
    # ✅ 明确的视频生成指令（最高优先级，直接触发）
    EXPLICIT_VIDEO_ACTIONS = [
        '生成视频', '制作视频', '视频生成', '做个视频', '做个动画',
        'create video', 'make video', 'generate video', 'animate',
        '短视频', '微电影', '纪录片', 'vlog', '动图', '动画',
    ]

    # ✅ 视频场景/动作词库（用于组合辅助判断，不单独触发）
    VIDEO_SCENE_KEYWORDS = [
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
        'slow motion', 'time-lapse', 'timelapse', 'special effect',
        'cartoon', 'realistic', 'watercolor', 'oil painting', 'anime',
    ]
    
    def __init__(self):
        self._safety = None
    
    def analyze(self, text: str, has_image: bool = False, 
                has_multiple: bool = False, image_count: int = 0) -> IntentResult:
        """
        分析用户输入意图
        
        Args:
            text: 用户输入
            has_image: 是否有图片
            has_multiple: 是否有 2+ 张图片
            image_count: 上传的图片数量（用于判断双人还是多人）
        """

        text_lower = text.lower()       

        # 1. 安全检查（最优先）
        if self._is_unsafe(text):
            # ✅ 尝试清理敏感词
            cleaned = SafetyChecker.sanitize(text)
            if cleaned and len(cleaned) > 3:
                # 清理成功，用清理后的文本继续分析
                print(f"⚠️ 已自动清理敏感词，继续生成: {cleaned[:50]}...")
                text = cleaned
                text_lower = text.lower()
                # 继续往下走（不再 return）
            else:
                # 清理后为空，返回 chat
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
        
        # 3. 双人/多人合成
        if has_multiple and any(k in text_lower for k in self.COUPLE_KEYWORDS):
            # 判断是双人还是多人
            is_multi = (
                any(k in text_lower for k in self.MULTI_PERSON_KEYWORDS) or 
                image_count >= 3
            )
            if is_multi:
                return self._analyze_multi_person(text, count=image_count)
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
            
        # ✅ 预设意图（优先于普通文生图）
        if self._is_preset_intent(text):
            preset = self._extract_preset_name(text)
            return IntentResult(
                type="preset_image",
                prompt=text,
                original_text=text,
                params={"preset": preset},
                confidence=0.9,
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

    def _is_preset_intent(self, text: str) -> bool:
        text_lower = text.lower()
        # 有"预设"字样，或同时提到预设名 + 生成意图
        if "预设" in text_lower or "preset" in text_lower:
            return True
        if any(k in text_lower for k in ["机甲", "水墨", "国风", "素描", "线稿", "动漫"]):
            if any(k in text_lower for k in self.GEN_KEYWORDS):
                return True
        return False

    def _extract_preset_name(self, text: str) -> str:
        from preset_bridge import preset_bridge
        return preset_bridge.find_preset_by_keyword(text)
    
    def _is_video_intent(self, text: str) -> bool:
        """
        判断是否为视频生成意图（分阶段严格判断）
        1. 先检查明确的视频指令 → 直接触发
        2. 再检查：动作词 + 场景词 同时出现，且无图像词 → 触发
        """
        text_lower = text.lower()
        
        # === 阶段 1：明确视频指令（最高优先级） ===
        if any(k in text_lower for k in self.EXPLICIT_VIDEO_ACTIONS):
            print(f"🎬 [意图] 明确视频指令命中")
            return True
        
        # === 阶段 2：动作 + 场景 组合判断 ===
        # 排除图像词（避免"生成风景照片"被误判）
        image_words = ['照片', '图片', '壁纸', '图像', 'photo', 'image', 'wallpaper']
        if any(k in text_lower for k in image_words):
            return False
        
        # 分别统计动作词和场景词的命中情况
        action_words = ['走路', '跑步', '跳', '飞', '游泳', '跳舞', '开车', '做饭', '唱歌', 
                        '演奏', '奔跑', '飞翔', '骑行', '散步', '冲浪', '滑雪']
        scene_words = ['海滩', '森林', '城市', '星空', '草原', '沙漠', '雪山', '花园', 
                       '公园', '街道', '夜景', '大海', '湖泊', '森林']
        
        has_action = any(k in text_lower for k in action_words)
        has_scene = any(k in text_lower for k in scene_words)
        
        if has_action and has_scene:
            print(f"🎬 [意图] 动作+场景组合命中")
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

    def _analyze_multi_person(self, text: str, count: int = 3) -> IntentResult:
        """多人合成"""
        action = "standing together"
        action_map = {
            '拥抱': 'hugging',
            '牵手': 'holding hands',
            '围坐': 'sitting together in a circle',
            '站在一起': 'standing together',
            '合影': 'group photo',
            '庆祝': 'celebrating',
            '聊天': 'chatting together',
            '笑': 'smiling together',
        }
        for cn, en in action_map.items():
            if cn in text:
                action = en
                break

        # 构造 N 人提示词
        subjects = ", ".join([
            "1girl" if i % 2 == 0 else "1boy"
            for i in range(count)
        ])
        prompt = f"{subjects}, group of {count} people, {action}, masterpiece, best quality"

        return IntentResult(
            type="multi_person",  # ✅ 新类型
            prompt=prompt,
            params={"action": action, "count": count},
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
        """安全回退：尝试清理后继续生成"""
        cleaned = SafetyChecker.sanitize(text)
        
        if cleaned and len(cleaned) > 3:
            # 清理成功，返回文生图意图
            return IntentResult(
                type="text_to_image",
                prompt=cleaned,
                original_text=text,
                confidence=0.5,
                system_hint="⚠️ 已自动过滤敏感词"
            )
        else:        
            return IntentResult(
                type="chat",
                prompt="请使用安全词汇描述您的需求",
                original_text=text,
                confidence=0.1
            )