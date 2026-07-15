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
    filtered against their own chart branches (days clashing the client's
    day/year branch are excluded; days combining with the day branch are
    flagged), and month-level clash/combine hits are pre-computed.
"""

from typing import Dict, Any, List

from almanac_2027 import (
    ANNUAL_YEAR,
    ANNUAL_YEAR_GANZHI,
    ALMANAC_2027_MONTHS,
    ALMANAC_2027_DAYS,
)

# ---------------------------------------------------------------------------
# Branch interaction tables (六冲 / 六合)
# ---------------------------------------------------------------------------

LIU_CHONG = {'子': '午', '丑': '未', '寅': '申', '卯': '酉', '辰': '戌', '巳': '亥',
             '午': '子', '未': '丑', '申': '寅', '酉': '卯', '戌': '辰', '亥': '巳'}

LIU_HE = {'子': '丑', '丑': '子', '寅': '亥', '亥': '寅', '卯': '戌', '戌': '卯',
          '辰': '酉', '酉': '辰', '巳': '申', '申': '巳', '午': '未', '未': '午'}

# 2027 annual flying stars (Period 9, annual star 9 in the center; standard
# Lo Shu flight path center→NW→W→NE→S→N→SW→E→SE).
FLYING_STARS_2027 = {
    'center': 9, 'NW': 1, 'W': 2, 'NE': 3, 'S': 4,
    'N': 5,      # 五黄 Five Yellow — misfortune star: keep quiet, no groundbreaking
    'SW': 6, 'E': 7, 'SE': 8,
}

TAG_LABELS = {
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

ANNUAL_SECTION_TYPES = [
    'overview', 'career_wealth', 'love_family',
    'health_wellness', 'monthly', 'cheatsheet',
]


# ---------------------------------------------------------------------------
# Chart helpers
# ---------------------------------------------------------------------------

def get_user_branches(bazi_json: Dict[str, Any]) -> Dict[str, str]:
    """{'year': 亥, 'month': ..., 'day': ..., 'hour': ...} from the chart."""
    pillars = bazi_json.get('pillars', {}) or {}
    out = {}
    for key in ('year', 'month', 'day', 'hour'):
        gz = (pillars.get(key) or {}).get('ganZhi') or ''
        if len(gz) >= 2:
            out[key] = gz[1]
    return out


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


def month_interactions(user_branches: Dict[str, str]) -> str:
    """Pre-computed month-branch clashes/combines against the client's pillars."""
    lines = ["### Pre-computed month interactions with the client's chart "
             "(ONLY these are confirmed — do not invent others)\n"]
    hits = []
    for m in ALMANAC_2027_MONTHS:
        mz = m['zhi']
        for pk, uz in user_branches.items():
            if LIU_CHONG.get(mz) == uz:
                hits.append(f"- Month {m['idx']} ({m['start']} ~ {m['end']}, "
                            f"{m['ganzhi']}): **{mz}-{uz} CLASH (冲)** with the "
                            f"client's {pk} branch — turbulence in that pillar's domain.")
            elif LIU_HE.get(mz) == uz:
                hits.append(f"- Month {m['idx']} ({m['start']} ~ {m['end']}, "
                            f"{m['ganzhi']}): {mz}-{uz} combine (六合) with the "
                            f"client's {pk} branch — supportive alignment.")
    if not hits:
        hits.append("- No direct month-branch clash or combine with this chart in "
                    f"{ANNUAL_YEAR} — a comparatively smooth calendar structure.")
    lines.extend(hits)
    return "\n".join(lines)


def year_pillar_relation(user_branches: Dict[str, str]) -> str:
    """How 丁未 itself lands on this chart (branch-level, pre-computed)."""
    notes = []
    for pk, uz in user_branches.items():
        if LIU_CHONG.get('未') == uz:
            notes.append(f"- The 未 year branch **CLASHES (冲)** the client's {pk} "
                         f"branch {uz} — this is a 冲太岁 year for that pillar.")
        elif LIU_HE.get('未') == uz:
            notes.append(f"- The 未 year branch combines (六合) with the client's "
                         f"{pk} branch {uz}.")
        elif uz == '未':
            notes.append(f"- The client's {pk} branch IS 未 — 值太岁 (meeting the "
                         f"Tai Sui) this year.")
    if not notes:
        notes.append("- 未 has no direct clash/combine/meet with this chart's "
                     "branches; read the year through stems and elements instead.")
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


def personal_calendar(bazi_json: Dict[str, Any], per_month: int = 8) -> str:
    """Markdown: for each month, the client's personally favorable days
    (generic almanac-good days minus days clashing their chart), plus the
    days they specifically must avoid (days clashing their day branch)."""
    ub = get_user_branches(bazi_json)
    day_branch = ub.get('day', '')
    lines = [
        "### THE CLIENT'S PERSONAL 2027 DAY CALENDAR",
        "(pre-computed from the traditional almanac AND this client's own chart: "
        "generically auspicious days that clash this client's day/year branch have "
        "already been REMOVED; 'personal caution days' are days whose branch clashes "
        "the client's day branch. Use these lists verbatim — never invent dates.)\n",
    ]
    for m in ALMANAC_2027_MONTHS:
        mdays = [d for d in ALMANAC_2027_DAYS if m['start'] <= d['d'] <= m['end']]
        good = [d for d in mdays if d['tags'] and _day_ok_for_user(d, ub)]
        # prefer days that ALSO combine with the client's day branch
        good.sort(key=lambda d: (0 if LIU_HE.get(d['zhi']) == day_branch else 1, d['d']))
        pick = sorted(good[:per_month], key=lambda d: d['d'])
        caution = [d['d'] for d in mdays
                   if day_branch and LIU_CHONG.get(d['zhi']) == day_branch]
        lines.append(f"\n**Month {m['idx']} — {m['start']} ~ {m['end']} "
                     f"({m['ganzhi']}月)**")
        if pick:
            for d in pick:
                star = ' ★(combines with the client\'s day branch)' \
                    if LIU_HE.get(d['zhi']) == day_branch else ''
                tags = ', '.join(TAG_LABELS[t] for t in d['tags'])
                lines.append(f"- {d['d']} ({d['gz']}日): good for {tags}{star}")
        else:
            lines.append("- (no strongly favorable personal days this month — "
                         "advise consolidation)")
        if caution:
            lines.append(f"- ⚠ personal caution days (clash the client's day "
                         f"branch): {', '.join(caution)}")
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
# Section prompts
# ---------------------------------------------------------------------------

def build_annual_specific_prompt(
    section_type: str,
    bazi_json: Dict[str, Any],
    context_str: str,
    previous_context: str,
    mode: str = 'gentle',
) -> Dict[str, Any]:
    """Returns {'prompt': str, 'max_tokens': int} for the given annual section."""
    ub = get_user_branches(bazi_json)
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

{year_pillar_relation(ub)}
"""

    tone = ("温暖鼓励但要具体,给出方向感与可执行的时机建议。"
            if mode == 'gentle' else
            "传统命理师直言风格,吉凶都明说,每个风险配化解方法与更好的时机。")

    if section_type == 'overview':
        prompt = f"""
## TASK: Chapter 1 — {ANNUAL_YEAR_GANZHI} {ANNUAL_YEAR} × This Chart: The Year Verdict
{year_frame}
{month_interactions(ub)}

### COMPLETE CHART DATA:
{context_str}

### REQUIRED STRUCTURE
# Part 1: What {ANNUAL_YEAR_GANZHI} Means for This Chart
- The 丁 fire stem and 未 earth branch: how each lands on day master [{day_master}]
- Which Ten God the year represents for this client, and the life theme that activates
- Tai Sui status this year (值/冲/合/none — use the pre-computed notes above)
# Part 2: The Year Inside the Luck Cycle
- Current 大运 [{current_dayun}]: does {ANNUAL_YEAR} reinforce it or fight it?
# Part 3: The Year's Verdict in One Page
- The single dominant opportunity of {ANNUAL_YEAR}
- The single dominant risk of {ANNUAL_YEAR}
- The client's {ANNUAL_YEAR} keyword (one phrase), with justification
- Lucky elements / colors / directions for THIS year specifically

Tone: {tone}
"""
        return {'prompt': prompt, 'max_tokens': 16000}

    if section_type == 'career_wealth':
        prompt = f"""
## TASK: Chapter 2 — Career & Wealth Battle Map for {ANNUAL_YEAR}
{year_frame}
{month_interactions(ub)}

### PREVIOUS CHAPTERS (for consistency — do not contradict):
{previous_context}

### COMPLETE CHART DATA:
{context_str}

### REQUIRED STRUCTURE
# Part 1: The {ANNUAL_YEAR} Wealth Curve
- Overall wealth trend of the year for this chart (rising/falling/choppy) and why
- The 2-3 strongest wealth months and the 1-2 weakest (pick FROM the month table)
# Part 2: Career Verdicts
- Job change this year: favorable or not, and WHICH months (from the table)
- Starting/expanding a business: green-light or red-light months
- Promotion/visibility windows
# Part 3: Money Discipline
- Investment posture for {ANNUAL_YEAR} (aggressive/selective/defensive) tied to the chart
- Months to absolutely avoid major financial commitments
# Part 4: Action Checklist
- 5 concrete career/wealth actions with their best timing windows

Tone: {tone}
"""
        return {'prompt': prompt, 'max_tokens': 16000}

    if section_type == 'love_family':
        prompt = f"""
## TASK: Chapter 3 — Love, Marriage & Family in {ANNUAL_YEAR}
{year_frame}
{month_interactions(ub)}

### PREVIOUS CHAPTERS (for consistency — do not contradict):
{previous_context}

### COMPLETE CHART DATA:
{context_str}

### REQUIRED STRUCTURE
# Part 1: Romance Activation
- Does {ANNUAL_YEAR_GANZHI} activate the spouse palace / romance stars of this chart?
- For singles: the months when meaningful encounters are most likely (from the table)
- For committed clients: pressure months vs harmony months for the relationship
# Part 2: Marriage & Milestones
- Is {ANNUAL_YEAR} a favorable year for engagement / marriage registration / wedding
  for THIS chart? Which months? (cross-reference the pre-computed interactions)
# Part 3: Family & Home
- Parents, children, household energy this year
- Whether moving home / major family decisions suit this year, and when
# Part 4: Guidance
- 3-5 concrete relationship actions with timing

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

### REQUIRED STRUCTURE
# Part 1: The Body in {ANNUAL_YEAR_GANZHI}
- Which elemental organ systems this chart should watch THIS year (未 earth + 丁 fire
  pressure on the chart's weak elements) — wellness framing, no medical predictions
- The seasons/months of the year needing the most rest (from the month table)
# Part 2: Seasonal Adjustment Protocol
- Season-by-season (spring/summer/autumn/winter) lifestyle & element adjustments
# Part 3: {ANNUAL_YEAR} Home Energy Map
- Using the FIXED flying-star data above: which sectors of the home to keep quiet,
  which to activate, tailored to this client's favorable elements
- Simple remedies (colors, materials, plants, habits) — practical, no superstition dump
# Part 4: The Year's Wellness Routine
- A compact monthly-rhythm checklist

Tone: {tone}
"""
        return {'prompt': prompt, 'max_tokens': 16000}

    if section_type == 'monthly':
        prompt = f"""
## TASK: Chapter 5 — The 12 Months of {ANNUAL_YEAR}, Decoded Month by Month
{year_frame}
{month_interactions(ub)}

{personal_calendar(bazi_json)}

### PREVIOUS CHAPTERS (for consistency — do not contradict):
{previous_context}

### COMPLETE CHART DATA:
{context_str}

### REQUIRED STRUCTURE — for EACH of the 12 months, exactly this format:

### Month {{idx}}: {{gregorian range}} | {{month pillar}}月
- **Theme**: 1-2 sentence energy verdict for this client
- **Career & Money**: the concrete read for this month
- **Love & People**: the concrete read for this month
- **Body & Mind**: one practical note
- **Your best days**: reproduce this month's pre-computed personal day list
  (dates + what each is good for). If the list is empty, say this is a
  consolidation month.
- **Handle with care**: the month's personal caution days (if any), plus what
  to defer

### HARD RULES
1. The day lists above were personally computed for this client — reproduce the
   dates EXACTLY as given; never add, drop, or invent dates.
2. Months flagged in the interactions section must explicitly mention the clash
   or combine and what it means for that month's decisions.
3. Every month gets its own section — no skipping, no merging.

Tone: {tone}
"""
        return {'prompt': prompt, 'max_tokens': 24000}

    if section_type == 'cheatsheet':
        prompt = f"""
## TASK: Chapter 6 — Your {ANNUAL_YEAR} Pocket Card (one-page cheat sheet)
{year_frame}

### PREVIOUS CHAPTERS (your ONLY source — distill, do not invent new claims):
{previous_context}

### REQUIRED STRUCTURE — keep the whole chapter SHORT and scannable:
# Your {ANNUAL_YEAR} at a Glance
- **Year keyword**: (from Chapter 1)
- **Three things to DO this year** (with their best months)
- **Three things NOT to do this year** (with the months to especially avoid)
- **Top 5 dates of the year** (pick the strongest from the personal calendar
  in Chapter 5 — dates only, with one-line reasons)
- **Lucky elements / colors / directions** (one line)
- **The one sentence to remember all year**

### HARD RULES
- Everything must trace back to the previous chapters. This is a distillation,
  not new analysis. Max ~600 words.
"""
        return {'prompt': prompt, 'max_tokens': 8000}

    raise ValueError(f"Unknown annual section type: {section_type}")
