const DATA=__DATA__;
const PTS=DATA.chartPoints;
const CURRENT_YEAR=2026;
const WEIGHTS=[.3,.3,.2,.2], SCORE_KEYS=['career','wealth','relationship','opportunity'];
const SCORE_NAMES={career:'事业',wealth:'财运',relationship:'感情',opportunity:'贵人'};
const SCORE_COLORS={career:'#75afff',wealth:'#ffb454',relationship:'#d895ee',opportunity:'#50d4cb'};
// 壬水日主：沿用最终母版的十神四维向量，再整体平移到原年度综合分，使分项趋势与旧版综合 K 线保持同一中心。
const STEM_VECTOR={壬:[1,-2,0,2],癸:[0,-3,-1,3],甲:[4,3,1,2],乙:[5,2,-1,1],丙:[2,6,2,2],丁:[2,5,4,1],戊:[3,0,-2,0],己:[5,1,1,2],庚:[3,0,0,5],辛:[3,1,1,5]};
const NATAL_BRANCHES=['未','卯','辰','子'];
const RELATIONS=[
 {pairs:['子丑','寅亥','卯戌','辰酉','巳申','午未'],v:[1,1,3,2]},
 {pairs:['子午','丑未','寅申','卯酉','辰戌','巳亥'],v:[-3,-3,-4,-1]},
 {pairs:['子未','丑午','寅巳','卯辰','申亥','酉戌'],v:[-1,-1,-3,-1]},
 {pairs:['子酉','丑辰','寅亥','卯午','巳申','未戌'],v:[-1,-2,-2,-1]}
];
function pairHit(a,b,pairs){return pairs.some(s=>s.includes(a)&&s.includes(b)&&a!==b)}
function deriveScores(p){
 let v=[50,50,50,50];
 const add=(arr,m=1)=>arr.forEach((x,i)=>v[i]+=x*m);
 add(STEM_VECTOR[p.ganZhi[0]]||[0,0,0,0],1.15);
 if(p.daYun&&p.daYun!=='童限'&&p.daYun.length>=2)add(STEM_VECTOR[p.daYun[0]]||[0,0,0,0],.72);
 const annualBranch=p.ganZhi[1];
 NATAL_BRANCHES.forEach((b,idx)=>RELATIONS.forEach(r=>{if(pairHit(annualBranch,b,r.pairs)){const vv=r.v.slice();if(idx===2)vv[2]*=1.5;add(vv,.72)}}));
 const composite=v.reduce((s,x,i)=>s+x*WEIGHTS[i],0),delta=p.score-composite;
 v=v.map(x=>clamp(x+delta,0,100));
 const finalComposite=v.reduce((s,x,i)=>s+x*WEIGHTS[i],0),fix=p.score-finalComposite;
 v=v.map(x=>Math.round(clamp(x+fix,0,100)*10)/10);
 return Object.fromEntries(SCORE_KEYS.map((k,i)=>[k,v[i]]));
}
PTS.forEach(p=>p.scores=deriveScores(p));
const $=id=>document.getElementById(id);
function clamp(v,a,b){return Math.max(a,Math.min(b,v))}
function svgEl(tag,attrs={}){const e=document.createElementNS('http://www.w3.org/2000/svg',tag);Object.keys(attrs).forEach(k=>e.setAttribute(k,attrs[k]));return e}
function scoreClass(v){return v>=70?'score-good':v<50?'score-bad':'score-mid'}
function mean(arr){return arr.reduce((a,b)=>a+b,0)/Math.max(1,arr.length)}
const peak=[...PTS].sort((a,b)=>b.high-a.high)[0], trough=[...PTS].sort((a,b)=>a.low-b.low)[0], current=PTS.find(p=>p.year===CURRENT_YEAR)||PTS[0];
const avg=Math.round(mean(PTS.map(p=>p.score))*10)/10;
$('metrics').innerHTML=[
 ['当前指数',current.score,`${current.year} · ${current.ganZhi}`],['百年均值',avg,'综合分均值'],['最高高点',peak.high,`${peak.year} · ${peak.ganZhi}`],['最低低点',trough.low,`${trough.year} · ${trough.ganZhi}`],['当前大运',current.daYun,`${current.age}岁 · 模型年龄`]
].map(([k,v,s])=>`<div class="metric"><div class="v">${v}</div><div class="k">${k}</div><div class="s">${s}</div></div>`).join('');

let viewStart=1,viewEnd=100,selectedYear=current.year;
const MIN_SPAN=6,MAX_SPAN=100;
const series={total:true,career:true,wealth:true,relationship:true,opportunity:true};
function contiguousBands(data){let out=[],s=null;for(const p of data){if(!s||s.name!==p.daYun){if(s)out.push(s);s={name:p.daYun,start:p.age,end:p.age}}else s.end=p.age}if(s)out.push(s);return out}
function renderSeriesControls(){
 const defs=[['total','综合 K 线','#dbe6f3'],...SCORE_KEYS.map(k=>[k,SCORE_NAMES[k],SCORE_COLORS[k]])];
 $('seriesControls').innerHTML=defs.map(([key,label,color])=>`<button type="button" class="series-toggle ${series[key]?'active':''}" data-series="${key}" style="--series:${color}" aria-pressed="${series[key]}"><span class="series-mark"></span>${label}</button>`).join('');
}
function chartData(){return PTS.filter(p=>p.age>=viewStart-.55&&p.age<=viewEnd+.55)}
function normalizeView(start,end){
 let span=clamp(end-start+1,MIN_SPAN,MAX_SPAN);
 let s=start,e=s+span-1;
 if(s<1){s=1;e=s+span-1}
 if(e>100){e=100;s=e-span+1}
 viewStart=clamp(s,1,100);viewEnd=clamp(e,viewStart,100);
}
function setViewAround(anchorAge,newSpan,anchorFrac=.5){
 newSpan=clamp(newSpan,MIN_SPAN,MAX_SPAN);
 const start=anchorAge-anchorFrac*(newSpan-1);
 normalizeView(start,start+newSpan-1);
 scheduleChart();
}
let renderQueued=false;
function scheduleChart(){if(renderQueued)return;renderQueued=true;requestAnimationFrame(()=>{renderQueued=false;renderChart()})}
function pickNiceStep(raw,candidates){for(const s of candidates){if(s>=raw)return s}return candidates[candidates.length-1]}
function adaptiveXTickStep(span,plotW,fontSize){
 const minGap=Math.max(58,fontSize*5.6);
 const maxTicks=Math.max(2,Math.floor(plotW/minGap));
 return pickNiceStep(span/Math.max(1,maxTicks-1),[1,2,5,10,20,25,50,100]);
}
function adaptiveYTickStep(yMin,yMax,plotH,fontSize){
 const range=Math.max(1,yMax-yMin),minGap=Math.max(30,fontSize*2.25);
 const maxTicks=Math.max(2,Math.floor(plotH/minGap));
 const bySpace=range/Math.max(1,maxTicks-1);
 const byRange=range<=30?5:range<=55?10:20;
 return pickNiceStep(Math.max(bySpace,byRange),[5,10,20,25,50,100]);
}
function renderChart(){
 const svg=$('chart');svg.innerHTML='';
 const stage=$('chartStage');
 const W=Math.max(320,Math.round(stage.clientWidth||360)),H=Math.max(360,Math.round(stage.clientHeight||420));
 svg.setAttribute('viewBox',`0 0 ${W} ${H}`);svg.setAttribute('preserveAspectRatio','none');
 svg.appendChild(svgEl('rect',{x:0,y:0,width:W,height:H,fill:'#080d13'}));
 const span=viewEnd-viewStart+1;
 const data=chartData();if(!data.length)return;
 const zoom=clamp(Math.sqrt(100/span),1,2.45);
 const axisFont=clamp(9.4*zoom,9.4,16), ageFont=clamp(7.8*zoom,7.8,13.2), bandFont=clamp(9.1*zoom,9.1,14.5);
 const L=clamp(38+axisFont*.35,40,52),R=12,T=26,B=clamp(42+ageFont*.9,46,62),plotW=W-L-R,plotH=H-T-B;
 const x=a=>L+(a-viewStart+.5)*plotW/span;
 const vals=[];if(series.total)data.forEach(p=>vals.push(p.low,p.high,p.score));SCORE_KEYS.forEach(k=>{if(series[k])data.forEach(p=>vals.push(p.scores[k]))});if(!vals.length)data.forEach(p=>vals.push(p.low,p.high));
 const yMin=Math.max(0,Math.floor((Math.min(...vals)-6)/10)*10),yMax=Math.min(100,Math.ceil((Math.max(...vals)+6)/10)*10);
 const y=v=>T+(yMax-v)*plotH/(yMax-yMin||1);
 const colors=['#162238','#162b2d','#251c34','#30251b','#1a2831','#2a1e25'];
 contiguousBands(data).forEach((b,i)=>{const x1=x(b.start)-plotW/span/2,x2=x(b.end)+plotW/span/2;if(x2<L||x1>W-R)return;svg.appendChild(svgEl('rect',{x:Math.max(L,x1),y:T,width:Math.max(1,Math.min(W-R,x2)-Math.max(L,x1)),height:plotH,fill:colors[i%colors.length],opacity:.13}));if(x2-x1>bandFont*2.3){const tx=svgEl('text',{x:clamp((x1+x2)/2,L+10,W-R-10),y:T+bandFont+2,fill:'#70849b','font-size':bandFont,'text-anchor':'middle','font-weight':'600'});tx.textContent=b.name;svg.appendChild(tx)}});
 const yStep=adaptiveYTickStep(yMin,yMax,plotH,axisFont);
 const yFirst=Math.ceil(yMin/yStep)*yStep;
 for(let v=yFirst;v<=yMax+.001;v+=yStep){svg.appendChild(svgEl('line',{x1:L,y1:y(v),x2:W-R,y2:y(v),stroke:'#213041','stroke-width':'1'}));const tx=svgEl('text',{x:L-7,y:y(v)+axisFont*.34,fill:'#7c8ba0','font-size':axisFont,'text-anchor':'end'});tx.textContent=v;svg.appendChild(tx)}
 const tickStep=adaptiveXTickStep(span,plotW,axisFont),minTickGap=Math.max(58,axisFont*5.6);
 let tickPts=data.filter(p=>p.age%tickStep===0);
 const addEdgeTick=p=>{if(!p)return;const xx=x(p.age);if(xx<L-4||xx>W-R+4)return;if(tickPts.every(q=>Math.abs(x(q.age)-xx)>=minTickGap))tickPts.push(p)};
 addEdgeTick(data[0]);addEdgeTick(data[data.length-1]);tickPts.sort((a,b)=>a.age-b.age);
 tickPts.forEach(p=>{const xx=x(p.age);const tx=svgEl('text',{x:xx,y:H-B+axisFont+7,fill:'#8291a5','font-size':axisFont,'text-anchor':'middle','font-weight':span<=20?'650':'500'});tx.textContent=p.year;svg.appendChild(tx);const ta=svgEl('text',{x:xx,y:H-B+axisFont+ageFont+10,fill:'#59697c','font-size':ageFont,'text-anchor':'middle'});ta.textContent=p.age+'岁';svg.appendChild(ta)});
 if(CURRENT_YEAR>=data[0].year&&CURRENT_YEAR<=data[data.length-1].year){const cp=data.find(p=>p.year===CURRENT_YEAR);if(cp){const xx=x(cp.age);if(xx>=L&&xx<=W-R){svg.appendChild(svgEl('line',{x1:xx,y1:T,x2:xx,y2:H-B,stroke:'#f0c36b','stroke-width':'1.3','stroke-dasharray':'5 5',opacity:.85}));const t=svgEl('text',{x:xx+5,y:T+bandFont*2.15,fill:'#f0c36b','font-size':bandFont,'font-weight':'700'});t.textContent='2026';svg.appendChild(t)}}}
 if(series.total){const d=data.map((p,i)=>(i?'L':'M')+x(p.age)+' '+y(p.score)).join(' ');svg.appendChild(svgEl('path',{d,fill:'none',stroke:'#77a7ff','stroke-width':clamp(1.4*zoom,1.4,2.3),opacity:.46,'stroke-linecap':'round','stroke-linejoin':'round'}))}
 SCORE_KEYS.forEach(k=>{if(!series[k])return;const d=data.map((p,i)=>(i?'L':'M')+x(p.age)+' '+y(p.scores[k])).join(' ');svg.appendChild(svgEl('path',{d,fill:'none',stroke:SCORE_COLORS[k],'stroke-width':clamp(1.65*zoom,1.7,2.8),'stroke-linecap':'round','stroke-linejoin':'round',opacity:.92}))});
 const bw=clamp(plotW/span*.56,3.5,18);
 if(series.total)data.forEach(p=>{const xx=x(p.age);if(xx<L-bw||xx>W-R+bw)return;const up=p.close>=p.open,col=up?'#2bd89f':'#ff6474';const g=svgEl('g',{'data-year':p.year,style:'cursor:pointer'});const bodyTop=Math.min(y(p.open),y(p.close)),bodyBottom=Math.max(y(p.open),y(p.close));const rawUpper=Math.max(0,bodyTop-y(p.high)),rawLower=Math.max(0,y(p.low)-bodyBottom);const upperLen=rawUpper?clamp(rawUpper*.18,1.5,6):0,lowerLen=rawLower?clamp(rawLower*.18,1.5,6):0;g.appendChild(svgEl('line',{x1:xx,y1:bodyTop-upperLen,x2:xx,y2:bodyBottom+lowerLen,stroke:col,'stroke-width':clamp(1.05*zoom,1,1.6)}));const hh=Math.max(3,Math.abs(y(p.open)-y(p.close)));g.appendChild(svgEl('rect',{x:xx-bw/2,y:bodyTop,width:bw,height:hh,fill:col,rx:'1.5',opacity:p.year===selectedYear?'1':'.9',stroke:p.year===selectedYear?'#fff':'none','stroke-width':p.year===selectedYear?'1.1':'0'}));const hit=svgEl('rect',{x:xx-Math.max(8,bw/2),y:T,width:Math.max(16,bw),height:plotH,fill:'transparent'});g.appendChild(hit);svg.appendChild(g)});
 svg.appendChild(svgEl('line',{x1:L,y1:H-B,x2:W-R,y2:H-B,stroke:'#56667a','stroke-width':'1'}));svg.appendChild(svgEl('line',{x1:L,y1:T,x2:L,y2:H-B,stroke:'#56667a','stroke-width':'1'}));
 $('gestureBadge').innerHTML=`<b>${Math.round(span)} 年</b> · ${data[0].year}–${data[data.length-1].year}`;
}
