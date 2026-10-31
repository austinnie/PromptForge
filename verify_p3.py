# verify_p3.py
"""P3 验证：config_schema 加载、settings 精简、provider 可用。"""
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")


def line(t=""):
    print(t)


line("=" * 60)
line("P3 验证")
line("=" * 60)

line("\n[1] registry + schema")
from providers import list_providers, get_meta, load_config
providers = list_providers("image")
line(f"  image providers: {providers}")
for p in providers:
    schema = get_meta(p).get("config_schema", {})
    line(f"  {p}: schema={list(schema.keys())}")

line("\n[2] load_config 读 env")
for p in providers:
    try:
        cfg = load_config(p)
        safe = {}
        for k, v in cfg.items():
            if k.isupper() or not isinstance(v, str):
                continue
            if "key" in k.lower() or "token" in k.lower():
                safe[k] = f"***{v[-4:]}" if v else "(空)"
            else:
                safe[k] = v
        line(f"  {p}: {safe}")
    except Exception as e:
        line(f"  {p}: ❌ {e}")

line("\n[3] settings.get_provider_config")
from config.settings import settings
for p in providers:
    cfg = settings.get_provider_config(p)
    line(f"  {p}: keys={sorted(k for k in cfg if k.islower())}")

line("\n[4] settings.py 行数")
n = len(Path("config/settings.py").read_text(encoding="utf-8").splitlines())
line(f"  {n} 行（原 400+）")

line("\n[5] 核心属性")
line(f"  agnes_api_key: {'✅' if settings.agnes_api_key else '❌ 空'}")
line(f"  generation_mode: {settings.generation_mode}")
line(f"  api_provider: {settings.api_provider}")
line(f"  output_dir: {settings.output_dir}")

line("\n[6] validate_all")
from providers import validate_all
missing = validate_all()
if missing:
    for name, keys in missing.items():
        line(f"  ⚠️ {name} 缺: {keys}")
else:
    line("  ✅ 所有 provider 配置齐全")

line("\n" + "=" * 60)
line("P3 验证完成")
line("=" * 60)