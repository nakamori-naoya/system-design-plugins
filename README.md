# システム設計

要件、利用負荷、品質要求を先に資料にし、その根拠からクラウドアーキテクチャを決める、Claude Code と Codex の両方で使える plugin です。公開するのは `system-design@system-design` の一つの package で、入口は二つあります。

`discover-requirements` は、要件（requirements-discovery）、利用負荷（workload-model）、品質要求（quality-requirements）のうち依頼された型の資料を一本、作るか深めます。作るか深めるかは同じ入口で扱い、grill で何を問うかで分けます。三つの型は一つの判断を一つの型だけが持つように分けてあり、値と偏りは利用負荷が、守る性質と頻度の制限は品質要求が持ち、要件は因果の要約とその ID の参照だけを持ちます。

`design-cloud-architecture` は、利用者が指定したプロバイダー（`aws` か `gcp`）と三つの資料から、代替案と比べた選定、ADR、障害と縮退の経路、編集できる構成図を持つクラウドアーキテクチャの資料を作ります。プロバイダーは推測せず、指定が無ければ止まります。

どちらの入口も、資料を write-doc で保存し、保存した資料に検査を一回かけます。検査が読むのは write-doc の各型の template にある「検査が読む目印」（追跡の表、ID、根拠の状態の値、構成図のブロック）だけで、見出しの文言は読みません。資料の中身が妥当かは、エージェントが読んで評価します。語は bdd-discovery-and-formulation の業務知識の資料が持つユビキタス言語に従い、この plugin は独自の用語集を持ちません。

この plugin は、プロダクトの北極星や戦略、業務知識や BDD、画面、API、データモデル、DDL、IaC を作りません。外部の package には、grill と write-doc の公開入口としてだけ依存します。

## 配布構造

Codex の marketplace は `.agents/plugins/marketplace.json`、Claude Code の marketplace は `.claude-plugin/marketplace.json`、配布する package は `plugins/system-design` です。

## 検証

`bash scripts/validate.sh` は、兄弟 checkout の `../harness-tools` による package の構造検査、各入口の SKILL.md から自分の reference へ届くことと兄弟の入口の path を書かないことの検査、検査 script の正例・反例・境界例の test、write-doc の見本（兄弟 checkout の `../write-doc-plugins`）が四つの検査を通ることを確かめます。harness-tools か write-doc の checkout が無ければ、fixture で代用せずに止まります。CI は `.github/workflows/validate.yml` から同じ command を実行します。
