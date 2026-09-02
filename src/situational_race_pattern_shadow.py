#!/usr/bin/env python3
from __future__ import annotations


def _f(v, d=0.0):
    try:
        return float(v)
    except Exception:
        return d


def classify_situation(race, q, durability, intrusion):
    """Research-only race regime classifier using pre-seal information only."""
    top = q[:8]
    if not top:
        return {'status': 'RESEARCH_ONLY', 'pattern': 'STANDARD', 'signals': ['no ranked runners'], 'proposed_strategy': 'production core only'}

    starts = [_f(x.get('starts_before')) for x in top]
    avg_starts = sum(starts) / len(starts)
    unc = [_f(x.get('uncertainty'), 1.0) for x in top]
    avg_unc = sum(unc) / len(unc)
    scores = [_f(x.get('score')) for x in top]
    spread_top5 = max(scores[:5]) - min(scores[:5]) if len(scores) >= 5 else (max(scores) - min(scores) if len(scores) > 1 else 0.0)
    styles = [str(x.get('running_style') or x.get('style') or 'UNKNOWN') for x in top]
    front = sum(s in ('ESCAPE', 'FRONT') for s in styles)
    stable = sum(_f(x.get('show_rate_prior'), .3) >= .38 and _f(x.get('uncertainty'), 1) <= .60 for x in top[:5])

    signals = [
        f'avg_starts={avg_starts:.2f}',
        f'avg_uncertainty={avg_unc:.3f}',
        f'top5_score_spread={spread_top5:.3f}',
        f'front_style_count_top8={front}',
        f'intrusion_candidates={len(intrusion)}',
        f'stable_top5_count={stable}',
    ]

    if avg_starts < 1.5 or avg_unc >= .82:
        pattern = 'LOW_EVIDENCE'
        strategy = '軸信頼度を下げ、証拠不足ならPASSを優先。新馬・少出走専用情報が揃う場合だけ別機構で補う。'
    elif durability.get('status') == 'HIGH' and durability.get('gap_to_second', 0) >= 3.0:
        pattern = 'DOMINANT_AXIS'
        strategy = '軸中心を許容しつつ、相手は脚質・条件・3着侵入の役割分散を強める。'
    elif spread_top5 < 2.0 and avg_unc >= .55:
        pattern = 'FLAT_CHAOS'
        strategy = '単一軸を避け、上位群生存・展開反転・PASS判定を強める。'
    elif front >= 4:
        pattern = 'FRONT_PRESSURE'
        strategy = '前同士の競合を減点し、番手・差しの展開耐性と3着侵入を別評価する。'
    elif front <= 1 and any(s in ('ESCAPE', 'FRONT', 'STALK') for s in styles[:4]):
        pattern = 'LOW_PACE_FRONT'
        strategy = '能力ガードを維持しながら前受け・位置取り再現性を上乗せする。'
    elif len(intrusion) >= 2:
        pattern = 'THIRD_PLACE_VOLATILE'
        strategy = '5〜10番手の3着侵入候補を厚くし、三連複の3列目カバー改善を影モデルで比較する。'
    elif stable >= 3:
        pattern = 'STABLE_TOP_CLUSTER'
        strategy = '上位安定群を共通候補コアとして扱い、券型変換と着順差だけを最適化する。'
    else:
        pattern = 'STANDARD'
        strategy = '現行の共通予想コアをそのまま使用し、状況別上書きは行わない。'

    return {
        'status': 'RESEARCH_ONLY',
        'pattern': pattern,
        'signals': signals,
        'proposed_strategy': strategy,
        'production_override_applied': False,
        'integration_rule': '独立検証3回以上（推奨5回）＋同パターン300R以上＋最終未見検証通過までは本番へ統合しない',
        'market_isolation': 'NO_ODDS_OR_POPULARITY_USED',
    }
