"""CS 线 house_types 薄壳：房子的几何、一生阶段（立架/换瓦/长苔/塌顶）、柱廊菜园全部用上游 tools/house_types.py（唯一来源）。
这里只补南港的两种街区 dock（码头货栈）、horrea（仓场）：配色加一行，类型挑选包一层。——Hark（CS线）"""
import importlib.util, os, sys
_T = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _T not in sys.path: sys.path.insert(0, _T)
_s = importlib.util.spec_from_file_location('house_types_upstream', os.path.join(_T, 'house_types.py'))
_up = importlib.util.module_from_spec(_s); sys.modules['house_types_upstream'] = _up; _s.loader.exec_module(_up)
_up.PAL['dock'] = ([(222, 210, 184), (212, 198, 170), (230, 220, 198)], [(170, 92, 60), (160, 88, 58), (182, 100, 64)])
_up.PAL['horrea'] = ([(232, 222, 200), (224, 212, 188)], [(184, 100, 62), (176, 94, 58)])
_pick = _up.pick_type
def _pick_cs(f, rank, area, on_main, hid):
    if f in ('dock', 'horrea'): return 'hall' if _up.hsh(hid, 31) < .85 else 'flat'
    return _pick(f, rank, area, on_main, hid)
_up.pick_type = _pick_cs
sys.modules[__name__] = _up
