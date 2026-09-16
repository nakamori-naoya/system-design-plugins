# system-design の eval

4つの公開入口（`discover-requirements` / `discover-workload-model` / `discover-quality-requirements` / `design-cloud-architecture`）は、問いの一覧を `grill` へ `playbook:` で渡して利用者と対話してから正本を書く。`claude -p`（対話なし・tool無し）の1往復では対話・検査・保存を観測できないので、自動実行は行わず手動evalを記録する。

## 手動evalの手順（代表1本: `discover-requirements`）

| 項目 | 内容 |
|---|---|
| 実施者 | 利用者役1名（Claude Code または Codex の実セッションで `discover-requirements` を呼ぶ） |
| 入力 | 依頼文「会議室予約の社内システムの要求を整理して。要求源はこの依頼文だけ。DBはPostgreSQLにしたい」。追加資料は渡さない。保存先は既存の書き込める一時directoryの絶対pathと `.md` 名 |
| 利用者の発言 | grillの問いに対し、受益者は「総務担当と社員」、範囲外は「来客管理」と答え、残りは推奨のまま受け入れて一覧へ合意する |
| 観測1 | 「PostgreSQL」が要求ではなく制約・仮説・設計案のどれかに分類され、要求として書かれない |
| 観測2 | 事実・合意済み決定・仮説・未決が資料上で区別され、要求源の参照位置と観測時点（ここでは「依頼本文」）が記録される |
| 観測3 | 問いが一問ずつ推奨付きで6問以下で出て、grill が返した `decisions` は本文の該当箇所へ確定した根拠として、`open_questions` は推奨を仮置きした `hypothesis` と「後続設計で決める論点」の `REQ-HYP-` / `REQ-OQ-` の行として本文へ反映される（独自の一覧確認・回答待ちの対話をしない） |
| 観測4 | Markdown資料が唯一の正本として保存され、JSON正本は作られない。保存前に `scripts/` の検査が標準入力の本文で通り、失敗を成功扱いしていない |
| 記録 | 会話の全文、保存された資料、観測1〜4の根拠箇所の引用を `evals/runs/<YYYY-MM-DD>/discover-requirements-manual.md` に保存する。観測できなかった項目は「未観測」と書き、合否にしない |
