#!/usr/bin/env python3
from __future__ import annotations
import json, hashlib
from pathlib import Path

from build_live_sealed_predictions import _new_horse_analysis

OUT=Path('docs/data/live_predictions_sealed.json')
STATUS=Path('status/live_prediction_seal.json')


def _missing_evidence(h):
    ev=h.get('new_horse_evidence') or {}
    missing=[]
    if not str(ev.get('sire') or '').strip(): missing.append('sire')
    if not str(ev.get('damsire') or '').strip(): missing.append('damsire')
    if not str(ev.get('trainer') or '').strip(): missing.append('trainer')
    if not str(ev.get('jockey') or '').strip(): missing.append('jockey')
    # Sire is a mandatory anchor for the current debut-horse model. If sire is
    # unavailable, or fewer than two of the four core fields exist, assigning a
    # numerical ability rank would create false precision.
    present=4-len(missing)
    return missing if ('sire' in missing or present < 2) else []


def main():
    if not OUT.exists():
        return
    payload=json.loads(OUT.read_text(encoding='utf-8'))
    changed=0
    unrated_total=0
    for race in payload.get('races') or []:
        analysis=race.get('analysis') or {}
        if analysis.get('model_version')!='NEW_HORSE_DEDICATED_V1':
            continue
        ranked=[]
        unrated=[]
        for h in race.get('ranked_snapshot') or []:
            missing=_missing_evidence(h)
            if missing:
                x=dict(h)
                x['score']=None
                x['evaluation_status']='UNRATED_DARK_HORSE'
                x['unrated_reason']='新馬専用機構の主要情報不足のため能力順位を付けない'
                x['missing_evidence']=missing
                unrated.append(x)
            else:
                ranked.append(h)
        if not unrated:
            race['unrated_dark_horses']=[]
            analysis['unrated_dark_horses']=[]
            analysis['excluded_zone_label']='未評価馬（完全ダークホース）'
            continue
        ranked.sort(key=lambda x: (-(float(x.get('score') or 0)), int(x.get('n')) if str(x.get('n') or '').isdigit() else 999))
        safe={k:race.get(k) for k in ('race_id','date','track','race_no','race_name','surface','distance_m')}
        safe['ranked_snapshot']=ranked
        new_analysis=_new_horse_analysis(safe)
        new_analysis['unrated_dark_horses']=unrated
        new_analysis['excluded_zone_label']='未評価馬（完全ダークホース）'
        new_analysis['excluded_zone_policy']='能力不足ではなく情報不足。順位・通常買い目から除外し、未知リスクとして別監視する。'
        race['ranked_snapshot']=ranked
        race['champion_ranked_snapshot']=ranked
        race['unrated_dark_horses']=unrated
        race['analysis']=new_analysis
        changed+=1
        unrated_total+=len(unrated)
    payload['new_horse_unrated_zone_enabled']=True
    payload['new_horse_unrated_race_count']=changed
    payload['new_horse_unrated_horse_count']=unrated_total
    hash_input=json.dumps({k:v for k,v in payload.items() if k not in ('generated_at','prediction_hash_sha256')},ensure_ascii=False,sort_keys=True,separators=(',',':'))
    payload['prediction_hash_sha256']=hashlib.sha256(hash_input.encode()).hexdigest()
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    if STATUS.exists():
        st=json.loads(STATUS.read_text(encoding='utf-8'))
        st['prediction_hash_sha256']=payload['prediction_hash_sha256']
        st['new_horse_unrated_zone_enabled']=True
        st['new_horse_unrated_race_count']=changed
        st['new_horse_unrated_horse_count']=unrated_total
        STATUS.write_text(json.dumps(st,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'new_horse_unrated_zone_enabled':True,'races':changed,'horses':unrated_total},ensure_ascii=False))

if __name__=='__main__':
    main()
