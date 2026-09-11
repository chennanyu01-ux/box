from pathlib import Path

base=Path(__file__).resolve().parent
parts=['source_part1.pyfrag','source_part2.pyfrag','source_part3.pyfrag']
# Always insert a newline between fragments. This keeps the generated source
# valid even when a fragment does not end with a trailing newline.
source='\n'.join((base/name).read_text(encoding='utf-8').rstrip('\n') for name in parts)+'\n'
namespace={'__name__':'__main__','__file__':str(base/'build_pdf.py')}
exec(compile(source,'<life-kline-pdf-v1.1>','exec'),namespace)
