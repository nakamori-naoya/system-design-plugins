# 品質要求正本の契約

この参照資料は、品質要求を測定可能にする項目、合意状態、利用・負荷対応、矛盾、保存スキーマを定める。クラウド・製品・構成は定めない。

## 品質区分

次の10区分を一件ずつ評価する。括弧内は現行公開契約で固定する機械値である。

1. 応答時間（`latency`）: 利用者またはシステム境界間で完了までに要する時間。
2. 処理量（`throughput`）: 指定時間内に受理または完了する仕事量。
3. 可用性（`availability`）: 定義したサービス時間窓と観測点で成功できる割合。
4. 整合性（`consistency`）: 書込み後の読取り、複製、競合で許容する不一致。
5. 耐久性（`durability`）: 受理済み情報を失わない割合または許容損失。
6. 復旧性（`recovery`）: 障害後の復旧時間、復旧点、再開条件。
7. 安全性（`security`）: 脅威、主体、資産、境界に対する防止・検出条件。
8. プライバシー（`privacy`）: 個人情報の収集、利用、保持、削除、開示の条件。
9. 運用性（`operability`）: 検知、診断、変更、復旧を運用者が行える条件。
10. 費用（`cost`）: 対象期間と利用量に対する費用上限または効率。

区分の網羅状況（機械キー: `category_coverage`）の判定（`disposition`）は次の通りである。

- `specified`: 一件以上のQRが測定可能な合意済みまたは仮説である。
- `unresolved`: 関係し得るが、判断に必要な情報がなく未決の問いがある。
- `not_applicable`: システム境界または業務結果から非該当である根拠がある。単に話題に出なかった場合には使わない。

典型例: 公開APIの可用性を「暦月の有効な要求のうち成功応答が99.9%以上」と指定する。

似て非なる例: 毎秒250要求という利用・負荷のピークは利用特性であり、処理量の閾値に対する合意ではない。

反例: 「高可用」を可用性要求として完了する。観測点、指標、閾値、時間窓、母集団がないため未決である。

境界例: 95パーセンタイル（`p95`）300ミリ秒に決定者と対象範囲があれば合意済みである。同じ値でも決定者の合意だけ欠ければ仮説へ切り替える。

## 測定可能な品質要求

`agreed`と`hypothesis`のQRは、次を一組にする。

- `observation_point`: 測定の開始・終了または境界。
- `metric`: `name`と`statistic`。例: `end_to_end_latency`と`p95`。
- `threshold`: `operator`、0以上の有限な`value`、`unit`。
- `time_window`: 集計窓と評価期間。
- `population`: 合否の分母となる要求、イベント、記録、操作等。
- `verification_method`: 再現可能な測定または試験。
- `verification_owner`: 実施または承認する役割。
- `confidence`: `high`、`medium`、`low`の一つ。
- `design_sensitivity`: 閾値または不確かさが変える後続判断。

`operator`は`<`、`<=`、`=`、`>=`、`>`のいずれかとする。範囲が必要なら上下限を別QRにする。一件のQRは一つの合否判定だけを持つ。

`unresolved`は`threshold=null`、`confidence=unknown`、一件以上の未決の問いを持つ。既知の観測点や指標を`null`に戻す必要はないが、必要項目が一つでも欠けた状態を合意済みまたは仮説にしない。

`agreed`は同じ区分の`agreed_decision` 根拠主張を最低一件持ち、仮説 根拠主張を根拠に含めない。`hypothesis`は同じ区分の仮説 根拠主張を最低一件持つ。現在実績を示す事実だけでは目標値にならない。

## 利用・負荷対応と矛盾

`workload_links`は品質要求と利用・負荷モデルの対応を保存する。

- `supports`: 確認済み 利用・負荷が検証条件または閾値を直接支える。
- `assumption`: 利用・負荷 仮説を設計比較の暫定入力として使う。
- `conflicts`: 利用・負荷と品質要求の値、時間窓、母集団または状態が両立しない。
- `blocked_by`: 利用・負荷が未決で、品質要求または検証条件を確定できない。

利用・負荷が仮説なら関係は`assumption`または`conflicts`でなければならない。利用・負荷が未決なら`blocked_by`または`conflicts`でなければならない。関係を変えて利用・負荷状態を隠さない。

`conflicts` 関係は最低一件の`QCON-` IDへ結ぶ。矛盾は`left_ref`、`right_ref`、statement、`open`または`resolved`状態を持つ。未解消の矛盾は解消内容をnullにし、解消する未決の問いを持つ。解消済みの矛盾は解消内容と事実/合意済み決定 根拠主張の根拠を持ち、仮説だけで解消扱いにしない。

典型例: QR-002が毎秒250要求のピークを暫定検証条件に使い、`WL-001.peak_rate`が仮説なら関係は`assumption`である。

非該当例: 「管理キューを使えば250 要求/秒を処理できる」と品質要求へ書く。これは製品・方式案であり、品質指標でも利用・負荷事実でもない。

境界例: 利用・負荷とQRの時間窓だけが異なる場合も、値が同じだから`supports`とはしない。換算根拠がなければ`conflicts`または`blocked_by`にする。

## 正本スキーマ

`schema_version`は2だけを受理する。最上位キーは次の12件だけにする。

- `schema_version`
- `artifact`
- `input_artifacts`
- `claims`
- `quality_requirements`
- `category_coverage`
- `workload_links`
- `conflicts`
- `open_questions`
- `question_review`
- `handoff`
- `change_log`

`artifact`は`id`、`version`、`subject`、`state`を持つ。状態は`ready_for_architecture`または`saved_with_open_questions`である。

`input_artifacts`は`id`、`kind`、`locator`、`version_or_hash`、`observed_at`を持つ。kindは`requirements`、`journey`、`domain`、`workload`、`telemetry`、`decision`、`other`の一つである。

`claims`は`id`、`statement`、`classification`、`source_artifact_id`、`source_ref`、`observed_at`、`category`を持つ。

`quality_requirements`は次を持つ。

```json
{
  "id": "QR-001",
  "category": "latency",
  "title": "状態確認の応答時間",
  "status": "agreed",
  "source_claim_ids": ["CLM-001"],
  "upstream_refs": ["REQ-003", "JRN-002"],
  "workload_link_ids": ["QWL-001"],
  "observation_point": "外部入口での要求受信から応答最終バイトまで",
  "metric": {"name": "end_to_end_latency", "statistic": "p95"},
  "threshold": {"operator": "<=", "value": 300, "unit": "milliseconds"},
  "time_window": "5分移動窓を暦月単位で評価",
  "population": "有効な状態確認要求",
  "verification_method": "代表要求を再生し、追跡区間を集計する",
  "verification_owner": "サービス責任者",
  "confidence": "high",
  "design_sensitivity": "閾値が200ミリ秒未満へ変わった場合は応答時間のトレードオフを再評価する",
  "open_question_ids": [],
  "conflict_ids": []
}
```

`category_coverage`は`category`、`disposition`、`rationale`、`quality_requirement_ids`、`open_question_ids`を持ち、10区分を一度ずつ含む。

`workload_links`は`id`、`quality_requirement_id`、`workload_source_id`、`workload_ref`、`workload_status`、`relation`、`rationale`、`conflict_ids`、`open_question_ids`を持つ。

`conflicts`は`id`、`left_ref`、`right_ref`、`statement`、`status`、`resolution`、`evidence_claim_ids`、`open_question_ids`を持つ。

`open_questions`は質問台帳であり、`id`、`question`、`owner`、`affected_refs`、`blocks`、`state`、`resolution`、`reason`を持つ。`state`は`open`、`resolved`、`withdrawn`を区別し、`resolved`だけが非空の`resolution`を持つ。`open`の`reason`には、その時点の根拠から仮置きした推奨、その根拠、採らなかった解釈を書き、推奨の閾値は正本側で`hypothesis`または`unresolved`として扱う。`question_review`は全質問ID、確認者、一覧全体の確認内容、`dialogue_complete=true`を持つ。`handoff`は`ready`、`blocking_question_ids`、`quality_requirement_ids`、`workload_link_ids`、`conflict_ids`を持つ。

未決の問いまたは未解消の矛盾が一件でもあれば`handoff.ready=false`、成果物の状態は`saved_with_open_questions`にする。なければ`handoff.ready=true`、状態は`ready_for_architecture`にする。仮説は状態を保って引き渡しできるが、後続は合意済み前提として扱わない。

`change_log`は版ごとに`version`、`changed_input_ids`、`invalidated_refs`、`summary`を持つ。上流版、観測点、時間窓、母集団、利用・負荷状態が変わったら、影響するQR/QWL/QCONを無効化した参照へ残す。
