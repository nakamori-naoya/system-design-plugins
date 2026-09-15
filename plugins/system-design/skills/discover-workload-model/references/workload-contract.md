# 利用負荷モデルの契約

この参照資料は、利用負荷モデル正本の項目、数値の完全性、分布と増幅の判断境界を定める。SLO、データモデル、処理容量、クラウドアーキテクチャは定めない。

## 数値の完全性

数値指標は次を一組にする。

- `status`: `confirmed`、`hypothesis`、`unresolved`、`not_applicable`
- `value`: 確認済み/仮説では0以上の数値。未決または非該当ではnull
- `unit`: 単位と分母。例: `events/second`、`bytes/request`、`fraction/year`
- `time_window`: 観測・予測・集計の期間と粒度
- `population`: 分子・分母の対象集合
- `claim_ids`: 同じ特性を述べる根拠主張
- `confidence`: `high`、`medium`、`low`、`unknown`
- `calculation`: 直接観測か、式・入力・単位変換
- `verification_plan`: 何を、誰が、どの条件で測るか
- `sensitivity`: 値域または不確かさが変える後続判断
- `open_question_ids`: 未決を解く問い

確認済み/仮説のvalueに単位、時間窓、母集団、根拠主張、確からしさ、算出方法の一つでもなければ数値を受理しない。未決はvalueをnull、確からしさをunknownにし、未決の問いを最低一件持つ。非該当はvalueをnull、未決の問いを空にし、算出方法へ非該当理由を書く。

典型例: 86,400 イベント/日を暦日86,400秒で割るなら、平均は1 イベント/秒、時間窓は対象日、母集団は対象イベント全件、算出方法は`86400 events/day / 86400 seconds/day`である。

似て非なる例: DAU 100,000は利用者 母集団であり、操作頻度と活動時間がなければ平均またはピークの到着率にはならない。

反例: 日次平均へ一般的な「ピークは平均の10倍」を掛け、対象のピークとして確認済みにする。対象根拠がないため拒否する。

境界例: 同じ1 イベント/秒でも、時系列観測から算出した値は事実を根拠に確認済み、計画担当の予測なら仮説のままにする。数値が同じでも検証計画と設計感度は変わる。

## 特性

各利用・負荷 項目は次の12 指標を必ず持つ。未観測を欠落させず、未決または非該当で示す。

1. `population_size`
2. `average_rate`
3. `peak_rate`
4. `burst_rate`
5. `read_share`
6. `write_share`
7. `request_payload`
8. `response_payload`
9. `retention_period`
10. `growth_rate`
11. `fan_out`
12. `hot_key_share`

読取と書込がともに確認済みまたは仮説で同じ母集団・時間窓なら、割合の合計を1にする。読み書きに分類できないイベントでは、理由付き非該当にする。

## 分布と増幅

`distribution`は状態、形状、偏りの軸、要約、根拠主張、確からしさ、検証計画、設計感度、未決の問いを持つ。`shape=uniform`は分布を測定した根拠主張がある場合だけ使う。データがなければ`shape=unknown`、statusを未決にする。

配信先数は一つの発生元の行為/イベントから生じる配信先数であり、`targets/source-event`等で測る。集中キー割合はキーまたはキー群に集中する負荷割合であり、キーの軸、母集団、時間窓とともに測る。どちらもキャッシュ、キュー、分割単位、データベースの採用決定ではない。

典型例: 一つの受注イベントを3つの外部受信者が読むなら配信先数は3 配信先/イベントである。

非該当例: 「メッセージキューを使うので配信先数がある」と記録する。手段から負荷を捏造しているため拒否する。

境界例: 全テナントの上位1 テナントが35%を占める観測があれば集中キー割合として記録する。同じ35%が「最大顧客はその程度のはず」という予測なら仮説にし、テナント別時系列集計を検証計画にする。

## 設計入力としての完了

利用負荷モデルは対象サービスの実情を紹介する調査報告ではない。公開情報、書籍、遠隔測定は根拠素材であり、成果物は対象システムで採用する仮定を要件と構成判断へ接続した設計入力である。

スキーマ2の`design_inputs`は、次を一組にする。

- `workload_refs`: 採用仮定を構成する負荷項目、指標、感度。
- `source_claim_ids`: 公開値、実測、合意、推定の根拠。
- `adopted_assumption`: 対象システムで設計に使う仮定。
- `applicability`: 世界規模などの比較値（`reference_scale`）、初期実装の合格値（`implementation_acceptance`）、局所負荷（`localized_load`）のどれか。
- `requirement_refs`: 補完する外部要求または制約ID。
- `architecture_concerns`: 容量、分割、非同期処理、流量制御、保持期限、障害隔離のうち比較すべき関心。
- `confidence`: 仮定を設計に使える確からしさ。
- `revisit_when`: どの観測で仮定と影響先を再確認するか。
- `out_of_scope`: この値を直接適用しない範囲。

典型例: 公開規模から推定した毎秒件数を世界規模の比較値として採用し、読取経路の容量判断へ渡す一方、初期実装がその値を直接処理する合格条件ではないと明記する。

似て非なる例: 公開利用者数と計算式を詳しく説明したが、補完する要件と構成上の関心がない。調査としては有用でも設計入力モデルとして未完了である。

反例: 推定値から特定クラウド製品、台数、分割数を決定する。利用負荷モデルの責務を越えるため拒否する。

境界例: 同じ毎秒件数でも、負荷試験の合格値として合意されていれば`implementation_acceptance`、世界規模の公開値を比較にだけ使うなら`reference_scale`である。変わる条件は値ではなく適用範囲である。

## 正本スキーマ

スキーマ1の最上位キーは次の9件だけにする。スキーマ2は同じ9件に`design_inputs`と`terminology`を加える。

- `schema_version`
- `artifact`
- `input_artifacts`
- `claims`
- `workload_items`
- `sensitivities`
- `open_questions`
- `handoff`
- `change_log`

`artifact`は`id`、`version`、`subject`、`state`を持つ。`input_artifacts`は`id`、`kind`、`locator`、`version_or_hash`、`observed_at`を持つ。`claims`は`id`、`statement`、`classification`、`source_artifact_id`、`locator`、`observed_at`、`characteristic`を持つ。

`workload_items`は次を持つ。

```json
{
  "id": "WL-001",
  "kind": "event",
  "name": "order-submitted",
  "period": "2026-Q2",
  "source_subject_refs": ["REQ-001", "CEVT-OrderSubmitted"],
  "characteristics": {
    "population_size": {},
    "average_rate": {},
    "peak_rate": {},
    "burst_rate": {},
    "read_share": {},
    "write_share": {},
    "request_payload": {},
    "response_payload": {},
    "retention_period": {},
    "growth_rate": {},
    "fan_out": {},
    "hot_key_share": {}
  },
  "distribution": {
    "status": "confirmed",
    "shape": "skewed",
    "skew_dimension": "tenant_id",
    "summary": "上位1 tenantが全eventの35%を占める",
    "claim_ids": ["CLM-012"],
    "confidence": "high",
    "verification_plan": "tenant別event数を週次で再集計する",
    "sensitivity": "集中率が上がれば単一キー集中を扱う設計判断を再確認する",
    "open_question_ids": []
  }
}
```

`sensitivities`は`id`、`workload_item_id`、`characteristic`、`condition`、`affected_decision`、`validation_trigger`を持つ。`open_questions`は`id`、`question`、`owner`、`affected_refs`、`blocks`を持つ。

`handoff`は`ready`、`blocking_question_ids`、`downstream`を持ち、後続は`quality`と`cloud_design`の配列である。作業を止める問いがあれば`ready=false`、成果物 状態は`saved_with_open_questions`にする。なければ`ready=true`、状態は`ready_for_downstream`にする。

`change_log`は初版を含む版ごとに、`version`、`changed_input_ids`、`invalidated_refs`、`summary`を持つ。ユーザージャーニー/ドメインの版変更時に、以前の値を黙って流用しない。

`schema_version=1`は既存正本の互換読取に使う。新規成果物は`schema_version=2`とし、`design_inputs`を1件以上持つ。`terminology`は共有Markdown用語正本の所在、1以上の整数版と、負荷項目・設計入力から日本語の推奨用語名への参照だけを持ち、用語IDや用語正本IDを要求せず、定義本文を複製しない。用語正本は表にせず、アクター、コマンド、クエリ、コマンドイベント、クエリイベント、時間イベント、システムイベント、値・指標、状態、データ、方針・制約、業務上の概念、負荷特性、設計上の概念の見出しで概念種別を明示する。操作の意図、各操作の成立事実、時間経過、内部処理の観測事実を区別し、業務上の対象・関係・情報、負荷を増幅する性質、測定値も区別する。スキーマ1から移行するときは、採用仮定の適用範囲、外部要求ID、構成上の関心、見直し条件、適用外、共有用語参照を補い、成果物版と`change_log`を更新する。

分類例では、投稿・フォロー関係・ホームタイムラインは業務上の概念、ファンアウトや操作頻度型は負荷特性、平均負荷は値・指標である。負荷特性は数値そのものではなく、何が処理量を増幅または集中させるかを表す。この分類例を対象サービスの既定用語や既定閾値にはしない。
