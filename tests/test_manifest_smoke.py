import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skills._manifest import load_all_manifests, import_skill_class

ms = load_all_manifests()
print(f'manifests: {len(ms)}')
ok, fail = 0, 0
for name, m in ms.items():
    try:
        cls = import_skill_class(m)
        ok += 1
        print(f'  OK   {name:24s} -> {m.get("class", "?"):30s} ({m.get("display_name", "?")})')
    except Exception as e:
        fail += 1
        print(f'  FAIL {name:24s} -> {type(e).__name__}: {e}')
print(f'\n总计: {ok} OK / {fail} FAIL / {len(ms)} total')