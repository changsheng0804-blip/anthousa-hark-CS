/* CS 线 · tile_heart.py 生成，勿手改 */
(window.__HEART=window.__HEART||{}).nangang=function(env){"use strict";
/* 以下五段取自 docs/living/nangang/index.html，一字不改（tile_heart.py 生成）。——Hark（CS线） */
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
  FLEET.crowd=function(Y){if(FLEET.cache[Y])return FLEET.cache[Y];const r=rng(hash('fleet'+Y));const out=[];
    const hs=houses.filter(h=>ok(h,Y)&&dQ(h.cx,h.cy)<C.reach).sort((a,b)=>dQ(a.cx,a.cy)-dQ(b.cx,b.cy));
    for(const h of hs){const hh=household(h);const F=famAt(hh,Y);const al=aliveAt(hh,Y);if(!al.length)continue;
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
        let moved=false;for(const m of pool){const t=[s[0]+(r()-.5)*6,s[1]+(r()-.5)*4];const e=m.spot;const RR=WK.R,gw=Math.ceil(W/RR),key=(a,b)=>b*gw+a;const sa=Math.floor(e[0]/RR),sb=Math.floor(e[1]/RR),ta=Math.floor(t[0]/RR),tb=Math.floor(t[1]/RR);
          const prev=new Map([[key(sa,sb),-1]]);const Q2=[[sa,sb]];let found=false;for(let qi=0;qi<Q2.length&&!found&&qi<40000;qi++){const[a,b]=Q2[qi];for(const[da,db]of[[1,0],[-1,0],[0,1],[0,-1],[1,1],[1,-1],[-1,1],[-1,-1]]){const na=a+da,nb=b+db;if(na<0||nb<0||prev.has(key(na,nb)))continue;if(!FLEET_walkable((na+.5)*RR,(nb+.5)*RR))continue;prev.set(key(na,nb),key(a,b));Q2.push([na,nb]);if(na===ta&&nb===tb){found=true;break}}}
          if(found){const seg=[];let k=key(ta,tb);while(k>=0){seg.push([(k%gw+.5)*RR,(Math.floor(k/gw)+.5)*RR]);k=prev.get(k)}seg.reverse();m.path=m.path.concat(seg,[t]);m.spot=t;m.pier=s;moved=true;break}}
        if(!moved)break}}}
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


FLEET&&(FLEET.dockDraw=function(){});   /* 码头逐年长的遮盖：瓦片页的烤图已经按年画好 */
return {houses,city,SCENE,household,famAt,aliveAt,
  get FLEET(){return FLEET},get YEAR(){return YEAR},set YEAR(v){YEAR=v},get clock(){return clock},set clock(v){clock=v},get dayIdx(){return dayIdx},set dayIdx(v){dayIdx=v},
  FW:W,FH:H,hash,rng};
};
