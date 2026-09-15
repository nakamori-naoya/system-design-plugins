> 作業を始める前に、workspace正本入口 `/Users/naoya-nakamoriq/Documents/Github/harness-pluginsv2/AGENTS.md` を読み、そこから指定される共通規約とこのrepository固有の規則を適用する。

# AGENTS.md

このrepositoryは、要求・利用負荷・品質要求を根拠付きで発見し、その成果からクラウドアーキテクチャを設計するsourceである。

- marketplaceへ公開するインストール対象は`system-design` package 1件だけにする。個々のplaybookやskillを別のインストール対象として公開しない。
- 公開入口は`discover-requirements`、`discover-workload-model`、`discover-quality-requirements`、`design-cloud-architecture`の独立playbook 4件だけにする。各playbookは同名の一責務skillへ明示的にルーティングし、他skillの仕事を暗黙に実行しない。
- 各`SKILL.md`に`入力`、`出力`、`非責務`、`開始条件`、`停止条件`、`完了条件`、`後続成果物への追跡`を明記する。保存できる状態と、後続判断へreadyな状態を混同しない。
- 確定事実、合意済み決定、仮説・推定、未確認事項を区別し、出典、観測時点、単位、計算式、影響先IDを後続へ残す。根拠のない値やcloud仕様を確定事項として補完しない。
- `design-cloud-architecture`はクラウド・サービス選定、代替案比較、ADR、編集可能なインフラ構成図、要求トレーサビリティ、検証計画を必須成果物とする。要求や品質目標の独断変更、論理DB設計、IaC実装、deployは行わない。
- `design-cloud-architecture`のクラウドプロバイダーはplaybookの`prepare-provider`、`resolve-provider`、`finalize-provider`工程からpackage rootの共通設定経路を使い、`aws`または`gcp`だけを許可する。未指定・不正値を暗黙の既定値へ倒さず、解決済み設定を入力根拠と正本へ追跡する。
- 既存BDD repositoryは公開入口へ利用者が資料を渡す境界で接続する。既存BDDの成果物形式、内部skill、script、install cacheを変更または直接参照しない。
- 外部packageが必要な場合は、公開playbookの`playbook.yml`で`{plugin, marketplace}`を宣言し、`playbook:`工程からだけ呼ぶ。外部packageを`skill:`、`script:`、内部path、固定versionで参照しない。
- 共通referenceは根拠状態、ID、追跡、検証などskill間の受渡し契約だけを所有する。各skill固有の意味判断を共通層へ移さない。
- fixtureは正常系、非対象、境界事例を持ち、入力と期待する分岐・停止・出力を実行前に定義する。fixtureの存在を実モデル評価の成功として扱わない。
- install cache、隣接repository、外部公開、pushは変更しない。このsource treeを正本として編集する。
- 変更後は`bash scripts/validate.sh`を実行する。未実装の公開skillがある間は失敗が正しく、検査を緩めて成功させない。
