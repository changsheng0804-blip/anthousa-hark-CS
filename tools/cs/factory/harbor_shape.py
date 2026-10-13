"""D2 港池岸线：底账港池是矩形，挖出来是方块水。这里在「港池区」里把岸线往水里收一点，收多少随世界坐标的噪声起伏，
再用圆盘开运算磨掉直角——只收水不加水（人不踩水、船不进岸的约束不会被放松）。ground_ng 和 check_harbors 共用这一个函数。
shore_keep(land, harb, X0, Y0, ppc): land=底账陆地(bool, 像素), harb=港池区(bool), X0/Y0=左上角世界像素, ppc=像素/格 → 保留为水的 bool 图"""
import numpy as np, cv2
def _hash(ix, iy, s=0):
    h = (ix * 374761393 + iy * 668265263 + s * 2147483647) & 0xffffffff
    h = ((h ^ (h >> 13)) * 1274126177) & 0xffffffff
    return ((h ^ (h >> 16)) & 0xffff) / 65535.0
def vnoise(H, W, X0, Y0, cell, s):
    ys, xs = np.mgrid[0:H, 0:W].astype(float); gx = (xs + X0) / cell; gy = (ys + Y0) / cell
    ix = np.floor(gx).astype(np.int64); iy = np.floor(gy).astype(np.int64); fx = gx - ix; fy = gy - iy
    fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy)
    h = lambda a, b: _hash(a, b, s)
    return (h(ix, iy) * (1 - fx) + h(ix + 1, iy) * fx) * (1 - fy) + (h(ix, iy + 1) * (1 - fx) + h(ix + 1, iy + 1) * fx) * fy
def shore_keep(land, harb, X0, Y0, ppc):
    H, W = land.shape
    wat = ~land
    d = cv2.distanceTransform(wat.astype(np.uint8), cv2.DIST_L2, 5)      # 离陆地多远（水像素）
    n = vnoise(H, W, X0, Y0, 2.6 * ppc, 41) * 0.7 + vnoise(H, W, X0, Y0, 1.1 * ppc, 42) * 0.3
    thr = (0.3 + 2.2 * n) * ppc
    zone = cv2.dilate(harb.astype(np.uint8), np.ones((3, 3), np.uint8), iterations=int(ppc)) > 0
    kept = wat & ~(zone & (d < thr))
    r = int(2.2 * ppc)
    op = cv2.morphologyEx(kept.astype(np.uint8), cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))) > 0
    kept = np.where(zone, op, kept)
    sm = cv2.GaussianBlur(kept.astype(np.float32), (0, 0), 0.6 * ppc) > 0.5
    return np.where(zone, sm & wat, kept)
