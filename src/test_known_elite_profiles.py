#!/usr/bin/env python3
import json
import collect_active_elite_horses as elite

# JRA official profiles currently showing GIII history and 20,000,000 yen
# flat acquired prize. These are parser regression fixtures, not hardcoded
# production catalog entries.
CASES=[
 {'horse_id':'pw01dud102024105568/6D','expected_min_prize':20_000_000,'expect_grade':'G3'},
 {'horse_id':'pw01dud102023103184/93','expected_min_prize':20_000_000,'expect_grade':'G3'},
]

out=[]
for case in CASES:
    c={'horse_id':case['horse_id'],'horse_name':'','candidate_sources':{'KNOWN_JRA_REGRESSION'}}
    p=elite.parse_profile(c,elite.request_profile(case['horse_id']))
    assert p['horse_name'],f"name unresolved {case['horse_id']}"
    assert p['active'] is True,f"expected active {p['horse_name']}"
    assert (p['flat_acquired_prize_yen'] or 0)>=case['expected_min_prize'],p
    assert p['current_flat_class']=='OPEN',p
    assert case['expect_grade'] in p['graded_experience'],p
    out.append({'horse_name':p['horse_name'],'horse_id':p['horse_id'],'active':p['active'],'flat_acquired_prize_yen':p['flat_acquired_prize_yen'],'graded_experience':p['graded_experience'],'graded_starts':p['graded_starts'][:3]})
print(json.dumps(out,ensure_ascii=False,indent=2))
