/* CS 线 · tile_heart.py 生成，勿手改 */
(window.__HEART=window.__HEART||{}).dongjia=function(env){"use strict";
/* 以下五段取自 docs/living/dongjia/index.html，一字不改（tile_heart.py 生成）。——Hark（CS线） */
const {city,HD,SCENE,PPL,pplImg,cam}=env;const W=1820,H=2048;
const ctx=new Proxy({},{get:(_,k)=>{const c=env.ctx(),v=c[k];return typeof v==='function'?v.bind(c):v},set:(_,k,v)=>{env.ctx()[k]=v;return true}});
let YEAR=60,clock=6.0,tkT=0;const $=id=>env.$(id);const smokes=[];const COLS=['#c98b3a','#9b3b2a','#d8cbb0','#3d5a80','#6b5a3a','#e0dccf','#7a4a6a'];
function hash(s){let h=2166136261>>>0;s=String(s);for(let i=0;i<s.length;i++){h^=s.charCodeAt(i);h=Math.imul(h,16777619)}return h>>>0}
function rng(seed){let a=seed>>>0;return function(){a|=0;a=a+0x6D2B79F5|0;let t=Math.imul(a^a>>>15,1|a);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296}}
const pick=(r,a)=>a[Math.floor(r()*a.length)];
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const dist=(a,b,c,d)=>Math.hypot(a-c,b-d);

const HB=city.harbor_box||[-9999,-9999,-9990,-9990];
const inHarbor=(x,y)=>x>HB[0]&&x<HB[2]&&y>HB[1]&&y<HB[3];
const CL=city.coast_line||[[-9999,-9999],[-9999,-9990]];
function isSea(x,y){ // lower-right of coast polyline
  for(let i=0;i<CL.length-1;i++){const[a,b]=CL[i],[c,d]=CL[i+1];
    if((y>=Math.min(b,d)&&y<=Math.max(b,d))){const t=(y-b)/(d-b||1);const xc=a+(c-a)*t;return x>xc}}
  return y>CL[CL.length-1][1]&&false;
}
const LM0={};city.landmarks.forEach(l=>LM0[l.id]=l);const FAR={xy:[-99999,-99999],name:'',now:{},story:''};const LM=new Proxy(LM0,{get:(t,k)=>t[k]||FAR});const has=id=>!!LM0[id];


const MAXY=60;let buildingNow=[];const houses=[];
for(const h of HD.houses){
  const [id,dist_,built,destroyed,p]=h;
  if(destroyed<=1||destroyed<=built+1) continue;
  let cx=0,cy=0;const n=p.length/2;for(let i=0;i<n;i++){cx+=p[2*i];cy+=p[2*i+1]}cx/=n;cy/=n;
  if(inHarbor(cx,cy)) continue;
  houses.push({id,d:dist_,built,destroyed,p,cx,cy,fx:h[5]||0,ty:h[6]||0,ht:h.length>7?h[7]:null,fn:h[8]||'homes'});
}
// spatial grid for click lookup
const G=60,grid=new Map();
houses.forEach(h=>{const k=Math.floor(h.cx/G)+','+Math.floor(h.cy/G);if(!grid.has(k))grid.set(k,[]);grid.get(k).push(h)});
function nearestHouse(x,y,Y,maxd=40){
  let best=null,bd=maxd;const gx=Math.floor(x/G),gy=Math.floor(y/G);
  for(let i=-1;i<=1;i++)for(let j=-1;j<=1;j++){const a=grid.get((gx+i)+','+(gy+j));if(!a)continue;
    for(const h of a){if(Y!=null&&!(h.built<=Y&&h.destroyed>Y))continue;const d=dist(x,y,h.cx,h.cy);if(d<bd){bd=d;best=h}}}
  return best;
}

const NM=city.names_m.filter(n=>n!=='狄奥多罗斯').concat(['格奥尔基奥斯','阿尔塞尼乌斯','佛提乌','雅各','米哈伊尔','狄米特里','马可','菲利普','科斯马斯','达米安','欧瑟比乌斯','利奥','提摩太','巴西尔','阿塔纳修斯','以撒','西奥菲勒斯','卡利尼科斯']);
const NF=city.names_f.filter(n=>n!=='达芙涅').concat(['阿格尼丝','马克里娜','索菲娅','欧朵西娅','普尔喀丽娅','西奥多西娅','奥林匹娅丝','克里斯蒂娜','巴尔巴拉','费布罗妮娅','塔伊斯','妮娜','尤朵拉','玛尔塔','苏珊娜','阿波洛尼娅']);
const ORIG=city.origins, FAITH=city.faiths;
const OBJ=['一盏印着凯乐符号的陶灯','一枚瓦伦斯的铜币，被摸得发亮','从{o}带来的一只陶罐，补过两次','一块蜡板，上面记着谁还欠他们钱','门楣上一个刻歪了的十字','一副骨头骰子，藏在枕头底下','一张蓝党的赛马签，已经输了','一小瓶从圣地带回来的油','一把铜钥匙，门早就换过了','墙角一尊没人敢扔的家神像','一卷写着孩子生日的莎草纸','一只少了把手的玻璃杯，是嫁妆'];
function landType(id){if(/harbor|horrea|granary/.test(id))return'harbor';if(/palace/.test(id))return'palace';if(/hippo/.test(id))return'hippodrome';if(/forum|agora|milion|column/.test(id))return'forum';if(/church/.test(id))return'church';return'other'}
function nearestLM(x,y,filter){let b=null,bd=1e9;for(const l of city.landmarks){if(filter&&!filter(l))continue;const d=dist(x,y,l.xy[0],l.xy[1]);if(d<bd){bd=d;b=l}}return[b,bd]}
const ARRIVE=[[-999,0,'那时这里还是拜扎斯旧城，卫城脚下的老街'],[1,10,'跟着奠基的工程来的，男人在工地上搬石头'],[11,20,'水渠修通后来的，听说城里终于有水了'],[21,30,'大教堂开工那几年来的，城里到处缺人手'],[31,40,'粮道修通后来的，跟着粮船一起进的城'],[41,47,'瓦伦斯在位时来的'],[48,50,'第 48 年南港大火烧了他们原来的家，搬到了这里'],[51,55,'狄奥多西刚登基那几年来的，城里正为信什么吵得厉害'],[56,60,'跟着埃及的粮船来的，城里新盖了好几座粮仓']];
const CITYEV=[[18,'水渠第一次通水，全家去喷泉边看热闹'],[19,'城西大火那夜，从屋顶上看见了半边天的红光'],[30,'大教堂落成，挤在人群里没看见主教'],[38,'城西又起大火，烧了三百多座房子，他们收留过一个远亲'],[44,'大喷泉落成那天，孩子们跳进了水池'],[46,'特罗阿德粮仓开工，家里有人去当了搬运工'],[48,'南港大火，烧了 287 座房子']];
const hhCache=new Map();
function household(h){
  if(hhCache.has(h.id))return hhCache.get(h.id);
  const r=rng(hash('hh'+h.id));
  const [lm]=nearestLM(h.cx,h.cy);const lt=landType(lm.id);
  const people=[];const ev=[];const used=new Set();const fams=[];
  const END=Math.min(MAXY,h.destroyed-1);
  const nm=sx=>{const L=sx==='m'?NM:NF;for(let k=0;k<12;k++){const n=pick(r,L);if(!used.has(n)){used.add(n);return n}}return pick(r,L)};
  function lifespan(){const q=r();if(q<.22)return Math.floor(r()*5);if(q<.3)return 5+Math.floor(r()*20);return 28+Math.floor(r()*45)}
  const AWAY=['去当了兵','去码头上找活干','去给一个石匠当学徒','进了修道院','跟着粮船出了海'];
  let B=h.built<1?-Math.floor(r()*40):h.built, first=true;
  while(B<=END&&fams.length<5){
    const origin=(first&&h.built<1&&r()<.7)||(!first&&r()<.35)?'本城生':pick(r,ORIG.filter(o=>o!=='本城生'));
    const fr=r();const faith=fr<.55?FAITH[0]:fr<.8?FAITH[1]:FAITH[2];
    const trade=pick(r,city.trades[lt]||city.trades.other);
    const fam={B,origin,faith,trade,people:[]};fams.push(fam);
    const E=(y,t)=>{if(y>=fam.B&&y<=END)ev.push([y,t])};
    const P=p=>{p.fam=fam;fam.people.push(p);people.push(p);return p};
    const hAge=20+Math.floor(r()*18);
    const head=P({n:nm('m'),s:'m',b:B-hAge,g:0});head.d=Math.max(head.b+lifespan(),B+1+Math.floor(r()*6));
    const wife=P({n:nm('f'),s:'f',b:head.b+2+Math.floor(r()*8),g:0,bride:true});wife.d=Math.max(wife.b+lifespan(),B+1);
    if(first){const arr=ARRIVE.find(a=>B>=a[0]&&B<=a[1])[2];ev.push([B,(origin==='本城生'?'一家人搬进这栋房子。':'一家人从'+origin+'来，住进这栋房子。')+arr])}
    else ev.push([B,'房子空了一阵，'+head.n+'一家'+(origin==='本城生'?'从城里另一头':'从'+origin)+'搬了进来。'+(B>=48?'他们原来的家烧在了南港大火里':ARRIVE.find(a=>B>=a[0]&&B<=a[1])[2].replace(/^那时.*$/,'')).replace(/。$/,'')]);
    function line(father,mother,g){let y=Math.max(mother.b+17,father.b+19,B-25);const end=Math.min(mother.b+40,mother.d,father.d+1,MAXY);let heir=false;
      while(true){y+=1+Math.floor(r()*3);if(y>end)break;
        const sx=r()<.5?'m':'f';const k=P({n:nm(sx),s:sx,b:y,g:g+1});k.d=k.b+lifespan();
        const life=k.d-k.b;E(y,(g===0?'':g===1?'孙辈':'曾孙辈')+(sx==='m'?'儿子':'女儿')+k.n+'出生'+(life<5?'，'+(life<1?'没满一年':'活到 '+life+' 岁')+'就夭折了':''));
        if(sx==='m'&&life>21&&g<4){const wy=k.b+20+Math.floor(r()*6);
          if(!heir&&wy<k.d&&wy<=MAXY){heir=true;const bride=P({n:nm('f'),s:'f',b:k.b-2+Math.floor(r()*6),g:g+1,bride:true,married:wy});bride.d=Math.max(bride.b+lifespan(),wy+1);E(wy,k.n+'娶了'+bride.n+'，新娘住进了这栋房子');line(k,bride,g+1)}
          else{const ly=k.b+17+Math.floor(r()*5);if(ly<k.d&&ly<=MAXY){k.left=ly;E(ly,k.n+pick(r,AWAY))}}}
        else if(sx==='f'&&life>17){const wy=k.b+15+Math.floor(r()*5);if(wy<k.d&&wy<=MAXY){k.left=wy;const tgt=nearestHouse(h.cx+(r()-.5)*700,h.cy+(r()-.5)*700,wy,220);if(tgt&&tgt.id!==h.id){k.to=tgt.id;E(wy,k.n+'出嫁，嫁到了另一个街区')}else{k.to='外城';E(wy,k.n+'出嫁，嫁到了城外')}}}
      }}
    line(head,wife,0);
    fam.people.forEach(p=>{const life=p.d-p.b;if(p.d<=END&&p.d>=B&&life>=5&&!(p.left&&p.left<=p.d))E(p.d,p.n+'去世，'+life+' 岁')});
    let last=B;fam.people.forEach(p=>{if(p.b>B+60)return;const out=p.left?Math.min(p.left,p.d):p.d;if(out>last)last=out});
    fam.out=last;
    if(last<=END)ev.push([last,'这一家的最后一个人'+(fam.people.some(p=>p.left===last)?'也搬走了':'也走了')+'，房子空了']);
    first=false;B=last+1+Math.floor(r()*3);
  }
  for(const[cy,t]of CITYEV)if(cy>fams[0].B&&cy<=END&&r()<.35)ev.push([cy,t]);
  if(h.destroyed<=MAXY){const why=h.destroyed===48?'南港大火烧了房子，一家人投奔了亲戚':h.destroyed>50?'房子被拆了，地皮给了新修的公家建筑':h.destroyed===30?'房子被拆了，给大教堂让路。一家人搬走了':h.destroyed===46?'房子被拆了，地皮划给了特罗阿德粮仓':h.destroyed===49?'房子卖给了一户尼西亚派信徒，后来成了阿纳斯塔西娅':'房子没了';ev.push([h.destroyed,why])}
  ev.sort((a,b)=>a[0]-b[0]);
  const obj=pick(r,OBJ).replace('{o}',fams[0].origin==='本城生'?'老家':fams[0].origin);
  const hh={h,B:fams[0].B,fams,people,ev,obj};
  hhCache.set(h.id,hh);return hh;
}
function famAt(hh,Y){let f=hh.fams[0];for(const x of hh.fams)if(x.B<=Y)f=x;return f}
function aliveAt(hh,Y){const f=famAt(hh,Y);return f.people.filter(p=>p.b<=Y&&p.d>Y&&(!p.married||p.married<=Y)&&!(p.left&&p.left<=Y))}

const _hid=new Map(houses.map(h=>[h.id,h]));function houseById(id){return _hid.get(id)}
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
  FLEET.crowdGen=function*(Y){if(FLEET.cache[Y])return FLEET.cache[Y];const r=rng(hash('fleet'+Y));const out=[];
    const hs=houses.filter(h=>ok(h,Y)&&dQ(h.cx,h.cy)<C.reach).sort((a,b)=>dQ(a.cx,a.cy)-dQ(b.cx,b.cy));
    for(const h of hs){yield;const hh=household(h);const F=famAt(hh,Y);const al=aliveAt(hh,Y);if(!al.length)continue;
      if(SPR[F.trade]&&out.filter(c=>c.kind==='work').length<Math.round(C.max*FLEET.shipN(Y)/ships.length)){const P=trail(WK.quay,h.cx,h.cy);if(P){const e=P[P.length-1];
        out.push({kind:'work',trade:F.trade,h,sp:sp(SPR[F.trade]),home:[h.cx,h.cy],path:P,spot:[e[0]+(r()-.5)*6,e[1]+(r()-.5)*4],go:7.4+r()*1.8,back:[16.8,17.3,17.8][out.filter(c=>c.kind==='work').length%3]+r()*.2,ph:r()})}}
      const kid=al.find(p=>Y-p.b>=6&&Y-p.b<=13);
      if(kid&&dQ(h.cx,h.cy)<C.reach*.7&&out.filter(c=>c.kind==='kid').length<C.kids){const P=trail(WK.wall,h.cx,h.cy);if(P){const e=P[P.length-1];
        out.push({kind:'kid',h,kid,sp:sp(9),home:[h.cx,h.cy],path:P,spot:[e[0]+(r()-.5)*4,e[1]+(r()-.5)*4],go:6.6+r()*1.2,back:11+r()*2,ph:r()})}}}
    const tav=houses.filter(h=>ok(h,Y)&&dQ(h.cx,h.cy)<C.reach*1.2&&famAt(household(h),Y).trade==='酒馆老板');
    /* cs18：每座栈桥都有人（人家就近选站位会全挤在最近一座） */
    /* cs22 码头逐年长：还没建成的栈桥上不站人——走到栈桥根就停在岸上等 */
    {const DK=(C.docks||[]).filter(d=>d.from>Y);const inDk=(x,y)=>DK.some(d=>d.rects.some(q=>x>=q[0]-2&&x<=q[0]+q[2]+2&&y>=q[1]-2&&y<=q[1]+q[3]+2));
      if(DK.length)for(const m of out){const k=m.path.findIndex(p=>inDk(p[0],p[1]));if(k>=0||inDk(m.spot[0],m.spot[1])){if(k>=0)m.path=m.path.slice(0,Math.max(1,k));const e=m.path[m.path.length-1];m.spot=[e[0],e[1]]}}}
    {const ps=(C.pier_spots||[]).filter((s,i)=>!C.pier_from||C.pier_from[i]<=Y);const wk=out.filter(c=>c.kind==='work');const at=s=>wk.filter(m=>m.pier===s);
      for(const m of wk){let b=null,bd=16;for(const s of ps){const d=dist(m.spot[0],m.spot[1],s[0],s[1]);if(d<bd){bd=d;b=s}}m.pier=b}
      for(const[want,give]of[[3,4],[2,2]])for(const s of ps){let guard=0;while(at(s).length<want&&guard++<4){const pool=wk.filter(m=>m.pier!==s&&(!m.pier||at(m.pier).length>give)).sort((a,b)=>dist(a.spot[0],a.spot[1],s[0],s[1])-dist(b.spot[0],b.spot[1],s[0],s[1]));
        let moved=false;for(const m of pool){yield;const t=[s[0]+(r()-.5)*6,s[1]+(r()-.5)*4];const e=m.spot;const RR=WK.R,gw=Math.ceil(W/RR),key=(a,b)=>b*gw+a;const sa=Math.floor(e[0]/RR),sb=Math.floor(e[1]/RR),ta=Math.floor(t[0]/RR),tb=Math.floor(t[1]/RR);
          const prev=new Map([[key(sa,sb),-1]]);const Q2=[[sa,sb]];let found=false;for(let qi=0;qi<Q2.length&&!found&&qi<40000;qi++){if(qi%1200===0)yield;const[a,b]=Q2[qi];for(const[da,db]of[[1,0],[-1,0],[0,1],[0,-1],[1,1],[1,-1],[-1,1],[-1,-1]]){const na=a+da,nb=b+db;if(na<0||nb<0||prev.has(key(na,nb)))continue;if(!FLEET_walkable((na+.5)*RR,(nb+.5)*RR))continue;prev.set(key(na,nb),key(a,b));Q2.push([na,nb]);if(na===ta&&nb===tb){found=true;break}}}
          if(found){const seg=[];let k=key(ta,tb);while(k>=0){seg.push([(k%gw+.5)*RR,(Math.floor(k/gw)+.5)*RR]);k=prev.get(k)}seg.reverse();m.path=m.path.concat(seg,[t]);m.spot=t;m.pier=s;moved=true;break}}
        if(!moved)break}}}
    const R={crowd:out,tav,g:granary(Y)};FLEET.cache[Y]=R;return R};
  FLEET.crowd=function(Y){if(FLEET.cache[Y])return FLEET.cache[Y];const g=FLEET.crowdGen(Y);let s;while(!(s=g.next()).done);return s.value};
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
  /* cs17 · 栈桥站位：从栈桥尖上扛包去粮仓，直线会跨水。直线每 6 像素都在网上就走直线，否则先沿自己来的路退到离扛包路最近的一点，再走；还不行就留在站位上 */
  const hauls={};
  function haul(m,g){const key=m.h.id+'|'+g.xy[0];if(key in hauls)return hauls[key];const base=[...C.route,g.xy];
    const ok=R=>{for(let k=1;k<R.length;k++){const a=R[k-1],b=R[k],n=Math.max(1,Math.ceil(Math.hypot(b[0]-a[0],b[1]-a[1])/6));for(let t=0;t<=n;t++)if(!FLEET_walkable(a[0]+(b[0]-a[0])*t/n,a[1]+(b[1]-a[1])*t/n))return false}return true};
    let r=[m.spot,...base];if(!ok(r)){const rp=m.path.slice().reverse();let bi=0,bd=1e9;rp.forEach((p,i)=>{const d=Math.hypot(p[0]-base[0][0],p[1]-base[0][1]);if(d<bd){bd=d;bi=i}});r=[m.spot,...rp.slice(0,bi+1),...base];if(!ok(r))r=null}
    return hauls[key]=r}
  /* 一个人在钟点 c 的位置：去码头、回家都沿着人走的网；扛包、粮商沿底账的路到粮仓 */
  FLEET.pos=function(m,c,g){if(c<m.go||c>=m.back+1.2)return null;
    const climax=c>=C.snap&&c<C.hold+.6,unload=c>=C.hold+.3&&c<16.8;const L=m.path.length;const T=Math.min(1.6,.5+L/120);   /* 路远走得久 */
    if(c<m.go+T){const[x,y,f]=along(m.path,sm((c-m.go)/T));return[x,y,f,false]}
    if(c>=m.back){const[x,y,f]=along(m.path.slice().reverse(),sm((c-m.back)/1.2));return[x,y,f,false]}
    if(g&&unload&&(m.trade==='搬运工'||m.trade==='粮商')&&haul(m,g)){const route=haul(m,g);   /* cs17：栈桥上的人扛包也不跨水，先顺自己的来路退回岸上 */
      if(m.trade==='粮商'){const[x,y,f]=along(route,sm((c-C.hold-.3)*1.5));return[x,y,f,false]}
      const u=((c-C.hold)/1.0+m.ph)%1;const fw=u<.5;const[x,y,f]=along(fw?route:route.slice().reverse(),fw?u*2:(u-.5)*2);return[x,y,f,!fw]}
    let p=m.spot.slice();if(climax&&m.kind==='work'){const k=sm((c-C.snap)*4)*(1-sm((c-C.hold-.3)*3));const p2=lerp(p,C.bollard,.35*k);if(FLEET_walkable(p2[0],p2[1]))p=p2}
    if(!FLEET_walkable(p[0],p[1]))p=m.path[m.path.length-1].slice();return[p[0],p[1],false,false]};
  FLEET.shipPos=(s,c)=>shipPos(s,c);
  FLEET.shipOn=(s,Y)=>!C.ship_from||C.ship_from[s.i]<=Y;FLEET.shipN=Y=>ships.filter(s=>FLEET.shipOn(s,Y)).length;   /* cs25 */
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
  /* cs22 码头逐年长：没建成的栈桥用四周的水色盖掉；建成前两年是工地（先打桩、再铺板，白天有人干活） */
  FLEET.dockWork=function(Y){const out=[];for(const d of C.docks||[]){if(!(d.from>Y&&d.from-Y<=2))continue;
      const R=d.rects.slice().sort((a,b)=>Math.hypot(a[0]-d.root[0],a[1]-d.root[1])-Math.hypot(b[0]-d.root[0],b[1]-d.root[1]));const n=Math.max(1,Math.round(R.length*(d.from-Y===2?.35:.7)));
      for(let j=0;j<3;j++){const q=R[Math.max(0,n-1-j)];let p=[q[0]+q[2]/2,q[1]+q[3]/2];if(!FLEET_walkable(p[0],p[1]))p=[d.root[0],d.root[1]];out.push({d,R,n,p})}}return out};
  FLEET.dockDraw=function(t){const D=C.docks;if(!D||!D.length)return;const Y=YEAR;const ks=(SCENE.keys||[]).map(k=>k[0]);let kk=ks[0];for(const k of ks)if(k<=Y)kk=k;
    for(const d of D){if(d.from<=Y||(d.borrow&&d.borrow[keyFor(Y)[0]]))continue;const c=d.col[kk]||d.col[Object.keys(d.col)[0]];ctx.save();ctx.fillStyle=ctx.shadowColor=`rgb(${c[0]},${c[1]},${c[2]})`;ctx.shadowBlur=5;for(const q of d.rects)ctx.fillRect(q[0]-1,q[1],q[2]+2,q[3]);ctx.restore()}   /* 借不到水才退回平涂 */
    const W=FLEET.dockWork(Y);const done=new Set();
    for(const w of W){if(done.has(w.d))continue;done.add(w.d);ctx.fillStyle='rgba(122,86,52,.95)';for(let i=0;i<w.n;i++){const q=w.R[i];ctx.fillRect(q[0],q[1]+1,q[2],q[3]-2)}
      ctx.fillStyle='rgba(58,40,26,.9)';for(let i=w.n;i<w.R.length;i++){const q=w.R[i];for(let x=q[0]+2;x<q[0]+q[2];x+=6){ctx.beginPath();ctx.arc(x,q[1]+4,1.3,0,7);ctx.fill()}}
      /* 岸上栈桥根：一垛木料、一堆石块（工地） */
      const [rx,ry]=w.d.root;ctx.fillStyle='rgba(150,108,66,.95)';for(let k=0;k<4;k++)ctx.fillRect(rx-9,ry-12+k*2,12,1.6);ctx.fillStyle='rgba(165,160,150,.95)';for(let k=0;k<5;k++){ctx.beginPath();ctx.arc(rx+6+(k%3)*2.4,ry-10+Math.floor(k/3)*2.2,1.3,0,7);ctx.fill()}}
    if(clock>=7&&clock<17)for(const [i,w] of W.entries()){const b=Math.sin(t*4+i*2)*.8;ctx.fillStyle='rgba(70,48,30,.95)';ctx.beginPath();ctx.arc(w.p[0]+(i-1)*3,w.p[1]+b,1.6,0,7);ctx.fill();ctx.fillStyle='rgba(220,190,150,.95)';ctx.beginPath();ctx.arc(w.p[0]+(i-1)*3,w.p[1]-2+b,1,0,7);ctx.fill()}};
  FLEET.draw=function(t,vis){FLEET.dockDraw(t);FLEET.on=FLEET.active(YEAR);FLEET.slow=false;if(!FLEET.on)return;const c=clock,Y=YEAR,R=FLEET.crowd(Y);
    FLEET.slow=c>=C.snap-.35&&c<C.hold+.3;
    // 船
    for(const s of ships){if(c<s.t0||!FLEET.shipOn(s,Y))continue;const[x,y,a,u]=shipPos(s,c);   /* cs25：岸线够几条船才来几条 */if(!vis(x,y,80))continue;drawBig(x,y,a,s.main?1.9:1.45,u>=.98&&c>C.hold+.3);
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


/* ── 项 4b 敲门卡（取自街区页，见 tile_heart.py 注释）── */
const late=HD.late;const STORIES=env.STORIES||{},VOICES=env.VOICES||{};let sel=null,threads=[],threadT=0;const VEIN=null;
const showCard=html=>env.showCard(html),blip=()=>{},flyTo=(x,y,z)=>env.flyTo(x,y,z),setYear=y=>env.setYear(y);
const TODAY_HILL={
 '陶匠':{morning:['开窑看昨夜那一窑成了几只','和泥，赤脚踩得啪啪响','把晾干的坯子搬到太阳底下'],day:['在转盘前拉坯','给新罐子刷釉','挑着一担罐子下坡去卖'],evening:['封窑，往火口里添最后一捆荆条','数今天烧裂了几只','坐在窑边吃晚饭'],night:['守着窑火打盹','睡了，窑还温着','听窑里罐子冷下来的轻响']},
 '面包师':{morning:['天没亮就生了炉子','头一炉饼出炉，门口已经有人在等','揉面揉得满头是汗'],day:['在门口卖饼','给坡下的酒馆送饼','扫面粉，扫出一小堆'],evening:['把卖剩的饼分给邻居','封了炉门','数今天的铜钱'],night:['把明天的面盖上湿布','睡了，炉灰还热','借着炉火补衣服']},
 '运水人':{morning:['在蓄水池边排队','挑着第一担水上坡','把水罐一只只冲干净'],day:['挑着水罐上坡，见人就点头','下山去金角湾码头卖水','给坡上的面包铺送水'],evening:['挑完最后一趟，坐在门口揉肩','给自家缸里添满水','在池边跟别的运水人说闲话'],night:['睡了，水罐倒扣在门外','肩膀疼得睡不着','给磨破的垫肩缝补']},
 '织工':{morning:['把经线绷上织机','到门口借着晨光理线','煮一锅染料'],day:['织机咔嗒咔嗒响了一整天','把一匹布送去主顾家','把染好的线晾在绳上'],evening:['收了机，把布卷起来','跟邻居换了一块饼','借着最后的天光接断线'],night:['还在织，梭子声一下一下','睡了，织机上搭着半匹布','在黑里摸着理线']},
 '鞋匠':{morning:['把皮子泡上水','在门口磨锥子','给搬运工补一双磨穿的鞋'],day:['坐在门口绱鞋','给一个孩子量脚','去坡下收皮子'],evening:['把做好的鞋一双双摆进柜子','去主顾家送鞋','收摊，把鞋楦挂回墙上'],night:['借着炉火钉鞋跟','睡了，锤子搁在门边','给自家孩子缝鞋']},
 '酒馆老板':{morning:['把昨夜的酒碗洗干净','卸下门板，洒水压尘','去坡下的酒窖搬酒'],day:['在柜台后舀酒','跟送酒的人讲价','给几个挑水的人倒水歇脚'],evening:['酒馆里挤满了收工的人','听人说皇帝在东方打了败仗','把醉倒的客人扶到门外'],night:['数今天的铜钱','送走最后一个酒客','插上门闩，熄了灯']}};
function todayFor(F,Y,per,id){const r=rng(hash(id+':'+Y+':'+per));if(SCENE.id!=='xero')return pick(r,city.today[per==='evening'?'evening':per]);
 const T=TODAY_HILL[F.trade];let a=T?T[per].slice():city.today[per].filter(t=>!/码头|粮船|渔网/.test(t));
 if(per==='evening'&&F.faith==='尼西亚派'&&Y>=49)a.push('去阿纳斯塔西娅听格里高利讲道');if(per==='day'&&Y>=25)a.push('下午挤进竞技场喊破了嗓子');return pick(r,a)}

const ZNAME={dock:'码头货栈',horrea:'仓场',water:'汲水坊',planned:'新街坊',market:'市集',shops:'铺面',homes:'民居'};
function zoneOf(h,Y){const z=SCENE.zones&&SCENE.zones[h.id];let c='homes';if(z)for(const [y,k] of z)if(y<=Y)c=k;return c}

function periodOf(t){return t>=5&&t<9?'morning':t>=9&&t<18?'day':t>=18&&t<21?'evening':'night'}
function relLabel(p,head,al){if(p===head)return'当家';const dg=p.g-head.g;
  if(dg===0)return p.bride?(head.bride?'妯娌':'妻子'):(p.s==='m'?'兄弟':'姐妹');
  if(dg===-1)return p.bride?'母亲':(p.s==='m'?'父亲':'姑母');
  const T=[null,['儿子','女儿','儿媳'],['孙子','孙女','孙媳'],['曾孙','曾孙女','曾孙媳'],['玄孙','玄孙女','玄孙媳']][dg];if(!T)return'亲戚';return p.bride?T[2]:p.s==='m'?T[0]:T[1]}

function tiePos(k,Y){if(k==='daph'){const w=DAPH.where(Y);return w}if(k==='theo'){const w=THEO.where(Y);return w}const t=houseById(+k);return t?[t.cx,t.cy,t.id]:null}
function renderDeep(h,S,Y,per){
  const beats=S.beats.filter(b=>b[0]<=Y);const cur=beats[beats.length-1];
  const al=S.members.filter(m=>m.b<=Y&&m.d>Y);const gone=Y>=h.destroyed||(Y>=h.built&&al.length===0&&S.members.every(m=>m.d<=Y));
  const tl='<div class="life">'+S.beats.map(([y,t])=>`<div class="${y>Y?'fut':''}"><span class="y">建城 ${y} 年</span>${y>Y?'……':t}</div>`).join('')+'</div>';
  if(Y<h.built&&!cur){showCard(`<h2>这里还是空地</h2><div class="meta">建城 ${Y} 年</div><div class="now">这栋房子要到建城 ${h.built} 年才盖起来，住进来的人家有一段故事。把年代往后拨。</div><div class="pin">◆ 已固定：拨动年代，看这一家怎么过</div>`);return}
  const now=gone||Y<h.built?'':(S.now[per==='race'?'day':per]||S.now.day);
  const ppl=al.map(m=>`${m.n}（${m.r}，${Y-m.b} 岁）`).join('、');
  showCard(`<h2>${S.title}</h2><div class="meta">${S.meta}</div>`
   +(now?`<div class="now">此刻：${now}</div>`:'')
   +`<div class="quote">“${S.quote}”</div>`
   +(gone?`<div class="story">${S.gone||'这家人已经不在这里了。'}</div>`:(cur?`<div class="story">${cur[1]}</div>`:''))
   +(gone?'':`<div class="wf"><b>想要</b>${S.want}</div><div class="wf"><b>怕</b>${S.fear}</div>`)
   +`<div class="obj">屋里有：<b>${S.object[0]}</b>。${S.object[1]}</div>`
   +(ppl&&!gone?`<div class="ppl">${ppl}</div>`:'')
   +`<details><summary>这一家的年代</summary>${tl}</details><div class="pin">◆ 已固定：拨动年代，看这一家怎么过</div>`);
  for(const [k,t,y0] of S.ties){if(Y<y0)continue;const p=tiePos(k,Y);if(!p)continue;threads.push({fx:h.cx,fy:h.cy,x:p[0],y:p[1],t,go:p[2]})}
}
function lifeHTML(items,Y){return '<div class="life">'+items.map(([y,t])=>`<div class="${y>Y?'fut':''}"><span class="y">${y<1?'建城前':'建城 '+y+' 年'}</span>${y>Y?'……':t}</div>`).join('')+'</div>'}
function isPresent(P){const t=clock;if(SCENE.id==='xero')return true;return P.key==='daph'?(t>=5&&t<17):(t>=6&&t<20)}
function renderCard(){
  const Y=YEAR,per=periodOf(clock);threads=[];
  if(!sel){return}
  if(sel.kind==='person'){csPersonCard(Y);threadT=performance.now();return}
  if(sel.kind==='house'&&STORIES[sel.hh.h.id]){renderDeep(sel.hh.h,STORIES[sel.hh.h.id],Y,per);return}
  if(sel.kind==='house'){
    const hh=sel.hh,h=hh.h;
    if(Y<h.built){showCard(`<h2>这里还是空地</h2><div class="meta">建城 ${Y} 年</div><div class="now">${h.built<1?'':'这栋房子要到建城 '+h.built+' 年才盖起来。'}把年代往后拨。</div>`+lifeHTML(hh.ev,Y)+`<div class="pin">◆ 已固定：拨动年代，这一家会跟着变</div>`);return}
    const al=aliveAt(hh,Y);const gone=Y>=h.destroyed;const F=famAt(hh,Y);
    const males=al.filter(p=>p.s==='m'&&!p.bride&&Y-p.b>=16).sort((a,b)=>a.b-b.b);const head=males[0]||al.slice().sort((a,b)=>a.b-b.b)[0];
    const nm=head?head.n+'家':'这一家';
    const ppl=gone?'<i>这家人已经搬走了。</i>':(al.length?al.slice().sort((a,b)=>a.b-b.b).map(p=>`<a class="csgo" data-p="${hh.people.indexOf(p)}">${p.n}</a>（${relLabel(p,head,al)}，${Y-p.b} 岁）`).join('、')+(()=>{const L=csInHere(h,Y);return L.length?'<br>嫁进来的：'+L.map(({x,p:q,hh:o})=>`<a class="csgo" data-pf="${x.from}:${x.pi}">${q.n}</a>（${csSpouse(q).hus.n}${csSpouse(q).hus.d<=Y?'的遗孀':csSpouse(q).hus.left&&csSpouse(q).hus.left<=Y?'的妻子，丈夫离家在外':'的妻子'}，从${csGo(x.from,(csHeadOf(o,q.left)||{n:'另一'}).n+'家')}嫁来，${Y-q.b} 岁）`).join('、'):''})():'<i>屋里没人了，只剩邻居偶尔来看看。</i>');
    let today=gone?'':todayFor(F,Y,per,h.id);if(!gone&&Y===48&&VEIN&&VEIN.steps.length){const vb=veinBread(h,Y);if(vb&&vb.lost)today=per==='night'?'明天还得天不亮就去台阶上排队，原来那家面包房烧没了':'在台阶上排了半天队才领到面包，原来那家面包房烧没了'}if(!gone&&FLEET){const fl=FLEET.line(h,Y,per);if(fl)today=fl}
    const V=VOICES[h.id],vOn=V&&V.fam===F.B&&!gone&&al.length>0;let vHTML='',objHTML=`<b>${hh.obj}</b>`,narH=null,narN='';
    if(vOn){const vn=V.now,nowT=typeof vn==='string'?(per!=='night'?vn:''):((vn&&vn[per])||'');if(V.nowY&&Y>=V.nowY[0]&&Y<=V.nowY[1]&&nowT)today=nowT;
      objHTML=`<b>${V.obj[0]}</b>。${V.obj[1]}`;narH=houseById(V.nar.house);
      const nf=narH?famAt(household(narH),Y):null;narN=V.nar.n;const by=`——${nf?nf.trade+'家的':''}${narN}说`;
      const beats=V.life.filter(b=>b[0]<=Y),cur=beats[beats.length-1];
      if(cur)vHTML=`<div class="story">${cur[1]}<div class="by">${by}</div></div>`;else vHTML=`<div class="story fut">${narN}还没搬来，这一家的事，过几年才有人讲。</div>`;
      vHTML+=`<details><summary>邻居讲的这一家</summary><div class="life">${V.life.map(([y,t])=>`<div class="${y>Y?'fut':''}"><span class="y">建城 ${y} 年</span>${y>Y?'……':t}</div>`).join('')}</div></details>`}
    const hk=gone||!al.length?'':csHook(hh,Y,al,head);
    const brief=gone?'这家人已经搬走了。':(al.length?`${al.length+csInHere(h,Y).length} 口人`:'屋里没人了。');
    showCard(`<h2>${al.length?nm:'空房子'}</h2><div class="meta">${F.trade} · ${F.origin==='本城生'?'本城生':'从'+F.origin+'来'}${zoneOf(h,Y)!=='homes'?' · 住在'+ZNAME[zoneOf(h,Y)]+'一带':''}</div>`
      +(vOn&&vHTML?vHTML.split('<details>')[0]:(today?`<div class="now">${today}</div>`:''))+(hk?`<div class="cshook">${hk}</div>`:'')+csTalkHTML(hh,Y)
      +`<details class="csmore"><summary>${brief} · 屋里有${vOn?V.obj[0]:hh.obj}</summary><div class="ppl">${ppl}</div><div class="meta">${F.faith} · 房子建于${h.built<1?'拜扎斯时代':'建城 '+h.built+' 年'}</div>${lifeHTML(hh.ev,Y)}</details>`);
    if(!gone&&al.length){
      const [wl]=nearestLM(h.cx,h.cy,l=>landType(l.id)===landType(nearestLM(h.cx,h.cy)[0].id)&&!(late[l.id]&&late[l.id].built>Y));if(wl)threads.push({x:wl.xy[0],y:wl.xy[1],t:'在'+wl.name+'一带干活：'+F.trade});
      const ch=F.faith==='阿里乌派'?LM.church_peace:F.faith==='尼西亚派'?(Y>=49?LM.church_anastasia:LM.church_megale):LM.fort_acropolis;
      if(F.faith==='阿里乌派'&&Y>=51){if(has('arian_meeting')&&Y>=52)threads.push({x:LM.arian_meeting.xy[0],y:LM.arian_meeting.xy[1],t:'节日出城祈祷'})}else if(ch!==FAR)threads.push({x:ch.xy[0],y:ch.xy[1],t:F.faith==='还拜旧神'?'偷偷去卫城的旧神庙':'做礼拜'});
      {const wl=has('cistern_founder')?LM.cistern_founder:(has('cistern_modestus')&&Y>=41?LM.cistern_modestus:null);if(wl)threads.push({x:wl.xy[0],y:wl.xy[1],t:'打水'})}
      if(vOn&&narH&&narH.built<=Y){threads.push({x:narH.cx,y:narH.cy,t:narN+'讲的这一家',go:narH.id})}
      {let k=0;for(const id in VOICES){const W2=VOICES[id];if(W2.nar.house!==h.id||k>=3)continue;const tg=houseById(+id);if(!tg||!(tg.built<=Y&&tg.destroyed>Y)||!W2.life.some(b=>b[0]<=Y))continue;const sp=al.find(p=>p.n===W2.nar.n);if(!sp)continue;threads.push({x:tg.cx,y:tg.cy,t:sp.n+'常说起这一家',go:tg.id});k++}}
      if(vOn&&V.ties)for(const [k,t,y0] of V.ties){if(Y<y0)continue;const tg=houseById(+k);if(tg&&tg.built<=Y&&tg.destroyed>Y)threads.push({x:tg.cx,y:tg.cy,t,go:tg.id})}
      for(const p of F.people)if(p.left&&p.left<=Y&&p.d>Y){if(typeof p.to==='number'){const t=houseById(p.to);if(t)threads.push({x:t.cx,y:t.cy,t:p.n+'嫁到了这里（'+(Y-p.b)+' 岁）',go:t.id})}}
      threads.sort((a,b)=>(b.go?1:0)-(a.go?1:0));threads=threads.slice(0,3);
      threads.forEach(t=>{t.fx=h.cx;t.fy=h.cy});
    }
  }else if(sel.kind==='named'){
    const P=sel.P;const age=Y-P.b;const L=lifeAt(P,Y);
    showCard(`<img class="portrait" src="${P.src}" alt=""><h2>${P.name}</h2><div class="meta">${P.meta}</div><div class="meta">建城 ${Y} 年 · ${age<0?'还没出生':age+' 岁'}</div><div class="quote">“${P.quote}”</div><div class="now">${L?L[1]:''}</div>${P===DAPH&&SCENE.id==='xero'&&Y>=29?'<div class="ppl">家里：父亲尼刻塔斯（运水人，'+(Y+3)+' 岁）、母亲伊琳娜（'+(Y-2)+' 岁）'+(Y>=37?'、弟弟米隆（'+(Y-37)+' 岁）':'')+'</div>':''}`+lifeHTML(P.life,Y)+`<div class="pin">◆ 已固定：拨动年代，看${P.key==='daph'?'她':'他'}老去</div>`);
    const w=P.where(Y);if(w){P.threads(Y).forEach(([x,y,t,link])=>threads.push({fx:w[0],fy:w[1],x,y,t,link}))}
  }else{
    const l=sel.l;let now=l.now[per]||l.now[per==='morning'||per==='day'?'day':'night']||'';
    if(l.id==='hippodrome'&&clock>=13&&clock<17)now=l.now.race+'。'+race.score;
    const built=late[l.id]?late[l.id].built:1;
    showCard(`<h2>${l.name}</h2><div class="meta">${Y<built?'建城 '+built+' 年才建成':'地标'}</div><div class="quote">${l.story}</div>`+(Y>=built?`<div class="now">此刻：${now}</div>`:''));
  }
  threadT=performance.now();
}


/* ---------- CS 线 · cs1：敲门问话（每一扇门都能问，答案只从底账推演的这一家里来） ---------- */
const CSQ=[['from','你们家从哪来？'],['work','靠什么过日子？'],['family','家里都有谁？'],['house','这房子以前住过谁？'],['city','这些年城里出过什么事？'],['faith','你们信哪一派？'],['nb','隔壁住的是谁？'],['talk','街坊怎么说你们？']];
function csSpeakers(al,Y){return al.filter(p=>Y-p.b>=7).sort((a,b)=>a.b-b.b)}
function csNeighbors(h,Y,k=3){return houses.filter(o=>o.id!==h.id&&o.built<=Y&&o.destroyed>Y).map(o=>[o,dist(h.cx,h.cy,o.cx,o.cy)]).sort((a,b)=>a[1]-b[1]).slice(0,k).filter(x=>{const hh=household(x[0]);return aliveAt(hh,Y).length>0})}
function csHeadOf(hh,Y){const al=aliveAt(hh,Y);const m=al.filter(p=>p.s==='m'&&!p.bride&&Y-p.b>=16).sort((a,b)=>a.b-b.b);return m[0]||al.slice().sort((a,b)=>a.b-b.b)[0]}
function csGo(id,label){return `<a class="csgo" data-go="${id}">${label}</a>`}
function csAnswer(hh,Y,q,sp){
  const h=hh.h,F=famAt(hh,Y),al=aliveAt(hh,Y),age=Y-sp.b,r=rng(hash('cs'+h.id+q+Y+sp.n));
  const kid=age<13,old=age>=60,I=kid?'我':'我';const head=csHeadOf(hh,Y);
  const myFam=sp.fam||F;const born=sp.b>=myFam.B;const bride=sp.bride;
  const here=Y-F.B;
  const tail=old?pick(r,['，老啦。','。那时候的事，我比谁都记得清。','。一晃这么多年。']):kid?pick(r,['。我妈说的。','。我爷爷讲过好多遍。','。']):'。';
  switch(q){
  case 'from':{
    if(F.origin==='本城生'){return born?`${I}就生在这栋房子里${kid?'':'，生在建城 '+sp.b+' 年'}。我们家是本城人，没从别处来过`+tail:(bride?(sp.married?`我是嫁进来的，建城 ${sp.married} 年。他们家是本城人，在这儿住了 ${here} 年了`:`我跟着当家的一起搬进来的。我们是本城人，在这儿住了 ${here} 年了`)+tail:`我们家是本城人，建城 ${F.B<1?'以前':F.B+' 年'}就住进了这栋房子`+tail)}
    const arr=hh.ev.find(e=>e[0]===F.B&&/搬|住进/.test(e[1]));const why=arr?arr[1].replace(/^[^。]*。/,'').replace(/他们/g,'我们'):'';const burnt=/大火/.test(why);
    if(born)return `${I}是在这儿生的。${sp.b-F.B>22?'家里老一辈':kid?'爸妈':'爹娘'}是从${F.origin}来的，建城 ${F.B} 年${why?'，'+why.replace(/。$/,''):''}。${kid?'我没去过'+F.origin+'。':'我只在他们嘴里见过'+F.origin+'。'}`;
    if(bride&&sp.married&&sp.married>F.B)return `我是嫁过来的，建城 ${sp.married} 年进的这个门。他们家早先从${F.origin}来，${why?why.replace(/。$/,''):'来了好些年了'}。`;
    return `从${F.origin}来的。建城 ${F.B} 年，${age-(Y-F.B)} 岁那年${why?'，'+why.replace(/。$/,''):''}。${burnt?'在这山上重新开始。':old?'那时候我还年轻，城墙还没这么长。':'刚来那几年，谁都不认识。'}`}
  case 'work':{
    const [lm]=nearestLM(h.cx,h.cy);
    if(kid)return `${F.trade==='运水人'?'爸爸挑水':'家里是'+F.trade}。${pick(r,['我帮着跑腿，送东西。','我还小，就在门口帮忙看摊。','等我长大，也干这个。'])}`;
    if(sp.s==='f'&&sp!==head)return `家里是${F.trade}，男人在${lm?lm.name+'那一带':'外头'}干活。我${pick(r,['纺线、做饭、挑水，一天到晚闲不住','管着账，谁欠了钱我都记在蜡板上','带孩子，空了给邻居缝补点东西'])}。`;
    return `${F.trade}。${lm?'活在'+lm.name+'一带，':''}${pick(r,['一年到头不得闲，够一家人吃饭。','好年景能攒几个铜子，坏年景就欠着。','粮船晚到一个月，日子就难过。'])}${old?'现在是儿孙们在干，我就坐着看。':''}`}
  case 'family':{
    const ppl=al.filter(p=>p!==sp).sort((a,b)=>a.b-b.b).map(p=>`${p.n}（${(sp===head?relLabel(p,head,al):(p===head?'当家的':'当家的'+relLabel(p,head,al)))}，${Y-p.b} 岁）`);
    const deadKids=myFam.people.filter(p=>p.d<=Y&&p.d-p.b<5&&p.b>=myFam.B);
    const out=myFam.people.filter(p=>p.left&&p.left<=Y&&p.d>Y);
    let s=ppl.length?`屋里还有：${ppl.join('、')}。`:'屋里就剩我一个了。';
    if(out.length)s+=out.map(p=>typeof p.to==='number'?(csIncoming(),csSpouse(p)?`${p.n}嫁给了${csGo(csSpouse(p).hid,csSpouse(p).hus.n)}`:`${p.n}嫁到了别的街区`):p.to==='外城'?`${p.n}嫁到了城外`:`${p.n}走了，`+(p.s==='m'?'在外头':'')).slice(0,2).join('；')+'。';
    if(deadKids.length&&!kid)s+=`${deadKids.length===1?'还有一个孩子，'+deadKids[0].n+'，没养住':'有 '+deadKids.length+' 个孩子没养住'}。${pick(r,['不说了。','这条坡上谁家不是这样。','我到现在还记得'+deadKids[deadKids.length-1].n+'的样子。'])}`;
    return s}
  case 'house':{
    const fi=hh.fams.indexOf(F);
    let s=h.built<1?'这房子比城还老，拜扎斯那会儿就有了。':`这房子是建城 ${h.built} 年盖的。`;
    if(fi>0){const p=hh.fams[fi-1];const ph=p.people.find(x=>x.g===0&&x.s==='m');s+=`我们之前住的是${ph?ph.n+'一家':'另一户人家'}，${p.origin==='本城生'?'本城人':'从'+p.origin+'来的'}，干${p.trade}。他们走了以后，房子空了一阵。`}
    else s+=`${F.B<=h.built+1?'盖好就是我们家住着，没换过人。':'我们是头一家。'}`;
    if(h.destroyed<=MAXY&&h.destroyed>Y&&old)s+='听说这一片以后要拆，谁知道呢。';
    return s}
  case 'city':{
    const seen=CITYEV.filter(e=>e[0]<=Y);if(!seen.length)return '城还小，没出过什么大事。';
    const inCity=F.origin==='本城生'||hh.ev.some(e=>e[0]===F.B&&/大火|城里另一头/.test(e[1]));const t0=inCity?sp.b+5:Math.max(F.B,sp.b+5);const lived=seen.filter(e=>e[0]>=t0);const before=seen.filter(e=>e[0]<t0);
    const mine=hh.ev.filter(e=>e[0]<=Y&&CITYEV.some(c=>c[0]===e[0]&&c[1]===e[1]));
    let s='';
    if(lived.length){const e=mine.length?mine[mine.length-1]:lived[lived.length-1];s+=`建城 ${e[0]} 年，${e[1].replace(/^全家/,'我们全家').replace(/^从/,'我们从')}。`;const e2=lived.find(x=>x!==e&&x[0]!==e[0]);if(e2&&!kid)s+=`还有第 ${e2[0]} 年，${e2[1]}。`}
    const lb=before[before.length-1];const pre=lb&&lb[0]>=F.B?(sp.b>lb[0]?'那会儿我还没出生，':'那会儿我还小，')+'是听大人讲的。':`是在我们${F.origin==='本城生'?'家搬进来':'来'}以前，${pick(r,['听街坊说的。','我没赶上。'])}`;
    if(before.length&&!lived.length)s+=`${lb[1].replace(/^全家/,'').replace(/^他们/,'')}的事，${pre}`;
    else if(before.length)s+=`再早的${before.length>1?'大火、水渠那些':'事'}，${pick(r,['我没赶上，是听老人讲的。','那会儿我们还没来。'])}`;
    return s||'这些年还算太平。'}
  case 'faith':{
    const f=F.faith;
    if(f==='阿里乌派')return Y>=51?`阿里乌派。${pick(r,['现在城里的教堂不让我们进了，过节得走出城门去祈祷。','皇帝换了，风向也换了。我们出城去做礼拜，不吵不闹。'])}`:`阿里乌派，跟皇帝一样。${pick(r,['和平教堂离得不远。','礼拜天去和平教堂。'])}`;
    if(f==='尼西亚派')return Y>=51?`尼西亚派。${pick(r,['这几年总算轮到我们了。','新皇帝站在我们这边。'])}`:Y>=49?'尼西亚派。阿纳斯塔西娅那间小屋子，挤得都站不下。':'尼西亚派。城里阿里乌派当家，我们小声点就是了。';
    return `${kid?'我不知道。':pick(r,['你别往外说。','在家里拜拜老神，出门就画个十字。'])}${kid?'奶奶在墙角供着一个小神像。':'我们家还拜旧神。卫城上那座老庙，我年轻时还进去过。'}`}
  case 'nb':{
    const nb=csNeighbors(h,Y);if(!nb.length)return '这一片还没几户人家。';
    return '挨着住的：'+nb.map(([o])=>{const hh2=household(o);const F2=famAt(hh2,Y);const hd=csHeadOf(hh2,Y);return csGo(o.id,(hd?hd.n+'家':'一户人家'))+`，${F2.trade}，${F2.origin==='本城生'?'本城人':F2.origin+'来的'}`}).join('；')+`。${pick(r,['你去敲敲看。','去问问他们，他们知道的比我多。','替我问声好。'])}`}
  case 'talk':{
    const V=VOICES[h.id];
    if(V&&V.fam===F.B){const nh=houseById(V.nar.house);const b=V.life.filter(x=>x[0]<=Y).pop();if(b)return `${nh?csGo(nh.id,V.nar.n):V.nar.n}最爱讲我们家：“${b[1]}”${pick(r,['她那张嘴。','也就她记得这么清楚。','说得倒也没错。'])}`}
    for(const id in VOICES){const W=VOICES[id];if(W.nar.house===h.id&&al.some(p=>p.n===W.nar.n)){const tg=houseById(+id);const b=W.life.filter(x=>x[0]<=Y).pop();if(tg&&b&&tg.built<=Y&&tg.destroyed>Y){const who=al.find(p=>p.n===W.nar.n);return `${who===sp?'我':who.n}倒是常说起${csGo(tg.id,'那一家')}：“${b[1]}”`}}}
    const nb=csNeighbors(h,Y,1)[0];if(nb){const hd=csHeadOf(household(nb[0]),Y);return `${hd?csGo(nb[0].id,hd.n):'隔壁'}${pick(r,['说我们家门口总是吵。','说我们家的狗半夜叫。','说我们欠了他半袋面粉。其实早还了。'])}`}
    return '这一片人少，没人说闲话。'}
  }
  return ''}
const CSORD=['talk','house','nb','from','work','family','city','faith'];
function csTalkHTML(hh,Y){
  const al=aliveAt(hh,Y);if(!al.length||Y>=hh.h.destroyed)return '';
  const sps=csSpeakers(al,Y);if(!sps.length)return '';
  if(!sel.cs||sel.cs.id!==hh.h.id)sel.cs={id:hh.h.id,n:-1};
  const st=sel.cs;if(st.n<0)return `<div class="cstalk"><a class="csq" data-q="next">敲门</a></div>`;
  const off=hh.h.id%CSORD.length,q=CSORD[(off+st.n)%CSORD.length],sp=sps[(hh.h.id+st.n)%sps.length];
  return `<div class="cstalk"><div class="csans"><b>${sp.n}（${Y-sp.b} 岁）：</b>${csAnswer(hh,Y,q,sp)}</div><a class="csq" data-q="next">再问一句</a></div>`}
function csHook(hh,Y,al,head){
  const L=csInHere(hh.h,Y).sort((a,b)=>b.p.left-a.p.left);
  if(L.length&&Y-L[0].p.left<=8){const {x,p:q,hh:o}=L[0];const fh=csHeadOf(o,q.left);const d=Y-q.left;return `<a class="csgo" data-pf="${x.from}:${x.pi}">${q.n}</a>是${d===0?'今年':d+' 年前'}从${fh?fh.n+'家':'别家'}嫁过来的。`}
  const ev=hh.ev.filter(e=>e[0]<=Y&&e[0]>=Y-3).pop();
  if(ev){const p=hh.people.find(p=>ev[1].includes(p.n));const t=ev[1];return (Y-ev[0]===0?'今年，':(Y-ev[0])+' 年前，')+(p?t.replace(p.n,`<a class="csgo" data-p="${hh.people.indexOf(p)}">${p.n}</a>`):t)+'。'}
  const out=hh.people.find(p=>p.s==='f'&&p.left&&p.left<=Y&&p.d>Y&&typeof p.to==='number'&&(csIncoming(),csSpouse(p)));
  if(out){const sp=csSpouse(out);return `这家的女儿<a class="csgo" data-p="${hh.people.indexOf(out)}">${out.n}</a>嫁给了${csGo(sp.hid,famAt(sp.hh,Y).trade+'家')}的${sp.hus.n}。`}
  const old=al.slice().sort((a,b)=>a.b-b.b)[0];const since=Math.max(old.b,old.fam.B,old.married||-99,hh.h.built);
  return `<a class="csgo" data-p="${hh.people.indexOf(old)}">${old.n}</a>${Y-old.b>=50?'已经 '+(Y-old.b)+' 岁了，':''}在这屋里住了 ${Math.max(1,Y-since)} 年。`}

/* ---------- CS 线 · cs2：跟着一个人走完一生（嫁到哪家，就跟到哪家；那一家的门里也能看见她） ---------- */
let CSIN=null;const CSHUS=new Map();const CSSP=new Map();
function csSpouse(p){if(CSSP.has(p))return CSSP.get(p);let res=null;const wy=p.left,ag=wy-p.b;const taken=csTaken();
  const tg=houseById(p.to);if(tg){const cands=[tg].concat(csNear(tg).filter(o=>o!==tg&&o.built<=wy&&o.destroyed>wy).sort((a,b)=>dist(a.cx,a.cy,tg.cx,tg.cy)-dist(b.cx,b.cy,tg.cx,tg.cy)).slice(0,8));
    for(const o of cands){if(o.built>wy||o.destroyed<=wy)continue;const hh=household(o);const m=hh.people.find(q=>q.s==='m'&&!q.bride&&q.g>0&&q.b<=wy-ag&&wy-q.b<=ag+15&&wy-q.b>=17&&q.d>wy+1&&!(q.left&&q.left<=wy)&&!csGrooms(hh).has(q.n)&&!hh.people.some(x=>x.n===p.n)&&!taken.has(q));if(m){taken.add(m);res={hid:o.id,hus:m,hh};break}}}
  CSSP.set(p,res);return res}
let CSG=null;function csNear(tg){if(!CSG){CSG=new Map();for(const o of houses){const k=Math.floor(o.cx/70)+','+Math.floor(o.cy/70);if(!CSG.has(k))CSG.set(k,[]);CSG.get(k).push(o)}}const gx=Math.floor(tg.cx/70),gy=Math.floor(tg.cy/70),r=[];for(let i=-1;i<=1;i++)for(let j=-1;j<=1;j++){const L=CSG.get((gx+i)+','+(gy+j));if(L)r.push(...L)}return r}
const CSGR=new WeakMap();function csGrooms(hh){let g=CSGR.get(hh);if(!g){g=new Set();for(const e of hh.ev){const i=e[1].indexOf('娶了');if(i>0)g.add(e[1].slice(0,i))}CSGR.set(hh,g)}return g}
let CSTK=null;function csTaken(){return CSTK||(CSTK=new Set())}
let CSST=null;function csIncoming(){csIncStep(1e9);return CSIN}
function csIncStep(ms){if(CSIN&&!CSST)return true;const t0=performance.now();if(!CSST){CSIN={};CSST={all:[],hi:0,i:0,sorted:false}}const S=CSST;
  while(S.hi<houses.length){const o=houses[S.hi++];if(o.built>MAXY)continue;const hh=household(o);hh.people.forEach((p,i)=>{if(typeof p.to==='number')S.all.push([o,p,i])});if(performance.now()-t0>ms)return false}
  if(!S.sorted){S.all.sort((a,b)=>a[1].left-b[1].left);S.sorted=true}
  while(S.i<S.all.length){const [o,p,i]=S.all[S.i++];const sp=csSpouse(p);if(sp){(CSIN[sp.hid]=CSIN[sp.hid]||[]).push({from:o.id,pi:i});CSHUS.set(sp.hus,{p,from:o})}if(performance.now()-t0>ms)return false}
  CSST=null;return true}
function csInHere(h,Y){const L=(csIncoming()[h.id]||[]);return L.map(x=>{const hh=household(houseById(x.from));return {x,p:hh.people[x.pi],hh}}).filter(({p})=>p.left<=Y&&p.d>Y&&h.destroyed>Y)}
const AWAY_LM={'当了兵':'barracks_gate','码头':'gate_founder','石匠':'aqb_valley','修道院':'gate_founder','出了海':'gate_founder'};
function csBeats(hh,p){
  const h=hh.h,F=p.fam,B=[];const mine=hh.ev.filter(e=>e[1].includes(p.n));
  const age=y=>y-p.b;
  if(p.b>=F.B)B.push([p.b,`${p.n}生在这栋房子里`+(F.origin==='本城生'?'。':`，一家人是从${F.origin}来的。`),h.id]);
  else if(p.bride&&p.married)B.push([p.married,`${p.n}嫁进这栋房子，${age(p.married)} 岁。`,h.id]);
  else B.push([Math.max(1,F.B),`${p.n} ${age(Math.max(1,F.B))} 岁，`+(F.origin==='本城生'?'一家人搬进这栋房子。':`跟着一家人从${F.origin}来，住进这栋房子。`),h.id]);
  for(const [cy,t] of CITYEV.filter(c=>hh.ev.some(e=>e[0]===c[0]&&e[1]===c[1]))){if(cy>Math.max(p.b,F.B,p.married||-999)&&cy<p.d&&!(p.left&&cy>p.left)&&cy<=MAXY&&age(cy)>=4){B.push([cy,`建城 ${cy} 年，${p.n} ${age(cy)} 岁。`+t.replace(/^全家/,'全家').replace(/^他们/,'一家人')+'。',h.id])}}
  if(p.left&&p.left<=MAXY&&!mine.some(e=>e[0]===p.left))mine.push([p.left,p.n+(p.s==='f'?'出嫁':'离家')]);
  for(const [y,t] of mine){if(y===p.b||y===p.d||(p.married&&y===p.married))continue;
    if(p.left&&y===p.left&&p.s==='f'){csIncoming();const sp=typeof p.to==='number'?csSpouse(p):null;if(sp){const thh=sp.hh;B.push([y,`${age(y)} 岁，${p.n}出嫁，嫁给了${famAt(thh,y).trade}家的${sp.hus.n}（${y-sp.hus.b} 岁）。从此那栋房子就是她的家。`,sp.hid])}else B.push([y,`${age(y)} 岁，${p.n}出嫁，嫁到了${p.to==='外城'?'城外':'别的街区'}。这一角再也找不到她的门了。`,h.id]);continue}
    if(p.left&&y===p.left){if(typeof p.to==='number'){const tg=houseById(p.to);const thh=tg?household(tg):null;const hd=thh?csHeadOf(thh,y):null;B.push([y,`${age(y)} 岁，${p.n}出嫁，嫁进了${hd?hd.n+'家':'另一户人家'}${thh?'（'+famAt(thh,y).trade+'）':''}。从此那栋房子就是她的家。`,p.to])}
      else if(p.to==='外城')B.push([y,`${age(y)} 岁，${p.n}出嫁，嫁到了城外。这座城里再也找不到她的门了。`,h.id]);
      else{const k=Object.keys(AWAY_LM).find(k=>t.includes(k));const lm=k&&LM[AWAY_LM[k]];B.push([y,`${age(y)} 岁，${t.replace(p.n,p.n)}。`,lm?'lm:'+AWAY_LM[k]:h.id])}continue}
    B.push([y,t.replace(/^/,`${p.n} ${age(y)} 岁那年，`).replace(p.n+' '+age(y)+' 岁那年，'+p.n,p.n+' '+age(y)+' 岁')+'。',h.id])}
  const parent=p.bride||hh.ev.some(e=>e[1].startsWith(p.n+'娶了'))||(p.g===0&&p.b<F.B);
  if(parent){const ks=F.people.filter(k=>k.g===p.g+1&&!k.bride&&k.b>p.b+14&&k.b<p.d);for(const k of ks){const life=k.d-k.b;B.push([k.b,`${p.n} ${age(k.b)} 岁，${p.s==='m'?'添了':'生下了'}${k.s==='m'?'儿子':'女儿'}${k.n}`+(life<5?`。孩子${life<1?'没满一岁':'活到 '+life+' 岁'}就没了。`:'。'),h.id])}}
  if(p.s==='m'){csIncoming();const w2=CSHUS.get(p);if(w2){const fh=csHeadOf(household(w2.from),w2.p.left);B.push([w2.p.left,`${p.n} ${age(w2.p.left)} 岁，娶了${fh?fh.n+'家的':''}${w2.p.n}（${w2.p.left-w2.p.b} 岁）。`+(w2.p.d<=MAXY&&w2.p.d<p.d?`她活到 ${w2.p.d-w2.p.b} 岁。`:''),h.id])}}
  const spx=p.left&&p.s==='f'&&typeof p.to==='number'?csSpouse(p):null;const home=spx?spx.hid:h.id;
  if(p.d<=MAXY){const life=p.d-p.b;B.push([p.d,life<5?`${p.n}${life<1?'没满一岁':'才 '+life+' 岁'}就走了。`:`${p.n}去世，${life} 岁。`+(spx?'死在她嫁过去的那栋房子里。':''),home])}
  else B.push([MAXY,`建城 ${MAXY} 年，${p.n} ${age(MAXY)} 岁，还活着。往后的事，底账还没写到。`,home]);
  B.sort((a,b)=>a[0]-b[0]);
  return B.filter(b=>b[0]>=1||b===B[0]).map(b=>[Math.max(1,Math.min(MAXY,b[0])),b[1],b[2]])}
function csPlace(where){if(typeof where==='string'&&where.startsWith('lm:')){const l=LM[where.slice(3)];return l?[l.xy[0],l.xy[1]]:null}const t=houseById(where);return t?[t.cx,t.cy]:null}
function csPersonCard(Y){
  const st=sel;const h=houseById(st.hid);const hh=household(h);const p=hh.people[st.pi];
  if(!st.beats)st.beats=csBeats(hh,p);const B=st.beats;
  if(st.step<0){let k=0;B.forEach((b,i)=>{if(b[0]<=Y)k=i});st.step=k}
  const cur=B[st.step];const age=Y-p.b;
  const status=Y<p.b?'还没出生':Y>=p.d?`已经不在了（${p.d-p.b} 岁去世）`:`${age} 岁`+(p.left&&p.left<=Y?(typeof p.to==='number'?'，嫁出去了':p.to==='外城'?'，在城外':'，不在家'):'');
  const hd=csHeadOf(hh,Math.min(Y,p.d-1));
  showCard(`<h2>${p.n}</h2><div class="meta">${csGo(h.id,(hd?hd.n:'')+'家')}的人 · ${status}</div>`
   +`<div class="story">${cur[1]}</div>`
   +`<div class="csstep">${st.step>0?`<a class="csq" data-step="${st.step-1}">‹ 之前</a>`:'<span></span>'}${st.step<B.length-1?`<a class="csq" data-step="${st.step+1}">后来呢 ›</a>`:'<span></span>'}</div>`
   );
  const pl=csPlace(cur[2]);if(pl&&cur[2]!==h.id){threads.push({fx:h.cx,fy:h.cy,x:pl[0],y:pl[1],t:p.n+(typeof cur[2]==='number'?'嫁到了这里':'去了这里'),go:typeof cur[2]==='number'?cur[2]:undefined})}
}
function csGoStep(i){const B=sel.beats;i=Math.max(0,Math.min(B.length-1,i));sel.step=i;const b=B[i];const pl=csPlace(b[2]);if(b[0]!==YEAR){$('yr').value=b[0];setYear(b[0])}else renderCard();if(pl)flyTo(pl[0],pl[1],Math.max(cam.z,1.5),1200);blip(600+i*20,.05)}

function openHouse(id){const h=houseById(id);if(!h)return null;sel={kind:'house',hh:household(h)};renderCard();return h}
function closeCard(){sel=null;threads=[]}
function cardClick(t){if(!sel)return;
  if(t.dataset.p!==undefined&&sel.kind==='house'){sel={kind:'person',hid:sel.hh.h.id,pi:+t.dataset.p,step:-1};renderCard();return}
  if(t.dataset.pf){const [hid,pi]=t.dataset.pf.split(':').map(Number);sel={kind:'person',hid,pi,step:-1};renderCard();return}
  if(t.dataset.step!==undefined&&sel.kind==='person'){csGoStep(+t.dataset.step);return}
  if(t.dataset.go&&sel.kind!=='house'){const id=+t.dataset.go;const tg=houseById(id);if(tg){openHouse(id);flyTo(tg.cx,tg.cy,Math.max(env.cam.z,1.6))}return}
  if(sel.kind!=='house')return;
  if(t.dataset.go){const id=+t.dataset.go;const tg=houseById(id);if(tg){openHouse(id);flyTo(tg.cx,tg.cy,Math.max(env.cam.z,1.6))}return}
  if(t.dataset.q==='next'&&sel.cs){sel.cs.n++}renderCard()}
const WG={};function warmCrowd(ms){if(!FLEET||!FLEET.crowdGen||YEAR<FLEET.C.from||FLEET.cache[YEAR])return true;const g=WG[YEAR]||(WG[YEAR]=FLEET.crowdGen(YEAR)),t0=performance.now();for(;;){const s=g.next();if(s.done)return true;if(performance.now()-t0>ms)return false}}
FLEET&&(FLEET.dockDraw=function(){});   /* 码头逐年长的遮盖：瓦片页的烤图已经按年画好 */
return {houses,houseById,city,SCENE,household,famAt,aliveAt,nearestHouse,openHouse,closeCard,cardClick,renderCard,csIncoming,csIncStep,warmCrowd,get sel(){return sel},periodOf,
  get FLEET(){return FLEET},get YEAR(){return YEAR},set YEAR(v){YEAR=v},get clock(){return clock},set clock(v){clock=v},get dayIdx(){return dayIdx},set dayIdx(v){dayIdx=v},
  FW:W,FH:H,hash,rng};
};
