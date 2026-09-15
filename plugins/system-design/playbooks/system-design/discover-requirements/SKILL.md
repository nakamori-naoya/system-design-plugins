---
name: discover-requirements
description: 要求源とサービス特性から、明示要求、導出要件、理由付き設計判断、仮説、未決を分離した要求発見正本を作る独立プレイブック。要求を整理し、暗黙の必要性まで明らかにしたいときに使う。
---

# discover-requirements

同梱の`playbook.yml`を公開入口とし、内部プラグイン`discover-requirements`の同名スキルへ明示的にルーティングする。Journey、Domain、データモデル、クラウド設計は実行しない。

## 実行

1. `scripts/prepare.sh`で、このプレイブックと対応スキルが同じ配布パッケージ内にあることを検査する。
2. `playbook.yml`の`steps`に従い、grill、ground、`skill: discover-requirements`、material、verify、write-docを順に実行する。
3. 成否にかかわらずcleanupを実行し、保存済み正本と参照資料を保持する。`scripts/resolve.sh`は公開入口と内部スキルの対応を機械可読なJSONとして確認する。

入力、出力、停止条件、非責務の詳細は、同梱内部スキル`skills/discover-requirements/SKILL.md`を正本とする。

共有用語がある場合は、一つのMarkdown用語正本の所在と版を入力に含める。用語や用語正本のIDは要求せず、成果物は日本語の推奨用語名を参照する。用語正本は表ではなく、アクター、コマンド、クエリ、コマンドイベント、クエリイベント、時間イベント、システムイベント、値・指標、状態、データ、方針・制約、業務上の概念、負荷特性、設計上の概念の見出しで各用語の概念種別を示す。要求発見では状態変更操作をコマンド、読み取り専用操作をクエリとして棚卸しし、それぞれを成功時のコマンドイベントとクエリイベントへ結ぶ。時刻・期限到達は時間イベント、内部処理の観測事実はシステムイベントとして分け、対操作と非成功結果の不明点を未決として残す。

## 公開依存の実行契約

`grill`は契約ID `grill/grill`の公開playbookとして呼ぶ。依頼と参照資料からは決まらない問いを、推奨回答と理由付きで1問ずつ渡す。返った`decisions`と`open_questions`を分離したまま`ground`へ渡し、未決を要求、閾値、仮説、設計決定へ昇格させない。grill用の解決済み設定はgrillが後片付けする。

`ground`、同名の一責務skill、`material`、`verify`を順に実行する。`verify`が`unresolved`を返した場合もwrite-docを実行し、未決状態のMarkdown正本を保存する。その正本とplaybook出力には`status: unresolved`、`open_questions`、`handoff.ready: false`を残し、未決を確定前提として後続へ渡さない。

`write-doc`は契約ID `write-doc/write-doc`の公開playbookとして呼び、`material`の絶対path、媒体`markdown`、日本語の本文題名と保存用ASCII名`requirements-discovery.md`を区別して渡す。呼出側が公開入口E1で作ったwrite-doc用設定だけを呼出側が保持し、最後の利用後に成功・失敗のどちらでも後片付けする。write-docの内部skill、references、非公開scriptは参照しない。

## 後片付け

`always_run: true`の最終工程で、このplaybookが作った一時成果物だけを削除する。参照資料、他playbookの一時領域、保存済みMarkdown正本は削除しない。所有を証明できないpathがあれば削除せず停止する。
