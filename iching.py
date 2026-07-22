# -*- coding: utf-8 -*-
"""
Prompt builders for `Ask Sifu Xion — Your Hexagram Reading` (周易解卦).

Design rule, same as the rest of this backend: everything factual is computed
upstream (iching_calculator.py in the worker) and arrives here as a finished
fact sheet. The model NEVER decides which hexagram, which line, or which
Zhu Xi rule applies — it only renders the facts it is handed into prose.

Chapter 1 ("Your question and your cast") is not generated here at all: the
worker builds it deterministically, so the numbers on the page cannot drift.
This module covers chapters 2-6.
"""

from typing import Dict, Any, List, Optional

ICHING_SECTION_TYPES = ['standing', 'line', 'turn', 'conduct', 'oneline']

SECTION_TITLES = {
    'standing': {
        'en': 'Where You Stand', 'zh': '你当下的处境', 'zh-tw': '你當下的處境',
        'de': 'Wo Sie stehen', 'es': 'Dónde estás', 'fr': 'Où vous en êtes',
    },
    'line': {
        'en': 'What the Line Asks of You', 'zh': '这一爻对你的要求', 'zh-tw': '這一爻對你的要求',
        'de': 'Was die Linie von Ihnen verlangt', 'es': 'Lo que la línea te pide',
        'fr': 'Ce que le trait exige de vous',
    },
    'turn': {
        'en': 'Where It Turns', 'zh': '局势的去向', 'zh-tw': '局勢的去向',
        'de': 'Wohin es sich wendet', 'es': 'Hacia dónde gira', 'fr': 'Vers où cela tourne',
    },
    'conduct': {
        'en': 'What to Do, What Not to Do', 'zh': '该做什么,不该做什么',
        'zh-tw': '該做什麼,不該做什麼', 'de': 'Was zu tun und was zu lassen ist',
        'es': 'Qué hacer y qué no hacer', 'fr': 'Ce qu\'il faut faire et ne pas faire',
    },
    'oneline': {
        'en': 'The One Line', 'zh': '一句话', 'zh-tw': '一句話',
        'de': 'Der eine Satz', 'es': 'La frase', 'fr': 'La phrase',
    },
}

# Gemini's thinking budget is drawn from maxOutputTokens, so a short chapter still
# needs plenty of headroom — 1,500 produced 200-character stubs. The other products
# in this backend sit at 7,000-30,000; these are sized to match.
SECTION_TOKENS = {
    'standing': 14000, 'line': 16000, 'turn': 13000, 'conduct': 13000, 'oneline': 6000,
}

# What each chapter must actually do. Kept concrete so the model has no room
# to drift into generic horoscope prose.
SECTION_BRIEF = {
    'standing': (
        "Open by reading the hexagram as what it structurally is: one trigram sitting on "
        "another. Name them and say what that pairing pictures — Thunder over the Lake, "
        "Fire under Heaven — and what kind of situation that arrangement describes. Then "
        "bring in the Judgment and the Image. Only then apply all of it to the querent's "
        "question, at length and in their own terms: what kind of moment this is, what is "
        "moving and what is still, where the pressure is coming from, what the shape of "
        "the difficulty or the opening actually is. Quote the Judgment in the original "
        "Chinese once, with the English beside it. Do not summarise the hexagram in the "
        "abstract — every classical observation must be turned back on their situation."
    ),
    'line': (
        "This is the heart of the reading and should be the longest chapter. Work from the "
        "GOVERNING TEXT(S) and nothing else. Quote the governing line in the original "
        "Chinese and in English. Then read it the way the Yi is read: say where the line "
        "sits, whether it is in its correct place, whether it is centred, whether it has "
        "correspondence — the fact sheet gives you all of this — and explain what that "
        "position means for someone in the querent's situation. A yin line holding a yang "
        "place is a person in a role they do not quite fit; a centred line is someone with "
        "ground under them. Make that concrete for them. Then say plainly what the line "
        "requires and what it warns against, specifically enough to act on tomorrow. If "
        "there is a secondary text, give it its own paragraph and mark it as secondary."
    ),
    'turn': (
        "Read the transformed hexagram as the direction the situation moves IF the querent "
        "acts as the governing line indicates. Name its trigrams too, and say what changes "
        "between the two pictures — which trigram was replaced, and what that replacement "
        "means. Quote the transformed Judgment. Frame everything as tendency and "
        "consequence, never as prophecy. If there is no transformed hexagram, say the "
        "situation is stable for now, explain what a hexagram with no moving lines means, "
        "and what that stability asks of them."
    ),
    'conduct': (
        "Ground this chapter in the Image (大象) of the primary hexagram — the line that "
        "says what the superior person does in such a situation. Quote it, then derive from "
        "it. Give four to six concrete items, each traceable to the Judgment, the Image, or "
        "the governing line; name which one each comes from. Split clearly into what to do "
        "and what to avoid. Practical, specific to their question, no generic self-help."
    ),
    'oneline': (
        "One or two sentences. The whole reading compressed into something the querent can "
        "carry and still remember a week from now. If a phrase from the governing text "
        "carries it, use that phrase. No heading, no preamble, no summary — just the line."
    ),
}

# Roughly how long each chapter should run. The Yi rewards unhurried reading; a
# paid reading that finishes in three paragraphs feels like a horoscope.
SECTION_LENGTH = {
    'standing': '600-750 words (Chinese/Japanese: 1,100-1,400 characters)',
    'line':     '750-900 words (Chinese/Japanese: 1,400-1,700 characters)',
    'turn':     '550-700 words (Chinese/Japanese: 1,000-1,300 characters)',
    'conduct':  '500-650 words (Chinese/Japanese: 900-1,200 characters)',
    'oneline':  'one or two sentences only',
}

BOUNDARY_RULES = """
BOUNDARIES — these are not stylistic preferences, they define the product:
- NEVER give a date, a deadline, a month, a season or any timing prediction.
- NEVER state whether the matter will succeed or fail, or answer a yes/no question
  with a yes or a no. You read the situation and the conduct it calls for; the
  querent decides.
- NEVER invent hexagram content. Every classical statement you make must come from
  the fact sheet you were given. If a text is not in the fact sheet, it does not exist.
- NEVER change the hexagram numbers, names, line numbers or the governing rule.
- If the question concerns a medical, legal, or life-and-death matter, do not read it.
  Say gently and briefly that this is not something a hexagram should decide, and that
  it belongs with a qualified doctor or lawyer. Write nothing else for that chapter.
- No disclaimers, no hedging about being an oracle, no talk of energy or vibrations.
  Speak as a reader of the Yi speaking plainly to one person.
""".strip()


def _fmt_text_block(t: Dict[str, Any]) -> str:
    bits = [f"  - {t.get('source', 'Text')} — {t.get('hexagram', '')}"]
    if t.get('line'):
        bits.append(f"    Line: {t['line']}")
    if t.get('text'):
        bits.append(f"    Text: {t['text']}")
    if t.get('text_zh'):
        bits.append(f"    In the original: {t['text_zh']}")
    pos = t.get('position')
    if pos:
        bits.append(f"    Position: a {'yang' if pos['yang'] else 'yin'} line in place "
                    f"{pos['place']}; {pos['note']}")
    if t.get('meaning'):
        bits.append(f"    Traditional meaning: {t['meaning']}")
    return "\n".join(bits)


def build_cast_context(cast: Dict[str, Any], question: str) -> str:
    """The fact sheet the whole reading is written from."""
    p = cast.get('primary') or {}
    t = cast.get('transformed')
    lines: List[str] = []
    lines.append("THE QUERENT'S QUESTION (answer THIS, in their own terms):")
    lines.append(f'  "{question.strip()}"')
    lines.append("")
    lines.append("THE CAST — already computed. Never recompute, never alter:")
    lines.append(f"  Cast code: {cast.get('cast_code', '')}"
                 + ("  (thrown on the querent's behalf at the moment the question arrived)"
                    if cast.get('was_thrown_for_them') else "  (cast by the querent)"))
    lines.append(f"  PRIMARY HEXAGRAM: #{p.get('number')} {p.get('name','')} "
                 f"— {p.get('english_name','')}")
    tg = p.get('trigrams') or {}
    if tg:
        lines.append(f"    TRIGRAMS: {tg['composition']}")
        lines.append(f"      upper {tg['upper']['name']} {tg['upper']['symbol']} — "
                     f"{tg['upper']['image']}, {tg['upper']['attribute']}, {tg['upper']['family']}")
        lines.append(f"      lower {tg['lower']['name']} {tg['lower']['symbol']} — "
                     f"{tg['lower']['image']}, {tg['lower']['attribute']}, {tg['lower']['family']}")
    if p.get('judgement'):
        lines.append(f"    Judgment: {p['judgement']}")
    gz = ((p.get('zh') or {}).get('zh-cn') or {}).get('gua_ci')
    if gz:
        lines.append(f"    Judgment in the original: {gz}")
    if p.get('judgement_meaning'):
        lines.append(f"    Judgment meaning: {p['judgement_meaning']}")
    if p.get('image'):
        lines.append(f"    Image: {p['image']}")
    if p.get('image_meaning'):
        lines.append(f"    Image meaning: {p['image_meaning']}")

    cl = cast.get('changing_lines') or []
    if cl:
        lines.append(f"  MOVING LINES: {', '.join(str(x) for x in cl)}")
        for c in cast.get('changing_line_texts') or []:
            lines.append(f"    {c.get('line','')}: {c.get('text','')}")
            zt = (c.get('zh') or {}).get('zh-cn')
            if zt:
                lines.append(f"      In the original: {zt}")
            pos = c.get('position')
            if pos:
                lines.append(f"      Position: a {'yang' if pos['yang'] else 'yin'} line in "
                             f"place {pos['place']}; {pos['note']}")
            if c.get('meaning'):
                lines.append(f"      Traditional meaning: {c['meaning']}")
    else:
        lines.append("  MOVING LINES: none — the situation is stable for now.")

    if t:
        lines.append(f"  TRANSFORMED HEXAGRAM: #{t.get('number')} {t.get('name','')} "
                     f"— {t.get('english_name','')}")
        if t.get('judgement'):
            lines.append(f"    Judgment: {t['judgement']}")
        if t.get('judgement_meaning'):
            lines.append(f"    Judgment meaning: {t['judgement_meaning']}")
    else:
        lines.append("  TRANSFORMED HEXAGRAM: none (no moving lines).")

    rule = cast.get('rule') or {}
    lines.append("")
    lines.append(f"  GOVERNING RULE (朱熹《周易本義》): {rule.get('en','')}")
    lines.append("  GOVERNING TEXT(S) — read these and only these:")
    for g in cast.get('governing_texts') or []:
        lines.append(_fmt_text_block(g))
    return "\n".join(lines)


def build_iching_prompt(*, section_type: str, cast: Dict[str, Any], question: str,
                        lang_code: str = 'en', previous_context: str = '',
                        client_name: str = '') -> Dict[str, Any]:
    """Return {'prompt': str, 'max_tokens': int} for one chapter."""
    if section_type not in ICHING_SECTION_TYPES:
        raise ValueError(f'Unknown iching section type: {section_type}')

    title = SECTION_TITLES[section_type].get(lang_code, SECTION_TITLES[section_type]['en'])
    brief = SECTION_BRIEF[section_type]
    length = SECTION_LENGTH[section_type]
    facts = build_cast_context(cast, question)

    who = f"The querent's name is {client_name.strip()}.\n" if client_name.strip() else ""
    prev = ""
    if previous_context.strip():
        prev = ("\nWHAT YOU HAVE ALREADY WRITTEN in earlier chapters — do not repeat it, "
                "do not contradict it, build on it:\n" + previous_context.strip() + "\n")

    prompt = f"""{facts}

{who}{prev}
WRITE ONE CHAPTER: "{title}"

Length: {length}. Reach it through depth, never through padding or restatement.

{brief}

{BOUNDARY_RULES}

FORM:
- Write in the reading's language as configured. Do not output the chapter title —
  it is added for you.
- Prose paragraphs. {"A clearly split list of do / avoid is right here." if section_type == 'conduct' else "No bullet lists."}
- No preamble, no "in this chapter", no restating these instructions.
- Output ONLY the finished chapter. Never show your planning, drafting notes, or
  scaffolding phrases such as "Drafting the text", "Here is the chapter", or
  "正在起草". The first character you write is the first character the client reads.
- Speak directly to the querent as "you".
"""
    return {'prompt': prompt, 'max_tokens': SECTION_TOKENS[section_type]}
