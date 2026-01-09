import json
from pathlib import Path

root = Path(__file__).resolve().parents[1] / 'data' / 'docling'
report = []

for p in sorted(root.glob('*.docling.json')):
    info = {"file": p.name}
    try:
        with p.open('r', encoding='utf-8') as f:
            lines = [next(f) for _ in range(50)]
    except StopIteration:
        # file shorter than 50 lines; read all
        with p.open('r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        info.update({"error": str(e)})
        report.append(info)
        continue
    snippet = ''.join(lines)
    info['snippet_first50'] = snippet[:1000]
    # quick heuristic parsing
    try:
        data = json.loads(p.read_text(encoding='utf-8'))
    except Exception as e:
        info.update({"error": f"json:{e}"})
        report.append(info)
        continue
    text_items = data.get('text_items') or []
    tables = data.get('tables') or []
    info['num_text_items'] = len(text_items)
    info['text_chars'] = sum(len(t.strip()) for t in text_items if isinstance(t, str))
    info['num_tables'] = len(tables)
    total_cells = 0
    nonempty_cells = 0
    cell_chars = 0
    for t in tables:
        rows = t.get('rows') or []
        for row in rows:
            if not isinstance(row, list):
                continue
            for cell in row:
                total_cells += 1
                if isinstance(cell, str) and cell.strip():
                    nonempty_cells += 1
                    cell_chars += len(cell.strip())
    info.update({
        'total_cells': total_cells,
        'nonempty_cells': nonempty_cells,
        'cell_chars': cell_chars,
    })
    # quality heuristics
    poor = False
    reasons = []
    if info['num_text_items'] == 0 and info['num_tables'] == 0:
        poor = True
        reasons.append('no_text_no_tables')
    if info['text_chars'] < 50 and info['nonempty_cells'] < 3:
        poor = True
        reasons.append('very_little_text_and_table_cells')
    if info['num_tables'] > 0 and info['nonempty_cells'] == 0:
        poor = True
        reasons.append('tables_present_but_empty')
    info['poor'] = poor
    info['reasons'] = reasons
    report.append(info)

out = Path(__file__).resolve().parents[1] / 'data' / 'docling_quality_report.json'
out.write_text(json.dumps(report, indent=2), encoding='utf-8')
# print concise summary of poor files
poor_files = [r['file'] for r in report if r.get('poor')]
print('TOTAL_FILES', len(report))
print('POOR_COUNT', len(poor_files))
for f in poor_files:
    print(f)
