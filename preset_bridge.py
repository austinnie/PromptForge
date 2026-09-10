# preset_bridge.py
"""把 LayerForge 的 6 层系统桥接到 PromptForge（自包含版本）"""

import importlib.util
import copy
from pathlib import Path

# 用 PromptForge 自己的目录
PROJECT_DIR = Path(__file__).parent


class PresetBridge:
    def __init__(self):
        self._composer = None
        self._layers = None
        self._load()

    def _load(self):
        try:
            from core.loader import load_all_layers
            from core.composer import PromptComposer

            layers_dir = PROJECT_DIR / "layers"
            self._layers = load_all_layers(str(layers_dir))
            self._composer = PromptComposer(self._layers)
            print(f"✅ 已加载 {len(self._layers)} 层")
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"⚠️ 加载失败: {e}")
            self._composer = None

    def is_ready(self) -> bool:
        return self._composer is not None

    def list_presets(self) -> list:
        preset_dir = PROJECT_DIR / "presets"
        if not preset_dir.exists():
            return []
        return sorted([
            f.stem for f in preset_dir.glob("*.py")
            if f.stem not in ("__init__", "index")
        ])

    def load_preset(self, name: str) -> dict:
        p = PROJECT_DIR / "presets" / f"{name}.py"
        if not p.exists():
            return None
        spec = importlib.util.spec_from_file_location(name, p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return getattr(mod, "PRESET", None)

    def find_preset_by_keyword(self, text: str) -> str:
        text_lower = text.lower()
        KEYWORD_MAP = {
            "机甲": ["mecha_glow", "mecha_girl_doll_kit", "mecha_sketch"],
            "赛博": ["mecha_glow", "mecha_thunder_cyberpunk"],
            "水墨": ["chinese_ink", "chinese_ink_animals", "chinese_ink_bird"],
            "国风": ["chinese_ink", "chinese_landscape_master"],
            "素描": ["pencil_sketch_01_fashion", "human_portrait_sketch", "tiger_sketch"],
            "线稿": ["pencil_sketch_05_minimal", "classical_chinese_lineart"],
            "老虎": ["tiger_sketch"],
            "龙": ["dragon_sketch", "dragon_vertical_sketch"],
            "动漫": ["anime_portrait", "autumn_anime_portrait"],
            "人像": ["human_portrait_sketch", "gallery_elegant"],
            "风景": ["healing_landscape", "chinese_landscape_master"],
            "珠宝": ["jewelry_showcase"],
            "手表": ["watch_blueprint"],
            "护士": ["medical_professional_nurse"],
            "海滩": ["beach_resort_swimwear"],
        }
        for kw, presets in KEYWORD_MAP.items():
            if kw in text_lower:
                for p in presets:
                    if (PROJECT_DIR / "presets" / f"{p}.py").exists():
                        return p
        return None

    def build_prompt(
        self,
        preset: str = None,
        subject_override: str = None,
        scene_override: str = None,
        style_override: str = None,
        lighting_override: str = None,
        view_override: str = None,
        quality_override: str = None,
        max_tokens: int = 77,
    ) -> str:
        if not self._composer:
            return subject_override or "beautiful scene, masterpiece"

        composer = copy.deepcopy(self._composer)

        if preset:
            data = self.load_preset(preset)
            if data:
                composer.apply_preset(data["layers"])

        overrides = {
            "subject": subject_override,
            "scene": scene_override,
            "style": style_override,
            "lighting": lighting_override,
            "view": view_override,
            "quality": quality_override,
        }
        for key, val in overrides.items():
            if val:
                composer.layers[key] = [val]

        return composer.compose_random(max_tokens=max_tokens)

    def get_layer_info(self) -> dict:
        if not self._composer:
            return {}
        return self._composer.get_layer_info()


preset_bridge = PresetBridge()