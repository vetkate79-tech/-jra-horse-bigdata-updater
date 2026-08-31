# AI答え合わせ・集合知バックグラウンド v1

## 公開UIフロー
1. 日付選択
2. 競馬場選択
3. レース選択
4. 賭け式選択
5. 買い目入力
6. AIに相談

## AI相談の返却
- 入力買い目が成立しやすい展開
- 崩れる展開
- 的中確率の目安（計算可能な場合のみ。未接続時は捏造しない）
- AIの純粋予想
- ユーザー予想とAI予想の一致点・相違点
- 必要に応じて注意点

## 最重要ファイアウォール
ユーザー入力はAI純粋予想より後に受け取る。純粋AI予想はユーザー入力・他ユーザー予想・人気・オッズから隔離する。

pure race data -> pure AI prediction -> seal
                                      |
user ticket --------------------------+--> comparison/advice response
                                      |
                                      +--> anonymous crowd store

匿名集合知データは純AIの能力順位へ直接投入しない。

## 保存イベント
`user-prediction-feedback-v1.json` の契約に従う。

最低保存項目:
- submission_id
- created_at
- anonymous_session_id
- race_id
- race_date
- track
- race_no
- bet_type
- normalized ticket_expression
- selected_horse_numbers
- pure_ai_prediction_id
- user_ticket_probability (算出できる場合のみ)

個人情報、メール、氏名、IPアドレスを分析キーとして保持しない。

## 結果確定後
race_id でJRA結果とJOINし、
- ticket_hit
- return_per_100yen
を追記する。

これにより、他ユーザーの予想を以下の研究に利用できる。
- 馬別支持率
- 券種別支持率
- 組み合わせ共起
- AIと集合知の一致率
- AIのみ正解 / 集合知のみ正解 / 両方正解
- 穴馬の早期発見率
- クラス別・競馬場別・券種別の集合知精度

## モデルへの昇格条件
集合知特徴は最初は weight=0。
OOSサンプル1000件未満では純AIへ一切寄与させない。
1000件以降も、時系列分割OOSで純AI単独より改善した場合だけ候補化する。
単発的中や直近成績だけで昇格させない。

## 推奨バックエンド
GitHub Pagesは静的サイトなので、全ユーザーの投稿を共有保存するAPIは別途必要。
推奨構造:

Browser -> POST /api/predictions -> serverless API -> DB
                              -> sealed pure AI JSON

API側必須処理:
- schema validation
- rate limit
- anonymous UUID
- race_id validation
- ticket normalization
- duplicate/spam suppression
- no PII logging policy
- result join worker

OpenAI等のLLMを利用する場合もAPIキーはブラウザへ置かず、必ずサーバー側から呼ぶ。

## 現在の段階
公開UIは先にこの入力フローへ変更する。
共有ビッグデータ保存はAPI/DB接続後に有効化する。
それまでは端末内localStorageをUIテスト用キューとして使い、共有データとしては扱わない。
