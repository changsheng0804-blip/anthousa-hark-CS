"""刘线 · 街坊的压力（liu3）：从 voices.json 的街坊闲话 + 页面自己的家谱推演，数出干山上居民的真实处境。
Count the pressures the Xerolophos residents actually live under, with evidence that can be counted:
  - story evidence: which voiced households (voices.json) talk about water queues, bread, the fire, crowding, faith, trade...;
    each pressure lists the house ids, the years and one or two quoted lines;
  - genealogy evidence: the page's own household() derivation (tools/export_households.js), projected year by year
    (people per house, sons grown up under the parents' roof, widows with small children, infant deaths, Arian households,
    water-carrier households, families burned out in the AF 48 fire);
  - ledger evidence (world.json, if built): population, food and water capacity, how many houses the districts still have room for.
Output: one JSON (default docs/living/xerolophos/talk.json) used by the 「街坊在说什么」 panel and by drafts/proposals_af61_70/.
usage:
  python3 tools/petitions.py                       # writes docs/living/xerolophos/talk.json, prints a summary
  python3 tools/petitions.py --out stats.json --from 61 --to 70
"""
import json, os, re, subprocess, sys, argparse, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XD = os.path.join(ROOT, 'docs', 'living', 'xerolophos')

# ---------- topics: what the street talks about. strong = a line that names the pressure itself ----------
TOPICS = [
    ('water', '缺水：排队挑水、水比粮贵', 'Water: queues at the cistern, water dearer than bread',
     r'排队|排到|占了个位置|占位|水比.{0,3}贵|水.{0,2}金贵|池子浅|一罐水|打听.{0,6}(挑水|水)|问蓄水池|蓄水池|池子|渴|等水|挑水.{0,3}上坡|上坡|运水|井'),
    ('bread', '粮与面包：配给、粮船、不够吃', 'Bread: the dole, the grain ships, not enough to eat',
     r'领面包|配给|不够吃|饿|粮价|涨价|(面|饼|粮)(价|贵了|涨)|粮船|运粮船|粮仓|面粉|兑了水|几张嘴|张嘴'),
    ('fire', '大火以后：烧掉的家、搬上山、重建', 'After the fire: burned homes, moving uphill, rebuilding',
     r'大火|南港.{0,8}(烧|火)|港边.{0,4}(火|家)|原来的家|烧(了|掉|没)了?.{0,4}家|废墟|满身是灰|抢出|漂了|挪了好几回窝|赁屋'),
    ('crowd', '屋里挤：添丁、几代同屋、住不下', 'Crowding: births, three generations under one roof',
     r'挤|睡不下|住不下|一间|加盖|地方不够|打地铺|人多|十几口|[七八九十]口|一窝|一大家子|添了|又添|又生'),
    ('faith', '信仰：城外礼拜、阿里乌派与尼西亚派、旧神', 'Faith: worship outside the wall, Arians and Nicenes, the old gods',
     r'阿里乌|尼西亚|旧神|礼拜|出城|城门外|城外的院子|聚会|神父|主教|祈祷|画个十字|为信什么|修行'),
    ('trade', '抢生意：同行、学徒、去码头找活', 'Trade: rivals, apprentices, looking for work at the quay',
     r'抢客人|抢生意|对手|同行|压价|讲价|生意|去码头.{0,4}找活|学徒|不够吃'),
    ('widow', '没了当家的：寡妇、孤儿撑门户', 'Losing the breadwinner: widows and orphans keeping the house',
     r'(死了|没了|走了).{0,16}(守着|接过|撑|带着|一个人)|寡妇|孤儿|独自|没再娶|没再嫁'),
    ('infant', '孩子没留住', 'Children who did not live',
     r'夭折|没留住|没满一年|生下来就没了|[一两三四五六七八九]岁上没了|才[一两三四五六]岁'),
]
SHARP = {  # the lines that say the pressure most plainly are quoted first
    'water': r'排队|排到|水比.{0,3}贵|金贵|池子浅|一罐水|占了个位置|打听.{0,6}水|问蓄水池|渴',
    'bread': r'领面包|不够吃|饿|张嘴|兑了水|(面|饼|粮)(价|贵了|涨)',
    'fire': r'赁屋|漂了|原来的家|港边.{0,6}火|烧在|那场火',
    'crowd': r'挤不下|睡不下|住不下|人多|十几口|一大家子|[七八九十]口',
    'faith': r'城外.{0,4}(祈祷|礼拜|院子)|阿里乌|旧神|神父|城门外|为信什么',
    'trade': r'抢客人|抢生意|码头.{0,4}找活|不够吃|对手',
    'widow': r'死了.{0,12}(守着|接过)|没再娶|没再嫁',
    'infant': r'没留住|夭折|岁上没了',
}
PERSONAL = {'widow', 'infant'}
NOISE = {  # words that look like a topic but are not (炉火 is a baker's oven, not a fire)
    'fire': r'窑火|炉火|火盆|火候|生火|添火|火塘',
    'faith': r'嫁到了?城外',
    'water': r'井井',
}


def load_households():
    out = subprocess.run(['node', os.path.join(ROOT, 'tools', 'export_households.js'), XD],
                         capture_output=True, text=True, check=True).stdout
    return {h['id']: h for h in json.loads(out)}


def fam_at(h, Y):
    f = None
    for x in h['fams']:
        if x['B'] <= Y: f = x
    return f


def alive_at(h, Y):
    """Same rule as the page's aliveAt(), plus: the house is standing and the family has not moved out."""
    if not (h['built'] <= Y < h['destroyed']): return None, []
    f = fam_at(h, Y)
    if not f or f['out'] <= Y: return f, []
    return f, [p for p in f['people'] if p['b'] <= Y < p['d'] and (not p['married'] or p['married'] <= Y)
               and not (p['left'] and p['left'] <= Y)]


def story_hits(V):
    hits = collections.defaultdict(list)  # topic -> [(house, year, text)]
    for hid, e in V.items():
        lines = [(y, t) for y, t in e['life']] + [(-(e['life'][-1][0] if e['life'] else 60), ' '.join(e.get('obj', [])))]
        for key, zh, en, pat in TOPICS:
            for y, t in lines:
                t2 = re.sub(NOISE.get(key, r'(?!x)x'), '', t)
                if re.search(pat, t2):
                    hits[key].append((int(hid), int(y), t))  # negative year = the household's object, undated
    return hits


def genealogy(HH, voiced, y0, y1):
    """Per year: what the family trees say about the corner of the city the page shows, and about the voiced houses."""
    out = {}
    for Y in range(y0, y1 + 1):
        r = collections.Counter()
        crowded, multi, widows, arian, carriers, newc, infant, grown = [], [], [], [], [], [], [], []
        for hid, h in HH.items():
            f, al = alive_at(h, Y)
            if not al: continue
            r['houses'] += 1; r['people'] += len(al)
            v = hid in voiced
            if v: r['v_houses'] += 1; r['v_people'] += len(al)
            if len(al) >= 10:
                r['crowded'] += 1
                if v: crowded.append(hid)
            brides = [p for p in al if p['bride'] and Y - p['b'] >= 15]
            gens = {p['g'] for p in brides}
            if len(brides) >= 2 and len(gens) >= 2:
                r['two_couples'] += 1
                if v: multi.append(hid)
            men = [p for p in al if p['s'] == 'm' and Y - p['b'] >= 16]
            kids = [p for p in al if Y - p['b'] < 14]
            if not men and kids:
                r['no_man_with_kids'] += 1
                if v: widows.append(hid)
            if f['faith'] == '阿里乌派':
                r['arian_houses'] += 1; r['arian_people'] += len(al)
                if v: arian.append(hid)
            if f['trade'] == '运水人':
                r['carrier_houses'] += 1
                if v: carriers.append(hid)
            r['trade:' + f['trade']] += 1
            if f['B'] == Y:
                r['moved_in'] += 1
                if v: newc.append(hid)
            for p in al:
                if p['s'] == 'm' and not p['bride'] and p['g'] > min(q['g'] for q in al) and Y - p['b'] == 18:
                    r['sons_of_age'] += 1
                    if v: grown.append(hid)
            for p in f['people']:
                if p['d'] == Y and p['d'] - p['b'] <= 1:
                    r['infant_deaths'] += 1
                    if v: infant.append(hid)
        r = dict(r)
        r['per_house'] = round(r['people'] / max(1, r['houses']), 2)
        r['voiced'] = {'crowded': crowded, 'two_couples': multi, 'no_man_with_kids': widows, 'arian': arian,
                       'carriers': carriers, 'moved_in': newc, 'infant_deaths': infant, 'sons_of_age': grown}
        out[Y] = r
    return out


def fire_families(HH, voiced):
    """Families who came up the hill because their old home burned (the page's own words), and those who watched it."""
    burned, sheltered = [], []
    for hid, h in HH.items():
        ev = ' '.join(t for y, t in h['ev'])
        if '原来的家烧在了' in ev or '原来的家烧' in ev: burned.append(hid)
        if '收留过一个远亲' in ev: sheltered.append(hid)
    return {'burned_out': len(burned), 'burned_out_voiced': [i for i in burned if i in voiced],
            'took_in_kin': len(sheltered), 'took_in_kin_voiced': [i for i in sheltered if i in voiced]}


def ledger():
    p = os.path.join(ROOT, 'world.json')
    if not os.path.exists(p): return None
    w = json.load(open(p, encoding='utf-8'))
    e = w['eras'][-1]
    return {'year': e['to'], **e['stats']}


def by_year(V, hits, ylo=30, yhi=60, k=3):
    """For each year: the three things most households talked about (by number of households), with who and one quote."""
    idx = collections.defaultdict(lambda: collections.defaultdict(list))
    for key, rows in hits.items():
        for hid, y, t in rows:
            if y > 0: idx[y][key].append((hid, t))
    zh = {k_: z for k_, z, _, _ in TOPICS}
    out = {}
    for Y in range(ylo, yhi + 1):
        # what was said in the last three years still goes round the street; this year counts double
        score = collections.Counter(); who = collections.defaultdict(dict)
        for yy in (Y, Y - 1, Y - 2):
            for key, rows in idx.get(yy, {}).items():
                for hid, t in rows:
                    if hid in who[key]: continue
                    if not (V[str(hid)]['fam'] <= Y): continue
                    who[key][hid] = (yy, t); score[key] += 2 if yy == Y else 1
        top = []
        personal = 0  # deaths are talked about every year; let at most one family sorrow into the three
        for key, s in score.most_common():
            if len(top) >= k: break
            if key in PERSONAL:
                if personal: continue
                personal += 1
            hs = sorted(who[key].items(), key=lambda kv: (not re.search(SHARP[key], kv[1][1]), -kv[1][0], kv[0]))
            top.append({'topic': key, 'zh': zh[key].split('：')[0], 'n': len(hs),
                        'houses': [h for h, _ in hs[:8]], 'quote': hs[0][1][1], 'quote_house': hs[0][0], 'quote_year': hs[0][1][0],
                        'alt': [[h, t] for h, (_, t) in hs[1:3]]})
        if top: out[Y] = top
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(XD, 'talk.json'))
    ap.add_argument('--stats', default=None, help='also write the full pressure statistics here')
    ap.add_argument('--from', dest='y0', type=int, default=61)
    ap.add_argument('--to', dest='y1', type=int, default=70)
    a = ap.parse_args()
    V = json.load(open(os.path.join(XD, 'voices.json'), encoding='utf-8'))
    HH = load_households()
    voiced = {int(k) for k in V}
    hits = story_hits(V)
    gen = genealogy(HH, voiced, 50, a.y1)
    pressures = []
    for key, zh, en, _ in TOPICS:
        rows = hits.get(key, [])
        hs = sorted({h for h, _, _ in rows})
        q = sorted([r for r in rows if r[1] > 0], key=lambda r: (not re.search(SHARP[key], r[2]), -r[1], r[0]))
        sharp = sorted({h for h, y, t in rows if re.search(SHARP[key], t)})
        pressures.append({'id': key, 'zh': zh, 'en': en, 'households': len(hs), 'house_ids': hs,
                          'sharp_households': len(sharp), 'sharp_house_ids': sharp,
                          'lines': len(rows), 'quotes': [{'house': h, 'year': y, 'text': t} for h, y, t in q[:3]]})
    pressures.sort(key=lambda p: -p['households'])
    stats = {'source': {'voices': len(V), 'page_houses': len(HH)}, 'ledger': ledger(),
             'pressures': pressures, 'fire': fire_families(HH, voiced),
             'genealogy': {str(k): v for k, v in gen.items()}}
    g0 = gen[a.y0 - 1]
    stats['projection_note'] = (f'家谱推演只生到建城 60 年：61 年以后没有新出生、没有新搬来的人家。{a.y0}–{a.y1} 年的数字是'
                                '「60 年时已经在世的人」长大、成家、老去的结果，是下限。')
    stats['coming_of_age'] = {'sons_turning_18': sum(gen[y].get('sons_of_age', 0) for y in range(a.y0, a.y1 + 1)),
                              'voiced': sorted({h for y in range(a.y0, a.y1 + 1) for h in gen[y]['voiced']['sons_of_age']})}
    stats['water_load'] = {'year': a.y0 - 1, 'people': g0['people'], 'carrier_houses': g0.get('carrier_houses', 0),
                           'people_per_carrier_house': round(g0['people'] / max(1, g0.get('carrier_houses', 1)), 1)}
    talk = {'_doc': '刘线 liu3 · tools/petitions.py 生成。每年街坊议论最多的三件事（按议论的户数，前两年的话也还在传）。',
            'years': {str(k): v for k, v in by_year(V, hits).items()}}
    json.dump(talk, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    if a.stats:
        json.dump(stats, open(a.stats, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'写入 {a.out}（{len(talk["years"])} 年）' + (f'，统计 {a.stats}' if a.stats else ''))
    for p in pressures:
        print(f"  {p['zh']}: {p['households']} 户 / {p['lines']} 句")
    for Y in (60, a.y0, a.y1):
        g = gen[Y]
        print(f"  AF {Y}: {g['houses']} 户 {g['people']} 人（每户 {g['per_house']}），≥10 人 {g.get('crowded', 0)} 户，"
              f"两代媳妇同屋 {g.get('two_couples', 0)}，无成年男人带小孩 {g.get('no_man_with_kids', 0)}，阿里乌派 {g.get('arian_houses', 0)} 户，"
              f"运水人 {g.get('carrier_houses', 0)} 户，婴儿夭折 {g.get('infant_deaths', 0)}")


if __name__ == '__main__':
    main()
