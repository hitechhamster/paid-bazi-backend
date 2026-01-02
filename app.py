from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
import json
import traceback  # 用于打印详细错误日志

app = Flask(__name__)
# 允许所有域名跨域访问 (这是解决 CORS 的关键)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# ================= 配置区域 =================
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
SITE_URL = os.getenv("SITE_URL", "https://your-shopify-store.com")
APP_NAME = "Bazi Pro Calculator"
MODEL_ID = "google/gemini-3-pro-preview"
# ===========================================

def format_bazi_context(data):
    """安全格式化数据，防止报错"""
    try:
        # 使用 .get() 并提供默认值，防止 KeyError
        year = data.get('year', {})
        month = data.get('month', {})
        day = data.get('day', {})
        hour = data.get('hour', {})
        wuxing = data.get('wuxing', {})
        strength = data.get('strength', {})
        dayun = data.get('dayun', {})

        context = f"""
        【四柱八字结构】：
        - 年柱 (祖业): {year.get('gan','')} {year.get('zhi','')} [纳音:{year.get('nayin','')}] [藏干:{year.get('hidden','')}]
        - 月柱 (父母): {month.get('gan','')} {month.get('zhi','')} [纳音:{month.get('nayin','')}] [藏干:{month.get('hidden','')}]
        - 日柱 (本我): {day.get('gan','')} {day.get('zhi','')} [纳音:{day.get('nayin','')}] [日元:{data.get('dayMaster','')}] [藏干:{day.get('hidden','')}]
        - 时柱 (子女): {hour.get('gan','')} {hour.get('zhi','')} [纳音:{hour.get('nayin','')}] [藏干:{hour.get('hidden','')}]

        【能量分析】：
        - 五行: 金[{wuxing.get('metal',0)}] 木[{wuxing.get('wood',0)}] 水[{wuxing.get('water',0)}] 火[{wuxing.get('fire',0)}] 土[{wuxing.get('earth',0)}]
        - 强弱: 同党{strength.get('same',0)}分 vs 异党{strength.get('diff',0)}分

        【大运与神煞】：
        - 当前大运: {dayun.get('ganZhi','')} (起运:{dayun.get('startYear','')}年)
        - 神煞: {', '.join(data.get('shenSha', []))}
        """
        return context
    except Exception as e:
        return f"数据解析异常: {str(e)}"

def ask_ai(system_prompt, user_prompt):
    if not OPENROUTER_API_KEY:
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
        # 增加 verify=False 以防某些 Render 环境下的 SSL 问题 (虽然不推荐生产环境，但能解决 fetch 问题)
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=120
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"OpenRouter API Error: {str(e)}") # 打印到 Render 日志
        return {"error": str(e)}

@app.route('/', methods=['GET'])
def health_check():
    return "Service is Running", 200

@app.route('/api/generate-section', methods=['POST'])
def generate_section():
    # === 全局错误捕获 (防弹衣) ===
    try:
        req_data = request.json
        if not req_data:
            return jsonify({"error": "No JSON received"}), 400

        bazi_json = req_data.get('bazi_data', {})
        section_type = req_data.get('section_type', 'core')
        
        context_str = format_bazi_context(bazi_json)
        
        # 安全获取字段，防止崩溃
        day_master = bazi_json.get('dayMaster', '日主')
        month_zhi = bazi_json.get('month', {}).get('zhi', '月令')
        day_zhi = bazi_json.get('day', {}).get('zhi', '日支')
        
        # 系统提示词
        base_system_prompt = """
        你是一位精通《三命通会》的国学大师。
        请撰写一份【专业八字命书】。
        要求：Markdown格式，论证严密，字数充足(2000字+)。
        """

        specific_prompt = ""

        # 构建提示词 (使用安全变量)
        if section_type == 'core':
            specific_prompt = f"""
            【任务】撰写第一章《命局格局与灵魂》
            【数据】{context_str}
            【指导】
            1. 分析日元[{day_master}]生于[{month_zhi}]月的旺衰。
            2. 结合藏干分析深层性格。
            3. 定格局并取用神。
            """
        
        elif section_type == 'wealth':
            specific_prompt = f"""
            【任务】撰写第二章《事业与财运》
            【数据】{context_str}
            【指导】
            1. 分析财星与财库。
            2. 根据喜用神建议行业。
            3. 分析一生财富大运趋势。
            """

        elif section_type == 'love':
            specific_prompt = f"""
            【任务】撰写第三章《婚恋与正缘》
            【数据】{context_str}
            【指导】
            1. 分析夫妻宫[{day_zhi}]的刑冲合害。
            2. 描述配偶特征与方位。
            3. 预测婚动年份。
            """

        elif section_type == '2026_forecast':
            specific_prompt = f"""
            【任务】撰写第四章《2026丙午流年详批》
            【数据】{context_str}
            【指导】
            1. 分析丙午流年与命局的冲合 (重点查子午冲)。
            2. 逐月(正月至腊月)详细推演运势。
            """
        
        else:
            return jsonify({"error": "Unknown section type"}), 400

        # 调用 AI
        ai_result = ask_ai(base_system_prompt, specific_prompt)

        # 检查 AI 返回结果
        if ai_result and 'choices' in ai_result:
            return jsonify({
                "content": ai_result['choices'][0]['message']['content']
            })
        elif ai_result and 'error' in ai_result:
             # 如果是 API Key 错误等，返回 500
            print(f"AI Error: {ai_result['error']}")
            return jsonify(ai_result), 500
        else:
            return jsonify({"error": "AI response format invalid", "raw": ai_result}), 500

    except Exception as e:
        # === 捕获所有未知错误，打印并返回 JSON ===
        error_msg = traceback.format_exc()
        print(f"CRITICAL SERVER ERROR: {error_msg}") # 这会显示在 Render Logs 里
        return jsonify({"error": "Internal Server Error", "details": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
