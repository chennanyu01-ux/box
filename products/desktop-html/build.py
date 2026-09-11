from pathlib import Path
import argparse

parser = argparse.ArgumentParser(description='Build the classic desktop Life K-Line into one offline HTML file.')
parser.add_argument('--name', default='客户', help='Customer display name')
parser.add_argument('--out', required=True, help='Output HTML path')
args = parser.parse_args()

base = Path(__file__).resolve().parent

def read(name: str) -> str:
    return (base / name).read_text(encoding='utf-8')

tpl = read('template.html')
out = (
    tpl.replace('__STYLE__', read('styles.css'))
       .replace('__CALENDAR__', read('calendar.js').replace('</script>', '<\\/script>'))
       .replace('__MODEL__', read('model.js').replace('</script>', '<\\/script>'))
       .replace('__APP1__', read('app1.js').replace('</script>', '<\\/script>'))
       .replace('__APP2__', read('app2.js').replace('</script>', '<\\/script>'))
       .replace('{{NAME}}', args.name)
)

path = Path(args.out)
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(out, encoding='utf-8')
print(path)
