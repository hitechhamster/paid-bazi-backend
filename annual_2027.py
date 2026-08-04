# -*- coding: utf-8 -*-
"""
annual_2027.py — 2027 丁未 "Year Ahead" report: prompt builders (6 chapters).

Used by app.py's /api/generate-annual-section endpoint (mirrors the way the
personal /api/generate-section chapters are prompted, but scoped to the full
丁未 year: 2027-02-04 → 2028-02-03).

Calendar facts are NEVER invented by the AI:
  - almanac_2027.py holds the pre-computed almanac (exact solar-term month
    boundaries + per-day ganzhi / clash / auspicious-activity tags for all
    365 days of the 丁未 year, generated with lunar-python).
  - This module personalizes it in code: each client's favorable days are
    filtered against their own chart branches, month-stem Ten Gods and all
    month-branch interactions (冲/合/刑/害) against the four pillars are
    pre-computed, and the AI is instructed to reason FROM these facts.

Style contract (v2, per owner feedback): flowing master-voice prose, bullets
only for date lists, every recommendation must state its BaZi reason first,
and the day-list labels follow the report language (no English leakage into
Chinese reports).
"""

from typing import Dict, Any, List

from almanac_2027 import (
    ANNUAL_YEAR,
    ANNUAL_YEAR_GANZHI,
    ALMANAC_2027_MONTHS,
    ALMANAC_2027_DAYS,
)

# ---------------------------------------------------------------------------
# Branch interaction tables (六冲 / 六合 / 相刑 / 相害)
# ---------------------------------------------------------------------------

LIU_CHONG = {'子': '午', '丑': '未', '寅': '申', '卯': '酉', '辰': '戌', '巳': '亥',
             '午': '子', '未': '丑', '申': '寅', '酉': '卯', '戌': '辰', '亥': '巳'}

LIU_HE = {'子': '丑', '丑': '子', '寅': '亥', '亥': '寅', '卯': '戌', '戌': '卯',
          '辰': '酉', '酉': '辰', '巳': '申', '申': '巳', '午': '未', '未': '午'}

LIU_HAI = {'子': '未', '未': '子', '丑': '午', '午': '丑', '寅': '巳', '巳': '寅',
           '卯': '辰', '辰': '卯', '申': '亥', '亥': '申', '酉': '戌', '戌': '酉'}

# 相刑 (pairs; 自刑 handled separately)
XING_PAIRS = {('寅', '巳'), ('巳', '申'), ('申', '寅'),
              ('丑', '戌'), ('戌', '未'), ('未', '丑'),
              ('子', '卯'), ('卯', '子')}
ZI_XING = {'辰', '午', '酉', '亥'}   # self-punishment branches


def _branch_relation(a: str, b: str) -> str:
    """Relation of branch a (month) to branch b (chart): 冲/合/刑/害 or ''."""
    if LIU_CHONG.get(a) == b:
        return '冲'
    if LIU_HE.get(a) == b:
        return '合'
    if (a, b) in XING_PAIRS or (b, a) in XING_PAIRS or (a == b and a in ZI_XING):
        return '刑'
    if LIU_HAI.get(a) == b:
        return '害'
    return ''


# ---------------------------------------------------------------------------
# Ten God of a stem relative to the day master (deterministic lookup)
# ---------------------------------------------------------------------------

STEM_INFO = {  # element, yang?
    '甲': ('木', True), '乙': ('木', False), '丙': ('火', True), '丁': ('火', False),
    '戊': ('土', True), '己': ('土', False), '庚': ('金', True), '辛': ('金', False),
    '壬': ('水', True), '癸': ('水', False),
}
SHENG = {'木': '火', '火': '土', '土': '金', '金': '水', '水': '木'}   # produces
KE = {'木': '土', '土': '水', '水': '火', '火': '金', '金': '木'}       # controls


def ten_god(day_stem: str, other_stem: str) -> str:
    """十神 of other_stem relative to day_stem."""
    if day_stem not in STEM_INFO or other_stem not in STEM_INFO:
        return ''
    de, dy = STEM_INFO[day_stem]
    oe, oy = STEM_INFO[other_stem]
    same_pol = (dy == oy)
    if oe == de:
        return '比肩' if same_pol else '劫财'
    if SHENG[de] == oe:
        return '食神' if same_pol else '伤官'
    if KE[de] == oe:
        return '偏财' if same_pol else '正财'
    if KE[oe] == de:
        return '七杀' if same_pol else '正官'
    if SHENG[oe] == de:
        return '偏印' if same_pol else '正印'
    return ''


# 2027 annual flying stars (Period 9, annual star 9 in the center; standard
# Lo Shu flight path center→NW→W→NE→S→N→SW→E→SE).
FLYING_STARS_2027 = {
    'center': 9, 'NW': 1, 'W': 2, 'NE': 3, 'S': 4,
    'N': 5,      # 五黄 Five Yellow — misfortune star: keep quiet, no groundbreaking
    'SW': 6, 'E': 7, 'SE': 8,
}

TAG_LABELS_EN = {
    'wedding': 'wedding / marriage registration',
    'engagement': 'engagement / proposal',
    'business': 'opening a business / launch',
    'contract': 'signing contracts / deals',
    'moving': 'moving house / settling in',
    'travel': 'travel / departure',
    'renovation': 'renovation / groundbreaking',
    'wealth': 'receiving wealth / collecting payment',
    'blessing': 'blessing / ceremony',
}

TAG_LABELS_ZH = {
    'wedding': '嫁娶/领证', 'engagement': '订盟/求婚', 'business': '开市/开业',
    'contract': '签约/立券', 'moving': '入宅/搬家', 'travel': '出行',
    'renovation': '动土/装修', 'wealth': '纳财/收款', 'blessing': '祈福',
}

TAG_LABELS_ZH_TW = {
    'wedding': '嫁娶/領證', 'engagement': '訂盟/求婚', 'business': '開市/開業',
    'contract': '簽約/立券', 'moving': '入宅/搬家', 'travel': '出行',
    'renovation': '動土/裝修', 'wealth': '納財/收款', 'blessing': '祈福',
}


def _tag_labels(lang_code: str) -> Dict[str, str]:
    if lang_code == 'zh':
        return TAG_LABELS_ZH
    if lang_code == 'zh-tw':
        return TAG_LABELS_ZH_TW
    return TAG_LABELS_EN


ANNUAL_SECTION_TYPES = [
    'overview', 'career_wealth', 'love_family',
    'health_wellness', 'monthly', 'cheatsheet',
]


# ---------------------------------------------------------------------------
# Chart helpers
# ---------------------------------------------------------------------------

PILLAR_CN = {'year': '年柱', 'month': '月柱', 'day': '日柱', 'hour': '时柱'}


def get_user_branches(bazi_json: Dict[str, Any]) -> Dict[str, str]:
    """{'year': 亥, 'month': ..., 'day': ..., 'hour': ...} from the chart."""
    pillars = bazi_json.get('pillars', {}) or {}
    out = {}
    for key in ('year', 'month', 'day', 'hour'):
        gz = (pillars.get(key) or {}).get('ganZhi') or ''
        if len(gz) >= 2:
            out[key] = gz[1]
    return out


def get_day_stem(bazi_json: Dict[str, Any]) -> str:
    dm = bazi_json.get('dayMaster') or ''
    if dm:
        return dm[0]
    gz = ((bazi_json.get('pillars') or {}).get('day') or {}).get('ganZhi') or ''
    return gz[0] if gz else ''


def annual_month_table() -> str:
    """Markdown table of the 12 solar-term months of the 丁未 year."""
    lines = [
        f"### The 12 months of {ANNUAL_YEAR_GANZHI} {ANNUAL_YEAR} "
        f"(exact solar-term boundaries — use these, do NOT recalculate)\n",
        "| # | Gregorian range | Month pillar | Branch |",
        "|---|-----------------|--------------|--------|",
    ]
    for m in ALMANAC_2027_MONTHS:
        lines.append(f"| {m['idx']} | {m['start']} ~ {m['end']} "
                     f"| {m['ganzhi']} | {m['zhi']} |")
    return "\n".join(lines)


def month_pillar_analysis(bazi_json: Dict[str, Any]) -> str:
    """Per-month PRE-COMPUTED facts: month-stem Ten God vs the day master +
    every month-branch interaction (冲/合/刑/害) against all four pillars.
    These are the confirmed technical facts the AI must reason FROM."""
    ub = get_user_branches(bazi_json)
    ds = get_day_stem(bazi_json)
    lines = [
        "### PRE-COMPUTED MONTH-PILLAR FACTS vs THIS CHART",
        f"(day master stem: {ds}. Ten Gods and branch interactions below are "
        "calculated — treat them as ground truth; do NOT invent additional "
        "interactions, but DO interpret what each means for this client.)\n",
    ]
    for m in ALMANAC_2027_MONTHS:
        gan, zhi = m['ganzhi'][0], m['ganzhi'][1]
        tg = ten_god(ds, gan) or '?'
        inter = []
        for pk in ('year', 'month', 'day', 'hour'):
            uz = ub.get(pk)
            if not uz:
                continue
            rel = _branch_relation(zhi, uz)
            if rel:
                inter.append(f"{zhi}-{uz}{rel}({PILLAR_CN[pk]})")
        inter_s = '、'.join(inter) if inter else '与四柱地支无冲合刑害,以五行生克论'
        lines.append(f"- Month {m['idx']} {m['ganzhi']} ({m['start']} ~ {m['end']}): "
                     f"月干{gan}={tg}; 月支{zhi}: {inter_s}")
    return "\n".join(lines)


def year_pillar_relation(bazi_json: Dict[str, Any]) -> str:
    """How 丁未 itself lands on this chart (stem Ten God + branch relations)."""
    ub = get_user_branches(bazi_json)
    ds = get_day_stem(bazi_json)
    notes = [f"- 年干丁 vs day master {ds}: Ten God = {ten_god(ds, '丁') or '?'} "
             f"(interpret what a {ten_god(ds, '丁') or '?'} year means)."]
    for pk, uz in ub.items():
        rel = _branch_relation('未', uz)
        if rel == '冲':
            notes.append(f"- 年支未 **冲** {PILLAR_CN[pk]}地支{uz} — 冲太岁 on that pillar.")
        elif rel:
            notes.append(f"- 年支未 与 {PILLAR_CN[pk]}地支{uz} 相{rel}.")
        elif uz == '未':
            notes.append(f"- {PILLAR_CN[pk]}地支即是未 — 值太岁.")
    if len(notes) == 1:
        notes.append("- 年支未与四柱地支无直接冲合刑害;以土旺之年对命局五行的影响论。")
    return "\n".join(notes)


# ---------------------------------------------------------------------------
# Personalized auspicious-day calendar (computed, not AI-generated)
# ---------------------------------------------------------------------------

def _day_ok_for_user(day: Dict[str, Any], user_branches: Dict[str, str]) -> bool:
    """A day is excluded if its branch clashes the client's day or year branch,
    or if the day 'chong' target IS the client's day/year branch."""
    protect = {user_branches.get('day'), user_branches.get('year')} - {None}
    if day['chong'] in protect:
        return False
    if any(LIU_CHONG.get(day['zhi']) == b for b in protect):
        return False
    return True


def personal_calendar(bazi_json: Dict[str, Any], lang_code: str = 'en',
                      per_month: int = 8) -> str:
    """Markdown: for each month, the client's personally favorable days
    (generic almanac-good days minus days clashing their chart), plus the
    days they specifically must avoid. Labels follow the report language."""
    ub = get_user_branches(bazi_json)
    day_branch = ub.get('day', '')
    labels = _tag_labels(lang_code)
    zh = lang_code in ('zh', 'zh-tw')
    star_note = ('★(与您的日支六合,格外有利)' if zh
                 else "★(combines with the client's day branch — extra favorable)")
    lines = [
        "### THE CLIENT'S PERSONAL 2027 DAY CALENDAR",
        "(pre-computed from the traditional almanac AND this client's own chart: "
        "generically auspicious days that clash this client's day/year branch have "
        "already been REMOVED; 'caution days' are days whose branch clashes the "
        "client's day branch. Reproduce dates and their uses EXACTLY as listed — "
        "never invent, add or drop dates. The labels are already in the report "
        "language.)\n",
    ]
    for m in ALMANAC_2027_MONTHS:
        mdays = [d for d in ALMANAC_2027_DAYS if m['start'] <= d['d'] <= m['end']]
        good = [d for d in mdays if d['tags'] and _day_ok_for_user(d, ub)]
        good.sort(key=lambda d: (0 if LIU_HE.get(d['zhi']) == day_branch else 1, d['d']))
        pick = sorted(good[:per_month], key=lambda d: d['d'])
        caution = [d['d'] for d in mdays
                   if day_branch and LIU_CHONG.get(d['zhi']) == day_branch]
        lines.append(f"\n**Month {m['idx']} — {m['start']} ~ {m['end']} "
                     f"({m['ganzhi']}月)**")
        if pick:
            for d in pick:
                star = ' ' + star_note if LIU_HE.get(d['zhi']) == day_branch else ''
                tags = ('、' if zh else ', ').join(labels[t] for t in d['tags'])
                if zh:
                    lines.append(f"- {d['d']}({d['gz']}日):宜 {tags}{star}")
                else:
                    lines.append(f"- {d['d']} ({d['gz']}日): good for {tags}{star}")
        else:
            lines.append("- (本月无特别有利的个人吉日,宜守成)" if zh else
                         "- (no strongly favorable personal days this month — "
                         "advise consolidation)")
        if caution:
            head = ('⚠ 个人忌日(冲您的日支),重大事项避开:' if zh else
                    "⚠ personal caution days (clash the client's day branch): ")
            lines.append(f"- {head}{('、' if zh else ', ').join(caution)}")
    return "\n".join(lines)


def flying_stars_block() -> str:
    fs = FLYING_STARS_2027
    return (
        f"### 2027 Annual Flying Stars (Period 9, annual 9 in center — fixed data, use as-is)\n"
        f"- Center: {fs['center']} | NW: {fs['NW']} | W: {fs['W']} (2 Black — illness star) "
        f"| NE: {fs['NE']} | S: {fs['S']}\n"
        f"- **N: {fs['N']} (5 Yellow — misfortune star: keep this sector quiet, no "
        f"groundbreaking/renovation)** | SW: {fs['SW']} | E: {fs['E']} | SE: {fs['SE']}\n"
    )


# ---------------------------------------------------------------------------
# Shared style contract (v2 — owner's voice)
# ---------------------------------------------------------------------------

STYLE_RULES = """
### WRITING CONTRACT — THIS OVERRIDES ANY INSTINCT TO MAKE LISTS

1. **Flowing prose is the default.** Write in connected paragraphs, like a
   seasoned master writing a personal letter — the same voice as a full
   hand-written reading. Markdown bullet lists are permitted ONLY for
   reproducing the pre-computed date lists. Everything else — analysis,
   advice, month narratives — must be paragraphs.
2. **Reason before advice, always.** Never hand out a recommendation without
   first showing the BaZi mechanism behind it. Wrong: "本月宜低调行事。"
   Right: "辛亥月的亥水冲您日支的巳火,动摇的是您日主的根基,因此这个月
   在重大决策上宜守不宜攻。" Every "宜/忌/建议" must be traceable to a stem,
   a branch interaction, a Ten God, or the client's favorable elements.
3. **Use the pre-computed facts as your skeleton** (Ten Gods, 冲合刑害, day
   lists) — interpret them deeply instead of listing them. Explain what each
   interaction touches in the client's life and WHY.
4. **No fragment-style bullet fields** like "- **主题**: ..." — weave theme,
   career, love, body into the narrative of each section instead.
"""


# ---------------------------------------------------------------------------
# Section prompts
# ---------------------------------------------------------------------------

def build_annual_specific_prompt(
    section_type: str,
    bazi_json: Dict[str, Any],
    context_str: str,
    previous_context: str,
    mode: str = 'gentle',
    lang_code: str = 'en',
) -> Dict[str, Any]:
    """Returns {'prompt': str, 'max_tokens': int} for the given annual section."""
    day_master = bazi_json.get('dayMaster', '')
    current_dayun = (bazi_json.get('currentDayun') or {}).get('ganZhi', 'N/A')

    year_frame = f"""
### ⚠ SCOPE ANCHOR — THE {ANNUAL_YEAR_GANZHI} YEAR ONLY ⚠
This chapter belongs to a dedicated **{ANNUAL_YEAR} Year-Ahead report**.
The year runs {ALMANAC_2027_MONTHS[0]['start']} → {ALMANAC_2027_MONTHS[-1]['end']}
(from 立春 {ANNUAL_YEAR} to the eve of 立春 {ANNUAL_YEAR + 1}).
Everything you write must be scoped to THIS year. Do not drift into other years
except for brief context. Never invent calendar dates — every date you mention
must come from the tables provided below.

{annual_month_table()}

{year_pillar_relation(bazi_json)}

{STYLE_RULES}
"""

    tone = ("温暖鼓励但要具体,先讲清命理机制再给方向,像一位资深师傅在给客户写信。"
            if mode == 'gentle' else
            "传统命理师直言风格,吉凶都明说,但每个判断都要先给出干支层面的依据,每个风险配化解方法与更好的时机。")

    if section_type == 'overview':
        prompt = f"""
## TASK: Chapter 1 — {ANNUAL_YEAR_GANZHI} {ANNUAL_YEAR} × This Chart: The Year Verdict
{year_frame}
{month_pillar_analysis(bazi_json)}

### COMPLETE CHART DATA:
{context_str}

### WHAT THIS CHAPTER MUST COVER (in flowing prose, at least 2,500 words of
report language and no upper limit — go deeper rather than stopping short, but
never pad or repeat; use ## subheadings to breathe, but the body is paragraphs):

Open the year like a master unrolling a scroll: what kind of year 丁未 is in
itself (丁 fire riding on 未 earth — the imagery, the season, the pace), then
turn to THIS chart: how the 丁 stem lands on day master [{day_master}] (use the
pre-computed Ten God and explain, concretely, what that Ten God activates in
this person's life), and how the 未 branch engages the four pillars (use the
pre-computed relations; if there is a Tai Sui clash/meet, treat it seriously —
what it shakes, and equally what it opens).

Then set the year inside the client's current luck cycle [{current_dayun}]:
does the year amplify the decade's current, or run against it? What does that
tension or resonance feel like in lived experience?

Close with the year's verdict, argued not asserted: the single dominant
opportunity, the single dominant risk, the client's {ANNUAL_YEAR} keyword
(one phrase, justified from the analysis above), and the year's favorable
elements, colors and directions — each tied back to WHY they help this chart
in this particular year.

Tone: {tone}
"""
        return {'prompt': prompt, 'max_tokens': 16000}

    if section_type == 'career_wealth':
        prompt = f"""
## TASK: Chapter 2 — Career & Wealth in {ANNUAL_YEAR}
{year_frame}
{month_pillar_analysis(bazi_json)}

### PREVIOUS CHAPTERS (for consistency — do not contradict):
{previous_context}

### COMPLETE CHART DATA:
{context_str}

### WHAT THIS CHAPTER MUST COVER (flowing prose, at least 2,500 words of report
language and no upper limit — go deeper rather than stopping short, but never
pad or repeat; ## subheadings allowed, body is paragraphs):

Begin from the mechanism: which Ten Gods govern career and wealth for THIS
day master, and what 丁未 does to them this year — then let every judgment
grow out of that. Walk through the year's wealth arc (when it swells, when it
thins, and the stem/branch reason for each turn), naming the specific months
from the table and quoting their pre-computed interactions as evidence.

Cover, woven into the narrative rather than listed: whether this is a year to
change jobs (and in which months the door actually opens); whether starting
or expanding a business suits this chart this year, with the months that
favor it and the ones that punish it; visibility/promotion windows; and the
investment posture the chart can afford this year — aggressive, selective or
defensive — argued from the strength of the wealth stars, never asserted.

End with a short strategic passage: how a person with this chart should
sequence their career moves across the year, so the reader closes the chapter
knowing not just WHAT to do but WHY the timing is theirs.

Tone: {tone}
"""
        return {'prompt': prompt, 'max_tokens': 16000}

    if section_type == 'love_family':
        prompt = f"""
## TASK: Chapter 3 — Love, Marriage & Family in {ANNUAL_YEAR}
{year_frame}
{month_pillar_analysis(bazi_json)}

### PREVIOUS CHAPTERS (for consistency — do not contradict):
{previous_context}

### COMPLETE CHART DATA:
{context_str}

### WHAT THIS CHAPTER MUST COVER (flowing prose, at least 2,200 words of report
language and no upper limit — go deeper rather than stopping short, but never
pad or repeat; ## subheadings allowed, body is paragraphs):

Start from the spouse palace and the romance stars of THIS chart: does 丁未
touch them — through the year stem's Ten God, through the 未 branch's
relations with the four pillars (use the pre-computed facts), through the
month pillars that clash or combine with the spouse palace during the year?
Name those months and explain the mechanism before describing the experience.

For a single reader: when meaningful encounters become likely and why those
months carry that quality. For a committed reader: where the pressure months
fall (and what the clash actually stresses — communication, family duty,
distance), and where the harmony months fall. If the year suits engagement or
marriage registration, argue it from the chart and point to the months; the
precise DAY selection belongs to Chapter 5, so refer forward to it.

Then family: parents, children, the household's energy this year, whether
moving or major family decisions suit this year and when. Close with guidance
that flows from everything above — reasons first, always.

Tone: {tone}
"""
        return {'prompt': prompt, 'max_tokens': 16000}

    if section_type == 'health_wellness':
        prompt = f"""
## TASK: Chapter 4 — Health, Balance & Home Energy in {ANNUAL_YEAR}
{year_frame}
{flying_stars_block()}

### PREVIOUS CHAPTERS (for consistency — do not contradict):
{previous_context}

### COMPLETE CHART DATA:
{context_str}

### WHAT THIS CHAPTER MUST COVER (flowing prose, at least 2,000 words of report
language and no upper limit — go deeper rather than stopping short, but never
pad or repeat; ## subheadings allowed, body is paragraphs):

Reason from the five elements: 丁未 adds fire and dry earth to this chart —
which of the client's elements does that parch, which organ systems (in the
TCM five-element sense) carry the year's load, and in which months does the
pressure peak (tie to the month table). Wellness framing only — no medical
predictions, no disease claims.

Then the seasons: how spring, summer, autumn and winter of {ANNUAL_YEAR} each
treat this chart, and the living adjustments (sleep, food energetics, pace,
exercise) that fit each season's element — always explaining why this remedy
suits this chart, not generic health advice.

Then the home: using the FIXED flying-star data above, which sectors to keep
quiet and which to activate this year, chosen through the lens of this
client's favorable elements; practical remedies (colors, materials, plants,
habits) with their reasoning. Close with the rhythm of the year in one
flowing passage — when to push the body, when to restore it.

Tone: {tone}
"""
        return {'prompt': prompt, 'max_tokens': 16000}

    if section_type == 'monthly':
        prompt = f"""
## TASK: Chapter 5 — The 12 Months of {ANNUAL_YEAR}, Decoded Month by Month
{year_frame}
{month_pillar_analysis(bazi_json)}

{personal_calendar(bazi_json, lang_code)}

### PREVIOUS CHAPTERS (for consistency — do not contradict):
{previous_context}

### COMPLETE CHART DATA:
{context_str}

### REQUIRED SHAPE — for EACH of the 12 months:

### 第N个月:{{gregorian range}} | {{month pillar}}月   (header in report language)

Then 2-4 paragraphs of connected prose (NOT bullet fields) that must:

1. **Open with the mechanism**: what this month's stem is to the day master
   (use the pre-computed Ten God) and what the month branch does to the four
   pillars (use the pre-computed 冲/合/刑/害 facts). Explain what that
   specific interaction touches — which pillar, which life domain, and why.
2. **Then the lived month**: career and money, love and people, body and
   mind — woven as narrative that follows FROM the mechanism, not as
   separate labeled fields. A month with a clash on the day pillar reads
   differently from one with a combine on the hour pillar; make that felt.
3. **Close with timing**: reproduce this month's pre-computed personal day
   list as a short bullet list — dates, day pillars and uses EXACTLY as
   provided (they are already in the report language). If the month has
   caution days, name them and say what to defer. If the list is empty, say
   plainly this is a consolidation month and what to use it for instead.

### HARD RULES
1. The day lists were personally computed for this client — reproduce dates
   EXACTLY; never add, drop, translate into another language, or invent dates.
2. Bullet lists are allowed ONLY for the date lists. All analysis is prose.
3. Every month gets its own section — no skipping, no merging, all 12.
4. Do not open the chapter with a long preamble — one short paragraph, then
   straight into Month 1.

Tone: {tone}
"""
        return {'prompt': prompt, 'max_tokens': 30000}

    if section_type == 'cheatsheet':
        prompt = f"""
## TASK: Chapter 6 — Your {ANNUAL_YEAR} Pocket Card (one-page cheat sheet)
{year_frame}

### PREVIOUS CHAPTERS (your ONLY source — distill, do not invent new claims):
{previous_context}

### REQUIRED STRUCTURE — this chapter is the ONE exception where a compact,
scannable layout is wanted (it is a pocket card). Keep it under ~600 words:

# Your {ANNUAL_YEAR} at a Glance
- **Year keyword** (from Chapter 1, one phrase + one-line reason)
- **Three things to DO this year** — each with its best months AND the
  one-line BaZi reason (e.g. "9月申金合日支巳火" style, in report language)
- **Three things NOT to do this year** — each with the months to avoid and
  the one-line reason
- **Top 5 dates of the year** (the strongest from Chapter 5's personal
  calendar — dates only, one-line use + reason each)
- **Lucky elements / colors / directions** (one line)
- **The one sentence to remember all year**

### HARD RULES
- Everything must trace back to the previous chapters. This is a distillation,
  not new analysis. Every line still carries its reason — even here, no bare
  commands.
"""
        return {'prompt': prompt, 'max_tokens': 8000}

    raise ValueError(f"Unknown annual section type: {section_type}")
