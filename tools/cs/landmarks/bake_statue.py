#!/usr/bin/env python3
"""纪功柱顶上的狄奥多西像：SDF 雕塑 → marching cubes → 静态网格（CS 线 landmark 试点，2026-10-20）。

为什么烘焙：在浏览器里现算 SDF + marching cubes 要几百毫秒（超过 300 ms 的门槛），所以离线算一次，
网格存成小二进制文件，column.js 在载入时读。确定性：没有随机数，同一份脚本永远出同一个文件。

  PYTHONPATH=<有 numpy + scikit-image 的目录> python3 tools/cs/landmarks/bake_statue.py
  → docs/living/nodes/nangang/3d/landmarks/column/statue_hi.bin  （近档，体素 0.055 m）
  → docs/living/nodes/nangang/3d/landmarks/column/statue_lo.bin  （远档，体素 0.16 m）

文件格式（小端）：uint32 顶点数 nv、uint32 三角形数 nt、float32 包围盒 min[3] max[3]，
然后 uint16 位置 nv*3（按包围盒量化）、int8 法线 nv*3（+1 字节对齐到 4）、uint16/uint32 索引 nt*3（nv<65536 用 uint16）。
坐标：米，y 向上，像脚底中心在原点，像面朝 +z；column.js 再按 1 像素 ≈ 0.84 米缩放、按机位朝向转。

造型（史料：LSA-2458「巨像」、Columbia IDP「镀银青铜像」；姿势是假设）：
晚期罗马皇帝立像，胸甲 + 下摆皮条裙（pteruges）+ 左肩披风（chlamys），头戴珠冠，
右臂向前外侧举起作训话手势（adlocutio），左手托球（globus）。烘焙高 5.3 m，column.js 放大到 7 m（≈ 真人 4 倍，「巨像」）。
"""
import os, struct, sys
import numpy as np
from skimage.measure import marching_cubes

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
OUT = os.path.join(ROOT, 'docs/living/nodes/nangang/3d/landmarks/column')


def length(v):
    return np.sqrt(np.sum(v * v, axis=-1))


def capsule(p, a, b, ra, rb=None):
    rb = ra if rb is None else rb
    a, b = np.array(a, float), np.array(b, float)
    pa, ba = p - a, b - a
    h = np.clip(np.sum(pa * ba, -1) / np.dot(ba, ba), 0, 1)
    return length(pa - ba * h[..., None]) - (ra + (rb - ra) * h)


def ellipsoid(p, c, r):
    q = (p - np.array(c, float)) / np.array(r, float)
    k0 = length(q)
    k1 = length(q / np.array(r, float))
    return k0 * (k0 - 1.0) / np.maximum(k1, 1e-6)


def sphere(p, c, r):
    return length(p - np.array(c, float)) - r


def rbox(p, c, b, r):
    q = np.abs(p - np.array(c, float)) - np.array(b, float)
    return length(np.maximum(q, 0)) + np.minimum(np.max(q, -1), 0) - r


def frustum(p, y0, y1, r0, r1, cz=0.0):
    """竖直圆台（y0 处半径 r0，y1 处 r1），圆角近似"""
    rr = np.sqrt(p[..., 0] ** 2 + (p[..., 2] - cz) ** 2)
    t = np.clip((p[..., 1] - y0) / (y1 - y0), 0, 1)
    d_side = rr - (r0 + (r1 - r0) * t)
    d_cap = np.maximum(y0 - p[..., 1], p[..., 1] - y1)
    return np.maximum(d_side, d_cap)


def torus_y(p, c, R, r):
    q = p - np.array(c, float)
    return np.sqrt((np.sqrt(q[..., 0] ** 2 + q[..., 2] ** 2) - R) ** 2 + q[..., 1] ** 2) - r


def smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b * (1 - h) + a * h - k * h * (1 - h)


def statue_sdf(p):
    x, y, z = p[..., 0], p[..., 1], p[..., 2]
    k = 0.07
    # 腿：左腿直立承重，右腿略前、膝微屈（对立式 contrapposto）
    d = capsule(p, (-0.2, 2.45, 0.0), (-0.22, 1.25, 0.02), 0.2, 0.15)
    d = smin(d, capsule(p, (-0.22, 1.25, 0.02), (-0.24, 0.16, 0.0), 0.15, 0.11), k)
    d = smin(d, capsule(p, (0.21, 2.45, 0.0), (0.27, 1.25, 0.16), 0.2, 0.15), k)
    d = smin(d, capsule(p, (0.27, 1.25, 0.16), (0.3, 0.16, 0.06), 0.15, 0.11), k)
    # 脚（靴）
    d = smin(d, rbox(p, (-0.24, 0.08, 0.1), (0.1, 0.06, 0.2), 0.03), 0.05)
    d = smin(d, rbox(p, (0.3, 0.08, 0.16), (0.1, 0.06, 0.2), 0.03), 0.05)
    # 下摆：皮条裙（pteruges），竖向褶子
    ang = np.arctan2(z, x)
    skirt = frustum(p, 2.0, 2.95, 0.6, 0.47) - 0.025 * np.sin(ang * 18) * np.clip((2.95 - y) / 0.9, 0, 1)
    d = smin(d, skirt, 0.05)
    # 胸甲（肌肉胸甲：两块胸肌的鼓起）
    d = smin(d, ellipsoid(p, (0, 3.42, 0.0), (0.56, 0.74, 0.36)), 0.1)
    d = smin(d, ellipsoid(p, (-0.18, 3.6, 0.2), (0.2, 0.16, 0.12)), 0.08)
    d = smin(d, ellipsoid(p, (0.18, 3.6, 0.2), (0.2, 0.16, 0.12)), 0.08)
    # 腰带
    d = smin(d, torus_y(p, (0, 2.95, 0), 0.48, 0.05), 0.03)
    # 肩、颈、头、珠冠
    d = smin(d, capsule(p, (-0.52, 3.95, -0.02), (0.52, 3.95, -0.02), 0.2), 0.12)
    d = smin(d, capsule(p, (0, 4.0, 0), (0, 4.42, 0.03), 0.15), 0.06)
    d = smin(d, ellipsoid(p, (0, 4.72, 0.03), (0.24, 0.31, 0.27)), 0.06)
    d = smin(d, ellipsoid(p, (0, 4.66, 0.27), (0.05, 0.08, 0.06)), 0.03)  # 鼻
    d = np.minimum(d, torus_y(p, (0, 4.86, 0.02), 0.25, 0.035))  # 珠冠
    # 右臂举起（训话手势）
    d = smin(d, capsule(p, (0.6, 3.92, 0.0), (1.08, 4.08, 0.22), 0.15, 0.13), 0.06)
    d = smin(d, capsule(p, (1.08, 4.08, 0.22), (1.55, 4.38, 0.45), 0.13, 0.1), 0.05)
    d = smin(d, ellipsoid(p, (1.65, 4.48, 0.5), (0.08, 0.16, 0.07)), 0.04)  # 张开的手
    # 左臂前伸托球
    d = smin(d, capsule(p, (-0.6, 3.92, 0.0), (-0.74, 3.28, 0.12), 0.14, 0.12), 0.06)
    d = smin(d, capsule(p, (-0.74, 3.28, 0.12), (-0.62, 3.14, 0.56), 0.12, 0.1), 0.05)
    d = np.minimum(d, sphere(p, (-0.6, 3.36, 0.62), 0.19))  # 球
    # 披风：从左肩搭到背后，垂到小腿，带横向起伏（褶）
    cl = rbox(p, (-0.08, 2.65, -0.4), (0.64, 1.35, 0.035), 0.05)
    cl = cl - 0.03 * np.sin(x * 14 + y * 2)
    cl = np.maximum(cl, -(z + 0.2))  # 只留背后
    d = smin(d, cl, 0.08)
    d = smin(d, ellipsoid(p, (-0.62, 3.75, -0.02), (0.24, 0.42, 0.24)), 0.08)  # 搭在左肩的披风团
    d = smin(d, rbox(p, (-0.82, 2.75, 0.02), (0.09, 0.85, 0.2), 0.06) - 0.025 * np.sin(y * 20), 0.06)  # 左臂下垂的披风角
    return d


def statue_sdf_rh(p):
    """上面的造型是按「+x = 像的右手」写的；像面朝 +z 时，它的右手应在 −x（右手坐标系），所以把 x 镜像过来再取样"""
    q = p.copy()
    q[..., 0] *= -1
    return statue_sdf(q)


def bake(vox, name):
    lo = np.array([-1.85, -0.05, -0.7])
    hi = np.array([1.1, 5.35, 0.95])
    n = np.ceil((hi - lo) / vox).astype(int) + 1
    xs, ys, zs = [lo[i] + np.arange(n[i]) * vox for i in range(3)]
    P = np.stack(np.meshgrid(xs, ys, zs, indexing='ij'), -1)
    D = statue_sdf_rh(P)
    D = np.pad(D, 1, constant_values=1.0)
    verts, faces, normals, _ = marching_cubes(D, 0.0, spacing=(vox, vox, vox), allow_degenerate=False)
    verts = verts - vox + lo
    normals = -normals  # skimage 的法线指向场增大的方向（SDF 外正 → 指向外面需要取反？看下面校正）
    # 校正：用中心差分重算法线，保证指向外面
    e = vox * 0.5
    def grad(v):
        g = np.zeros_like(v)
        for i in range(3):
            dv = np.zeros(3); dv[i] = e
            g[:, i] = statue_sdf_rh(v + dv) - statue_sdf_rh(v - dv)
        return g / np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-9)
    normals = grad(verts)
    # 三角形朝向和法线一致
    a, b, c = verts[faces[:, 0]], verts[faces[:, 1]], verts[faces[:, 2]]
    fn = np.cross(b - a, c - a)
    if np.mean(np.sum(fn * normals[faces[:, 0]], 1)) < 0:
        faces = faces[:, [0, 2, 1]]
    bmin, bmax = verts.min(0), verts.max(0)
    q = np.round((verts - bmin) / (bmax - bmin) * 65535).astype('<u2')
    nq = np.clip(np.round(normals * 127), -127, 127).astype('i1')
    nv, nt = len(verts), len(faces)
    buf = struct.pack('<II6f', nv, nt, *bmin, *bmax) + q.tobytes() + nq.tobytes()
    buf += b'\0' * ((4 - len(buf) % 4) % 4)
    buf += faces.astype('<u2' if nv < 65536 else '<u4').tobytes()
    path = os.path.join(OUT, name)
    open(path, 'wb').write(buf)
    print(f'{name}: voxel {vox} m, {nv} verts, {nt} tris, {len(buf)/1024:.0f} KB, bbox {bmin.round(2)}..{bmax.round(2)}')


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    bake(0.055, 'statue_hi.bin')
    bake(0.16, 'statue_lo.bin')
