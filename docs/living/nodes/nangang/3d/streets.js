/* streets（第 2 轮第 0 步从 3d.html 原样拆出）：地面贴图上的街（m/s/c/l 四级，两遍：路缘深色 + 路面）和地标地皮（广场铺石、院子）。
   以后：石板、缝、路缘、街具，写 ctx.reg.frontage（哪户面向哪条街，buildings 读）。现在还没写 frontage。 */
export const name='streets';
export const checkShot=2;
const SC={m:['rgba(118,104,86,.7)','rgb(188,176,154)'],s:['rgba(140,118,88,.4)','rgb(204,188,154)'],c:['rgba(140,118,88,.3)','rgb(206,190,156)'],l:[null,'rgba(212,196,162,.9)']};
export function paint(ctx,X){const {by}=ctx;X.lineCap='round';
  for(let pas=0;pas<2;pas++)for(const k of 'lcsm'){const col=SC[k][pas];if(!col)continue;X.strokeStyle=col;for(const f of by.street){if(f.k!==k||!ctx.live(f))continue;const q=f.g;X.beginPath();X.moveTo(q[0],q[1]);X.lineTo(q[2],q[3]);X.lineWidth=f.w+(pas?0:2);X.stroke()}}
  for(const f of by.landmark||[])if(ctx.live(f)){X.beginPath();f.g.forEach((p,i)=>i?X.lineTo(p[0],p[1]):X.moveTo(p[0],p[1]));X.closePath();X.fillStyle=f.k==='forum'?'rgb(226,218,198)':'rgb(212,200,174)';X.fill()}}
export function build(ctx){}
export function dispose(ctx){}
