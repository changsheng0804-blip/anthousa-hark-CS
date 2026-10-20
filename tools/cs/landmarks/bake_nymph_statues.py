#!/usr/bin/env python3
"""大宁芙殿（Nymphaeum Maius）壁龛里的雕像：SDF → marching cubes → 静态网格（CS 线 landmark 第 2 座，2026-10-20）。

复用 bake_statue.py 的原语（胶囊、椭球、圆台、圆角盒、平滑并）和文件格式（kit/baked.js 读），只是造型换成 3 种姿势：
  A 顶罐的宁芙（hydriaphoros）：长裙（peplos），右手扶肩上的水罐，左手垂下提裙；
  B 披袍的立像：长袍（himation）裹身，右臂横在胸前，左臂垂下，头微侧；
  C 捧贝的宁芙：腰以下披布、上身裸，双手在腹前捧一只贝壳。
史料没有记下宁芙殿里有哪些像（Themistius 只说「宁芙」被请进城），姿势全是假设；按 2 世纪小亚细亚宁芙殿（米利都、锡德）的壁龛像来。
没有十字、没有基督教题材。像高 2.4 m（≈ 真人 1.4 倍），nymphaeum.js 再按壁龛大小放。

  PYTHONPATH=<有 numpy + scikit-image 的目录> python3 tools/cs/landmarks/bake_nymph_statues.py
  → docs/living/nodes/nangang/3d/landmarks/nymphaeum/statue_{a,b,c}_{hi,lo}.bin
坐标：米，y 向上，脚底中心在原点，像面朝 +z；+x = 像的左手（右手坐标系里面朝 +z 的人，右手在 −x），所以下面「右」写 −x。
确定性：没有随机数。
"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import bake_statue as B   # 原语 + 写盘
from skimage.measure import marching_cubes
import struct

ROOT = B.ROOT
OUT = os.path.join(ROOT, 'docs/living/nodes/nangang/3d/landmarks/nymphaeum')
cap, ell, sph, rbox, fr, smin, tor = B.capsule, B.ellipsoid, B.sphere, B.rbox, B.frustum, B.smin, B.torus_y


def body_common(p, head_tilt=0.0):
    """头、颈、肩、胸（女像），各姿势共用；单位米，身高 2.4"""
    k = 0.04
    d = ell(p, (0, 1.62, 0.0), (0.24, 0.33, 0.16))                       # 胸廓
    d = smin(d, ell(p, (0.09, 1.66, 0.11), (0.09, 0.08, 0.07)), 0.04)
    d = smin(d, ell(p, (-0.09, 1.66, 0.11), (0.09, 0.08, 0.07)), 0.04)
    d = smin(d, cap(p, (-0.23, 1.86, -0.01), (0.23, 1.86, -0.01), 0.09), 0.08)   # 肩
    d = smin(d, cap(p, (0, 1.9, 0), (0, 2.05, 0.02), 0.06), k)                 # 颈
    hx = 0.05 * head_tilt
    d = smin(d, ell(p, (hx, 2.19, 0.03), (0.105, 0.135, 0.12)), 0.04)          # 头
    d = smin(d, ell(p, (hx, 2.2, -0.05), (0.12, 0.11, 0.11)), 0.05)            # 发髻
    d = smin(d, ell(p, (hx, 2.17, 0.14), (0.025, 0.04, 0.03)), 0.02)           # 鼻
    return d


def skirt(p, y0, y1, r0, r1, folds=14, amp=0.018, cz=0.0):
    ang = np.arctan2(p[..., 2] - cz, p[..., 0])
    t = np.clip((y1 - p[..., 1]) / (y1 - y0), 0, 1)
    return fr(p, y0, y1, r0, r1, cz) - amp * np.sin(ang * folds) * (0.3 + 0.7 * t)


def pose_a(p):
    """顶罐的宁芙：右手（−x）举到肩上扶罐，罐斜着搭在右肩，左手垂下提裙"""
    d = body_common(p, 0.4)
    d = smin(d, skirt(p, 0.0, 1.32, 0.3, 0.2, 16, 0.02), 0.05)                 # 长裙
    d = smin(d, ell(p, (0, 1.25, 0.0), (0.24, 0.2, 0.17)), 0.08)               # 腰臀
    d = smin(d, cap(p, (0.06, 1.0, 0.02), (0.1, 0.25, 0.14), 0.11, 0.08), 0.06) # 左膝前顶（对立式）
    # 右臂：上臂向外上，前臂折回到头侧扶罐
    d = smin(d, cap(p, (-0.27, 1.86, 0), (-0.38, 2.08, 0.02), 0.055, 0.05), 0.03)
    d = smin(d, cap(p, (-0.38, 2.08, 0.02), (-0.24, 2.3, 0.04), 0.05, 0.04), 0.03)
    # 水罐：椭球 + 罐颈，斜放在右肩上
    d = np.minimum(d, ell(p, (-0.2, 2.42, 0.0), (0.15, 0.2, 0.15)))
    d = np.minimum(d, cap(p, (-0.12, 2.56, 0.0), (-0.02, 2.66, 0.0), 0.05, 0.065))
    # 左臂垂下，手提裙边
    d = smin(d, cap(p, (0.27, 1.86, 0), (0.34, 1.45, 0.03), 0.05, 0.045), 0.03)
    d = smin(d, cap(p, (0.34, 1.45, 0.03), (0.3, 1.08, 0.1), 0.045, 0.04), 0.03)
    d = smin(d, rbox(p, (0.3, 0.85, 0.1), (0.06, 0.24, 0.04), 0.02), 0.05)     # 提起的一束裙褶
    d = smin(d, rbox(p, (0, 0.04, 0.08), (0.2, 0.04, 0.12), 0.02), 0.04)       # 脚
    return d


def pose_b(p):
    """披袍的立像：长袍裹身，右臂（−x）横在胸前，左臂垂下握袍角，头微侧"""
    d = body_common(p, -0.6)
    d = smin(d, skirt(p, 0.0, 1.45, 0.32, 0.23, 11, 0.025), 0.06)
    d = smin(d, ell(p, (0, 1.3, 0.0), (0.26, 0.24, 0.18)), 0.08)
    # 袍子斜搭的一道（从左肩斜到右胯），横向起伏
    band = rbox(p, (0, 1.45, 0.0), (0.3, 0.06, 0.2), 0.04)
    d = smin(d, band - 0.01 * np.sin(p[..., 0] * 30), 0.06)
    # 右臂：上臂下垂，前臂横到胸前
    d = smin(d, cap(p, (-0.27, 1.86, 0), (-0.3, 1.52, 0.06), 0.055, 0.05), 0.03)
    d = smin(d, cap(p, (-0.3, 1.52, 0.06), (0.08, 1.62, 0.17), 0.05, 0.04), 0.03)
    # 左臂垂下，握袍角
    d = smin(d, cap(p, (0.27, 1.86, 0), (0.33, 1.42, 0.0), 0.055, 0.05), 0.03)
    d = smin(d, cap(p, (0.33, 1.42, 0.0), (0.32, 1.02, 0.06), 0.05, 0.045), 0.03)
    d = smin(d, rbox(p, (0.33, 0.7, 0.04), (0.07, 0.33, 0.05), 0.03) - 0.012 * np.sin(p[..., 1] * 40), 0.05)
    d = smin(d, rbox(p, (0, 0.04, 0.08), (0.22, 0.04, 0.12), 0.02), 0.04)
    return d


def pose_c(p):
    """捧贝的宁芙：腰以下披布，上身裸，双手在腹前捧贝壳"""
    d = body_common(p, 0.2)
    d = smin(d, ell(p, (0, 1.38, 0.01), (0.19, 0.2, 0.13)), 0.08)              # 腰腹
    d = smin(d, ell(p, (0, 1.12, 0.0), (0.25, 0.17, 0.17)), 0.07)              # 胯
    d = smin(d, skirt(p, 0.0, 1.12, 0.3, 0.26, 18, 0.022), 0.05)               # 披布（胯以下）
    d = smin(d, tor(p, (0, 1.12, 0), 0.24, 0.035), 0.03)                        # 布卷
    # 两臂向前下，手在腹前合拢
    for s in (-1, 1):
        d = smin(d, cap(p, (0.27 * s, 1.86, 0), (0.3 * s, 1.52, 0.08), 0.05, 0.045), 0.03)
        d = smin(d, cap(p, (0.3 * s, 1.52, 0.08), (0.1 * s, 1.36, 0.24), 0.045, 0.04), 0.03)
    # 贝壳：扁椭球 + 放射棱
    ang = np.arctan2(p[..., 0], p[..., 2] - 0.2)
    sh = ell(p, (0, 1.33, 0.3), (0.2, 0.06, 0.13)) - 0.008 * np.sin(ang * 14)
    d = np.minimum(d, sh)
    d = smin(d, rbox(p, (0, 0.04, 0.08), (0.2, 0.04, 0.12), 0.02), 0.04)
    return d


POSES = {'a': pose_a, 'b': pose_b, 'c': pose_c}


def bake(f, vox, path):
    lo = np.array([-0.62, -0.03, -0.42]); hi = np.array([0.62, 2.72, 0.5])
    n = np.ceil((hi - lo) / vox).astype(int) + 1
    xs, ys, zs = [lo[i] + np.arange(n[i]) * vox for i in range(3)]
    P = np.stack(np.meshgrid(xs, ys, zs, indexing='ij'), -1)
    D = np.pad(f(P), 1, constant_values=1.0)
    verts, faces, _, _ = marching_cubes(D, 0.0, spacing=(vox, vox, vox), allow_degenerate=False)
    verts = verts - vox + lo
    e = vox * 0.5
    g = np.zeros_like(verts)
    for i in range(3):
        dv = np.zeros(3); dv[i] = e
        g[:, i] = f(verts + dv) - f(verts - dv)
    normals = g / np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-9)
    a, b, c = verts[faces[:, 0]], verts[faces[:, 1]], verts[faces[:, 2]]
    if np.mean(np.sum(np.cross(b - a, c - a) * normals[faces[:, 0]], 1)) < 0:
        faces = faces[:, [0, 2, 1]]
    bmin, bmax = verts.min(0), verts.max(0)
    q = np.round((verts - bmin) / (bmax - bmin) * 65535).astype('<u2')
    nq = np.clip(np.round(normals * 127), -127, 127).astype('i1')
    nv, nt = len(verts), len(faces)
    buf = struct.pack('<II6f', nv, nt, *bmin, *bmax) + q.tobytes() + nq.tobytes()
    buf += b'\0' * ((4 - len(buf) % 4) % 4)
    buf += faces.astype('<u2' if nv < 65536 else '<u4').tobytes()
    open(path, 'wb').write(buf)
    print(f'{os.path.basename(path)}: voxel {vox} m, {nv} verts, {nt} tris, {len(buf)/1024:.0f} KB')


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    for k, f in POSES.items():
        bake(f, 0.08, os.path.join(OUT, f'statue_{k}_hi.bin'))
        bake(f, 0.15, os.path.join(OUT, f'statue_{k}_lo.bin'))
