# 期待する判定

この較正の資料は、2026-09-27 の1回目の実行（claude plugin eval、`--runs 1 --ablation none`）で作られた `requirements-discovery.md` と grill の記録である。下の判定は、eval を組んだ担当が資料、記録、要件の文書を読んで出したもので、採点役がこれを再現できるかで採点の形を確かめる。境目と書いた条件は、読み方で判定が分かれうるので、一致の数を別に数える。

採点役には、このファイルを読ませない。

## 判定

- evidence-no-promotion: PASS
- evidence-open-kept: PASS
- how-not-requirement: PASS
- derived-causal: FAIL
- owner-no-numbers-copy: PASS（境目）
- language-from-knowledge: PASS
- scope-and-done: PASS
- observable-outcomes: PASS
- pairs-checked: PASS
- grill-only-conclusion-changing: PASS
- et-req-strong-and-delayed: PASS
- et-req-open-not-answered: PASS
- et-req-payment-outcome: PASS
- et-req-how-classified: FAIL（境目）

## 理由

`REQ-` はどれも要件の文書で未決・暫定と書かれていない決まりに結ばれ、暫定値の数値は REQ-HYP-002 に、仮置きの答えは REQ-HYP-003〜006 に置かれているので、evidence-no-promotion は PASS とした。承認した人の記名が無いことを本文で断っている点は、条件の FAIL の文（暫定値、仮定、未決、仮置きを根拠にする）に当たらない。

要件の文書の未決は REQ-OQ-001〜013 に残り、本文でも断定していないので、evidence-open-kept と et-req-open-not-answered は PASS とした。

owner-no-numbers-copy は、REQ-HYP-001 と 002 に規模と品質の数値を並べているが、仮説として後続の型へ送る書き方なので PASS とした。値を並べたこと自体を書き写しと読むかで分かれるので境目とした。

et-req-how-classified は、「提供する結果」の発券の節に「入場に使う画面の表示（入場コード）は…一定の時間ごとに変わる。間隔の30秒は暫定値である」と、入場コードが変わる方式を利用者の得る結果の節に書いているので FAIL とした。待合室と端末へ入れておく情報と決済の送り方は、未決か DEC-001 か後続の比較に分けている。一文の置き場を方式の混入と読むかで分かれるので境目とした。

derived-causal は、最初は PASS と置いたが、採点役3回がそろって FAIL とし、読み直して採点役が正しいと判断した。「以下の性質そのものは値に依らず成り立つ」と断りながら、DRV-003 と DRV-005 の段落に「開演30分前」「10分程度の通信断」「5万枚」を書き写しており、特性の値は利用負荷の資料が持つという条件の文に当たる。
