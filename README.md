# JRA Horse Big Data Updater

JRA公式の年度別全成績から出走馬名簿を構築し、プロフィール・競走履歴を段階的に補完する独立更新機構です。

## 実行

- 定期実行: 毎週月曜 06:00（日本時間）
- 手動実行: GitHub Actions の **Update JRA horse big data**
- 中断再開: `status/checkpoint.json`
- ChatGPTを開いていなくてもGitHub Actionsが動作

## モード

- `registry`: 年度別全成績から固有馬名簿を再構築
- `profile`: 未取得プロフィールをバッチ補完
- `history`: 未取得履歴をバッチ補完
- `all`: 上記を順番に実行

現行版はregistryを実装済みです。profile/historyは処理待ちキューを保持し、JRA馬ID解決モジュール追加後に同じ定期実行へ統合します。

## Google Sheets連携

Repository Secret `GOOGLE_SERVICE_ACCOUNT_JSON` を登録すると、`config.json`で指定したSpreadsheetへ安全にupsertします。既存シートの全消去は行いません。サービスアカウントのメールアドレスには対象シートの編集権限が必要です。Secret未設定でもCSVとチェックポイントは更新されます。

## 品質ルール

- 架空馬を生成しない
- JRA公式年度別成績PDFで確認した馬だけを登録
- 馬名重複排除
- 出典PDF、取得時刻、処理状態を保持
- 既存データを全消去しない
- 失敗時は完成済みCSVを置き換えない
