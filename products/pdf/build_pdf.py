from pathlib import Path

base=Path(__file__).resolve().parent
parts=['source_part1.pyfrag','source_part2.pyfrag','source_part3.pyfrag']
source=''.join((base/name).read_text(encoding='utf-8') for name in parts)
namespace={'__name__':'__main__','__file__':str(base/'build_pdf.py')}
exec(compile(source,'<life-kline-pdf-v1>','exec'),namespace)
