> 作業を始める前に、workspace規約入口 `/Users/naoya-nakamoriq/Documents/Github/harness-pluginsv2/AGENTS.md` を読み、そこから指定される共通規約とこのrepository固有の規則を適用する。

# AGENTS.md

このrepositoryは、要求・利用負荷・品質要求を根拠付きで発見し、その成果からクラウドアーキテクチャを設計するsourceである。

- marketplaceへ公開するインストール対象は`system-design` package 1件だけにする。
- package manifestは`discover-requirements`、`discover-workload-model`、`discover-quality-requirements`、`design-cloud-architecture`の自己完結skill 4件を`skills/`から直接公開する。設定解決script、外側のrouting playbook、入口別runtime manifestを持たない。各skill直下の`playbook.yml` v2を工程順序の正式な定義とし、同じagentが`agent_work: invoking_agent`の工程を宣言順に実行する。利用者へ問う場面は公開playbook `grill`へ`playbook:`で委ね、作法（問い方・上限・合意）をこのrepositoryへ複製しない。正式な資料はwrite-docが保存するMarkdown 1本だけで、JSON資料を持たない。本文はagentがインメモリで保持し、入口の`scripts/`の検査scriptへ標準入力で渡し（正解は`--upstream`の上流資料と記法から導く）、`kind: text`で公開playbook `write-doc`へ渡して保存する。外部依存は`requires`に宣言した`grill`と`write-doc`だけである。
- 各`SKILL.md`は、目的、入力契約（任意の`references`＝追加で従う資料の絶対path配列を含む）、判断基準（観察対象と二者択一の述語）、手順、停止条件、出力契約を実行agentが判断に使える形で持つ。見出しの形や個数は固定せず、機械検査にもしない。scriptは入口directory相対のpathで示し、入力・出力・失敗の観測・失敗時の扱いを宣言する。保存できる状態（`unresolved`）と、後続判断へreadyな状態（`ready`）を混同しない。
- 確定事実、合意済み決定、仮説・推定、未確認事項を区別し、出典、観測時点、単位、計算式、影響先IDを後続へ残す。根拠のない値やcloud仕様を確定事項として補完しない。
- `design-cloud-architecture`はクラウド・サービス選定と代替案の比較、ADR、編集可能なインフラ構成図、要求から構成への追跡、検証計画を必須成果物とする。要求や品質目標の独断変更、論理DB設計、IaC実装、deployは行わない。
- `design-cloud-architecture`は利用者が明示した`provider`（`aws`または`gcp`）を公開入力として受け取り、設定ファイルや既定値を持たない。未指定・不正値は確認を求めて停止し、指定の根拠を合意済み制約として基準資料へ追跡する。
- 既存BDD repositoryは利用者が資料を渡す境界で接続する。既存BDDの成果物形式、内部skill、script、install cacheを変更または直接参照しない。
- 検査が読む目印（追跡の表の見出し行・ID・根拠状態の値・構成図のブロック）はwrite-docの公開契約「検査が読む目印」が所有する。このrepositoryの検査scriptはその目印だけを読み、見出しの文言を読まない。目印とscriptが食い違えばscript側を直す。package共有code（`plugins/system-design/scripts/`）は構文解析と用語定義の検査だけを持ち、各skill固有の意味判断を共通層へ移さない。
- fixtureは各入口のMarkdown正例（`tests/fixtures/<入口>/success.md`）を持ち、testが文字列置換で反例・境界例を作って検査scriptへ標準入力で渡す。fixtureの存在を実モデル評価の成功として扱わない。案件固有の値（特定サービスの用語、閾値、採用技術）を既定値や例の正解にしない。2026-09-16以前のJSON fixtureは`tests/fixtures/legacy-json/`に記録として保全し、現行testからは参照しない。
- install cache、隣接repository、外部公開、pushは変更しない。このsource treeだけを編集対象とする。
- 変更後は`bash scripts/validate.sh`を実行する。未実装の公開skillがある間は失敗が正しく、検査を緩めて成功させない。

## 検査スクリプトは、意味が一意に決まることだけを判定する

このrepositoryの検査スクリプト（validate、lint、verify、checkなど、名前を問わない）が判定してよいのは、ファイルや見出しの有無、識別子や版の一致、宣言と配置の対応、禁止された書き方の有無のように、入力と基準資料から意味が決定論的に一意に決まることだけである。読んで解釈しないと決まらないことや、件数や語の出現のような品質の代わりの指標は判定せず、エージェントが読んで評価する（意味評価）。判定が一意に決まることを宣言できない検査は作らず、詳しい条件は `/Users/naoya-nakamoriq/Documents/Github/harness-pluginsv2/.agents/rules/deterministic-validation.md` に従う。
