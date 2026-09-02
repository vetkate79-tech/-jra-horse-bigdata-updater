#!/usr/bin/env python3
from __future__ import annotations

EXPERTS = {
    'STRUCTURAL': '長期能力・クラス・距離/馬場適性を重視',
    'FORM': '直近3〜5走・上がり・状態変化を重視',
    'PACE': '脚質構成・前圧・位置取り再現性を重視',
    'AXIS_SURVIVAL': '多少の前提崩れでも3着以内へ残る耐久性を重視',
    'INTRUSION': '5〜10番手からの3着侵入候補を重視',
    'STABILITY': '上位候補の再現性・不確実性の低さを重視',
}

PATTERN_WEIGHTS = {
    'LOW_EVIDENCE': {'STRUCTURAL': .35, 'FORM': .10, 'PACE': .05, 'AXIS_SURVIVAL': .20, 'INTRUSION': .05, 'STABILITY': .25},
    'DOMINANT_AXIS': {'STRUCTURAL': .25, 'FORM': .15, 'PACE': .10, 'AXIS_SURVIVAL': .30, 'INTRUSION': .10, 'STABILITY': .10},
    'FLAT_CHAOS': {'STRUCTURAL': .15, 'FORM': .15, 'PACE': .20, 'AXIS_SURVIVAL': .10, 'INTRUSION': .25, 'STABILITY': .15},
    'FRONT_PRESSURE': {'STRUCTURAL': .15, 'FORM': .15, 'PACE': .30, 'AXIS_SURVIVAL': .10, 'INTRUSION': .20, 'STABILITY': .10},
    'LOW_PACE_FRONT': {'STRUCTURAL': .20, 'FORM': .15, 'PACE': .25, 'AXIS_SURVIVAL': .20, 'INTRUSION': .10, 'STABILITY': .10},
    'THIRD_PLACE_VOLATILE': {'STRUCTURAL': .15, 'FORM': .15, 'PACE': .15, 'AXIS_SURVIVAL': .10, 'INTRUSION': .35, 'STABILITY': .10},
    'STABLE_TOP_CLUSTER': {'STRUCTURAL': .25, 'FORM': .15, 'PACE': .10, 'AXIS_SURVIVAL': .20, 'INTRUSION': .05, 'STABILITY': .25},
    'STANDARD': {'STRUCTURAL': .25, 'FORM': .20, 'PACE': .15, 'AXIS_SURVIVAL': .20, 'INTRUSION': .10, 'STABILITY': .10},
}


def route_ensemble(situational):
    pattern = str((situational or {}).get('pattern') or 'STANDARD')
    weights = PATTERN_WEIGHTS.get(pattern, PATTERN_WEIGHTS['STANDARD'])
    return {
        'status': 'RESEARCH_ONLY',
        'architecture': 'MIXTURE_OF_EXPERTS_SHADOW_V1',
        'race_pattern': pattern,
        'expert_weights': weights,
        'experts': EXPERTS,
        'fusion_rule': '各専門モデルの候補順位・軸耐久・3着侵入評価を重み付きで統合し、専門家間の不一致が大きいレースは信頼度を下げる。',
        'production_override_applied': False,
        'promotion_rule': '専門モデル単体または組合せが独立検証3回以上（推奨5回）で再現し、500R/8週の大母集団ゲートと最終未見検証を通過した場合のみ統合候補。',
        'market_isolation': 'NO_ODDS_OR_POPULARITY_USED',
    }
