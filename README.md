# システム設計

要件と非機能要件を先に資料にし、その根拠からクラウドのインフラ構成を決める、Claude Code と Codex の両方で使える plugin です。公開するのは `system-design@system-design` の一つの package で、入口は二つあります。

`discover-requirements` は、要件（requirements-discovery）と非機能要件（non-functional-requirements）のうち依頼された型の資料を一本、作るか深めます。作るか深めるかは同じ入口で扱い、grill で何を問うかで分けます。要件は誰が何を得るかと範囲を、非機能要件は守る順位、規模と負荷の値、速さや復旧や費用の目標を持ち、同じ値を二つの資料に写しません。

`design-cloud-architecture` は、利用者が指定したプロバイダー（`aws` か `gcp`）と二つの資料から、構成図を先頭に置き、選んだ理由と比べた候補、障害時の振る舞い、費用の見込みを持つインフラ構成の資料を作ります。プロバイダーは推測せず、指定が無ければ止まります。

どちらの資料も、結論と図を先頭に置いた、今のあるべき姿だけを書きます。要求ごとの ID、追跡の表、決定の番号、検討の経過は書きません。図は draw.io で描き、定義を埋め込んだ `.drawio.svg` として資料の `.assets/` に置くので、draw.io で開いて直せます。どちらの入口も資料を write-doc で保存し、保存した資料に検査を一回かけます。検査が読むのは、write-doc の各型の template にある「検査が読む目印」（題名と冒頭の本文、図のファイルとその置き場、Mermaid が無いこと）だけで、見出しの文言は読みません。資料の中身が妥当かは、エージェントが読んで評価します。語は bdd-discovery-and-formulation の業務知識の資料が持つユビキタス言語に従い、この plugin は独自の用語集を持ちません。

この plugin は、プロダクトの北極星や戦略、業務知識や BDD、画面、API、データモデル、DDL、IaC を作りません。外部の package には、grill と write-doc の公開入口としてだけ依存します。

## 配布構造

Codex の marketplace は `.agents/plugins/marketplace.json`、Claude Code の marketplace は `.claude-plugin/marketplace.json`、配布する package は `plugins/system-design` です。

## 検証

`bash scripts/validate.sh` は、兄弟 checkout の `../harness-tools` による package の構造検査、各入口の SKILL.md から自分の reference へ届くことと兄弟の入口の path を書かないことの検査、検査 script の正例と反例の test を確かめます。正例は `tests/fixtures/` にあります。harness-tools の checkout が無ければ止まります。CI は `.github/workflows/validate.yml` から同じ command を実行します。
