# テストデータの契約

各公開スキルは、少なくとも`success`、`out_of_scope`、`boundary`のテストデータを持つ。各テストデータには次を記録する。

- 入力と、その根拠状態
- 一条件だけ変えた点
- 期待する分岐、停止、出力
- 禁止する補完または越境
- 静的検査、実モデル評価、実ツール端から端までの検証（E2E）のどれを実行したか

テストデータファイルが存在するだけでは合格にしない。実モデル未実行なら未検証として報告する。

`runtime-config/`は`design-cloud-architecture`の共通prepare/run-config経路を実行する設定テストデータである。`aws.config.yml`は正常系、`provider-missing.config.yml`は必須値欠落、`provider-invalid.config.yml`はenum外プロバイダーの負例として実行する。

`playbooks/`は4本の公開プレイブックごとに、`normal`、`unresolved`、`invalid-input`、`cleanup-boundary`を持つ。正常系と未決系はどちらも日本語Markdown正本を保存する。未決系は`status: unresolved`、`open_questions`、`handoff.ready: false`を残す。入力契約違反は正本工程へ進まず最終工程を実行し、境界系は所有範囲外の削除を拒否する。

`terminology/success.md`は共有用語正本の正常例である。用語IDを持たず、日本語の推奨用語名を概念種別ごとのMarkdown見出しとして置く。状態変更の意図はコマンド、読み取り専用操作はクエリ、各操作が成立した事実はコマンドイベントとクエリイベント、時刻・期限到達の事実は時間イベント、内部処理の観測事実はシステムイベントとして区別する。業務対象・関係・情報は業務上の概念、処理量を増幅する性質は負荷特性、測定値は値・指標として区別する。用語ごとに定義、合意済みまたは暫定の状態、根拠、見直し条件を持ち、Markdown表は使わない。
