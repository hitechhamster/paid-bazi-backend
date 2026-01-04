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

# ================= 多语言配置 (完整版：含强制规则) =================
LANGUAGE_PROMPTS = {
    "en": {
        "name": "English",
        "instruction": "Write your response in fluent, natural English.",
        "pronoun_rule": "Address the user as 'you'. Maintain a consistent professional yet warm tone.",
        "style": "Use a warm, insightful tone like a wise mentor sharing ancient wisdom with a modern friend.",
        "opening": "In this chapter, I will analyze for you...",
        "closing": "End of this chapter."
    },
    "zh": {
        "name": "中文",
        "instruction": "请用流畅自然的中文撰写。",
        "pronoun_rule": "必须统一使用'您'（尊称）来称呼用户，切勿使用'你'。保持语气的一致性。",
        "style": "用温暖睿智的语气，像一位通晓古今的智者在与朋友分享人生智慧。",
        "opening": "本章为您分析...",
        "closing": "此章节完"
    },
    "de": {
        "name": "Deutsch",
        "instruction": "Schreiben Sie Ihre Antwort in flüssigem, natürlichem Deutsch.",
        "pronoun_rule": "Verwenden Sie KONSEQUENT die Höflichkeitsform 'Sie' und 'Ihre' (formal). Vermeiden Sie unbedingt das 'Du' (informal). Dies ist eine strikte Regel.",
        "style": "Verwenden Sie einen warmen, einfühlsamen Ton wie ein weiser Mentor, der alte Weisheiten mit einem modernen Freund teilt.",
        "opening": "In diesem Kapitel analysiere ich für Sie...",
        "closing": "Ende dieses Kapitels."
    },
    "es": {
        "name": "Español",
        "instruction": "Escribe tu respuesta en español fluido y natural.",
        "pronoun_rule": "Utiliza consistentemente la forma 'Usted' (formal) para dirigirte al usuario. No uses 'Tú'.",
        "style": "Usa un tono cálido y perspicaz, como un mentor sabio compartiendo sabiduría ancestral con un amigo moderno.",
        "opening": "En este capítulo, analizo para usted...",
        "closing": "Fin de este capítulo."
    },
    "fr": {
        "name": "Français",
        "instruction": "Rédigez votre réponse dans un français fluide et naturel.",
        "pronoun_rule": "Utilisez systématiquement le vouvoiement ('Vous'). Ne tutoyez jamais l'utilisateur.",
        "style": "Utilisez un ton chaleureux et perspicace, comme un sage mentor partageant une sagesse ancestrale avec un ami moderne.",
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
# ===========================================

def get_gender_instruction(gender, lang_code):
    """获取性别相关的解读指令"""
    # 确定使用英文还是中文规则
    rule_lang = "zh" if lang_code == "zh" else "en"
    
    if gender == "male":
        return GENDER_INSTRUCTIONS["male"].get(rule_lang, GENDER_INSTRUCTIONS["male"]["en"])
    elif gender == "female":
        return GENDER_INSTRUCTIONS["female"].get(rule_lang, GENDER_INSTRUCTIONS["female"]["en"])
    else:
        # 默认返回男性规则，但标注性别未知
        default = GENDER_INSTRUCTIONS["male"].get(rule_lang, GENDER_INSTRUCTIONS["male"]["en"])
        return {
            "pronoun": "they/them/their",
            "bazi_rules": f"Gender not specified. Defaulting to general interpretation:\n{default['bazi_rules']}"
        }

def format_bazi_context(data):
    """安全格式化数据 - 包含性别和姓名"""
    try:
        # ✅ 提取性别和姓名
        gender = data.get('gender', 'unknown')
        name = data.get('name', 'Client')
        
        # 性别显示
        if gender == 'male':
            gender_display = "Male (男命/乾造)"
        elif gender == 'female':
            gender_display = "Female (女命/坤造)"
        else:
            gender_display = "Unknown"
        
        year = data.get('year', {})
        month = data.get('month', {})
        day = data.get('day', {})
        hour = data.get('hour', {})
        wuxing = data.get('wuxing', {})
        strength = data.get('strength', {})
        dayun = data.get('dayun', {})
        birth_info = data.get('birthInfo', {})

        context = f"""
【Client Information / 客户信息】:
- Name / 姓名: {name}
- Gender / 性别: {gender_display}
- Birthplace / 出生地: {birth_info.get('location', 'Unknown')}

【Four Pillars Structure / 四柱结构】:
- Year Pillar 年柱 (Ancestry/祖上): {year.get('gan','')} {year.get('zhi','')} [NaYin/纳音: {year.get('nayin','')}] [Hidden Stems/藏干: {year.get('hidden','')}]
- Month Pillar 月柱 (Parents/父母): {month.get('gan','')} {month.get('zhi','')} [NaYin/纳音: {month.get('nayin','')}] [Hidden Stems/藏干: {month.get('hidden','')}]
- Day Pillar 日柱 (Self/自己): {day.get('gan','')} {day.get('zhi','')} [NaYin/纳音: {day.get('nayin','')}] [Day Master/日主: {data.get('dayMaster','')}] [Hidden Stems/藏干: {day.get('hidden','')}]
- Hour Pillar 时柱 (Children/子女): {hour.get('gan','')} {hour.get('zhi','')} [NaYin/纳音: {hour.get('nayin','')}] [Hidden Stems/藏干: {hour.get('hidden','')}]

【Five Elements Analysis / 五行分析】:
- Metal/金: {wuxing.get('metal', wuxing.get('Metal', 0))}
- Wood/木: {wuxing.get('wood', wuxing.get('Wood', 0))}
- Water/水: {wuxing.get('water', wuxing.get('Water', 0))}
- Fire/火: {wuxing.get('fire', wuxing.get('Fire', 0))}
- Earth/土: {wuxing.get('earth', wuxing.get('Earth', 0))}
- Day Master Strength: Supporting {strength.get('same',0)} vs Challenging {strength.get('diff',0)}

【Luck Cycles / 大运】:
- Current Major Luck/当前大运: {dayun.get('ganZhi','')} (Starting year/起运年: {dayun.get('startYear','')})
- Special Stars/神煞: {', '.join(data.get('shenSha', [])) if data.get('shenSha') else 'None specified'}
"""
        return context
    except Exception as e:
        return f"Data parsing error: {str(e)}"

def get_language_config(lang_code, custom_lang=None):
    """获取语言配置"""
    if lang_code == "custom" and custom_lang:
        return {
            "name": custom_lang,
            "instruction": f"Write your response in fluent, natural {custom_lang}.",
            "pronoun_rule": "Address the user in a formal and respectful manner consistent with this language.",
            "style": "Use a warm, insightful tone like a wise mentor sharing ancient wisdom with a modern friend.",
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
    return jsonify({"status": "running", "api_key_set": bool(OPENROUTER_API_KEY)}), 200

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

        print(f"Request data: {json.dumps(req_data, ensure_ascii=False)[:500]}")
        
        bazi_json = req_data.get('bazi_data', {})
        section_type = req_data.get('section_type', 'core')
        
        # 获取语言设置
        lang_code = req_data.get('language', 'en')
        custom_lang = req_data.get('custom_language', None)
        lang_config = get_language_config(lang_code, custom_lang)
        
        # ✅ 提取性别和姓名
        gender = bazi_json.get('gender', 'unknown')
        client_name = bazi_json.get('name', 'Client')
        print(f"Client: {client_name}, Gender: {gender}")
        
        # ✅ 获取性别相关的八字解读规则
        gender_info = get_gender_instruction(gender, lang_code)
        
        # 提取语言特定配置
        default_config = LANGUAGE_PROMPTS["en"]
        current_opening = lang_config.get('opening', default_config['opening'])
        current_closing = lang_config.get('closing', default_config['closing'])
        current_pronoun_rule = lang_config.get('pronoun_rule', "Address the user formally.")
        
        context_str = format_bazi_context(bazi_json)
        
        day_master = bazi_json.get('dayMaster', 'Day Master')
        month_zhi = bazi_json.get('month', {}).get('zhi', 'Month Branch')
        day_zhi = bazi_json.get('day', {}).get('zhi', 'Day Branch')
        
        # ================= 核心 Prompt (包含性别规则) =================
        base_system_prompt = f"""
You are a master of BaZi (Chinese Four Pillars of Destiny) with deep knowledge of classical texts like "San Ming Tong Hui" (三命通会) and "Yuan Hai Zi Ping" (渊海子平).

【CLIENT GENDER - CRITICAL / 客户性别 - 关键】
The client is: {gender.upper() if gender != 'unknown' else 'UNKNOWN'}
Client name: {client_name}
Use pronouns: {gender_info['pronoun']}

{gender_info['bazi_rules']}

⚠️ IMPORTANT: You MUST apply these gender-specific interpretation rules throughout your analysis, especially for:
- Relationship/marriage analysis (love chapter)
- Spouse palace (Day Branch) interpretation
- Wealth and Officer star meanings

【LANGUAGE & PRONOUNS / 语言与称谓】
1. Language: {lang_config['instruction']}
2. **Pronoun Rules (CRITICAL)**: {current_pronoun_rule}
   - When referring to the client in third person, use: {gender_info['pronoun']}
   - Do NOT switch between formal and informal addressing. Adhere strictly to this rule.

【MANDATORY STRUCTURE / 强制结构】
1. **START** your response exactly with this phrase: "{current_opening}"
   - Do NOT add greetings like "Welcome back", "Hello again", or "As we discussed previously".
   - Start immediately with the analysis phrase above.
2. **END** your response exactly with this phrase: "{current_closing}"
3. **INDEPENDENCE**: Treat this as a standalone chapter. Assume this is the first time the user is reading this. Do not reference previous conversations.

【WRITING STYLE / 写作风格】
{lang_config['style']}

【CONTENT GUIDELINES / 内容指南】
1. Be ACCESSIBLE: Explain complex concepts in simple terms that anyone can understand, using everyday analogies and examples.
2. Be PROFESSIONAL: Ground your analysis in authentic BaZi principles - mention specific concepts like Day Master strength, useful gods, elemental interactions.
3. Be PERSONAL: Write as if speaking directly to this individual about THEIR unique chart - avoid generic statements.
4. Be PRACTICAL: Provide actionable insights they can apply to their life.
5. Be BALANCED: Acknowledge both strengths and challenges honestly, but frame challenges as growth opportunities.

【FORMAT / 格式】
- Use Markdown formatting
- Include clear section headers
- Use bullet points for key insights
- Aim for 3000+ words per chapter
- Add occasional Chinese terms (with translation) for authenticity

【IMPORTANT / 重要提示】
- Never make absolute predictions about health, death, or guaranteed outcomes
- Frame everything as "tendencies," "potentials," or "energetic patterns"
- End sections with empowering, actionable advice
"""

        specific_prompt = ""

        # ================= 各章节详细指令 =================
        if section_type == 'core':
            specific_prompt = f"""
【TASK】Write Chapter 1: Soul Blueprint & Destiny Overview

【CHART DATA】
{context_str}

【MUST COVER】
1. **Day Master Analysis**: Analyze [{day_master}] born in [{month_zhi}] month
   - Is the Day Master strong or weak? Why?
   - What element does this person embody?
   
2. **Hidden Stems Deep Dive**: 
   - What do the hidden stems reveal about their inner nature?
   - Any conflicts or harmony between surface and hidden elements?
   
3. **Destiny Structure (格局)**:
   - What pattern/structure does this chart form?
   - What is their "Useful God" (用神) - the element that brings balance?
   
4. **Core Personality Portrait**:
   - Natural talents and gifts
   - Thinking style and decision-making approach
   - How others perceive them vs. who they really are
   
5. **Life Theme**:
   - What is the central lesson or mission of this lifetime?
   - What unique contribution can they make?

Make it feel like a profound self-discovery journey, not a cold analysis.
"""
        
        elif section_type == 'wealth':
            # ✅ 根据性别调整财运分析的说明
            wealth_gender_note = ""
            if gender == "female":
                wealth_gender_note = """
【GENDER-SPECIFIC NOTE FOR FEMALE CHART】
For women, Wealth Stars primarily represent financial ability and relationship with father.
Officer Stars (正官/七殺) represent husband and male relationships - this will be covered in the Love chapter.
Focus this chapter on her career potential and money-making abilities.
"""
            else:
                wealth_gender_note = """
【GENDER-SPECIFIC NOTE FOR MALE CHART】
For men, Wealth Stars represent both financial ability AND wife/female relationships.
You may briefly mention how wealth stars affect his relationships, but detailed romance analysis belongs in the Love chapter.
"""
            
            specific_prompt = f"""
【TASK】Write Chapter 2: Career Empire & Wealth Potential

{wealth_gender_note}

【CHART DATA】
{context_str}

【MUST COVER】
1. **Wealth Star Analysis (财星)**:
   - Where is their wealth element? Strong or weak?
   - Do they have "wealth storage" (财库)?
   - Natural relationship with money - easy or challenging?

2. **Career DNA**:
   - What industries/fields align with their Useful God?
   - Leadership style: boss, partner, or specialist?
   - Best work environment: corporate, startup, freelance?
   
3. **Wealth-Building Strategy**:
   - Their natural path to prosperity
   - Should they focus on salary, business, or investments?
   - Any warnings about financial pitfalls?
   
4. **Career Timeline**:
   - Major luck cycles affecting career
   - Best years for career moves/changes
   - Periods requiring caution

5. **Practical Recommendations**:
   - Specific industries to consider
   - Skills to develop
   - Networking and partnership advice

Make them feel excited about their potential while being realistic.
"""

        elif section_type == 'love':
            # ✅ 根据性别完全不同的婚恋分析
            if gender == "female":
                love_specific_instruction = f"""
【CRITICAL: FEMALE CHART RELATIONSHIP ANALYSIS / 女命婚恋分析】

For this FEMALE client, you MUST analyze relationships using these rules:
- **Officer Star (正官)** = Represents her HUSBAND, the "right" man, legitimate relationship
- **Seven Killings (七殺)** = Represents boyfriends, lovers, passionate but potentially unstable relationships
- If both 正官 and 七殺 appear: Suggests complexity in love life, possibly multiple significant relationships
- If 正官 is absent but 七殺 is strong: May attract intense but non-traditional relationships
- **Hurting Officer (傷官) clashing with Officer**: Classic indicator of marriage challenges for women
- **Day Branch (日支) [{day_zhi}]** = Her Spouse Palace, represents her husband's characteristics

Analyze:
1. Where are her Officer Stars? Strong or weak?
2. Any 傷官見官 (Hurting Officer seeing Officer) patterns?
3. What type of man is she attracted to based on her chart?
4. What does her spouse palace [{day_zhi}] reveal about her ideal husband?
"""
            else:
                love_specific_instruction = f"""
【CRITICAL: MALE CHART RELATIONSHIP ANALYSIS / 男命婚恋分析】

For this MALE client, you MUST analyze relationships using these rules:
- **Direct Wealth (正財)** = Represents his WIFE, stable and legitimate relationship
- **Indirect Wealth (偏財)** = Represents girlfriends, lovers, romantic but potentially less stable
- If both 正財 and 偏財 appear: Suggests he may have multiple romantic interests
- If 偏財 is stronger than 正財: May prefer casual relationships or marry later
- **Day Branch (日支) [{day_zhi}]** = His Spouse Palace, represents his wife's characteristics
- **Rob Wealth (劫財) clashing with Wealth**: Can indicate competition for partners or financial drain through relationships

Analyze:
1. Where are his Wealth Stars? Strong or weak?
2. Any 比劫奪財 (Rob Wealth taking Wealth) patterns?
3. What type of woman is he attracted to based on his chart?
4. What does his spouse palace [{day_zhi}] reveal about his ideal wife?
"""

            specific_prompt = f"""
【TASK】Write Chapter 3: Love, Relationships & Soulmate Profile

{love_specific_instruction}

【CHART DATA】
{context_str}

【MUST COVER】
1. **Spouse Palace Analysis (夫妻宫)**:
   - Analyze the Day Branch [{day_zhi}] as the marriage palace
   - Any clashes, combinations, or special formations?
   - What does this reveal about marriage destiny?

2. **Ideal Partner Profile**:
   - Personality traits that complement this chart
   - Physical characteristics tendencies (based on elements)
   - Career/background of ideal match
   - Which direction (literally geographic) might they come from?

3. **Love Patterns**:
   - How do they behave in relationships?
   - Common relationship challenges they face
   - Their attachment style based on the chart
   
4. **Marriage Timing**:
   - Which luck cycles activate romance?
   - Favorable years for meeting someone/marriage
   - Years requiring relationship caution

5. **Relationship Advice**:
   - How to attract the right partner
   - How to maintain a healthy relationship
   - Red flags to watch for based on their chart

Be warm and hopeful while being honest about challenges. Remember to use correct pronouns ({gender_info['pronoun']}).
"""

        elif section_type == '2026_forecast':
            specific_prompt = f"""
【TASK】Write Chapter 4: 2026 Year of the Fire Horse (丙午) - Complete Forecast

【CHART DATA】
{context_str}

【GENDER REMINDER】
Client is {gender.upper()}. When discussing relationship forecasts, apply correct gender-based star interpretations.

【MUST COVER】
1. **2026 Overview**:
   - How does 丙午 (Fire Horse) interact with their chart?
   - Check especially for 子午冲 (Rat-Horse clash) if applicable
   - Overall theme and energy of 2026 for them

2. **Key Opportunities**:
   - Which areas of life get activated?
   - Best timing for major decisions
   - Lucky elements and colors for 2026

3. **Challenges to Navigate**:
   - Potential obstacles or difficult periods
   - Health areas to watch
   - Relationship or career cautions

4. **Month-by-Month Breakdown**:
   Provide guidance for each month (Chinese lunar months):
   - Month 1 (寅月 Feb): ...
   - Month 2 (卯月 Mar): ...
   - Month 3 (辰月 Apr): ...
   - Month 4 (巳月 May): ...
   - Month 5 (午月 Jun): ...
   - Month 6 (未月 Jul): ...
   - Month 7 (申月 Aug): ...
   - Month 8 (酉月 Sep): ...
   - Month 9 (戌月 Oct): ...
   - Month 10 (亥月 Nov): ...
   - Month 11 (子月 Dec): ...
   - Month 12 (丑月 Jan 2027): ...

5. **2026 Action Plan**:
   - Top 3 things to focus on
   - Things to avoid
   - Feng shui or element remedies if relevant

Make this feel like a practical roadmap they can actually use.
"""
        
        else:
            return jsonify({"error": f"Unknown section type: {section_type}"}), 400

        print(f"Calling AI for section: {section_type} in language: {lang_config['name']} for {gender} client")
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

