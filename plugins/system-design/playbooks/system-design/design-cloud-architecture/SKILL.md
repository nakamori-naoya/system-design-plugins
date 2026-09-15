---
name: design-cloud-architecture
description: AWSまたはGCPの実行時設定を根拠として解決し、比較、ADR、Mermaid図、要求追跡を作る独立プレイブック。クラウド構成を設計したいときに使う。
---

# design-cloud-architecture

同梱の`playbook.yml`を公開入口とし、内部プラグイン`design-cloud-architecture`の同名スキルへ明示的にルーティングする。要求、Journey、Domain、論理データモデルを作り直さず、Terraformを実装しない。

## 実行

1. `scripts/prepare.sh <対象リポジトリ>`で、一実行だけに閉じた解決済み設定を作る。プロバイダー未指定・不正値では停止する。
2. `scripts/resolve.sh <解決済み設定>`で、プロバイダー、解決済み設定path、設定指紋、選択元を一つの設計入力根拠へ変換する。この値を内部skillへ渡し、内部skillでは二重にprepareしない。
3. grill、ground、`skill: design-cloud-architecture`、material、verify、write-docを順に実行し、検証済みのクラウドアーキテクチャ正本を作る。
4. 成否にかかわらず`finalize-provider`工程として`scripts/finalize.sh <解決済み設定>`を実行する。

入力、出力、停止条件、非責務の詳細は、同梱内部スキル`skills/design-cloud-architecture/SKILL.md`を正本とする。

共有用語がある場合は、一つのMarkdown用語正本の所在と版を入力に含める。用語や用語正本のIDは要求せず、成果物は日本語の推奨用語名を参照する。用語正本は表ではなく、アクター、コマンド、クエリ、コマンドイベント、クエリイベント、時間イベント、システムイベント、値・指標、状態、データ、方針・制約、業務上の概念、負荷特性、設計上の概念の見出しで各用語の概念種別を示す。

## 公開依存の実行契約

`grill`は契約ID `grill/grill`の公開playbookとして呼ぶ。依頼と参照資料からは決まらない問いを、推奨回答と理由付きで1問ずつ渡す。返った`decisions`と`open_questions`を分離したまま`ground`へ渡し、未決を要求、閾値、仮説、設計決定へ昇格させない。grill用の解決済み設定はgrillが後片付けする。

`ground`、同名の一責務skill、`material`、`verify`を順に実行する。`verify`が`unresolved`を返した場合もwrite-docを実行し、未決状態のMarkdown正本を保存する。その正本とplaybook出力には`status: unresolved`、`open_questions`、`handoff.ready: false`を残し、未決を確定前提として後続へ渡さない。

`write-doc`は契約ID `write-doc/write-doc`の公開playbookとして呼び、`material`の絶対path、媒体`markdown`、日本語の本文題名と、保存契約に適合するASCII名`cloud-architecture.md`を区別して渡す。呼出側が公開入口E1で作ったwrite-doc用設定だけを呼出側が保持し、最後の利用後に成功・失敗のどちらでも後片付けする。write-docの内部skill、references、非公開scriptは参照しない。

## 後片付け

`always_run: true`の最終工程で、このplaybookが作った一時成果物だけを削除する。参照資料、他playbookの一時領域、保存済みMarkdown正本は削除しない。所有を証明できないpathがあれば削除せず停止する。
