// 目检图：把街上的人（按几个位置取样）和摊子叠到画上。用法：cd /workspace/work/csjs; NODE_PATH=node_modules node <本文件> > /tmp/movers.json；再由 movers_vis.py 画
const src=require('fs').readFileSync((process.env.CSJS||'/workspace/work/csjs')+'/run_ng.js','utf8').split('const w=dom.window;')[0];eval(src+`
const w=dom.window;setTimeout(()=>{const FL=w.__fleet;const o={stalls:FL.stalls.map(s=>[s.x|0,s.y|0]),walkers:[]};
for(const wk of FL.walkers){const r=FL.roads[wk.r];for(const f of [.2,.5,.8]){const q=FL.walkerXY(wk,r.L*f);o.walkers.push([q[0]|0,q[1]|0])}}
console.log('@@'+JSON.stringify(o));process.exit()},6000);`)
