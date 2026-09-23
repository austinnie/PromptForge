# core/composer.py
"""6层提示词组合器 - LayerForge 核心引擎"""

import random
from typing import Dict, List, Optional

# 尝试导入 tiktoken（用于精确 token 计数）
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False


class PromptComposer:
    """6层提示词组合器，支持智能 token 截断"""
    
    LAYER_ORDER = ["subject", "scene", "style", "lighting", "view", "quality"]
    
    # 各层的优先级权重（数字越大越重要，裁剪时优先保留）
    LAYER_PRIORITY = {
        "subject": 100,   # 核心内容，必须保留
        "scene": 80,      # 场景设定，重要
        "style": 70,      # 画风风格，重要
        "lighting": 50,   # 光影氛围，中等
        "view": 30,       # 视角构图，可裁剪
        "quality": 20,    # 画质修饰，最可裁剪
    }
    
    def __init__(self, layers: Dict[str, List[str]]):
        self.layers = layers
        self._tokenizer = None
        
        # 初始化 tokenizer
        if TIKTOKEN_AVAILABLE:
            try:
                self._tokenizer = tiktoken.get_encoding("cl100k_base")
            except:
                self._tokenizer = None
        
        self._validate()
    
    def _validate(self):
        for key in self.LAYER_ORDER:
            if key not in self.layers or not self.layers[key]:
                print(f"   ⚠️ 警告: 层 '{key}' 为空")
    
    def _count_tokens(self, text: str) -> int:
        """计算文本的 token 数量"""
        if not text:
            return 0
        if self._tokenizer:
            return len(self._tokenizer.encode(text))
        # fallback: 粗略估算（1 token ≈ 4 字符）
        return len(text) // 4
    
    def _truncate_to_limit(self, prompt: str, max_tokens: int = 77) -> str:
        """
        智能截断提示词到指定 token 数
        按优先级保留各层内容
        """
        current_tokens = self._count_tokens(prompt)
        if current_tokens <= max_tokens:
            return prompt
        
        # 按 ", " 分割各部分
        parts = prompt.split(", ")
        if len(parts) <= 1:
            # 单一部分，直接截断
            return prompt[:max_tokens * 4]
        
        # 尝试按层分组（简化方法：根据内容特征判断）
        # 由于我们无法精确还原层归属，采用保守策略：
        # 1. 优先保留包含主体关键词的部分（subject 层特征）
        # 2. 其次保留场景描述
        # 3. 最后裁剪修饰词
        
        core_parts = []
        scene_parts = []
        detail_parts = []
        
        subject_keywords = ["woman", "girl", "man", "person", "figure", "character", 
                           "portrait", "body", "face", "hair", "eyes"]
        
        scene_keywords = ["in", "on", "at", "with", "under", "above", "by", 
                         "street", "room", "garden", "forest", "building", "city"]
        
        for part in parts:
            part_lower = part.lower()
            # 判断是否是主体描述
            if any(kw in part_lower for kw in subject_keywords):
                core_parts.append(part)
            elif any(kw in part_lower for kw in scene_keywords) and len(part) < 50:
                scene_parts.append(part)
            else:
                detail_parts.append(part)
        
        # 构建核心提示词
        core_prompt = ", ".join(core_parts)
        core_tokens = self._count_tokens(core_prompt)
        
        # 如果核心部分已经超限，直接截断核心
        if core_tokens > max_tokens:
            # 保留主体描述，截断其他
            if core_parts:
                # 只保留第一个核心部分（通常是最重要的）
                trimmed = core_parts[0]
                if self._count_tokens(trimmed) > max_tokens:
                    return trimmed[:max_tokens * 4]
                return trimmed
            return prompt[:max_tokens * 4]
        
        # 添加场景描述（如果还有空间）
        remaining = max_tokens - core_tokens
        for part in scene_parts:
            test_prompt = core_prompt + ", " + part
            if self._count_tokens(test_prompt) <= max_tokens:
                core_prompt = test_prompt
                remaining = max_tokens - self._count_tokens(core_prompt)
            else:
                # 尝试截断这个场景描述
                part_tokens = self._count_tokens(part)
                if part_tokens <= remaining:
                    core_prompt = test_prompt
                    break
        
        # 最后添加细节（如果还有空间）
        remaining = max_tokens - self._count_tokens(core_prompt)
        for part in detail_parts:
            test_prompt = core_prompt + ", " + part
            if self._count_tokens(test_prompt) <= max_tokens:
                core_prompt = test_prompt
        
        return core_prompt
    
    def apply_preset(self, preset_layers: Dict[str, List[str]]):
        """用预设层配置覆盖默认层（只覆盖存在的键）"""
        for key, values in preset_layers.items():
            if values and isinstance(values, list):
                self.layers[key] = values
                print(f"   🎯 预设锁定层: {key} -> {len(values)} 个选项")
        self._validate()
    
    def compose_by_index(self, index: int, max_tokens: Optional[int] = None) -> str:
        """
        根据索引从每层取一个选项（轮询算法）
        
        参数:
            index: 组合索引
            max_tokens: 最大 token 数（None 表示不限制）
        """
        parts = []
        for key in self.LAYER_ORDER:
            options = self.layers.get(key, [])
            if not options:
                continue
            chosen = options[index % len(options)]
            parts.append(chosen)
            index = index // len(options) if len(options) > 0 else index + 1
        
        full_prompt = ", ".join(parts)
        
        if max_tokens and max_tokens > 0:
            return self._truncate_to_limit(full_prompt, max_tokens)
        return full_prompt
    
    def compose_random(self, max_tokens: Optional[int] = None) -> str:
        """完全随机组合"""
        parts = []
        for key in self.LAYER_ORDER:
            options = self.layers.get(key, [])
            if options:
                parts.append(random.choice(options))
        
        full_prompt = ", ".join(parts)
        
        if max_tokens and max_tokens > 0:
            return self._truncate_to_limit(full_prompt, max_tokens)
        return full_prompt
    
    def get_total_combinations(self) -> int:
        """计算总组合数（笛卡尔积）"""
        total = 1
        for key in self.LAYER_ORDER:
            count = len(self.layers.get(key, []))
            if count == 0:
                return 0
            total *= count
        return total
    
    def get_layer_info(self) -> Dict[str, int]:
        """获取各层选项数量信息"""
        return {key: len(self.layers.get(key, [])) for key in self.LAYER_ORDER}



    # ==================== 动态提示词 (Ollama) ====================

    def generate_prompt_with_ollama(
        self,
        user_desc: str,
        model: str = None,
        style_hint: str = "general",
        retry: int = 2,
    ) -> str:
        """使用 LLM 生成高质量 SD 提示词。

        优先 Agnes，Ollama 兜底（可通过 LLM_BACKENDS 环境变量覆盖）。
        model 参数保留兼容，但实际生效的模型由 LLMClient 决定。
        """
        from core.llm_client import get_default_client

        SYSTEM_PROMPTS = { ... }   # 保持不变
        QUALITY_TAGS = { ... }     # 保持不变

        system_prompt = SYSTEM_PROMPTS.get(style_hint, SYSTEM_PROMPTS["general"])
        quality_tag = QUALITY_TAGS.get(style_hint, QUALITY_TAGS["general"])

        if len(user_desc.strip()) < 5:
            user_desc = f"a beautiful scene with {user_desc}"

        prompt = f"""{system_prompt}

    用户描述：{user_desc}

    要求：
    1. 提示词用英文，逗号分隔
    2. 包含：主体描述 + 环境/背景 + 光影氛围 + 画质修饰词
    3. 长度控制在 30-80 词之间
    4. 只输出提示词，不要有其他内容

    自动追加质量词：{quality_tag}
    """

        llm = get_default_client(temperature=0.7, max_tokens=300, timeout=60)

        for attempt in range(retry + 1):
            result = llm.generate(prompt, system=system_prompt)
            if result:
                result = result.replace("提示词：", "").replace("Prompt:", "").strip()
                if quality_tag not in result:
                    result = f"{result}, {quality_tag}"
                return result
            if attempt < retry:
                time.sleep(2)

        # 兜底
        fallback = f"{user_desc}, {quality_tag}"
        print(f"   ⚠️ LLM 不可用，使用备用提示词")
        return fallback
    