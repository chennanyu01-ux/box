(()=>{
const S='甲乙丙丁戊己庚辛壬癸',B='子丑寅卯辰巳午未申酉戌亥';
const gz=y=>{const i=(y-1984)%60;return S[(i+60)%60%10]+B[(i+60)%60%12]};
const lucks=[[2004,'辛亥'],[2014,'庚戌'],[2024,'己酉'],[2034,'戊申'],[2044,'丁未'],[2054,'丙午'],[2064,'乙巳'],[2074,'甲辰'],[2084,'癸卯'],[2094,'壬寅'],[2104,'辛丑']];
const d=(y,m,day,h=0,min=0)=>new Date(Date.UTC(y,m-1,day,h-8,min));
const pad=n=>String(n).padStart(2,'0');
const iso=x=>{const z=new Date(x.getTime()+8*3600e3);return `${z.getUTCFullYear()}-${pad(z.getUTCMonth()+1)}-${pad(z.getUTCDate())}T${pad(z.getUTCHours())}:${pad(z.getUTCMinutes())}:00.000+08:00`};
const human=x=>iso(x).replace('T',' ').replace('.000','');
const luckAt=x=>{let n='童限';for(const [y,v] of lucks){if(x>=d(y,6,25))n=v;else break}return n};
window.CALENDAR=[];
for(let y=2002;y<=2101;y++){
 const start=y===2002?d(2002,12,12,4,30):d(y,2,4),end=d(y+1,2,4),cuts=[start,...lucks.map(([yy])=>d(yy,6,25)).filter(x=>x>start&&x<end),end],total=end-start,segs=[];
 for(let i=0;i<cuts.length-1;i++){const a=cuts[i],b=cuts[i+1],mid=new Date((a.getTime()+b.getTime())/2);segs.push({name:luckAt(mid),weight:(b-a)/total,start:iso(a),end:iso(b)})}
 CALENDAR.push({year:y,ganZhi:gz(y),start:human(start),end:human(end),segments:segs});
}
})();