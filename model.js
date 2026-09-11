(function(root){
'use strict';
const elements={甲:'木',乙:'木',丙:'火',丁:'火',戊:'土',己:'土',庚:'金',辛:'金',壬:'水',癸:'水'};
const hidden={子:[['癸',1]],丑:[['己',.6],['癸',.3],['辛',.1]],寅:[['甲',.6],['丙',.3],['戊',.1]],卯:[['乙',1]],辰:[['戊',.6],['乙',.3],['癸',.1]],巳:[['丙',.6],['戊',.3],['庚',.1]],午:[['丁',.7],['己',.3]],未:[['己',.6],['丁',.3],['乙',.1]],申:[['庚',.6],['壬',.3],['戊',.1]],酉:[['辛',1]],戌:[['戊',.6],['辛',.3],['丁',.1]],亥:[['壬',.7],['甲',.3]]};
const gods={甲:'偏印',乙:'正印',丙:'比肩',丁:'劫财',戊:'食神',己:'伤官',庚:'偏财',辛:'正财',壬:'七杀',癸:'正官'};
const vectors={甲:[3,0,0,5],乙:[3,1,1,5],丙:[1,-2,0,2],丁:[0,-3,-1,3],戊:[4,3,1,2],己:[5,2,-1,1],庚:[2,6,2,2],辛:[2,5,4,1],壬:[3,0,-2,0],癸:[5,1,1,2]};
const profiles={
 support:{label:'金水调衡',description:'水、金出现时额外加分；木、火、土相应减分。',prefs:{金:4,水:6,木:-5,火:-4,土:-2}},
 balanced:{label:'中性参考',description:'不预设哪一种五行更有帮助，只计算十神与干支关系。',prefs:{金:0,水:0,木:0,火:0,土:0}},
 release:{label:'木火土补强',description:'木、火、土出现时额外加分；金、水相应减分。',prefs:{金:-4,水:-5,木:5,火:4,土:2}}
};
const weights=[.3,.3,.2,.2],keys=['career','wealth','relationship','opportunity'],names=['事业','财运','感情','贵人 / 机会'];
const natal=['乙酉','癸未','丙辰','丙申'],positions=['年柱','月柱','日柱','时柱'];
const relations=[{name:'六合',pairs:['子丑','寅亥','卯戌','辰酉','巳申','午未'],v:[1,1,3,2]},{name:'六冲',pairs:['子午','丑未','寅申','卯酉','辰戌','巳亥'],v:[-3,-3,-4,-1]},{name:'六害',pairs:['子未','丑午','寅巳','卯辰','申亥','酉戌'],v:[-1,-1,-3,-1]},{name:'相破',pairs:['子酉','丑辰','寅亥','卯午','巳申','未戌'],v:[-1,-2,-2,-1]},{name:'子卯刑',pairs:['子卯'],v:[-1,0,-3,-1]}];
const round=n=>Math.round((n+Number.EPSILON)*100)/100,clamp=n=>Math.max(0,Math.min(100,n)),dot=v=>v.reduce((s,x,i)=>s+x*weights[i],0),pair=(a,b,p)=>p.some(s=>s.includes(a)&&s.includes(b)&&a!==b);
function factors(annual,dayun,profile){
 const rows=[];const add=(id,evidence,vector,multiplier=1)=>rows.push({id,evidence,vector:vector.map(v=>v*multiplier),multiplier});
 function pillar(p,label,m){
  const parts=[[p[0],.4,'透干'],...hidden[p[1]].map(([s,w])=>[s,w*.6,'藏干'])];
  for(const [s,w,part] of parts){const base=vectors[s],pref=profiles[profile].prefs[elements[s]],v=base.map((n,i)=>n+pref*[1,1,.5,1][i]);add('E-'+s,label+' '+p+' · '+part+s+'（'+elements[s]+' / '+gods[s]+'）：十神 ['+base.join(', ')+'] + 喜忌 '+pref+' × [1,1,0.5,1]；占比 '+round(w*100)+'%',v,m*w);}
 }
 function interact(a,b,label,m,isDay){
  for(const r of relations)if(pair(a[1],b[1],r.pairs)){const v=r.v.slice();if(isDay)v[2]*=1.5;add('B-'+r.name,label+'：'+a[1]+b[1]+r.name+(isDay?'，日支感情项 ×1.5':'')+'；不推断合化',v,m);}
  if(a[1]===b[1]&&'辰午酉亥'.includes(a[1]))add('B-自刑',label+'：'+a[1]+'重复，自刑简化项',[-1,0,-2,-1],m);
  if(pair(a[0],b[0],['甲己','乙庚','丙辛','丁壬','戊癸']))add('S-五合',label+'：'+a[0]+b[0]+'天干五合，只计连接，不判合化',[1,1,1,2],m);
 }
 pillar(annual,'流年',1.4);if(dayun!=='童限')pillar(dayun,'大运',1);
 natal.forEach((p,i)=>{interact(annual,p,'流年 '+annual+' × 原局'+positions[i]+' '+p,1,i===2);if(dayun!=='童限')interact(dayun,p,'大运 '+dayun+' × 原局'+positions[i]+' '+p,.6,i===2);});
 if(dayun!=='童限')interact(annual,dayun,'流年 '+annual+' × 大运 '+dayun,.8,false);
 if('酉亥'.includes(annual[1]))add('G-天乙','丙日天乙贵人取酉、亥：流年'+annual[1]+'命中；仅加机会项',[0,0,0,4]);
 return rows;
}
function generate(calendar,profile='support'){
 if(!profiles[profile])throw Error('未知评分口径');let previous=50;
 return calendar.map(c=>{
  const ledger=[{id:'BASE',evidence:'中性起点；四项统一 50 分',vector:[50,50,50,50],multiplier:1}];
  for(const segment of c.segments){for(const r of factors(c.ganZhi,segment.name,profile))ledger.push({...r,period:segment.name,periodWeight:segment.weight,evidence:r.evidence+(c.segments.length>1?'；'+segment.name+'占年度 '+round(segment.weight*100)+'%':''),vector:r.vector.map(v=>v*segment.weight)});}
  const raw=keys.map((_,i)=>ledger.reduce((s,r)=>s+r.vector[i],0));const bounded=raw.map(clamp);if(raw.some((v,i)=>v!==bounded[i]))ledger.push({id:'CAP',evidence:'限制到 0–100 分',vector:bounded.map((v,i)=>v-raw[i])});
  const scores=bounded.map(round);ledger.push({id:'ROUND',evidence:'分项保留两位小数',vector:scores.map((v,i)=>v-bounded[i])});
  const score=round(dot(scores)),open=previous,close=score,movement=ledger.filter(r=>!['BASE','CAP','ROUND'].includes(r.id)).reduce((s,r)=>s+Math.abs(dot(r.vector)),0),spread=round(1+Math.min(3,movement*.08));
  const top=ledger.filter(r=>!['BASE','CAP','ROUND'].includes(r.id)).sort((a,b)=>Math.abs(dot(b.vector))-Math.abs(dot(a.vector))).slice(0,2);
  const result={age:c.year-2004,year:c.year,ganZhi:c.ganZhi,daYun:c.segments.map(x=>x.name).join(' → '),open,close,high:round(clamp(Math.max(open,close)+spread)),low:round(clamp(Math.min(open,close)-spread)),score,reason:top.map(r=>r.evidence.split('；')[0]).join(' / '),scores:Object.fromEntries(keys.map((k,i)=>[k,scores[i]])),rawScores:Object.fromEntries(keys.map((k,i)=>[k,raw[i]])),ledger,period:c,spread,change:round(close-open)};
  previous=close;return result;
 });
}
function exportData(calendar,profile){return {schemaVersion:'life-terminal/1.0',modelVersion:'rules-1.0.1-bing',profile,profileLabel:profiles[profile].label,birth:{gender:'女',civil:'2005-07-31 申时（16:00仅用于起运估算）',place:'未提供',apparentSolarTime:'四柱已由用户校准，本版不再换算',bazi:natal,status:'用户指定并确认已校准；具体时分未提供，起运时刻按申时中点估算'},model:{weights:Object.fromEntries(keys.map((k,i)=>[k,weights[i]])),profiles,tenGodVectors:vectors,hiddenStems:hidden,relations,calendarMethod:'按2005乙酉年推定公历2005-07-31；女命阴年顺行；申时以16:00为估算点，起运约2007-12-11；流年按立春分界，交运年按实际覆盖时长混合。',ohLC:'open=前一年close，首年50；close=score；spread=1+min(3,0.08×逐条非基准规则的总分贡献绝对值之和)；high/low=开收盘包络±spread，限制0–100。影线仅为较弱的K线视觉提示。',limitations:'自定义传统文化模型，系数未经经验校准。未实现完整格局、调候、三合三会及刑局、合化、神煞体系；没有现实事件回测。不预测收入、婚期或寿命。'},chartData:generate(calendar,profile)};}
root.LifeModel={generate,exportData,keys,names,weights,natal,profiles,vectors,gods,hidden,relations,dot,round};
})(typeof window==='undefined'?globalThis:window);
