# 期待する判定

この較正の資料は、2026-09-27 の1回目の実行（claude plugin eval、`--runs 1 --ablation none`）で作られた `workload-model.md` と grill の記録である。上流には、同じ日の要件のケースの成果（`materials/upstream/requirements-discovery.md`）を渡した。下の判定は、eval を組んだ担当が資料、記録、要件の文書を読んで出したもので、採点役がこれを再現できるかで採点の形を確かめる。境目と書いた条件は、読み方で判定が分かれうるので、一致の数を別に数える。

採点役には、このファイルを読ませない。

## 判定

- value-complete: PASS
- evidence-no-promotion: PASS
- no-generic-multiplier: PASS
- peak-and-skew: PASS
- retention-values-only: PASS
- owner-no-slo-no-solution: PASS
- design-input-linked: PASS
- scope-roles: PASS（境目）
- grill-only-conclusion-changing: PASS
- et-wl-hot-target: PASS
- et-wl-confidence-kept: PASS
- et-wl-external-rate: PASS

## 理由

設計入力の値はどれも単位と時間窓を持ち、根拠の状態はすべて hypothesis で、演習の観測も仮説の根拠として書かれているので、value-complete と evidence-no-promotion は PASS とした。抽選と分配の山は「平均に一般の倍率を掛けたピークは置かない」として未決にしているので、no-generic-multiplier は PASS とした。

scope-roles は、公演一つ・会場一つの値を設計入力とし、中央全体の重なりを未決にして書き分けているので PASS としたが、比べるための参照値という役割を明示した値が無いので境目とした。

「実測の値が仮説の半分未満か二倍を超えたら」の見直しの閾値には根拠が書かれていないが、この種類の条件のどれにも当たらないので判定に使っていない。
