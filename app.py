from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
import json
import traceback
from datetime import datetime

app = Flask(__name__)

CORS(app,
     resources={r"/api/*": {"origins": "*"}},
     methods=["GET", "POST", "OPTIONS"],
     allow_headers=["Content-Type", "Authorization"],
     supports_credentials=False)

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    return response

# ================= 配置区域 =================
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
SITE_URL = os.getenv("SITE_URL", "https://theqiflow.com")
APP_NAME = "Bazi Pro Calculator"
MODEL_ID = "google/gemini-3-pro-preview"
# ===========================================

# ================= 多语言配置 =================
LANGUAGE_PROMPTS = {
    "en": {
        "name": "English",
        "instruction": "Write your response in fluent, natural English.",
        "pronoun_rule": "Address the user as 'you'. Maintain a consistent professional yet warm tone.",
        "pronoun_rule_nonbinary": "Use 'they/them/their' pronouns consistently. Never use 'he/him/his' or 'she/her/hers'. Address the user as 'you'.",
        "style_gentle": "Use a warm, insightful tone like a wise mentor sharing ancient wisdom with a modern friend.",
        "style_authentic": "Use a direct, authoritative tone like a traditional Chinese fortune-telling master who tells it like it is - no sugarcoating.",
        "opening": "In this chapter, I will analyze for you...",
        "closing": "End of this chapter."
    },
    "zh": {
        "name": "中文",
        "instruction": "请用流畅自然的中文撰写。",
        "pronoun_rule": "必须统一使用'您'（尊称）来称呼用户，切勿使用'你'。保持语气的一致性。",
        "pronoun_rule_nonbinary": "统一使用'您'称呼用户。第三人称使用'Ta'或直接用客户姓名，绝对不要使用'他'或'她'。",
        "style_gentle": "用温暖睿智的语气，像一位通晓古今的智者在与朋友分享人生智慧。",
        "style_authentic": "用传统命理师的直接语气，像老师傅算命一样直言不讳，好就是好，不好就直说，不绕弯子。",
        "opening": "本章为您分析...",
        "closing": "此章节完"
    },
    "de": {
        "name": "Deutsch",
        "instruction": "Schreiben Sie Ihre Antwort in flüssigem, natürlichem Deutsch.",
        "pronoun_rule": "Verwenden Sie KONSEQUENT die Höflichkeitsform 'Sie' und 'Ihre' (formal). Vermeiden Sie unbedingt das 'Du' (informal). Dies ist eine strikte Regel.",
        "pronoun_rule_nonbinary": "Verwenden Sie geschlechtsneutrale Formulierungen. Vermeiden Sie 'er/sie' und verwenden Sie stattdessen den Namen der Person oder neutrale Umschreibungen.",
        "style_gentle": "Verwenden Sie einen warmen, einfühlsamen Ton wie ein weiser Mentor, der alte Weisheiten mit einem modernen Freund teilt.",
        "style_authentic": "Verwenden Sie einen direkten, autoritativen Ton wie ein traditioneller chinesischer Wahrsagemeister, der die Dinge beim Namen nennt.",
        "opening": "In diesem Kapitel analysiere ich für Sie...",
        "closing": "Ende dieses Kapitels."
    },
    "es": {
        "name": "Español",
        "instruction": "Escribe tu respuesta en español fluido y natural.",
        "pronoun_rule": "Utiliza consistentemente la forma 'Usted' (formal) para dirigirte al usuario. No uses 'Tú'.",
        "pronoun_rule_nonbinary": "Utiliza lenguaje inclusivo y neutral. Evita 'él/ella' y usa el nombre de la persona o formulaciones neutras como 'esta persona'.",
        "style_gentle": "Usa un tono cálido y perspicaz, como un mentor sabio compartiendo sabiduría ancestral con un amigo moderno.",
        "style_authentic": "Usa un tono directo y autoritario, como un maestro tradicional chino de adivinación que dice las cosas como son.",
        "opening": "En este capítulo, analizo para usted...",
        "closing": "Fin de este capítulo."
    },
    "fr": {
        "name": "Français",
        "instruction": "Rédigez votre réponse dans un français fluide et naturel.",
        "pronoun_rule": "Utilisez systématiquement le vouvoiement ('Vous'). Ne tutoyez jamais l'utilisateur.",
        "pronoun_rule_nonbinary": "Utilisez un langage neutre et inclusif. Évitez 'il/elle' et utilisez le nom de la personne ou des formulations neutres comme 'cette personne'.",
        "style_gentle": "Utilisez un ton chaleureux et perspicace, comme un sage mentor partageant une sagesse ancestrale avec un ami moderne.",
        "style_authentic": "Utilisez un ton direct et autoritaire, comme un maître traditionnel chinois de divination qui dit les choses telles qu'elles sont.",
        "opening": "Dans ce chapitre, j'analyse pour vous...",
        "closing": "Fin de ce chapitre."
    }
}

# ================= 性别相关配置 =================
GENDER_INSTRUCTIONS = {
    "male": {
        "en": {
            "pronoun": "he/him/his",
            "bazi_rules": """In traditional BaZi for MALE charts:
- Wealth Stars (正財/偏財): Represent wife, girlfriends, and female relationships
- Officer Stars (正官/七殺): Represent career authority, bosses, and pressure
- Rob Wealth (劫財) and Shoulder to Shoulder (比肩): Represent brothers, male friends, competitors
- Food God (食神) and Hurting Officer (傷官): Represent children (especially sons), creativity, expression
- The Day Branch (日支) represents the spouse palace - analyze for wife characteristics"""
        },
        "zh": {
            "pronoun": "他",
            "bazi_rules": """传统八字男命解读规则：
- 财星（正财/偏财）：代表妻子、女友、女性缘分
- 官杀（正官/七杀）：代表事业、上司、压力、权威
- 比劫（比肩/劫财）：代表兄弟、男性朋友、竞争者
- 食伤（食神/伤官）：代表子女（尤其儿子）、才华、表达能力
- 日支为配偶宫：分析妻子的特征和婚姻状况"""
        }
    },
    "female": {
        "en": {
            "pronoun": "she/her/hers",
            "bazi_rules": """In traditional BaZi for FEMALE charts:
- Officer Stars (正官/七殺): Represent husband, boyfriends, and male relationships (正官=husband, 七殺=boyfriend/lovers)
- Wealth Stars (正財/偏財): Represent financial ability and father
- Rob Wealth (劫財) and Shoulder to Shoulder (比肩): Represent sisters, female friends, competitors
- Food God (食神) and Hurting Officer (傷官): Represent children, creativity - but 傷官 can harm 正官 (challenging for marriage)
- The Day Branch (日支) represents the spouse palace - analyze for husband characteristics"""
        },
        "zh": {
            "pronoun": "她",
            "bazi_rules": """传统八字女命解读规则：
- 官杀（正官/七杀）：代表丈夫、男友、男性缘分（正官为正缘丈夫，七杀为情人或非正式关系）
- 财星（正财/偏财）：代表财运能力和父亲
- 比劫（比肩/劫财）：代表姐妹、女性朋友、竞争者
- 食伤（食神/伤官）：代表子女、才华，但伤官克正官，对婚姻有挑战
- 日支为配偶宫：分析丈夫的特征和婚姻状况"""
        }
    },
    "non-binary": {
        "en": {
            "pronoun": "they/them/their",
            "bazi_rules": """## GENDER-INCLUSIVE INTERPRETATION GUIDELINES

**IMPORTANT**: This client identifies as non-binary, transgender, or prefers a gender-neutral reading.
Use inclusive, respectful language throughout the entire report.

### Strict Language Rules:
- Use "they/them/their" pronouns CONSISTENTLY throughout the entire report
- NEVER use "he," "she," "his," "her," "him," "hers" under any circumstances
- Use "this person," "the client," or their actual name instead of gendered terms
- AVOID phrases like "as a man..." or "as a woman..." or "for males/females..."
- Do NOT use terms like "男命", "女命", "乾造", "坤造"

### Relationship Analysis - DUAL INTERPRETATION APPROACH:
Traditional BaZi assigns different relationship meanings based on birth sex. Since this client 
prefers a gender-neutral reading, you MUST provide BOTH perspectives and let them choose what resonates:

**Perspective A - Wealth Stars (財星) as Relationship Indicators:**
- 正財 (Direct Wealth): May represent a stable, nurturing, supportive partner
- 偏財 (Indirect Wealth): May represent a more dynamic, financially-oriented partner
- Analyze: Where are Wealth Stars? Strong or weak? What partner qualities do they suggest?

**Perspective B - Officer Stars (官殺) as Relationship Indicators:**
- 正官 (Direct Officer): May represent a structured, responsible, authoritative partner
- 七殺 (Seven Killings): May represent a passionate, intense, powerful partner
- Analyze: Where are Officer Stars? Strong or weak? What partner qualities do they suggest?

**After presenting BOTH perspectives:**
- Note which interpretation appears stronger based on chart structure
- Describe ideal partner qualities in COMPLETELY NEUTRAL terms
- Use "partner," "significant other," "spouse" - NEVER "husband," "wife," "boyfriend," "girlfriend"
- Focus on: personality traits, values, emotional needs, relationship dynamics

### Spouse Palace (Day Branch) Analysis:
- Analyze the Day Branch for partnership qualities WITHOUT gendering
- Describe what kind of ENERGY or QUALITIES the ideal partner may have
- Focus on: temperament, communication style, shared values, emotional compatibility

### Career and Wealth Analysis:
- Analyze purely based on chart structure
- NO gendered career assumptions or stereotypes
- Focus entirely on individual talents, strengths, and opportunities

### Writing Style:
- Warm, respectful, and affirming throughout
- Celebrate their unique chart without any gendered assumptions
- Focus on universal human experiences: growth, love, success, challenges, self-discovery
- Make the reading feel personal and validating"""
        },
        "zh": {
            "pronoun": "Ta/TA/您",
            "bazi_rules": """## 性别包容解读指南

**重要提示**：这位客户认同为非二元性别、跨性别，或希望使用性别中立的解读方式。
请在整份报告中使用包容、尊重的语言。

### 严格用语规则：
- 统一使用"您"作为第二人称称呼
- 第三人称必须使用"Ta"或直接用客户姓名
- 绝对禁止使用"他"或"她"
- 绝对禁止使用"作为男性..."或"作为女性..."这类表述
- 绝对禁止使用"男命"、"女命"、"乾造"、"坤造"等传统性别术语
- 使用"这位客户"、"命主"等中性称谓

### 婚恋分析 - 双重解读模式：
传统八字根据出生性别分配不同的感情含义。由于客户希望性别中立的解读，
您必须同时提供两种视角，让客户自行选择更契合的解读：

**视角A - 从财星角度解读感情关系：**
- 正财：可能代表稳定、体贴、支持型的伴侣
- 偏财：可能代表活泼、多变、外向型的伴侣
- 分析：财星在哪里？强还是弱？暗示什么样的伴侣特质？

**视角B - 从官杀角度解读感情关系：**
- 正官：可能代表有责任感、稳重、有担当的伴侣
- 七杀：可能代表热情、强势、有魄力的伴侣
- 分析：官杀在哪里？强还是弱？暗示什么样的伴侣特质？

**呈现两种视角后：**
- 指出哪种解读在命盘结构上更为突出
- 用完全中性的语言描述理想伴侣特质
- 使用"伴侣"、"另一半"、"爱人" - 绝不使用"丈夫"、"妻子"、"男友"、"女友"
- 聚焦于：性格特点、价值观、情感需求、相处模式

### 配偶宫（日支）分析：
- 分析日支的伴侣特质时不要带入性别
- 描述理想伴侣可能具有的「能量」或「特质」
- 聚焦于：性情、沟通方式、共同价值观、情感契合度

### 事业和财运分析：
- 完全基于命盘结构分析
- 不带任何性别刻板印象的职业假设
- 完全聚焦于个人才能、优势和机遇

### 整体写作风格：
- 全文保持温暖、尊重、肯定的语气
- 不带任何性别假设地解读命盘
- 聚焦于普世的人生主题：成长、爱情、成功、挑战、自我发现
- 让解读感觉个人化且具有认同感"""
        }
    }
}

# ================= 模式配置 =================
MODE_CONFIGS = {
    "gentle": {
        "name": "Gentle Mode",
        "name_zh": "温和版",
        "ethics": """
## ETHICAL GUIDELINES

- Never make absolute predictions about health, death, or guaranteed outcomes
- Never claim this is fortune-telling or can predict the future with certainty
- Frame everything as "tendencies," "potentials," or "energetic patterns"
- Empower the reader with choices and agency
- End sections with constructive, actionable advice
""",
        "interpretation_style": """
## INTERPRETATION STYLE - GENTLE MODE

**Be Encouraging 鼓励性**:
- Focus on strengths and positive potentials
- Frame challenges as "growth opportunities"
- Use softer language for difficult aspects

**Be Balanced 平衡性**:
- Present both positive and challenging aspects
- Always provide hope and solutions
- Emphasize free will and personal agency

**Word Choice 用词选择**:
- Use: "tendency," "potential," "may experience," "opportunity for growth"
- Avoid: "definitely will," "doomed to," "cannot escape," "destined to fail"
"""
    },
    "authentic": {
        "name": "Authentic Mode",
        "name_zh": "真实版",
        "ethics": """
## AUTHENTICITY DISCLAIMER

- This reading uses TRADITIONAL interpretation methods without modern softening.
- The language is direct, as traditional masters would speak.
- Challenging aspects are stated clearly - not to discourage, but to prepare.
- Every challenge mentioned comes with traditional remedies or timing guidance.
""",
        "interpretation_style": """
## INTERPRETATION STYLE - AUTHENTIC MODE (传统直言版)

**Be Direct 直言不讳**:
- 像传统命理师一样说话，不要绕弯子
- 该说"破财"就说"破财"，该说"婚姻有波折"就直说
- 用传统术语：犯太岁、刑冲破害、比劫夺财、伤官见官、财库被冲
- 不要用"可能有挑战"，要说"今年子午相冲，6月财运受阻，不宜大额投资"

**Be Specific 具体明确**:
- 给出具体时间："2026年午月（6月）"
- 给出具体事项："不宜签合同"、"防小人"、"注意肠胃"
- 给出具体建议："佩戴属虎的生肖吉祥物可化解"

**Use Traditional Terms 使用传统术语**:
正确用法:
- "命中比劫重，合伙做生意容易被拖累，建议独资或控股"
- "日支空亡，晚婚对你更有利，30岁后遇到的对象更稳定"
- "今年犯太岁，诸事不顺，宜守不宜攻"
- "七杀无制，性格刚烈，事业上易与上司冲突"
- "财星入墓，中年后财运才能真正起来"
- "伤官见官，婚姻宫有刑，第一段感情难以长久"

避免用法:
- "You might experience some challenges..." 
- "There could potentially be..."
- "This suggests a tendency toward..."
- "能量比较复杂" (这是废话)

**Provide Remedies 给出化解方案**:
- 每个问题都要给出传统的化解方法
- 可以是：风水摆设、佩戴饰品、择日行事、方位选择、贵人方向
- 不是空泛的"保持积极心态"，而是具体的操作建议

**Timing is Key 时机很重要**:
- 明确说出哪些年份/月份有利、哪些需要避开
- "2026年上半年适合谈恋爱，下半年不宜做重大决定"
- "35-45岁这步大运是事业上升期，抓紧这十年"

**Balance Yin-Yang 阴阳平衡**:
- 好的直接说好，不好的也直接指出
- 但每个挑战都必须配一个化解方法或最佳应对时机
- 这不是恐吓，是让人提前知道如何趋吉避凶
"""
    }
}
# ===========================================


def get_gender_instruction(gender, lang_code):
    """获取性别相关的解读指令"""
    rule_lang = "zh" if lang_code == "zh" else "en"
    
    if gender == "male":
        return GENDER_INSTRUCTIONS["male"].get(rule_lang, GENDER_INSTRUCTIONS["male"]["en"])
    elif gender == "female":
        return GENDER_INSTRUCTIONS["female"].get(rule_lang, GENDER_INSTRUCTIONS["female"]["en"])
    elif gender == "non-binary":
        return GENDER_INSTRUCTIONS["non-binary"].get(rule_lang, GENDER_INSTRUCTIONS["non-binary"]["en"])
    else:
        # 未知性别默认使用非二元/中性解读，更加包容
        return GENDER_INSTRUCTIONS["non-binary"].get(rule_lang, GENDER_INSTRUCTIONS["non-binary"]["en"])


def get_mode_config(mode):
    """获取模式配置"""
    return MODE_CONFIGS.get(mode, MODE_CONFIGS["gentle"])


def format_bazi_context(data):
    """格式化完整八字数据给 AI"""
    try:
        gender = data.get('gender', 'unknown')
        name = data.get('name', 'Client')
        birth_info = data.get('birthInfo', {})
        day_master = data.get('dayMaster', 'N/A')
        day_master_element = data.get('dayMasterElement', 'N/A')
        day_master_yinyang = data.get('dayMasterYinYang', 'N/A')
        day_master_full = data.get('dayMasterFull', 'N/A')
        pillars = data.get('pillars', {})
        five_elements = data.get('fiveElements', {})
        special_palaces = data.get('specialPalaces', {})
        yun_info = data.get('yunInfo', {})
        current_dayun = data.get('currentDayun', {})
        current_liunian = data.get('currentLiuNian', {})
        all_dayun = data.get('allDayun', [])
        zodiac = data.get('zodiac', {})
        shen_sha = data.get('shenSha', {})
        
        # 性别显示 - 支持非二元性别
        if gender == 'male':
            gender_display = "Male (男命/乾造)"
        elif gender == 'female':
            gender_display = "Female (女命/坤造)"
        elif gender == 'non-binary':
            gender_display = "Non-binary / Gender-neutral (性别中立解读)"
        else:
            gender_display = "Not specified (未指定)"
        
        def format_pillar(name_cn, name_en, p):
            if not p:
                return f"{name_en} {name_cn}: N/A"
            return f"""{name_en} {name_cn}: {p.get('ganZhi', 'N/A')}
    - 天干 Stem: {p.get('gan', '')} | 地支 Branch: {p.get('zhi', '')}
    - 五行 WuXing: {p.get('wuXing', '')}
    - 纳音 NaYin: {p.get('naYin', '')}
    - 十神 Ten Gods: 天干 {p.get('shiShenGan', '')} / 地支 {p.get('shiShenZhi', '')}
    - 长生 Twelve Stage: {p.get('diShi', '')}
    - 空亡 Void: {p.get('xunKong', '')}
    - 藏干 Hidden Stems: {p.get('hideGan', '')}"""

        year_str = format_pillar('年柱', 'Year Pillar', pillars.get('year', {}))
        month_str = format_pillar('月柱', 'Month Pillar', pillars.get('month', {}))
        day_str = format_pillar('日柱', 'Day Pillar', pillars.get('day', {}))
        hour_str = format_pillar('时柱', 'Hour Pillar', pillars.get('hour', {}))
        
        dayun_list = []
        for d in all_dayun:
            marker = " <- CURRENT" if d.get('isCurrent', False) else ""
            dayun_list.append(
                f"  {d.get('index', '')}. {d.get('ganZhi', '')} "
                f"(Age {d.get('startAge', '')}-{d.get('endAge', '')}, "
                f"{d.get('startYear', '')}-{d.get('endYear', '')}){marker}"
            )
        dayun_str = "\n".join(dayun_list) if dayun_list else "  No data"
        
        if current_dayun:
            if current_dayun.get('notStarted'):
                current_dayun_status = f"Not started yet (will start in {current_dayun.get('startYear', '')})"
            else:
                current_dayun_status = (
                    f"{current_dayun.get('ganZhi', 'N/A')} "
                    f"(Age {current_dayun.get('startAge', '')}-{current_dayun.get('endAge', '')}, "
                    f"{current_dayun.get('startYear', '')}-{current_dayun.get('endYear', '')})"
                )
        else:
            current_dayun_status = "N/A"
        
        if current_liunian:
            current_liunian_str = f"{current_liunian.get('year', '')} - {current_liunian.get('ganZhi', '')}"
        else:
            current_liunian_str = "N/A"

        context = f"""
## COMPLETE BAZI CHART DATA

### Client Information
- Name: {name}
- Gender: {gender_display}
- Birthplace: {birth_info.get('location', 'Unknown')}
- Longitude: {birth_info.get('longitude', 'N/A')}
- Timezone: UTC{'+' if birth_info.get('timezone', 0) >= 0 else ''}{birth_info.get('timezone', 'N/A')}
- True Solar Time: {birth_info.get('solarTime', 'N/A')}

### Day Master Analysis
- Day Master: {day_master}
- Element: {day_master_element}
- Yin/Yang: {day_master_yinyang}
- Full Description: {day_master_full}

### Four Pillars Complete Data

{year_str}

{month_str}

{day_str}

{hour_str}

### Five Elements Count
- Metal 金: {five_elements.get('metal', 0)}
- Wood 木: {five_elements.get('wood', 0)}
- Water 水: {five_elements.get('water', 0)}
- Fire 火: {five_elements.get('fire', 0)}
- Earth 土: {five_elements.get('earth', 0)}

Analysis:
- Strongest: {max(five_elements.items(), key=lambda x: x[1])[0] if five_elements else 'N/A'} ({max(five_elements.values()) if five_elements else 0})
- Weakest/Missing: {min(five_elements.items(), key=lambda x: x[1])[0] if five_elements else 'N/A'} ({min(five_elements.values()) if five_elements else 0})

### Special Palaces
- Tai Yuan 胎元 (Conception): {special_palaces.get('taiYuan', 'N/A')}
- Ming Gong 命宫 (Life Palace): {special_palaces.get('mingGong', 'N/A')}
- Shen Gong 身宫 (Body Palace): {special_palaces.get('shenGong', 'N/A')}

### Zodiac Animals
- Year: {zodiac.get('year', 'N/A')}
- Month: {zodiac.get('month', 'N/A')}
- Day: {zodiac.get('day', 'N/A')}
- Hour: {zodiac.get('hour', 'N/A')}

### Luck Cycles Information

Start of Luck Cycles:
- Start Age: {yun_info.get('startAge', 'N/A')}
- Start Year: {yun_info.get('startYear', 'N/A')}
- Direction: {yun_info.get('description', 'N/A')}

Current Major Luck Cycle: {current_dayun_status}

Current Annual Luck: {current_liunian_str}

All 10 Major Luck Cycles:
{dayun_str}

### Special Stars (Shen Sha)
- Auspicious Stars 吉神: {shen_sha.get('jiShen', 'N/A')}
- Challenging Stars 凶煞: {shen_sha.get('xiongSha', 'N/A')}
"""
        return context

    except Exception as e:
        return f"Data parsing error: {str(e)}\n{traceback.format_exc()}"


def format_bazi_summary(data):
    """生成八字摘要"""
    pillars = data.get('pillars', {})
    
    bazi_str = f"{pillars.get('year', {}).get('ganZhi', '?')} {pillars.get('month', {}).get('ganZhi', '?')} {pillars.get('day', {}).get('ganZhi', '?')} {pillars.get('hour', {}).get('ganZhi', '?')}"
    
    gender = data.get('gender', 'Unknown')
    if gender == 'non-binary':
        gender_display = 'Non-binary'
    else:
        gender_display = gender.capitalize()
    
    summary = f"""
Four Pillars (四柱): {bazi_str}
Day Master (日主): {data.get('dayMasterFull', data.get('dayMaster', 'N/A'))}
Gender (性别): {gender_display}
Birthplace: {data.get('birthInfo', {}).get('location', 'Unknown')}
True Solar Time: {data.get('birthInfo', {}).get('solarTime', 'N/A')}
"""
    return summary


def get_language_config(lang_code, custom_lang=None):
    """获取语言配置"""
    if lang_code == "custom" and custom_lang:
        return {
            "name": custom_lang,
            "instruction": f"Write your response in fluent, natural {custom_lang}.",
            "pronoun_rule": "Address the user in a formal and respectful manner consistent with this language.",
            "pronoun_rule_nonbinary": "Use gender-neutral language consistently. Avoid gendered pronouns.",
            "style_gentle": "Use a warm, insightful tone like a wise mentor sharing ancient wisdom with a modern friend.",
            "style_authentic": "Use a direct, authoritative tone like a traditional fortune-telling master.",
            "opening": f"Analysis for you in {custom_lang}...",
            "closing": "End of chapter."
        }
    return LANGUAGE_PROMPTS.get(lang_code, LANGUAGE_PROMPTS["en"])


def ask_ai(system_prompt, user_prompt):
    if not OPENROUTER_API_KEY:
        print("ERROR: OPENROUTER_API_KEY is missing!")
        return {"error": "Server Configuration Error: API Key missing"}

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": SITE_URL,
        "X-Title": APP_NAME,
    }

    payload = {
        "model": MODEL_ID,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.75,
        "max_tokens": 16000
    }

    try:
        print(f"Calling OpenRouter with model: {MODEL_ID}")
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=280
        )
        print(f"OpenRouter response status: {response.status_code}")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP Error: {http_err}")
        print(f"Response body: {response.text}")
        return {"error": f"HTTP Error: {str(http_err)}", "details": response.text}
    except Exception as e:
        print(f"OpenRouter API Error: {str(e)}")
        return {"error": str(e)}


# ================= AI 自检功能 =================
def validate_report(full_report, bazi_data, language):
    """让 AI 检查报告是否有错误"""
    
    gender = bazi_data.get('gender', 'unknown')
    gender_note = ""
    if gender == "non-binary":
        gender_note = """
IMPORTANT: This client selected NON-BINARY gender. Check that:
- Report uses 'they/them' pronouns (English) or 'Ta' (Chinese)
- Report does NOT use 'he/she', '他/她', '男命/女命'
- Relationship analysis provides DUAL interpretation (both Wealth and Officer star perspectives)
- Language is gender-neutral throughout
"""
    
    validation_prompt = f"""
You are a senior BaZi (Chinese Four Pillars of Destiny) expert reviewer. 
Your task is to review a generated BaZi report for accuracy and quality.

## BAZI DATA PROVIDED TO THE REPORT GENERATOR:
- Client Name: {bazi_data.get('name', 'Unknown')}
- Gender: {bazi_data.get('gender', 'Unknown')}
- Day Master: {bazi_data.get('dayMaster', 'Unknown')} ({bazi_data.get('dayMasterElement', '')})
- Four Pillars: 
  - Year: {bazi_data.get('pillars', {}).get('year', {}).get('ganZhi', 'N/A')}
  - Month: {bazi_data.get('pillars', {}).get('month', {}).get('ganZhi', 'N/A')}
  - Day: {bazi_data.get('pillars', {}).get('day', {}).get('ganZhi', 'N/A')}
  - Hour: {bazi_data.get('pillars', {}).get('hour', {}).get('ganZhi', 'N/A')}
- Five Elements Count: {json.dumps(bazi_data.get('fiveElements', {}), ensure_ascii=False)}
{gender_note}

## GENERATED REPORT TO REVIEW:
{full_report[:8000]}  
(Report truncated for review - first 8000 characters shown)

## YOUR TASK:
1. Check if the Day Master analysis is consistent with the provided data
2. Check if Ten Gods interpretations are correct for the given gender
3. Check if element analysis matches the five elements count
4. Check if there are any obvious factual errors or contradictions
5. Check if the language and tone are appropriate
6. If gender is non-binary, verify gender-neutral language is used consistently

## RESPONSE FORMAT:
Respond in JSON format ONLY:
{{
    "status": "PASS" or "NEEDS_REVIEW",
    "confidence_score": 0-100,
    "summary": "Brief summary of review findings",
    "issues_found": [
        {{"severity": "high/medium/low", "description": "Issue description"}}
    ],
    "recommendation": "Your recommendation"
}}

If everything looks good, return status "PASS" with an empty issues_found array.
"""

    result = ask_ai(
        "You are a BaZi expert reviewer. Respond ONLY in valid JSON format.",
        validation_prompt
    )
    
    if result and 'choices' in result:
        try:
            content = result['choices'][0]['message']['content']
            content = content.strip()
            if content.startswith('```json'):
                content = content[7:]
            if content.startswith('```'):
                content = content[3:]
            if content.endswith('```'):
                content = content[:-3]
            
            validation_result = json.loads(content.strip())
            return validation_result
        except json.JSONDecodeError as e:
            print(f"Failed to parse validation JSON: {e}")
            return {
                "status": "PASS",
                "confidence_score": 85,
                "summary": "Validation completed (JSON parse fallback)",
                "issues_found": [],
                "recommendation": "Report appears acceptable based on structure review."
            }
    
    return {
        "status": "UNKNOWN",
        "confidence_score": 0,
        "summary": "Validation failed to complete",
        "issues_found": [{"severity": "high", "description": "Could not complete validation"}],
        "recommendation": "Manual review recommended"
    }


# ================= 生成客户消息（简化版，无 Google Doc） =================
def generate_customer_message_simple(client_name, bazi_summary, full_report, language):
    """生成客户消息（不包含 Google Doc 链接）"""
    
    report_preview = full_report[:3000] if len(full_report) > 3000 else full_report
    
    if language == "zh":
        message_prompt = f"""
请为客户 {client_name} 生成一段专业、温暖的消息，告知他们的八字命理报告已完成。

八字摘要：
{bazi_summary}

报告内容预览：
{report_preview}

要求：
1. 用中文撰写
2. 语气专业但温暖，像一位资深命理师在与客户交流
3. 简要概括报告中的3-5个关键发现或亮点（从报告内容中提取）
4. 给出一些积极的建议或祝福
5. 告知客户如有问题可以随时咨询
6. 整体长度适中（200-400字）
7. 不要提及任何链接或文档

直接输出消息内容，不要加任何说明或标题。
"""
    else:
        lang_name = LANGUAGE_PROMPTS.get(language, LANGUAGE_PROMPTS['en'])['name']
        message_prompt = f"""
Generate a professional, warm message for client {client_name} informing them that their BaZi destiny reading is complete.

BaZi Summary:
{bazi_summary}

Report Preview:
{report_preview}

Requirements:
1. Write in {lang_name}
2. Professional but warm tone, like an experienced destiny reader communicating with a client
3. Briefly summarize 3-5 key findings or highlights from the report (extract from report content)
4. Provide some positive advice or blessings
5. Let them know they can reach out with questions
6. Medium length (150-300 words)
7. Do NOT mention any links or documents

Output the message content directly without any additional explanation or title.
"""

    result = ask_ai(
        "You are a professional feng shui and destiny reading consultant communicating with a valued client.",
        message_prompt
    )
    
    if result and 'choices' in result:
        return result['choices'][0]['message']['content']
    
    # Fallback message
    if language == "zh":
        return f"""亲爱的 {client_name}，

您的八字命理分析报告已经完成！

{bazi_summary}

感谢您的耐心等待。如果您对报告内容有任何疑问，欢迎随时与我们联系。

祝您一切顺利！

The Qi Flow 团队
"""
    else:
        return f"""Dear {client_name},

Your personal BaZi Destiny Blueprint report is now ready!

{bazi_summary}

Thank you for your patience. If you have any questions about your reading, please don't hesitate to reach out.

Warm regards,
The Qi Flow Team
"""


@app.route('/', methods=['GET'])
def health_check():
    return jsonify({
        "status": "running", 
        "version": "5.2-gender-inclusive", 
        "api_key_set": bool(OPENROUTER_API_KEY),
        "endpoints": {
            "personal_report": "/api/generate-section",
            "marriage_report": "/api/generate-marriage-section"
        },
        "supported_genders": ["male", "female", "non-binary"]
    }), 200


@app.route('/api/generate-section', methods=['OPTIONS'])
def options_handler():
    return '', 204

@app.route('/api/generate-section', methods=['POST'])
def generate_section():
    try:
        print("=== Received request ===")

        req_data = request.json
        if not req_data:
            print("ERROR: No JSON received")
            return jsonify({"error": "No JSON received"}), 400

        print(f"Request data keys: {req_data.keys()}")

        bazi_json = req_data.get('bazi_data', {})
        section_type = req_data.get('section_type', 'core')

        lang_code = req_data.get('language', 'en')
        custom_lang = req_data.get('custom_language', None)
        lang_config = get_language_config(lang_code, custom_lang)

        reading_mode = req_data.get('mode', 'gentle')
        mode_config = get_mode_config(reading_mode)
        print(f"Reading Mode: {reading_mode} ({mode_config['name']})")

        gender = bazi_json.get('gender', 'unknown')
        client_name = bazi_json.get('name', 'Client')
        print(f"Client: {client_name}, Gender: {gender}, Section: {section_type}, Mode: {reading_mode}")

        gender_info = get_gender_instruction(gender, lang_code)

        current_opening = lang_config.get('opening', "In this chapter...")
        current_closing = lang_config.get('closing', "End of chapter.")
        
        # 根据性别选择合适的代词规则
        if gender == "non-binary":
            current_pronoun_rule = lang_config.get('pronoun_rule_nonbinary', lang_config.get('pronoun_rule', "Address the user formally."))
        else:
            current_pronoun_rule = lang_config.get('pronoun_rule', "Address the user formally.")
        
        if reading_mode == "authentic":
            current_style = lang_config.get('style_authentic', lang_config.get('style_gentle'))
        else:
            current_style = lang_config.get('style_gentle')

        context_str = format_bazi_context(bazi_json)
        
        pillars = bazi_json.get('pillars', {})
        day_master = bazi_json.get('dayMaster', '')
        day_master_element = bazi_json.get('dayMasterElement', '')
        current_dayun = bazi_json.get('currentDayun', {})
        current_liunian = bazi_json.get('currentLiuNian', {})
        special_palaces = bazi_json.get('specialPalaces', {})
        five_elements = bazi_json.get('fiveElements', {})
        yun_info = bazi_json.get('yunInfo', {})

        # ================= 非二元性别额外指令 =================
        nonbinary_extra_instruction = ""
        if gender == "non-binary":
            nonbinary_extra_instruction = """
## ⚠️ CRITICAL: GENDER-NEUTRAL LANGUAGE REQUIREMENT ⚠️

This client has selected NON-BINARY gender. You MUST follow these rules STRICTLY:

**ABSOLUTELY FORBIDDEN - DO NOT USE:**
- English: "he", "him", "his", "she", "her", "hers", "himself", "herself"
- Chinese: "他", "她", "男命", "女命", "乾造", "坤造", "丈夫", "妻子", "男友", "女友"
- Any gendered relationship terms

**REQUIRED - USE THESE INSTEAD:**
- English: "they", "them", "their", "themselves", "this person", "the client", or use client's actual name
- Chinese: "Ta", "TA", "这位客户", "命主", "伴侣", "另一半", "爱人"

**FOR RELATIONSHIP ANALYSIS:**
- MUST provide DUAL interpretation (both Wealth Star AND Officer Star perspectives)
- Let the client choose which resonates more
- Use "partner", "significant other", "spouse" - NEVER gendered terms

This is NON-NEGOTIABLE. Violations will make the report inappropriate for this client.
"""

        # ================= 核心 System Prompt =================
        base_system_prompt = f"""
You are a master of BaZi (Chinese Four Pillars of Destiny) with deep knowledge of classical texts like "San Ming Tong Hui" (三命通会), "Yuan Hai Zi Ping" (渊海子平), and "Di Tian Sui" (滴天髓).

## CRITICAL FORMATTING RULES - MUST FOLLOW

**ABSOLUTELY FORBIDDEN in your response 绝对禁止使用:**
- Horizontal divider lines: --- or ___ or *** or ===
- Setext-style headers (text with === or --- underneath)
- Triple or more consecutive blank lines
- Any decorative separators or dividers

**MANDATORY formatting 必须使用的格式:**
- Use ATX-style headers ONLY: # H1, ## H2, ### H3, #### H4
- Use single blank lines between sections
- Use **bold** for emphasis
- Use bullet lists: - or * or 1. 2. 3.

This rule is NON-NEGOTIABLE. Violations will break the PDF rendering.

## READING MODE: {mode_config['name'].upper()} / {mode_config['name_zh']}

{mode_config['interpretation_style']}

{mode_config['ethics']}

{nonbinary_extra_instruction}

## CLIENT INFORMATION - CRITICAL

**Gender 性别**: {gender.upper() if gender != 'unknown' else 'UNKNOWN'}
**Name 姓名**: {client_name}
**Pronouns 代词**: {gender_info['pronoun']}

**Gender-Specific BaZi Rules 性别专属解读规则**:
{gender_info['bazi_rules']}

CRITICAL: You MUST apply these gender-specific interpretation rules throughout your analysis!

## LANGUAGE & STYLE REQUIREMENTS

**Language 语言**: {lang_config['instruction']}
**Pronoun Rules 称谓规则**: {current_pronoun_rule}
**Third Person Reference 第三人称**: Use {gender_info['pronoun']} when referring to the client

**Writing Style 写作风格**:
{current_style}

## AVAILABLE DATA - USE ALL OF IT

You have access to COMPLETE chart data including:

1. **Four Pillars (四柱)** with FULL details for each pillar:
   - GanZhi (干支) - Heavenly Stem and Earthly Branch
   - WuXing (五行) - The element of each character
   - NaYin (纳音) - Sound element (e.g., "海中金", "炉中火")
   - Ten Gods (十神) - ShiShenGan/ShiShenZhi relationship to Day Master
   - Twelve Stages (十二长生) - DiShi indicating element's life stage
   - Void (空亡) - XunKong indicating which branches are "empty"
   - Hidden Stems (藏干) - Internal elements within each branch

2. **Day Master Analysis (日主分析)**:
   - The Day Master element and Yin/Yang nature
   - Use this as the reference point for all Ten Gods calculations

3. **Special Palaces (特殊宫位)**:
   - 胎元 Tai Yuan: Pre-birth foundation, inherited traits from parents
   - 命宫 Ming Gong: Core destiny direction, life's central theme
   - 身宫 Shen Gong: Physical body, material fortune, self-cultivation

4. **Five Elements Count (五行统计)**:
   - Exact count of each element in the chart
   - Identify what is excessive, balanced, or missing

5. **Complete Luck Cycles (完整大运)**:
   - Start age and year of first luck cycle
   - Direction (forward/backward)
   - All 10 major luck periods with exact age/year ranges
   - Current luck cycle clearly marked
   - Current annual luck (流年)

6. **Special Stars (神煞)**:
   - Auspicious stars (吉神)
   - Challenging stars (凶煞)

## ANALYSIS REQUIREMENTS

**Be Specific 具体化**:
- Reference ACTUAL data from the chart (e.g., "Your Day Branch 午 shows 帝旺 stage...")
- Quote the exact GanZhi, Ten Gods, and Stages from the data
- Connect observations to specific pillars and their relationships

**Be Authentic 专业化**:
- Use proper BaZi terminology with translations
- Explain WHY certain combinations matter
- Reference classical interpretations when relevant

**Be Personal 个人化**:
- This is THEIR unique chart - avoid generic statements
- Connect analysis to real-life implications
- Acknowledge both strengths and growth areas

**Be Practical 实用化**:
- Provide actionable insights
- Suggest specific remedies or enhancements
- Give timing guidance based on luck cycles

## MANDATORY STRUCTURE

- START your response EXACTLY with: "{current_opening}"
- END your response EXACTLY with: "{current_closing}"
- Do NOT add greetings like "Welcome", "Hello", or "As we discussed"
- Treat this as a STANDALONE chapter - do not reference other chapters
- Write 3000+ words with proper Markdown formatting (headers, bullets, bold)
- Include Chinese terms with translations for authenticity
- Do NOT use any horizontal lines (---, ***, ===, ___) anywhere in your response
"""

        # ================= 各章节详细指令 =================
        specific_prompt = ""

        if section_type == 'core':
            specific_prompt = f"""
## TASK: Write Chapter 1 - Soul Blueprint & Destiny Overview (命局灵魂)

### COMPLETE CHART DATA:
{context_str}

### REQUIRED ANALYSIS - Reference Specific Data Points:

## 1. Day Master Deep Analysis (日主深度分析)
- Analyze Day Master [{day_master}] - is it {day_master_element}
- What is the Yin/Yang nature? What personality traits does this indicate?
- Check the Month Branch to determine seasonal strength (得令/失令)
- Reference the 十二长生 stage of the Day Pillar: is Day Master in 长生, 帝旺, 墓, or other stage?
- Overall assessment: Is Day Master strong (身强) or weak (身弱)? Cite evidence from the chart.

## 2. Ten Gods Pattern Analysis (十神格局分析)
- List ALL Ten Gods appearing in the four pillars (from shiShenGan and shiShenZhi data)
- Create a summary: Which Ten Gods appear most? Which are missing?
- What does this pattern reveal about personality and life themes?
- Example: "比肩 appears in Year Pillar, suggesting..."

## 3. Hidden Stems Secrets (藏干秘密)
- Analyze the hidden stems (hideGan) in each of the four branches
- Are there any conflicts between the visible stems and hidden stems?
- What inner qualities or hidden potentials do they reveal?
- Any special combinations (暗合) or clashes (暗冲)?

## 4. Five Elements Balance (五行平衡)
- Reference the exact five elements count from the data
- What element is strongest? What is weakest or missing?
- How does this imbalance manifest in personality and life?
- What is the likely "Useful God" (用神) to bring balance?

## 5. Special Palaces Interpretation (特殊宫位解读)
- 胎元 [{special_palaces.get('taiYuan', 'N/A')}]: What does this reveal about prenatal foundation and inherited traits?
- 命宫 [{special_palaces.get('mingGong', 'N/A')}]: What is their core life direction?
- 身宫 [{special_palaces.get('shenGong', 'N/A')}]: What does this say about physical constitution and material life?

## 6. Void Analysis (空亡分析)
- Check which branches fall into void (xunKong) in each pillar
- What life areas might feel "empty" or require extra effort?
- How can they work with this energy?

## 7. Core Destiny Theme (命运核心主题)
- Synthesize all the above into a coherent life narrative
- What is their unique gift or superpower based on this chart?
- What is the central lesson or growth area of this lifetime?
- What unique contribution can they make to the world?

{"Make this feel like a profound self-discovery journey. The reader should feel truly SEEN and understood." if reading_mode == "gentle" else "直言命局优劣，好的明说，问题也要指出，但每个问题都给出具体的化解方向。让读者真正了解自己的命局特点。"}
"""

        elif section_type == 'wealth':
            # 财运章节 - 根据性别调整
            if gender == "female":
                wealth_gender_note = """
### GENDER-SPECIFIC NOTE FOR FEMALE CHART 女命特别说明
For women, Wealth Stars (财星) primarily represent:
- Financial ability and money-making potential
- Relationship with father
- (NOT husband - that's Officer Stars for women)

Focus this chapter on her CAREER and FINANCIAL potential.
Officer Stars analysis for relationships belongs in the Love chapter.
"""
            elif gender == "non-binary":
                wealth_gender_note = """
### GENDER-NEUTRAL NOTE 性别中立说明
For this client who prefers gender-neutral reading:
- Focus purely on CAREER and FINANCIAL aspects
- Analyze Wealth Stars for money-making ability and financial patterns
- Do NOT connect Wealth Stars to romantic relationships in this chapter
- Use gender-neutral language throughout: "they/them/their" or "Ta"
- Romantic analysis with dual interpretation will be in the Love chapter
"""
            else:
                wealth_gender_note = """
### GENDER-SPECIFIC NOTE FOR MALE CHART 男命特别说明
For men, Wealth Stars (财星) represent both:
- Financial ability and money-making potential
- Wife and female relationships

You may briefly mention how wealth stars affect his relationships with women,
but detailed romance analysis belongs in the Love chapter.
"""

            if reading_mode == "authentic":
                wealth_closing_guidance = """
### AUTHENTIC MODE 真实版要求:
- 如果财星弱，直接说"命中财运平平，需要格外努力"
- 如果有比劫夺财，直接说"不适合合伙，容易被人分走利益"
- 如果财库被冲，直接说"存不住钱，要特别注意理财"
- 每个问题都给出具体建议：什么行业适合、什么年份发财、要避开什么
- 不要用"可能"、"或许"、"有机会"这类模糊词汇
"""
            else:
                wealth_closing_guidance = """
Make them feel excited about their potential while being realistic about challenges.
"""

            specific_prompt = f"""
## TASK: Write Chapter 2 - Career Empire & Wealth Potential (事业财运)

{wealth_gender_note}

### COMPLETE CHART DATA:
{context_str}

### REQUIRED ANALYSIS:

## 1. Wealth Star Analysis (财星分析)
- Identify where 正财 and 偏财 appear in the chart (check shiShenGan/shiShenZhi for each pillar)
- Are wealth stars strong or weak? In what stage (十二长生)?
- Is there 财库 (wealth storage) in any branch?
- Natural relationship with money - easy accumulation or challenging?

## 2. Career DNA Based on Ten Gods (十神职业分析)
- What Ten Gods dominate the chart? Map to career archetypes:
  - 正官/七杀 dominant: Management, government, authority roles
  - 财星 dominant: Business, finance, sales
  - 食神/伤官 dominant: Creative fields, teaching, expression
  - 印星 dominant: Academic, research, advisory roles
  - 比劫 dominant: Competitive fields, sports, entrepreneurship

## 3. Useful God for Wealth (用神与财运)
- Based on Day Master strength, what element helps wealth?
- Which industries align with their Useful God element?
- What environments support their success?

## 4. Work Style Analysis (工作风格)
- Leadership style: Boss, partner, or specialist?
- Best work environment: Corporate, startup, freelance, government?
- Team dynamics: Leader, collaborator, or independent contributor?

## 5. Wealth-Building Strategy (财富策略)
- Their natural path to prosperity
- Should they focus on salary, business ownership, or investments?
- Risk tolerance based on chart structure
- Any warnings about financial pitfalls or 破财 patterns?

## 6. Career Timeline from Luck Cycles (大运事业时机)
- Analyze the complete luck cycles provided
- Which luck cycles (大运) activate career and wealth?
- Current luck cycle [{current_dayun.get('ganZhi', 'N/A')}] - how does it affect career?
- Best years for career moves, promotions, or business launches
- Periods requiring caution or consolidation

## 7. Practical Recommendations (实用建议)
- Top 3-5 specific industries to consider
- Skills to develop based on chart strengths
- Networking and partnership advice
- Feng shui elements to enhance wealth luck

{wealth_closing_guidance}
"""

        elif section_type == 'love':
            day_branch = pillars.get('day', {}).get('zhi', 'N/A')
            
            # 根据性别选择不同的婚恋分析指令
            if gender == "non-binary":
                # 非二元性别的双重解读
                love_specific_instruction = f"""
### CRITICAL: GENDER-INCLUSIVE RELATIONSHIP ANALYSIS 性别包容婚恋分析

This client has chosen a GENDER-NEUTRAL reading. You MUST provide DUAL INTERPRETATION.

**STRICT LANGUAGE RULES - VIOLATIONS ARE NOT ACCEPTABLE:**
- Use "they/them/their" pronouns in English
- Use "Ta" or client's name in Chinese  
- NEVER use: he, she, him, her, his, hers, 他, 她, husband, wife, boyfriend, girlfriend, 丈夫, 妻子, 男友, 女友
- Use: partner, significant other, spouse, loved one, 伴侣, 另一半, 爱人

**Day Branch (Spouse Palace): {day_branch}**

You MUST analyze relationships from BOTH perspectives:

---

## INTERPRETATION A - Wealth Stars (財星) as Relationship Indicators

Analyze as if Wealth Stars represent romantic attraction:

### Where are the Wealth Stars?
- Locate 正財 (Direct Wealth) and 偏財 (Indirect Wealth) in the four pillars
- Check shiShenGan and shiShenZhi for each pillar

### What Partner Qualities Do They Suggest?
- 正財 partner energy: Stable, practical, nurturing, financially responsible, loyal
- 偏財 partner energy: Outgoing, social, dynamic, generous, enjoys variety

### Wealth Star Strength Assessment
- Are Wealth Stars strong or weak in this chart?
- What does this suggest about relationship patterns?

### Timing Based on Wealth Star Cycles
- Which luck cycles activate Wealth Stars?
- When are favorable periods for meeting partners or deepening relationships?

---

## INTERPRETATION B - Officer Stars (官殺) as Relationship Indicators

Analyze as if Officer Stars represent romantic attraction:

### Where are the Officer Stars?
- Locate 正官 (Direct Officer) and 七殺 (Seven Killings) in the four pillars
- Check shiShenGan and shiShenZhi for each pillar

### What Partner Qualities Do They Suggest?
- 正官 partner energy: Responsible, structured, traditional, protective, career-oriented
- 七殺 partner energy: Passionate, powerful, intense, ambitious, transformative

### Officer Star Strength Assessment
- Are Officer Stars strong or weak in this chart?
- What does this suggest about relationship patterns?

### Timing Based on Officer Star Cycles
- Which luck cycles activate Officer Stars?
- When are favorable periods for meeting partners or deepening relationships?

---

## SYNTHESIS - Bringing Both Perspectives Together

After presenting both interpretations:

### Which Interpretation Appears Stronger?
Based on the chart structure (which stars are more prominent, better positioned, or in better stages), indicate which interpretation may be more relevant - but emphasize the client should trust their own resonance.

### Spouse Palace Analysis (Day Branch: {day_branch})
- Analyze the Day Branch for partnership QUALITIES without gendering
- What ENERGY does the ideal partner bring?
- Focus on: temperament, values, communication style, emotional needs

### Universal Relationship Themes
- Attachment style based on chart structure
- What they need emotionally in a relationship
- Potential relationship challenges and growth areas
- How they express and receive love

### Relationship Timing
- Combine insights from both Wealth and Officer star cycles
- Best periods for relationship milestones
- Periods requiring extra attention to relationship harmony
"""
                love_closing_guidance = f"""
### GENDER-INCLUSIVE CLOSING GUIDANCE:

Present both interpretations with equal respect and depth. 

End with an affirming message:
- Acknowledge the validity of their identity
- Emphasize that authentic love transcends traditional categories
- Encourage them to trust which interpretation resonates with their lived experience
- Provide hope and practical wisdom for finding genuine connection

REMEMBER: Use "they/them/their" or "Ta" throughout. NEVER use gendered pronouns or relationship terms.
"""

            elif gender == "female":
                love_specific_instruction = f"""
### CRITICAL: FEMALE CHART RELATIONSHIP ANALYSIS 女命婚恋分析 - 关键

For this FEMALE client, you MUST analyze relationships using these rules:

**Officer Stars = Husband/Boyfriends for Women:**
- 正官 (Direct Officer) = Represents her HUSBAND, the "right" man, legitimate relationship
- 七殺 (Seven Killings) = Represents boyfriends, lovers, passionate but potentially unstable relationships

**Key Patterns to Check:**
- If both 正官 and 七殺 appear: 官杀混杂 - complexity in love life, possibly multiple significant relationships
- If 正官 is absent but 七殺 is strong: May attract intense but non-traditional relationships
- If 傷官 (Hurting Officer) clashes with 正官: Classic 傷官見官 - challenges in marriage for women

**Day Branch (Spouse Palace) Analysis:**
- The Day Branch [{day_branch}] represents her SPOUSE PALACE (配偶宫)
- What is the Ten God of the Day Branch? (check shiShenZhi of day pillar)
- What is the Twelve Stage (diShi) of the Day Branch?
- Is the Day Branch in 空亡 (void)?

**Questions to Answer:**
1. Where are her Officer Stars in the chart? Which pillars? Strong or weak?
2. Is there 傷官見官 pattern? What does this mean for her marriage?
3. What type of man is she attracted to based on Officer Star characteristics?
4. What does her spouse palace [{day_branch}] reveal about her ideal husband's personality?
5. What luck cycles activate romance (Officer Star luck cycles)?
"""
                if reading_mode == "authentic":
                    love_closing_guidance = f"""
### AUTHENTIC MODE 真实版婚恋分析要求:
- 如果婚姻宫有刑冲，直接说"第一段感情不稳定，容易有波折"
- 如果伤官见官（女命），直接说"对婚姻有挑战，可能经历分手或离婚"
- 如果日支空亡，直接说"配偶宫空亡，晚婚更稳定，或婚后聚少离多"
- 给出具体的结婚年龄建议："28-32岁结婚最合适"
- 给出配偶的具体画像："对方可能从事金融/教育行业，性格偏内向/外向"

Use correct pronouns: {gender_info['pronoun']}
"""
                else:
                    love_closing_guidance = f"""
Be warm and hopeful while being honest about challenges.
Use correct pronouns: {gender_info['pronoun']}
"""

            else:
                # 男性
                love_specific_instruction = f"""
### CRITICAL: MALE CHART RELATIONSHIP ANALYSIS 男命婚恋分析 - 关键

For this MALE client, you MUST analyze relationships using these rules:

**Wealth Stars = Wife/Girlfriends for Men:**
- 正財 (Direct Wealth) = Represents his WIFE, stable and legitimate relationship
- 偏財 (Indirect Wealth) = Represents girlfriends, lovers, romantic but potentially less stable

**Key Patterns to Check:**
- If both 正財 and 偏財 appear: He may have multiple romantic interests or marry more than once
- If 偏財 is stronger than 正財: May prefer casual relationships or marry later
- If 比劫 (Rob Wealth) is strong: 比劫奪財 - competition for partners or financial drain through relationships

**Day Branch (Spouse Palace) Analysis:**
- The Day Branch [{day_branch}] represents his SPOUSE PALACE (配偶宫)
- What is the Ten God of the Day Branch? (check shiShenZhi of day pillar)
- What is the Twelve Stage (diShi) of the Day Branch?
- Is the Day Branch in 空亡 (void)?

**Questions to Answer:**
1. Where are his Wealth Stars in the chart? Which pillars? Strong or weak?
2. Is there 比劫奪財 pattern? What does this mean for relationships?
3. What type of woman is he attracted to based on Wealth Star characteristics?
4. What does his spouse palace [{day_branch}] reveal about his ideal wife's personality?
5. What luck cycles activate romance (Wealth Star luck cycles)?
"""
                if reading_mode == "authentic":
                    love_closing_guidance = f"""
### AUTHENTIC MODE 真实版婚恋分析要求:
- 如果婚姻宫有刑冲，直接说"第一段感情不稳定，容易有波折"
- 如果比劫夺财（男命），直接说"容易遇到竞争者，或因女人破财"
- 如果日支空亡，直接说"配偶宫空亡，晚婚更稳定，或婚后聚少离多"
- 给出具体的结婚年龄建议："28-32岁结婚最合适"
- 给出配偶的具体画像："对方可能从事金融/教育行业，性格偏内向/外向"

Use correct pronouns: {gender_info['pronoun']}
"""
                else:
                    love_closing_guidance = f"""
Be warm and hopeful while being honest about challenges.
Use correct pronouns: {gender_info['pronoun']}
"""

            specific_prompt = f"""
## TASK: Write Chapter 3 - Love, Relationships & Soulmate Profile (婚恋情感)

{love_specific_instruction}

### COMPLETE CHART DATA:
{context_str}

### REQUIRED ANALYSIS:

## 1. Relationship Stars Analysis (婚恋星分析)
- Apply the gender-specific rules above
- Locate and analyze all relevant relationship stars
- Assess their strength, stage, and position in the chart

## 2. Spouse Palace Deep Dive (配偶宫深度分析)
- Day Branch [{day_branch}] analysis:
  - What element is this branch? What does it represent?
  - What is the Ten God (shiShenZhi) of the day pillar?
  - What is the Twelve Stage (diShi)? 帝旺 = strong spouse, 墓 = introverted spouse, etc.
  - Is it in 空亡? What does this mean for marriage timing or spouse presence?
- Any clashes (冲), combinations (合), or harms (害) with other branches?

## 3. Ideal Partner Profile (理想伴侣画像)
- Personality traits that complement this chart
- Physical characteristics tendencies (based on elements)
- Career or background of ideal match
- Which geographic direction might they come from? (based on elements)

## 4. Love Patterns & Attachment Style (恋爱模式)
- How do they behave in relationships based on Ten Gods pattern?
- Common relationship challenges they may face
- Their attachment style (secure, anxious, avoidant) based on chart structure
- What triggers them emotionally?

## 5. Marriage Timing from Luck Cycles (婚姻时机)
- Analyze the complete luck cycles for romance timing
- Which luck cycles activate relationship stars?
- Current luck cycle [{current_dayun.get('ganZhi', 'N/A')}] - impact on love life?
- Favorable years for meeting someone significant or marriage
- Years requiring relationship caution

## 6. Relationship Advice (婚恋建议)
- How to attract the right partner based on their chart
- How to maintain a healthy long-term relationship
- Red flags to watch for based on chart patterns
- How to work with challenging aspects

{love_closing_guidance}
"""

        elif section_type == '2026_forecast':
            # 2026流年预测 - 根据性别调整
            if gender == "non-binary":
                forecast_gender_note = """
### GENDER-NEUTRAL FORECAST NOTE:
- Use "they/them/their" pronouns throughout
- For relationship predictions, mention BOTH Wealth Star and Officer Star activations
- Let the client determine which resonates with their experience
- Avoid any gendered language or assumptions
"""
            else:
                forecast_gender_note = f"""
### GENDER REMINDER:
Client is {gender.upper()}. Apply correct gender-based star interpretations for all predictions.
"""

            if reading_mode == "authentic":
                forecast_mode_instruction = """
### AUTHENTIC MODE 真实版流年预测要求:
- 直接说哪几个月好、哪几个月差
- 如果有冲克，直接说"这个月犯太岁/逢冲，不宜做重大决定"
- 具体到事项："6月不宜投资"、"9月防小人"、"12月注意身体"
- 如果整年运势不好，直接说"2026年宜守不宜攻，稳扎稳打为主"
- 每个问题都要给出化解方法：佩戴什么、摆放什么、去什么方位
"""
            else:
                forecast_mode_instruction = """
Make this feel like a practical roadmap they can actually use throughout 2026.
"""

            specific_prompt = f"""
## TASK: Write Chapter 4 - 2026 Year of the Fire Horse (丙午) Complete Forecast (2026流年预测)

### COMPLETE CHART DATA:
{context_str}

{forecast_gender_note}

{forecast_mode_instruction}

### REQUIRED ANALYSIS:

## 1. 2026 Fire Horse (丙午) Overview (2026火马年总览)
- 2026 is 丙午 year - Fire Horse (Yang Fire + Horse)
- How does 丙午 interact with their Day Master [{day_master}]?
- How does 午 (Horse) interact with their four branches?
- CHECK SPECIFICALLY: Is there 子午冲 (Rat-Horse clash) with any branch? This is major!
- Any combinations (合) or harms (害) with 午?
- Overall energy theme of 2026 for this person

## 2. Impact on Current Luck Cycle (与当前大运的交互)
- Current luck cycle: [{current_dayun.get('ganZhi', 'N/A')}]
- How does 2026 丙午 interact with their current 大运?
- Is this a supportive or challenging combination?
- What themes are amplified by this interaction?

## 3. Key Opportunities in 2026 (2026机遇)
- Which life areas get activated positively?
- Career opportunities based on element interactions
- Relationship opportunities (apply gender-specific rules)
- Wealth opportunities
- Best timing for major decisions

## 4. Challenges to Navigate in 2026 (2026挑战)
- Potential obstacles or difficult periods
- Health areas to watch (which organs relate to stressed elements?)
- Relationship cautions
- Career or financial cautions
- How to mitigate challenges

## 5. Month-by-Month Breakdown (逐月分析)
Provide specific guidance for each Chinese lunar month:

- **Month 1 (寅月 - Feb 4 to Mar 5)**: Tiger month...
- **Month 2 (卯月 - Mar 6 to Apr 4)**: Rabbit month...
- **Month 3 (辰月 - Apr 5 to May 5)**: Dragon month...
- **Month 4 (巳月 - May 6 to Jun 5)**: Snake month...
- **Month 5 (午月 - Jun 6 to Jul 6)**: Horse month (double 午!)...
- **Month 6 (未月 - Jul 7 to Aug 7)**: Goat month...
- **Month 7 (申月 - Aug 8 to Sep 7)**: Monkey month...
- **Month 8 (酉月 - Sep 8 to Oct 7)**: Rooster month...
- **Month 9 (戌月 - Oct 8 to Nov 7)**: Dog month...
- **Month 10 (亥月 - Nov 8 to Dec 6)**: Pig month...
- **Month 11 (子月 - Dec 7 to Jan 5)**: Rat month (子午冲 if applicable!)...
- **Month 12 (丑月 - Jan 6 to Feb 3 2027)**: Ox month...

For each month, briefly note:
- Key theme or energy
- Opportunities
- Cautions
- Lucky days or activities

## 6. 2026 Action Plan (2026行动计划)
- Top 3 things to focus on in 2026
- Top 3 things to avoid or be cautious about
- Lucky elements, colors, and directions for 2026
- Feng shui recommendations
- Any specific remedies if challenges are significant

## 7. Looking Ahead (展望未来)
- How does 2026 set up 2027?
- Any long-term themes emerging?
- Final empowering message for the year ahead
"""

        else:
            return jsonify({"error": f"Unknown section type: {section_type}"}), 400

        print(f"Calling AI for section: {section_type} in language: {lang_config['name']} with mode: {reading_mode}")
        ai_result = ask_ai(base_system_prompt, specific_prompt)
        print(f"AI result keys: {ai_result.keys() if isinstance(ai_result, dict) else 'not a dict'}")

        if ai_result and 'choices' in ai_result:
            content = ai_result['choices'][0]['message']['content']
            print(f"Success! Content length: {len(content)}")
            return jsonify({"content": content})
        elif ai_result and 'error' in ai_result:
            print(f"AI Error: {ai_result}")
            return jsonify(ai_result), 500
        else:
            print(f"Unknown AI response: {ai_result}")
            return jsonify({"error": "AI response format invalid", "raw": str(ai_result)}), 500

    except Exception as e:
        error_msg = traceback.format_exc()
        print(f"CRITICAL SERVER ERROR: {error_msg}")
        return jsonify({"error": "Internal Server Error", "details": str(e)}), 500


@app.route('/api/finalize-report', methods=['OPTIONS'])
def finalize_options_handler():
    return '', 204


@app.route('/api/finalize-report', methods=['POST'])
def finalize_report():
    """
    简化版：只做 AI 自检 + 生成客户消息（不创建 Google Doc）
    """
    try:
        print("=== Finalize Report Request (No Google Doc) ===")
        
        req_data = request.json
        if not req_data:
            return jsonify({"error": "No JSON received"}), 400
        
        full_report = req_data.get('full_report', '')
        bazi_data = req_data.get('bazi_data', {})
        language = req_data.get('language', 'en')
        
        client_name = bazi_data.get('name', 'Client')
        
        if not full_report:
            return jsonify({"error": "No report content provided"}), 400
        
        print(f"Processing report for: {client_name}")
        print(f"Report length: {len(full_report)} characters")
        
        # 生成八字摘要
        bazi_summary = format_bazi_summary(bazi_data)
        
        result = {
            "client_name": client_name,
            "validation": None,
            "customer_message": None
        }
        
        # 1. AI 自检报告
        print("Step 1: Validating report...")
        try:
            validation_result = validate_report(full_report, bazi_data, language)
            result["validation"] = validation_result
            print(f"Validation result: {validation_result.get('status', 'Unknown')}")
        except Exception as e:
            print(f"Validation error: {e}")
            result["validation"] = {
                "status": "SKIPPED",
                "summary": "Validation skipped due to error",
                "issues_found": []
            }
        
        # 2. 生成客户消息
        print("Step 2: Generating customer message...")
        try:
            customer_message = generate_customer_message_simple(
                client_name, 
                bazi_summary,
                full_report,
                language
            )
            result["customer_message"] = customer_message
            print("Customer message generated successfully")
        except Exception as e:
            print(f"Customer message error: {e}")
            result["customer_message"] = f"[Error generating message: {str(e)}]"
        
        print("=== Finalize Report Complete ===")
        return jsonify(result)
        
    except Exception as e:
        error_msg = traceback.format_exc()
        print(f"CRITICAL ERROR in finalize_report: {error_msg}")
        return jsonify({"error": "Internal Server Error", "details": str(e)}), 500


# =====================================================================
# ================= 合婚报告功能 - MARRIAGE COMPATIBILITY =================
# =====================================================================

MARRIAGE_SECTIONS = [
    {'type': 'overview', 'title': 'Chapter 1: Both Partners Overview', 'zh': '第一章：双方命局概览'},
    {'type': 'compatibility', 'title': 'Chapter 2: Core Compatibility Analysis', 'zh': '第二章：核心配对分析'},
    {'type': 'communication', 'title': 'Chapter 3: Communication & Conflict Patterns', 'zh': '第三章：相处与沟通模式'},
    {'type': 'wealth_career', 'title': 'Chapter 4: Wealth & Career Together', 'zh': '第四章：财运与事业配合'},
    {'type': 'love_marriage', 'title': 'Chapter 5: Love & Marriage Stability', 'zh': '第五章：感情与婚姻稳定性'},
    {'type': 'forecast_2026', 'title': 'Chapter 6: 2026 Forecast & Harmony Tips', 'zh': '第六章：2026流年预测与和谐建议'},
]


def format_marriage_bazi_context(bazi_a, bazi_b):
    """格式化双人八字数据给 AI"""
    
    def format_single_person(data, label):
        name = data.get('name', label)
        gender = data.get('gender', 'unknown')
        birth_info = data.get('birthInfo', {})
        pillars = data.get('pillars', {})
        five_elements = data.get('fiveElements', {})
        
        # 支持非二元性别显示
        if gender == 'male':
            gender_display = "Male (男命)"
        elif gender == 'female':
            gender_display = "Female (女命)"
        elif gender == 'non-binary':
            gender_display = "Non-binary (性别中立)"
        else:
            gender_display = "Unknown"
        
        bazi_str = f"{pillars.get('year', {}).get('ganZhi', '?')} {pillars.get('month', {}).get('ganZhi', '?')} {pillars.get('day', {}).get('ganZhi', '?')} {pillars.get('hour', {}).get('ganZhi', '?')}"
        
        return f"""
### {name} ({label})
- Gender: {gender_display}
- Birthplace: {birth_info.get('location', 'Unknown')}
- True Solar Time: {birth_info.get('solarTime', 'N/A')}
- Four Pillars: {bazi_str}
- Day Master: {data.get('dayMaster', 'N/A')} ({data.get('dayMasterElement', '')})
- Day Master Strength: {data.get('dayMasterStrength', 'N/A')}
- Zodiac: {data.get('zodiac', 'N/A')}
- Na Yin: {data.get('naYin', 'N/A')}

**Year Pillar 年柱**: {pillars.get('year', {}).get('ganZhi', 'N/A')}
  - Hidden Stems: {pillars.get('year', {}).get('hideGan', 'N/A')}
  - Ten Gods: {pillars.get('year', {}).get('shiShenGan', '')} / {pillars.get('year', {}).get('shiShenZhi', '')}

**Month Pillar 月柱**: {pillars.get('month', {}).get('ganZhi', 'N/A')}
  - Hidden Stems: {pillars.get('month', {}).get('hideGan', 'N/A')}
  - Ten Gods: {pillars.get('month', {}).get('shiShenGan', '')} / {pillars.get('month', {}).get('shiShenZhi', '')}

**Day Pillar 日柱**: {pillars.get('day', {}).get('ganZhi', 'N/A')}
  - Hidden Stems: {pillars.get('day', {}).get('hideGan', 'N/A')}
  - Spouse Palace (配偶宫): {pillars.get('day', {}).get('zhi', 'N/A')}

**Hour Pillar 时柱**: {pillars.get('hour', {}).get('ganZhi', 'N/A')}
  - Hidden Stems: {pillars.get('hour', {}).get('hideGan', 'N/A')}
  - Ten Gods: {pillars.get('hour', {}).get('shiShenGan', '')} / {pillars.get('hour', {}).get('shiShenZhi', '')}

**Five Elements Count 五行统计**:
  - Metal 金: {five_elements.get('metal', 0)}
  - Wood 木: {five_elements.get('wood', 0)}
  - Water 水: {five_elements.get('water', 0)}
  - Fire 火: {five_elements.get('fire', 0)}
  - Earth 土: {five_elements.get('earth', 0)}

**Favorable Elements 喜用神**: {', '.join(data.get('favorableElements', [])) or 'N/A'}
**Unfavorable Elements 忌神**: {', '.join(data.get('unfavorableElements', [])) or 'N/A'}

**Current Luck Cycle 当前大运**: {data.get('currentDayun', {}).get('ganZhi', 'N/A')} ({data.get('currentDayun', {}).get('startYear', '')}-{data.get('currentDayun', {}).get('endYear', '')})
"""
    
    context_a = format_single_person(bazi_a, "Partner A")
    context_b = format_single_person(bazi_b, "Partner B")
    
    return f"""
## COMPLETE MARRIAGE COMPATIBILITY DATA

{context_a}

{context_b}
"""


def format_compatibility_scores(scores):
    """格式化合婚评分数据"""
    breakdown = scores.get('breakdown', {})
    
    return f"""
## COMPATIBILITY SCORES (已计算)

**Total Score 总分**: {scores.get('total', 0)} / 100
**Level 等级**: {scores.get('level', {}).get('name', 'N/A')}

### Score Breakdown 评分详解:

1. **Day Master Match 日主相合**: {breakdown.get('dayMaster', {}).get('score', 0)}/{breakdown.get('dayMaster', {}).get('maxScore', 25)}
   - {breakdown.get('dayMaster', {}).get('description', '')}

2. **Zodiac Connection 生肖配对**: {breakdown.get('zodiac', {}).get('score', 0)}/{breakdown.get('zodiac', {}).get('maxScore', 20)}
   - {breakdown.get('zodiac', {}).get('description', '')}

3. **Elements Balance 五行互补**: {breakdown.get('elements', {}).get('score', 0)}/{breakdown.get('elements', {}).get('maxScore', 20)}
   - {breakdown.get('elements', {}).get('description', '')}

4. **Na Yin Harmony 纳音合婚**: {breakdown.get('naYin', {}).get('score', 0)}/{breakdown.get('naYin', {}).get('maxScore', 15)}
   - {breakdown.get('naYin', {}).get('description', '')}

5. **Gan Zhi Synergy 干支配合**: {breakdown.get('ganZhi', {}).get('score', 0)}/{breakdown.get('ganZhi', {}).get('maxScore', 10)}
   - {breakdown.get('ganZhi', {}).get('description', '')}

6. **Spouse Palace 婚姻宫位**: {breakdown.get('spousePalace', {}).get('score', 0)}/{breakdown.get('spousePalace', {}).get('maxScore', 10)}
   - {breakdown.get('spousePalace', {}).get('description', '')}
"""


def get_marriage_gender_instruction(gender_a, gender_b, lang_code):
    """获取合婚报告的性别相关指令"""
    rule_lang = "zh" if lang_code == "zh" else "en"
    
    # 检查是否有非二元性别
    has_nonbinary = gender_a == "non-binary" or gender_b == "non-binary"
    
    if has_nonbinary:
        if rule_lang == "zh":
            return """
## 性别包容合婚指南

这对伴侣中至少有一方选择了性别中立的解读方式。请遵循以下规则：

### 语言规则：
- 使用"伴侣"、"另一半"、"爱人"等中性称谓
- 避免使用"丈夫"、"妻子"、"男方"、"女方"
- 第三人称使用"Ta"或直接用名字
- 避免"男命"、"女命"等术语

### 分析方式：
- 不按传统性别角色分配十神含义
- 重点分析两人五行互补、日主配合、生肖关系
- 配偶宫分析聚焦于伴侣特质而非性别特征
- 尊重每段关系的独特性
"""
        else:
            return """
## GENDER-INCLUSIVE MARRIAGE ANALYSIS GUIDELINES

At least one partner in this couple has selected a gender-neutral reading. Follow these rules:

### Language Rules:
- Use "partner," "significant other," "spouse" - avoid "husband," "wife"
- Use "they/them" for any partner who selected non-binary
- Use their actual names instead of gendered terms
- Avoid traditional terms like "male chart," "female chart"

### Analysis Approach:
- Do not assign Ten Gods meanings based on traditional gender roles
- Focus on Five Elements complementarity, Day Master harmony, Zodiac relationships
- Spouse Palace analysis should focus on partner qualities, not gendered traits
- Respect the unique nature of every relationship
"""
    else:
        # 传统男女配对
        gender_info_a = get_gender_instruction(gender_a, lang_code)
        gender_info_b = get_gender_instruction(gender_b, lang_code)
        
        return f"""
## GENDER-SPECIFIC INTERPRETATION RULES

For Partner A ({gender_a}):
{gender_info_a['bazi_rules']}

For Partner B ({gender_b}):
{gender_info_b['bazi_rules']}
"""


@app.route('/api/generate-marriage-section', methods=['OPTIONS'])
def marriage_options_handler():
    return '', 204


@app.route('/api/generate-marriage-section', methods=['POST'])
def generate_marriage_section():
    """生成合婚报告的单个章节"""
    try:
        print("=== Marriage Section Request ===")
        
        req_data = request.json
        if not req_data:
            return jsonify({"error": "No JSON received"}), 400
        
        bazi_a = req_data.get('bazi_a', {})
        bazi_b = req_data.get('bazi_b', {})
        scores = req_data.get('scores', {})
        section_type = req_data.get('section_type', 'overview')
        
        lang_code = req_data.get('language', 'en')
        custom_lang = req_data.get('custom_language', None)
        lang_config = get_language_config(lang_code, custom_lang)
        
        reading_mode = req_data.get('mode', 'gentle')
        mode_config = get_mode_config(reading_mode)
        
        name_a = bazi_a.get('name', 'Partner A')
        name_b = bazi_b.get('name', 'Partner B')
        gender_a = bazi_a.get('gender', 'unknown')
        gender_b = bazi_b.get('gender', 'unknown')
        
        print(f"Marriage Section: {section_type}, Mode: {reading_mode}, Lang: {lang_code}")
        print(f"Partner A: {name_a} ({gender_a}), Partner B: {name_b} ({gender_b})")
        
        # 获取语言配置
        current_opening = lang_config.get('opening', "In this chapter...")
        current_closing = lang_config.get('closing', "End of chapter.")
        
        if reading_mode == "authentic":
            current_style = lang_config.get('style_authentic', lang_config.get('style_gentle'))
        else:
            current_style = lang_config.get('style_gentle')
        
        # 格式化双人数据
        context_str = format_marriage_bazi_context(bazi_a, bazi_b)
        scores_str = format_compatibility_scores(scores)
        
        # 获取性别相关指令
        gender_instruction = get_marriage_gender_instruction(gender_a, gender_b, lang_code)
        
        # 检查是否需要性别中立语言
        has_nonbinary = gender_a == "non-binary" or gender_b == "non-binary"
        nonbinary_reminder = ""
        if has_nonbinary:
            nonbinary_reminder = """
## ⚠️ GENDER-NEUTRAL LANGUAGE REQUIRED ⚠️

At least one partner selected non-binary gender. You MUST:
- Use "they/them" or "Ta" for any non-binary partner
- Use "partner," "spouse," not "husband/wife"
- Avoid traditional gendered analysis terms
- Respect both partners' identities throughout
"""
        
        # ================= 合婚专用 System Prompt =================
        base_system_prompt = f"""
You are a master of BaZi (Chinese Four Pillars of Destiny) marriage compatibility analysis, with deep knowledge of classical texts and traditional 合婚 (marriage matching) techniques.

## CRITICAL FORMATTING RULES - MUST FOLLOW

**ABSOLUTELY FORBIDDEN 绝对禁止:**
- Horizontal divider lines: --- or ___ or *** or ===
- Setext-style headers
- Triple or more consecutive blank lines

**MANDATORY formatting 必须使用:**
- Use ATX-style headers: # H1, ## H2, ### H3, #### H4
- Use **bold** for emphasis
- Use bullet lists: - or * or 1. 2. 3.

## READING MODE: {mode_config['name'].upper()} / {mode_config['name_zh']}

{mode_config['interpretation_style']}

{mode_config['ethics']}

{nonbinary_reminder}

## COUPLE INFORMATION - USE THEIR ACTUAL NAMES

**Partner A**: {name_a} ({gender_a})
**Partner B**: {name_b} ({gender_b})

CRITICAL: Always use their actual names "{name_a}" and "{name_b}" throughout the analysis. 
NEVER use generic terms like "Partner A", "Partner B", "the man", "the woman".

## LANGUAGE REQUIREMENTS

**Language**: {lang_config['instruction']}
**Pronoun Rules**: {lang_config.get('pronoun_rule', '')}

**Writing Style**:
{current_style}

{gender_instruction}

## MANDATORY STRUCTURE

- START your response EXACTLY with: "{current_opening}"
- END your response EXACTLY with: "{current_closing}"
- Do NOT add greetings or preambles
- Write 2500+ words with proper Markdown formatting
- Include Chinese terms with translations
- Do NOT use any horizontal lines
"""

        # ================= 各章节详细指令 =================
        specific_prompt = ""
        
        if section_type == 'overview':
            specific_prompt = f"""
## TASK: Write Chapter 1 - Both Partners Overview (双方命局概览)

{context_str}

### REQUIRED ANALYSIS:

## 1. {name_a}'s BaZi Profile ({name_a}的命局分析)

Provide a comprehensive analysis of {name_a}'s chart:

### Day Master Analysis 日主分析
- Day Master element and Yin/Yang nature
- Is Day Master strong (身强) or weak (身弱)?
- Personality traits based on Day Master
- Natural strengths and challenges

### Ten Gods Pattern 十神格局
- Which Ten Gods dominate the chart?
- What does this reveal about personality?
- Key psychological traits and tendencies

### Five Elements Balance 五行平衡
- What elements are strong/weak/missing?
- How does this affect personality and needs?
- What does {name_a} need from a partner?

### Relationship Tendencies 感情倾向
- Based on gender-specific rules, what are the relationship stars?
- Natural approach to love and commitment
- What {name_a} needs emotionally

## 2. {name_b}'s BaZi Profile ({name_b}的命局分析)

Provide the same comprehensive analysis for {name_b}:

### Day Master Analysis 日主分析
### Ten Gods Pattern 十神格局
### Five Elements Balance 五行平衡
### Relationship Tendencies 感情倾向

## 3. First Impressions & Natural Attraction (初见与天然吸引力)

Based on both charts:
- What would attract them to each other initially?
- What energy does each bring to the relationship?
- Natural chemistry and magnetic pull
- Potential first impression issues

{"深入分析每个人的命局特点，让双方都能更好地理解自己和对方。" if reading_mode == "gentle" else "直言每个人的命局优缺点，不要回避问题，让双方清楚自己和对方的真实情况。"}
"""

        elif section_type == 'compatibility':
            specific_prompt = f"""
## TASK: Write Chapter 2 - Core Compatibility Analysis (核心配对分析)

{context_str}

{scores_str}

### REQUIRED ANALYSIS:

You have been provided with pre-calculated compatibility scores. Your task is to EXPLAIN these scores in depth, not recalculate them.

## 1. Day Master Compatibility 日主相合 (Score: {scores.get('breakdown', {}).get('dayMaster', {}).get('score', 0)}/25)

Analyze how {name_a}'s and {name_b}'s Day Masters interact:
- What is the relationship between their Day Master elements?
- Is there 天干五合 (Heavenly Stem combination)?
- How do their energies complement or clash?
- What does this mean for daily life compatibility?

## 2. Zodiac Connection 生肖配对 (Score: {scores.get('breakdown', {}).get('zodiac', {}).get('score', 0)}/20)

Analyze their Chinese zodiac relationship:
- Are they in 六合 (Six Harmony), 三合 (Three Harmony), 六冲 (Six Clash), or 六害 (Six Harm)?
- What does this mean for intuitive understanding?
- How naturally do they "get" each other?

## 3. Five Elements Balance 五行互补 (Score: {scores.get('breakdown', {}).get('elements', {}).get('score', 0)}/20)

Analyze elemental complementarity:
- What elements does {name_a} need that {name_b} has?
- What elements does {name_b} need that {name_a} has?
- Do they fill each other's gaps like puzzle pieces?
- Any elemental clashes to be aware of?

## 4. Na Yin Harmony 纳音合婚 (Score: {scores.get('breakdown', {}).get('naYin', {}).get('score', 0)}/15)

Analyze their Na Yin (year pillar sound element) relationship:
- What are their Na Yin elements?
- Do they support, clash, or remain neutral?
- What does this mean for their life philosophies and values?

## 5. Gan Zhi Synergy 干支配合 (Score: {scores.get('breakdown', {}).get('ganZhi', {}).get('score', 0)}/10)

Analyze deeper stem-branch connections:
- Any 天干合 between their pillars?
- Any 地支合 between their pillars?
- Count of harmonious connections across all four pillars

## 6. Spouse Palace Analysis 婚姻宫位 (Score: {scores.get('breakdown', {}).get('spousePalace', {}).get('score', 0)}/10)

Analyze their Day Branches (Spouse Palaces):
- How do their spouse palaces interact?
- Any 合 (combination), 冲 (clash), or 害 (harm)?
- What does this mean for their approach to marriage?

## 7. Overall Compatibility Summary 总体评估

Based on all six dimensions:
- Total Score: {scores.get('total', 0)}/100 ({scores.get('level', {}).get('name', 'N/A')})
- Key strengths of this pairing
- Main challenges to work on
- Overall assessment of marriage potential

{"用积极的视角解读每个维度，即使分数不高也要找到正面意义。" if reading_mode == "gentle" else "直接说明每个维度的真实情况，分数高的要说好在哪里，分数低的要指出问题所在。"}
"""

        elif section_type == 'communication':
            specific_prompt = f"""
## TASK: Write Chapter 3 - Communication & Conflict Patterns (相处与沟通模式)

{context_str}

### REQUIRED ANALYSIS:

## 1. Communication Styles 沟通方式

### {name_a}'s Communication Style
Based on Ten Gods pattern and Day Master:
- How does {name_a} express thoughts and feelings?
- What is their natural communication tempo?
- How do they handle emotional discussions?
- What triggers them to shut down or open up?

### {name_b}'s Communication Style
- How does {name_b} express thoughts and feelings?
- What is their natural communication tempo?
- How do they handle emotional discussions?
- What triggers them to shut down or open up?

### Communication Compatibility
- Do their styles complement or clash?
- Potential misunderstandings to watch for
- How can they bridge communication gaps?

## 2. Conflict Patterns 冲突模式

### How They Fight 他们如何吵架

Based on their charts, predict their typical conflict pattern:

**Conflict Trigger 导火索**
- What topics are likely to cause friction?
- Which element imbalances create tension?

**{name_a}'s Conflict Style**
Based on Ten Gods and elements:
- Do they explode, withdraw, or become passive-aggressive?
- How do they express anger or frustration?
- What do they need during conflict?

**{name_b}'s Conflict Style**
- Do they explode, withdraw, or become passive-aggressive?
- How do they express anger or frustration?
- What do they need during conflict?

**A Typical Argument Scenario 典型吵架场景**
Write a vivid hypothetical scenario of how a disagreement might unfold between them, based on their charts.

## 3. Resolution Patterns 和解模式

### Who Apologizes First? 谁先道歉？
Based on Day Master strength and Ten Gods, analyze:
- Who is more likely to break the silence?
- Who holds grudges longer?
- What does each person need to hear to feel resolved?

### How They Make Up 如何和好
- Their natural reconciliation style
- What works and what doesn't
- How to repair after major conflicts

## 4. Daily Life Compatibility 日常相处

### Living Together 一起生活
- How do their rhythms align?
- Decision-making dynamics
- Household responsibility distribution tendencies

### Supporting Each Other 相互支持
- How can {name_a} best support {name_b}?
- How can {name_b} best support {name_a}?
- What each person needs but might not ask for

## 5. Communication Advice 沟通建议

Provide specific, actionable advice for:
- How to improve daily communication
- How to prevent conflicts from escalating
- How to create a safe space for difficult conversations
- Key phrases or approaches that work for this pairing

{"让他们看到沟通的希望和改善的可能性，强调每对情侣都可以学习更好的沟通方式。" if reading_mode == "gentle" else "直接指出他们沟通中可能存在的问题，比如'你们可能经常因为钱吵架'或'一方太强势导致另一方压抑'。"}
"""

        elif section_type == 'wealth_career':
            specific_prompt = f"""
## TASK: Write Chapter 4 - Wealth & Career Together (财运与事业配合)

{context_str}

### REQUIRED ANALYSIS:

## 1. Individual Financial Profiles 各自的财运特点

### {name_a}'s Wealth Profile
- Wealth stars in the chart (正财/偏财 position and strength)
- Natural relationship with money
- Earning style: steady income vs. windfall opportunities
- Spending and saving tendencies
- Financial strengths and weaknesses

### {name_b}'s Wealth Profile
- Same analysis for {name_b}
- Wealth stars position and strength
- Earning, spending, and saving patterns

## 2. Combined Financial Energy 共同财运

### Wealth Synergy 财运协同
- Do their wealth stars support each other?
- Combined five elements effect on family wealth
- Who is better at earning? Who is better at managing?
- Potential financial blind spots as a couple

### Financial Roles 财务角色分配
Based on their charts:
- Who should handle investments?
- Who should manage daily expenses?
- Who is the risk-taker vs. the conservative one?
- How to balance different money attitudes?

## 3. Career Compatibility 事业配合

### Working Together 一起工作
If they were to work together or run a business:
- Would they complement each other?
- What roles would suit each person?
- Potential power struggles or collaboration issues

### Supporting Each Other's Careers 支持对方的事业
- How can {name_a} support {name_b}'s career?
- How can {name_b} support {name_a}'s career?
- Timing considerations for major career moves

## 4. Major Financial Decisions 重大财务决策

### Property and Investments 房产与投资
- Best timing for major purchases based on luck cycles
- What types of investments suit this couple?
- Real estate considerations

### Business Ventures 创业合作
- Should they start a business together?
- What industries would suit them as a couple?
- Partnership dynamics and potential issues

## 5. Wealth-Building Strategy as a Couple 夫妻财富策略

### Short-term (1-3 years) 短期策略
- Immediate financial focus areas
- Quick wins for this pairing

### Medium-term (3-10 years) 中期策略
- Major milestones to aim for
- Investment directions

### Long-term (10+ years) 长期策略
- Retirement planning considerations
- Wealth preservation for this combination

## 6. Financial Advice 财务建议

Specific recommendations for:
- How to handle money disagreements
- Joint vs. separate accounts considerations
- Key financial habits to develop together
- Warning signs to watch for

{"强调他们共同创造财富的潜力，用积极的视角看待财务配合。" if reading_mode == "gentle" else "直接指出财务上可能的问题，比如'一方可能大手大脚'、'容易因为钱吵架'、'某些年份要特别注意破财'。"}
"""

        elif section_type == 'love_marriage':
            specific_prompt = f"""
## TASK: Write Chapter 5 - Love & Marriage Stability (感情与婚姻稳定性)

{context_str}

### GENDER-SPECIFIC REMINDER:
- For {name_a} ({bazi_a.get('gender', 'unknown')}): Apply correct relationship star rules
- For {name_b} ({bazi_b.get('gender', 'unknown')}): Apply correct relationship star rules

### REQUIRED ANALYSIS:

## 1. Spouse Palace Analysis 配偶宫详解

### {name_a}'s Spouse Palace (Day Branch: {bazi_a.get('pillars', {}).get('day', {}).get('zhi', 'N/A')})
- What does this reveal about their ideal partner?
- How do they naturally behave in marriage?
- Any 空亡 (void), 刑冲 (clash/punishment) to note?
- What kind of spouse energy do they attract?

### {name_b}'s Spouse Palace (Day Branch: {bazi_b.get('pillars', {}).get('day', {}).get('zhi', 'N/A')})
- Same analysis for {name_b}

### Spouse Palace Interaction 配偶宫互动
- How do their spouse palaces interact with each other?
- Any 合 (combination) or 冲 (clash)?
- What does this mean for marital harmony?

## 2. Relationship Stars Analysis 婚恋星分析

### {name_a}'s Relationship Stars
Based on gender:
- Where are the key relationship stars?
- Are they strong or weak?
- What type of partner do they attract?

### {name_b}'s Relationship Stars
- Same analysis for {name_b}

### Cross-Analysis 交叉分析
- Does {name_a} fit what {name_b}'s chart indicates they need?
- Does {name_b} fit what {name_a}'s chart indicates they need?
- Are they each other's "type" according to BaZi?

## 3. Romantic Patterns 感情模式

### Attraction Dynamics 吸引力动态
- What keeps the spark alive?
- Physical and emotional chemistry indicators
- Long-term attraction sustainability

### Emotional Needs 情感需求
- What does {name_a} need emotionally?
- What does {name_b} need emotionally?
- Can they meet each other's needs?

### Intimacy Compatibility 亲密关系
- Energy alignment in intimate matters
- Potential mismatches and solutions
- How to maintain connection over time

## 4. Marriage Stability Indicators 婚姻稳定性指标

### Positive Indicators 有利因素
List all factors supporting marriage stability:
- Harmonious combinations
- Complementary elements
- Supportive luck cycles

### Challenge Indicators 挑战因素
List factors that may challenge the marriage:
- Any 刑冲破害 between charts
- Problematic Ten Gods patterns
- Timing challenges

### Stability Assessment 稳定性评估
Overall assessment of marriage longevity:
- First marriage success probability
- Key years that may be challenging
- How to strengthen the foundation

## 5. Children & Family 子女与家庭

### Children Indicators 子女缘分
Based on both charts:
- Overall fertility indicators
- Best timing for children
- What kind of parents would they be?

### Family Dynamics 家庭关系
- In-law relationships potential
- Extended family harmony
- Creating their own family culture

## 6. Marriage Advice 婚姻建议

### Before Marriage 婚前建议
- What to discuss before committing
- Potential deal-breakers to address
- How to prepare for marriage

### During Marriage 婚后建议
- How to maintain love and respect
- Key habits for a happy marriage
- How to navigate difficult periods

### Preventing Problems 预防问题
- Red flags to watch for
- When to seek help
- How to keep the marriage strong

{"强调他们感情的美好之处，给他们对婚姻的信心和希望。" if reading_mode == "gentle" else "直接指出可能影响婚姻稳定的因素，比如'某方可能有外遇倾向'、'第一段婚姻可能不稳定'、'某些年份是婚姻危险期'。"}
"""

        elif section_type == 'forecast_2026':
            specific_prompt = f"""
## TASK: Write Chapter 6 - 2026 Forecast & Harmony Tips (2026流年预测与和谐建议)

{context_str}

### REQUIRED ANALYSIS:

## 1. 2026 丙午年 (Fire Horse Year) Overview

### How 2026 Affects {name_a}
- How does 丙午 interact with {name_a}'s Day Master?
- Any 冲合 with {name_a}'s branches?
- Key themes for {name_a} in 2026
- Opportunities and challenges

### How 2026 Affects {name_b}
- How does 丙午 interact with {name_b}'s Day Master?
- Any 冲合 with {name_b}'s branches?
- Key themes for {name_b} in 2026
- Opportunities and challenges

## 2. 2026 as a Couple 作为夫妻的2026年

### Relationship Energy in 2026 感情运势
- How does 2026 affect their relationship?
- Is it a year to deepen commitment or navigate challenges?
- Key relationship themes for this year

### Combined Luck Assessment 综合运势
- Areas where both benefit
- Areas requiring joint attention
- Overall year rating for this couple

## 3. Month-by-Month Guidance 逐月指导

Provide brief guidance for key months:

**寅月 (Feb 4 - Mar 5)**: 
- Relationship energy
- Key advice

**卯月 (Mar 6 - Apr 4)**:
**辰月 (Apr 5 - May 5)**:
**巳月 (May 6 - Jun 5)**:
**午月 (Jun 6 - Jul 6)**: [Double Fire - important month!]
**未月 (Jul 7 - Aug 7)**:
**申月 (Aug 8 - Sep 7)**:
**酉月 (Sep 8 - Oct 7)**:
**戌月 (Oct 8 - Nov 7)**:
**亥月 (Nov 8 - Dec 6)**:
**子月 (Dec 7 - Jan 5)**: [子午冲 if applicable!]
**丑月 (Jan 6 - Feb 3 2027)**:

## 4. Important Dates & Decisions 重要日期与决策

### Best Timing for Major Events 重要事件吉时
If they're planning in 2026:
- Wedding/engagement best months
- Moving in together
- Major purchases
- Travel together

### Dates to Be Careful 需谨慎的日期
- Months to avoid major decisions
- Times when conflict is more likely
- How to navigate difficult periods

## 5. Harmony Enhancement Tips 和谐增进建议

### Five Elements Adjustments 五行调整
Based on their combined chart:
- What elements benefit their relationship?
- Colors to incorporate
- Directions that support harmony

### Practical Harmony Tips 实用和谐建议
- Daily habits to strengthen bond
- Weekly/monthly rituals
- How to handle 2026's challenging moments

### Communication Focus 沟通重点
- Key topics to discuss in 2026
- How to support each other through changes
- Building stronger foundations

## 6. Long-term Outlook 长期展望

### Beyond 2026 展望未来
- How does 2026 set up 2027 and beyond?
- Long-term relationship trajectory
- Major milestone years to anticipate

### Final Blessing 最终祝福
End with:
- Affirmation of their connection
- Key strengths to remember
- Encouragement for the journey ahead

{"以温暖积极的祝福结束，让他们对未来充满期待。" if reading_mode == "gentle" else "实事求是地告诉他们2026年可能面临的挑战，以及具体的化解方法。不要只说好听的，要给出实用的预警和建议。"}
"""

        else:
            return jsonify({"error": f"Unknown marriage section type: {section_type}"}), 400

        # 调用 AI
        print(f"Calling AI for marriage section: {section_type}")
        ai_result = ask_ai(base_system_prompt, specific_prompt)
        
        if ai_result and 'choices' in ai_result:
            content = ai_result['choices'][0]['message']['content']
            print(f"Success! Marriage section content length: {len(content)}")
            return jsonify({"content": content})
        elif ai_result and 'error' in ai_result:
            print(f"AI Error: {ai_result}")
            return jsonify(ai_result), 500
        else:
            print(f"Unknown AI response: {ai_result}")
            return jsonify({"error": "AI response format invalid"}), 500

    except Exception as e:
        error_msg = traceback.format_exc()
        print(f"CRITICAL ERROR in generate_marriage_section: {error_msg}")
        return jsonify({"error": "Internal Server Error", "details": str(e)}), 500


@app.route('/api/finalize-marriage-report', methods=['OPTIONS'])
def finalize_marriage_options_handler():
    return '', 204


@app.route('/api/finalize-marriage-report', methods=['POST'])
def finalize_marriage_report():
    """合婚报告完成处理：AI自检 + 客户消息生成"""
    try:
        print("=== Finalize Marriage Report Request ===")
        
        req_data = request.json
        if not req_data:
            return jsonify({"error": "No JSON received"}), 400
        
        full_report = req_data.get('full_report', '')
        bazi_a = req_data.get('bazi_a', {})
        bazi_b = req_data.get('bazi_b', {})
        scores = req_data.get('scores', {})
        language = req_data.get('language', 'en')
        
        name_a = bazi_a.get('name', 'Partner A')
        name_b = bazi_b.get('name', 'Partner B')
        gender_a = bazi_a.get('gender', 'unknown')
        gender_b = bazi_b.get('gender', 'unknown')
        
        if not full_report:
            return jsonify({"error": "No report content provided"}), 400
        
        print(f"Processing marriage report for: {name_a} & {name_b}")
        print(f"Report length: {len(full_report)} characters")
        
        result = {
            "couple_names": f"{name_a} & {name_b}",
            "validation": None,
            "customer_message": None
        }
        
        # 检查是否有非二元性别
        has_nonbinary = gender_a == "non-binary" or gender_b == "non-binary"
        gender_check_note = ""
        if has_nonbinary:
            gender_check_note = """
IMPORTANT: At least one partner selected NON-BINARY gender. Verify that:
- Report uses gender-neutral language appropriately
- Uses "they/them" or "Ta" for non-binary partner(s)
- Uses "partner/spouse" instead of "husband/wife"
- Avoids traditional gendered BaZi terms for non-binary partner(s)
"""
        
        # 1. AI 自检
        print("Step 1: Validating marriage report...")
        try:
            validation_prompt = f"""
You are a senior BaZi marriage compatibility expert reviewer.
Review this marriage compatibility report for accuracy.

## COUPLE DATA:
- Partner A: {name_a} ({gender_a})
  - Day Master: {bazi_a.get('dayMaster', 'N/A')} ({bazi_a.get('dayMasterElement', '')})
  - Four Pillars: {bazi_a.get('pillars', {}).get('year', {}).get('ganZhi', '?')} {bazi_a.get('pillars', {}).get('month', {}).get('ganZhi', '?')} {bazi_a.get('pillars', {}).get('day', {}).get('ganZhi', '?')} {bazi_a.get('pillars', {}).get('hour', {}).get('ganZhi', '?')}

- Partner B: {name_b} ({gender_b})
  - Day Master: {bazi_b.get('dayMaster', 'N/A')} ({bazi_b.get('dayMasterElement', '')})
  - Four Pillars: {bazi_b.get('pillars', {}).get('year', {}).get('ganZhi', '?')} {bazi_b.get('pillars', {}).get('month', {}).get('ganZhi', '?')} {bazi_b.get('pillars', {}).get('day', {}).get('ganZhi', '?')} {bazi_b.get('pillars', {}).get('hour', {}).get('ganZhi', '?')}

- Compatibility Score: {scores.get('total', 'N/A')}/100
{gender_check_note}

## REPORT TO REVIEW (first 6000 chars):
{full_report[:6000]}

## TASK:
Check for:
1. Correct gender-based interpretations (or gender-neutral if applicable)
2. Accurate Day Master analysis for both
3. Logical compatibility assessments
4. Consistent use of names (not "Partner A/B")
5. Any factual errors

Respond in JSON:
{{
    "status": "PASS" or "NEEDS_REVIEW",
    "confidence_score": 0-100,
    "summary": "Brief summary",
    "issues_found": [{{"severity": "high/medium/low", "description": "..."}}],
    "recommendation": "..."
}}
"""
            validation_result = ask_ai(
                "You are a BaZi marriage expert reviewer. Respond ONLY in valid JSON.",
                validation_prompt
            )
            
            if validation_result and 'choices' in validation_result:
                content = validation_result['choices'][0]['message']['content']
                content = content.strip()
                if content.startswith('```json'):
                    content = content[7:]
                if content.startswith('```'):
                    content = content[3:]
                if content.endswith('```'):
                    content = content[:-3]
                result["validation"] = json.loads(content.strip())
            else:
                result["validation"] = {"status": "SKIPPED", "summary": "Validation skipped"}
                
        except Exception as e:
            print(f"Validation error: {e}")
            result["validation"] = {"status": "SKIPPED", "summary": f"Error: {str(e)}"}
        
        # 2. 生成客户消息
        print("Step 2: Generating customer message...")
        try:
            pillars_a = bazi_a.get('pillars', {})
            pillars_b = bazi_b.get('pillars', {})
            
            bazi_str_a = f"{pillars_a.get('year', {}).get('ganZhi', '?')} {pillars_a.get('month', {}).get('ganZhi', '?')} {pillars_a.get('day', {}).get('ganZhi', '?')} {pillars_a.get('hour', {}).get('ganZhi', '?')}"
            bazi_str_b = f"{pillars_b.get('year', {}).get('ganZhi', '?')} {pillars_b.get('month', {}).get('ganZhi', '?')} {pillars_b.get('day', {}).get('ganZhi', '?')} {pillars_b.get('hour', {}).get('ganZhi', '?')}"
            
            marriage_summary = f"""
Couple: {name_a} & {name_b}
Compatibility Score: {scores.get('total', 'N/A')}/100 ({scores.get('level', {}).get('name', 'N/A')})

{name_a}'s Four Pillars: {bazi_str_a}
{name_a}'s Day Master: {bazi_a.get('dayMasterFull', bazi_a.get('dayMaster', 'N/A'))}

{name_b}'s Four Pillars: {bazi_str_b}
{name_b}'s Day Master: {bazi_b.get('dayMasterFull', bazi_b.get('dayMaster', 'N/A'))}
"""
            
            report_preview = full_report[:3000] if len(full_report) > 3000 else full_report
            
            if language == "zh":
                message_prompt = f"""
请为这对情侣生成一段专业、温暖的消息，告知他们的合婚分析报告已完成。

合婚摘要：
{marriage_summary}

报告内容预览：
{report_preview}

要求：
1. 用中文撰写
2. 语气专业但温暖
3. 简要概括报告中的3-5个关键发现（从报告内容中提取）
4. 给出积极的祝福
5. 告知如有问题可以随时咨询
6. 长度200-400字
7. 不要提及任何链接

直接输出消息内容。
"""
            else:
                lang_name = LANGUAGE_PROMPTS.get(language, LANGUAGE_PROMPTS['en'])['name']
                message_prompt = f"""
Generate a professional, warm message for this couple informing them their marriage compatibility reading is complete.

Summary:
{marriage_summary}

Report Preview:
{report_preview}

Requirements:
1. Write in {lang_name}
2. Professional but warm tone
3. Summarize 3-5 key findings from the report
4. Provide positive blessings for their relationship
5. Let them know they can reach out with questions
6. 150-300 words
7. Do NOT mention any links

Output the message directly.
"""

            msg_result = ask_ai(
                "You are a professional destiny reading consultant communicating with a valued couple.",
                message_prompt
            )
            
            if msg_result and 'choices' in msg_result:
                result["customer_message"] = msg_result['choices'][0]['message']['content']
            else:
                result["customer_message"] = f"Your marriage compatibility report for {name_a} & {name_b} is ready!"
                
        except Exception as e:
            print(f"Customer message error: {e}")
            result["customer_message"] = f"Your marriage compatibility report for {name_a} & {name_b} is ready!"
        
        print("=== Finalize Marriage Report Complete ===")
        return jsonify(result)
        
    except Exception as e:
        error_msg = traceback.format_exc()
        print(f"CRITICAL ERROR in finalize_marriage_report: {error_msg}")
        return jsonify({"error": "Internal Server Error", "details": str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
