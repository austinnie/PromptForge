# core/safety.py
import re
from typing import Tuple, List, Optional


class SafetyChecker:
    """安全/NSFW检查器 - 增强版"""
    
    # ============================================================
    # 敏感词库（按类别分组）
    # ============================================================
    
    # ----- 性器官/直接色情 -----
    SEXUAL_ORGANS = [
        '阴茎', '阳具', '肉棒', '鸡巴', '屌', '大屌', '巨屌',
        '阴道', '阴户', '小穴', '骚穴', '嫩穴', '肉穴',
        '乳房', '奶子', '巨乳', '爆乳', '乳晕', '乳头',
        '屁股', '臀部', '美臀', '翘臀',
        '阴蒂', '阴唇', '阴毛', '精子', '精液',
        '阴茎', '阴道', '阴囊', '睾丸', '前列腺',
        'penis', 'vagina', 'clitoris', 'penile', 'vaginal',
        'sperm', 'ejaculate', 'orgasm',
    ]
    
    # ----- 性行为/色情动作 -----
    SEXUAL_ACTS = [
        '性交', '做爱', '爱爱', '啪啪', '做爱', '上床',
        '口交', '肛交', '乳交', '手淫', '自慰', '打飞机',
        '插入', '抽插', '进出', '冲刺', '喷射',
        '射精', '高潮', '潮吹', '内射', '颜射',
        '性爱', '交配', '繁衍', '性行为',
        'intercourse', 'penetration', 'ejaculation',
        'masturbate', 'masturbation', 'orgasm',
        'fuck', 'fucking', 'suck', 'blowjob', 'handjob',
    ]
    
    # ----- 色情内容/裸露 -----
    PORNOGRAPHIC = [
        '色情', '情色', '成人', '限制级', '十八禁',
        '裸体', '全裸', '一丝不挂', '赤裸', '裸照', '裸图',
        '露点', '露乳', '露阴', '走光', '透视',
        '诱惑', '勾引', '挑逗', '撩人', '艳照',
        '艳舞', '脱衣', '裸聊', '视频裸', '裸播',
        'nude', 'naked', 'porn', 'porno', 'xxx', 'hardcore',
        'explicit', 'nsfw', '18+', 'adult', 'erotic',
        'erotica', 'bdsm', 'bondage', 'fetish',
    ]
    
    # ----- 性暗示/擦边球（只保留真正具有性暗示意图的词）-----
    SEXUAL_SUGGESTIVE = [
        '性感', '妩媚', '妖娆', '尤物', '欲火',
        'S身材', '情趣内衣', '情趣',
        '诱惑照', '福利照', '私房照',
        'sexy', 'seductive', 'provocative',
        'lingerie', 'panties',
        'bondage', 'dominatrix',
    ]

    # ----- 以下为正常词汇，不拦截（仅记录）-----
    NORMAL_FASHION = [
        '蕾丝', '丝袜', '吊带', '比基尼', '泳装',
        '内衣', '内裤', 'bra', '写真',
        '丰满', '圆润', '曼妙', '曲线',
        'bikini', 'underwear', 'hot',
    ]
    
    # ----- 暴力/血腥 -----
    VIOLENCE = [
        '杀人', '谋杀', '自杀', '自残', '割腕',
        '血腥', '血淋淋', '脑浆', '内脏', '断肢',
        '爆炸', '尸体', '腐烂', '恶心',
        'kill', 'murder', 'death', 'bloody', 'gore',
        'suicide', 'self-harm', 'torture', 'abuse',
    ]
    
    # ----- 仇恨/歧视 -----
    HATE_SPEECH = [
        '种族歧视', '纳粹', '法西斯', '恐怖分子',
        'racist', 'nazi', 'fascist', 'terrorist',
        '歧视', '侮辱', '蔑视',
    ]
    
    # ----- 非法内容 -----
    ILLEGAL = [
        '毒品', '贩毒', '吸毒', '大麻', '冰毒', '海洛因',
        '枪支', '手枪', '步枪', 'AK47', '枪杀',
        '炸弹', '爆炸物', '军火',
        '诈骗', '洗钱', '黑客', '入侵', '网络攻击',
        'drugs', 'cocaine', 'heroin', 'marijuana',
        'gun', 'pistol', 'rifle', 'weapon', 'bomb',
        'explosive', 'hack', 'malware',
    ]
    
    # ----- 合并为总列表（用于检查） -----
    UNSAFE_KEYWORDS = (
        SEXUAL_ORGANS +
        SEXUAL_ACTS +
        PORNOGRAPHIC +
        SEXUAL_SUGGESTIVE +
        VIOLENCE +
        HATE_SPEECH +
        ILLEGAL
    )
    
    # ============================================================
    # 安全替代提示词（针对常见敏感意图）
    # ============================================================
    SAFE_ALTERNATIVES = {
        '裸露': '穿着得体的时尚摄影',
        '裸体': '穿着时尚衣物的肖像摄影',
        '全裸': '穿着优雅服装的人像',
        '性感': '优雅的时尚摄影',
        '色情': '浪漫的艺术摄影',
        '性爱': '浪漫的情侣摄影',
        '诱惑': '优雅的时尚肖像',
        '裸照': '唯美的人像摄影',
        '裸图': '优雅的肖像摄影',
        '一丝不挂': '穿着时尚衣物的人像',
        'sex': 'romantic couple photography',
        'nude': 'elegant portrait photography',
        'naked': 'fashion portrait photography',
        'porn': 'romantic art photography',
        'sexy': 'elegant fashion photography',
    }
    
    # ============================================================
    # 核心方法
    # ============================================================
    
    @classmethod
    def check(cls, text: str) -> Tuple[bool, List[str]]:
        """
        检查不安全内容
        返回: (是否不安全, 匹配的关键词列表)
        """
        text_lower = text.lower()
        matched = []
        
        for kw in cls.UNSAFE_KEYWORDS:
            if kw.lower() in text_lower:
                matched.append(kw)
        
        return len(matched) > 0, matched
    
    @classmethod
    def sanitize(cls, text: str, aggressive: bool = True) -> str:
        """
        清理不安全关键词
        参数:
            - aggressive: True=移除所有敏感词, False=只移除最严重的
        """
        text_lower = text.lower()
        
        # 先尝试用安全替代词替换
        for original, replacement in cls.SAFE_ALTERNATIVES.items():
            if original in text_lower:
                text = text.replace(original, replacement)
        
        # 再移除剩余敏感词
        keywords_to_remove = cls.UNSAFE_KEYWORDS if aggressive else (
            cls.SEXUAL_ORGANS + cls.SEXUAL_ACTS + cls.PORNOGRAPHIC
        )
        
        for kw in keywords_to_remove:
            text = text.replace(kw, '')
        
        # 清理多余空格和标点
        text = re.sub(r',\s*,', ',', text)
        text = re.sub(r'^\s*,\s*', '', text)
        text = re.sub(r',\s*$', '', text)
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    @classmethod
    def get_safe_alternatives(cls, text: str) -> List[str]:
        """
        获取安全替代提示词
        根据检测到的敏感类型返回替代方案
        """
        text_lower = text.lower()
        alternatives = []
        
        # 检测色情/裸露
        if any(kw in text_lower for kw in cls.SEXUAL_ORGANS + cls.PORNOGRAPHIC):
            alternatives.extend([
                "elegant portrait photography, beautiful lighting, artistic composition, masterpiece",
                "fashion photography, stylish outfit, professional studio lighting, high quality",
                "beautiful woman in elegant dress, sophisticated portrait, soft natural lighting",
            ])
        
        # 检测性暗示
        if any(kw in text_lower for kw in cls.SEXUAL_SUGGESTIVE):
            alternatives.extend([
                "beautiful portrait, natural lighting, elegant style, fashion photography",
                "graceful figure, artistic photography, soft focus, beautiful composition",
            ])
        
        # 检测情侣/浪漫（但非色情）
        if any(kw in text_lower for kw in ['情侣', '拥抱', '亲吻', '浪漫']):
            alternatives.extend([
                "romantic couple, beautiful moment, soft lighting, intimate atmosphere, masterpiece",
                "loving couple, warm embrace, golden sunset, romantic photography",
            ])
        
        # 默认安全方案
        if not alternatives:
            alternatives.extend([
                "beautiful scene, artistic composition, professional photography, masterpiece",
                "elegant artwork, stunning visuals, high quality, detailed rendering",
            ])
        
        return alternatives
    
    @classmethod
    def get_safe_prompt(cls, text: str) -> str:
        """
        获取一个安全的生成提示词（使用替代方案）
        """
        alternatives = cls.get_safe_alternatives(text)
        return alternatives[0] if alternatives else "beautiful scene, masterpiece"
    
    @classmethod
    def get_unsafe_categories(cls, text: str) -> List[str]:
        """检测触发了哪些敏感类别"""
        text_lower = text.lower()
        categories = []
        
        checks = [
            ("性器官/色情", cls.SEXUAL_ORGANS),
            ("性行为", cls.SEXUAL_ACTS),
            ("色情内容", cls.PORNOGRAPHIC),
            ("性暗示", cls.SEXUAL_SUGGESTIVE),
            ("暴力血腥", cls.VIOLENCE),
            ("仇恨歧视", cls.HATE_SPEECH),
            ("非法内容", cls.ILLEGAL),
        ]
        
        for category, keywords in checks:
            if any(kw in text_lower for kw in keywords):
                categories.append(category)
        
        return categories
    
    @classmethod
    def get_score(cls, text: str) -> int:
        """
        计算不安全评分 (0-100)
        用于判断是否需要拦截
        """
        text_lower = text.lower()
        score = 0
        
        # 检查各类敏感词并累加分值
        checks = [
            (10, cls.SEXUAL_ORGANS),
            (15, cls.SEXUAL_ACTS),
            (10, cls.PORNOGRAPHIC),
            (5, cls.SEXUAL_SUGGESTIVE),
            (8, cls.VIOLENCE),
            (10, cls.HATE_SPEECH),
            (10, cls.ILLEGAL),
        ]
        
        for points, keywords in checks:
            for kw in keywords:
                if kw in text_lower:
                    score += points
        
        return min(score, 100)
    
    @classmethod
    def is_safe_for_api(cls, text: str, threshold: int = 30) -> bool:
        """
        判断是否安全发送给第三方 API
        如果评分超过阈值，建议拦截
        """
        score = cls.get_score(text)
        return score < threshold


# ============================================================
# 便捷函数
# ============================================================

def check_safety(text: str) -> Tuple[bool, List[str]]:
    """快捷检查"""
    return SafetyChecker.check(text)


def sanitize_text(text: str) -> str:
    """快捷清理"""
    return SafetyChecker.sanitize(text)


def get_safe_prompt(text: str) -> str:
    """获取安全提示词"""
    return SafetyChecker.get_safe_prompt(text)


__all__ = [
    'SafetyChecker',
    'check_safety',
    'sanitize_text',
    'get_safe_prompt',
]