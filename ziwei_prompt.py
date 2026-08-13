#!/usr/bin/env python
"""紫微付费详批 —— 事实块、章节规格、机器校对。

从 `tools/ziwei_report.py` 移植而来(那是本地 CLI 版)。三处按服务端改写:

1. **不做分段文件缓存。** 原版 `_seg_path(out_stem, tag, lang)` 默认 `stem='seg'`,
   本地单人跑没问题,搬上多租户服务端会让客户 B 收到客户 A 的缓存章节。
   端点做成无状态,重试单位交给 worker 的逐段调用。

2. **不搬基准率。** `rated`/`rate_block` 在报告链路里从来没被调用过
   (基准率只给免费页/营销用),连带 `assets/ziwei/baserates.json` 依赖一起去掉。

3. **不搬渲染。** `plate_html`/`to_html` 留在本地版;线上十二宫方盘由 worker 的
   报告模板拿 `chart_payload()` 的数据自己画 —— 和风水报告的罗盘同一个套路。

`ds()` 是本模块自带的,不复用 app.py 的 `ask_ai`:定调预判要 `json_mode`,
各章 `max_tokens`/`effort` 逐章不同,而 `_ask_deepseek` 用的是全局常量,
传进去的 max_tokens 根本不生效。
"""
import json, os, re, time

import requests
from ziwei import (build, features, san_fang,
                   ZHI, GAN, PALACES, MAIN14, SHA6, HUA_DISPUTED, SI_HUA)
from ziwei_i18n import L as T, PALACE_EN, STAR_EN_BARE, HUA_EN_BARE

Z_ = {z: i for i, z in enumerate(ZHI)}

DS_URL = "https://api.deepseek.com/chat/completions"
DS_MODEL = os.getenv("DEEPSEEK_MODEL_ID", "deepseek-v4-flash")
DS_TIMEOUT = int(os.getenv("DEEPSEEK_TIMEOUT", "900"))


def ds(prompt, effort='high', max_tokens=32000, retries=3, json_mode=False):
    """DeepSeek 调用。thinking 模式下 temperature 无效,不传。

    ⚠️ **max_tokens 把思考链算在内**,必须为它留出预算。
       effort=high 时思考链能占到总输出的 70-86%。

    防线照 app.py `_ask_deepseek`:空 content 和 finish_reason=length 都要重试 ——
    截断的章节绝不能交付。
    """
    key = os.getenv("DEEPSEEK_API_KEY", "")
    if not key:
        raise RuntimeError('DEEPSEEK_API_KEY 未设置')
    body = {
        "model": DS_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "reasoning_effort": effort,
        "thinking": {"type": "enabled"},
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    last = None
    for attempt in range(1, retries + 1):
        try:
            r = requests.post(DS_URL, json=body, timeout=DS_TIMEOUT,
                              headers={"Authorization": f"Bearer {key}",
                                       "Content-Type": "application/json"})
            r.raise_for_status()
            j = r.json()
            ch = j["choices"][0]
            txt = (ch.get("message") or {}).get("content") or ""
            fin = ch.get("finish_reason", "")
            u = j.get("usage", {})
            print(f"    DS {effort}/{max_tokens}: finish={fin} out={u.get('completion_tokens')} "
                  f"(reasoning={(u.get('completion_tokens_details') or {}).get('reasoning_tokens')})")
            if not txt.strip():
                last = 'empty content'; continue
            if fin == 'length':
                last = 'truncated (finish_reason=length)'; continue
            return txt.strip()
        except Exception as e:
            last = str(e)
            print(f"    DS attempt {attempt} error: {e}")
        time.sleep(2 * attempt)
    raise RuntimeError(f'DeepSeek 失败: {last}')


def facts(c, lang='zh'):
    """所有断语必须能回溯到这里的某一行。AI 不许自己发明盘上没有的东西。
    中英共用 ziwei_i18n 的名表 —— 渲染与校对同源,不会各写一套飘掉。"""
    P = lambda x: T(lang, 'palace')(x)
    S_ = lambda x: T(lang, 'star')(x)
    H = lambda x: T(lang, 'hua')(x)
    inv = {v: k for k, v in c['palace'].items()}
    G = T(lang, 'male') if c['gender'] == 'male' else T(lang, 'female')
    if lang == 'en':
        return _facts_en(c, inv, P, S_, H, G)
    L = [f'出生:{c["clock"]:%Y-%m-%d %H:%M}　{c["place"]}　{G}',
         f'时区 {c.get("tz") or "东八区(默认)"}　当时偏移 UTC{c.get("utc_offset", 8):+.0f}'
         f'(中央经线 {c.get("utc_offset", 8) * 15:+.0f}°)',
         f'真太阳时 {c["solar"]:%Y-%m-%d %H:%M}(校正 {c["corr"]:+.1f} 分)→ 定时辰',
         f'北京时间 {c["beijing"]:%Y-%m-%d %H:%M} → 定农历年月日(节气基准)',
         f'农历 {c["lunar"]}',
         f'命宫 {c["ming_gz"]}　身宫 {ZHI[c["shen"]]}({inv_name(inv, c["shen"])})　'
         f'{c["ju_name"]}　大限{"顺" if c["forward"] else "逆"}行　'
         f'命主 {c["ming_zhu"]}　身主 {c["shen_zhu"]}',
         '', '【十二宫】']
    for nm in PALACES:
        i = inv[nm]
        main = [s for s in c['stars'][i] if s in MAIN14]
        if not main:
            bp = (i + 6) % 12
            bs = '·'.join(x for x in c['stars'][bp] if x in MAIN14)
            main = [f'无主星(借对宫{inv_name(inv, bp)}:{bs})']
        oth = [s for s in c['stars'][i] if s not in MAIN14]
        hua = [f'{n}化{m}' for n, (m, p) in c['hua'].items() if p == i]
        a, b = c['daxian'][i]
        L.append(f'  {nm:4}{c["gong_gan"][i]}{ZHI[i]}　主星:{"　".join(main)}'
                 + (f'　辅煞:{" ".join(oth)}' if oth else '')
                 + (f'　★{" ".join(hua)}' if hua else '')
                 + f'　十二神:{c["changsheng"][i]}　大限 {a}-{b} 岁')
    sf = san_fang(c, c['ming'])
    L += ['', f'【命宫三方四正】{ZHI[c["ming"]]}(命) · {ZHI[sf[1]]}({inv_name(inv,sf[1])},对宫) · '
              f'{ZHI[sf[2]]}({inv_name(inv,sf[2])}) · {ZHI[sf[3]]}({inv_name(inv,sf[3])})',
          '  合计主星:' + '　'.join(sorted({s for i in sf for s in c['stars'][i] if s in MAIN14})),
          '  合计辅煞:' + '　'.join(sorted({s for i in sf for s in c['stars'][i] if s not in MAIN14})),
          '', f'【生年四化 · {c["y_gan"]}干】'
              + '　'.join(f'{n}化{m}(在{ZHI[p]}·{inv_name(inv,p)})'
                          for n, (m, p) in c['hua'].items())]
    lu_pal = next(inv_name(inv, i) for i, v in c['stars'].items() if '禄存' in v)
    L += ['', '【星曜落宫总表 —— 引用任何星前必须对照,写错即报废】',
          '  ' + '　'.join(f'{st}:{inv_name(inv, i)}'
                          for i in range(12) for st in c['stars'][i]),
          f'  注:禄存只有本命一颗(在{lu_pal}宫)。流年只论流年四化(禄权科忌),'
          '本报告不排流年禄存,凡"流年禄存"皆为错误写法。']
    feats = features(c)
    ok_terms = [t for t, ks in
                [('杀破狼', ('杀破狼:坐命', '杀破狼:在对宫')),
                 ('府相朝垣', ('府相朝垣',)), ('机月同梁', ('机月同梁',)),
                 ('禄马交驰', ('禄马交驰',)), ('双禄交流', ('双禄交流',)),
                 ('火贪', ('火贪同宫',)), ('铃贪', ('铃贪同宫',)),
                 ('马头带箭', ('马头带箭',)), ('魁钺夹命', ('魁钺夹命',)),
                 ('羊陀夹命', ('羊陀夹命',)), ('财荫夹印', ('财荫夹印',))]
                if any(feats.get(k) for k in ks)]
    L += ['', '【格局判定(引擎计算,格局名只准用这里列为成立的)】',
          '  成立:' + ('、'.join(ok_terms) or '无'),
          '  其余一切格局名(君臣庆会、日月并明、阳梁昌禄等)一律不得出现。']
    if c['y_gan'] in HUA_DISPUTED:
        L.append('  ⚠️ 该年干的化科各派有分歧,凡涉及化科的判断必须注明这一点')
    if c.get('_extra'):
        L += ['', c['_extra']]
    return '\n'.join(L)


def _facts_en(c, inv, P, S_, H, G):
    """英文事实层。干支/四化一律带中文字 —— 拼音有歧义(戊Wu/午Wu、己Ji/忌Ji),
    中文字才是语言无关的锚点,校对正则中英通用一套。"""
    ln = [f'Born: {c["clock"]:%Y-%m-%d %H:%M} local clock　{c["place"]}　{G}',
          f'Timezone {c.get("tz") or "UTC+8 (assumed)"}, offset at birth '
          f'UTC{c.get("utc_offset", 8):+.0f} (zone meridian {c.get("utc_offset", 8) * 15:+.0f}°)',
          f'True solar time {c["solar"]:%Y-%m-%d %H:%M} '
          f'(correction {c["corr"]:+.1f} min) → sets the HOUR branch',
          f'Beijing time {c["beijing"]:%Y-%m-%d %H:%M} → sets the LUNAR date '
          f'(solar-term basis)',
          f'Lunar: {c["lunar"]}',
          f'Life Palace {c["ming_gz"]}　Body Palace {ZHI[c["shen"]]} '
          f'({P(inv_name(inv, c["shen"]))})　{T("en", "ju")(c["ju_name"])}　'
          f'Major limits run {"forward" if c["forward"] else "backward"}',
          '', T('en', 'twelve')]
    for nm in PALACES:
        i = inv[nm]
        main = [S_(x) for x in c['stars'][i] if x in MAIN14]
        if not main:
            bp = (i + 6) % 12
            bs = ' + '.join(S_(x) for x in c['stars'][bp] if x in MAIN14)
            main = [T('en', 'no_main').format(p=P(inv_name(inv, bp)), s=bs)]
        oth = [S_(x) for x in c['stars'][i] if x not in MAIN14]
        hu = [f'{S_(nm2)} {H(m)}' for nm2, (m, pp) in c['hua'].items() if pp == i]
        a, b = c['daxian'][i]
        ln.append(f'  {P(nm):18}{c["gong_gan"][i]}{ZHI[i]}　majors: {", ".join(main)}'
                  + (f'　others: {", ".join(oth)}' if oth else '')
                  + (f'　★{"; ".join(hu)}' if hu else '')
                  + f'　limit {a}-{b}')
    sf = san_fang(c, c['ming'])
    ln += ['', T('en', 'sanfang') + ': ' + ' · '.join(
               f'{ZHI[i]} ({P(inv_name(inv, i))})' for i in sf),
           '  majors in view: ' + ', '.join(sorted(
               {S_(x) for i in sf for x in c['stars'][i] if x in MAIN14})),
           '  others in view: ' + ', '.join(sorted(
               {S_(x) for i in sf for x in c['stars'][i] if x not in MAIN14})),
           '', T('en', 'natal_hua').format(g=c['y_gan']) + ' ' + '; '.join(
               f'{S_(nm2)} {H(m)} (in {ZHI[pp]} · {P(inv_name(inv, pp))})'
               for nm2, (m, pp) in c['hua'].items())]
    lu_pal = next(inv_name(inv, i) for i, v in c['stars'].items() if '禄存' in v)
    ln += ['', T('en', 'star_table') + ' — check every star against this before writing',
           '  ' + '　'.join(f'{S_(x)}:{P(inv_name(inv, i))}'
                            for i in range(12) for x in c['stars'][i]),
           f'  Note: there is only ONE natal Lu Cun (in {P(lu_pal)}). Flowing years carry '
           'only the four transformations — "annual Lu Cun" is always wrong.']
    feats = features(c)
    ok = [T('en', 'geju')(t) for t, ks in _GEJU_KEYS if any(feats.get(k) for k in ks)]
    ln += ['', '[FORMATION CHECK — engine-computed; use ONLY those listed as present]',
           '  present: ' + (', '.join(ok) or 'none'),
           '  Any other formation name is forbidden.']
    if c['y_gan'] in HUA_DISPUTED:
        ln.append(f'  WARNING: schools disagree on the Hua Ke star for the '
                  f'{c["y_gan"]} stem — say so wherever Hua Ke is used.')
    if c.get('_extra'):
        ln += ['', c['_extra']]
    return chr(10).join(ln)


def inv_name(inv, pos):
    return next(k for k, v in inv.items() if v == pos)


_GEJU_KEYS = [('杀破狼', ('杀破狼:坐命', '杀破狼:在对宫')),
              ('府相朝垣', ('府相朝垣',)), ('机月同梁', ('机月同梁',)),
              ('禄马交驰', ('禄马交驰',)), ('双禄交流', ('双禄交流',)),
              ('火贪', ('火贪同宫',)), ('铃贪', ('铃贪同宫',)),
              ('马头带箭', ('马头带箭',)), ('魁钺夹命', ('魁钺夹命',)),
              ('羊陀夹命', ('羊陀夹命',)), ('财荫夹印', ('财荫夹印',))]

def _star_palace(c, star):
    for i, v in c['stars'].items():
        if star in v:
            return i
    return None


def daxian_hua_facts(c):
    """每个大限的宫干自带一组四化 —— 该限化忌落哪宫,哪宫就是这十年的坑。
    只列禄/忌两头(权科噪音大),按岁数顺序。"""
    inv = {v: k for k, v in c['palace'].items()}
    rows = []
    for i, (a, b) in sorted(c['daxian'].items(), key=lambda kv: kv[1][0]):
        if a > 92:      # 93 岁以后的大限是填充物,不进报告
            continue
        g = c['gong_gan'][i]
        lu, _, _, ji = SI_HUA[g]
        pl = _star_palace(c, lu); pj = _star_palace(c, ji)
        rows.append(f'  {a}-{b} 岁 走{c["palace"][i]}({ZHI[i]}),宫干{g}:'
                    f'化禄={lu}(落{c["palace"][pl]})　化忌={ji}(落{c["palace"][pj]})')
    return '【大限四化 · 每个十年自己的红利位与坑位】\n' + '\n'.join(rows)


def year_scan_facts(c, start=2026, n=15):
    """逐年扫:流年命宫落哪、流年禄忌打到哪,标出双忌年/红鸾天喜入命年(婚恋窗口)。"""
    born = c['clock'].year
    ji0_star = next(nm for nm, (m, _) in c['hua'].items() if m == '忌')
    dx_start = {a: i for i, (a, b) in c['daxian'].items() if a <= 92}
    rows = []
    for y in range(start, start + n):
        gan = GAN[(y - 1984) % 10]; zhi = ZHI[(y - 1984) % 12]
        pos = ZHI.index(zhi)
        age = y - born + 1
        lu, _, _, ji = SI_HUA[gan]
        pj = _star_palace(c, ji)
        cell = c['stars'][pos]
        tags = []
        if age in dx_start:
            di = dx_start[age]; dg = c['gong_gan'][di]
            dlu, _, _, dji = SI_HUA[dg]
            tags.append(f'⚡换大限:自此十年走{c["palace"][di]}限'
                        f'(宫干{dg},限禄={dlu} 限忌={dji})')
        if ji == ji0_star:
            tags.append('⚠️双忌叠加(流年忌与生年忌同星)')
        if '红鸾' in cell:
            tags.append('★红鸾入流年命宫(婚恋窗口)')
        if '天喜' in cell:
            tags.append('★天喜入流年命宫(婚恋窗口)')
        if _star_palace(c, lu) == pos:
            tags.append('☆流年禄入命')
        if pos == c['shen']:
            tags.append('流年命宫踩身宫')
        main = '·'.join(x for x in cell if x in MAIN14) or '无主星'
        rows.append(f'  {y} {gan}{zhi} 虚岁{age}　流年命宫={c["palace"][pos]}({main})'
                    f'　流年忌:{ji}→{c["palace"][pj]}' + ('　' + ' '.join(tags) if tags else ''))
    return f'【未来{n}年逐年扫描】(流年命宫=当年地支所在宫)\n' + '\n'.join(rows)


def hour_sens_facts(c, y, mo, d, h, mi, lng, gender, place, tz=None):
    """时辰敏感度:钟表时间 ±1 小时各排一张,看命宫动不动。
    紫微错时辰是命宫移位、全盘作废 —— 稳不稳本身就是值得写进报告的信息。"""
    import datetime as _dt
    base = _dt.datetime(y, mo, d, h, mi)
    res = []
    for off in (-1, 1):
        t = base + _dt.timedelta(hours=off)
        cc = build(t.year, t.month, t.day, t.hour, t.minute, lng, gender, place, tz)
        res.append((off, cc['ming'], cc['ming_gz']))
    moved = [(o, gz) for o, m, gz in res if m != c['ming']]
    if not moved:
        return ('【时辰稳定性】出生时间前后各挪一小时,命宫都不动 —— '
                '这张盘对时辰误差不敏感,记错半小时也不影响结论。')
    det = ';'.join(f'{"早" if o < 0 else "晚"}一小时命宫变为{gz}' for o, gz in moved)
    return (f'【时辰稳定性】⚠️ 这张盘对时辰敏感:{det}。'
            '本报告按所报时刻(经真太阳时校正)排盘;若出生时间有出入,以上结论需重排。')




# ──────────── 生成后校对:同星异宫是分段生成的老病,靠机器扫不靠人眼 ────────────

def _palace_tokens(c, lang='zh'):
    if lang == 'en':
        return [(nm, PALACE_EN[nm] + ' Palace') for nm in PALACES]
    return [(nm, nm if nm == '命宫' else nm + '宫') for nm in PALACES]


# 中英各一套模式,但**名表同源**(ziwei_i18n),不会各写一套飘掉。
_PAT = {
    'zh': dict(
        sit=r'(?:又|也|则|就)?(?:在|落在|坐在|坐|同宫在|安在)([\u4e00-\u9fff]{1,2})宫',
        cut=['三方', '对宫', '会照', '借', '冲', '照', '流年', '当年', '该年', '大限', '限',
             '是', '像', '如同', '宛如', '般', '与', '和', '跟', '比作',
             '。', '!', '?', ';', chr(10)],
        pre=['借', '对宫', '流年', '大限'],
        mark=('主星', '辅星', '坐', '见', '带', '同宫', '同度', '里', '中', '有', '加'),
        lucun=r'流年禄存', ordinal=r'第[一二三四五六七八九十]宫',
        hua=r'([\u4e00-\u9fff]{2})化([禄权科忌])',
    ),
    'en': dict(
        sit=r'\s+(?:is\s+|sits\s+|sitting\s+|falls\s+)?'
            r'(?:in|at|occupies|located in|placed in)\s+(?:the\s+)?(\w+)\s+Palace',
        # ⚠️ 不要把 ' and '/' with '/' is ' 当断点 —— 英文列举("A and B, with C")
        #    天然用它们,当断点会把同宫的星切掉,漏检。只断真正的语境切换与比喻。
        cut=['San Fang', 'opposite', 'oppose', 'borrow', 'clash', 'trine',
             'flowing year', 'that year', 'major limit', 'limit',
             ' like ', ' such as ', ' compared', ' resembles',
             '.', '!', '?', ';', chr(10)],
        pre=['borrow', 'opposite', 'flowing year', 'major limit'],
        mark=('majors', 'others', 'sits', 'holds', 'carries', 'with', 'in', 'has'),
        lucun=r'(?:annual|flowing[- ]year)\s+Lu Cun|Lu Cun of the (?:flowing )?year',
        ordinal=r'(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|'
                r'tenth|eleventh|twelfth)\s+house',
        hua=r'([A-Z][a-z]+(?: [A-Z][a-z]+)?)\s+Hua\s+(Lu|Quan|Ke|Ji)\b',
    ),
}

def verify_text(text, c, lang='zh'):
    """返回 (hard, soft)。

    **分级是有意的**:
      hard = 确定性规则(「星在X宫」直陈句、流年禄存、序数宫)——命中必错,拦截。
      soft = 窗口启发式(「X宫……某星」)——会误判,只告警不拦。
    2026-08-11 教训:曾把 soft 也当拦截,流年章一句「当年文昌化忌」被判成
    「文昌在夫妻宫」,整轮 15 分钟生成被 raise 掉。**启发式不配决定成败。**"""
    pt = _PAT[lang]
    inv = {v: k for k, v in c['palace'].items()}
    name = (lambda x: STAR_EN_BARE.get(x, x)) if lang == 'en' else (lambda x: x)
    star_pal = {name(st): inv_name(inv, i) for i in range(12) for st in c['stars'][i]}
    if lang == 'en':
        short = {PALACE_EN[n]: n for n in PALACES}
        disp = lambda pal: PALACE_EN[pal] + ' Palace'
    else:
        short = {(n[:-1] if n.endswith('宫') else n): n for n in PALACES}
        disp = lambda pal: pal if pal.endswith('宫') else pal + '宫'
    hard, soft = [], []

    for st, pal in star_pal.items():
        for m in re.finditer(re.escape(st) + pt['sit'], text):
            claimed = m.group(1)
            if claimed in short and short[claimed] != pal:
                hard.append(f'{st} placed in {disp(short[claimed])} '
                            f'but actually in {disp(pal)}' if lang == 'en'
                            else f'{st}被写到{disp(short[claimed])},实际在{disp(pal)}')

    for m in re.finditer(pt['lucun'], text):
        hard.append('"annual Lu Cun" — flowing years carry only transformations'
                    if lang == 'en'
                    else '出现"流年禄存"——流年只论四化,禄存只有本命一颗')
    for m in re.finditer(pt['ordinal'], text):
        hard.append(f'ordinal house wording "{m.group(0)}" — use palace names'
                    if lang == 'en'
                    else f'出现序数宫位写法"{m.group(0)}",一律用宫名')

    for nm, tok in _palace_tokens(c, lang):
        me = PALACE_EN[nm] if lang == 'en' else (nm[:-1] if nm.endswith('宫') else nm)
        cutters = [k for k in short if k != me] + pt['cut']
        for m in re.finditer(re.escape(tok), text):
            pre = text[max(0, m.start() - 12):m.start()]
            if any(k in pre for k in pt['pre']):
                continue
            win = text[m.end():m.end() + (70 if lang == 'en' else 40)]
            cut = len(win)
            for kw in cutters:
                k = win.find(kw)
                if k >= 0:
                    cut = min(cut, k)
            win = win[:cut]
            for st, pal in star_pal.items():
                if pal == nm:
                    continue
                if lang == 'en':
                    # ⚠️ 必须按词边界:拼音星名互为子串 —— Tian Xi(天喜)⊂ Tian Xiang(天相),
                    #    裸 find 会把「天相」读成「天喜」,凭空造出一条落宫矛盾。
                    _m = re.search(r'\b' + re.escape(st) + r'\b', win)
                    si = _m.start() if _m else -1
                else:
                    si = win.find(st)
                if si < 0:
                    continue
                if lang == 'zh' and win[si + len(st):si + len(st) + 1] == '化':
                    continue                      # 「文昌化忌」是四化,不是落宫
                if lang == 'en' and win[si + len(st):si + len(st) + 5].strip().startswith('Hua'):
                    continue
                if st == '紫微' and win[si + 2:si + 4] == '斗数':
                    continue                      # 「紫微斗数」是学科名
                if any(0 <= win.find(mk) < si for mk in pt['mark']):
                    soft.append(f'{tok} description mentions {st}, which is in {disp(pal)}'
                                if lang == 'en'
                                else f'{tok}的描述里出现了{st},但{st}实际在{disp(pal)}')
    return sorted(set(hard)), sorted(set(soft))




# 有严格定义的格局:能算的交引擎判,不能算的直接禁用。
# "校对从『星在哪』升到『话有据』"(用户 2026-08-11 审稿结论)。
GEJU_TERMS = {
    '杀破狼': ('杀破狼:坐命', '杀破狼:在对宫'),
    '府相朝垣': ('府相朝垣',), '机月同梁': ('机月同梁',),
    '禄马交驰': ('禄马交驰',), '双禄交流': ('双禄交流',),
    '火贪': ('火贪同宫',), '铃贪': ('铃贪同宫',),
    '马头带箭': ('马头带箭',), '魁钺夹命': ('魁钺夹命',),
    '羊陀夹命': ('羊陀夹命',), '财荫夹印': ('财荫夹印',),
}
GEJU_FORBIDDEN = ['君臣庆会', '明珠出海', '石中隐玉', '日月并明', '阳梁昌禄',
                  '七杀朝斗', '雄宿朝垣', '日照雷门', '月朗天门', '英星入庙',
                  '紫府同宫', '金舆扶驾', '刑囚夹印']
GEJU_TERMS_EN = {k: v.split(' (')[0] for k, v in __import__('ziwei_i18n').GEJU_EN.items()}
GEJU_FORBIDDEN_EN = ['Jun Chen Qing Hui', 'Ming Zhu Chu Hai', 'Shi Zhong Yin Yu',
                     'Ri Yue Bing Ming', 'Yang Liang Chang Lu', 'Qi Sha Chao Dou',
                     'Zi Fu Tong Gong', 'Xing Qiu Jia Yin']
HUA_IDX = {'禄': 0, '权': 1, '科': 2, '忌': 3}
SIHUA_STARS = {st for v in SI_HUA.values() for st in v}


def _gans_in(seg):
    import re as _re
    out = set(_re.findall(r'([甲乙丙丁戊己庚辛壬癸])干', seg))
    out |= set(_re.findall(r'宫干([甲乙丙丁戊己庚辛壬癸])', seg))
    # 英文稿里干支照样带中文字(见 ziwei_i18n),所以这里中英通用
    out |= set(_re.findall(r'([甲乙丙丁戊己庚辛壬癸])\s*stem', seg))
    out |= set(_re.findall(r'stem\s*[((]?([甲乙丙丁戊己庚辛壬癸])', seg))
    out |= set(_re.findall(r'[((]([甲乙丙丁戊己庚辛壬癸])[))]', seg))
    for y in _re.findall(r'20\d{2}', seg):
        out.add(GAN[(int(y) - 1984) % 10])
    return out


def verify_claims(text, c, lang='zh'):
    """论述层:格局名与四化归属。返回 (hard, soft)。
    英文稿里干支照样带中文字(见 ziwei_i18n 说明),所以天干识别中英通用一套。"""
    pt = _PAT[lang]
    hard, soft = [], []
    feats = features(c)
    name = (lambda x: STAR_EN_BARE.get(x, x)) if lang == 'en' else (lambda x: x)
    term_of = (lambda t: GEJU_TERMS_EN[t]) if lang == 'en' else (lambda t: t)
    for term, keys in GEJU_TERMS.items():
        shown = term_of(term)
        if shown in text and not any(feats.get(k) for k in keys):
            hard.append(f'formation "{shown}" does not hold for this chart'
                        if lang == 'en' else f'格局「{shown}」在本盘不成立,不得使用')
    for term in (GEJU_FORBIDDEN_EN if lang == 'en' else GEJU_FORBIDDEN):
        if term in text:
            hard.append(f'formation "{term}" is not engine-verified; do not use'
                        if lang == 'en' else f'格局「{term}」未经引擎判定,不得使用')

    star_of = {name(s): s for v in SI_HUA.values() for s in v}
    hua_of = {'禄': '禄', '权': '权', '科': '科', '忌': '忌',
              'Lu': '禄', 'Quan': '权', 'Ke': '科', 'Ji': '忌'}
    birth_pairs = {(name(n), m) for n, (m, _) in c['hua'].items()}
    splitter = r'[。!?;\n]' if lang == 'zh' else r'[.!?;\n]'

    for sent in re.split(splitter, text):
        gans = _gans_in(sent)
        if not gans:
            continue
        for star, h in re.findall(pt['hua'], sent):
            if star not in star_of:
                continue
            hm = hua_of.get(h)
            if hm is None or (star, hm) in birth_pairs:
                continue
            if not any(name(SI_HUA[g][HUA_IDX[hm]]) == star for g in gans):
                exp = ' '.join(f'{g}={name(SI_HUA[g][HUA_IDX[hm]])}' for g in sorted(gans))
                hard.append(f'wrong transformation: "{star} Hua {h}" contradicts the '
                            f'stem in this sentence (should be {exp})' if lang == 'en'
                            else f'四化归属错误:「{star}化{h}」与句中天干不符(应为 {exp})')

    for para in text.split('\n\n'):
        gans = _gans_in(para)
        for a, _b in re.findall(r'(\d{1,3})\s*[-–—~]\s*(\d{1,3})', para):
            for i, (da, db) in c['daxian'].items():
                if da == int(a):
                    gans.add(c['gong_gan'][i])
        if not gans:
            continue
        for star, h in re.findall(pt['hua'], para):
            if star not in star_of:
                continue
            hm = hua_of.get(h)
            if hm is None or (star, hm) in birth_pairs:
                continue
            if not any(name(SI_HUA[g][HUA_IDX[hm]]) == star for g in gans):
                soft.append(f'"{star} Hua {h}" does not match the stems in this paragraph '
                            f'({"".join(sorted(gans))}) — check for a mix-up'
                            if lang == 'en'
                            else f'「{star}化{h}」与所在段落的天干语境对不上,查一下是否串了'
                                 f'(段内天干:{"".join(sorted(gans))})')
    return sorted(set(hard)), sorted(set(soft))


# ────────────────────────────────── 章节 ──────────────────────────────────

# 风格对齐气流八字万字产品(paid-bazi-backend):深入浅出、引用真实盘面、写足。
# 基准率那套从报告里整个拿掉 —— 用户判决"太离奇"(2026-08-11),读者要的是解盘,
# 不是统计学。数据表留着给免费页/营销用,付费报告不提。
STYLE = """
【写法 —— 深入浅出】
中文,第二人称"你"。像一个懂行的老师傅坐在对面,把你的盘一格一格讲给你听。
- **每个小节开头,先用一句加粗的大白话给出该节结论**,然后再展开讲为什么。
- 任何术语第一次出现,当场用一句大白话解释清楚再往下走。
  例:"命宫又同度天马(子年天马正好在寅),这是标准的'驿马入命':越动越旺,
  离开出生地反而运势打开。"——先讲是什么,紧跟着讲意味着什么。
- **具体引用盘面**:说到哪一宫,就把那一宫坐的星(含辅星、四化)摆出来,
  让读者能对着上方命盘逐格核对。不引用盘面的泛泛之谈一句都不要。
- 大白话比喻可以用且鼓励(如"破军坐命的人天生'不安分'——不是贬义,
  是骨子里排斥一成不变"),但一节里别堆超过两个。
- 判断要落到实处:讲到事业就说适合什么样的环境和行业方向,讲到内耗就给
  具体的化解动作。不写"会有起伏""注意平衡"这类没内容的话。
- 篇幅写足。这是付费的深度详批,读者按万字产品的标准付钱,别惜字。
- 不喊口号不打气;不写"综上所述""值得注意的是""根据您的命盘显示"这类 AI 腔。

【硬约束 —— 违反即报废】
1. 只能用【事实】里给出的数据。盘上没有的星、没有的宫位关系,一个字都不许编。
2. 禁止使用庙旺利陷(庙/旺/利/平/陷)。本引擎不提供亮度,任何依赖亮度的判断不写。
3. **禁止出现百分比、基准率、"罕见""款型""区分度"这类统计话术。**
4. 无主星的宫一律以【事实】里标注的"借对宫某宫:某星"为准,**禁止自行推算借哪一宫**;
   分析时用一句话说明借宫规矩。
7. **强信号也说倾向**:禁写"一定""必然""一步到位";重大年份写"最该发力/最需收着"。
8. 峰值十年、人生拐点这类重判断,**必须与【全篇统一结论】一致**,并给至少三条
   独立盘面证据;各章不得另立论点、不得互相打架。
9. **每颗星只有一个落宫**,以【星曜落宫总表】为准;说"某星在某宫"前先查表。
10. 宫位一律用宫名,禁止"第N宫"序数写法(易与西洋占星混淆);
    化禄是四化、禄存是另一颗星,禁止混用,禁止出现"流年禄存"。
11. 年份段落里的虚岁一律以该段标题为准,段内不得出现第二个岁数。
12. 写「某星化某」之前,先对照【大限四化】/流年干核对归属 —— 禄权科忌一字之差
    含义完全不同;格局名只准用【格局判定】列为成立的,并按其判据推理。
13. 比喻纪律:全篇自创比喻不超过 4 处;一个比喻只对应一颗星,不许一套比喻
    硬套多颗星;不许为了修辞升级引入新的格局名。
5. 不预测寿命、疾病诊断、生死、具体金额。身体只谈倾向与提示。
6. 不确定就说不确定。宁可少写一条,不许凑。
"""

CHAPTERS = [
    ('A', 'high', 38000, """写前三个部分。

## 命格画像
**开篇即形象**:用一句大白话给这张盘一个定格形象,像给人起外号
(例:"你是一个带刀闯关外的马匪头子""你是账房里坐着一位女捕头")。
形象必须从盘上推出来 —— 命宫主星给的性子、同宫辅煞给的气质、身宫给的去向,
每一笔都有出处。要有劲、见血、让人会心一笑,但不贬低不吓人。
定格之后用 200 字左右拆解这个形象:哪颗星给的"匪气",哪颗星给的"分寸",
哪颗星决定他抢完往哪跑。结尾一句自然过渡到下一节。
若【时辰稳定性】标了敏感,在本节末尾用一句话如实告知。

## 命格骨架
第一句加粗核心结论:把命宫、三方四正、身宫落点串起来。然后:
- 大白话讲透命宫主星的性子;同宫辅星杂曜(天马、孤辰之类)当场解释合进来讲。
- 迁移宫(对宫)对照:在外的形象和命宫性子的反差。
- 身宫落点=人生重心,该宫的星与煞讲清楚。
- 格局名(杀破狼/府相朝垣/机月同梁)讲透它的人生节奏,不只报名字。
1200 字以上。

## 内心世界
福德宫全解:同宫每颗星逐一大白话(化忌的典型表现、煞星组合的体感、
兜底的星),最后给落地解法(具体动作,不写鸡汤)。
命主/身主与命宫若有张力,在结尾点破。800 字以上。"""),

    ('B', 'high', 36000, """写"事业·财富·人缘"三个部分。

## 事业
官禄宫全解:主星做事风格、辅星助力、煞星的竞争形态;身宫若在此点明重心所在。
落到实处:适合什么环境什么行业,不适合什么。600 字以上。

## 财富
**财帛宫和田宅宫放在一起讲**:财帛=流量,田宅=存量。分别摆星讲透,
合起来给"你的钱以什么形态存在"的判断,讲适不适合合伙、怎么管钱。600 字以上。

## 人缘与出外
交友宫+迁移宫:朋友圈是助力还是消耗、什么贵人、出外的运和形象。
化禄/化科落这两宫的重点展开。500 字以上。"""),

    ('C', 'high', 36000, """写"感情·家人·身体"三个部分。

## 感情与婚姻
夫妻宫全解:配偶画像、相处模式、同宫煞星的摩擦形态。
红鸾天喜落哪宫、孤辰寡宿天姚咸池落哪宫,与婚恋有关的都要点到并解释。
**夫妻宫对宫是官禄宫**:若官禄有煞,讲清事业与婚姻的结构性对冲,给具体建议。
800 字以上。

## 家人
父母、兄弟、子女三宫各一段,无主星按借对宫处理并说明。从星出发讲关系形态,
不写套话。500 字以上。

## 身体
疾厄宫:摆星,讲倾向和注意方向(作息、情绪对身体的路径),明确说不是诊断。
300 字以上。"""),

    ('D', 'high', 38000, """写"十年地图"和"这两年"。

## 十年地图
一句话讲大限规矩(命宫起、起运岁=局数、顺逆看阴阳男女)。
按【事实】做表(**只列到 83-92,之后的不写**):岁数 / 宫位 / 主星与煞 /
该限四化(化禄落哪宫=红利位,化忌落哪宫=坑位)/ 一句话定性。
表后写三段:
(a) **现在走在哪一步**(2026 年按虚岁):这十年的主题、体感,该限化忌落的宫
    意味着这十年的坑具体在哪块;
(b) **下一步**:几岁开始、什么性质、和现在的反差;
(c) **一生力量最集中的十年**:直接采用【全篇统一结论】给的峰值,把三条证据展开;
    若统一结论给了从属兑现期,按"主峰挣顶点、从期收成果"的主从关系写,不许并列。
1000 字以上。

## 这两年
2026 丙午、2027 丁未各一段:流年命宫落本命哪宫、流年四化打到哪
(丙:天同禄 天机权 文昌科 廉贞忌;丁:太阴禄 天同权 天机科 巨门忌),
与生年四化叠加冲突之处点明,给出这一年该做什么、该避什么。每年 400 字左右。"""),

    ('E', 'high', 36000, """写最后两个部分。

## 未来十五年,重点看这几年
把【未来15年逐年扫描】做成一张表:年份 / 干支 / 虚岁 / 流年命宫 / 一句话提示。
表要全 15 年,但**表后只挑 4-6 个真正值得圈出来的年份逐个展开**。
展开顺序**严格按时间先后**,每段开头保留 ⚡/★/⚠️ 分量标记:
- 带⚡换大限标记的年份写最重:讲清从哪一幕换到哪一幕、限禄限忌落哪、该做的准备;
  **并且必须点明上一限的限忌就此卸任** —— 若十年地图里据旧限限忌给过提醒
  (如"出外碰壁"),要写一句"该提醒到换限前一年为止",与十年地图互相印证,
  不许留下一处说碰壁、一处说快去的自相矛盾;
- 带★婚恋窗口标记的年份(红鸾/天喜入流年命宫):讲清那年感情上的形态,
  **并把该年流年忌的落宫转成一条落地告诫**(如文昌文曲忌=文书合约易错),
  只写亮点不写告诫的年份展开不合格;
- 带⚠️双忌叠加的年份:那年哪块最耗,怎么提前避;
- 流年禄入命/踩身宫的年份:该发力做什么(说倾向,不说"一定")。
每个重点年 100-150 字,写具体,别写"总体运势不错"。

## 一页总结
全篇收口,读者合上报告能带走的一页。三块,各用一个小清单:
**三条判断**(全篇最重要的三个结论,每条一句);
**三条动作**(落地到行为的建议,每条一句);
**三个年份**(未来15年里最该记住的三年:拐点年/发力年/收着年,各配半句说明)。
不写新内容,只提炼前文。写完就停。"""),
]


# 干支与四化保留中文字 —— 既是既有风格,也是校对闸的语言无关锚点(见 ziwei_i18n)。
STYLE_EN = """
[HOW TO WRITE]
English, second person "you". Write like an experienced reader sitting across the
table, going palace by palace — not like marketing copy, not like a textbook.
- **Open every section with one bolded plain-English verdict**, then explain why.
- The first time a term appears, define it in one clause and move on. Example:
  "Tian Ma (天馬), the Travelling Horse, sits in your Life Palace — you do better
  the more you move, and leaving your birthplace opens things up."
- **Quote the chart**: name the exact stars (including auxiliaries and any
  transformation) in whatever palace you discuss, so the reader can check them
  against the chart above. No generic statements that skip the chart.
- Plain metaphors are welcome, but at most two per section.
- Land every judgement somewhere concrete: for career, name the kind of
  environment and field; for inner strain, name the actual action that helps.
  Never write "there will be ups and downs" or "seek balance".
- Write in full. This is a paid, in-depth reading — do not be brief.
- No cheerleading. Never write "as we can see", "in conclusion", "it is worth
  noting", "based on your chart" — those read as filler.

[HARD CONSTRAINTS — violating any of these voids the section]
1. Use ONLY the data in [FACTS]. Never invent a star or a palace relationship.
2. NEVER use brightness grades (miao/wang/li/ping/xian). The engine does not
   provide them; skip any judgement that would depend on brightness.
3. No percentages, base rates, or "rare/common" statistics language.
4. Empty palaces: use exactly the borrowed palace given in [FACTS]; never work
   out the borrowing yourself. Say once, in a clause, that an empty palace
   borrows from its opposite.
5. No predictions of lifespan, medical diagnosis, death, or specific amounts of
   money. Health is discussed as tendency and what to watch only.
6. If something is uncertain, say so. Leave a claim out rather than pad.
7. Refer to palaces by name (Career Palace, Travel Palace). NEVER use ordinal
   houses ("seventh house") — that is Western astrology and does not apply.
8. There is only ONE natal Lu Cun. A flowing year brings only the four
   transformations — never write "annual Lu Cun".
9. Every star has exactly one palace: check [STAR PLACEMENT TABLE] before writing.
10. Before writing "X Hua Lu/Quan/Ke/Ji", check it against the stem that governs
    that context — Lu, Quan, Ke and Ji mean completely different things.
11. Formation names may ONLY be those listed as present in [FORMATION CHECK],
    and must be argued from their actual criteria.
12. Keep the age given in a year's heading consistent throughout that section.
13. The Life Master and the Body Master are each exactly ONE star. Never describe
    either as a pair, and never merge a malefic that merely happens to be on the
    chart into them.
"""

CHAPTERS_EN = [
    ('A', 'high', 60000, """Write the first three sections.

## Portrait
**Open with one vivid image** that fixes who this person is, the way you would
give someone a nickname ("you are a horse-thief chieftain riding out past the
frontier"). Every stroke of that image must come from the chart — the Life
Palace star's temperament, the auxiliaries and malefics beside it, where the
Body Palace sends them. Then spend about 200 words taking the image apart:
which star gives the edge, which gives the restraint, which decides where they
run afterwards. It should have bite and make the reader smile — never demeaning.
If [FACTS] flags hour sensitivity, say so plainly in one closing line.
**If the birthplace is outside China, show the time conversion in one short
line** (local clock → timezone offset → true solar time for the hour branch,
and Beijing time for the lunar date), so the reader can check it. An overseas
chart that hides this step cannot be verified by anyone.

## The Frame
First line, bolded: tie together the Life Palace, its San Fang Si Zheng
(the opposite palace plus the two trine palaces), and where the Body Palace
falls. Then:
- Explain the Life Palace's main star in plain language; fold in the
  auxiliaries sitting with it, defining each as it appears.
- Contrast the Travel Palace (opposite): how the person reads to outsiders
  versus how they actually are.
- The Body Palace shows where life's weight is carried — cover its stars too.
- If a formation is present, explain the life *rhythm* it implies, not just
  its name.
1200+ words.

## Inner World
The Wellbeing Palace in full: take every star in it one at a time in plain
language (what the transformation does, what the malefics feel like from the
inside, whether anything cushions it). End with a concrete way to discharge the
strain — actions, not comfort. If the Life Master and Body Master pull against
the Life Palace star, land that tension here. 800+ words."""),

    ('B', 'high', 60000, """Write "Career · Money · People".

## Career
The Career Palace in full: how this person works, what the auxiliaries add,
what the malefics do to the competitive climate. If the Body Palace sits here,
say that the centre of gravity is here. Land it: which environments and fields
suit them, which do not. 600+ words.

## Money
**The Wealth Palace and the Property Palace must be read together** — Wealth is
flow (how money comes and goes), Property is stock (what actually stays). Lay
out each, then give one verdict on the *form* their money takes, plus whether
partnership suits them and how they should hold money. 600+ words.

## People and Being Away
Friends Palace + Travel Palace: whether the circle feeds them or drains them,
what kind of allies show up, how they fare away from home. If Hua Lu or Hua Ke
lands in either, make that the centre of the section. 500+ words."""),

    ('C', 'high', 60000, """Write "Love · Family · Body".

## Love and Marriage
The Spouse Palace in full: the partner it describes, how the relationship runs,
what any malefic there does to the friction. Mention where Hong Luan, Tian Xi,
Gu Chen, Gua Su, Tian Yao and Xian Chi fall if they bear on relationships, and
say what each is. **The Spouse Palace faces the Career Palace** — if there are
malefics in Career, spell out the structural pull between work and marriage and
give practical advice. 800+ words.

## Family
One passage each for Parents, Siblings and Children. Empty palaces borrow per
[FACTS]. Work from the stars; no platitudes. 500+ words.

## Body
The Health Palace: lay out the stars, describe tendencies and what to watch
(sleep, how emotion reaches the body). State plainly that this is not a
diagnosis. 300+ words."""),

    ('D', 'high', 60000, """Write "The Ten-Year Map" and "The Next Two Years".

## The Ten-Year Map
One line on how major limits are laid out (start at the Life Palace, first limit
begins at the Bureau number, direction by yin/yang and sex). Then a table
(**only up to the 83–92 limit**): ages / palace / stars and malefics / that
limit's own Hua Lu and Hua Ji from [MAJOR-LIMIT TRANSFORMATIONS] (where the Lu
lands = that decade's dividend, where the Ji lands = that decade's pitfall) /
one line of character. After the table, three passages:
(a) **which limit they are in now** (2026, by East Asian reckoning), its theme,
    and what the limit's Hua Ji specifically makes hard — plus the calendar year
    this limit ends and the next one takes over;
(b) **the next limit**: when it starts, its nature, how it contrasts with now;
(c) **the strongest decade of the life**: take the peak given in [VERDICT],
    unfold its three pieces of evidence, and if a secondary period is given,
    write them as main-peak-then-payoff, never as equals.
1000+ words.

## The Next Two Years
2026 is 丙午, 2027 is 丁未. One passage each: which natal palace the flowing-year
Life Palace lands on and what sits there; where that year's transformations land
(丙: Tian Tong Hua Lu, Tian Ji Hua Quan, Wen Chang Hua Ke, Lian Zhen Hua Ji;
丁: Tai Yin Hua Lu, Tian Tong Hua Quan, Tian Ji Hua Ke, Ju Men Hua Ji); call out
any pile-up with the natal transformations; say what to do and what to avoid.
About 400 words each."""),

    ('E', 'high', 60000, """Write the final two sections.

## The Next Fifteen Years
Turn [FIFTEEN-YEAR SCAN] into a table: year / stem-branch / age / flowing-year
Life Palace / one line of guidance. **Right after the table, add one sentence
stating the rule you used to pick the years unfolded below** (limit changes,
marriage windows, double-Ji years, Lu entering the Life or Body Palace), so the
reader can see why those years and not others. Keep all fifteen rows, then unfold **only
the four to six years worth stopping on**, **strictly in chronological order**,
keeping the ⚡/★/⚠️ marker at the head of each:
- ⚡ limit-change years get the most space: which act ends and which begins,
  **all four of that year's transformations (Lu, Quan, Ke, Ji) and where each
  lands** — a limit-change year written with only the Ji is incomplete —
  where the new limit's Lu and Ji land, what to prepare — **and state that the
  previous limit's Hua Ji stands down**, so any warning given in the Ten-Year
  Map from that old limit expires here. The two sections must agree.
- ★ marriage-window years (Hong Luan / Tian Xi entering the flowing-year Life
  Palace): describe the shape the year takes — **and convert that year's Hua Ji
  into one practical caution** (e.g. Wen Chang/Wen Qu Hua Ji = paperwork and
  contracts go wrong). A year with only good news is not acceptable.
- ⚠️ double-Ji years: what drains most, how to see it coming.
- Years where the flowing Lu enters the Life Palace or the Body Palace: what to
  push on (write it as a leaning, never "you must").
100–150 words each, concrete.

## One Page
Close the report with a page the reader can carry away. Three short lists:
**Three judgements** (the most important conclusions, one line each);
**Three actions** (behaviour, one line each);
**Three years** (the three to remember out of the next fifteen — the turn, the
one to push, the one to sit out — half a line of why each).
Nothing new; only distilled from above. Stop when done."""),
]


# ═══════════════════════════ 服务端入口 ═══════════════════════════
# worker 逐段调用:verdict → A → B → C → D → E。
#
# ⚠️ **不喂前面章节。** 本地 CLI 版也不喂 —— 各章都从同一份【事实】+【全篇统一
#    结论】推导,靠 verdict 保证不打架,而不是靠上下文堆叠。第 E 章说"只提炼前
#    文"指的是同源推导,不是真读前文。改成喂前文会同时改掉 token 预算和已验证
#    的行为,线上和本地版就没法逐段比对了。

ZIWEI_SECTION_TYPES = ('verdict', 'A', 'B', 'C', 'D', 'E')

# 可见正文段(verdict 不是章节,是喂给这五段的前置判断)
ZIWEI_CHAPTER_TAGS = ('A', 'B', 'C', 'D', 'E')


def chart_for(birth, lang='zh'):
    """从出生数据建盘,并挂上三块扩展事实。

    birth: {date:'1990-07-20', time:'04:37', longitude:118.96,
            gender:'male'|'female', place:'赤峰', timezone:'Asia/Shanghai'}

    每次调用重新建盘是**故意的**:确定性、约 50ms,而且保证校对器看到的盘
    和喂给模型的盘是同一张。若改成让 worker 序列化传盘,盘结构一漂移校对就失灵。
    """
    y, mo, d = (int(x) for x in str(birth['date']).split('-'))
    h, mi = (int(x) for x in str(birth['time']).split(':')[:2])
    lng = float(birth['longitude'])
    gender = 'female' if str(birth.get('gender', 'male')).lower().startswith('f') else 'male'
    place = birth.get('place') or ''
    tz = birth.get('timezone') or None

    c = build(y, mo, d, h, mi, lng, gender, place, tz)
    c['_lang'] = lang
    c['_extra'] = '\n\n'.join([
        hour_sens_facts(c, y, mo, d, h, mi, lng, gender, place, tz),
        daxian_hua_facts(c),
        year_scan_facts(c),
    ])
    return c


def chart_payload(c, lang='zh'):
    """给 worker 报告模板画十二宫方盘用的结构化数据(纯 JSON-safe)。

    方盘由模板前端画 —— 和风水报告的罗盘同一个套路,后端不出 HTML。
    """
    P = lambda x: T(lang, 'palace')(x)
    S_ = lambda x: T(lang, 'star_bare')(x)
    HU = lambda x: (T(lang, 'hua')(x).split(' (')[0] if lang == 'en' else x)
    return {
        'lang': lang,
        'ming': c['ming'], 'shen': c['shen'],
        'ming_gz': c['ming_gz'], 'ju_name': T(lang, 'ju')(c['ju_name']),
        'ming_zhu': S_(c['ming_zhu']), 'shen_zhu': S_(c['shen_zhu']),
        'forward': c['forward'], 'gender': c['gender'],
        'y_gan': c['y_gan'], 'y_zhi': c['y_zhi'],
        'lunar': c['lunar'], 'bazi': c['bazi'],
        'place': c['place'], 'tz': c['tz'],
        # 索引键转成字符串 —— JSON 对象的键本来就是字符串,显式转避免两边理解不一致
        'palace':     {str(k): P(v) for k, v in c['palace'].items()},
        'stars':      {str(k): [S_(s) for s in v] for k, v in c['stars'].items()},
        'gong_gan':   {str(k): v for k, v in c['gong_gan'].items()},
        'changsheng': {str(k): v for k, v in c['changsheng'].items()},
        'daxian':     {str(k): list(v) for k, v in c['daxian'].items()},
        'hua':        {S_(n): [HU(m), p] for n, (m, p) in c['hua'].items()},
        'clock':      c['clock'].strftime('%Y-%m-%d %H:%M'),
        'solar':      c['solar'].strftime('%Y-%m-%d %H:%M'),
        'corr_min':   round(c['corr'], 1),
    }


def verifiable(lang):
    """校对器只有中英两套正则(见 _PAT)。其它语言生成得了,校对不了。

    不静默降级 —— 端点把这个值原样返回,worker 记进审计表。
    """
    return lang in ('zh', 'en')


def build_verdict(c, lang='zh', lang_instruction=''):
    """定调预判 —— 峰值十年只能有一个答案,先定下来再写正文。

    五段独立生成,不做这步就会出现"事业章说 43-52、地图章说 63-72"的自打架。
    失败不抛:各段自行判断,有打架风险但不该整单挂掉。

    lang_instruction:客户选了西/德/法等语言时的"用 X 语写"指令。
    定调是内部判断不直接交付,但它会被原样拼进正文 prompt,
    所以必须和正文同语种 —— 否则中文定调块喂给西语正文会引发语种串台。
    """
    F = facts(c, lang)
    VZH = ('你是资深紫微命理师。根据下面的盘面事实,做四个全局判断,输出 JSON:\n'
           '{"dingdiao": "一句话总定调(外X内Y式)",\n'
           ' "peak": "一生力量最集中的大限(须在13-82岁的现实区间选,格式:XX-XX岁 某某限)",\n'
           ' "peak_evidence": ["证据1","证据2","证据3"](每条一句,引用具体盘面),\n'
           ' "secondary": "从属的兑现期及其与主峰的关系,没有就留空",\n'
           ' "turning": "未来15年里最大的一个拐点年(优先选换大限之年)及一句话原因"}\n'
           '只输出 JSON。\n\n')
    VEN = ('You are an expert Zi Wei Dou Shu reader. From the chart facts below, '
           'make four global calls and return JSON. **Write all values in English.**\n'
           '{"dingdiao": "one-line overall read (outer X, inner Y)",\n'
           ' "peak": "the strongest major limit of the life '
           '(must fall in the realistic 13-82 range; format: XX-XX, <Palace> limit)",\n'
           ' "peak_evidence": ["ev1","ev2","ev3"] (one line each, citing the chart),\n'
           ' "secondary": "a subordinate payoff period and how it relates '
           'to the peak; empty string if none",\n'
           ' "turning": "the single biggest turning-point year in the next 15 '
           '(prefer a limit-change year) and one line of why"}\n'
           'Return JSON only.\n\n')
    li = (f'\n{lang_instruction}\n' if lang_instruction else '')
    try:
        v = json.loads(ds((VEN if lang == 'en' else VZH) + li + F,
                          effort='high', max_tokens=32000, json_mode=True))
    except Exception as e:
        print(f'    定调失败,各段自行判断(有打架风险): {e!r:.90}')
        return ''
    en = lang == 'en'
    out = ['[VERDICT — every section must follow this; no competing claims]' if en
           else '【全篇统一结论 —— 所有章节必须遵循,不得另立论点】']
    out.append((f'  Overall: {v.get("dingdiao","")}' if en
                else f'  总定调:{v.get("dingdiao","")}'))
    out.append((f'  Peak decade (the only one): {v.get("peak","")}' if en
                else f'  峰值十年(唯一):{v.get("peak","")}'))
    out += [f'    - {e}' for e in v.get('peak_evidence', [])]
    if v.get('secondary'):
        out.append((f'  Secondary payoff: {v["secondary"]}' if en
                    else f'  从属兑现期:{v["secondary"]}'))
    out.append((f'  Biggest turning point: {v.get("turning","")}' if en
                else f'  最大拐点:{v.get("turning","")}'))
    print(f'    ✓ 定调: {v.get("peak", "?")}')
    return '\n'.join(out) + '\n'


def _spec_for(tag, lang):
    for t, effort, mt, spec in (CHAPTERS_EN if lang == 'en' else CHAPTERS):
        if t == tag:
            return effort, mt, spec
    raise KeyError(f'未知章节 {tag}')


def generate_section(tag, c, lang='zh', verdict='', lang_instruction=''):
    """出一段正文 + 机器校对 + 最多两轮打回重写。

    返回 (text, residual)。硬错误(确定性的星曜落宫/四化归属错误)修不掉就抛 ——
    紫微客户手里就有免费排盘,能自己对出来,错的不如不交。
    软错误(启发式)留稿,随返回值报出来供人工扫。

    lang 只取 'zh'/'en',决定事实块与章节规格用哪套。客户选了西/德/法等语言时,
    用英文脚手架 + lang_instruction 让模型改用目标语言写 —— 和八字/风水/2027
    三条线同一个做法。这时校对器无正则可用(见 verifiable),整段跳过校对,
    由调用方把这个事实记进审计表,不假装校过。
    """
    effort, mt, spec = _spec_for(tag, lang)
    ST = STYLE_EN if lang == 'en' else STYLE
    head = ('你是一位资深紫微斗数命理师,正在为客户写一份付费详批。\n\n'
            f'【事实 —— 由排盘引擎算出,不可更改】\n{facts(c, lang)}\n\n{verdict}\n{ST}\n')
    if lang_instruction:
        head += f'\n{lang_instruction}\n'
    base = head + '\n' + spec + ('\n\n直接输出 Markdown 正文,不要前言,'
                                 '不要代码块包裹,不要重复标题层级以外的编号。')

    txt = ds(base, effort=effort, max_tokens=mt)
    if lang_instruction:
        return txt, []                        # 非中英:生成得了,校对不了,如实返回
    hard, soft = verify_text(txt, c, lang)
    h2, s2 = verify_claims(txt, c, lang)
    hard += h2; soft += s2
    for _ in range(2):                        # 重写一轮 → 点修一轮
        if not hard and not soft:
            break
        allerr = hard + soft
        print(f'    ✗ 段 {tag} 校对 {len(hard)}硬/{len(soft)}软,修: ' + ' | '.join(allerr[:3]))
        txt = ds('下面是一段紫微斗数报告草稿,其中几处星曜落宫可能写错。'
                 '只修正清单里的问题(及被牵连的语句),其余一字不改,'
                 '输出修正后的全文,不要前言。\n\n【问题清单】\n'
                 + '\n'.join('- ' + e for e in allerr)
                 + '\n\n【草稿】\n' + txt, effort='low', max_tokens=mt)
        hard, soft = verify_text(txt, c, lang)
        h2, s2 = verify_claims(txt, c, lang)
        hard += h2; soft += s2
    if hard:
        raise RuntimeError(f'段 {tag} 修完仍有确定性错误: {hard[:5]}')
    if soft:
        print(f'    ⚠ 段 {tag} 启发式残留 {len(soft)} 处(不拦): {soft[:3]}')
    return txt, soft
