"""Terrain for Anthousa, calibrated to real geography (v3).
Coastline: OpenStreetMap natural=coastline (data/osm_coastline.json, fetched 2026-10-09).
Elevation: SRTM 30 m via opentopodata, sampled every 20 units (data/elev_grid20.json).
Projection: equirectangular, 1 unit = 12 m, origin (lon 28.884, lat 41.058) at top-left.
Note: the coastline is the modern one, including some landfill along the Marmara shore."""
import json, math, os
from functools import lru_cache
from shapely.geometry import shape, Point

W, H = 1200, 800
SEED = 330
LON0, LAT0, MPU = 28.884, 41.058, 12
KX = math.cos(math.radians(41.015)) * 111320 / MPU
KY = 110574 / MPU
_D = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def to_xy(lat, lon):
    return ((lon - LON0) * KX, (LAT0 - lat) * KY)


@lru_cache(maxsize=1)
def land():
    return shape(json.load(open(os.path.join(_D, "land.geojson"))))


@lru_cache(maxsize=1)
def _grid():
    g = json.load(open(os.path.join(_D, "elev_grid20.json")))
    return {tuple(map(int, k.split(","))): (v if v is not None else 0) for k, v in g.items()}


def elevation(x, y):
    g = _grid()
    x = min(max(x, 0), W - 0.001); y = min(max(y, 0), H - 0.001)
    i0, j0 = int(x // 20) * 20, int(y // 20) * 20
    fx, fy = (x - i0) / 20, (y - j0) / 20
    a, b = g[(i0, j0)], g[(i0 + 20, j0)]
    c, d = g[(i0, j0 + 20)], g[(i0 + 20, j0 + 20)]
    return (a + (b - a) * fx) * (1 - fy) + (c + (d - c) * fx) * fy


def is_land(x, y):
    return land().contains(Point(x, y))
