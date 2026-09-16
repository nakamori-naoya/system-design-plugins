> 作業を始める前に、workspace正本入口 `/Users/naoya-nakamoriq/Documents/Github/harness-pluginsv2/AGENTS.md` を読み、そこから指定される共通規約とこのrepository固有の規則を適用する。

# AGENTS.md

このrepositoryは、要求・利用負荷・品質要求を根拠付きで発見し、その成果からクラウドアーキテクチャを設計するsourceである。

- marketplaceへ公開するインストール対象は`system-design` package 1件だけにする。
- package manifestは`discover-requirements`、`discover-workload-model`、`discover-quality-requirements`、`design-cloud-architecture`の自己完結skill 4件を`skills/`から直接公開する。設定解決script、外側のrouting playbook、入口別runtime manifestを持たない。各skill直下の`playbook.yml` v2を工程順序の正本とし、同じagentが`agent_work: invoking_agent`の工程を宣言順に実行し、日本語Markdown正本は同じagentが本文を`kind: text`で公開playbook `write-doc`へ渡して保存する。外部依存は`requires`に宣言した`write-doc`だけである。
- 各`SKILL.md`は、目的、入力契約、判断基準（観察対象と二者択一の述語）、手順、停止条件、出力契約を実行agentが判断に使える形で持つ。見出しの形や個数は固定せず、機械検査にもしない。scriptは入口directory相対のpathで示し、入力・出力・失敗の観測・失敗時の扱いを宣言する。保存できる状態と、後続判断へreadyな状態を混同しない。
- 確定事実、合意済み決定、仮説・推定、未確認事項を区別し、出典、観測時点、単位、計算式、影響先IDを後続へ残す。根拠のない値やcloud仕様を確定事項として補完しない。
- `design-cloud-architecture`はクラウド・サービス選定、代替案比較、ADR、編集可能なインフラ構成図、要求トレーサビリティ、検証計画を必須成果物とする。要求や品質目標の独断変更、論理DB設計、IaC実装、deployは行わない。
- `design-cloud-architecture`は利用者が明示した`provider`（`aws`または`gcp`）を公開入力として受け取り、設定ファイルや既定値を持たない。未指定・不正値は一問で確認して停止し、指定の根拠を合意済み制約として正本へ追跡する。
- 既存BDD repositoryは利用者が資料を渡す境界で接続する。既存BDDの成果物形式、内部skill、script、install cacheを変更または直接参照しない。
- 共通referenceは根拠状態、ID、追跡、検証などskill間の受渡し契約だけを所有する。各skill固有の意味判断を共通層へ移さない。
- fixtureは正常系、非対象、境界事例を持ち、入力と期待する分岐・停止・出力を実行前に定義する。fixtureの存在を実モデル評価の成功として扱わない。案件固有の値（特定サービスの用語、閾値、採用技術）を既定値や例の正解にしない。
- install cache、隣接repository、外部公開、pushは変更しない。このsource treeを正本として編集する。
- 変更後は`bash scripts/validate.sh`を実行する。未実装の公開skillがある間は失敗が正しく、検査を緩めて成功させない。
