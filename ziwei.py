#!/usr/bin/env python
"""
紫微斗数排盘引擎。

    python tools/ziwei.py --date 1996-05-12 --time 04:36 --lng 118.96 --gender male --place 赤峰

为什么单独写而不是套现成库:这套东西**全是确定性规则**,没有八字里"身强身弱""取用神"
那种需要判断的环节 —— 起盘不该有任何模糊地带,自己实现才能逐条对着口诀验。

⚠️ 与八字的三个根本差异,决定了不能复用八字那套输入处理:
  1. 紫微走**农历**(朔望月),八字走**节气**。所以要先把真太阳时换算成农历年月日。
  2. 紫微的命宫由**农历月 + 时辰**共同决定 —— 时辰错一格,命宫整体移位,
     十二宫全部跟着转,**全盘作废**。八字错时辰只错 2/8 个字。所以真太阳时校正
     对紫微比对八字更要命。
  3. **闰月**在紫微里是真问题(各派处理不一),八字里根本不存在这个概念。
     本引擎的处理见 lunar_month() 注释。

⚠️ 本引擎**不含庙旺利陷表**。那张表(14主星 × 12宫)各家版本有出入,
   凭记忆重建等于埋雷 —— 位置算错看得出来,庙旺标错看不出来。要用请单独提供底本。
"""
import argparse, math, sys, datetime, json

for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass

ZHI = ['子','丑','寅','卯','辰','巳','午','未','申','酉','戌','亥']
GAN = ['甲','乙','丙','丁','戊','己','庚','辛','壬','癸']
Z = {z: i for i, z in enumerate(ZHI)}

# 十二宫名。命宫定下后**逆行**安其余十一宫(地支索引递减)。
# 自检:迁移宫永远是命宫的对宫,命/财帛/官禄永远三合 —— 见 _selftest()。
PALACES = ['命宫','兄弟','夫妻','子女','财帛','疾厄',
           '迁移','交友','官禄','田宅','福德','父母']

# 五虎遁:由生年天干定寅宫天干,其余顺排。命宫天干靠它,而命宫干支决定五行局。
WU_HU = {'甲':'丙','己':'丙','乙':'戊','庚':'戊','丙':'庚','辛':'庚',
         '丁':'壬','壬':'壬','戊':'甲','癸':'甲'}

# 六十甲子纳音 → 五行局。index = 甲子起的序号 // 2(每两位共一个纳音)。
# 纳音五行以 **15 对为周期**重复,所以只写一轮再乘 2。
# 逐条对照:海中金 炉中火 大林木 路旁土 剑锋金 / 山头火 涧下水 城头土 白蜡金 杨柳木 /
#           泉中水 屋上土 霹雳火 松柏木 长流水
_NAYIN_CYCLE = ['金','火','木','土','金',
                '火','水','土','金','木',
                '水','土','火','木','水']
NAYIN_PAIRS = _NAYIN_CYCLE * 2
JU = {'水': (2, '水二局'), '木': (3, '木三局'), '金': (4, '金四局'),
      '土': (5, '土五局'), '火': (6, '火六局')}

# 四化。⚠️ 庚干的化科各派不一(太阴/天同/天府/太阳都有人用),
# 这里取中州派的「太阳禄 武曲权 太阴科 天同忌」,输出里会标出该干有分歧。
SI_HUA = {
    '甲': ('廉贞','破军','武曲','太阳'), '乙': ('天机','天梁','紫微','太阴'),
    '丙': ('天同','天机','文昌','廉贞'), '丁': ('太阴','天同','天机','巨门'),
    '戊': ('贪狼','太阴','右弼','天机'), '己': ('武曲','贪狼','天梁','文曲'),
    '庚': ('太阳','武曲','太阴','天同'), '辛': ('巨门','太阳','文曲','文昌'),
    '壬': ('天梁','紫微','左辅','武曲'), '癸': ('破军','巨门','太阴','贪狼'),
}
HUA_DISPUTED = {'庚'}

LU_CUN = {'甲':'寅','乙':'卯','丙':'巳','丁':'午','戊':'巳',
          '己':'午','庚':'申','辛':'酉','壬':'亥','癸':'子'}
# 「甲戊庚牛羊,乙己鼠猴乡,丙丁猪鸡位,壬癸兔蛇藏,六辛逢马虎」
KUI_YUE = {'甲':('丑','未'),'戊':('丑','未'),'庚':('丑','未'),
           '乙':('子','申'),'己':('子','申'),
           '丙':('亥','酉'),'丁':('亥','酉'),
           '壬':('卯','巳'),'癸':('卯','巳'),
           '辛':('午','寅')}
# 火铃起宫,按年支三合局:「寅午戌丑卯,申子辰寅戌,巳酉丑卯戌,亥卯未酉戌」
HUO_LING = {('寅','午','戌'): ('丑','卯'), ('申','子','辰'): ('寅','戌'),
            ('巳','酉','丑'): ('卯','戌'), ('亥','卯','未'): ('酉','戌')}
MA = {('寅','午','戌'): '申', ('申','子','辰'): '寅',
      ('巳','酉','丑'): '亥', ('亥','卯','未'): '巳'}

MING_ZHU = {'子':'贪狼','丑':'巨门','亥':'巨门','寅':'禄存','戌':'禄存',
            '卯':'文曲','酉':'文曲','辰':'廉贞','申':'廉贞',
            '巳':'武曲','未':'武曲','午':'破军'}
# 身主按年支,六对循环:子午火星 丑未天相 寅申天梁 卯酉天同 辰戌文昌 巳亥天机
SHEN_ZHU = {'子':'火星','午':'火星','丑':'天相','未':'天相',
            '寅':'天梁','申':'天梁','卯':'天同','酉':'天同',
            '辰':'文昌','戌':'文昌','巳':'天机','亥':'天机'}
assert len(SHEN_ZHU) == 12 and len(MING_ZHU) == 12, '命主/身主表必须覆盖十二支'


def equation_of_time(d: datetime.datetime) -> float:
    n = d.timetuple().tm_yday
    b = 2 * math.pi * (n - 81) / 364
    return 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)


# 中国大陆经度范围。没给时区时只能假定东八区,超出这个范围一定是海外盘 —— 必须报错。
CN_LNG = (72.0, 136.0)


def zone_meridian(dt: datetime.datetime, tz: str | None, lng: float) -> float:
    """出生**当时**该地的时区中央经线(度)。

    ⚠️ 这里曾把 120 写死。对国内盘无碍,对海外盘是灾难:芝加哥 (-87.63°) 会算出
       (-87.63-120)*4 = -830 分,加均时差正好 -14 小时 —— 等于把当地钟当北京时间用,
       时辰、命宫、全盘一起错,而且**不报错、结果看着还很合理**。
       2026-08-12 用户从一份英文 sample 里反推出 "-840.2 分" 才发现。
       气流整个市场都是海外盘,这是必须在入口拦住的一类错。

    用 IANA 历史偏移还白拿一个好处:**中国 1986–1991 的夏令时自动被算进去**
    (那六年 Asia/Shanghai 的偏移是 +9,中央经线 135°),不必再单独维护 DST 表。
    偏移只用来定中央经线,**不移动钟面时间本身**。
    """
    if tz:
        from zoneinfo import ZoneInfo
        off = dt.replace(tzinfo=ZoneInfo(tz)).utcoffset()
        return off.total_seconds() / 3600.0 * 15.0
    if not (CN_LNG[0] <= lng <= CN_LNG[1]):
        raise ValueError(
            f'经度 {lng} 不在中国境内({CN_LNG[0]}–{CN_LNG[1]}°E),必须显式给出时区 '
            f'(如 tz="America/Chicago")。不给就只能假定东八区,会算出十几小时的偏差。')
    return 120.0


def true_solar(dt: datetime.datetime, lng: float, tz: str | None = None):
    """真太阳时 = 钟面时间 + 经度差 + 均时差。经度差以**当地时区中央经线**为基准。"""
    corr = (lng - zone_meridian(dt, tz, lng)) * 4 + equation_of_time(dt)
    return dt + datetime.timedelta(minutes=corr), corr


def nayin_element(gan: str, zhi: str) -> str:
    """六十甲子序号 → 纳音五行。甲子=0,每两位共一个纳音。"""
    g, z = GAN.index(gan), Z[zhi]
    for i in range(60):
        if i % 10 == g and i % 12 == z:
            return NAYIN_PAIRS[i // 2]
    raise ValueError(f'{gan}{zhi} 不是有效干支')


def ziwei_position(ju: int, day: int) -> int:
    """安紫微星。口诀:日数除局数取商,寅宫顺数商位;借数为偶则顺进,为奇则逆退。
    整除时无借数,直接落在商位上。已用木三局/水二局全月表逐日对过。"""
    r = day % ju
    if r == 0:
        return (2 + day // ju - 1) % 12
    n = ju - r                       # 借数
    shang = (day + n) // ju
    base = (2 + shang - 1) % 12      # 寅宫起顺数 shang 位
    return (base + n) % 12 if n % 2 == 0 else (base - n) % 12


def chart_from_lunar(y_gan, y_zhi, lmonth, lday, ti, gender):
    """纯规则层:只吃农历年干支/月/日/时辰索引,不碰日期换算。
    单独抽出来是为了能**穷举整个参数空间**算基准率 —— 判断一句断语到底是在说
    这个人,还是在说四分之一的人。见 tools/ziwei_baserate.py。"""
    # 命宫:寅起正月顺数到生月,再从该宫起子时逆数到生时。身宫同起点但顺数。
    ming = (2 + (lmonth - 1) - ti) % 12
    shen = (2 + (lmonth - 1) + ti) % 12

    # 宫干:五虎遁定寅宫天干,**从寅顺排十二宫**(10 干轮 12 支,子丑两宫是
    # 干序的第 11、12 位,会拿到与卯辰同字的干)。
    # ⚠️ 曾写成 (zi-2) 不取模 —— 丑宫算出 -1,变成"从寅倒退一位",干支错两位。
    #    命宫落子/丑的盘(1/6)因此五行局全错、紫微错位、全盘报废;
    #    2026-08-11 用户拿庚辰年丑命宫的盘(应为己丑火六局)当场戳穿。
    yin_gan = GAN.index(WU_HU[y_gan])
    gong_gan = {zi: GAN[(yin_gan + (zi - 2) % 12) % 10] for zi in range(12)}

    elem = nayin_element(gong_gan[ming], ZHI[ming])
    ju, ju_name = JU[elem]

    zw = ziwei_position(ju, lday)
    tf = (4 - zw) % 12

    stars = {i: [] for i in range(12)}
    def put(pos, name): stars[pos].append(name)

    # 紫微星系逆行:天机-1 太阳-3 武曲-4 天同-5 廉贞-8
    for off, nm in ((0,'紫微'), (-1,'天机'), (-3,'太阳'),
                    (-4,'武曲'), (-5,'天同'), (-8,'廉贞')):
        put((zw + off) % 12, nm)
    # 天府星系顺行:太阴+1 贪狼+2 巨门+3 天相+4 天梁+5 七杀+6 破军+10
    for off, nm in ((0,'天府'), (1,'太阴'), (2,'贪狼'), (3,'巨门'),
                    (4,'天相'), (5,'天梁'), (6,'七杀'), (10,'破军')):
        put((tf + off) % 12, nm)

    aux = {}                              # 名 → 宫位,便于四化定位
    def putx(pos, name):
        put(pos, name); aux[name] = pos

    putx((10 - ti) % 12, '文昌')          # 戌起子时逆数
    putx((4 + ti) % 12, '文曲')           # 辰起子时顺数
    putx((4 + lmonth - 1) % 12, '左辅')   # 辰起正月顺数
    putx((10 - (lmonth - 1)) % 12, '右弼')# 戌起正月逆数
    k, y = KUI_YUE[y_gan]
    putx(Z[k], '天魁'); putx(Z[y], '天钺')

    lu = Z[LU_CUN[y_gan]]
    putx(lu, '禄存'); putx((lu + 1) % 12, '擎羊'); putx((lu - 1) % 12, '陀罗')
    putx((11 + ti) % 12, '地劫'); putx((11 - ti) % 12, '地空')

    for grp, (h, l) in HUO_LING.items():
        if y_zhi in grp:
            putx((Z[h] + ti) % 12, '火星'); putx((Z[l] + ti) % 12, '铃星')
    for grp, m in MA.items():
        if y_zhi in grp: putx(Z[m], '天马')

    hong = (3 - Z[y_zhi]) % 12
    putx(hong, '红鸾'); putx((hong + 6) % 12, '天喜')

    # ── 杂曜(全部查表,无流派分歧的那几颗)──
    putx((9 + lmonth - 1) % 12, '天刑')      # 酉起正月顺行
    putx((1 + lmonth - 1) % 12, '天姚')      # 丑起正月顺行
    # 华盖=年支三合的库地;咸池(桃花)=三合的沐浴地
    MISC_SANHE = {('寅','午','戌'): ('戌','卯'), ('申','子','辰'): ('辰','酉'),
                  ('巳','酉','丑'): ('丑','午'), ('亥','卯','未'): ('未','子')}
    for grp, (hg, xc) in MISC_SANHE.items():
        if y_zhi in grp:
            putx(Z[hg], '华盖'); putx(Z[xc], '咸池')
    # 孤辰寡宿按年支三会方
    GU_GUA = {('亥','子','丑'): ('寅','戌'), ('寅','卯','辰'): ('巳','丑'),
              ('巳','午','未'): ('申','辰'), ('申','酉','戌'): ('亥','未')}
    for grp, (gu, gua) in GU_GUA.items():
        if y_zhi in grp:
            putx(Z[gu], '孤辰'); putx(Z[gua], '寡宿')

    # 四化:找到该星在哪一宫,给它挂标记
    hua = {}
    for nm, mark in zip(SI_HUA[y_gan], ('禄','权','科','忌')):
        for i in range(12):
            if nm in stars[i]:
                hua[nm] = (mark, i); break

    # 十二宫逆行安放
    palace = {}
    for k2, nm in enumerate(PALACES):
        palace[(ming - k2) % 12] = nm

    # 大限:阳男阴女顺行,阴男阳女逆行;起运岁=局数,每宫十年
    yang_year = GAN.index(y_gan) % 2 == 0
    forward = (yang_year and gender == 'male') or (not yang_year and gender == 'female')
    daxian = {}
    for k2 in range(12):
        pos = (ming + k2) % 12 if forward else (ming - k2) % 12
        daxian[pos] = (ju + k2 * 10, ju + k2 * 10 + 9)

    # 长生十二神:起点由五行局定(水土申/木亥/金巳/火寅),顺逆与大限同
    CS_START = {'水': '申', '土': '申', '木': '亥', '金': '巳', '火': '寅'}
    CS12 = ['长生','沐浴','冠带','临官','帝旺','衰','病','死','墓','绝','胎','养']
    cs0 = Z[CS_START[elem]]
    changsheng = {}
    for k2 in range(12):
        pos = (cs0 + k2) % 12 if forward else (cs0 - k2) % 12
        changsheng[pos] = CS12[k2]

    return dict(
        changsheng=changsheng,
        gender=gender, y_gan=y_gan, y_zhi=y_zhi,
        lmonth=lmonth, lday=lday, t_zhi=ZHI[ti],
        ming=ming, shen=shen, ju=ju, ju_name=ju_name,
        ming_gz=gong_gan[ming] + ZHI[ming],
        gong_gan=gong_gan, stars=stars, hua=hua, palace=palace, daxian=daxian,
        forward=forward,
        ming_zhu=MING_ZHU[ZHI[ming]], shen_zhu=SHEN_ZHU[y_zhi],
    )


def build(year, month, day, hour, minute, lng, gender, place='', tz=None):
    """日期层:真太阳时 → 农历 → 交给纯规则层。海外盘必须给 tz。"""
    clock = datetime.datetime(year, month, day, hour, minute)
    solar, corr = true_solar(clock, lng, tz)

    # ⚠️ 两个基准,别混用(照搬气流八字计算器踩出来的做法):
    #   · **时辰** 用真太阳时 —— 时辰问的是「太阳在出生地的什么位置」,是地方天象。
    #   · **农历年/月/日** 用出生那一刻的**北京时间** —— 农历与节气是中国历法,
    #     节气表按北京时间发布,是全球同一瞬间的天文事件。
    # 国内盘两者几乎重合,所以在国内怎么测都测不出差别;海外盘会差一整天:
    #   芝加哥 1990-03-15 20:00 → 真太阳时仍是 3/15(农历二月十九),
    #   北京时间已是 3/16 10:00(农历二月二十) → 命宫、五行局、紫微星位全变。
    from lunar_python import Solar
    off_h = zone_meridian(clock, tz, lng) / 15.0
    beijing = clock - datetime.timedelta(hours=off_h) + datetime.timedelta(hours=8)
    lun = Solar.fromYmdHms(beijing.year, beijing.month, beijing.day,
                           beijing.hour, beijing.minute, 0).getLunar()
    lun_hour = Solar.fromYmdHms(solar.year, solar.month, solar.day,
                                solar.hour, solar.minute, 0).getLunar()
    y_gz = lun.getYearInGanZhi()
    # ⚠️ lunar_python 用负数表示闰月。紫微各派对闰月处理不一,这里取最通行的
    #    「闰月归本月」(闰三月按三月论)。若改口径,只需动这一行。
    c = chart_from_lunar(y_gz[0], y_gz[1], abs(lun.getMonth()),
                         lun.getDay(), Z[lun_hour.getTimeZhi()], gender)
    c.update(clock=clock, solar=solar, corr=corr, place=place, tz=tz,
             beijing=beijing, utc_offset=off_h,
             lunar=f'{y_gz}年 {lun.getMonthInChinese()}月 '
                   f'{lun.getDayInChinese()} {lun_hour.getTimeZhi()}时',
             bazi=lun.getEightChar().toString())
    return c


MAIN14 = {'紫微','天机','太阳','武曲','天同','廉贞','天府','太阴',
          '贪狼','巨门','天相','天梁','七杀','破军'}
SHA6 = ('擎羊', '陀罗', '火星', '铃星', '地空', '地劫')
SPW = {'七杀', '破军', '贪狼'}          # 骨架层:三者永远互成三合
FUXIANG = {'天府', '天相'}              # 府相朝垣
JIYUE = {'天机', '太阴', '天同', '天梁'} # 机月同梁


def san_fang(c, pos):
    """三方四正:本宫 + 对宫(+6) + 三合两宫(±4)。看一个宫从来不能只看一格。"""
    return [pos, (pos + 6) % 12, (pos + 4) % 12, (pos - 4) % 12]


def features(c):
    """任意盘都能算的结构特征 → 布尔。键名就是报告里会出现的说法。

    这一层的意义:让"这句话说的是多少人"变成可计算的量。
    穷举全参数空间跑一遍就得到每条的基准率(见 ziwei_baserate.py),
    生成报告时把百分比挂在断语上 —— 常见的照讲,只是标明它常见。"""
    f = {}
    inv = {v: k for k, v in c['palace'].items()}          # 宫名 → 地支索引
    S = c['stars']
    ming, shen = c['ming'], c['shen']
    hua = {m: p for _, (m, p) in c['hua'].items()}        # 禄/权/科/忌 → 宫位
    sf = san_fang(c, ming)
    sf_stars = set().union(*(set(S[i]) for i in sf))
    ming_stars = set(S[ming])

    # ── 骨架层:命宫坐谁、三方是什么班子 ──
    for st in sorted(MAIN14):
        f[f'命宫主星:{st}'] = st in ming_stars
    f['命宫:无主星'] = not (ming_stars & MAIN14)
    # ⚠️ 杀破狼必须分"坐命"和"在对宫",不能笼统说"三方见"。
    #    七杀破军贪狼两两相隔 4 位,天然同属一个三合组;命宫坐其一,另两颗必在三合位
    #    —— 这才是正统的杀破狼格(25%)。而对宫比命宫多隔 6 位,属另一个三合组,
    #    所以"三方四正里出现杀破狼之一"会连对宫那种也算进来,变成 50%。
    #    早先用宽口径,结果 AI 对着一张命宫只借到贪狼的盘写"你属于杀破狼",
    #    下一段又说"你三方里没有七杀和破军",自相矛盾。定义含糊,输出就打架。
    f['杀破狼:坐命'] = bool(SPW & ming_stars)
    f['杀破狼:在对宫'] = bool(SPW & set(S[(ming + 6) % 12])) and not (SPW & ming_stars)
    f['府相朝垣'] = FUXIANG <= sf_stars
    f['机月同梁'] = len(JIYUE & sf_stars) >= 3

    # ── 装饰层:各听各的年干/年支/月/时,不在主星轮盘上 ──
    for nm in PALACES:
        f[f'身宫落:{nm}'] = shen == inv[nm]
        f[f'化忌落:{nm}'] = hua.get('忌') == inv[nm]
        f[f'化禄落:{nm}'] = hua.get('禄') == inv[nm]
        f[f'禄存落:{nm}'] = '禄存' in S[inv[nm]]
        f[f'擎羊落:{nm}'] = '擎羊' in S[inv[nm]]
    f['身命同宫'] = shen == ming

    # 化忌是全盘最要紧的记号:落哪宫是个人信息,同宫见煞才真难受
    if hua.get('忌') is not None:
        f['化忌同宫见煞'] = bool(set(SHA6) & set(S[hua['忌']]))
        f['化忌坐命宫'] = hua['忌'] == ming
    else:
        f['化忌同宫见煞'] = f['化忌坐命宫'] = False

    # ── 会合类格局:凑到才算,凑不到就没有(与骨架类的"人人有份"相反)──
    lu = next(i for i, v in S.items() if '禄存' in v)
    ma = next((i for i, v in S.items() if '天马' in v), None)
    f['禄马交驰'] = ma is not None and (lu == ma or (lu - ma) % 12 == 6)
    f['双禄交流'] = (hua.get('禄') is not None and
                    (hua['禄'] == lu or (hua['禄'] - lu) % 12 == 6))
    tan = next(i for i, v in S.items() if '贪狼' in v)
    f['火贪同宫'] = '火星' in S[tan]
    f['铃贪同宫'] = '铃星' in S[tan]
    f['命宫:见天马'] = '天马' in ming_stars
    f['命宫:见禄存'] = '禄存' in ming_stars
    f['命宫:见四煞'] = bool({'擎羊','陀罗','火星','铃星'} & ming_stars)
    f['命宫:见空劫'] = bool({'地空','地劫'} & ming_stars)
    f['命宫:昌曲同宫'] = {'文昌','文曲'} <= ming_stars
    f['命宫:辅弼同宫'] = {'左辅','右弼'} <= ming_stars
    # 夹:前后两宫各有一颗。夹的力量比同宫弱,但古法很看重
    nb = set(S[(ming + 1) % 12]) | set(S[(ming - 1) % 12])
    # 财荫夹印:天相被 荫(天梁)与 财(禄存或生年化禄星)左右邻宫相夹。
    # ⚠️ 判据是**邻宫夹**,不是"武曲天相同宫"。"财"包括邻宫里带生年化禄的那颗星
    #    (2026-08-11:赤峰盘天相在申,酉天梁为荫、未天同化禄为财 —— 成立;
    #     审稿双方各错一半:报告推理错,人工核对漏了化禄。所以交给引擎判。)
    xiang = next(i for i, v in S.items() if '天相' in v)
    lu_star = next(n for n, (m, _) in c['hua'].items() if m == '禄')
    def _cai(p):
        return '禄存' in S[p] or lu_star in S[p]
    xa, xb = (xiang + 1) % 12, (xiang - 1) % 12
    f['财荫夹印'] = ('天梁' in S[xa] and _cai(xb)) or ('天梁' in S[xb] and _cai(xa))
    f['魁钺夹命'] =('天魁' in S[(ming+1)%12] and '天钺' in S[(ming-1)%12]) or \
                    ('天钺' in S[(ming+1)%12] and '天魁' in S[(ming-1)%12])
    f['羊陀夹命'] = ('擎羊' in S[(ming+1)%12] and '陀罗' in S[(ming-1)%12]) or \
                    ('陀罗' in S[(ming+1)%12] and '擎羊' in S[(ming-1)%12])
    f['马头带箭'] = '擎羊' in S[Z['午']] and Z['午'] in (ming, shen)
    return f


def render(c):
    """按传统方盘布局打印:寅在左下,顺时针 寅卯辰巳/午未/申酉戌亥/子丑。"""
    def cell(i):
        head = f'{c["gong_gan"][i]}{ZHI[i]} {c["palace"][i]}'
        if i == c['ming']: head += '☜命'
        if i == c['shen']: head += '·身'
        a, b = c['daxian'][i]
        lines = [head, f'  大限 {a}-{b}']
        main = [s for s in c['stars'][i] if s in MAIN14]
        oth  = [s for s in c['stars'][i] if s not in MAIN14]
        def mark(s):
            h = c['hua'].get(s)
            return s + f'({h[0]})' if h and h[1] == i else s
        lines.append('  ' + ('　'.join(mark(s) for s in main) if main else '—'))
        if oth:
            for k in range(0, len(oth), 3):
                lines.append('  ' + ' '.join(mark(s) for s in oth[k:k+3]))
        return lines

    # 传统方盘:寅在左下,顺时针走一圈,中宫留空。中文字宽按 2 计。
    W = 28
    def pad(s):
        wide = sum(1 for ch in s if ord(ch) > 0x2E80)
        return s + ' ' * max(0, W - len(s) - wide)

    GRID = [[Z['巳'], Z['午'], Z['未'], Z['申']],
            [Z['辰'], None,    None,    Z['酉']],
            [Z['卯'], None,    None,    Z['戌']],
            [Z['寅'], Z['丑'], Z['子'], Z['亥']]]

    sep = lambda l, m, r: l + m.join('─' * W for _ in range(4)) + r
    out = [sep('┌', '┬', '┐')]
    for r_i, gr in enumerate(GRID):
        cols = [cell(i) if i is not None else [] for i in gr]
        h = max(len(x) for x in cols)
        for k in range(h):
            out.append('│' + '│'.join(
                pad(col[k] if k < len(col) else '') for col in cols) + '│')
        out.append(sep('├', '┼', '┤') if r_i < 3 else sep('└', '┴', '┘'))
    return '\n'.join(out)


def summary(c):
    L = []
    L.append(f'钟表 {c["clock"]:%Y-%m-%d %H:%M}　{c["place"]}　'
             f'真太阳时校正 {c["corr"]:+.2f} 分 → {c["solar"]:%H:%M}')
    L.append(f'农历 {c["lunar"]}　|　八字 {c["bazi"]}')
    L.append(f'命宫 {c["ming_gz"]}　身宫 {ZHI[c["shen"]]}　'
             f'{c["ju_name"]}(纳音定局)　大限{"顺" if c["forward"] else "逆"}行')
    L.append(f'命主 {c["ming_zhu"]}　身主 {c["shen_zhu"]}')
    hh = '　'.join(f'{n}化{m}' for n, (m, _) in c['hua'].items())
    tail = '　⚠️该年干化科各派有分歧' if c['y_gan'] in HUA_DISPUTED else ''
    L.append(f'生年四化({c["y_gan"]}干) {hh}{tail}')
    return '\n'.join(L)


def _selftest(c):
    """结果不变量。位置算错时这几条会先炸,比肉眼查表可靠。"""
    errs = []
    inv = {v: k for k, v in c['palace'].items()}
    if (inv['命宫'] - inv['迁移']) % 12 != 6:
        errs.append('迁移宫不在命宫对面')
    if sorted(((inv['命宫'] - inv['财帛']) % 12, (inv['命宫'] - inv['官禄']) % 12)) != [4, 8]:
        errs.append('命/财/官不成三合')
    got = sorted(s for v in c['stars'].values() for s in v if s in MAIN14)
    if len(got) != 14 or set(got) != MAIN14:
        errs.append(f'十四主星不全:{got}')
    # ⚠️ 宫干必须沿地支一圈连续递增(五虎遁从寅宫起顺排)。
    #    2026-08-11 事故:`(zi-2)` 漏了 `% 12`,子丑两宫算成负数偏移,
    #    Python 负数取模不报错 → 宫干错 → 纳音错 → 五行局错 → 紫微错 → **整盘作废**。
    #    命宫落子或丑的人(约 1/6)全中招,其余无感,所以肉眼极难发现。
    #    这条不变量在当时会直接炸在 亥→子 的接缝上。
    #    ⚠️ 递增是沿 **寅→卯→…→子→丑** 走的(月序),不是沿 子→亥(地支序)。
    #       丑→寅 那个接缝本来就该断(12 宫配 10 干,绕一圈进 2 位),不能检查它。
    #       我第一版不变量就是从子起走整圈,反而把正确的盘判成错的。
    for k in range(11):
        cur, nxt_zi = (2 + k) % 12, (2 + k + 1) % 12
        want = GAN[(GAN.index(c['gong_gan'][cur]) + 1) % 10]
        if c['gong_gan'][nxt_zi] != want:
            errs.append(f'宫干不连续:{ZHI[cur]}={c["gong_gan"][cur]} 之后应是{want},'
                        f'实为{c["gong_gan"][nxt_zi]}')
            break
    for a, b in (('破军','天相'), ('天府','七杀'), ('紫微','贪狼')):
        pa = next(i for i, v in c['stars'].items() if a in v)
        pb = next(i for i, v in c['stars'].items() if b in v)
        if a == '紫微' and (pa - pb) % 12 not in (0, 6, 2, 10):
            continue
        if a != '紫微' and (pa - pb) % 12 != 6:
            errs.append(f'{a}{b}不成对宫')
    return errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', required=True)
    ap.add_argument('--time', required=True)
    ap.add_argument('--lng', type=float, required=True)
    ap.add_argument('--gender', default='male', choices=['male', 'female'])
    ap.add_argument('--place', default='')
    ap.add_argument('--tz', default=None,
                    help='IANA 时区名,海外盘必填(如 America/Chicago)')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    y, mo, d = map(int, a.date.split('-'))
    h, mi = map(int, a.time.split(':'))
    c = build(y, mo, d, h, mi, a.lng, a.gender, a.place, a.tz)
    if a.json:
        print(json.dumps({k: v for k, v in c.items()
                          if k not in ('clock', 'solar')}, ensure_ascii=False, default=str))
        return
    print(summary(c)); print()
    print(render(c))
    errs = _selftest(c)
    print('\n自检:' + ('✓ 全部通过' if not errs else ' / '.join(errs)))


if __name__ == '__main__':
    main()
