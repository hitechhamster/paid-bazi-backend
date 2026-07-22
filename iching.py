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
    'standing': 9000, 'line': 10000, 'turn': 9000, 'conduct': 9000, 'oneline': 6000,
}

# What each chapter must actually do. Kept concrete so the model has no room
# to drift into generic horoscope prose.
SECTION_BRIEF = {
    'standing': (
        "Describe the situation the querent is standing in, strictly in the terms of the "
        "PRIMARY hexagram's judgment and image. Name the hexagram by number and name once, "
        "early. Then spend the rest of the chapter on THEIR question, not on the hexagram in "
        "the abstract: what kind of moment is this, what forces are in play, what is the "
        "shape of the difficulty or the opening. If the querent's question names people, a "
        "job, a decision, a place — use those words back to them."
    ),
    'line': (
        "This is the heart of the reading. Work from the GOVERNING TEXT(S) listed in the fact "
        "sheet and nothing else. Quote the governing line text once, plainly. Then say what it "
        "requires of the querent in their situation, and what it warns against. Be specific "
        "enough that they could act on it tomorrow. If there is a secondary text, give it a "
        "short paragraph and make clear it is secondary."
    ),
    'turn': (
        "Read the TRANSFORMED hexagram as the direction the situation moves IF the querent "
        "acts as the governing line indicates. Frame it as tendency and consequence, never as "
        "prophecy. Name the transformed hexagram by number and name. If there is no "
        "transformed hexagram (no moving lines), say instead that the situation is stable for "
        "now and describe what that stability means for their question."
    ),
    'conduct': (
        "Three to five concrete items, each one traceable to the judgment or the governing "
        "line — no invented advice. Split them clearly into what to do and what to avoid. "
        "Practical and specific to the querent's question. No generic self-help."
    ),
    'oneline': (
        "One or two sentences. The whole reading compressed into something the querent can "
        "carry with them and remember a week from now. No heading, no preamble, no summary "
        "of what was already said — just the line itself."
    ),
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


def _fmt_text_block(t: Dict[str, str]) -> str:
    bits = [f"  - {t.get('source', 'Text')} — {t.get('hexagram', '')}"]
    if t.get('line'):
        bits.append(f"    Line: {t['line']}")
    if t.get('text'):
        bits.append(f"    Text: {t['text']}")
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
    if p.get('judgement'):
        lines.append(f"    Judgment: {p['judgement']}")
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
    facts = build_cast_context(cast, question)

    who = f"The querent's name is {client_name.strip()}.\n" if client_name.strip() else ""
    prev = ""
    if previous_context.strip():
        prev = ("\nWHAT YOU HAVE ALREADY WRITTEN in earlier chapters — do not repeat it, "
                "do not contradict it, build on it:\n" + previous_context.strip() + "\n")

    prompt = f"""{facts}

{who}{prev}
WRITE ONE CHAPTER: "{title}"

{brief}

{BOUNDARY_RULES}

FORM:
- Write in the reading's language as configured. Do not output the chapter title —
  it is added for you.
- Prose paragraphs. {"A short list is appropriate here." if section_type == 'conduct' else "No bullet lists."}
- No preamble, no "in this chapter", no restating these instructions.
- Output ONLY the finished chapter. Never show your planning, drafting notes, or
  scaffolding phrases such as "Drafting the text", "Here is the chapter", or
  "正在起草". The first character you write is the first character the client reads.
- Speak directly to the querent as "you".
"""
    return {'prompt': prompt, 'max_tokens': SECTION_TOKENS[section_type]}
