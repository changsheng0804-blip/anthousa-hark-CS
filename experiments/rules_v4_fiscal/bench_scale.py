"""规则预演 v4 · 账本规模计算量：干山户籍拼 7 份（3.07 万户/年，与 v3 registry.py scale 同法），只测编册 + 财政的时间与内存。
usage: python3 bench_scale.py"""
import os, sys, time, json, resource
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fiscal as FI  # noqa: E402
RG = FI.RG
G = RG.Registry('scale', 7)
t = time.perf_counter(); years, _ = G.build(50, 70); t_reg = time.perf_counter() - t
rss0 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
X = FI.Fiscal(G, years)
t = time.perf_counter(); F = X.run(51, 70); t_fis = time.perf_counter() - t
out = dict(household_years=sum(len(years[Y]['S']) for Y in range(51, 71)), registry_21y_s=round(t_reg, 3), fiscal_20y_s=round(t_fis, 3),
           per_year_ms=round(t_fis / 20 * 1000, 2), conservation=FI.check_conservation(F), rss_after_registry_mb=round(rss0, 1),
           peak_rss_mb=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1))
json.dump(out, open(os.path.join(HERE, 'out', 'bench_scale.json'), 'w'), indent=1)
print(out)
