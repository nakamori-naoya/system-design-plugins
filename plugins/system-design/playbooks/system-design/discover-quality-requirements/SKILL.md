---
name: discover-quality-requirements
description: 業務影響を観測点、指標、閾値、時間窓、検証方法を持つ品質要求へ落とす独立プレイブック。品質要求を発見したいときに使う。
---

# discover-quality-requirements

同梱の`playbook.yml`を公開入口とし、内部プラグイン`discover-quality-requirements`の同名スキルへ明示的にルーティングする。クラウドや製品は選定しない。

## 実行

1. `scripts/prepare.sh`で、このプレイブックと対応スキルが同じ配布パッケージ内にあることを検査する。
2. `playbook.yml`の`steps`に従い、grill、ground、`skill: discover-quality-requirements`、material、verify、write-docを順に実行する。
3. 成否にかかわらずcleanupを実行し、保存済み正本と参照資料を保持する。`scripts/resolve.sh`は公開入口と内部スキルの対応を機械可読なJSONとして確認する。

入力、出力、停止条件、非責務の詳細は、同梱内部スキル`skills/discover-quality-requirements/SKILL.md`を正本とする。

## 公開依存の実行契約

`grill`は契約ID `grill/grill`の公開playbookとして呼ぶ。依頼と参照資料からは決まらない問いを、推奨回答と理由付きで1問ずつ渡す。返った`decisions`と`open_questions`を分離したまま`ground`へ渡し、未決を要求、閾値、仮説、設計決定へ昇格させない。grill用の解決済み設定はgrillが後片付けする。

`ground`、同名の一責務skill、`material`、`verify`を順に実行する。`verify`が`unresolved`を返した場合もwrite-docを実行し、未決状態のMarkdown正本を保存する。その正本とplaybook出力には`status: unresolved`、`open_questions`、`handoff.ready: false`を残し、未決を確定前提として後続へ渡さない。

`write-doc`は契約ID `write-doc/write-doc`の公開playbookとして呼び、`material`の絶対path、媒体`markdown`、日本語の本文題名と保存用ASCII名`quality-requirements.md`を区別して渡す。呼出側が公開入口E1で作ったwrite-doc用設定だけを呼出側が保持し、最後の利用後に成功・失敗のどちらでも後片付けする。write-docの内部skill、references、非公開scriptは参照しない。

## 後片付け

`always_run: true`の最終工程で、このplaybookが作った一時成果物だけを削除する。参照資料、他playbookの一時領域、保存済みMarkdown正本は削除しない。所有を証明できないpathがあれば削除せず停止する。
