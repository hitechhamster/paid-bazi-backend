# -*- coding: utf-8 -*-
"""
fengshui.py — Personal Feng Shui (命理风水 / 用神补救) report: prompt builders.

Used by app.py's /api/generate-fengshui-section endpoint. This is the
"person's half" of feng shui: everything is derived from the birth chart
(用神喜忌 + 调候), NOT from a house survey. No compass, no floor plan — the
report prescribes what THIS chart needs from its environment.

Discipline (mirrors the 2027 almanac's calendar discipline):
  - Element↔direction↔colour↔material mappings, the 调候 (climate) verdict
    hint, and the zodiac-clash / annual Tai Sui directions are PRE-COMPUTED
    here in code. The AI interprets them into a master's prose; it never
    invents a mapping.
  - NEVER issues a house-fixed verdict ("your north sector is bad"). It only
    ever says "your chart needs / must avoid element X -> so in the space you
    touch, feed / avoid it this way." This keeps it orthogonal to (never in
    conflict with) 八宅 / 玄空 house schools.
"""

from datetime import datetime, date
from typing import Dict, Any, List

# ---------------------------------------------------------------------------
# Five-element static maps (Later-Heaven bagua directions, colours, materials)
# ---------------------------------------------------------------------------

# element -> {directions, colours, materials, shapes, water/plants notes}
ELEMENT_MAP = {
    'wood':  {'zh': '木',
              'dirs_en': 'East, Southeast', 'dirs_zh': '东、东南',
              'colours_en': 'green, teal, jade', 'colours_zh': '绿、青、翠',
              'materials_en': 'wood, bamboo, rattan, tall living plants', 'materials_zh': '木材、竹、藤、高大绿植',
              'shapes_en': 'tall rectangular, columnar', 'shapes_zh': '长方、直立',
              'number': '3, 4'},
    'fire':  {'zh': '火',
              'dirs_en': 'South', 'dirs_zh': '南',
              'colours_en': 'red, purple, warm orange', 'colours_zh': '红、紫、暖橙',
              'materials_en': 'candles, warm lighting, leather, wool', 'materials_zh': '烛光、暖光、皮革、羊毛',
              'shapes_en': 'triangular, pointed, star', 'shapes_zh': '三角、尖形',
              'number': '9'},
    'earth': {'zh': '土',
              'dirs_en': 'Southwest, Northeast, center', 'dirs_zh': '西南、东北、中宫',
              'colours_en': 'yellow, beige, terracotta, brown', 'colours_zh': '黄、米、赭、棕',
              'materials_en': 'ceramic, clay, crystal, stone', 'materials_zh': '陶瓷、黏土、水晶、石',
              'shapes_en': 'flat square, cubic', 'shapes_zh': '方形、扁平',
              'number': '2, 5, 8'},
    'metal': {'zh': '金',
              'dirs_en': 'West, Northwest', 'dirs_zh': '西、西北',
              'colours_en': 'white, gold, silver, grey', 'colours_zh': '白、金、银、灰',
              'materials_en': 'metal, brass, copper, round mirrors', 'materials_zh': '金属、铜、圆镜',
              'shapes_en': 'round, spherical, arched', 'shapes_zh': '圆形、弧形',
              'number': '6, 7'},
    'water': {'zh': '水',
              'dirs_en': 'North', 'dirs_zh': '北',
              'colours_en': 'black, deep blue, charcoal', 'colours_zh': '黑、深蓝、墨',
              'materials_en': 'water features, aquariums, glass, mirrors, flowing shapes', 'materials_zh': '水景、鱼缸、玻璃、镜、流线',
              'shapes_en': 'wavy, irregular, flowing', 'shapes_zh': '波浪、流线、不规则',
              'number': '1'},
}

STEM_ELEMENT = {
    '甲': 'wood', '乙': 'wood', '丙': 'fire', '丁': 'fire', '戊': 'earth',
    '己': 'earth', '庚': 'metal', '辛': 'metal', '壬': 'water', '癸': 'water',
}
BRANCH_ELEMENT = {
    '寅': 'wood', '卯': 'wood', '巳': 'fire', '午': 'fire',
    '辰': 'earth', '戌': 'earth', '丑': 'earth', '未': 'earth',
    '申': 'metal', '酉': 'metal', '亥': 'water', '子': 'water',
}
SHENG = {'wood': 'fire', 'fire': 'earth', 'earth': 'metal', 'metal': 'water', 'water': 'wood'}
KE = {'wood': 'earth', 'earth': 'water', 'water': 'fire', 'fire': 'metal', 'metal': 'wood'}
EL_ZH = {'wood': '木', 'fire': '火', 'earth': '土', 'metal': '金', 'water': '水'}
EL_EN = {'wood': 'Wood', 'fire': 'Fire', 'earth': 'Earth', 'metal': 'Metal', 'water': 'Water'}

# Zodiac (year branch) clash direction: branch -> (clashing branch, its direction)
BRANCH_DIR = {
    '子': ('N', '北'), '丑': ('NNE', '东北偏北'), '寅': ('ENE', '东北偏东'), '卯': ('E', '东'),
    '辰': ('ESE', '东南偏东'), '巳': ('SSE', '东南偏南'), '午': ('S', '南'), '未': ('SSW', '西南偏南'),
    '申': ('WSW', '西南偏西'), '酉': ('W', '西'), '戌': ('WNW', '西北偏西'), '亥': ('NNW', '西北偏北'),
}
LIU_CHONG = {'子': '午', '丑': '未', '寅': '申', '卯': '酉', '辰': '戌', '巳': '亥',
             '午': '子', '未': '丑', '申': '寅', '酉': '卯', '戌': '辰', '亥': '巳'}

# Annual afflictions are computed per year from the year's stem/branch — no
# hard-coded year list, so the product never expires.
TIAN_GAN = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸']
DI_ZHI = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥']

# Three Killings (三煞): by the year branch's trine (三合局), the killings sit in
# the opposite cardinal triad. Keyed by year branch -> (block name zh, block en).
SANSHA = {
    ('申', '子', '辰'): ('南方三煞(巳午未)', 'South (Si-Wu-Wei)'),   # water trine -> south
    ('寅', '午', '戌'): ('北方三煞(亥子丑)', 'North (Hai-Zi-Chou)'),  # fire trine -> north
    ('亥', '卯', '未'): ('西方三煞(申酉戌)', 'West (Shen-You-Xu)'),   # wood trine -> west
    ('巳', '酉', '丑'): ('东方三煞(寅卯辰)', 'East (Yin-Mao-Chen)'),  # metal trine -> east
}

# 9-palace annual star -> its Lo Shu direction. 5-Yellow & 2-Black positions
# move each year with the annual central star. Annual central star for a
# solar year Y (Period 9 era formula, holds for the modern range):
#   center = (11 - (sum of digits of Y) reduced to 1..9) ... we use the standard
#   table via: c = (9 - ((Y - 2017) % 9)) mapped; simpler: precompute per year.
# Annual stars always fly FORWARD along the Lo Shu path, starting from the
# central star. Index k = (star - center) mod 9 gives the palace on this path.
FLIGHT_ZH = ['中宫', '西北', '西', '东北', '南', '北', '西南', '东', '东南']
FLIGHT_EN = ['center', 'NW', 'W', 'NE', 'S', 'N', 'SW', 'E', 'SE']


def _year_ganzhi(y):
    """Solar-year ganzhi (post-LiChun). 1984 = 甲子."""
    off = y - 1984
    return TIAN_GAN[off % 10] + DI_ZHI[off % 12]


def _annual_central_star(y):
    """Annual central Lo Shu star for solar year y (descending 9->1 cycle)."""
    return (11 - (y % 9)) % 9 or 9


def _star_direction(star, y):
    """Where a given star flies in year y (forward-flying annual chart)."""
    center = _annual_central_star(y)
    k = (star - center) % 9
    return FLIGHT_ZH[k], FLIGHT_EN[k]


def annual_affliction(y):
    """Compute one year's affliction directions from its ganzhi. Never hard-coded."""
    gz = _year_ganzhi(y)
    yb = gz[1]
    taisui_dir = BRANCH_DIR.get(yb, ('', ''))
    suipo_b = LIU_CHONG.get(yb, '')
    suipo_dir = BRANCH_DIR.get(suipo_b, ('', ''))
    sansha_zh = sansha_en = ''
    for trine, (zh, en) in SANSHA.items():
        if yb in trine:
            sansha_zh, sansha_en = zh, en
            break
    wuhuang = _star_direction(5, y)
    erhei = _star_direction(2, y)
    return {
        'year': gz, 'branch': yb,
        'taisui_zh': f'{taisui_dir[1]}({yb})', 'taisui_en': taisui_dir[0],
        'suipo_zh': f'{suipo_dir[1]}({suipo_b})', 'suipo_en': suipo_dir[0],
        'sansha_zh': sansha_zh, 'sansha_en': sansha_en,
        'wuhuang_zh': f'五黄在{wuhuang[0]}', 'wuhuang_en': f'5-Yellow at {wuhuang[1]}',
        'erhei_zh': f'二黑在{erhei[0]}', 'erhei_en': f'2-Black at {erhei[1]}',
    }


def _year_element_pair(y):
    """(stem element, branch element) of the solar year — for the favour clash read."""
    gz = _year_ganzhi(y)
    return STEM_ELEMENT.get(gz[0], ''), BRANCH_ELEMENT.get(gz[1], '')

FENGSHUI_SECTION_TYPES = [
    'constitution', 'directions', 'rooms', 'wearable', 'annual', 'cheatsheet',
]


# ---------------------------------------------------------------------------
# Chart-derived helpers
# ---------------------------------------------------------------------------

def _pillars(bazi_json):
    return bazi_json.get('pillars', {}) or {}


def get_element_tally(bazi_json: Dict[str, Any]) -> Dict[str, int]:
    """Count five elements across the 8 chart characters (stems+branches)."""
    tally = {e: 0 for e in ('wood', 'fire', 'earth', 'metal', 'water')}
    fe = bazi_json.get('fiveElements') or {}
    if fe and sum(fe.values()) > 0:
        for e in tally:
            tally[e] = fe.get(e, 0)
        return tally
    for k in ('year', 'month', 'day', 'hour'):
        gz = (_pillars(bazi_json).get(k) or {}).get('ganZhi', '')
        if len(gz) >= 2:
            if gz[0] in STEM_ELEMENT:
                tally[STEM_ELEMENT[gz[0]]] += 1
            if gz[1] in BRANCH_ELEMENT:
                tally[BRANCH_ELEMENT[gz[1]]] += 1
    return tally


def get_day_master_element(bazi_json: Dict[str, Any]) -> str:
    dm = bazi_json.get('dayMaster') or ''
    if dm and dm[0] in STEM_ELEMENT:
        return STEM_ELEMENT[dm[0]]
    gz = (_pillars(bazi_json).get('day') or {}).get('ganZhi', '')
    return STEM_ELEMENT.get(gz[0], '') if gz else ''


def get_birth_month_branch(bazi_json: Dict[str, Any]) -> str:
    gz = (_pillars(bazi_json).get('month') or {}).get('ganZhi', '')
    return gz[1] if len(gz) >= 2 else ''


def climate_hint(bazi_json: Dict[str, Any]) -> Dict[str, str]:
    """调候: crude season/climate read from the month branch. A hint for the AI,
    which makes the final call from the full chart."""
    mb = get_birth_month_branch(bazi_json)
    winter = {'亥', '子', '丑'}       # cold, needs warmth (fire)
    summer = {'巳', '午', '未'}       # hot, needs moisture (water)
    spring = {'寅', '卯', '辰'}
    autumn = {'申', '酉', '戌'}
    if mb in winter:
        return {'season_en': 'winter (cold)', 'season_zh': '冬(寒)',
                'need_en': 'warmth — Fire, and warm light/colour',
                'need_zh': '暖——需火,宜暖光暖色'}
    if mb in summer:
        return {'season_en': 'summer (hot)', 'season_zh': '夏(燥热)',
                'need_en': 'moisture — Water, cool tones, flow',
                'need_zh': '润——需水,宜清凉流动'}
    if mb in spring:
        return {'season_en': 'spring (wood rising)', 'season_zh': '春(木旺)',
                'need_en': 'balance — watch excess Wood, temper with Metal/Fire',
                'need_zh': '平——木旺,酌情以金火调'}
    if mb in autumn:
        return {'season_en': 'autumn (metal strong)', 'season_zh': '秋(金旺)',
                'need_en': 'balance — watch excess Metal, warm with Fire/Wood',
                'need_zh': '平——金旺,酌情以火木暖'}
    return {'season_en': 'transitional', 'season_zh': '过渡',
            'need_en': 'balance across the elements', 'need_zh': '五行调和'}


def favour_hint(bazi_json: Dict[str, Any]) -> Dict[str, Any]:
    """Heuristic favourable/unfavourable elements from tally + day master.
    A STARTING POINT for the AI (which weighs season, roots, combinations).
    Rule of thumb: the day-master element and the element that produces it are
    supportive when the DM is weak; the elements that drain/control it help
    when the DM is strong. We give the AI both the tally and the mechanics."""
    tally = get_element_tally(bazi_json)
    dm = get_day_master_element(bazi_json)
    if not dm:
        return {'tally': tally, 'dm': '', 'note': 'day master unknown'}
    supporter = [e for e, prod in SHENG.items() if prod == dm]  # element that produces DM
    same = dm
    drain = SHENG[dm]                                           # DM produces this (output)
    wealth = KE[dm]                                             # DM controls this (wealth)
    officer = [e for e, t in KE.items() if t == dm]            # controls DM (pressure)
    dm_support_total = tally[dm] + (tally[supporter[0]] if supporter else 0)
    total = sum(tally.values()) or 1
    strong = dm_support_total > total * 0.45
    return {
        'tally': tally, 'dm': dm, 'strong': strong,
        'supporter': supporter[0] if supporter else '',
        'drain': drain, 'wealth': wealth,
        'officer': officer[0] if officer else '',
        'ratio': round(dm_support_total / total, 2),
    }


def _el_line(e, lang_code):
    m = ELEMENT_MAP[e]
    if lang_code in ('zh', 'zh-tw'):
        return (f"{EL_ZH[e]}: 方位 {m['dirs_zh']}; 颜色 {m['colours_zh']}; "
                f"材质 {m['materials_zh']}; 形状 {m['shapes_zh']}; 数字 {m['number']}")
    return (f"{EL_EN[e]}: directions {m['dirs_en']}; colours {m['colours_en']}; "
            f"materials {m['materials_en']}; shapes {m['shapes_en']}; numbers {m['number']}")


def element_reference_block(lang_code: str) -> str:
    zh = lang_code in ('zh', 'zh-tw')
    head = ("### 五行↔方位/颜色/材质 对照(固定常识,照用勿改)\n" if zh else
            "### Element ↔ direction / colour / material reference (fixed — use as given)\n")
    return head + "\n".join('- ' + _el_line(e, lang_code)
                            for e in ('wood', 'fire', 'earth', 'metal', 'water'))


def precomputed_facts(bazi_json: Dict[str, Any], lang_code: str) -> str:
    """The chart-derived facts the AI must reason FROM (not re-derive)."""
    zh = lang_code in ('zh', 'zh-tw')
    dm = get_day_master_element(bazi_json)
    fav = favour_hint(bazi_json)
    clim = climate_hint(bazi_json)
    tally = fav['tally']
    yb = (_pillars(bazi_json).get('year') or {}).get('ganZhi', '')
    year_branch = yb[1] if len(yb) >= 2 else ''
    clash_b = LIU_CHONG.get(year_branch, '')
    clash_dir = BRANCH_DIR.get(clash_b, ('', ''))

    lines = []
    if zh:
        lines.append("### 命盘预计算事实(据此推演,勿自行改动)")
        lines.append(f"- 日主五行:{EL_ZH.get(dm, '?')}")
        lines.append(f"- 五行统计:" + "、".join(f"{EL_ZH[e]}{tally[e]}" for e in tally))
        lines.append(f"- 日主强弱初判:{'偏强' if fav.get('strong') else '偏弱'}"
                     f"(日主+生我 占比 {fav.get('ratio')});喜忌须结合调候与月令定夺")
        lines.append(f"- 生我(印):{EL_ZH.get(fav.get('supporter'), '?')} | "
                     f"我生(食伤):{EL_ZH.get(fav.get('drain'), '?')} | "
                     f"我克(财):{EL_ZH.get(fav.get('wealth'), '?')} | "
                     f"克我(官杀):{EL_ZH.get(fav.get('officer'), '?')}")
        lines.append(f"- 调候:生于{clim['season_zh']},{clim['need_zh']}")
        if clash_b:
            lines.append(f"- 生肖年支{year_branch},六冲{clash_b},犯冲方位在{clash_dir[1]}"
                         f"(该方位宜静不宜大动)")
    else:
        lines.append("### PRE-COMPUTED CHART FACTS (reason FROM these; do not alter)")
        lines.append(f"- Day-master element: {EL_EN.get(dm, '?')}")
        lines.append("- Element tally: " + ", ".join(f"{EL_EN[e]} {tally[e]}" for e in tally))
        lines.append(f"- Rough strength: {'stronger' if fav.get('strong') else 'weaker'} "
                     f"(self+resource share {fav.get('ratio')}); final favour must weigh "
                     f"climate and month command")
        lines.append(f"- Resource(印): {EL_EN.get(fav.get('supporter'),'?')} | "
                     f"Output(食伤): {EL_EN.get(fav.get('drain'),'?')} | "
                     f"Wealth(财): {EL_EN.get(fav.get('wealth'),'?')} | "
                     f"Officer(官杀): {EL_EN.get(fav.get('officer'),'?')}")
        lines.append(f"- Climate (调候): born in {clim['season_en']}; needs {clim['need_en']}")
        if clash_b:
            lines.append(f"- Zodiac year branch {year_branch} clashes {clash_b}; the clash "
                         f"direction is {clash_dir[0]} — keep that direction calm, no major disturbance")
    return "\n".join(lines)


def window_years() -> List[int]:
    """The solar years the rolling ~24-month window from *today* covers.
    (This year + next; if we're already deep in the year, that's the pair that
    matters for a 24-month horizon.)"""
    y = datetime.utcnow().year
    return [y, y + 1]


def annual_block(bazi_json: Dict[str, Any], lang_code: str) -> str:
    """Per-year affliction directions (computed) + how each year's element
    energy pushes on THIS chart's favour — dynamic, never a fixed year list."""
    zh = lang_code in ('zh', 'zh-tw')
    fav = favour_hint(bazi_json)
    dm = fav.get('dm', '')
    years = window_years()
    head = ("### 流年方位煞与流年五行(据当前日期动态计算,照用):\n" if zh else
            "### Annual affliction directions + this-window years (computed live — use as given):\n")
    out = [head]
    for y in years:
        a = annual_affliction(y)
        se, be = _year_element_pair(y)  # stem/branch element of the year
        # how the year's dominant element relates to the chart's favour
        if zh:
            fav_note = ""
            if dm:
                yel = EL_ZH.get(se, '') + EL_ZH.get(be, '')
                fav_note = f" 本年五行偏{yel}"
            out.append(f"- {y}({a['year']}): 太岁在{a['taisui_zh']}、岁破在{a['suipo_zh']}、"
                       f"{a['sansha_zh']}、{a['wuhuang_zh']}、{a['erhei_zh']}——这些方位忌大动、忌久居,宜静宜化。"
                       f"{fav_note}(据此判断今年环境需给命主额外补强/克泄的五行)。")
        else:
            yel = f"{EL_EN.get(se,'')}/{EL_EN.get(be,'')}"
            out.append(f"- {y} ({a['year']}): Tai Sui {a['taisui_zh']}, Sui Po {a['suipo_zh']}, "
                       f"{a['sansha_zh']} San Sha, {a['wuhuang_en']}, {a['erhei_en']} — keep these "
                       f"directions quiet (no groundbreaking, no prolonged stays). Year element leans "
                       f"{yel} (judge how the year presses on this chart's favour and adjust the "
                       f"remedy's emphasis accordingly).")
    return "\n".join(out)


STYLE_RULES = """
### WRITING & DOCTRINE CONTRACT — NON-NEGOTIABLE

1. **Flowing master prose.** Connected paragraphs, a seasoned consultant's
   voice. Bullet lists ONLY for the compact reference/checklist items; all
   analysis and advice is prose.
2. **Reason before advice, always.** Never give a placement without first
   stating the chart mechanism: "your chart is short on Water and born in a
   hot summer month, so your day master is parched — therefore in your bedroom
   ..." Every colour, direction, object must trace to a favoured/avoided
   element or the climate verdict.
3. **NEVER issue a house verdict.** Do NOT say "your north sector is
   auspicious/inauspicious", do NOT flying-star or 八宅 the house. You read the
   PERSON. You say: "your chart needs / must avoid element X → so in the space
   you touch, feed it / avoid it like this." This is deliberate: it keeps the
   reading from ever contradicting a house-feng-shui school the reader may have
   read elsewhere.
4. **One honest line, once (not a disclaimer festival):** somewhere natural,
   note that this reading is the person's half of feng shui — it works from the
   chart, so the same room serves two people differently. Do not belabour it.
"""


def build_fengshui_prompt(section_type, bazi_json, context_str, previous_context,
                          mode='gentle', lang_code='en') -> Dict[str, Any]:
    zh = lang_code in ('zh', 'zh-tw')
    dm_el = get_day_master_element(bazi_json)
    facts = precomputed_facts(bazi_json, lang_code)
    ref = element_reference_block(lang_code)
    tone = ("温暖笃定,像一位深耕多年的师傅在给客户开方,先讲清命理机制再给具体布置。"
            if mode == 'gentle' else
            "传统师傅直言风格,喜忌明说,每条布置先给命理依据,再给可执行的做法。")

    frame = f"""
### SCOPE ANCHOR — PERSONAL FENG SHUI (命理风水 / 用神补救)
This is the person's half of feng shui: every recommendation is derived from
THIS birth chart, never from a house survey. No compass reading, no floor plan.

{facts}

{ref}

{STYLE_RULES}
"""

    if section_type == 'constitution':
        prompt = f"""
## TASK: Chapter 1 — Your Elemental Constitution (五行体质·喜忌调候)
{frame}
### COMPLETE CHART DATA:
{context_str}

Write ~1,500-2,000 words of flowing {('中文' if zh else 'English')} prose. Establish
the whole prescription's foundation: read this chart's five-element balance and
the day master [{EL_EN.get(dm_el,'?')}]; deliver the FAVOUR VERDICT — which
elements this person should surround themselves with and which to minimise —
arguing it from strength, the resource/output/wealth/officer structure, AND the
climate (调候) note. Make the verdict unambiguous: name the 1-2 elements this
home should be rich in, and the 1-2 to keep sparse. Everything in later chapters
hangs on this call, so justify it like a master, not a calculator.

Tone: {tone}
"""
        return {'prompt': prompt, 'max_tokens': 15000}

    if section_type == 'directions':
        prompt = f"""
## TASK: Chapter 2 — Your Directions (喜用方位与回避)
{frame}
### PREVIOUS CHAPTERS (do not contradict the favour verdict):
{previous_context}
### COMPLETE CHART DATA:
{context_str}

Write ~1,500-2,000 words of prose. Translate the favour verdict into directions
the reader can actually use WITHOUT a compass — phone-compass-level guidance:
which directions to face and dwell toward (the ones carrying the favoured
elements), which to de-emphasise (the avoided elements), and the zodiac-clash
direction to keep calm this year (from the facts). Explain the mechanism each
time. Frame directions as "face this way when you work / sleep with your head
toward / place your desk toward" — usable, not abstract. Never label a sector of
the house good or bad; speak only of the elements the reader should move toward.

Tone: {tone}
"""
        return {'prompt': prompt, 'max_tokens': 15000}

    if section_type == 'rooms':
        prompt = f"""
## TASK: Chapter 3 — Room-by-Room Prescription (逐房间处方)
{frame}
### PREVIOUS CHAPTERS (stay consistent with the favour verdict):
{previous_context}
### COMPLETE CHART DATA:
{context_str}

Write ~1,800-2,400 words of prose. Go room by room — Bedroom, Living room,
Workspace/Study, Entryway/Kitchen as relevant — and for EACH prescribe, from
this chart's favoured/avoided elements: colours to use and avoid, materials
(wood/metal/water-feature/ceramic/textile), lighting warmth, plants vs metal,
what to add and what to remove. Every instruction states its chart reason first.
Weave it as a consultant's walk-through, not a checklist. Reproduce specific
colours/materials from the element reference so the reader can act immediately.

Tone: {tone}
"""
        return {'prompt': prompt, 'max_tokens': 18000}

    if section_type == 'wearable':
        prompt = f"""
## TASK: Chapter 4 — Wearable & Carry Feng Shui (随身风水)
{frame}
### PREVIOUS CHAPTERS:
{previous_context}
### COMPLETE CHART DATA:
{context_str}

Write ~1,200-1,600 words of prose. The feng shui the reader carries on the body,
all from the favoured elements: clothing and accessory colours; the materials
and gemstones/crystals that carry their favoured element (this is where a
favoured-element bracelet or stone naturally belongs); wallet colour; favourable
numbers; even favourable shapes. Reason each from the chart. Practical, wearable,
immediately usable.

Tone: {tone}
"""
        return {'prompt': prompt, 'max_tokens': 13000}

    if section_type == 'annual':
        yrs = window_years()
        prompt = f"""
## TASK: Chapter 5 — This Year & Next: Directions & Energy to Respect (流年方位与五行)
{frame}
{annual_block(bazi_json, lang_code)}
### PREVIOUS CHAPTERS:
{previous_context}
### COMPLETE CHART DATA:
{context_str}

Write ~1,300-1,700 words of prose covering the window of {yrs[0]}-{yrs[1]}
(a rolling ~two-year horizon from today). Two threads, woven together:

1. **Directions to keep calm** — layer each year's affliction directions (Tai
   Sui / Sui Po / Three Killings / 5-Yellow / 2-Black, computed above) onto this
   home: which directions to leave quiet this year and next, and what "quiet"
   concretely means (no renovation/groundbreaking there, don't relocate the bed
   or desk into it, etc.). These affliction directions are the ONE place you may
   name a direction as needing caution — they are annual and universal, not a
   house-sector judgement.
2. **Adjusting the remedy for the year's energy** — each year leans toward
   certain elements (given above). Explain how THIS year and next press on this
   chart's favoured/avoided elements, and therefore what to dial UP or DOWN in
   the home for this window (e.g. a Water-favouring chart in a Fire-heavy year
   should reinforce Water more than usual). This is the living, year-by-year
   layer on top of the standing prescription from earlier chapters.

Reason before every instruction. Stay practical.

Tone: {tone}
"""
        return {'prompt': prompt, 'max_tokens': 14000}

    if section_type == 'cheatsheet':
        prompt = f"""
## TASK: Chapter 6 — Your Feng Shui Pocket Card (随身速查卡)
{frame}
### PREVIOUS CHAPTERS (your ONLY source — distill, invent nothing):
{previous_context}

This ONE chapter may be compact and scannable (it is a pocket card). Under ~600
words:
# Your Feng Shui at a Glance
- **Feed these elements** (with their colours/materials, one line)
- **Keep these sparse** (one line + why)
- **Best directions to face / sleep toward** (one line)
- **Directions to keep calm this year** (from the annual block)
- **Your colours / numbers / materials** (one line)
- **Three things to add · three to remove** (six short lines, each with its
  one-clause chart reason)
- **The one sentence to remember**

Everything traces to earlier chapters. Even here, each line carries its reason.
"""
        return {'prompt': prompt, 'max_tokens': 7000}

    raise ValueError(f"Unknown fengshui section type: {section_type}")
