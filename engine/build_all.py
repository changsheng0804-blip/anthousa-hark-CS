"""Rebuild the whole city from source: genesis -> every era proposal in order -> check -> render.
The repo holds only proposals, rules and chronicles; world.json and docs/years are derived.
Run on any machine (e.g. the server's pull task): python engine/build_all.py"""
import glob, json, os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
def run(*a):
    r = subprocess.run([sys.executable, *a], capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-2000:], r.stderr[-2000:]); sys.exit(r.returncode)
    return r.stdout
props = sorted(glob.glob("proposals/era_*.json"), key=lambda p: json.load(open(p, encoding="utf-8"))["era"]["from"])
run("engine/genesis.py")
for p in props:
    run("engine/step.py", p)
print(run("engine/check.py").strip())
print(run("engine/render.py").strip())
d = json.load(open("docs/data.json", encoding="utf-8"))
print(json.dumps(d["eras"][-1]["stats"]))
