# 2026-09-16以前のJSON正本の記録

このdirectoryは、system-designの4入口がJSON正本（`<repo>/system-design/<kind>/<slug>.<kind>.json`、`schema_version: 2`）を持っていた時期のfixtureを、資産として保全したものである。2026-09-16のハーネス進化第3回（D5）でJSON正本を廃止し、write-docが保存するMarkdown資料を唯一の正本にしたため、現行の検査script（`requirements.py` / `workload.py` / `quality.py` / `architecture.py`）はJSONを読まず、現行testもこのdirectoryを参照しない。

| 移動元 | 内容 |
|---|---|
| `tests/fixtures/discover-requirements/{success,boundary,cases}.json` | 要求発見のJSON正本の正例・境界例・シナリオ |
| `tests/fixtures/discover-workload-model/{success,cases}.json` | 利用負荷モデルのJSON正本の正例・シナリオ |
| `tests/fixtures/discover-quality-requirements/{success,cases}.json` | 品質要求のJSON正本の正例・シナリオ |
| `tests/fixtures/design-cloud-architecture/{success,cases}.json` | クラウドアーキテクチャのJSON正本の正例・シナリオ |
| `tests/fixtures/playbooks/*.json` | 4入口の `normal` / `unresolved` / `invalid-input` / `cleanup-boundary` の意味評価シナリオ（`grill` keyを含む） |

これらは当時の判断記録として読む。現行の記法と検査は `tests/fixtures/README.md` と各入口の `references/*-contract.md` が定める。削除は別の明示された変更として扱う。
