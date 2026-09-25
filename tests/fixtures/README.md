# テストデータ

四つの型の資料の正例を一本ずつ置く。`requirements-discovery.md`、`workload-model.md`、`quality-requirements.md`、`cloud-architecture.md` で、同じ架空の対象（申請結果の確認）について上流から下流への ID の参照が閉じている。下流の型の検査は、上流の正例を `--upstream` に渡して実行する。

test は正例を文字列の置換で反例と境界例に変えて、検査 script へ標準入力で渡す。正例のファイルは書き換えず、一時ファイルも作らない。各検査の合格述語、反例、境界例は、それぞれの script の docstring に書いてある。

正例が通ることは、構造の検査が通ることだけを示す。案件に固有の値を、既定値や正解として扱わない。
