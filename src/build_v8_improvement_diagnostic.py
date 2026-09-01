#!/usr/bin/env python3
from pathlib import Path
import json

V6=Path('docs/data/oral-v6-72-scored.json')
V7=Path('docs/data/oral-v7-72-style-scored.json')
OUT=Path('status/oral-v8-improvement-diagnostic.json')

def key(r):
    return (str(r.get('date') or ''), str(r.get('track') or ''), int(r.get('race_no') or 0))

def main():
    if not V6.exists() or not V7.exists():
        raise SystemExit('V6/V7 scored replay missing')
    a=json.loads(V6.read_text())
    b=json.loads(V7.read_text())
    am={key(r):r for r in a.get('races',[])}
    bm={key(r):r for r in b.get('races',[])}
    changed=[]; new_hits=[]; lost_hits=[]
    for k in sorted(set(am)|set(bm)):
        x=am.get(k,{}); y=bm.get(k,{})
        fields={
          'decision':(x.get('decision'),y.get('decision')),
          'axis':(x.get('axis_horse_no'),y.get('axis_horse_no')),
          'main_partners':(x.get('main_partners'),y.get('main_partners')),
          'holes':(x.get('holes'),y.get('holes')),
          'tickets':(x.get('tickets'),y.get('tickets')),
          'trio_hit':(bool(x.get('trio_hit')),bool(y.get('trio_hit'))),
        }
        diff={n:v for n,v in fields.items() if v[0]!=v[1]}
        if diff:
            row={'date':k[0],'track':k[1],'race_no':k[2],'diff':diff}
            changed.append(row)
        if not bool(x.get('trio_hit')) and bool(y.get('trio_hit')):
            new_hits.append({'date':k[0],'track':k[1],'race_no':k[2]})
        if bool(x.get('trio_hit')) and not bool(y.get('trio_hit')):
            lost_hits.append({'date':k[0],'track':k[1],'race_no':k[2]})
    payload={
      'source':'V6 no-style vs V7 pre-target-style sealed replay',
      'changed_races':len(changed),
      'new_hits':len(new_hits),
      'lost_hits':len(lost_hits),
      'new_hit_races':new_hits,
      'lost_hit_races':lost_hits,
      'changes':changed,
      'v6_summary':a.get('summary',{}),
      'v7_summary':b.get('summary',{}),
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2))
    print(json.dumps({k:payload[k] for k in ('changed_races','new_hits','lost_hits')},ensure_ascii=False))

if __name__=='__main__':main()
