# テストデータの契約

各公開スキルは、Markdown資料の正例 `tests/fixtures/<入口>/success.md` を1本持つ。testは正例を文字列置換して反例・境界例を作り、入口の検査scriptへ標準入力で渡す。fixture fileを書き換えず、一時fileも作らない。

- `discover-requirements/success.md`: 要求発見資料（上流なし）。`status: unresolved`。
- `discover-workload-model/success.md`: 利用負荷モデル資料。`--upstream` に要求発見fixture。
- `discover-quality-requirements/success.md`: 品質要求資料。`--upstream` に要求発見・利用負荷fixture。
- `design-cloud-architecture/success.md`: クラウドアーキテクチャ資料。`--provider aws`、`--upstream` に上流3 fixture。
- `terminology/success.md`: 共有用語定義の正例。要求発見fixtureの `## 用語` が参照し、`terminology.py` が同じ所在・版・推奨用語名・コマンド／クエリの操作名を検査する。

4本は同じ架空の対象（申請結果確認）で上流→下流の参照が閉じている。案件固有の値を既定値や例の正解にしない。fixtureの存在を実モデル評価の成功として扱わない。

## 検査scriptの契約（4入口共通）

- 基準資料: write-docの各文書型templateが定める記法と、`--upstream` の上流資料が定義するID。
- 入力: 標準入力の本文。`--upstream`（複数可）。`design-cloud-architecture` は `--provider`。
- 正規化: HTMLコメントを除き、H2で節を切り、表を見出し行・本文行に分け、`<接頭辞>-<数字>` のIDを拾う。
- 合格述語・診断・正例・反例・境界例・意味評価として残す範囲: 各入口の `references/*-contract.md`「基準資料の記法と機械検査の宣言」。
- 出力: 終了code 0でstdoutに `verified: true`、`status`（`ready` / `unresolved`）、ID一覧のJSON。不合格は終了code 2でstderrに `FAIL: <理由>`。

## grill → 検査script → write-doc の受け渡し検査

- 基準資料: 各公開入口の`playbook.yml`と、grill / write-docの公開契約（`playbook:` でだけ呼ぶ）。
- 入力: 4入口のYAML宣言。実モデルもgrillもwrite-docも呼ばない。
- 正規化: YAMLをJSONへ変換し、`requires`、`inputs`、`steps`を読む。
- 合格述語: `requires`に`grill`と`write-doc`があり、`playbook: grill`の工程が`verify`（入口の`scripts/`）より前、`playbook: write-doc`の工程が`verify`より後にあり、`input.document_type`が入口ごとの文書型と一致し、`inputs`に`references`があり、JSON資料を保存する工程が無い。
- 診断: 違反した入口・フィールドを示す。
- 正例: 4入口。反例: `requires`無し、`verify`より前のwrite-doc、別の文書型、`skill:`での呼び出し。
- 境界例: 本文と保存先は実行時の値なので検査しない。write-docの`completed`を設計の`ready`に使わない。
- 意味評価: 渡す本文が検査済み本文のID・根拠・数値・未決・図を保っているかは、agentが保存後の資料を読み戻して確認する。

## 保全している過去の資産

- `legacy-json/`: 2026-09-16以前のJSON資料（`schema_version: 2`）のfixtureと意味評価シナリオ。現行testからは参照しない。詳細は `legacy-json/README.md`。
- `runtime-config/`: 撤去した設定解決経路（`prepare.sh` / `resolve.sh`）の設定テストデータ。現在どのtestからも参照されない。資産の削除は別の明示された変更として扱うため保持している。
