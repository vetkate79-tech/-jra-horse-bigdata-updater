# JRA競馬AI 運用・引継ぎ

更新日: 2026-09-06

## 1. このリポジトリの役割

このリポジトリが現行の本番運用オーナーです。
Replitは本番運用に必須ではありません。コード作成・修正・一時検証に利用してもよいですが、Replit停止で本番ジョブが止まる設計は禁止します。

## 2. 最上位原則

1. 運用継続性を最優先する。
2. 人気・オッズは純予想の能力順位へ入れない。
3. 純予想を封印した後だけ市場情報を読む。
4. 取得失敗を0・空値で成功扱いしない。
5. 予想・市場・結果・PDCAは別レイヤーで保存する。
6. 確定データは上書きだけで消さず、履歴を残す。
7. 変更はGit履歴で追跡し、ロールバック可能にする。
8. 特定AI・IDE・ホスティングへ属人化しない。

## 3. 本番フロー

JRA公式データ取得
→ 馬マスター更新
→ レース週出走馬展開
→ 純予想
→ 予想封印
→ 独立Market Layer
→ 最終購入判断
→ 結果取得
→ 採点
→ PDCA
→ 馬マスター反映

## 4. 市場レイヤー

本番ジョブ: `.github/workflows/jra-market-timing.yml`

通常取得:
- 09:00 JST
- 13:00 JST

watchdog:
- 09:25 JST
- 13:25 JST

watchdogは該当スロットの保存済みスナップショットが存在する場合は取得を重複実行しません。

取得処理:
- `src/collect_current_market_odds.py`
- JRA公式出馬表/オッズPOST経路を使用
- `market_layer_only=true`
- `pure_prediction_mutated=false`

現行出力:
- `docs/data/current_market_odds.json`
- `status/current_market_odds.json`
- `docs/data/market-odds-history/YYYY-MM-DD/09/`
- `docs/data/market-odds-history/YYYY-MM-DD/13/`

2026-09-06 10:18 JSTの実測では36R・馬別単勝491件を取得。

## 5. 公開・ERP

本番公開はこの公開リポジトリのGitHub Pagesを使用します。
`.github/workflows/deploy-management-erp.yml` が `docs/` を配信します。

privateの `vetkate79-tech/-jra-horse-data-collector-web` は引継ぎ・移行・バックアップ用であり、本番の定期書き込みオーナーにはしません。二重実行・二重書き込みを避けます。

## 6. 障害時の確認順

1. GitHub Actionsの対象workflowが起動したか
2. workflow jobのどのstepで失敗したか
3. `status/*.json` の時刻・件数・error
4. JRA公式取得元のHTML/API構造変更
5. 保存先の履歴ファイルが消えていないか
6. 純予想hashが市場処理前後で変わっていないか

市場取得失敗時は予想を変更せず、市場データ不足として扱います。

## 7. 実行基盤を変える場合

GitHub Actions以外へ移す場合も、業務ロジックと入出力スキーマを維持してください。
変更対象はscheduler/runnerだけに限定し、Prediction CoreやMarket Layerの意味を変えません。

移行は旧系を止めてから開始せず、旧系と新系を並走して保存件数・hash・出力差分を確認してから切り替えます。

## 8. Replit

Replit依存の本番処理は0を目標とします。
Replit固有DB/Scheduler/Deploymentへ重要データを閉じ込めないでください。
