# 要求発見正本の契約

この参照資料は、要求発見正本の項目と判断境界を定める。要求の内容そのもの、ユーザージャーニー、ドメイン、データモデル、技術方式、クラウド選定は定めない。

## 中核概念と行動

### 根拠主張の状態

同じ文章でも、状態が違えば行動が変わる。

| 状態 | 該当条件 | 要求・受入条件への行動 |
|---|---|---|
| `fact` | 観測対象、条件、時点、根拠 所在情報がある | 必要性の根拠に使える。観測した事実だけで将来の受入目標を決めない |
| `agreed_decision` | 決定者、対象範囲、決定内容がある | 要求または受入観測の根拠に使える |
| `hypothesis` | 予測、提案、推定であり反証が残る | `hypotheses`へ置き、確認済み要求や受入観測へ使わない |
| `open_question` | 回答により要求、境界、受入が変わる | 回答者、影響ID、止める判断を記録する |

典型例: 問い合わせ記録に「利用者の30%が申請結果を電話確認した」と期間付きである。これは事実であり、「電話確認をゼロにする」はまだ合意済み目標ではない。

似て非なる例: 担当者が「多分半数が困っている」と述べた。同じ割合の話でも観測条件がなく仮説なので、確認済み要求の根拠へ昇格させない。

反例: 一般的な業界傾向を、対象製品の観測事実として書く。対象と根拠 所在情報が一致しないため拒否する。

境界例: 「申請者が結果を当日中に確認できる」が担当者の希望なら仮説、決定権者が対象申請と期限を指定して合意したなら合意済み決定である。変わる条件は合意の有無であり、文章の具体性ではない。

### 要求と仮説

要求は、受益者が必要とする結果について、根拠、合意済み成功観測、検証方法、満たす／満たさない影響が揃った項目である。仮説は、必要性または手段を確かめる余地が残る項目である。

要求に見える具体的な文章でも根拠が仮説なら`requirements`へ入れない。逆に、技術語を含んでいても決定権者が必須制約として合意していれば、目的ではなく`constraints`へ置ける。

### 成功観測と受入条件

成功観測は、誰が何を見て業務結果の成立を判断するかである。`requirements[].success_observation_ids`へ結べるのは`agreed_decision`の観測だけである。事実は現在地の観測であり、将来の受入目標とは限らない。仮説は候補であり、受入条件ではない。

## 手段指定（How）の分類

入力にHowがある場合は、次の順で一つへ分類する。

1. 決定権者、対象範囲、決定時点が揃い、選択余地を拘束するか。該当するなら`constraint`。
2. 特定の結果を満たすと予測しているが検証・合意が残るか。該当するなら`hypothesis`。
3. 後続で比較・選定する候補か。該当するなら`design_proposal`。
4. どれか判定できない場合は、決定済みか候補かを一問で確認して停止する。

典型例: 「Redisなら速くなるはず」は仮説にし、対象操作、測定方法、反証条件を残す。

非該当例: 「会社の承認済み標準として、顧客データは指定リージョン内のmanaged データベースに保存する」は、決定記録と対象範囲があればtechnical 制約である。Redisを採用する目的や要求にはしない。

境界例: 「Redisを使う」という同じ文でも、提案なら仮説、アーキテクチャ委員会が対象と時点を指定した必須決定なら制約である。後者でも、Redisの選定理由を受益者の目的へ置換しない。

## 導出要件と設計判断

導出要件は、入力にそのまま書かれていないが、確認したサービス特性から避けるべき失敗と必要な成果を因果で説明できる要件である。次の五項目を一組にする。

1. `service_characteristic`: 負荷、保持、偏り、整合性、障害波及、再試行などの観測または仮定。
2. `failure_risk`: その特性から誰に何が起こるか。
3. `required_outcome`: 実現手段を外しても成立する必要な成果。
4. `design_impacts`: 後続が比較する設計上の関心。
5. `revisit_when`: 特性または仮定を再確認する条件。

典型例: 一部の発生元だけ配信先数が桁違いに多いという観測から、一操作の処理増幅を通常利用者へ波及させない成果を導く。配信方式の候補は設計影響であり、キュー製品や分割数は導出要件にしない。

似て非なる例: 「キャッシュを置けば速い」は方式の仮説であり、サービス特性、失敗リスク、必要な成果がないため導出要件ではない。

反例: APIの任意冪等キー、具体的なエラーコード、再試行回数を、再送時の重複を避けたいという成果そのものとして記録する。これは実装詳細を要件へ逆流させている。

境界例: 同じ方式でも、利用者が対象と必須性を決めた場合は固定制約、確認済み導出要件から他の方式では成果を満たせない場合は理由付き設計判断、候補が複数ある場合は設計案である。

`design_decisions`へ置けるのは、合意済み決定を根拠にするか、確認済み導出要件から論理的に不可避な方式だけである。いずれも採用理由と見直し条件を必須にする。実装製品、API項目、表、キュー、キャッシュ期限などの詳細は`solution_inputs`から後続へ送る。

`scope_budget`は機能一覧ではなく実装可能性を閉じる。`implementation_scope`、`design_only_scope`、`out_of_scope`、`delivery_constraints`を分け、世界規模の設計説明を初期実装の合格値へ暗黙に昇格させない。

## 操作とイベントの分類

対象内で利用者または外部システムが開始する操作は、状態変更の意図を表すコマンドと、状態を変えず情報を得るクエリに分ける。コマンド名は「注文を取り消す」のような意図、コマンドイベント名は「注文が取り消された」のような成功後の完了事実として書く。同じ語形で両者を兼用しない。

各コマンドは、対象アクター、根拠主張、状態変更対象、成功時のコマンドイベントを持つ。コマンドイベントは業務上の状態変化の前後を持ち、成功したコマンドから追跡できる。読み取り専用操作はクエリとして、読み取る対象と成功時のクエリイベントを持つ。クエリイベントは読み取りが成立または実行された完了事実であり、状態変更を持たない。イベントであることを理由にクエリイベントを除外しない。コマンドとクエリは確認済み根拠だけから登録し、未確認の操作は仮説または未決として扱う。

コマンドイベント、クエリイベント、時間イベント、システムイベントを分ける。コマンドイベントは状態変更コマンドが成功した業務上の完了事実、クエリイベントは状態変更なしに読み取りが成立した観測可能な事実である。時間イベントは保持期限や契約期限など、時刻または期間への到達により成立する事実であり、操作や内部処理へ無理に分類しない。システムイベントは、配信先への複製、索引更新、物理削除など、内部処理で観測した技術的な完了事実である。システムイベントは関連する操作イベントまたは時間イベントへ結べるが、コマンドやクエリの成功を置き換えない。

コマンドごとに開始／解除、登録／取消、付与／剥奪など対になる操作を反証する。対があるなら双方を相互参照し、業務上存在しないなら非該当理由を残す。判断できないなら未決の問いへ結び、片方を創作しない。また、無変更、拒否、失敗は別々に確認する。根拠がなければ具体的な状態遷移、エラーコード、再試行、補償を決めず、それぞれを未決の問いにする。

典型例: 「会員登録を解除する」はコマンド、「会員登録が解除された」はコマンドイベント、「解除済みか確認する」はクエリ、「解除済みであることが確認された」はクエリイベント、「保持期限に到達した」は時間イベント、「削除対象レコードが物理削除された」はシステムイベントである。

反例: 「通知が配信先へ複製された」をコマンドイベントとして登録する。これは内部処理の観測事実なのでシステムイベントへ分ける。また、クエリイベントへ「未確認から確認済み」の状態変化を持たせない。閲覧履歴更新などの副作用があっても、読み取り対象の業務状態を変えるコマンドとは別に扱う。

境界例: 「注文登録」という名詞句だけでは意図と完了事実を区別できない。「注文を登録する」という状態変更の意図はコマンド、「注文が登録された」という完了事実はコマンドイベントとして別に記録する。これらの語を汎用既定へ登録しない。

## JSONスキーマ

正本はUTF-8 JSON object、`schema_version=2`とする。最上位は基礎14項目に`derived_requirements`、`design_decisions`、`scope_budget`、`decision_history`、`terminology`、`interaction_catalog`を加えた20項目である。次のJSONは基礎項目の形を説明する抜粋であり、検査可能な正本は後続の全項目規則を満たす。

```json
{
  "schema_version": 2,
  "artifact": {
    "id": "REQDOC-order-status",
    "version": 1,
    "subject": "申請結果確認",
    "state": "ready_for_downstream"
  },
  "claims": [
    {
      "id": "CLM-001",
      "statement": "申請者が結果確認のため電話している",
      "classification": "fact",
      "source": "問い合わせ集計 2026-Q2 p.4",
      "observed_at": "2026-07-01",
      "owner": "サポート責任者"
    },
    {
      "id": "CLM-002",
      "statement": "申請者が結果と次の行動を確認できれば受入とする",
      "classification": "agreed_decision",
      "source": "要求確認会議 DR-2026-018",
      "observed_at": "2026-07-08",
      "owner": "業務責任者"
    }
  ],
  "stakeholders": [
    {
      "id": "STK-001",
      "role": "申請者",
      "relationship": "beneficiary",
      "interest": "申請結果を確認できる",
      "claim_ids": ["CLM-001"]
    }
  ],
  "purpose": {
    "beneficiary_ids": ["STK-001"],
    "problem": "結果確認に別経路が必要",
    "desired_outcome": "申請者が結果を確認できる",
    "claim_ids": ["CLM-001"]
  },
  "observations": {
    "success": [
      {
        "id": "OBS-S-001",
        "statement": "申請者が結果と次の行動を確認できる",
        "observer": "申請者",
        "classification": "agreed_decision",
        "claim_ids": ["CLM-002"],
        "verification_method": "対象申請の受入観察"
      }
    ],
    "failure": [
      {
        "id": "OBS-F-001",
        "statement": "申請者が結果を確認できず問い合わせる",
        "observer": "申請者",
        "classification": "fact",
        "claim_ids": ["CLM-001"],
        "verification_method": "問い合わせ理由の集計"
      }
    ]
  },
  "scope": {
    "in": [{"id": "SCP-I-001", "statement": "申請結果の提示", "claim_ids": ["CLM-002"]}],
    "out": [{"id": "SCP-O-001", "statement": "審査規則の変更", "claim_ids": ["CLM-002"]}]
  },
  "system_boundary": {
    "responsibilities": [{"id": "BND-S-001", "statement": "確定した申請結果を提示する", "claim_ids": ["CLM-002"]}],
    "external_parties": [{"id": "BND-E-001", "statement": "審査担当が結果を確定する", "claim_ids": ["CLM-002"]}]
  },
  "constraints": [],
  "requirements": [
    {
      "id": "REQ-001",
      "statement": "申請者は確定した申請結果と次の行動を確認できる",
      "beneficiary_ids": ["STK-001"],
      "claim_ids": ["CLM-001", "CLM-002"],
      "success_observation_ids": ["OBS-S-001"],
      "verification_method": "対象申請の受入観察",
      "impact": {"if_met": "別経路なしで次へ進める", "if_unmet": "問い合わせが必要になる"},
      "affects": ["workload", "quality", "cloud_design"]
    }
  ],
  "hypotheses": [],
  "open_questions": [],
  "question_review": {
    "question_ids": [],
    "confirmed_by": "利用者",
    "confirmation": "質問一覧全体と対話終了を確認した",
    "dialogue_complete": true
  },
  "solution_inputs": [],
  "handoff": {
    "ready": true,
    "blocking_question_ids": [],
    "downstream": {
      "workload": ["REQ-001"],
      "quality": ["REQ-001"],
      "cloud_design": ["REQ-001"]
    }
  }
}
```

## 項目規則

- `schema_version`: 現行値は2だけである。旧版を現行正本として読取り、更新、変換する経路は持たない。

- `artifact.state`: `ready_for_downstream`または`saved_with_open_questions`。
- `claims[].classification`: `fact`、`agreed_decision`、`hypothesis`、`open_question`。
- `stakeholders[].relationship`: `beneficiary`または`stakeholder`。beneficiaryを最低1件持つ。
- `observations.success`と`observations.failure`: 各1件以上。要求へ結べるsuccessは`agreed_decision`だけ。
- `constraints[].kind`: `business`、`regulatory`、`organizational`、`technical`。
- `constraints[].classification`: `fact`または`agreed_decision`。未確認の制約は仮説へ置く。
- `requirements`: 根拠主張 ID、受益者ID、成功観測ID、検証方法、`impact.if_met`、`impact.if_unmet`、`affects`を必須にする。根拠主張は`fact`または`agreed_decision`だけ。
- `hypotheses`: `id`、`statement`、仮説の`claim_ids`、`falsification_method`、`affected_ids`を持つ。
- `open_questions`: 質問台帳であり、`id`、`question`、根拠の`claim_ids`、`owner`、`affected_ids`、`blocks`、`state`、`resolution`、`reason`を持つ。`state`は`open`、`resolved`、`withdrawn`を区別し、`resolved`だけが非空の`resolution`を持つ。
- `question_review`: 質問台帳の全ID、確認者、一覧全体の確認内容、対話終了の真偽を持つ。全質問IDが一致し、`dialogue_complete=true`になるまで正本を保存しない。
- `solution_inputs[].classification`: `constraint`、`hypothesis`、`design_proposal`。`linked_id`はそれぞれCON、HYP、nullにする。設計案の`routed_to`には要求を変更せず技術方式を比較・選定する責務の機械識別子を記録する。
- `derived_requirements[]`: `DRV-` ID、`statement`、`classification`、`derived_from_claim_ids`、サービス特性、失敗リスク、必要な成果、検証方法、設計影響、見直し条件、後続を持つ。`confirmed`は確認済み根拠だけ、`hypothesis`は仮説根拠を一件以上持つ。
- `design_decisions[]`: `DEC-` ID、方式、`basis`、根拠主張、導出要件、理由、見直し条件、後続を持つ。`basis=agreed_decision`は合意済み根拠を、`basis=logically_required`は導出要件を必要とする。
- `scope_budget`: 実装必須、設計説明のみ、対象外、実現上の制約を別々の配列で持つ。
- `decision_history`: 成果物版ごとに変更した根拠と影響IDを残し、1から現在版まで連続させる。
- `terminology`: 定義本体ではなく、共有Markdown用語正本の`locator`、1以上の整数`version`と、正本内項目から日本語の`preferred_terms`への参照を持つ。用語や用語正本のIDを必須にせず、同じ項目の参照を複数箇所へ重複させない。
- `interaction_catalog.commands[]`: `CMD-` ID、名前、アクター、確認済み根拠、状態変更対象、成功時の`CEVT-` IDを持つ。`counterpart_review`は`paired`、`not_applicable`、`unresolved`の一つとし、`paired`は対コマンドを相互参照する。`unresolved`は`counterpart_open_question_ids`へ一件以上を結ぶ。`non_success_outcomes`は`no_change`、`rejected`、`failed`を別々に持ち、`defined`、`unresolved`、`not_applicable`の状態に応じて確定文または未決の問いを記録する。
- `interaction_catalog.queries[]`: `QRY-` ID、名前、アクター、確認済み根拠、読み取る対象、成功時の`QEVT-` IDを持つ。状態変化を持たせない。
- `interaction_catalog.command_events[]`: `CEVT-` ID、過去形の名前、確認済み根拠、完了事実、業務状態の対象、変更前後を持つ。変更前後が同じものはコマンドイベントにしない。
- `interaction_catalog.query_events[]`: `QEVT-` ID、過去形の名前、確認済み根拠、完了事実、読み取りにより観測できた結果を持つ。業務状態変化を持たせず、クエリの成功イベントとして参照する。
- `interaction_catalog.time_events[]`: `TEVT-` ID、過去形の名前、確認済み根拠、時刻または期限到達の事実、その時間上の基準を持つ。コマンド、クエリ、内部処理の事実として扱わない。
- `interaction_catalog.system_events[]`: `SEVT-` ID、過去形の名前、確認済み根拠、内部処理の観測事実、任意の関連イベントIDを持つ。業務状態変化を持たせず、コマンドまたはクエリの成功イベントとして参照しない。

用語正本はMarkdown表にしない。`## アクター`、`## コマンド`、`## クエリ`、`## コマンドイベント`、`## クエリイベント`、`## 時間イベント`、`## システムイベント`、`## 値・指標`、`## 状態`、`## データ`、`## 方針・制約`、`## 業務上の概念`、`## 負荷特性`、`## 設計上の概念`のうち該当する概念種別を置き、その下の`### 日本語の推奨用語名`に定義本文、状態、根拠、見直し条件を記録する。状態変更の意図はコマンド、読み取り専用操作はクエリ、各操作の成立事実はコマンドイベントとクエリイベント、時刻・期限到達は時間イベント、内部処理の観測事実はシステムイベントへ分ける。業務上の対象・関係・情報は業務上の概念、処理量や共有資源への負荷を増やす性質は負荷特性、測定値は値・指標へ分ける。用語見出しの重複と、概念種別に属さない用語を拒否する。

分類例として、会員はアクター、注文を登録する操作はコマンド、注文が登録された事実はコマンドイベント、注文履歴を取得する操作はクエリ、その取得が成立した事実はクエリイベント、保持期限に到達した事実は時間イベント、通知が配信先へ複製された内部処理の事実はシステムイベント、注文・会員関係・注文履歴は業務上の概念、一操作あたりの配信先数の増幅や操作頻度の集中は負荷特性、平均負荷は値・指標に当たる。この例の語や境界値を汎用既定へ登録せず、対象サービスの用語正本で意味を決める。
- `handoff.ready`がtrueなら作業を止める問いは空で状態は`ready_for_downstream`。falseなら作業を止める問いを1件以上持ち状態は`saved_with_open_questions`。

IDの意味を版更新で別の意味へ使い回さない。変更前のIDを廃止する場合は、その理由と影響を新しい根拠主張または未決の問いとして残す。
