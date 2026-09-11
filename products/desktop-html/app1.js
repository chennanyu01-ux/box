'use strict';
const M=LifeModel,$=id=>document.getElementById(id),colors=['#75afff','#ffb454','#d895ee','#50d4cb'];
const YEAR_MIN=2002,YEAR_MAX=2101,MIN_SPAN=4;
const legacyRanges={near:[2020,2050],early:[2002,2031],middle:[2032,2061],late:[2062,2101],all:[2002,2101]};
const saved=window.SAVED_STATE||{},fallbackRange=legacyRanges[saved.range]||[2020,2050];
let profile=saved.profile||'support',selected=saved.year||2026;
let viewStart=Math.max(YEAR_MIN,Math.min(YEAR_MAX-MIN_SPAN,saved.startYear??fallbackRange[0]));
let viewEnd=Math.max(viewStart+MIN_SPAN,Math.min(YEAR_MAX,saved.endYear??fallbackRange[1]));
let all=[],variants={};
let series={total:true,career:true,wealth:true,relationship:true,opportunity:true,...(saved.series||{})};

const fmt=n=>Number(n).toFixed(2),sign=(n,d=2)=>(n>0?'+':'')+Number(n).toFixed(d),tone=n=>n>0?'up':n<0?'down':'muted';
const sourceName=s=>s==='流年'?'当年（流年）':'十年阶段（大运）';
function visible(){return all.filter(d=>d.year>=viewStart&&d.year<=viewEnd);}
function keepYearVisible(y){
 const span=viewEnd-viewStart;
 if(y<viewStart){viewStart=y;viewEnd=Math.min(YEAR_MAX,y+span);}
 if(y>viewEnd){viewEnd=y;viewStart=Math.max(YEAR_MIN,y-span);}
}
function selectYear(y){if(!Number.isInteger(y)||y<YEAR_MIN||y>YEAR_MAX)throw Error(`年份必须在 ${YEAR_MIN}–${YEAR_MAX} 之间`);selected=y;keepYearVisible(y);render();}
function recalc(){variants=Object.fromEntries(Object.keys(M.profiles).map(p=>[p,M.generate(CALENDAR,p)]));all=variants[profile];render();}
function line(data,key,width=700,height=60){return data.map((d,i)=>`${i/(data.length-1)*width},${height-((key?d.scores[key]:d.score)/100)*height}`).join(' ');}
function chartDomain(){const values=[];for(const d of all){if(series.total)values.push(d.low,d.high);M.keys.forEach(k=>{if(series[k])values.push(d.scores[k])});}if(!values.length)values.push(...all.flatMap(d=>[d.low,d.high]));let lo=Math.max(0,Math.floor(Math.min(...values)/5)*5-5),hi=Math.min(100,Math.ceil(Math.max(...values)/5)*5+5);if(hi-lo<30){const mid=(hi+lo)/2;lo=Math.max(0,Math.floor((mid-15)/5)*5);hi=Math.min(100,lo+30)}return [lo,hi];}

function friendlyEvidence(text){
 if(text.startsWith('中性起点'))return '统一从 50 分起算，作为各年份之间的中性比较起点。';
 if(text.startsWith('分项保留'))return '完成全部加减后，把四项分数保留到小数点后两位。';
 if(text.startsWith('限制到'))return '为保持统一量尺，把超出范围的结果限制在 0–100 分。';
 if(text.startsWith('甲日天乙贵人'))return '传统规则中，甲日主的天乙贵人位为丑、未；当年（流年）命中，因此只给“贵人”项加分。';
 const stem=text.match(/^(流年|大运) ([^ ]+) · (透干|藏干)(.)（(.) \/ ([^）]+)）：十神 \[([^\]]+)\] \+ 喜忌 (-?\d+(?:\.\d+)?) × \[1,1,0.5,1\]；占比 ([\d.]+)%/);
 if(stem){const [,source,pillar,place,gan,element,god,base,prefRaw,weight]=stem,pref=Number(prefRaw);const placeText=place==='透干'?'在天干直接出现（透干）':'包含在地支内部（藏干）';const prefText=pref===0?'当前口径不额外加减':`当前口径对${element}的五行加权为 ${sign(pref,0)}`;return `${sourceName(source)} ${pillar}：${gan}${element}${placeText}，相对甲日主属于“${god}”；十神基础分为 [${base}]，${prefText}，本位置权重 ${weight}%。`;}
 let s=text.replace(/^流年 /,'当年（流年） ').replace(/^大运 /,'十年阶段（大运） ')
  .replace(' × 原局年柱 ',' 与出生盘（原局）的年柱 ')
  .replace(' × 原局月柱 ',' 与出生盘（原局）的月柱 ')
  .replace(' × 原局日柱 ',' 与出生盘（原局）的日柱 ')
  .replace(' × 原局时柱 ',' 与出生盘（原局）的时柱 ')
  .replace(' × 大运 ',' 与十年阶段（大运） ')
  .replace(/六冲/g,'牵动较强（六冲）').replace(/六合/g,'较易配合（六合）')
  .replace(/六害/g,'有隐性牵扯（六害）').replace(/相破/g,'配合中带消耗（相破）')
  .replace(/子卯刑/g,'关系偏紧（子卯刑）').replace(/自刑简化项/g,'同支重复，按内耗关系（自刑）简化计分')
  .replace('日支感情项 ×1.5','日支通常用于观察亲密关系，因此感情项 ×1.5')
  .replace('天干五合，只计连接，不判合化','天干形成连接（五合）；只计连接，不判断合化')
  .replace('不推断合化','只记录关系，不判断是否合化');
 return s;
}
function impactLabel(row){
 const stem=row.evidence.match(/^(流年|大运) ([^ ]+) · (透干|藏干)(.)（(.) \/ ([^）]+)）/);
 if(stem)return `${sourceName(stem[1])} ${stem[2]}：${stem[4]}${stem[5]}（${stem[6]}，${stem[3]==='透干'?'天干直接出现':'地支内含'}）`;
 return friendlyEvidence(row.evidence).split('；')[0];
}
function syncRangeControls(){
 $('rangeStart').value=viewStart;$('rangeEnd').value=viewEnd;$('rangeLabel').textContent=`${viewStart}–${viewEnd}`;
 const left=(viewStart-YEAR_MIN)/(YEAR_MAX-YEAR_MIN)*100,right=(viewEnd-YEAR_MIN)/(YEAR_MAX-YEAR_MIN)*100;
 $('rangeFill').style.left=`${left}%`;$('rangeFill').style.width=`${right-left}%`;
}
function renderSeriesControls(){const defs=[['total','综合 K 线','#dbe6f3'],...M.keys.map((k,i)=>[k,M.names[i],colors[i]])];$('seriesControls').innerHTML=defs.map(([key,label,color])=>`<label class="series-toggle ${series[key]?'active':''}" style="--series:${color}"><input type="checkbox" data-series="${key}" ${series[key]?'checked':''}><span class="series-mark"></span>${label}</label>`).join('');}
function renderProfiles(){
 const current=variants[profile][selected-YEAR_MIN].score,values=Object.fromEntries(Object.keys(M.profiles).map(p=>[p,variants[p][selected-YEAR_MIN].score]));
 $('sensitivity').innerHTML=Object.entries(M.profiles).map(([p,meta])=>{const delta=values[p]-current;return `<button type="button" class="profile-option ${p===profile?'active':''}" data-profile="${p}" aria-pressed="${p===profile}"><span class="profile-copy"><b>${meta.label}</b><small>${meta.description}</small></span><span class="profile-score"><strong>${fmt(values[p])}</strong><em>${p===profile?'当前口径':sign(delta)+' 分'}</em></span></button>`;}).join('');
 const spread=Math.max(...Object.values(values))-Math.min(...Object.values(values));
 const reading=spread<=4?'三种结果接近，判断较稳定。':spread<=9?'三种结果有一定差异，解读时应保留余地。':'三种结果差异明显，本年分数较依赖身强弱与五行取用的判断。';
 $('profileSummary').innerHTML=`口径差 <strong>${fmt(spread)}</strong> 分 · ${reading}`;
}

function render(){
 const d=all[selected-YEAR_MIN],data=visible();syncRangeControls();$('year').value=selected;$('prev').disabled=selected===YEAR_MIN;$('next').disabled=selected===YEAR_MAX;
 $('metrics').innerHTML=[['综合指数',d.score,'#ffb454',null],...M.names.map((n,i)=>[n,d.scores[M.keys[i]],colors[i],M.keys[i]])].map(([n,v,col,key])=>{const prev=all[selected-YEAR_MIN-1];const change=prev?v-(key?prev.scores[key]:prev.score):v-50;return `<div class="metric"><div class="metric-name">${n}</div><div class="metric-value" style="color:${col}">${fmt(v)}</div><svg class="metric-line" viewBox="0 0 100 40" preserveAspectRatio="none" aria-hidden="true"><polyline points="${line(data,key,100,40)}" fill="none" stroke="${col}" stroke-width="2"/></svg><div class="metric-change"><span>${selected} · ${d.ganZhi}</span><span class="${tone(change)}">${sign(change)} ${selected===YEAR_MIN?'较基准':'较上年'}</span></div></div>`}).join('');
 renderSeriesControls();drawChart(data,d);renderProfiles();
 $('yearDetail').innerHTML=`<div class="year-head"><strong>${d.ganZhi}年</strong><span>${d.age} 虚岁</span></div><p class="year-sub">十年阶段（大运）：${d.daYun==='童限'?'尚未起运':d.daYun}<br>本流年：${d.period.start.slice(0,10)} — ${d.period.end.slice(0,10)}<br>结束日也是下一流年的起点</p><div class="ohlc">${[['年初承接',d.open],['年度结果',d.close],['图示上界',d.high],['图示下界',d.low]].map(([n,v])=>`<div><span>${n}</span><b>${fmt(v)}</b></div>`).join('')}</div><p class="year-description">综合分 ${fmt(d.score)}，较上年 <span class="${tone(d.change)}">${sign(d.change)}</span>。<br>四项最高与最低相差 ${fmt(Math.max(...Object.values(d.scores))-Math.min(...Object.values(d.scores)))} 分。</p><h3>这一年为什么这样打分</h3>${d.ledger.filter(r=>!['BASE','CAP','ROUND'].includes(r.id)).sort((a,b)=>Math.abs(M.dot(b.vector))-Math.abs(M.dot(a.vector))).slice(0,3).map(r=>`<p class="impact">${impactLabel(r)}<br><span class="${tone(M.dot(r.vector))}">综合影响 ${sign(M.dot(r.vector))}</span></p>`).join('')}${d.period.segments.length>1?'<p class="small-note">这一年正好更换大运，按实际覆盖时间计算：'+d.period.segments.map(s=>s.name+' '+(s.weight*100).toFixed(1)+'%').join(' / ')+'</p>':''}`;
 $('ledgerTitle').textContent=`${selected} ${d.ganZhi} · 评分账本`;
 $('ledger').innerHTML=d.ledger.map(r=>`<tr><td>${friendlyEvidence(r.evidence)}<small>规则 ${r.id}${r.multiplier!=null?' · 本项权重 '+M.round(r.multiplier):''}</small></td>${r.vector.map(v=>`<td class="${tone(v)} numeric">${sign(v,3)}</td>`).join('')}<td class="${tone(M.dot(r.vector))} numeric">${sign(M.dot(r.vector),3)}</td></tr>`).join('');
 $('ledgerTotal').innerHTML=`<tr><td>最终分数 <small>全部规则汇总后保留两位小数</small></td>${M.keys.map(k=>`<td>${fmt(d.scores[k])}</td>`).join('')}<td style="color:var(--amber)">${fmt(d.score)}</td></tr>`;
}

function drawChart(data,d){
 const rect=$('chart').getBoundingClientRect(),w=Math.max(300,rect.width||1000),h=rect.height||410,l=54,r=20,t=42,b=44,pw=w-l-r,ph=h-t-b,step=pw/data.length,[lo,hi]=chartDomain(),x=i=>l+(i+.5)*step,y=n=>t+(hi-n)/(hi-lo)*ph;let s='';
 $('axisDomain').textContent=`纵轴 ${lo}–${hi}`;
 for(let i=0;i<=5;i++){const n=Math.round((lo+(hi-lo)*i/5)*10)/10;s+=`<line x1="${l}" y1="${y(n)}" x2="${w-r}" y2="${y(n)}" stroke="#2e3b49" stroke-dasharray="${Math.abs(n-50)<.01?'6 5':'2 5'}"/><text x="${l-12}" y="${y(n)+5}" fill="#9eb0c4" font-size="14" text-anchor="end">${n}</text>`;}
 let last='';data.forEach((p,i)=>{const name=p.period.segments[p.period.segments.length-1].name;if(name!==last){s+=`<line x1="${x(i)-step/2}" x2="${x(i)-step/2}" y1="24" y2="${h-b}" stroke="#46566a" stroke-dasharray="4 5"/><text x="${x(i)}" y="18" font-size="12" fill="#9cacbf">${name}</text>`;last=name;}});
 const at=data.findIndex(p=>p.year===selected);s+=`<rect x="${x(at)-step/2}" y="30" width="${step}" height="${h-b-30}" fill="#eef5ff" opacity=".055"/><line x1="${x(at)}" x2="${x(at)}" y1="${t}" y2="${h-b}" stroke="#d8e3ef" opacity=".42" stroke-dasharray="4 5"/>`;
 if(series.total)data.forEach((p,i)=>{const col=p.close>=p.open?'#40cc9a':'#f47b80',cw=Math.max(1.5,step*.48);s+=`<g><title>${p.year} ${p.ganZhi}：综合 ${p.score}，${p.daYun}</title><line x1="${x(i)}" x2="${x(i)}" y1="${y(p.high)}" y2="${y(p.low)}" stroke="${col}" stroke-width="1" opacity=".58"/><rect x="${x(i)-cw/2}" y="${y(Math.max(p.open,p.close))}" width="${cw}" height="${Math.max(2,Math.abs(y(p.open)-y(p.close)))}" rx="1" fill="${col}" ${p.year===selected?'stroke="#eef5ff" stroke-width="1.2"':''}/></g>`;});
 M.keys.forEach((key,k)=>{if(!series[key])return;const points=data.map((p,i)=>`${x(i)},${y(p.scores[key])}`).join(' ');s+=`<polyline points="${points}" fill="none" stroke="${colors[k]}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"><title>${M.names[k]}趋势</title></polyline><circle cx="${x(at)}" cy="${y(d.scores[key])}" r="4.2" fill="${colors[k]}" stroke="#0b0f15" stroke-width="2"><title>${selected} ${M.names[k]} ${d.scores[key]}</title></circle>`;});
 data.forEach((p,i)=>{if(i%Math.ceil(data.length/Math.max(4,Math.floor(w/95)))===0)s+=`<text x="${x(i)}" y="${h-15}" fill="#a6b7ca" font-size="14" text-anchor="middle">${p.year}</text>`;});
 if(series.total)s+=`<circle cx="${x(at)}" cy="${y(d.score)}" r="4.5" fill="#eef5ff" stroke="#101820" stroke-width="2"><title>${selected} 综合 ${d.score}</title></circle>`;
 $('chart').innerHTML=`<svg viewBox="0 0 ${w} ${h}" aria-label="${data[0].year}至${data.at(-1).year}综合运势 K 线与分项折线">${s}</svg>`;
 $('chartHint').textContent=`${selected} ${d.ganZhi} · 综合 ${fmt(d.score)} · 点击选年 / ← → 切换`;
}
