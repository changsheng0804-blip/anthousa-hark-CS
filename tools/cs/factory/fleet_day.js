/* ---------- CS 线 · cs6 粮船日 ----------
   南港的心跳。每三天一回（打开页面的第一天就是），建城 33 年狄奥多西港挖成以后才有。
   节奏照《清明上河图》：清晨码头空 → 望楼喊帆、船队进港、人往码头聚 → 大船靠岸、缆绳崩断、又拉住（唯一亲手设计的一刻）→ 卸粮，扛包的人在码头和粮仓之间来回 → 傍晚散去 → 入夜酒馆挤满水手。
   人群不是随机撒的：每一个都是底账里的一户人家（搬运工、水手、粮商、船匠、近处人家的孩子），从自己家门口出发。
   敲门卡上的话由「身份 × 处境 × 经历」决定，邻居之间不重样（贪心分配，check_fleet.js 检查）。 */
var FLEET=null,FLEET_walkable=()=>true;let dayIdx=0;
(function(){if(!SCENE.fleet)return;const C=SCENE.fleet;
  const sm=u=>{u=clamp(u,0,1);return u*u*(3-2*u)};
  const TR={porter:'搬运工',sailor:'水手',merchant:'粮商',wright:'船匠'};
  const SPR={'搬运工':1,'水手':11,'粮商':2,'船匠':17};
  const sp=k=>PPL.find(m=>m.k===k)||PPL[0];
  const Q=C.quay;const dQ=(x,y)=>Math.hypot(x-Q[0],y-Q[1]);
  /* cs8 再来：船太快。领头的是大船，其余依次跟进；每艘按自己水路的长短走（C.speed 像素/小时） */
  const plen=P=>{let L=0;for(let k=1;k<P.length;k++)L+=Math.hypot(P[k][0]-P[k-1][0],P[k][1]-P[k-1][1]);return L};
  const order=C.ships.map((s,i)=>i).sort((a,b)=>(C.ships[b].main?1:0)-(C.ships[a].main?1:0));
  /* cs15 · backlog 2：船进港最后一段慢下来。起步 40 像素匀加速，中间匀速 C.speed，离泊位最后 140 像素匀减速到停 */
  const SD0=40,SD1=140;
  function prof(s,c){const v=C.speed,L=s.L,T=c-s.t0;if(T<=0)return 0;const T1=2*SD0/v,T3=2*SD1/v,T2=(L-SD0-SD1)/v;let d;
    if(T<T1)d=v*T*T/(2*T1);else if(T<T1+T2)d=SD0+v*(T-T1);else{const r=Math.min(T-T1-T2,T3);d=SD0+v*T2+v*r-v*r*r/(2*T3)}
    return Math.min(1,d/L)}
  const ships=C.ships.map((s,i)=>({...s,i,t0:C.t_in+order.indexOf(i)*C.t_gap,L:s.path?plen(s.path):0,ts:s.path?Math.max(1.2,(plen(s.path)+SD0+SD1)/C.speed):C.t_sail}));
  /* cs7 再来：人不能从海里走。heart.py 从底账算出人走的网（陆地 + 港墙顶，水里不能走），存成方向场；每个人沿着它走到码头/港墙 */
  const WK=C.walk;const DIR={0:[-1,0],1:[1,0],2:[0,-1],3:[0,1],4:[-1,-1],5:[1,1],6:[-1,1],7:[1,-1]};
  const cellAt=(f,x,y)=>{const j=Math.floor(y/WK.R),i=Math.floor(x/WK.R);if(j<0||i<0||j>=WK.H||i>=WK.W)return 'w';return f[j*WK.W+i]};
  FLEET_walkable=(x,y)=>{const ch=cellAt(WK.quay,x,y);return ch!=='w'&&ch!=='x'};
  function trail(f,x,y){/* 从 (x,y) 顺着方向场走到终点；家门口不在网上就找最近的一格 */
    let j=Math.floor(y/WK.R),i=Math.floor(x/WK.R);const at=(j,i)=>j>=0&&i>=0&&j<WK.H&&i<WK.W?f[j*WK.W+i]:'w';
    if(!/[0-7s]/.test(at(j,i))){let best=null;for(let r=1;r<8&&!best;r++)for(let dj=-r;dj<=r;dj++)for(let di=-r;di<=r;di++)if(!best&&/[0-7s]/.test(at(j+dj,i+di)))best=[j+dj,i+di];if(!best)return null;[j,i]=best}
    const P=FLEET_walkable(x,y)?[[x,y]]:[];let n=0;P.push([(i+.5)*WK.R,(j+.5)*WK.R]);while(at(j,i)!=='s'&&n++<2000){const d=DIR[at(j,i)];j+=d[0];i+=d[1];P.push([(i+.5)*WK.R,(j+.5)*WK.R])}
    P.push([(i+.5)*WK.R,(j+.5)*WK.R]);return P}
  {const r=rng(hash('smoke16'));for(const s of smokes){let n=0;while(!FLEET_walkable(s.x,s.y)&&n++<600){s.x=r()*W;s.y=r()*H}}}   /* cs16：炊烟不从海里冒 */
  FLEET={C,on:false,slow:false,cache:{},ships,msgs:{},lineCache:{}};
  FLEET.active=Y=>Y>=C.from&&dayIdx%3===0;
  const ok=(h,Y)=>h.built<=Y&&h.destroyed>Y;
  function granary(Y){const g=(C.granaries||[]).filter(([k,y])=>Y>=y&&has(k)).map(([k])=>LM[k]);let b=null,bd=1e9;for(const l of g){const d=dist(l.xy[0],l.xy[1],Q[0],Q[1]);if(d<bd){bd=d;b=l}}return b}
  // 这一年来码头的人：都是底账里的人家
  FLEET.crowd=function(Y){if(FLEET.cache[Y])return FLEET.cache[Y];const r=rng(hash('fleet'+Y));const out=[];
    const hs=houses.filter(h=>ok(h,Y)&&dQ(h.cx,h.cy)<C.reach).sort((a,b)=>dQ(a.cx,a.cy)-dQ(b.cx,b.cy));
    for(const h of hs){const hh=household(h);const F=famAt(hh,Y);const al=aliveAt(hh,Y);if(!al.length)continue;
      if(SPR[F.trade]&&out.filter(c=>c.kind==='work').length<C.max){const P=trail(WK.quay,h.cx,h.cy);if(P){const e=P[P.length-1];
        out.push({kind:'work',trade:F.trade,h,sp:sp(SPR[F.trade]),home:[h.cx,h.cy],path:P,spot:[e[0]+(r()-.5)*6,e[1]+(r()-.5)*4],go:7.4+r()*1.8,back:[16.8,17.3,17.8][out.filter(c=>c.kind==='work').length%3]+r()*.2,ph:r()})}}
      const kid=al.find(p=>Y-p.b>=6&&Y-p.b<=13);
      if(kid&&dQ(h.cx,h.cy)<C.reach*.7&&out.filter(c=>c.kind==='kid').length<C.kids){const P=trail(WK.wall,h.cx,h.cy);if(P){const e=P[P.length-1];
        out.push({kind:'kid',h,kid,sp:sp(9),home:[h.cx,h.cy],path:P,spot:[e[0]+(r()-.5)*4,e[1]+(r()-.5)*4],go:6.6+r()*1.2,back:11+r()*2,ph:r()})}}}
    const tav=houses.filter(h=>ok(h,Y)&&dQ(h.cx,h.cy)<C.reach*1.2&&famAt(household(h),Y).trade==='酒馆老板');
    const R={crowd:out,tav,g:granary(Y)};FLEET.cache[Y]=R;return R};
  function shipPos(s,c){const u=s.path?prof(s,c):sm((c-s.t0)/s.ts);
    if(s.path){const[px,py]=along(s.path,u);const[qx,qy]=along(s.path,Math.min(1,u+.01));let ang=u>=.98?s.ang:Math.atan2(qy-py,qx-px)+Math.PI;let x=px,y=py;   /* 水路是 heart.py 从底账算的 */
      if(s.main&&c>=C.snap&&c<C.hold+.15){const k=c<C.hold?sm((c-C.snap)/(C.hold-C.snap)):1-sm((c-C.hold)/.15);x+=C.drift[0]*k;y+=C.drift[1]*k;ang+=.12*k}return[x,y,ang,u]}
    const w=C.mouth;
    const a=[C.enter[0]+s.i*22,C.enter[1]+s.i*14];const q1=(1-u)*(1-u),q2=2*(1-u)*u,q3=u*u;
    let x=q1*a[0]+q2*w[0]+q3*s.at[0],y=q1*a[1]+q2*w[1]+q3*s.at[1];
    const du=Math.min(1,u+.02);const x2=(1-du)*(1-du)*a[0]+2*(1-du)*du*w[0]+du*du*s.at[0],y2=(1-du)*(1-du)*a[1]+2*(1-du)*du*w[1]+du*du*s.at[1];
    let ang=u>=.98?s.ang:Math.atan2(y2-y,x2-x)+Math.PI;
    if(s.main&&c>=C.snap&&c<C.hold+.15){const k=c<C.hold?sm((c-C.snap)/(C.hold-C.snap)):1-sm((c-C.hold)/.15);x+=C.drift[0]*k;y+=C.drift[1]*k;ang+=.12*k}
    return[x,y,ang,u]}
  /* 一个人在钟点 c 的位置：去码头、回家都沿着人走的网；扛包、粮商沿底账的路到粮仓 */
  FLEET.pos=function(m,c,g){if(c<m.go||c>=m.back+1.2)return null;
    const climax=c>=C.snap&&c<C.hold+.6,unload=c>=C.hold+.3&&c<16.8;const L=m.path.length;const T=Math.min(1.6,.5+L/120);   /* 路远走得久 */
    if(c<m.go+T){const[x,y,f]=along(m.path,sm((c-m.go)/T));return[x,y,f,false]}
    if(c>=m.back){const[x,y,f]=along(m.path.slice().reverse(),sm((c-m.back)/1.2));return[x,y,f,false]}
    if(g&&unload&&(m.trade==='搬运工'||m.trade==='粮商')){const route=[m.spot,...C.route,g.xy];
      if(m.trade==='粮商'){const[x,y,f]=along(route,sm((c-C.hold-.3)*1.5));return[x,y,f,false]}
      const u=((c-C.hold)/1.0+m.ph)%1;const fw=u<.5;const[x,y,f]=along(fw?route:route.slice().reverse(),fw?u*2:(u-.5)*2);return[x,y,f,!fw]}
    let p=m.spot.slice();if(climax&&m.kind==='work'){const k=sm((c-C.snap)*4)*(1-sm((c-C.hold-.3)*3));const p2=lerp(p,C.bollard,.35*k);if(FLEET_walkable(p2[0],p2[1]))p=p2}
    if(!FLEET_walkable(p[0],p[1]))p=m.path[m.path.length-1].slice();return[p[0],p[1],false,false]};
  FLEET.shipPos=(s,c)=>shipPos(s,c);
  FLEET.tavPeople=h=>{const r2=rng(hash('tv'+h.id));const o=[];for(let k=0;k<7;k++){const a=r2()*6.28,d=9+r2()*9;const x=h.cx+Math.cos(a)*d,y=h.cy+Math.sin(a)*d*.6+4;if(FLEET_walkable(x,y))o.push([x,y])}return o};   /* 酒馆门口挤的人也不下水 */
  function drawBig(x,y,a,s,furl){ctx.save();ctx.translate(x,y);ctx.rotate(a);ctx.fillStyle='rgba(20,30,40,.25)';ctx.beginPath();ctx.ellipse(1.5*s,2.5*s,15*s,5.5*s,0,0,7);ctx.fill();
    ctx.fillStyle='#4e321d';ctx.beginPath();ctx.ellipse(0,0,15*s,5.2*s,0,0,7);ctx.fill();ctx.fillStyle='#7a5434';ctx.beginPath();ctx.ellipse(0,-.6*s,12.5*s,3.4*s,0,0,7);ctx.fill();
    ctx.fillStyle='#d9c08a';for(let k=-2;k<=2;k++)ctx.fillRect(k*3.6*s-1.2*s,-1.6*s,2.4*s,2.4*s);
    ctx.fillStyle='#3a2414';ctx.fillRect(-.6*s,-14*s,1.2*s,14*s);
    if(!furl){ctx.fillStyle='rgba(244,234,210,.97)';ctx.beginPath();ctx.moveTo(-7*s,-13*s);ctx.lineTo(7*s,-13*s);ctx.quadraticCurveTo(9*s,-7*s,7*s,-3*s);ctx.lineTo(-7*s,-3*s);ctx.quadraticCurveTo(-5*s,-7*s,-7*s,-13*s);ctx.fill();ctx.fillStyle='rgba(170,60,40,.8)';ctx.fillRect(-7*s,-9*s,14*s,1.4*s)}
    else{ctx.fillStyle='rgba(230,220,195,.95)';ctx.fillRect(-7*s,-13.5*s,14*s,1.6*s)}ctx.restore()}
  function bubble(x,y,t){const z=cam.z;ctx.font=`${13/z}px serif`;const tw=ctx.measureText(t).width;ctx.fillStyle='rgba(250,244,228,.95)';ctx.strokeStyle='rgba(60,40,20,.8)';ctx.lineWidth=1/z;
    ctx.beginPath();ctx.rect(x-tw/2-6/z,y-24/z,tw+12/z,18/z);ctx.fill();ctx.stroke();ctx.fillStyle='#2a1c10';ctx.fillText(t,x-tw/2,y-10/z)}
  function person(m,x,y,t,i,flip){const z=cam.z;if(z>=1.4){const hh=m.h/72*9.5,ww=m.w/m.h*hh;const bob=Math.abs(Math.sin(t*8+i))*.5;ctx.save();ctx.translate(x,y-bob);if(flip)ctx.scale(-1,1);ctx.drawImage(pplImg,m.x,m.y,m.w,m.h,-ww/2,-hh,ww,hh);ctx.restore()}
    else{ctx.fillStyle=COLS[i%COLS.length];const r=Math.max(1.2,1.6/z);ctx.fillRect(x-r,y-r,2*r,2*r)}}
  const lerp=(a,b,u)=>[a[0]+(b[0]-a[0])*u,a[1]+(b[1]-a[1])*u];
  function along(P,u){let L=0;const seg=[];for(let i=0;i<P.length-1;i++){const l=dist(P[i][0],P[i][1],P[i+1][0],P[i+1][1]);seg.push(l);L+=l}let s=u*L;for(let i=0;i<seg.length;i++){if(s<=seg[i])return[...lerp(P[i],P[i+1],s/seg[i]),P[i+1][0]<P[i][0]];s-=seg[i]}return[...P[P.length-1],false]}
  FLEET.draw=function(t,vis){FLEET.on=FLEET.active(YEAR);FLEET.slow=false;if(!FLEET.on)return;const c=clock,Y=YEAR,R=FLEET.crowd(Y);
    FLEET.slow=c>=C.snap-.35&&c<C.hold+.3;
    // 船
    for(const s of ships){if(c<s.t0)continue;const[x,y,a,u]=shipPos(s,c);if(!vis(x,y,80))continue;drawBig(x,y,a,s.main?1.9:1.45,u>=.98&&c>C.hold+.3);
      if(s.main&&u>=.98){const b=C.bollard;const sx=x+Math.cos(s.ang)*-22,sy=y+Math.sin(s.ang)*-22;
        if(c<C.snap||c>=C.hold){ctx.strokeStyle='#d9c08a';ctx.lineWidth=1.6/cam.z;ctx.beginPath();ctx.moveTo(sx,sy);ctx.quadraticCurveTo((sx+b[0])/2,(sy+b[1])/2+6,b[0],b[1]);ctx.stroke()}
        else{ctx.strokeStyle='#d9c08a';ctx.lineWidth=1.6/cam.z;ctx.beginPath();ctx.moveTo(sx,sy);ctx.lineTo(sx+8,sy+10);ctx.moveTo(b[0],b[1]);ctx.lineTo(b[0]+6,b[1]+9);ctx.stroke()}}}
    // 码头上的人：从自家门口来，到点回家
    const climax=c>=C.snap&&c<C.hold+.6;const unload=c>=C.hold+.3&&c<16.8;const g=R.g;
    R.crowd.forEach((m,i)=>{const q=FLEET.pos(m,c,g);if(!q)return;if(vis(q[0],q[1]))person(q[3]?sp(11):m.sp,q[0],q[1],t,i,q[2])});
    // 那一刻
    const b=C.bollard;if(c>=C.snap-.05&&c<C.snap+.25)bubble(b[0],b[1]-14,'缆绳断了！');else if(c>=C.snap+.25&&c<C.hold)bubble(b[0]-30,b[1]-14,'快！再扔一根过来！');else if(c>=C.hold&&c<C.hold+.3)bubble(b[0],b[1]-14,'拉住了！');
    // 夜里的酒馆
    if(c>=18.6&&c<23.6){R.tav.forEach((h,j)=>{if(!vis(h.cx,h.cy,60))return;ctx.fillStyle=`rgba(255,170,80,${.28+.08*Math.sin(t*2+j)})`;ctx.beginPath();ctx.arc(h.cx,h.cy,10,0,7);ctx.fill();
      FLEET.tavPeople(h).forEach(([x,y],k)=>person(sp(k%3?11:2),x,y,t,k+j,k%2));
      if(cam.z>=1.6&&Math.floor(t/5+j)%4===0)bubble(h.cx,h.cy-12,C.tavern[(Math.floor(t/5)+j)%C.tavern.length])})}
    // 消息栏：照钟点报
    for(const[hh,msg]of C.ticker){const k=Y+':'+dayIdx+':'+hh;if(c>=hh&&c<hh+.4&&!FLEET.msgs[k]){FLEET.msgs[k]=1;$('tk').textContent=msg;$('ticker').style.opacity=1;tkT=14}}};
  // 敲门：身份 × 处境 × 经历；邻居不重样
  FLEET.line=function(h,Y,per){if(!FLEET.active(Y))return null;const d=dQ(h.cx,h.cy);const hh=household(h);const F=famAt(hh,Y);const al=aliveAt(hh,Y);if(!al.length)return null;
    const L=C.lines;let key=null,pool=null,fill={};
    const kid=al.find(p=>Y-p.b>=6&&Y-p.b<=13);const burned=F.B>=48&&hh.ev.some(e=>e[0]===F.B&&/火/.test(e[1]));
    key=FLEET.keyOf(h,Y,per);if(!key)return null;pool=(L[key]||{})[per];if(key==='孩子')fill.k=kid.n;
    if(!pool||!pool.length)return null;
    const ck=Y+':'+per+':'+key;let A=FLEET.lineCache[ck];
    if(!A){A=new Map();const grp=houses.filter(o=>ok(o,Y)).filter(o=>{if(o===h)return true;return dQ(o.cx,o.cy)<C.reach&&FLEET.keyOf(o,Y,per)===key}).sort((a,b)=>a.id-b.id);
      for(const o of grp){const near=new Array(pool.length).fill(1e9);for(const[q,v]of A){const oo=houseById(q);const dd=dist(oo.cx,oo.cy,o.cx,o.cy);if(dd<near[v])near[v]=dd}const st=hash(o.id+key)%pool.length;let v=st,best=-1;for(let k=0;k<pool.length;k++){const c2=(st+k)%pool.length;if(near[c2]>=C.apart){v=c2;break}if(near[c2]>best){best=near[c2];v=c2}}A.set(o.id,v)}   /* 选离得最远的那句，实在不够才重 */
      FLEET.lineCache[ck]=A}
    let v=A.get(h.id);if(v===undefined)v=hash(h.id+key)%pool.length;
    return pool[v].replace('{k}',fill.k||'孩子')};
  FLEET.keyOf=function(h,Y,per){const d=dQ(h.cx,h.cy);const hh=household(h);const F=famAt(hh,Y);const al=aliveAt(hh,Y);if(!al.length)return null;const L=C.lines;
    if(L[F.trade]&&d<C.reach&&L[F.trade][per]&&(per==='morning'||per==='day'||hash('ev'+h.id)%3===0))return F.trade;   /* 入夜以后只有三成人家还在说这件事 */
    const kid=al.find(p=>Y-p.b>=6&&Y-p.b<=13);const burned=F.B>=48&&hh.ev.some(e=>e[0]===F.B&&/火/.test(e[1]));
    if(burned&&d<C.reach&&per==='morning')return '火后';if(kid&&d<C.reach*.7&&(per==='morning'||per==='day'))return '孩子';if(d<C.reach*.6&&L['近处'][per]&&hash('bg'+h.id)%5<2)return '近处';return null};   // 近处人家只有两成被这件事带走，其余照常过日子
})();

/* cs16 · backlog 3：会动的东西登记册。页面上每一种会动（或冒烟）的东西都要登记在这里，写明它该在哪（land 陆地 / water 水 / off 画外 / absent 此街区不出现 / air 天上），
   check_fleet.js 逐种、逐年、逐钟点检查；登记册里少一种，或 frame() 里冒出没登记的新循环，都判不过。 */
/* cs16：队伍、工地的站位算法放在一处，页面画的和检查量的是同一套 */
function csQueueN(s,Y){const R=VEIN.at(Y);const long=Y===48&&R.steps.some(q=>q.lost&&q.b===s.b)||s.lost;return Math.min(long?34:12,Math.round(s.n/(long?6:14)))}
function csQueueAng(s,Y,n){const r=rng(hash('q'+s.i+Y));return r()*6.28}
function csQueuePt(s,ang,k){const d=4+k*3.2,wob=Math.sin(k*1.7)*2.2;return[s.x+Math.cos(ang)*d-Math.sin(ang)*wob,s.y+Math.sin(ang)*d+Math.cos(ang)*wob]}
function csDryNear(x,y,offs){for(const[dx,dy]of offs)if(FLEET_walkable(x+dx,y+dy))return[x+dx,y+dy];return null}   /* 附近第一个人站得住的点，没有就不画这个人 */
function csSitePos(h){return csDryNear(h.cx,h.cy,[[6,3],[-6,3],[0,5],[0,0]])}
function csLateC(L){return L.p.reduce((a,q)=>[a[0]+q[0]/L.p.length,a[1]+q[1]/L.p.length],[0,0])}
function csLatePos(L,j){const c=csLateC(L);return csDryNear(c[0],c[1],[[-15+j*12,4.5],[-15+j*12,12],[j*12-6,-3],[0,0]])}
function csBakeries(R){return R.bak.filter(b=>FLEET_walkable(b.x,b.y))}
function csMovers(Y){const out=[];if(!SCENE.fleet||!FLEET)return out;const add=(kind,domain,pts)=>out.push({kind,domain,pts});
  const Fl=FLEET,wk=[],st=[],pl=[];
  for(const w of walkers){const r=roads[w.r];for(let s=0;s<=r.L;s+=12){const q=walkerXY(w,s);wk.push([q[0],q[1]])}}
  add('街上的人','land',wk);add('摊子','land',stalls.map(s=>[s.x,s.y]));add('烟囱的烟','land',smokes.map(s=>[s.x,s.y]));
  const sites=buildingNow.map(h=>csSitePos(h)).filter(Boolean);for(const k in late){const L=late[k];if(!(L.built>Y&&L.built<=Y+2))continue;for(let j=0;j<3;j++){const q=csLatePos(L,j);if(q)sites.push(q)}}
  add('工地上的人','land',sites);
  if(typeof VEIN!=='undefined'&&VEIN&&VEIN.steps&&VEIN.steps.length&&Y>=33){const R=VEIN.at(Y);
    add('面包房炉烟','land',csBakeries(R).map(b=>[b.x,b.y]));
    for(const s of R.steps){const n=csQueueN(s,Y);const ang=csQueueAng(s,Y,n);for(let k=0;k<n;k++)pl.push(csQueuePt(s,ang,k))}
    add('早市队伍','land',pl)}
  else{add('面包房炉烟','land',[]);add('早市队伍','land',[])}
  const cw=[],tv=[],sh=[];const R=Fl.crowd(Y);
  for(let cl=6;cl<23.5;cl+=.25)for(const m of R.crowd){const q=Fl.pos(m,cl,R.g);if(q)cw.push([q[0],q[1]])}
  for(const h of R.tav)for(const q of Fl.tavPeople(h))tv.push(q);
  for(let cl=6;cl<23.5;cl+=.25)for(const s of Fl.ships){if(cl<s.t0)continue;const p=Fl.shipPos(s,cl);sh.push([p[0],p[1]])}
  add('码头人群','land',cw);add('酒馆门口的人','land',tv);add('大船队','water',sh);
  const outside=a=>a.map(s=>[s.x,s.y]);
  add('旧版停泊船','off',ships.map(s=>[s.x,s.y]));add('旧版海上帆影','off',CL);
  add('旧版进港船','absent',SCENE.intro===false?[]:[[900,190]]);add('赛马','absent',has('hippodrome')?[[0,0]]:[]);
  add('海鸥','air',gulls.map(g=>[g.cx,g.cy]));
  return out}
