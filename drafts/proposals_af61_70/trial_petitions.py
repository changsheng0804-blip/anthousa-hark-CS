"""Trial-run each petition draft through the engine in throwaway copies under /tmp. Never touches the repo.
usage (from the repo root):  rm -rf /tmp/anth && cp -r . /tmp/anth && (cd /tmp/anth && python3 engine/build_all.py)
                             python3 drafts/proposals_af61_70/trial_petitions.py drafts/proposals_af61_70 [baseline petition_1_water ...]
Each run copies /tmp/anth, puts the draft in as proposals/era_0061.json, adds tmp-only i18n names and a placeholder chronicle
(the check needs them), runs build_all + check, and records accepted/rejected, stats and houses pulled down in trial_results.json."""
import json, os, shutil, subprocess, sys, glob, re
SRC = '/tmp/anth'   # clean copy of the repo, already built to AF 60
DR = sys.argv[1]
def run(cwd, *a):
    r = subprocess.run([sys.executable, *a], cwd=cwd, capture_output=True, text=True); return r.returncode, r.stdout + r.stderr
def xero_houses(w, Y):
    return sum(1 for h in w['houses'] if h['d'] == 'd_xerolophos' and h['built'] <= Y and (h.get('destroyed') is None or h['destroyed'] > Y))
res = {}
files = sorted(glob.glob(os.path.join(DR, 'petition_*.json'))) + [os.path.join(DR, 'petitions_all.json'), 'BASE']
only = sys.argv[2:]
if os.path.exists(os.path.join(DR, 'trial_results.json')): res = json.load(open(os.path.join(DR, 'trial_results.json')))
for f in files:
    name = 'baseline' if f == 'BASE' else os.path.basename(f)[:-5]
    if only and name not in only: continue
    T = f'/tmp/trial_{name}'
    shutil.rmtree(T, ignore_errors=True); shutil.copytree(SRC, T, ignore=shutil.ignore_patterns('.git'))
    prop = {"era": {"from": 61, "to": 70, "title": "baseline"}, "actions": [], "review": []} if f == 'BASE' else json.load(open(f))
    json.dump(prop, open(f'{T}/proposals/era_0061.json', 'w'), ensure_ascii=False, indent=1)
    rc, out = run(T, 'engine/step.py', 'proposals/era_0061.json', '--dry-run')
    dry = json.loads(out[out.index('{'):])
    # tmp-only scaffolding the check needs: i18n names and a placeholder chronicle quoting the population
    i = json.load(open(f'{T}/i18n/i18n.json')); add = json.load(open(os.path.join(DR, 'i18n_additions.json')))
    for k in ('names_zh', 'labels_zh'): i[k].update(add[k])
    i['titles_en']['61'] = 'Petitions (trial)'
    json.dump(i, open(f'{T}/i18n/i18n.json', 'w'), ensure_ascii=False, indent=1)
    pop = dry['stats']['population']; ids = ' '.join('{{%s}}' % a['id'] for a in dry.get('accepted_list', []))
    acc_ids = [a['structure']['id'] for a in prop['actions'] if a['structure']['id'] not in {r['id'] for r in dry['rejected']}]
    refs = ' '.join('{{%s}}' % x for x in acc_ids if not x.startswith('d_'))
    open(f'{T}/chronicle/61_70.md', 'w').write(f'试跑占位编年史。全城 {pop:,} 人。{refs}\n')
    open(f'{T}/chronicle/en/61_70.md', 'w').write(f'Trial placeholder chronicle. The city holds {pop:,} people. {refs}\n')
    rc, out = run(T, 'engine/build_all.py')
    w = json.load(open(f'{T}/world.json'))
    e = w['eras'][-1]
    pulled = {}
    for s in w['structures']:
        if s['built'] >= 61:
            for h in s['history']:
                m = re.match(r'(\d+) houses were pulled down', h['text'])
                if m: pulled[s['id']] = int(m.group(1))
    res[name] = {'build_all_rc': rc, 'check': [l for l in out.splitlines() if 'checks passed' in l or ':' in l][:6],
                 'accepted': [a['id'] for a in e['accepted']], 'rejected': e['rejected'], 'stats': e['stats'],
                 'events': e['events'], 'houses_pulled_down': pulled,
                 'xero_houses_60': xero_houses(w, 60), 'xero_houses_70': xero_houses(w, 70),
                 'new_district_houses': sum(1 for h in w['houses'] if h['d'] == 'd_exokionion')}
    json.dump(res, open(os.path.join(DR, 'trial_results.json'), 'w'), ensure_ascii=False, indent=1)
    print(name, json.dumps(res[name], ensure_ascii=False)[:900], flush=True)
json.dump(res, open(os.path.join(DR, 'trial_results.json'), 'w'), ensure_ascii=False, indent=1)
