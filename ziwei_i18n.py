# -*- coding: utf-8 -*-
"""紫微报告的双语名表 —— **事实层与校对闸共用同一张表**。

为什么单独抽一个模块:如果渲染用一套名字、校对正则里再手抄一套,两边一定会飘,
而且飘了不报错(校对静默扫出 0 错,看着像全过)。所以只此一份,两边都从这里取。

术语风格对齐气流八字产品(paid-bazi-backend):**English Term (中文)**,
如 "Rob Wealth (劫財)"。紫微星名是专名,用拼音而非意译("Po Jun"不是"Army Breaker"),
拼音在英文紫微文献里才是通行写法,意译各家不一。

⚠️ 干支与四化在英文稿里**也保留中文字**(如「Gui (癸) stem」「Tai Yin Hua Ke (化科)」)。
   两个原因:① 拼音有致命歧义 —— 戊=Wu 与 午=Wu 同形,己=Ji 与 忌=Ji 同形;
   ② 中文字成了语言无关的机器锚点,四化核对的正则一套通吃中英,不必维护两份。
"""

PALACE_EN = {
    '命宫': 'Life', '兄弟': 'Siblings', '夫妻': 'Spouse', '子女': 'Children',
    '财帛': 'Wealth', '疾厄': 'Health', '迁移': 'Travel', '交友': 'Friends',
    '官禄': 'Career', '田宅': 'Property', '福德': 'Wellbeing', '父母': 'Parents',
}

# 十四主星:拼音 + 繁体。首次出现时正文再补一句白话释义,由写作层负责。
STAR_EN = {
    '紫微': 'Zi Wei (紫微)', '天机': 'Tian Ji (天機)', '太阳': 'Tai Yang (太陽)',
    '武曲': 'Wu Qu (武曲)', '天同': 'Tian Tong (天同)', '廉贞': 'Lian Zhen (廉貞)',
    '天府': 'Tian Fu (天府)', '太阴': 'Tai Yin (太陰)', '贪狼': 'Tan Lang (貪狼)',
    '巨门': 'Ju Men (巨門)', '天相': 'Tian Xiang (天相)', '天梁': 'Tian Liang (天梁)',
    '七杀': 'Qi Sha (七殺)', '破军': 'Po Jun (破軍)',
    # 辅星与煞星
    '文昌': 'Wen Chang (文昌)', '文曲': 'Wen Qu (文曲)',
    '左辅': 'Zuo Fu (左輔)', '右弼': 'You Bi (右弼)',
    '天魁': 'Tian Kui (天魁)', '天钺': 'Tian Yue (天鉞)',
    '禄存': 'Lu Cun (祿存)', '擎羊': 'Qing Yang (擎羊)', '陀罗': 'Tuo Luo (陀羅)',
    '地空': 'Di Kong (地空)', '地劫': 'Di Jie (地劫)',
    '火星': 'Huo Xing (火星)', '铃星': 'Ling Xing (鈴星)', '天马': 'Tian Ma (天馬)',
    '红鸾': 'Hong Luan (紅鸞)', '天喜': 'Tian Xi (天喜)',
    '天刑': 'Tian Xing (天刑)', '天姚': 'Tian Yao (天姚)',
    '华盖': 'Hua Gai (華蓋)', '咸池': 'Xian Chi (咸池)',
    '孤辰': 'Gu Chen (孤辰)', '寡宿': 'Gua Su (寡宿)',
}
# 校对用的裸拼音(去掉括号里的中文),正文里重复提及时用的就是这个
STAR_EN_BARE = {k: v.split(' (')[0] for k, v in STAR_EN.items()}

HUA_EN = {'禄': 'Hua Lu (化祿)', '权': 'Hua Quan (化權)',
          '科': 'Hua Ke (化科)', '忌': 'Hua Ji (化忌)'}
HUA_EN_BARE = {'禄': 'Hua Lu', '权': 'Hua Quan', '科': 'Hua Ke', '忌': 'Hua Ji'}

JU_EN = {'水二局': 'Water 2 Bureau', '木三局': 'Wood 3 Bureau',
         '金四局': 'Metal 4 Bureau', '土五局': 'Earth 5 Bureau',
         '火六局': 'Fire 6 Bureau'}

CS_EN = {'长生': 'Growth', '沐浴': 'Bathing', '冠带': 'Capping', '临官': 'Office',
         '帝旺': 'Peak', '衰': 'Decline', '病': 'Illness', '死': 'Death',
         '墓': 'Tomb', '绝': 'Severance', '胎': 'Conception', '养': 'Nurture'}

GEJU_EN = {
    '杀破狼': 'Sha Po Lang (殺破狼)', '府相朝垣': 'Fu Xiang Chao Yuan (府相朝垣)',
    '机月同梁': 'Ji Yue Tong Liang (機月同梁)', '禄马交驰': 'Lu Ma Jiao Chi (祿馬交馳)',
    '双禄交流': 'Double Lu (雙祿交流)', '火贪': 'Huo Tan (火貪)',
    '铃贪': 'Ling Tan (鈴貪)', '马头带箭': 'Ma Tou Dai Jian (馬頭帶箭)',
    '魁钺夹命': 'Kui Yue Jia Ming (魁鉞夾命)', '羊陀夹命': 'Yang Tuo Jia Ming (羊陀夾命)',
    '财荫夹印': 'Cai Yin Jia Yin (財蔭夾印)',
}

LABELS = {
    'zh': {
        'palace': lambda p: p if p == '命宫' else p + '宫',
        'star': lambda s: s,
        'star_bare': lambda s: s,
        'hua': lambda h: '化' + h,
        'ju': lambda j: j,
        'cs': lambda x: x,
        'geju': lambda g: g,
        'no_main': '无主星(借对宫{p}:{s})',
        'twelve': '【十二宫】', 'sanfang': '【命宫三方四正】',
        'natal_hua': '【生年四化 · {g}干】', 'star_table': '【星曜落宫总表】',
        'male': '男', 'female': '女', 'age': '岁',
    },
    'en': {
        'palace': lambda p: PALACE_EN[p] + ' Palace',
        'star': lambda s: STAR_EN.get(s, s),
        'star_bare': lambda s: STAR_EN_BARE.get(s, s),
        'hua': lambda h: HUA_EN[h],
        'ju': lambda j: JU_EN.get(j.replace('(纳音定局)', ''), j),
        'cs': lambda x: CS_EN.get(x, x),
        'geju': lambda g: GEJU_EN.get(g, g),
        'no_main': 'empty (borrows from opposite {p}: {s})',
        'twelve': '[TWELVE PALACES]', 'sanfang': '[LIFE PALACE — SAN FANG SI ZHENG]',
        'natal_hua': '[NATAL FOUR TRANSFORMATIONS · {g} stem]',
        'star_table': '[STAR PLACEMENT TABLE]',
        'male': 'male', 'female': 'female', 'age': '',
    },
}


def L(lang, key):
    return LABELS[lang][key]
