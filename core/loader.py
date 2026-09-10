# core/loader.py
import os
import importlib.util
import sys

def load_all_layers(layers_dir="layers"):
    layers = {}
    if not os.path.exists(layers_dir):
        return layers
    for filename in sorted(os.listdir(layers_dir)):
        if not filename.startswith("layer_") or not filename.endswith(".py"):
            continue
        layer_name = filename.replace("layer_", "").replace(".py", "").split("_", 1)[-1]
        module_path = os.path.join(layers_dir, filename)
        spec = importlib.util.spec_from_file_location(layer_name, module_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[layer_name] = module
        spec.loader.exec_module(module)
        if hasattr(module, "LAYER") and isinstance(module.LAYER, list):
            layers[layer_name] = module.LAYER
            print(f"   ✅ 加载层: {layer_name} ({len(module.LAYER)} 个选项)")
        else:
            print(f"   ⚠️ 跳过 {filename}: 未找到 LAYER 列表")
    return layers
