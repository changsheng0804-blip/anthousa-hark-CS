/* ---------- CS 线 · cs5 粮脉 ----------
   一条「脉」= 一条在底账上跑的规则，不是手写的故事。
   粮：港（底账）→ 粮仓（底账）→ 面包房（这一年住着面包师一家的房子，和敲门卡同一份推演）→ 发面包的台阶（按当年站着的房子聚出来）→ 每一户。
   48 年大火（底账里烧掉的 287 栋）烧掉的面包房当年就没了，台阶改去更远的面包房；粮仓到面包房的路穿过火场的，要绕。
   打开粮脉时，其余的东西一律压暗、拿掉：只留这一条脉。 */
const VEIN={on:false,sel:null,steps:[],cache:{}};
(function(){
  const BAKE='面包师';
  const ok=(h,Y)=>h.built<=Y&&h.destroyed>Y;
  const SRC=[['harbor_theodosius',33],['harbor_julian',1]].filter(([k])=>has(k));
  const GRA=[['horrea_theodosius',34],['horrea_alexandrina',55]].filter(([k])=>has(k));
  const burned=houses.filter(h=>h.destroyed===48);
  // 台阶：用建城 60 年站着的房子做 k 均值（固定种子），每 400 户左右一处；位置固定，哪一年周围房子够多才开
  (function(){const P=houses.filter(h=>ok(h,60));const K=Math.max(4,Math.round(P.length/400));const r=rng(hash('gradus'));
    let C=[];for(let k=0;k<K;k++){const h=P[Math.floor(r()*P.length)];C.push([h.cx,h.cy])}
    for(let it=0;it<12;it++){const S=C.map(()=>[0,0,0]);for(const h of P){let b=0,bd=1e18;for(let k=0;k<K;k++){const d=(h.cx-C[k][0])**2+(h.cy-C[k][1])**2;if(d<bd){bd=d;b=k}}S[b][0]+=h.cx;S[b][1]+=h.cy;S[b][2]++}C=S.map((s,k)=>s[2]?[s[0]/s[2],s[1]/s[2]]:C[k])}
    C.sort((a,b)=>a[1]-b[1]||a[0]-b[0]);VEIN.steps=C.map((c,i)=>({i,x:c[0],y:c[1]}))})();
  const crosses=(a,b,Y)=>{if(Y<48||Y>=55)return false;for(let k=1;k<12;k++){const x=a[0]+(b[0]-a[0])*k/12,y=a[1]+(b[1]-a[1])*k/12;for(const h of burned)if((h.cx-x)**2+(h.cy-y)**2<400)return true}return false};
  VEIN.at=function(Y){if(VEIN.cache[Y])return VEIN.cache[Y];
    const src=SRC.filter(s=>Y>=s[1]).map(([k])=>({id:k,name:LM[k].name,x:LM[k].xy[0],y:LM[k].xy[1]}));
    const gra=GRA.filter(g=>Y>=g[1]).map(([k])=>({id:k,name:LM[k].name,x:LM[k].xy[0],y:LM[k].xy[1]}));
    const bak=houses.filter(h=>ok(h,Y)&&famAt(household(h),Y).trade===BAKE).map(h=>({h,x:h.cx,y:h.cy}));
    const live=houses.filter(h=>ok(h,Y));
    const near=(L,x,y)=>{let b=null,bd=1e18;for(const q of L){const d=(q.x-x)**2+(q.y-y)**2;if(d<bd){bd=d;b=q}}return[b,Math.sqrt(bd)]};
    const st=[];for(const s of VEIN.steps){const n=live.filter(h=>(h.cx-s.x)**2+(h.cy-s.y)**2<160*160).length;if(n<25)continue;
      const[b,bd]=near(bak,s.x,s.y);if(!b)continue;st.push({...s,n,b,bd})}
    const used=[...new Set(st.map(s=>s.b))];
    for(const b of used){const[g]=near(gra.length?gra:src,b.x,b.y);b.g=g;b.detour=g?crosses([g.x,g.y],[b.x,b.y],Y):false}
    for(const g of gra){const[s]=near(src,g.x,g.y);g.s=s}
    // 去年的面包房今年还在不在：48 年那场火
    const prev=Y>1?VEIN.at0(Y-1):null;
    for(const s of st){const pb=prev&&prev[s.i];s.lost=pb&&pb.destroyed===Y&&pb.id!==s.b.h.id?pb:null}
    const R={Y,src,gra,bak:used,steps:st,houses:live.length};VEIN.cache[Y]=R;return R};
  // 只算「每处台阶去年用的是哪家面包房」，不递归
  VEIN.at0=function(Y){const bak=houses.filter(h=>ok(h,Y)&&famAt(household(h),Y).trade===BAKE);const o={};
    for(const s of VEIN.steps){let b=null,bd=1e18;for(const h of bak){const d=(h.cx-s.x)**2+(h.cy-s.y)**2;if(d<bd){bd=d;b=h}}o[s.i]=b}return o};
  VEIN.stepOf=function(h,R){let b=null,bd=1e18;for(const s of R.steps){const d=(h.cx-s.x)**2+(h.cy-s.y)**2;if(d<bd){bd=d;b=s}}return b?{s:b,d:Math.sqrt(bd)}:null};
  const mins=d=>Math.max(1,Math.round(d/14*60/80));   // 页面 14 像素≈1 世界单位≈10 米上下，人走 80 米/分
  VEIN.mins=mins;
})();
function veinBread(h,Y){ // 这一户这一年的面包：给普通敲门卡也用，保证全城说的是同一件事
  if(Y<33)return null;const R=VEIN.at(Y);const q=VEIN.stepOf(h,R);if(!q)return null;
  const {s,d}=q;const b=s.b;const fam=famAt(household(b.h),Y);const bh=(aliveAt(household(b.h),Y).filter(p=>p.s==='m'&&Y-p.b>=16).sort((a,c)=>a.b-c.b)[0]||{n:''}).n;
  return {s,d,b,bh,lost:s.lost,detour:b.detour,g:b.g}}
function veinCard(h){const Y=YEAR;VEIN.sel=h;const per=periodOf(clock);
  const hh=household(h);const al=aliveAt(hh,Y);const head=(al.filter(p=>p.s==='m'&&!p.bride&&Y-p.b>=16).sort((a,b)=>a.b-b.b)[0]||al[0]);
  const nm=head?head.n+'家':'这一家';
  if(Y<33){showCard(`<h2>${nm}</h2><div class="now">建城 ${Y} 年，狄奥多西港还没挖出来。这一带吃的面包，是从城北的老港一车车拉过来的。</div><div class="meta">把年代拨到 33 以后，看这条脉怎么长出来。</div>`);return}
  const v=veinBread(h,Y);if(!v||!al.length){showCard(`<h2>${al.length?nm:'空房子'}</h2><div class="now">这里没有人领面包。</div>`);return}
  const L=[];
  L.push(`<div><span class="y">船</span>埃及的麦子装上粮船，进了<b>${v.g&&v.g.s?v.g.s.name:(v.g?v.g.name:'港口')}</b></div>`);
  if(v.g&&v.g.id.startsWith('horrea'))L.push(`<div><span class="y">仓</span>卸进<b>${v.g.name}</b></div>`);
  L.push(`<div><span class="y">炉</span><b>${v.bh?v.bh+'家的':''}面包房</b>${v.detour?'——粮车要绕开火场走':''}</div>`);
  L.push(`<div><span class="y">阶</span>第 ${v.s.i+1} 处发面包的台阶，${v.s.n.toLocaleString()} 户在这里领</div>`);
  L.push(`<div><span class="y">家</span>${nm}，走过去约 ${VEIN.mins(v.d)} 分钟</div>`);
  let now;
  if(v.lost){const lf=famAt(household(v.lost),Y-1);now=`今年南港那场火，把原来烤面包的那家烧没了。台阶上的面包改从${v.bh?v.bh+'家':'更远的一家'}送来，${per==='morning'?'天不亮就排起了长队':'今天又有人没领到'}。`}
  else if(v.detour)now=`火场还没清干净，粮车得绕着走，面包常常晚到。`;
  else now=per==='morning'?`${head?head.n:'家里的人'}正排在台阶上等今天的面包。`:per==='night'?`面包房里已经在和明天的面了。`:`今天的面包领回来了。`;
  showCard(`<h2>${nm}的面包</h2><div class="meta">粮脉 · 建城 ${Y} 年</div><div class="now">${now}</div><div class="life">${L.join('')}</div><div class="pin">拨动年代，看这条脉在哪一年断、在哪一年接上</div>`)}
function veinToggle(on){VEIN.on=on;VEIN.sel=null;closeCard();$('vein').classList.toggle('on',on);
  $('ticker').style.opacity=on?0:1;['daph','other','next'].forEach(k=>{const e=$(k);if(e)e.style.visibility=on?'hidden':''});
  if(on){flyTo(W/2,H/2,minZ()*1.05,1200);veinStat()}else setYear.call(null,YEAR)}
function veinStat(){if(!VEIN.on)return;const Y=YEAR;
  if(Y<33){$('ystat').textContent=`粮脉 · 建城 ${Y} 年：狄奥多西港还没有`;return}
  const R=VEIN.at(Y);const lost=R.steps.filter(s=>s.lost).length,det=R.bak.filter(b=>b.detour).length;
  $('ystat').textContent=`粮脉 · ${R.gra.length?R.gra.map(g=>g.name).join('、'):'港口直送'} → ${R.bak.length} 家面包房 → ${R.steps.length} 处台阶 → ${R.houses.toLocaleString()} 户`+(lost?` · 今年 ${lost} 处台阶断了供`:'')+(det&&!lost?` · ${det} 条粮路绕开火场`:'')}
function veinDraw(t){if(!VEIN.on)return;const Y=YEAR;
  ctx.fillStyle='rgba(12,9,6,.74)';ctx.fillRect(-50,-50,W+100,H+100);   // 减法：整座城压暗
  if(Y<33)return;const R=VEIN.at(Y);const z=cam.z;const per=periodOf(clock);
  const sel=VEIN.sel?veinBread(VEIN.sel,Y):null;
  const curve=(a,b,bend)=>{const mx=(a.x+b.x)/2,my=(a.y+b.y)/2,dx=b.x-a.x,dy=b.y-a.y;return[mx-dy*bend,my+dx*bend]};
  const path=(a,b,bend,col,w,dash)=>{const[cx,cy]=curve(a,b,bend);ctx.strokeStyle=col;ctx.lineWidth=w/z;ctx.setLineDash(dash?dash.map(v=>v/z):[]);ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.quadraticCurveTo(cx,cy,b.x,b.y);ctx.stroke();ctx.setLineDash([])};
  const dot=(a,b,bend,u,col,r)=>{const[cx,cy]=curve(a,b,bend);const x=(1-u)*(1-u)*a.x+2*(1-u)*u*cx+u*u*b.x,y=(1-u)*(1-u)*a.y+2*(1-u)*u*cy+u*u*b.y;ctx.fillStyle=col;ctx.beginPath();ctx.arc(x,y,r/z,0,7);ctx.fill()};
  const GOLD='rgba(240,196,98,', RED='rgba(226,82,58,';
  const dim=a=>sel?a*.25:a;
  // 港 → 仓
  for(const g of R.gra)if(g.s){const on=sel&&sel.g===g;path(g.s,g,.12,GOLD+(on?.95:dim(.7))+')',on?5:3.5);for(let k=0;k<4;k++)dot(g.s,g,.12,(t*.05+k/4)%1,GOLD+'1)',3)}
  // 仓 → 面包房
  for(const b of R.bak){const g=b.g;if(!g)continue;const on=sel&&sel.b===b;const col=b.detour?RED:GOLD;path(g,b,b.detour?.35:.08,col+(on?.95:dim(.55))+')',on?3.5:2,b.detour?[6,5]:null);dot(g,b,b.detour?.35:.08,(t*.08+b.h.id%7/7)%1,col+'1)',2.2)}
  // 面包房 → 台阶
  for(const s of R.steps){const on=sel&&sel.s===s;const col=s.lost?RED:GOLD;path(s.b,s,.05,col+(on?1:dim(.8))+')',on?3:1.8,s.lost?[4,4]:null);if(per==='morning'||per==='day')dot(s.b,s,.05,(t*.12+s.i/9)%1,'rgba(255,236,190,1)',2)}
  // 早上：台阶向周围的房子发面包
  if(per==='morning'){for(const s of R.steps){if(sel&&sel.s!==s)continue;const r=rng(hash('d'+s.i));for(let k=0;k<26;k++){const a=r()*6.283,rr=30+r()*130,u=(t*.18+r())%1;ctx.fillStyle=`rgba(255,236,190,${.85*(1-u)})`;ctx.beginPath();ctx.arc(s.x+Math.cos(a)*rr*u,s.y+Math.sin(a)*rr*u,1.6/z,0,7);ctx.fill()}}}
  // 节点
  const node=(x,y,r,col,label,big)=>{ctx.fillStyle=col;ctx.beginPath();ctx.arc(x,y,r/z,0,7);ctx.fill();ctx.strokeStyle='rgba(20,15,10,.9)';ctx.lineWidth=1.2/z;ctx.stroke();
    if(label&&(big||z>=.9)){ctx.font=`${(big?14:11)/z}px serif`;const tw=ctx.measureText(label).width;ctx.fillStyle='rgba(12,9,6,.8)';ctx.fillRect(x+r/z+3/z,y-9/z,tw+8/z,16/z);ctx.fillStyle='#f6e7c4';ctx.fillText(label,x+r/z+7/z,y+4/z)}};
  for(const s of R.src)node(s.x,s.y,9,GOLD+'1)',s.name,true);
  for(const g of R.gra)node(g.x,g.y,9,'rgba(250,226,160,1)',g.name,true);
  for(const b of R.bak)node(b.x,b.y,5.5,'rgba(255,170,90,1)',z>=1.4?'面包房':'',false);
  for(const s of R.steps)node(s.x,s.y,s.lost?7:5,s.lost?RED+'1)':'rgba(255,240,200,1)',s.lost?'这里今年断了供':(z>=1.4?'第 '+(s.i+1)+' 处台阶':''),!!s.lost);
  if(sel){const h=VEIN.sel;path(sel.s,{x:h.cx,y:h.cy},0,'rgba(255,255,255,.95)',2,[3,3]);node(h.cx,h.cy,5,'#fff','',false)}
  // 火场：只在火后几年画出轮廓
  if(Y>=48&&Y<55){ctx.fillStyle='rgba(226,82,58,.18)';for(const h of houses)if(h.destroyed===48){ctx.beginPath();ctx.arc(h.cx,h.cy,9,0,7);ctx.fill()}}
}
$('vein').onclick=()=>veinToggle(!VEIN.on);
