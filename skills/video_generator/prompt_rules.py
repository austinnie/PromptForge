"""
video_generator / prompt_rules.py

把「关键帧视频制作」SKILL 里最实用、且不依赖关键帧流程的几条规则，
固化成固定文本块，逐字拼进每个视频提示词。

来源与验证状态（请区分）：
  - ONE_TAKE_EN_*      英文原句来自 SKILL（agnes-video-2.5-flash，2026-09 实测止住片段内切镜）
  - NO_TEXT_* / SOUND  结构（人声/音效/音乐，人声栏写「无台词」）来自 SKILL；
                       中文具体措辞是本文件作者按该结构写的，未在你的账号上实测。
  - ONE_TAKE_ZH_*      SKILL 只说「中英各有一份固定版本」但没给原文，中文为本文件自译，未实测。
  - STYLE_LOCKS        水彩句来自 SKILL，其余预设没有。
所有规则都是对某一家供应商某一时间点的观察，不是保证；用之前请自己抽查几条。

设计原则：
  1. 固定块是常量，只在这里改一处；绝不在调用处临时改写。
  2. 幂等：提示词里已含某个块，就不再重复加。
  3. 可整体关闭（apply_prompt_rules=False），方便做 A/B 对照。

语言策略（重要）：
  1. 场景描述用英文，台词保留它自己的语言 —— 这是 SKILL 的结论，不是本文件的偏好。
  2. 所以「场景语言」和「台词语言」是两件事：
     - 场景语言决定 ONE_TAKE / NO_TEXT / SILENT_SOUND 走哪一版；
     - 台词永远单独成段，语言由用户输入的原文决定，不受场景语言影响。
  3. 默认场景语言 = "en"。只有你确实写全中文提示词时才传 lang="zh"。
     绝不因为「台词里有汉字」就把整块切成中文 —— 那正是 SKILL 反复踩过的坑。
"""

import re
from typing import Optional

_CJK = re.compile(r"[\u4e00-\u9fff]")

# ==================== 固定块：一镜到底 ====================

# reference 模式：图只是风格/构图参考，不是首帧，所以不能说「与首帧一致」。
# 说「和参考图的构图一致」，比「保持一致」这种模糊措辞强，也不会暗示它是 first_frame。
ONE_TAKE_EN = (
    "One single unbroken take from one locked camera position; the location, "
    "angle and framing stay as in the reference image from the first frame to the last."
)
ONE_TAKE_ZH = (
    "一个不间断的长镜头，机位始终在同一位置；从第一帧到最后一帧，"
    "地点、角度和取景与参考图保持一致，中途不切镜。"
)

# keyframe 模式（first_frame 真的是第一帧）才用；SKILL 原句
ONE_TAKE_EN_KEYFRAME = (
    "One single unbroken take from one locked camera position; the location, "
    "angle and framing stay exactly as in the first frame from the first frame to the last."
)
ONE_TAKE_ZH_KEYFRAME = (
    "一个不间断的长镜头，机位始终在同一位置；从第一帧到最后一帧，"
    "地点、角度和取景与首帧完全一致。"
)

# ==================== 固定块：禁文字 ====================

NO_TEXT_EN = "No text, subtitles, captions, watermark or logo anywhere in the frame."
NO_TEXT_ZH = "画面中不出现任何文字、字幕、水印或 logo。"

# ==================== 固定块：无台词镜头的声音段 ====================
# SKILL：无台词镜头若只写英文「no one speaks」，模型反而会自己编一句话；
# 有效写法是中文 + 把声音拆成 人声/音效/音乐 三栏，控制句放在人声栏。
#
# 音乐栏 = 无背景音乐，是 2026-09-29 那一节改的：
#   模型自己加的背景声音「一开一关听得出来」，用户判定难受；
#   被接受的做法是保留片段自然声音，音乐后期整片铺。
#   所以无台词镜头不该让模型主动加 BGM —— 那是后期在合成阶段干的事。

SILENT_SOUND_ZH = (
    "【声音】\n"
    "人声：无台词，没有对白或人声。\n"
    "音效：与画面相符的自然环境声。\n"
    "音乐：无背景音乐。"
)
SILENT_SOUND_EN = (
    "[Sound]\n"
    "Voice: none — no dialogue, no narration, no voice-over.\n"
    "Sound effects: natural ambient sound matching the scene.\n"
    "Music: none."
)

# ==================== 画风锁定 ====================
# SKILL：首帧/图片提示词里的画风不会自动带进视频，风格化片子要在视频提示词里再写一遍。

STYLE_LOCKS = {
    "watercolor": (
        "The whole clip stays a flat watercolour children's-book illustration exactly "
        "like the first frame — soft paper texture and painted colours; it never turns "
        "into a photograph or live-action footage."
    ),
}


def _resolve_scene_lang(text: str, lang: Optional[str]) -> str:
    """决定固定块用哪一版。

    规则（按优先级）：
      1. 显式传 lang="zh" / "en" —— 直接用。
      2. 不传 —— 默认 "en"。绝不因为台词里有汉字就切成中文。
    这样「英文场景 + 中文台词」的常见组合不会误判。
    """
    if lang in ("zh", "en"):
        return lang
    return "en"


def apply_rules(
    prompt: str,
    *,
    lang: Optional[str] = None,          # "zh" / "en" / None -> 默认 "en"
    has_first_frame: bool = False,       # 仅当真的用 keyframe(first_frame) 模式时为 True
    one_take: bool = True,
    no_text: bool = True,
    dialogue: Optional[str] = None,      # 有台词：单独成段，一字不改
    speaker: Optional[str] = None,       # 台词说话人（可选，如「少女」）
    voice: Optional[str] = None,         # 声音设定（年龄/性别/音色/语速/口音）
    silent_audio: bool = True,           # 没有台词时是否加「人声：无台词」声音段
    style_lock: Optional[str] = None,    # STYLE_LOCKS 的 key，或一整句自定义文本
) -> str:
    """把固定块按 SKILL 的顺序拼到提示词外面，返回最终提示词。

    顺序：一镜到底 → 画风锁 → 你的场景描述 → 声音/台词 → 禁文字
    """
    prompt = (prompt or "").strip()
    scene_lang = _resolve_scene_lang(prompt, lang)
    zh = (scene_lang == "zh")

    parts = []

    if one_take:
        if has_first_frame:
            block = ONE_TAKE_ZH_KEYFRAME if zh else ONE_TAKE_EN_KEYFRAME
        else:
            block = ONE_TAKE_ZH if zh else ONE_TAKE_EN
        # 幂等：任何一个版本已经在提示词里就不重复
        if not any(b in prompt for b in (
            ONE_TAKE_EN, ONE_TAKE_ZH,
            ONE_TAKE_EN_KEYFRAME, ONE_TAKE_ZH_KEYFRAME,
        )):
            parts.append(block)

    if style_lock:
        text = STYLE_LOCKS.get(style_lock, style_lock)
        if text not in prompt:
            parts.append(text)

    parts.append(prompt)

    if dialogue:
        # SKILL：声音设定逐字复用；台词单独成段，舞台说明不要挨着台词。
        # 声音设定 / 台词头用场景语言；台词本身原样保留，不翻译。
        if voice:
            parts.append(("【声音】\n" if zh else "[Voice]\n") + voice.strip())
        if zh:
            head = f"【台词】\n{speaker.strip() + '说' if speaker else '说'}，一字不改，不增不减："
        else:
            who = (speaker.strip() + " says") if speaker else "Say"
            head = f"[Dialogue]\n{who} exactly this, do not change or add any words:"
        parts.append(f"{head}\n{dialogue.strip()}")
    elif silent_audio:
        sound = SILENT_SOUND_ZH if zh else SILENT_SOUND_EN
        if sound not in prompt:
            parts.append(sound)

    if no_text:
        nt = NO_TEXT_ZH if zh else NO_TEXT_EN
        if nt not in prompt:
            parts.append(nt)

    return "\n\n".join(p for p in parts if p)