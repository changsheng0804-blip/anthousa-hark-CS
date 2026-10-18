#!/usr/bin/env python3
"""检查 docs/flags.json：字段齐全、没过期、同时登记不超过 5 个。失败返回 1。——Hark（CS线）"""
import json, sys, datetime, pathlib
p = pathlib.Path(__file__).resolve().parent.parent / 'docs' / 'flags.json'
flags = json.loads(p.read_text(encoding='utf-8'))['flags']
today = datetime.date.today().isoformat()
bad = []
if len(flags) > 5: bad.append(f'登记了 {len(flags)} 个开关，上限 5 个')
seen = set()
for f in flags:
    n = f.get('name', '?')
    for k in ('name', 'owner', 'note', 'expires'):
        if not f.get(k): bad.append(f'{n}: 缺 {k}')
    if n in seen: bad.append(f'{n}: 重名')
    seen.add(n)
    if f.get('expires', '9999') < today: bad.append(f'{n}: {f["expires"]} 已过期，转正删开关或删代码')
for b in bad: print('✗', b)
print('✓ 开关检查通过' if not bad else f'✗ {len(bad)} 处问题')
sys.exit(1 if bad else 0)
