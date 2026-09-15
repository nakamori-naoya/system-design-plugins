---
name: discover-quality-requirements
description: 業務影響を観測点、指標、閾値、時間窓、検証方法を持つ品質要求へ落とす独立プレイブック。品質要求を発見したいときに使う。
---

# discover-quality-requirements

同梱の`playbook.yml`を公開入口とし、内部プラグイン`discover-quality-requirements`の同名スキルへ明示的にルーティングする。クラウドや製品は選定しない。

## 実行

1. `scripts/prepare.sh`で、このプレイブックと対応スキルが同じ配布パッケージ内にあることを検査する。
2. `playbook.yml`の`steps`に従い、grill、ground、`skill: discover-quality-requirements`、material、verify、write-docを順に実行する。
3. 成否にかかわらずcleanupを実行し、保存済み正本と参照資料を保持する。`scripts/resolve.sh`は公開入口と内部スキルの対応を機械可読なJSONとして確認する。

入力、出力、停止条件、非責務の詳細は、同梱内部スキル`skills/discover-quality-requirements/SKILL.md`を正本とする。

## 公開依存の実行契約

`settle` は、`requires` で宣言した `grill` の公開入口へ契約 v1 の入力YAMLの絶対パスを直接渡す。相手の設定解決は行わない。入力は `contract: grill/grill`、`version: 1`、`topic`、`context`（`purpose`・`audience`・`boundary`）、`questions`、`output_to` とし、参照素材がある場合だけ `grounding` に読み取り可能な通常ファイルの絶対パスを渡す。

依頼と参照資料からは決まらない問いを、前提が揃う順に `{id, question, recommendation}` で用意する。推奨回答には理由を含め、一問ずつ利用者の回答を待つ。入力と `output_to` は自分の `run_root` 内の未使用パスを割り当て、作成前に後片付け対象へ登録する。外部から渡された参照素材は後片付け対象にしない。

回答待ち・一覧の合意待ちには後続へ進まない。対話と一覧への明示合意が完了したら、入力に指定した `output_to` のYAMLを読み、公開契約の `contract`・`version`・`status` と配列の形式を照合する。`completed` の `decisions` と `open_questions` はID、理由、`open`／`withdrawn` を保持したまま `ground` 入力の `grill` に渡す。未決を要求、閾値、仮説、設計決定へ昇格させない。`failed`、出力未保存、契約不一致では停止理由を返し、後片付けだけを行う。

`ground`、同名の一責務skill、`material`、`verify`を順に実行する。`verify`が`unresolved`を返した場合もwrite-docを実行し、未決状態のMarkdown正本を保存する。その正本とplaybook出力には`status: unresolved`、`open_questions`、`handoff.ready: false`を残し、未決を確定前提として後続へ渡さない。

### 資料の保存（write-doc 契約 v2）

開始時に保存先 `document_destination` を確認する。新規作成は `{output_directory: <既存の書き込み可能な絶対ディレクトリ>}`、更新は `{update_target: <既存Markdownの絶対パス>}` のどちらか一方だけを受け取る。未指定、相対パス、両方式の併記では一問で確認して停止し、保存先を補わない。

`write-doc/write-doc` 契約 v2 の公開入口へ、`document` 工程の入力を直接渡す。`material` は生成済み素材の絶対パスを `[{kind: file, path: <materialの絶対パス>}]` に変換する。`document_type: quality-requirements` を維持し、新規作成は `output_directory` と `name: quality-requirements.md`、更新は `update_target` だけを加える。日本語の本文題名は素材に保持する。更新時は `name` と `output_directory` を渡さない。入力・出力用の中間ファイルや相手用の実行設定は作らず、返された `status` と `path` または `reason` を直接受け取る。

`status: completed` は保存成功だけを示す。返却された絶対パスの文書を読み、素材のID、根拠、数値、未決、`handoff`、後続成果物への追跡が保持されていることを確認してから `quality_document_path` へ割り当てる。検証結果の `ready`／`unresolved` を `completed` に置き換えない。保存成功と内容保持を確認できた場合だけ `contract.outcome` を返す。

`status: failed`、不正な戻り値、保存後の欠落では後続へ成功を返さず、`status: failed`、停止理由、検証時点の未決、`handoff.ready: false` を返す。部分保存のパスが理由に含まれる場合は報告し、完成資料のパスへ昇格させない。後片付け前に結果をメモリへ保持する。write-docの内部構成にはアクセスしない。

## 後片付け

`always_run: true`の最終工程で、このplaybookが作った一時成果物だけを削除する。参照資料、他playbookの一時領域、保存済みMarkdown正本は削除しない。所有を証明できないpathがあれば削除せず停止する。
