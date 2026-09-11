'use strict';
const M=LifeModel,$=id=>document.getElementById(id),colors=['#75afff','#ffb454','#d895ee','#50d4cb'];
const YEAR_MIN=2005,YEAR_MAX=2104,MIN_SPAN=4;
const legacyRanges={near:[2020,2050],early:[2003,2032],middle:[2033,2062],late:[2063,2102],all:[2003,2102]};
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
 if(text.startsWith('壬日天乙贵人'))return '传统规则中，丙日主的天乙贵人位为酉、亥；当年（流年）命中，因此只给“贵人 / 机会”项加分。';
 const stem=text.match(/^(流年|大运) ([^ ]+) · (透干|藏干)(.)（(.) \/ ([^）]+)）：十神 \[([^\]]+)\] \+ 喜忌 (-?\d+(?:\.\d+)?) × \[1,1,0.5,1\]；占比 ([\d.]+)%/);
 if(stem){const [,source,pillar,place,gan,element,god,base,prefRaw,weight]=stem,pref=Number(prefRaw);const placeText=place==='透干'?'在天干直接出现（透干）':'包含在地支内部（藏干）';const prefText=pref===0?'当前口径不额外加减':`当前口径对${element}的五行加权为 ${sign(pref,0)}`;return `${sourceName(source)} ${pillar}：${gan}${element}${placeText}，相对丙日主属于“${god}”；十神基础分为 [${base}]，${prefText}，本位置权重 ${weight}%。`;}
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

