---
description: 電子チケットの要件の文書と業務知識を渡し、discover-requirements で要件の資料（requirements-discovery 型）を作らせる。grill の問いには実行者が渡した資料の事実で答える。
tags: [electronic-ticket, requirements-discovery]
plugins: ["../../../plugins/system-design"]
max_turns: 200
timeout_seconds: 3600
allowed_tools: [Read, Glob, Grep, Skill, TodoWrite, Write, Edit, Bash]
---

電子チケットのサービス「ステージパス」について、要件の資料（requirements-discovery 型）を新しく作ってください。資料の型は要件（requirements-discovery）です。

## 入力

要件の文書は、この作業場所の `input/` の下にある三つのファイルです。業務知識の資料は `business-knowledge/<業務>/business-knowledge.md` の六本で、業務の語の持ち主です。業務知識の資料の中にほかの資料へのリンクがありますが、置かれていないものは、資料が無いまま進めてください。どの資料も書き換えないでください。

## 保存先

資料は、作業場所の `out/requirements-discovery.md` に新しく保存してください。skill が絶対パスを求めたら、作業場所の絶対パスを `pwd` で確かめて渡してください。

## ほかの package のファイル

この環境には write-doc と grill の skill が入っていません。代わりに、その最新のファイルを作業場所へ写してあります。skill が write-doc の template、見本、規範を読むよう求めたら `harness/write-doc/` の下を、grill の規律に従うよう求めたら `harness/grill/SKILL.md` を読んでください。write-doc に保存を任せるよう求められたら、`harness/write-doc/SKILL.md` を読み、その指示どおりに保存してください。

## grill の問いへの答え方

この実行には、問いに答える利用者がいません。あなたが利用者の代わりも務めます。skill が grill で問いを出したら、次の決まりで自分で答えてください。

- 要件の文書、業務知識、上流の資料にある事実で答えが決まるなら、その事実で答える。
- 渡した資料に無いことは、問いに添えた推奨を仮置きする。仮置きした答えは合意ではないので、決定として本文で断定せず、資料の仮説か未決に、仮置きであること、根拠、採らなかった案、誰が決めるかと一緒に書く。
- 推奨も無いときは、未決として残す。要件の文書で未決、暫定、仮定と書かれていることも、合意された答えが無いものとして扱う。

問い、推奨、あなたの答え、その根拠（どのファイルのどの文か、推奨を仮置きしたか）は、出た順にすべて `grill-log/requirements-discovery.md` に書いてください。grill の終わりの一覧も、同じファイルに書いてください。問いが一つも無かったときも、そのファイルを作り、問わなかった理由を書いてください。

## 止まるとき

skill の停止条件に当たったら、skill の指示どおりに止まってください。止まったときは、何が分からず、それで結論のどこが変わるかを報告に書いてください。

## 報告

最後に、日本語で、保存した資料のパス、検査の script の結果と status、grill の問いの数、推奨を仮置きした未決、途中で止まったならその理由を短く書いてください。
