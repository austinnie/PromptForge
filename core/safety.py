# core/safety.py
import re
from typing import Tuple, List, Optional


class SafetyChecker:
    """安全/NSFW检查器"""
    
    UNSAFE_KEYWORDS = [
        '阴茎', '阴道', '插入', '性交', '做爱', '操', '干', '肏',
        '射精', '高潮', '精液', '阴蒂', '口交', '肛交', '自慰',
        '手淫', '淫荡', '色情', '全裸', '一丝不挂',
        'penis', 'vagina', 'intercourse', 'sexual', 'fuck',
        'sperm', 'ejaculate', 'orgasm', 'clitoris', 'porn',
        'explicit', 'xxx', 'hardcore', 'nude', 'naked',
    ]
    
    @classmethod
    def check(cls, text: str) -> Tuple[bool, List[str]]:
        """检查不安全内容"""
        text_lower = text.lower()
        matched = [kw for kw in cls.UNSAFE_KEYWORDS if kw in text_lower]
        return len(matched) > 0, matched
    
    @classmethod
    def sanitize(cls, text: str) -> str:
        """清理不安全关键词"""
        for kw in cls.UNSAFE_KEYWORDS:
            text = text.replace(kw, '')
        # 清理多余空格和逗号
        text = re.sub(r',\s*,', ',', text)
        text = re.sub(r'^\s*,\s*', '', text)
        text = re.sub(r',\s*$', '', text)
        return text.strip()
    
    @classmethod
    def get_safe_alternatives(cls, text: str) -> List[str]:
        """获取安全替代提示词"""
        text_lower = text.lower()
        
        if '拥抱' in text_lower or 'hug' in text_lower:
            return [
                "couple hugging, romantic atmosphere, soft lighting, masterpiece",
                "intimate embrace, loving couple, warm sunset, beautiful photography"
            ]
        elif '接吻' in text_lower or 'kiss' in text_lower:
            return [
                "couple kissing, romantic moment, soft focus, warm lighting",
                "passionate kiss, beautiful couple, dreamy atmosphere, artistic"
            ]
        else:
            return [
                "romantic couple, beautiful moment, soft lighting, masterpiece",
                "loving couple, intimate atmosphere, warm colors, fine art"
            ]