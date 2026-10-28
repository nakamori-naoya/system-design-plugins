> 共通の規約は /Users/naoya-nakamoriq/Documents/Github/harness-pluginsv2/AGENTS.md にある。ここには、この repository だけの規則を置く。

# system-design

この repository は、要件と非機能要件を根拠付きで書き、その成果からクラウドのインフラ構成を設計する skill を配布する。インストール対象は package `system-design` 一つで、公開入口は二つである。`discover-requirements` は要件と非機能要件の二つの資料型を扱い、発見と定式化を同じ入口で行って、深さは grill の問い方で分ける。`design-cloud-architecture` はクラウドの構成を設計し、構成図を draw.io で描く。

- 資料は write-doc が保存する Markdown 1 本と、その資料の `.assets/` に置く draw.io の図だけで、節構成と検査が読む目印は write-doc の各型の template が持つ。検査スクリプトはその目印だけを読み、見出しの文言を読まない。
- 資料は、結論と図を先頭に置いた、今のあるべき姿だけを書く。要求ごとの ID、追跡の表、決定の番号、Mermaid は使わない。
- 用語の持ち主は bdd のユビキタス言語で、この repository は独自の用語集を持たない。
- 事実、決めたこと、推定や仮置き、未確認を文の言い方で区別し、根拠のない値やクラウドの仕様を確定事項として補わない。
- `design-cloud-architecture` は、利用者が明示した provider（`aws` か `gcp`）を入力で受け取り、既定値を持たない。要求や品質目標の独断の変更、論理 DB 設計、IaC、deploy は行わない。
- 案件固有の値（特定サービスの用語、閾値、採用技術）を既定値や見本の正解にしない。
