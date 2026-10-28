# scripts/migrate_meta_class_paths.py
"""把 meta.json 里的短名 class 改成全路径（幂等，可重复跑）。"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"

def guess_module_path(skill_name: str) -> str:
    """约定：skills.<name>.skill.<Class> 优先，其次 skills.<name>.<Class>"""
    skill_dir = SKILLS / skill_name
    if (skill_dir / "skill.py").exists():
        return f"skills.{skill_name}.skill"
    return f"skills.{skill_name}"

def main():
    for meta_file in sorted(SKILLS.glob("*/meta.json")):
        data = json.loads(meta_file.read_text(encoding="utf-8"))
        cls_path = data.get("class", "")
        if not cls_path or "." not in cls_path:
            continue
        module, cls_name = cls_path.rsplit(".", 1)
        # 已经是全路径（含 3 段以上或含 'skill'）就跳过
        if module.count(".") >= 1 and module != "skills":
            print(f"  跳过 {meta_file.parent.name}: 已是 {cls_path}")
            continue
        # 短名且 module == 'skills'，展开成全路径
        if module == "skills":
            base = guess_module_path(meta_file.parent.name)
            new_path = f"{base}.{cls_name}"
            data["class"] = new_path
            meta_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"  ✅ {meta_file.parent.name}: {cls_path} -> {new_path}")

if __name__ == "__main__":
    main()