---
name: discover-quality-requirements
description: ユーザージャーニー、ドメイン、要求、利用・負荷モデルから、応答時間、処理量、可用性、整合性、耐久性、復旧性、安全性、プライバシー、運用性、費用を、観測点・指標・閾値・時間窓・母集団・検証方法と根拠状態付きの一つの品質要求正本（JSONと日本語Markdown）へ保存する。「高速」「高可用」を測定可能にしたい、負荷仮説との対応や矛盾を設計前に明らかにしたいときに使う。
---

# discover-quality-requirements

このskillを読み終えたagentは、「どこで何を測り、どの母集団と時間窓で、どの閾値を満たせば品質要求を満たすか」を、根拠状態と利用・負荷との関係を保ったまま一つの品質要求正本にできる。クラウドプロバイダー、リージョン、サービス、データベース、キャッシュ、キュー、インスタンス、構成、IaCは選定しない。

工程順は[工程順序の正本](playbook.yml)が正本で、同じagentが`steps`を宣言順に実行する。失敗した工程は成功扱いせず停止し、完了工程、根拠、未決を残す。再開時は最初の未完了工程から続ける。

## 入力

- 対象の利用者目的または業務結果と、対象システムの境界。要求発見正本、ユーザージャーニー、ドメイン成果物があれば絶対pathと版またはハッシュ。
- 利用・負荷モデル。平均、ピーク、突発、分布、成長の状態と、対象WL・指標のIDを識別できること。無い場合も未決を保存できるが、負荷依存の閾値はアーキテクチャへ引き渡せる状態にしない。
- 品質についての合意、観測事実、仮説、規制・契約上の制約。各主張の根拠の所在情報、観測時点、決定者を識別できること。
- 更新する場合は、既存の品質要求正本の絶対pathと現在の`artifact.version`。
- `document_destination`。新規は`{output_directory, name}`、更新は`{update_target}`のどちらか一方。名前と置き場は利用者の既存資料構成に従い、依頼に無いときだけ`quality-requirements.md`を初回提案する。

入力の状態と版またはハッシュを捨てた転記は入力として完成扱いしない。

## 判断基準

| 観察対象 | 判定 |
|---|---|
| 品質根拠主張の分類 | 観測条件と時点があれば`fact`。決定者・対象・条件が揃えば`agreed_decision`。それ以外は`hypothesis`。過去の実績は目標ではなく、希望は合意ではなく、利用・負荷の仮説は事実ではない |
| 10区分の判定 | 対象に関係し、合意または仮説の値があれば`specified`。関係し得るが答えが無ければ`unresolved`。対象境界から関係しないと言えるときだけ`not_applicable`。語られなかったことは非該当の理由にならない |
| 測定可能か | 観測点、指標名と統計量、演算子付き閾値と単位、時間窓、母集団、検証方法、検証責任者が揃えば`QR-`として`agreed`または`hypothesis`。一つでも欠ければ既知項目を保持した`unresolved`で閾値はnull |
| 合意状態 | 決定者と対象範囲を持つ`agreed_decision`だけが`agreed`の根拠。業界標準、クラウドの仕様値、現在実績、利用・負荷値は根拠無しに閾値にならず、使うなら`hypothesis`にして誰がいつ合意または反証するかを持たせる |
| 利用・負荷との関係 | 合否または検証条件が規模・平均・ピーク・突発・分布・配信先数・集中キー・成長で変わるなら`QWL-`で`supports`、`assumption`、`conflicts`、`blocked_by`のどれかに結ぶ。負荷側の仮説は`assumption`または`conflicts`のまま渡す |
| 矛盾 | 両立しない値、母集団、時間窓、前提は`QCON-`として左右のIDと`open`／`resolved`状態を持つ。一方の数値の上書きは解消ではない |
| 質問の状態 | 回答を受理した問いは`resolved`、利用者が理由付きで取り下げた問いは`withdrawn`、未回答または未合意は`open` |

## 手順

### 1. 上流成果物と品質根拠主張を固定する

各入力へ`SRC-` IDを付け、`kind`、絶対pathまたは再現可能な所在情報、版またはハッシュ、観測時点を記録する。各品質根拠主張へ`CLM-` IDを付け、判断基準で分類し、根拠成果物、根拠内ID、観測時点、品質区分へ結ぶ。分類できない主張は未決の問いと影響先を返して停止する。

### 2. 品質区分を一件ずつ判定する

[品質要求正本の契約](references/quality-contract.md)の「品質区分」を読む。`latency`、`throughput`、`availability`、`consistency`、`durability`、`recovery`、`security`、`privacy`、`operability`、`cost`を一件ずつ、判断基準で`specified`、`unresolved`、`not_applicable`へ判定する。

### 3. 測定不能表現を観測可能な条件へ分解する

「高速」「高可用」「安全」「低コスト」のように合否を一意に観測できない表現は、一つの合否判断ごとに`QR-` IDを付け、`observation_point`、`metric.name`、`metric.statistic`、演算子付き閾値と単位、時間窓、母集団、検証方法、検証責任者へ分ける。元の表現は根拠主張に残す。異なる検証者が同じ観測から同じ合否を判定できる状態が完成である。

### 4. 数値の合意状態を保つ

閾値、許容障害量、割合、時間、件数、費用などの数値候補を判断基準で`agreed`または`hypothesis`にし、仮説には確からしさ、検証方法、設計感度を持たせる。各`agreed`から合意根拠主張へ、各`hypothesis`から仮説根拠主張へ戻れる状態にする。

### 5. 利用・負荷との対応と矛盾を記録する

[品質要求正本の契約](references/quality-contract.md)の「利用・負荷対応と矛盾」を読む。`QWL-`対応にQR ID、WL／指標ID、利用・負荷状態、関係、判断理由を記録し、両立しない値・母集団・時間窓・前提は`QCON-`矛盾へ記録する。ピークを平均で代用せず、時間窓や母集団の違いを保つ。

### 6. 後続設計へ渡す感度を記録する

QRごとの`design_sensitivity`に再検討を起こす値域、不確かさ、対象判断を書く。引き渡しには測定可能なQR、利用・負荷対応、矛盾、作業を止める問いのIDを渡す。選択候補が入力にあれば設計案として後続へ返し、品質要求へ混ぜない。

### 7. 質問一覧と対話終了を明示確認する

決まらない事項は理由付きの推奨を添えて一問ずつ確認する。全問を聞いた後、`open`、`resolved`、`withdrawn`に分けた一覧、解決内容、撤回理由、影響先を提示し、一覧全体と対話終了の明示確認を得る。`open_questions`の各要素は`state`、`resolution`、`reason`を持ち、`resolved`だけが非空の`resolution`を持つ。`question_review`へ全質問ID、確認者、確認内容、`dialogue_complete: true`を記録する。全IDの一致と明示確認が揃って初めて保存へ進む。

### 8. JSON正本を検査して保存する

[品質要求正本の契約](references/quality-contract.md)のスキーマと不変条件に従って候補JSONを作り、このskill直下の`scripts/quality.py`で検査・保存する。

| 呼び出し | 入力 | 出力 | 失敗の観測 | 失敗時 |
|---|---|---|---|---|
| `python3 scripts/quality.py check --file <候補JSONの絶対path>` | 候補正本 | stdoutに候補の絶対path、stderr空 | 終了code 2、stderrに`FAIL: <理由>` | 理由を変えずに返して停止する。曖昧な表現へ閾値を補わず、仮説を合意、負荷仮説を確認済みへ変えて通さない |
| `python3 scripts/quality.py write --repo <対象repositoryの絶対path> --slug <slug> --file <候補JSONの絶対path>` | 初回保存 | stdoutに保存先`<repo>/system-design/quality-requirements/<slug>.quality.json`の絶対path | 同上 | 同上 |
| 上に`--expected-version <現在version>`を加える | 更新保存 | 同上。版は現在+1 | 版不一致は終了code 2 | 期待版を確認して停止する |

用語正本を参照したときは、package共有のtool`../../scripts/terminology.py`で参照の整合を検査する。

| 呼び出し | 入力 | 出力 | 失敗の観測 | 失敗時 |
|---|---|---|---|---|
| `python3 ../../scripts/terminology.py check --terminology <用語正本の絶対path> --artifact <保存したJSON正本の絶対path>`（`--artifact`は複数可） | 用語正本Markdownと参照側JSON | stdoutに用語正本の絶対path、stderr空 | 終了code 2、stderrに`FAIL: <理由>`（未解決の用語名、版・所在の不一致、見出しの重複、概念種別に無い用語） | 理由を変えずに返して停止する。用語の定義を正本へ複製して通さない |

### 9. 日本語Markdown正本の本文を組み立てる

保存したJSONと根拠資料から本文を組み立てる。冒頭は、誰がどの判断に使う品質要求か、どの合意と観測から始まり、何が測定可能で何が未決かを、読み手の既知の語で書いた段落にする。成果物IDと版、JSON正本の絶対path、QR/QWL/QCON ID、観測点、指標、閾値、時間窓、母集団、検証方法、未決、`handoff`を含める。JSON状態が`ready_for_architecture`なら`status: ready`、`saved_with_open_questions`なら`status: unresolved`と`handoff.ready: false`を本文へ書く。

### 10. write-docへ渡して保存する

本文を`material: [{kind: text, content: <本文>}]`、`document_type: quality-requirements`、`document_destination`の保存先として`write-doc`へ渡す。`status: completed`なら`path`を`quality_document_path`にする。`status: failed`なら`reason`をそのまま報告して停止する。

### 11. 読み戻して確かめる

保存した資料を全文読み、JSON正本のID、状態、根拠、測定条件、未決、handoffが欠落・昇格していないことを確かめる。欠落があれば`failed`として資料pathと理由を報告する。

## 停止条件

- 対象システムの境界または観測対象の未決により、観測点、指標、母集団の意味が変わる。
- 根拠主張の根拠、状態、観測時点または決定者が無く、合意済みと仮説を区別できない。
- 利用・負荷の対象、版、指標状態が分からず、品質閾値との対応または矛盾を判定できない。
- 測定条件の欠落を未決として切り離せず、正本全体の対象を一意にできない。
- `document_destination`が未指定、相対path、または両方式の併記である。
- 既存正本の版が指定された期待版と一致しない。
- 依頼の中心がクラウド・製品選定、論理データ設計、IaC、配置で、品質要求発見の目的が無い。この場合は責務外として返し、このskillの完了としない。

停止時は確認済み根拠主張と測定条件を残し、止めた判断、欠けた観測点・指標・閾値・時間窓・母集団・検証方法、回答者または検証者、影響するQR/QWL/QCON ID、再開条件を返す。

## 出力

- JSON正本: `<対象repository>/system-design/quality-requirements/<slug>.quality.json`（スキーマ2）。入力成果物、根拠主張、測定可能な品質要求、10区分の網羅状況、利用・負荷対応、矛盾、未決の問い、アーキテクチャへの引き渡し、変更履歴を含む。旧スキーマの正本は参照資産として残せるが、現行入力や更新対象として受理しない。
- Markdown正本: write-docが返した`quality_document_path`。
- 公開結果: `status`、`questions`、`open_questions`、`resolved_questions`、`withdrawn_questions`、`question_review`、`handoff`、`quality_artifact_path`、`quality_document_path`。
- 報告: 正本の絶対path、成果物の状態と版、合意済み・仮説・未決件数、未解消矛盾、作業を止める問い、アーキテクチャへ引き渡せるか、実行した検証、未検証範囲。負荷試験、障害試験、セキュリティ試験、費用計測は実行していないので、未実施の検証を合格として報告しない。

完了とは、両正本が保存され読み戻しで意味が一致し、状態が`ready_for_architecture`または`saved_with_open_questions`であり、10区分が評価され、合意済みまたは仮説の品質要求が測定条件・確からしさ・設計感度を持つことをいう。`saved_with_open_questions`は保存完了であり、作業を止める問いまたは未解消の矛盾の影響先をアーキテクチャへ引き渡せることを意味しない。

## 責務の外

ユーザージャーニーの場面、ドメインルール、要求、利用・負荷の値の創作や変更、クラウドプロバイダー、サービス、リージョン、可用性ゾーン、データベース、キャッシュ、キュー、インスタンス、ネットワーク、構成図、IaC、論理データモデル、API、画面の設計は、このskillの成果物ではない。

## 後続成果物への追跡

`handoff`にアーキテクチャへ渡すQR、QWL、QCON、作業を止める問いのIDを記録する。後続は成果物の版、QRの状態、利用・負荷の状態、矛盾の状態を引用し、仮説を合意済み前提へ変えない。ユーザージャーニー、ドメイン、要求、利用・負荷の版またはハッシュまたは意味が変わったときは正本版を上げ、`change_log.invalidated_refs`へ再確認するQR/QWL/QCON IDを記録する。既存IDを別の観測対象、時間窓、母集団へ再利用しない。
