from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
import json

app = Flask(__name__)
CORS(app)

# ================= 配置区域 =================
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
SITE_URL = os.getenv("SITE_URL", "https://your-shopify-store.com")
APP_NAME = "Bazi Pro Calculator"
MODEL_ID = "google/gemini-flash-1.5" # 逻辑强且上下文长的模型
# ===========================================

def format_bazi_context(data):
    """
    将前端数据格式化为 AI 可读的结构化文本。
    """
    try:
        context = f"""
        【四柱八字结构】：
        - 年柱 (祖业/根基)：{data['year']['gan']}{data['year']['zhi']} [纳音:{data['year']['nayin']}] [十神:{data['year']['shishen']}] [藏干:{data['year']['hidden']}]
        - 月柱 (父母/格局)：{data['month']['gan']}{data['month']['zhi']} [纳音:{data['month']['nayin']}] [十神:{data['month']['shishen']}] [藏干:{data['month']['hidden']}]
        - 日柱 (本我/配偶)：{data['day']['gan']}{data['day']['zhi']} [纳音:{data['day']['nayin']}] [日元:{data['dayMaster']}] [藏干:{data['day']['hidden']}]
        - 时柱 (子女/晚运)：{data['hour']['gan']}{data['hour']['zhi']} [纳音:{data['hour']['nayin']}] [十神:{data['hour']['shishen']}] [藏干:{data['hour']['hidden']}]

        【能量分析】：
        - 五行分布：金[{data['wuxing']['metal']}] 木[{data['wuxing']['wood']}] 水[{data['wuxing']['water']}] 火[{data['wuxing']['fire']}] 土[{data['wuxing']['earth']}]
        - 强弱指标：同党{data['strength']['same']}分 vs 异党{data['strength']['diff']}分
        - 日主旺衰状态：{data.get('dayMasterStatus', '需推导')}

        【大运与神煞】：
        - 当前大运：{data['dayun']['ganZhi']} (起运时间:{data['dayun']['startYear']}年)
        - 命局神煞：{', '.join(data.get('shenSha', []))}
        """
        return context
    except Exception as e:
        return f"数据解析异常: {str(e)}"

def ask_ai(system_prompt, user_prompt):
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
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=120
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}

@app.route('/api/generate-section', methods=['POST'])
def generate_section():
    req_data = request.json
    bazi_json = req_data.get('bazi_data', {})
    section_type = req_data.get('section_type', 'core')
    
    context_str = format_bazi_context(bazi_json)
    
    # 1. 系统级指令：确立大师人设
    base_system_prompt = """
    你是一位精通《三命通会》与《子平真诠》的国学大师，同时也是一位心理学家。
    你正在撰写一份【万字终身命书】。
    
    【写作原则】：
    1. **数据驱动**：不要泛泛而谈。你必须根据我提供的“藏干”、“纳音”、“神煞”等具体数据进行推导。
    2. **古今结合**：先引用命理逻辑，再用现代职场/心理学术语解释。
    3. **格式要求**：使用 Markdown，多用 H3 (###) 标题，重要断语加粗。
    4. **字数要求**：本章节内容必须丰富扎实，不少于 2000 字。
    """

    # 2. 章节级指令：【核心修改点】 - 明确告诉AI怎么用数据
    specific_prompt = ""

    if section_type == 'core':
        specific_prompt = f"""
        【任务】：撰写第一章《命局格局与灵魂底色》
        
        【八字详细数据】：
        {context_str}
        
        【写作指导（必须严格遵守）】：
        1. **分析日元本源**：
           - **数据调用**：对比“日元”({bazi_json['dayMaster']}) 与 “月支”({bazi_json['month']['zhi']})。
           - **分析逻辑**：如果月支生助日元，定为得令；否则为失令。结合“五行分布”判断身强身弱。
           - **输出**：用“自然意象”描述命主（如：你是生在深秋的树木，凋零感强...）。
           
        2. **分析深层性格（隐性人格）**：
           - **数据调用**：重点分析四柱的【藏干】数据。
           - **分析逻辑**：天干代表面子，藏干代表里子。如果日支藏干与天干不一致，说明命主表里不一。
           - **输出**：揭示命主不为人知的性格阴暗面或潜能。
           
        3. **分析纳音与祖业**：
           - **数据调用**：使用年柱和月柱的【纳音】({bazi_json['year']['nayin']} / {bazi_json['month']['nayin']})。
           - **分析逻辑**：年柱代表祖上，月柱代表父母。纳音相生则家庭和睦，相克则早年离家。
           
        4. **定格局**：
           - **数据调用**：查看月柱的【十神】。
           - **输出**：明确指出格局名称（如：七杀格、建禄格），并评价格局高低。
        """

    elif section_type == 'wealth':
        specific_prompt = f"""
        【任务】：撰写第二章《事业版图与财富层级》
        
        【八字详细数据】：
        {context_str}
        
        【写作指导（必须严格遵守）】：
        1. **寻找财星与财库**：
           - **数据调用**：在四柱中寻找【正财】、【偏财】。检查地支是否有【辰、戌、丑、未】（作为财库）。
           - **分析逻辑**：财星透干（在天干）代表钱财外露，爱面子；财星藏支代表积蓄。
           - **输出**：判断是“正财命”（上班/稳健）还是“偏财命”（投资/经商）。
           
        2. **职业五行定夺**：
           - **数据调用**：基于“日主旺衰”，找出【喜用神】（五行得分最低或最需要的那个）。
           - **输出**：列出 3 个具体的现代行业建议，必须对应喜用神五行。
           
        3. **十神与工作能力**：
           - **数据调用**：检查是否有【食神/伤官】（代表创意、技术）或【正官/七杀】（代表管理、权力）。
           - **输出**：分析命主适合做技术专家、管理层还是自由职业者？
           
        4. **大运财富趋势**：
           - **数据调用**：结合【当前大运】({bazi_json['dayun']['ganZhi']})。
           - **分析逻辑**：大运五行是帮身还是泄身？
           - **输出**：预测这十年是敛财期还是耗财期。
        """

    elif section_type == 'love':
        specific_prompt = f"""
        【任务】：撰写第三章《婚恋情感与宿命正缘》
        
        【八字详细数据】：
        {context_str}
        
        【写作指导（必须严格遵守）】：
        1. **扫描夫妻宫（日支）**：
           - **数据调用**：重点分析日柱的地支 ({bazi_json['day']['zhi']})。
           - **分析逻辑**：日支五行生助日干吗？（生则配偶宠爱，克则压力大）。
           - **输出**：描述未来配偶的性格画像、能力强弱。
           
        2. **检查刑冲合害**：
           - **数据调用**：检查日支与月支、时支是否有【冲】（如子午冲）、【合】（如六合）、【刑】。
           - **输出**：如果有冲，直言婚姻不稳，建议晚婚或聚少离多。
           
        3. **查看神煞**：
           - **数据调用**：在【命局神煞】列表中查找“桃花”、“红艳”、“孤辰寡宿”。
           - **输出**：如果有桃花，说明异性缘好；如果有孤辰，说明内心孤独。
           
        4. **流年婚动预测**：
           - **分析逻辑**：未来几年中，哪一年地支与夫妻宫相合？
           - **输出**：给出容易结婚或遇到正缘的具体年份。
        """

    elif section_type == '2026_forecast':
        specific_prompt = f"""
        【任务】：撰写第四章《2026 丙午流年·十二月运程详解》
        
        【背景】：
        - 流年：2026 丙午年（天干丙火，地支午火）。
        - 命主日元：{bazi_json.get('dayMaster')}。
        
        【八字详细数据】：
        {context_str}
        
        【写作指导（必须严格遵守）】：
        1. **核心冲合分析 (重中之重)**：
           - **数据调用**：拿“丙午”与命局四柱地支对比。
           - **检测逻辑**：
             - 是否有【子】？(如有，形成子午冲，大凶，预警心血管或变动)。
             - 是否有【午】？(如有，形成午午自刑，预警纠结内耗)。
             - 是否有【丑】？(如有，形成丑午害)。
             - 是否有【寅、戌】？(如有，形成寅午戌三合火局)。
           - **输出**：在开头第一段，明确指出今年的核心风险点或机遇点。
           
        2. **十神流年定义**：
           - **数据调用**：丙火对于日元（{bazi_json.get('dayMaster')}）来说是什么十神？（例如：甲木日主见丙火为食神）。
           - **输出**：定义今年是“食伤年”（主创造/享受）、“官杀年”（主压力/事业）还是“财星年”？
           
        3. **逐月运势撰写**：
           - **要求**：必须从【农历正月】写到【农历十二月】。
           - **输出**：每月一段，结合该月干支与命局的关系，给出具体的生活建议。
        """

    else:
        return jsonify({"error": "Invalid section type"}), 400

    ai_result = ask_ai(base_system_prompt, specific_prompt)

    if ai_result and 'choices' in ai_result:
        return jsonify({
            "content": ai_result['choices'][0]['message']['content']
        })
    else:
        return jsonify({"error": "Failed to generate content", "details": ai_result}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)