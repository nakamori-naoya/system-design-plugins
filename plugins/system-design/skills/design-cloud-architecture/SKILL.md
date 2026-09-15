---
name: design-cloud-architecture
description: システム要求の基準資料、論理設計、利用・負荷モデル、品質要求、組織・運用・予算制約から、根拠付きのクラウド・サービス選定、代替案比較、ADR、要求トレーサビリティ、障害・縮退経路、編集可能なMermaidインフラ構成図を一つのクラウドアーキテクチャ正本へ保存する。クラウド案を比較して採用構成を決めたい、人気ではなく要求からサービスを選びたいときに使う。
---

# design-cloud-architecture

[工程順序の正本](playbook.yml)を最初に読み、同じagentが\`steps\`を宣言順に実行する。YAMLは工程順序と実値依存を決め、各工程の判断内容と根拠はこの本文と参照資料を実読して評価する。実行設定をこのskillが生成した後に失敗または停止する場合は、未実行の認知工程へ進まず`cleanup-provider-configuration`だけを実行してから報告する。外部供給設定ではcleanup runtimeを呼ばない。失敗を成功扱いせず、完了工程、根拠、未決、設定の所有・cleanup結果を残し、再開時は最初の未完了工程から続ける。

検査済みの要求、論理境界、負荷、品質要求、制約を受け取り、選定、比較、決定、構成図、失敗時挙動、追跡、検証計画を一体として監査できる一つのクラウドアーキテクチャ正本を返す。

これは「どの配置方式とクラウド機能領域を、どの根拠・トレードオフ・障害時の挙動で採用するか」を設計するスキルである。要求、ユーザージャーニー、ドメイン、論理データモデルは作り直さず、アプリケーション内部設計、Terraform、配置も実装しない。

## 実行設定

YAMLの`resolve-provider-configuration`工程へ公開呼出しの`request` objectをそのまま渡す。完全な`provider_resolution`がある場合、同工程の専用adapterは`provider`、選択元の永続`config_locator`、そのfile内容と一致する`config_fingerprint`を検査し、`resolved_provider_configuration`へ変更せず返す。所有は`external_input`、`transient_provider_configuration_path`は`null`である。同じrequestに`target_repository`もあっても、この枝では使わず外部供給値を優先する。

`request.provider_resolution`がない場合だけ、専用adapterは同じobjectの`target_repository`にある既存directoryの絶対pathをpackage既存の設定runtimeへ渡す。runtimeが返す解決済み一時設定の絶対path、`.resolution.selected_config`、`.resolution.config_fingerprint`、`cloud.provider`を読み、前3値を同じ`resolved_provider_configuration`形へ正規化する。所有は`generated_by_this_skill`、一時pathは`transient_provider_configuration_path`としてcleanupまでだけ保持する。adapterはskill隣接の公開実行入口からpackage既存runtimeへ固定接続するだけで、設定解決・削除ロジックを複製しない。公開SKILLがplugin rootやpackage runtime pathを推測しない。

`provider`が未指定または`aws`/`gcp`以外、永続locatorが絶対pathの通常fileでない、指紋が実内容と一致しない、生成runtimeが非zero、一時pathが絶対pathの通常fileでない、ownershipが2語彙以外、または来歴が不完全なら後続の認知工程へ進まない。生成済み一時設定がある場合はYAMLのcleanup工程だけを実行して失敗を報告する。正本には永続する`config_locator`、選択元の内容指紋`config_fingerprint`、解決した`provider`を残し、cleanup対象の一時file pathは残さない。

## 入力

- 公開呼出しの`request` object。依頼本文に加え、完全な`provider_resolution`、または実行設定を解決する既存directoryの絶対pathである`target_repository`を持つ。完全な`provider_resolution`があるときはそれを優先して非所有入力として使い、`target_repository`は使わない。無いときだけ`target_repository`から解決する。どちらも無い、または選んだ枝の値が不正なら推測せず停止する。
- システム要求の基準資料。要求、境界、制約のID、状態、根拠、版またはハッシュを識別できること。
- 論理設計。システム/構成要素の責任境界、データの流れ、外部依存を含むが、クラウド製品を前提にしなくてよい。
- 利用・負荷モデル。母集団、平均、ピーク、突発、データ量、保持、成長、分布、配信先数、集中キーのIDと状態。
- 品質要求。観測点、指標、閾値、時間窓、母集団、検証方法、合意状態を持つQR ID。
- 組織、運用、予算、法令・規約順守、所在地、既存契約の制約。
- 複数成果物で共有する業務用語と暫定境界がある場合は、その一つのMarkdown用語正本の所在、版、参照する日本語の推奨用語名。
- `request.provider_resolution`で供給する実行設定の来歴。`provider`は`aws`または`gcp`であり、選択元の永続設定を指す`config_locator`、内容ハッシュ`config_fingerprint`を識別できること。供給しない場合は`request.target_repository`から同じ値を解決する。
- 既存のクラウドアーキテクチャ正本を更新する場合は、その絶対パスと現在の成果物の版。
- 日本語Markdown正本の保存先。新規は既存の書き込み可能な絶対directory、更新は既存Markdownの絶対path。

入力成果物は同等内容でよく、生成方法や固有の内部形式を要求しない。ただし状態、根拠、版またはハッシュ、入力IDを失った転記は入力として完成扱いしない。

## 開始条件

システム境界、最低一件の確認済み要求、最低一件の測定可能な品質要求、利用・負荷モデル、制約、AWS（機械値: `aws`）またはGCP（`gcp`）へ解決済みの実行設定を識別できる場合に開始する。論理設計はクラウド非依存の責任境界とデータの流れを識別できること。

プロバイダーや配置方式が未決でも、候補比較と未決の問いを持つ正本は保存できる。ただし採用サービスを推測せず、実装への引き渡しを後続利用可能にしない。

## 作業手順

### 1. 上流基準資料と設計根拠を固定する

適用条件: 要求の基準資料、論理設計、利用・負荷、品質、制約資料が入力にある。

必須行動: 各入力へ`SRC-` ID、種類（機械キー: `kind`）、絶対パスまたは再現可能な所在情報、版またはハッシュ、観測時点を付ける。選択元の永続設定は`runtime_config`として登録し、`provider_resolution`の`source_artifact_id`からそのSRC IDへ結ぶ。`provider_resolution.config_locator`は同じSRCの所在、`config_fingerprint`は同じSRCの版またはハッシュと完全一致させる。プロバイダー採用制約も同じSRC IDを根拠に持つ。要求、品質、利用・負荷の各設計根拠へ`DRV-` IDを付け、上流ID、状態、内容（`statement`）、設計への影響（`impact`）を保存する。制約へ`CON-` IDを付け、事実、合意済み決定、仮説を保つ。共有用語がある場合は入力を`terminology`として登録し、定義を再記述せず、構成判断から一つのMarkdown用語正本の版・所在と日本語の推奨用語名を`terminology`で参照する。用語や用語正本のIDを利用者へ要求しない。

成功判定: 後続の選定理由から上流成果物、版またはハッシュ、REQ/QR/WL ID、根拠状態に加え、プロバイダー値、永続設定locator/ハッシュへ戻れる。

失敗時: プロバイダー未指定・不正値を候補先頭や人気プロバイダーへ倒さない。要求や品質閾値を都合よく変更せず、不足・矛盾を未決の問いまたは停止理由として返す。論理データモデルをクラウド製品向けに作り直さない。

### 2. 配置方式の境界を判定する

[クラウドアーキテクチャ契約](references/architecture-contract.md)の「配置方式境界」を必ず読む。

適用条件: プロバイダー、所在地、既存設備、契約、可用性、データ所在地の制約を比較できる。

必須行動: 単一クラウド（機械値: `single_cloud`）、マルチクラウド（`multi_cloud`）、ハイブリッド（`hybrid`）、オンプレミス（`on_prem`）、クラウド未決（`cloud_undecided`）の一つを記録する。クラウド未決ではプロバイダーとサービスを`null`にする。

成功判定: 配置方式、プロバイダー範囲、根拠制約、採用代替案、未決が互いに矛盾しない。

失敗時: 「可用性が高そう」という理由だけでマルチクラウドにせず、「クラウド設計だから」という理由だけでオンプレミス制約を消さない。プロバイダー未決時は人気プロバイダーを仮採用しない。

### 3. 機能領域ごとに代替案を比較する

[クラウドアーキテクチャ契約](references/architecture-contract.md)の「選定と代替案」を必ず読む。

適用条件: プロバイダー、リージョンと可用性ゾーン、計算処理、ネットワーク、保管、データベース、メッセージング、識別、外部入口、可観測性、バックアップと災害復旧、配置の候補を一件以上作れる。

必須行動: アーキテクチャ代替案を最低二件作り、各案へ配置方式、プロバイダー範囲、設計根拠、利点、欠点、リスク、費用影響、運用性影響、選択状態を記録する。12機能領域を採用済み（機械値: `selected`）、未決（`unresolved`）、非該当（`not_applicable`）で一度ずつ扱う。

成功判定: 採用済み機能領域ごとに選択、プロバイダー、サービス、役割、要求 設計根拠、品質 設計根拠、利用・負荷 設計根拠、制約、比較代替案、ADR、検証がある。

失敗時: プロバイダー名や人気サービスの羅列、比較なしの単一候補、品質/利用・負荷/制約のいずれかへ戻れない選定を採用しない。根拠を補えなければ未決へ戻す。

### 4. 採用判断をADRへ固定する

適用条件: 少なくとも二案のトレードオフと採用候補がある。

必須行動: 各主要選定を最低一件の`ADR-`へ結び、文脈、判断、比較代替案、設計根拠、正負の帰結、追跡作業、検証を記録する。後続利用可能な正本では採用済みADRを最低一件持つ。

成功判定: 採用構成だけでなく、退けた案、判断条件、負のトレードオフ、再判断契機を説明できる。

失敗時: サービス一覧、プロバイダーの宣伝、担当者の好みを判断根拠にしない。未合意判断は提案中（機械値: `proposed`）とし、正本を実装へ引き渡せる状態にしない。

### 5. 障害・縮退経路を設計する

適用条件: 可用性単位、外部依存、同期・非同期流れのいずれかが失敗し得る。

必須行動: 障害シナリオごとに、発生条件、影響する可用性単位と選定、検出、縮退時の挙動、復旧、守る要求、検証を記録する。通常の流れと障害・縮退経路を区別する。

成功判定: 構成要素停止、可用性ゾーン障害、外部依存遅延、メッセージ滞留などの少なくとも一件で、検出から縮退・復旧まで追跡できる。

失敗時: 「自動復旧」「高可用」で済ませず、観測点、失敗範囲、縮退結果、検証方法が欠ければ未決にする。

### 6. 編集可能なインフラ構成図を作る

[クラウドアーキテクチャ契約](references/architecture-contract.md)の「図の観測可能性」を必ず読む。

適用条件: システム境界、信頼境界、構成要素、流れ、外部依存、可用性単位を識別できる。

必須行動: `flowchart`で始まるMermaid記法を正本内へ保存する。構造化した境界（機械キー: `boundaries`）、ノード（`nodes`）、流れ（`flows`）、外部依存（`external_dependencies`）、可用性単位（`availability_units`）も同じIDで保存し、根拠内へ全IDを出す。流れはデータ、同期方式（`sync`／`async`）、通信規約、信頼境界の通過、障害時の挙動を持つ。

成功判定: Mermaid記法を直接編集でき、システム境界、信頼境界、外部境界、データの流れ、同期・非同期、外部依存、可用性単位を図と構造の両方で確認できる。

失敗時: 画像だけ、サービス名だけの箱、矢印にデータや同期方式がない図を成果物にしない。アプリケーションのクラスやメソッド内部をインフラのノードへ展開しない。

### 7. 要求トレーサビリティと検証計画を閉じる

適用条件: 採用済み機能領域、ADR、障害シナリオ、構成図がある。

必須行動: 各選定について要求、品質、利用・負荷、制約、ADR、検証を`traceability`へ同じ集合で複写し、双方向一致を検査する。検証計画には目的、方法、期待する証拠、責任者、計画済み・成功・失敗の状態、追跡対象を記録する。

成功判定: 採用済み機能領域に根拠なしのtrace空欄がなく、未実行検証は計画済みのままである。

失敗時: テストデータ、文書レビュー、プロバイダー仕様の読取りを実負荷試験・障害試験・災害復旧訓練の成功へ変えない。未検証は計画済みとし、引き渡しへ残す。

### 8. 質問一覧と対話終了を明示確認する

依頼と参照資料から決まらない事項は、同じ担当が理由付きの推奨を添えて一問ずつ確認する。個別回答だけで対話を完了しない。全問を聞いた後、`open`、`resolved`、`withdrawn`に分けた質問一覧、解決内容、撤回理由、影響先を利用者へ提示し、一覧全体と対話終了の明示確認を得る。回答を受理した問いだけを`resolved`、利用者が理由付きで取り下げた問いだけを`withdrawn`、未回答または未合意を`open`とし、解決を撤回へ読み替えない。

JSONの各`open_questions`要素は従来の項目に`state`、`resolution`、`reason`を加える。`resolved`だけが非空の`resolution`を持ち、`open`と`withdrawn`の`resolution`は`null`である。`question_review`へ全質問ID、確認者、確認内容、`dialogue_complete: true`を記録する。全IDの一致と明示確認が無ければ次の保存工程へ進まない。

### 9. 正本を検査して保存する

[クラウドアーキテクチャ契約](references/architecture-contract.md)のスキーマと不変条件を読み、正本をJSONで作る。配布パッケージ内の`scripts/architecture.py`を絶対パスで解決し、次を順番に実行する。

1. `python3 <architecture.pyの絶対path> check --file <候補正本の絶対path>`
2. 初回保存は`python3 <architecture.pyの絶対path> write --repo <対象repositoryの絶対path> --slug <slug> --file <候補正本の絶対path>`
3. 更新保存は2へ`--expected-version <現在version>`を加える。

成功判定: stdoutが返す絶対パスに正本があり、同じスクリプトの`check`が成功し、stderrが空である。

失敗時: 検証器の理由を変更せず返す。検査を通すためにプロバイダーを仮選定せず、設計根拠状態、トレードオフ、障害経路、図要素を捏造しない。

### 10. 日本語Markdown正本を直接保存する

開始時に`document_destination`を確認する。新規作成は既存の書き込み可能な絶対directoryを`output_directory`で、更新は既存Markdownの絶対pathを`update_target`で受け取り、必ずどちらか一方だけとする。未指定、相対path、両方指定では、保存先を補完せず一問で確認して停止する。

JSON正本の保存後、同じ担当がそのJSONと根拠資料を読み、日本語Markdown正本を直接作る。別playbook、別agent、意味を決めるrendererへ委譲しない。Markdownには成果物IDと版、JSON正本の絶対path、provider設定根拠、DRV/CON/ADR/検証ID、代替案、採否理由、障害・縮退経路、編集可能なMermaid図、未決、`handoff`を含める。JSON状態が`ready_for_implementation_handoff`なら`status: ready`、`saved_with_open_questions`なら`status: unresolved`とし、後者は`handoff.ready: false`を明記する。新規名は`cloud-architecture.md`、更新は`update_target`そのものとする。保存後に全文を読み戻してJSONのID、状態、根拠、ADR、図、未決、handoffが欠落・昇格していないことを確認する。欠落時は`failed`として部分保存pathと理由を報告し、完成文書pathへ昇格させない。

### 11. 所有するプロバイダー設定を後片付けする

`provider_configuration_ownership`が`generated_by_this_skill`である場合だけ、最後の設定利用後に`transient_provider_configuration_path`をYAMLが接続する専用adapterへ渡す。adapterはpackage既存cleanup runtimeへ委譲し、成功時に`provider_cleanup_status: completed`を返す。`provider_configuration_ownership`が`external_input`の場合、adapterはcleanup runtimeを呼ばず、`provider_cleanup_status: preserved_external_input`を返す。これ以外のownershipは削除を試みず失敗する。

入力の`request.provider_resolution`から受け取った非所有設定、選択元の永続設定、他実行の設定directory、JSON/Markdown正本は削除しない。YAMLのconditional needは、所有時だけ`transient_provider_configuration_path`をcleanup工程へ要求する。

このskillが設定を生成した後に停止または失敗した場合は、未実行の認知・保存工程へ進まず、この工程だけを実行してから失敗を報告する。所有を証明できない、またはcleanupが失敗した場合は削除済みとせず、設定path、ownership、cleanup失敗理由を未解決のまま返す。

## 出力

対象リポジトリの`system-design/architectures/<slug>.architecture.json`に、スキーマ2のクラウドアーキテクチャ正本を保存する。正本には解決プロバイダーと設定根拠、クラウド・サービス選定、代替案比較、ADR、編集可能なインフラ構成図、要求トレーサビリティ、障害・縮退経路、検証計画を含める。旧スキーマ正本は参照資産として変更せず保持できるが、現行入力または更新対象として受理しない。

公開結果は`status`、全状態を含む`questions`、状態別の`open_questions`、`resolved_questions`、`withdrawn_questions`、`question_review`、`handoff`、`architecture_artifact_path`、`architecture_document_path`、`provider_configuration_ownership`、`provider_cleanup_status`を返す。JSON正本だけ、Markdown正本だけ、または必要なcleanupが失敗した状態を完了としない。

報告には正本の絶対パス、成果物の状態と版、配置方式、採用済み・未決の機能領域、採用・棄却代替案、採用済み・提案中のADR、未決の問い、検証状態、実行した検証、未検証範囲を含める。

## 非責務

- 要求、受入条件、ユーザージャーニー、ドメインルール、BDD、品質閾値、利用・負荷値を作り直さない。
- エンティティ、表、列、キー、索引、論理データモデルを変更しない。
- アプリケーション内部のモジュール、クラス、メソッド、アルゴリズム、APIデータ量を設計しない。
- Terraform、CloudFormation、配置マニフェスト、アプリケーションコードを実装せず、クラウドへ配置しない。
- アカウント作成、契約、購入、外部公開、インストール用キャッシュ更新、pushを行わない。

入力の意味が不足する場合は、その入力の所有者へ未決を返す。入力成果物をこのスキル内で修正して設計を進めない。

## 停止条件

- システム境界、確認済み要求、測定可能な品質要求、利用・負荷モデルのいずれかがなく、選定結果が変わる。
- 実行時設定の`cloud.provider`が未指定、または`aws`/`gcp`以外である。
- 解決プロバイダー、永続設定locator/ハッシュを入力根拠へ追跡できない。
- 上流成果物の版またはハッシュまたは状態が食い違い、同じ対象か確認できない。
- プロバイダー/配置方式の未決を未決として切り離せず、選択肢の母集団が定まらない。
- 採用済み機能領域を要求、品質、利用・負荷、制約へ追跡できない。
- 図のシステム境界、信頼境界、外部依存、データの流れ、同期方式、可用性単位を識別できない。
- 既存正本の版が指定された期待版と一致しない。
- 依頼の中心が上流要求の再発見、論理データモデル、アプリケーション内部設計、IaC実装、配置である。

停止時は比較済み代替案と確認済み設計根拠を破棄しない。止めた選定/ADR、欠けた上流ID・状態・制約・図要素、回答者、影響先、再開条件を返す。

## 完了条件

- 機械可読JSON正本と日本語Markdown正本が両方保存され、読戻しで意味が一致し、状態が`ready_for_implementation_handoff`または`saved_with_open_questions`である。
- 解決プロバイダーが`aws`または`gcp`で、`provider_resolution`、`runtime_config`入力、プロバイダー制約、採用選定へ追跡できる。
- 12機能領域が採用済み、未決、非該当のいずれかで評価され、採用済みは要求・品質・負荷・制約・代替案・ADR・検証へ追跡できる。
- 配置方式とプロバイダー範囲が単一クラウド、マルチクラウド、ハイブリッド、オンプレミス、クラウド未決の境界規則に従う。
- 最低二案を比較し、採用案、棄却・保留案、正負トレードオフ、費用/運用性影響を持つ。
- ADR、障害・縮退経路、要求トレーサビリティ、検証計画がある。
- スキーマ2では、共有語の定義を複製せず、用語正本の版・所在と日本語の推奨用語名を参照している。
- 編集可能なMermaidインフラ構成図が境界、信頼境界、データの流れ、同期非同期、外部依存、可用性単位を表す。
- 検証器の成功と、実配置・負荷試験・障害試験・災害復旧訓練で未検証の範囲を分けて報告している。

`saved_with_open_questions`は比較と保存の完了であり、未決の選定、提案中のADR、作業を止める問いの対象について実装へ引き渡せる状態を意味しない。

## 後続成果物への追跡

`traceability`とADRにREQ/QR/WL/CON、選定、検証のIDを残す。実装や検証の後続成果物はアーキテクチャの版とIDを引用し、仮説の設計根拠と計画済みの検証を確定扱いしない。

上流成果物、プロバイダー条件、価格、サービス機能、障害前提が変わった場合は正本版を上げ、`change_log.invalidated_refs`へ再比較する選定、代替案、ADR、障害、構成図ノード、検証のIDを記録する。古いプロバイダー仕様や価格を黙って引き継がない。
