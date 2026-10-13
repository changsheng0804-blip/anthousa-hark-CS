"""CS 线 · 工厂总装：一条命令，一块地 → 一个能验收的街区
用法: python make_quarter.py <q> [--from 段名]
  配方在 quarters/<q>.json（名字、框、关键年、地标中文名和一句话、街头气氛）。其余全部从底账推。
段（按顺序；--from 从某段接着跑）：
  grow    底账 → houses.json / frame.json / 每个关键年的草图 base_Y.png、蒙版 mask_Y.png
  scene   配方 → scene.json / city.json；拷公用页面和素材（所有街区共用一份 index.html）；和链接的街区互相指
  paint   （cs35 起新街区）AI 只画地标：缺的列进 raw/landmarks/PROMPTS.txt、退出码 3；齐了 landmarks.py 用草图 + 地标图合成每个关键年的画。
          （老街区）每个关键年要一张 AI 画：tools/cs/factory/raw/<q>/<pre>Y_ai_*.png。缺的话写出草图和提示词、退出码 3，
          由 Hark 调 generate_image（只给草图 + east_af30.jpg 风格，不给旧画）存进去再接着跑。
          有了就按「底账陆地画成水最少」挑一张，记进 scene.paint，repaint.py 一栋一栋重铺屋顶、蒙版合成补岸。
  land    land.py：走得上的网（底账 ∧ 每张画都是陆地）、城里的街
  heart   框里有已建的港、scene 里有 fleet 才跑 heart.py（心跳要配方，新港不自动造）
  streets streets_ng.py：长街、横街、地块，房子按街重排（底账 houses.json 不动）
  ground  ground_ng.py：抹掉画上的旧房子，留水、地标、绿地、焦土
  render  render_ng.py：三个关键年的预览图
  accept  accept.py --fix：定律、比对、画面、页面冒烟，全过才算长成"""
import json, os, subprocess, sys
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
LIV = os.path.join(ROOT, 'docs', 'living')
sys.path.insert(0, HERE)
import critic
STAGES = ['grow', 'scene', 'paint', 'land', 'heart', 'streets', 'ground', 'render', 'accept']
PROMPT = ("Top-down orthographic painted map of a late-Roman city quarter, in exactly the painterly style of the second reference image "
          "(warm sandy ground, small terracotta-roofed houses seen from directly above, soft shadows, muted blue-green water). "
          "The FIRST image is the engine draft and is the absolute layout: every small red-brown block is one house and must be painted as one small roof "
          "at exactly that position and size; tan background = open sandy ground with paths; the dark blue area is water and is the ONLY place to paint water "
          "(with a few small boats); keep the shoreline pixel-exact, never paint water on tan, never paint land on blue. Thin brown lines are dirt roads, "
          "light grey shapes are public buildings painted as stone buildings with tiled roofs at the same spot. Same framing and aspect as the draft. "
          "No text, no labels, no grid, no border, no compass.")


def run(*a, check=True):
    print('  $', ' '.join(os.path.basename(x) if i < 2 else x for i, x in enumerate(a)), flush=True)
    r = subprocess.run([sys.executable, *a], cwd=ROOT, capture_output=True, text=True)
    tail = (r.stdout + r.stderr).strip().splitlines()[-4:]
    for ln in tail: print('    ' + ln[:200])
    if check and r.returncode: sys.exit(f'段失败：{os.path.basename(a[0])}（退出码 {r.returncode}）')
    return r


def land_as_water(q, img):   # 底账陆地画成水的格数（定律四同一种量法）
    M = np.load(os.path.join(HERE, 'out', f'{q}_masks.npz')); lm = M['landm']
    a = np.asarray(Image.open(img).convert('RGB').resize((lm.shape[1], lm.shape[0]), Image.BOX)).astype(int)
    wk = (a[..., 2] > a[..., 0] + 15) & (a[..., 2] > a[..., 1] - 10)
    return int((lm & wk).sum())


def main():
    q = sys.argv[1]; R = json.load(open(os.path.join(HERE, 'quarters', q + '.json')))
    start = STAGES.index(sys.argv[sys.argv.index('--from') + 1]) if '--from' in sys.argv else 0
    py = lambda n: os.path.join(HERE, n)
    pre = {'nangang': 'ng'}.get(q, q[:2]); Q = os.path.join(LIV, q); raw = os.path.join(HERE, 'raw', q)
    for st in STAGES[start:]:
        print(f'== {st}', flush=True)
        if st == 'grow':
            run(py('grow.py'), q, *map(str, R['box']), *map(str, R['keys']))
        elif st == 'scene':
            run(py('scene_auto.py'), q)
        elif st == 'paint':
            run(py('land.py'), q, '--masks-only')
            os.makedirs(raw, exist_ok=True); need = []
            sc = json.load(open(os.path.join(Q, 'scene.json'))); P = sc.setdefault('paint', {})
            # cs35：新街区不再要 AI 整张画。只要地标图（raw/landmarks/<id>.webp，全城共用）；缺的先列出来让 Hark 画，齐了就由 landmarks.py 合成每个关键年的「画」
            if not any(f.endswith('.png') and '_ai_' in f for f in os.listdir(raw)) or any('_ai_c' in f for f in os.listdir(raw)):
                r = run(py('landmarks.py'), q, 'drafts'); 
                if '缺 0' not in r.stdout: print('缺地标图：照 raw/landmarks/PROMPTS.txt 调 generate_image（只给 style_crop.jpg 做风格参考），存成 <id>.webp 后 --from paint'); sys.exit(3)
                run(py('landmarks.py'), q, 'compose')
            for Y in R['keys']:
                cands = sorted(f for f in os.listdir(raw) if f.startswith(f'{pre}{Y}_ai_') and f.endswith('.png'))
                if not cands:
                    d = os.path.join(raw, f'draft_{Y}.png')
                    Image.open(os.path.join(Q, f'base_{Y}.png')).convert('RGB').resize((976, 1088)).save(d); need.append((Y, d)); continue
                sc_ = {}
                for f in cands:   # 每张候选都真铺一遍屋顶、交给 critic 打分：先看房子对位过不过（≥0.8），再看底账陆地画成水少不少
                    t = os.path.join('/tmp', f'mq_{q}_{f}.jpg')
                    if len(cands) > 1:
                        subprocess.run([sys.executable, py('reroof.py'), q, str(Y), os.path.join(raw, f), t], cwd=ROOT, capture_output=True)
                        hs_ = critic.score(q, Y, t)['houses'] if os.path.exists(t) else 0
                    else: hs_ = 1
                    sc_[f] = (hs_ >= 0.8, hs_, -land_as_water(q, os.path.join(raw, f)))
                best = max(sc_, key=sc_.get)
                print(f'    {Y} 年候选 ' + '，'.join(f'{f}: 对位 {v[1]:.2f} 画成水 {-v[2]}' for f, v in sc_.items()) + f' → {best}')
                if P.get(str(Y), {}).get('src') != best: P[str(Y)] = {'src': best, 'why': f'工厂挑的：对位 {sc_[best][1]:.2f}，底账陆地画成水 {-sc_[best][2]} 格'}
            json.dump(sc, open(os.path.join(Q, 'scene.json'), 'w'), ensure_ascii=False)
            if need:
                open(os.path.join(raw, 'PROMPT.txt'), 'w').write(PROMPT + '\n')
                for Y, d in need: print(f'PAINT {Y} draft={d} style={os.path.join(LIV, "east_af30.jpg")} save_as={os.path.join(raw, f"{pre}{Y}_ai_m1.png")}')
                print('缺画：调 generate_image（提示词在 PROMPT.txt），存好后 --from paint 接着跑'); sys.exit(3)
            run(py('repaint.py'), q)
        elif st == 'land':
            run(py('land.py'), q)
        elif st == 'heart':
            sc = json.load(open(os.path.join(Q, 'scene.json')))
            if sc.get('fleet'): run(py('heart.py'), q); run(py('land.py'), q)
            else:
                fr = json.load(open(os.path.join(Q, 'frame.json')))
                hb = [s['id'] for s in fr['structures'] if s['type'] == 'harbor' and s['built'] <= max(R['keys'])]
                print('    没有心跳配方，跳过' + (f'（框里有港 {hb}，要心跳得先写 fleet 配方）' if hb else ''))
        elif st == 'streets':
            run(py('streets_ng.py'), q)   # check_streets 要地面图，挪到 ground 段后面跑（cs36）
        elif st == 'ground':
            run(py('ground_ng.py'), q); run(os.path.join(ROOT, 'tools', 'cs', 'check_streets.py'), q)
        elif st == 'render':
            for Y in R['keys']: run(py('render_ng.py'), q, str(Y))
        elif st == 'accept':
            r = run(py('accept.py'), q, '--fix', check=False)
            sys.exit(r.returncode)


if __name__ == '__main__':
    main()
