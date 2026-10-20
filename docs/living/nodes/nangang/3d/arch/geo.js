/* buildings · 合并几何的小工具：桶（一种材质一个桶，最后一桶一个网格）、三角/四边带 UV、sRGB→线性色。——Hark（CS线）2026-10-20 */
export const lin=c=>{c/=255;return c<=.04045?c/12.92:Math.pow((c+.055)/1.055,2.4)};
export const linC=a=>[lin(a[0]),lin(a[1]),lin(a[2])];
export const mul=(a,k)=>[a[0]*k,a[1]*k,a[2]*k];
export function bucket(){return {pos:[],col:[],uv:[]}}
/* a,b,c = [x,y,z]；col = 线性 [r,g,b]；ua.. = [u,v] */
export function tri(B,a,b,c,col,ua=[0,0],ub=[0,0],uc=[0,0]){B.pos.push(a[0],a[1],a[2],b[0],b[1],b[2],c[0],c[1],c[2]);for(let i=0;i<3;i++)B.col.push(col[0],col[1],col[2]);B.uv.push(ua[0],ua[1],ub[0],ub[1],uc[0],uc[1])}
export function quad(B,a,b,c,d,col,ua,ub,uc,ud){tri(B,a,b,c,col,ua,ub,uc);tri(B,a,c,d,col,ua,uc,ud)}
/* 竖墙：底边 a→b（[x,z]），高 y0→y1，u 0→uL，v v0→v1 */
export function wall(B,a,b,y0,y1,col,uL,v0,v1,u0=0){quad(B,[a[0],y0,a[1]],[b[0],y0,b[1]],[b[0],y1,b[1]],[a[0],y1,a[1]],col,[u0,v0],[u0+uL,v0],[u0+uL,v1],[u0,v1])}
/* 屋面：任意平面多边形（3 或 4 点 [x,y,z]），按檐线 A→B（3D）给 UV：u 沿檐，v 顺坡的斜距；RT = 一张瓦贴图对应的世界长度 */
export function roofFace(B,pts,A,Bp,col,RT){const dx=Bp[0]-A[0],dz=Bp[2]-A[2],L=Math.hypot(dx,dz)||1,ex=dx/L,ez=dz/L;
  const uv=p=>{const px=p[0]-A[0],pz=p[2]-A[2],u=(px*ex+pz*ez)/RT,hd=Math.abs(px*ez-pz*ex),dy=p[1]-A[1];return [u,Math.hypot(hd,dy)/RT]};
  if(pts.length===3)tri(B,pts[0],pts[1],pts[2],col,uv(pts[0]),uv(pts[1]),uv(pts[2]));else quad(B,pts[0],pts[1],pts[2],pts[3],col,uv(pts[0]),uv(pts[1]),uv(pts[2]),uv(pts[3]))}
/* 无贴图的盒子（u,v 都给 0 → 贴图左下角；plain 桶不带贴图） */
export function box(B,c,hx,hz,y0,y1,ax,az,col,top=true){const C=(u,v)=>[c[0]+ax*u-az*v,c[1]+az*u+ax*v],k=[C(-hx,-hz),C(hx,-hz),C(hx,hz),C(-hx,hz)];
  for(let i=0;i<4;i++){const a=k[i],b=k[(i+1)%4];wall(B,a,b,y0,y1,col,0,0,0)}
  if(top)quad(B,[k[0][0],y1,k[0][1]],[k[3][0],y1,k[3][1]],[k[2][0],y1,k[2][1]],[k[1][0],y1,k[1][1]],col,[0,0],[0,0],[0,0],[0,0])}
export function meshOf(T,B,mat,{cast=true,recv=true}={}){if(!B.pos.length)return null;const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(B.pos,3));g.setAttribute('color',new T.Float32BufferAttribute(B.col,3));g.setAttribute('uv',new T.Float32BufferAttribute(B.uv,2));g.computeVertexNormals();const m=new T.Mesh(g,mat);m.castShadow=cast;m.receiveShadow=recv;return m}
/* 柱子：底座 + 柱身（略收分）+ 柱头（钟形 + 方顶板），高度归一到 1，实例按 (r, h, r) 缩放 */
export function columnGeo(T){/* 柱身（6 面、开口）+ 方底座 + 柱头（钟形 + 方顶板），≈44 三角形，高度归一到 1，实例按 (r, h, r) 缩放 */
  const parts=[[new T.BoxGeometry(.95,.06,.95),.03],[new T.CylinderGeometry(.3,.36,.86,6,1,true),.49],[new T.CylinderGeometry(.46,.3,.06,6,1,true),.95],[new T.BoxGeometry(.95,.05,.95),.98]];
  const pos=[],nor=[];for(const [g0,y] of parts){const g=g0.toNonIndexed();g.translate(0,y,0);pos.push(...g.attributes.position.array);nor.push(...g.attributes.normal.array);g0.dispose();g.dispose()}
  const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(pos,3));g.setAttribute('normal',new T.Float32BufferAttribute(nor,3));return g}
