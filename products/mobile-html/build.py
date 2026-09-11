from pathlib import Path
import argparse, json

parser=argparse.ArgumentParser()
parser.add_argument('--data',required=True)
parser.add_argument('--out',required=True)
args=parser.parse_args()
base=Path(__file__).resolve().parent
d=json.loads(Path(args.data).read_text(encoding='utf-8'))
meta=d.get('meta',{})
name=meta.get('name','客户')
gender=meta.get('gender','')
birth=meta.get('birth_local','')
true_solar=meta.get('true_solar','')
day_master=meta.get('day_master','')
start_luck=meta.get('start_luck','')
direction=meta.get('direction','')
bazi=d.get('bazi',[])
subtitle=f'真太阳时修正版 · 北京时间 {birth} → 真太阳时约 {true_solar} · {gender}命'
pills=''.join([f'<span class="pill accent">{x[0]}{x[1]}年</span>' if i==0 else f'<span class="pill accent">{x[0]}{x[1]}'+('月' if i==1 else '日' if i==2 else '时')+'</span>' for i,x in enumerate(bazi)])
pills+=f'<span class="pill">{day_master}日主</span><span class="pill">{start_luck}起运 · {direction}</span>'
tpl=(base/'template.html').read_text(encoding='utf-8')
style=(base/'styles.css').read_text(encoding='utf-8')
app=(base/'app1.js').read_text(encoding='utf-8')+'\n'+(base/'app2.js').read_text(encoding='utf-8')
data_json=json.dumps(d,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')
app=app.replace('__DATA__',data_json)
out=(tpl.replace('__STYLE__',style).replace('__APP__',app).replace('{{NAME}}',name).replace('{{SUBTITLE}}',subtitle).replace('{{PILLS}}',pills))
Path(args.out).write_text(out,encoding='utf-8')
print(args.out)
