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
# ===========================================

def format_bazi_context(data):
    """安全格式化数据"""
    try:
        year = data.get('year', {})
        month = data.get('month', {})
        day = data.get('day', {})
        hour = data.get('hour', {})
        wuxing = data.get('wuxing', {})
        strength = data.get('strength', {})
        dayun = data.get('dayun', {})

        context = f"""
        【Four Pillars Structure】:
        - Year Pillar (Ancestry): {year.get('gan','')} {year.get('zhi','')} [NaYin: {year.get('nayin','')}] [Hidden Stems: {year.get('hidden','')}]
        - Month Pillar (Parents): {month.get('gan','')} {month.get('zhi','')} [NaYin: {month.get('nayin','')}] [Hidden Stems: {month.get('hidden','')}]
        - Day Pillar (Self): {day.get('gan','')} {day.get('zhi','')} [NaYin: {day.get('nayin','')}] [Day Master: {data.get('dayMaster','')}] [Hidden Stems: {day.get('hidden','')}]
        - Hour Pillar (Children): {hour.get('gan','')} {hour.get('zhi','')} [NaYin: {hour.get('nayin','')}] [Hidden Stems: {hour.get('hidden','')}]

        【Five Elements Analysis】:
        - Metal: {wuxing.get('metal',0)}, Wood: {wuxing.get('wood',0)}, Water: {wuxing.get('water',0)}, Fire: {wuxing.get('fire',0)}, Earth: {wuxing.get('earth',0)}
        - Strength: Supporting {strength.get('same',0)} vs Challenging {strength.get('diff',0)}

        【Luck Cycles】:
        - Current Major Luck: {dayun.get('ganZhi','')} (Starting year: {dayun.get('startYear','')})
        - Special Stars: {', '.join(data.get('shenSha', []))}
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
        
        # 提取语言特定配置
        default_config = LANGUAGE_PROMPTS["en"]
        current_opening = lang_config.get('opening', default_config['opening'])
        current_closing = lang_config.get('closing', default_config['closing'])
        current_pronoun_rule = lang_config.get('pronoun_rule', "Address the user formally.")
        
        context_str = format_bazi_context(bazi_json)
        
        day_master = bazi_json.get('dayMaster', 'Day Master')
        month_zhi = bazi_json.get('month', {}).get('zhi', 'Month Branch')
        day_zhi = bazi_json.get('day', {}).get('zhi', 'Day Branch')
        
        # ================= 核心 Prompt (保持新逻辑) =================
        base_system_prompt = f"""
You are a master of BaZi (Chinese Four Pillars of Destiny) with deep knowledge of classical texts like "San Ming Tong Hui" (三命通会) and "Yuan Hai Zi Ping" (渊海子平).

【LANGUAGE & PRONOUNS】
1. Language: {lang_config['instruction']}
2. **Pronoun Rules (CRITICAL)**: {current_pronoun_rule}
   - Do NOT switch between formal and informal addressing. Adhere strictly to this rule.

【MANDATORY STRUCTURE】
1. **START** your response exactly with this phrase: "{current_opening}"
   - Do NOT add greetings like "Welcome back", "Hello again", or "As we discussed previously".
   - Start immediately with the analysis phrase above.
2. **END** your response exactly with this phrase: "{current_closing}"
3. **INDEPENDENCE**: Treat this as a standalone chapter. Assume this is the first time the user is reading this. Do not reference previous conversations.

【WRITING STYLE】
{lang_config['style']}

【CONTENT GUIDELINES】
1. Be ACCESSIBLE: Explain complex concepts in simple terms that anyone can understand, using everyday analogies and examples.
2. Be PROFESSIONAL: Ground your analysis in authentic BaZi principles - mention specific concepts like Day Master strength, useful gods, elemental interactions.
3. Be PERSONAL: Write as if speaking directly to this individual about THEIR unique chart - avoid generic statements.
4. Be PRACTICAL: Provide actionable insights they can apply to their life.
5. Be BALANCED: Acknowledge both strengths and challenges honestly, but frame challenges as growth opportunities.

【FORMAT】
- Use Markdown formatting
- Include clear section headers
- Use bullet points for key insights
- Aim for 2000+ words per chapter
- Add occasional Chinese terms (with translation) for authenticity

【IMPORTANT】
- Never make absolute predictions about health, death, or guaranteed outcomes
- Frame everything as "tendencies," "potentials," or "energetic patterns"
- End sections with empowering, actionable advice
"""

        specific_prompt = ""

        # ================= 恢复了原始详细指令 =================
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
            specific_prompt = f"""
【TASK】Write Chapter 2: Career Empire & Wealth Potential

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
            specific_prompt = f"""
【TASK】Write Chapter 3: Love, Relationships & Soulmate Profile

【CHART DATA】
{context_str}

【MUST COVER】
1. **Spouse Palace Analysis (夫妻宫)**:
   - Analyze the Day Branch [{day_zhi}] as the marriage palace
   - Any clashes, combinations, or special formations?
   - What does this reveal about marriage destiny?

2. **Ideal Partner Profile**:
   - Personality traits that complement this chart
   - Physical characteristics tendencies
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
   - Red flags to watch for

Be warm and hopeful while being honest about challenges.
"""

        elif section_type == '2026_forecast':
            specific_prompt = f"""
【TASK】Write Chapter 4: 2026 Year of the Fire Horse (丙午) - Complete Forecast

【CHART DATA】
{context_str}

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
            return jsonify({"error": "Unknown section type"}), 400

        print(f"Calling AI for section: {section_type} in language: {lang_config['name']}")
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
