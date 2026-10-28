# テストデータ

三つの型の資料の正例を一本ずつ置く。`requirements-discovery.md`、`non-functional-requirements.md`、`cloud-architecture.md` で、図は資料の名前に `.assets/` を付けたディレクトリにある。

test は正例を一時ディレクトリへ写し、文字列の置換や図の削除で反例に変えて検査 script に渡す。正例のファイルは書き換えない。各検査の合格述語と反例は、それぞれの script の docstring に書いてある。

正例が通ることは、構文の検査が通ることだけを示す。案件に固有の値を、既定値や正解として扱わない。
