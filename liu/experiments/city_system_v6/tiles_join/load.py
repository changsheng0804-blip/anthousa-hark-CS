"""CS 矢量瓦片与账本的读取工具。——Hark（刘线）"""
import glob, json, os, re, subprocess
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
BASE = "https://changsheng0804-blip.github.io/anthousa-hark-CS/living/tiles/"
VEC = "/tmp/vec"

def fetch_meta():
    p = "/tmp/cs_meta.json"
    if not os.path.exists(p):
        subprocess.run(["curl", "-sf", "-o", p, BASE + "meta.json"], check=True)
    return json.load(open(p))

def fetch_vec(meta):
    os.makedirs(VEC, exist_ok=True)
    gx, gy = meta["grid"]
    for tx in range(gx):
        for ty in range(gy):
            f = f"{VEC}/{tx}_{ty}.json"
            if not os.path.exists(f):
                subprocess.run(["curl", "-sf", "-o", f, f"{BASE}vec/{tx}_{ty}.json"])
                if os.path.exists(f) and os.path.getsize(f) == 0:
                    os.remove(f)

def tiles():
    out = {}
    for f in glob.glob(f"{VEC}/*.json"):
        m = re.match(r"(\d+)_(\d+)\.json", os.path.basename(f))
        if m:
            out[(int(m[1]), int(m[2]))] = json.load(open(f))
    return out

def area(xy):
    x, y = xy[:, 0], xy[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))
