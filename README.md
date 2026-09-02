# JRA Horse Big Data Updater / JRA AI

JRA公式情報を基準に、馬データ更新・レース週の出走馬展開・純予想・予想封印・市場判断・結果取得・PDCAまでを分離しながら一本の運用フローとして管理するリポジトリです。

## 正規運用フロー

```text
JRA公式データ取得
  ↓
馬マスター更新
  ↓
レース週の出走馬展開
  ↓
純予想（人気・オッズ・結果を使用しない）
  ↓
予想封印 / SHA256
  ↓
独立した市場・EVゲート
  ↓
最終買い目
  ↓
結果取得
  ↓
採点
  ↓
PDCA
  ↓
馬マスターへ結果反映
```

正規構成の機械可読マニフェストは `config/system_architecture.json`、監査結果は `status/system_architecture.json` を正とします。

## 独立機構

以下は正規フローと接続しますが、責務と書き込み領域を分離します。

- **市場・オッズ**: `jra-market-timing.yml`。予想封印済みレースだけを対象にし、能力順位を書き換えません。
- **モデル検証**: `validate-jra-model.yml`。読み取り専用で、本番予想へ書き込みません。
- **モデル認定**: `audit-oral-v6-certification.yml`。Golden Case・漏洩・再現性を独立監査します。
- **辞書/サイト**: `build-word-dictionary.yml` / `deploy-management-erp.yml`。競馬モデル状態と分離します。
- **緊急修復**: `repair-horse-master-integrity.yml`。通常フロー外の手動経路です。

競馬ワードは、JRA公式「競馬用語辞典」と「海外競馬英和辞典」を最優先ソースとして定期取得します。用語・読み・分類・出典URLを保持し、JRAの説明文は大量転載せず、このサイト独自の短い案内文と公式出典リンクを表示します。トップページは自動用語リンクの対象外です。

## Active GitHub Actions

Active Actionsは正規運用に必要な11本だけです。

- `post-jra-meeting-update.yml`
- `register-upcoming-new-horses.yml`
- `horse-master-maintenance.yml`
- `race-week-prediction-seal.yml`
- `jra-market-timing.yml`
- `validate-jra-model.yml`
- `audit-oral-v6-certification.yml`
- `build-word-dictionary.yml`
- `deploy-management-erp.yml`
- `repair-horse-master-integrity.yml`
- `system-architecture-audit.yml`

過去のV2〜V14検証、72R再生、診断、バックフィル、一回限りのWorkflowは `.github/workflow-archive/` に保存し、Actionsとしては起動しません。検証コードや証跡自体は削除していません。

Active Workflowから実行を許可するPythonファイルは、`config/system_architecture.json` の `active_workflow_script_policy` にWorkflow単位で明示します。Workflowへスクリプトを追加・削除したのに許可表を更新していない場合、構成監査は失敗します。これにより、同じ `src/` に保存されている過去実験・診断コードが正規運用へ暗黙に再接続されることを防ぎます。

## データ更新の書き込み整理

- 馬マスター関連は `horse-data-writes` で直列化します。
- 市場監視は `market-status-writes` で独立します。
- 辞書生成は `site-dictionary-writes` で独立します。
- Pages公開は `pages` で独立します。
- 市場監視は状態が変わらない限りGit commitを作りません。

## 純予想と市場情報のファイアウォール

`PURE_PREDICTION` では、人気・オッズ・払戻・対象レース結果を入力に使用しません。予想結果を封印した後にのみ市場層へ渡します。

現在の市場層は封印済みレースだけを受け取る接続まで実装済みです。実オッズ/EVデータが未接続の場合は `MARKET_DATA_PENDING` とし、オッズやEVを推測して最終買い目を作りません。

## 馬データ方針

- 架空馬を生成しない
- JRA公式で確認した馬のみ登録
- 馬名/馬IDを重複排除
- 馬マスターは軽量に保ち、実際に出走する馬だけレース週詳細を展開
- 騎手はレース単位の情報であり馬の固定基礎情報には保持しない
- 新馬のみデビュー前に軽い血統・調教メモを保持可能
- 失敗時に完成済みデータを無条件で全置換しない

## 管理・監査

`system-architecture-audit.yml` は以下を自動確認します。

- Active Workflowが許可された構成だけか
- 正規フローに欠落がないか
- 馬データ書き込みが直列化されているか
- 市場/検証/辞書/修復の独立性が維持されているか
- 純予想の市場・結果ファイアウォールが存在するか
- 市場層が封印済み予想だけを受け取るか
- Active Workflowが許可済みの本番・独立監査スクリプトだけを実行するか

この監査の `PASS` は構成・接続・独立性の合格を意味し、予測精度やライブオッズ取得成功を意味しません。
