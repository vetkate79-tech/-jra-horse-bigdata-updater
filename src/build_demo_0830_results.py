#!/usr/bin/env python3
import csv
import json
from pathlib import Path

SRC = Path('data/race_results_html_2026.csv')
OUT = Path('docs/data/demo-results-2026-08-30.json')
TARGET = '2026-08-30'

races = {}
with SRC.open('r', encoding='utf-8-sig', newline='') as f:
    for row in csv.DictReader(f):
        if row.get('race_date') != TARGET:
            continue
        finish_raw = (row.get('finish_position') or '').strip()
        if not finish_raw.isdigit():
            continue
        finish = int(finish_raw)
        track = row.get('course') or ''
        race_no = int(row.get('race_no') or 0)
        if not track or not race_no:
            continue
        key = f'{track}:{race_no}'
        race = races.setdefault(key, {
            'date': TARGET,
            'track': track,
            'race_no': race_no,
            'race_name': row.get('race_name') or '',
            'finishes': {},
            'top3': []
        })
        horse_no = str(row.get('horse_no') or '').strip()
        horse_name = row.get('horse_name') or ''
        if horse_no:
            race['finishes'][horse_no] = {'finish': finish, 'horse_name': horse_name}
        if finish <= 3:
            race['top3'].append({'finish': finish, 'horse_no': horse_no, 'horse_name': horse_name})

for race in races.values():
    race['top3'].sort(key=lambda x: x['finish'])

payload = {
    'source': 'JRA_OFFICIAL_RESULT_HTML',
    'purpose': 'POST_HOC_UI_JUDGEMENT_ONLY',
    'leakage_rule': 'DO_NOT_USE_FOR_PREDICTION_OR_AI_PRE_RACE_REASONING',
    'date': TARGET,
    'race_count': len(races),
    'races': sorted(races.values(), key=lambda r: (r['track'], r['race_no']))
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'wrote {OUT} races={len(races)}')
