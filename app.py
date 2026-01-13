from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
import json
import traceback

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
        "style_gentle": "Use a warm, insightful tone like a wise mentor sharing ancient wisdom with a modern friend.",
        "style_authentic": "Use a direct, authoritative tone like a traditional Chinese fortune-telling master who tells it like it is - no sugarcoating.",
        "opening": "In this chapter, I will analyze for you...",
        "closing": "End of this chapter."
    },
    "zh": {
        "name": "中文",
        "instruction": "请用流畅自然的中文撰写。",
        "pronoun_rule": "必须统一使用'您'（尊称）来称呼用户，切勿使用'你'。保持语气的一致性。",
        "style_gentle": "用温暖睿智的语气，像一位通晓古今的智者在与朋友分享人生智慧。",
        "style_authentic": "用传统命理师的直接语气，像老师傅算命一样直言不讳，好就是好，不好就直说，不绕弯子。",
        "opening": "本章为您分析...",
        "closing": "此章节完"
    },
    "de": {
        "name": "Deutsch",
        "instruction": "Schreiben Sie Ihre Antwort in flüssigem, natürlichem Deutsch.",
        "pronoun_rule": "Verwenden Sie KONSEQUENT die Höflichkeitsform 'Sie' und 'Ihre' (formal). Vermeiden Sie unbedingt das 'Du' (informal). Dies ist eine strikte Regel.",
        "style_gentle": "Verwenden Sie einen warmen, einfühlsamen Ton wie ein weiser Mentor, der alte Weisheiten mit einem modernen Freund teilt.",
        "style_authentic": "Verwenden Sie einen direkten, autoritativen Ton wie ein traditioneller chinesischer Wahrsagemeister, der die Dinge beim Namen nennt.",
        "opening": "In diesem Kapitel analysiere ich für Sie...",
        "closing": "Ende dieses Kapitels."
    },
    "es": {
        "name": "Español",
        "instruction": "Escribe tu respuesta en español fluido y natural.",
        "pronoun_rule": "Utiliza consistentemente la forma 'Usted' (formal) para dirigirte al usuario. No uses 'Tú'.",
        "style_gentle": "Usa un tono cálido y perspicaz, como un mentor sabio compartiendo sabiduría ancestral con un amigo moderno.",
        "style_authentic": "Usa un tono directo y autoritario, como un maestro tradicional chino de adivinación que dice las cosas como son.",
        "opening": "En este capítulo, analizo para usted...",
        "closing": "Fin de este capítulo."
    },
    "fr": {
        "name": "Français",
        "instruction": "Rédigez votre réponse dans un français fluide et naturel.",
        "pronoun_rule": "Utilisez systématiquement le vouvoiement ('Vous'). Ne tutoyez jamais l'utilisateur.",
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
    else:
        default = GENDER_INSTRUCTIONS["male"].get(rule_lang, GENDER_INSTRUCTIONS["male"]["en"])
        return {
            "pronoun": "they/them/their",
            "bazi_rules": f"Gender not specified. Defaulting to general interpretation:\n{default['bazi_rules']}"
        }


def get_mode_config(mode):
    """获取模式配置"""
    return MODE_CONFIGS.get(mode, MODE_CONFIGS["gentle"])


def format_bazi_context(data):
    """格式化完整八字数据给 AI - v4.0"""
    try:
        # === 基础信息 ===
        gender = data.get('gender', 'unknown')
        name = data.get('name', 'Client')
        birth_info = data.get('birthInfo', {})
        
        # === 日主信息 ===
        day_master = data.get('dayMaster', 'N/A')
        day_master_element = data.get('dayMasterElement', 'N/A')
        day_master_yinyang = data.get('dayMasterYinYang', 'N/A')
        day_master_full = data.get('dayMasterFull', 'N/A')
        
        # === 四柱数据 ===
        pillars = data.get('pillars', {})
        
        # === 五行统计 ===
        five_elements = data.get('fiveElements', {})
        
        # === 特殊宫位 ===
        special_palaces = data.get('specialPalaces', {})
        
        # === 起运信息 ===
        yun_info = data.get('yunInfo', {})
        
        # === 当前大运 ===
        current_dayun = data.get('currentDayun', {})
        
        # === 当前流年 ===
        current_liunian = data.get('currentLiuNian', {})
        
        # === 完整大运列表 ===
        all_dayun = data.get('allDayun', [])
        
        # === 生肖 ===
        zodiac = data.get('zodiac', {})
        
        # === 神煞 ===
        shen_sha = data.get('shenSha', {})
        
        # 性别显示
        if gender == 'male':
            gender_display = "Male (男命/乾造)"
        elif gender == 'female':
            gender_display = "Female (女命/坤造)"
        else:
            gender_display = "Unknown"
        
        # 格式化单柱信息
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
        
        # 格式化大运列表
        dayun_list = []
        for d in all_dayun:
            marker = " <- CURRENT" if d.get('isCurrent', False) else ""
            dayun_list.append(
                f"  {d.get('index', '')}. {d.get('ganZhi', '')} "
                f"(Age {d.get('startAge', '')}-{d.get('endAge', '')}, "
                f"{d.get('startYear', '')}-{d.get('endYear', '')}){marker}"
            )
        dayun_str = "\n".join(dayun_list) if dayun_list else "  No data"
        
        # 当前大运状态
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
        
        # 当前流年
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


def get_language_config(lang_code, custom_lang=None):
    """获取语言配置"""
    if lang_code == "custom" and custom_lang:
        return {
            "name": custom_lang,
            "instruction": f"Write your response in fluent, natural {custom_lang}.",
            "pronoun_rule": "Address the user in a formal and respectful manner consistent with this language.",
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
        "max_tokens": 8192
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


@app.route('/', methods=['GET'])
def health_check():
    return jsonify({"status": "running", "version": "4.2", "api_key_set": bool(OPENROUTER_API_KEY)}), 200


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

        # 获取语言设置
        lang_code = req_data.get('language', 'en')
        custom_lang = req_data.get('custom_language', None)
        lang_config = get_language_config(lang_code, custom_lang)

        # 获取模式设置
        reading_mode = req_data.get('mode', 'gentle')
        mode_config = get_mode_config(reading_mode)
        print(f"Reading Mode: {reading_mode} ({mode_config['name']})")

        # 提取性别和姓名
        gender = bazi_json.get('gender', 'unknown')
        client_name = bazi_json.get('name', 'Client')
        print(f"Client: {client_name}, Gender: {gender}, Section: {section_type}, Mode: {reading_mode}")

        # 获取性别相关的八字解读规则
        gender_info = get_gender_instruction(gender, lang_code)

        # 提取语言特定配置
        current_opening = lang_config.get('opening', "In this chapter...")
        current_closing = lang_config.get('closing', "End of chapter.")
        current_pronoun_rule = lang_config.get('pronoun_rule', "Address the user formally.")
        
        # 根据模式选择风格
        if reading_mode == "authentic":
            current_style = lang_config.get('style_authentic', lang_config.get('style_gentle'))
        else:
            current_style = lang_config.get('style_gentle')

        # 格式化完整八字数据
        context_str = format_bazi_context(bazi_json)
        
        # 提取关键数据点供 prompt 使用
        pillars = bazi_json.get('pillars', {})
        day_master = bazi_json.get('dayMaster', '')
        day_master_element = bazi_json.get('dayMasterElement', '')
        current_dayun = bazi_json.get('currentDayun', {})
        current_liunian = bazi_json.get('currentLiuNian', {})
        special_palaces = bazi_json.get('specialPalaces', {})
        five_elements = bazi_json.get('fiveElements', {})
        yun_info = bazi_json.get('yunInfo', {})

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
            
            if gender == "female":
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
            else:
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
- 如果伤官见官（女命），直接说"对婚姻有挑战，可能经历分手或离婚"
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

### GENDER REMINDER:
Client is {gender.upper()}. Apply correct gender-based star interpretations for all predictions.

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


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
