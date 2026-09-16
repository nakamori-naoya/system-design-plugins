# クラウドアーキテクチャ契約

この参照資料は配置方式、選定と比較、ADR、構成図、追跡可能性、障害、検証、保存スキーマを定める。上流要求や論理データモデル、アプリケーション内部、IaCは定めない。

正本は`schema_version=2`だけを受理する。`terminology`は共有Markdown用語正本の所在、1以上の整数版と、構成判断から日本語の推奨用語名への参照だけを持つ。用語や用語正本のIDを要求せず、要求・負荷資料の定義や暫定閾値を構成資料へ複製しない。用語正本では表ではなく概念種別見出しによって、各用語がアクター、コマンド、クエリ、コマンドイベント、クエリイベント、時間イベント、システムイベント、値・指標、状態、データ、方針・制約、業務上の概念、負荷特性、設計上の概念のどれかを明示する。操作の意図、各操作の成立事実、時間経過、内部処理の観測事実を混同しない。用語正本の版が変わった場合は、参照項目を`change_log.invalidated_refs`へ記録して再評価する。旧版を現行正本として読取り、更新、変換する経路は持たない。

## 入力プロバイダーの根拠

`provider`は公開入力であり、許可値は`aws`と`gcp`だけである。未指定、空、その他の値は停止する。既定値は無い。

利用者がプロバイダーを指定した依頼または決定記録を`input_artifacts`（`kind`は`decision_record`、`organization`、`contract`など実際の出所）として登録し、その制約を`constraints`へ`classification=agreed_decision`で記録する。`provider_decision.constraint_id`はその制約を指し、`provider`機能領域の選定はその制約IDを`constraint_ids`に含める。正常例は`provider: aws`とそれを裏付ける合意済み制約、反例は`provider: azure`、仮説の制約を根拠にした指定、または制約を引用しない`provider`選定である。境界例は制約が存在するのに`provider`選定が引用しない場合で、これは追跡不能として停止する。

## 配置方式境界

- `single_cloud`: プロバイダー範囲が一件で、採用サービスはそのプロバイダー内にある。
- `multi_cloud`: 独立したクラウドプロバイダーが二件以上あり、各プロバイダーの責任と障害範囲を図示する。二プロバイダー名の列挙だけでは該当しない。
- `hybrid`: 一件以上のクラウドプロバイダーとオンプレミス境界があり、接続、trust crossing、運用責任を図示する。
- `on_prem`: クラウドプロバイダー範囲は空で、クラウド 機能領域は非該当またはオンプレミス実装として明記する。
- `cloud_undecided`: プロバイダー範囲とサービス 選択を空にし、比較候補、決める問い、作業を止めた選定を残す。

典型例: データ所在地、既存契約、運用スキル、品質、利用・負荷を比較し、プロバイダー A一件を採用するなら`single_cloud`である。

似て非なる例: バックアップを別プロバイダーへ出力するだけで、サービス責任が二クラウドへ分割されない場合は`multi_cloud`と断定しない。

反例: 「可用性向上のためマルチクラウド」と書き、障害 独立性、データ整合性、運用性、費用を比較しない。

境界例: オンプレミス接続要件だけが追加されたとき、純粋な単一クラウドからhybridへ切り替える。仮想専用網（VPN）製品を先に決めず、境界と流れを先に記録する。

## 選定と代替案

次の12機能領域を一度ずつ評価する。括弧内は現行公開契約で固定する機械値である。

1. プロバイダー（`provider`）
2. リージョンと可用性ゾーン（`region_az`）
3. 計算処理（`compute`）
4. ネットワーク（`network`）
5. 保管（`storage`）
6. データベース（`database`）
7. メッセージング（`messaging`）
8. 識別（`identity`）
9. 外部入口（`edge`）
10. 可観測性（`observability`）
11. バックアップと災害復旧（`backup_dr`）
12. 配置（`delivery`）

採用済み（機械値: `selected`）は、選択、プロバイダー、サービス、役割に加え、要求・品質・利用負荷の設計根拠、制約、代替案、ADR、検証を最低一件ずつ持つ。

未決（機械値: `unresolved`）は選択、プロバイダー、サービスを`null`にし、作業を止める問いを持つ。非該当（`not_applicable`）もこれらを`null`にし、対象境界に基づく理由を持つ。

代替案は最低二件とし、設計根拠、利点、欠点、リスク、費用への影響、運用性への影響を持つ。後続利用可能状態では採用（機械値: `chosen`）を一件だけにする。人気、慣例、プロバイダー一覧に載っていることは設計根拠ではない。

## 図の観測可能性

`diagram.notation`は`mermaid`、`editable`はtrue、`source`は`flowchart`で始める。根拠と構造化要素は同じIDを使う。

- `boundaries`: システム、信頼境界、外部を最低一件ずつ持つ。
- `nodes`: 表示名、選定IDまたは外部、境界ID、可用性単位IDを持つ。クラウド未決時は候補（機械値: `candidate`）ノードから未決の選定へ結ぶ。
- `flows`: 始点・終点、データ、同期（`sync`）または非同期（`async`）、通信規約、信頼境界の通過、障害時の挙動を持つ。
- `external_dependencies`: 外部ノード、責任者、契約参照を持つ。
- `availability_units`: 障害範囲とノードIDを持つ。各単位はMermaid記法で`subgraph AU001["AU-001 ..."]`のように、ハイフンを除いた別名と元IDを表示名に持つ描画対象として表す。コメント内のID列挙は描画扱いにしない。

Mermaid記法はすべての境界、ノード、流れ、可用性単位IDを含む。図だけに情報を隠さず、構造だけ作って空のMermaidを返さない。

## 正本スキーマ

最上位キーは次の18件だけにする。

- `schema_version`
- `artifact`
- `input_artifacts`
- `provider_decision`
- `drivers`
- `constraints`
- `scope`
- `deployment_model`
- `alternatives`
- `selections`
- `adrs`
- `diagram`
- `failure_scenarios`
- `traceability`
- `verification_plan`
- `open_questions`
- `question_review`
- `change_log`
- `terminology`

`artifact`は`id`、`version`、`subject`、`state`を持つ。状態は`ready_for_implementation_handoff`または`saved_with_open_questions`である。

`provider_decision`は`provider`と`constraint_id`を持つ。プロバイダーは`aws`または`gcp`、`constraint_id`は`classification=agreed_decision`の制約IDである。単一クラウド、マルチクラウド、hybridでは入力プロバイダーがプロバイダー範囲に含まれ、採用済み機能領域のプロバイダーは入力プロバイダーと一致する。

`drivers`は`id`、`kind`、`upstream_ref`、`source_artifact_id`、`state`、`statement`、`observed_at`、`impact`を持つ。kindは要求、品質、利用・負荷の一つである。

`constraints`は`id`、`type`、`statement`、`classification`、`source_artifact_id`、`source_ref`、`observed_at`を持つ。

`deployment_model`は`mode`、`provider_scope`、`decision_state`、`constraint_ids`、`alternative_id`、`open_question_ids`を持つ。プロバイダー範囲に置けるクラウドプロバイダーは`aws`と`gcp`だけである。

`selections`は`id`、`category`、`status`、`choice`、`provider`、`service`、`role`、`requirement_driver_ids`、`quality_driver_ids`、`workload_driver_ids`、`constraint_ids`、`alternative_ids`、`adr_ids`、`verification_ids`、`rationale`、`open_question_ids`を持つ。

`adrs`は`id`、`status`、`title`、`context`、`decision`、`alternative_ids`、`selection_ids`、`driver_ids`、`positive_consequences`、`negative_consequences`、`follow_ups`、`verification_ids`を持つ。

`failure_scenarios`は`id`、`trigger`、`affected_availability_unit_ids`、`affected_selection_ids`、`detection`、`degradation_behavior`、`recovery`、`requirement_driver_ids`、`verification_ids`を持つ。

`traceability`は選定ごとに`selection_id`、`requirement_driver_ids`、`quality_driver_ids`、`workload_driver_ids`、`constraint_ids`、`adr_ids`、`verification_ids`を持ち、選定上の集合と一致する。

`verification_plan`は`id`、`kind`、`objective`、`method`、`expected_evidence`、`owner`、`status`、`trace_refs`を持つ。実行していない検証は計画済みにする。

`open_questions`は質問台帳であり、`id`、`question`、`owner`、`affected_refs`、`blocks`、`state`、`resolution`、`reason`を持つ。`state`は`open`、`resolved`、`withdrawn`を区別し、`resolved`だけが非空の`resolution`を持つ。`question_review`は全質問ID、確認者、一覧全体の確認内容、`dialogue_complete=true`を持つ。

未決の問いがある、配置判断が未決、選定が未決、採用済みADRがない場合は状態を`saved_with_open_questions`にする。それ以外は`ready_for_implementation_handoff`にできる。

`change_log`は版ごとに`version`、`changed_input_ids`、`invalidated_refs`、`summary`を持つ。
