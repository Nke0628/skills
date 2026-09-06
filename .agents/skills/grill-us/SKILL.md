---
name: grill-us
description: "詳細な実装計画を立てられるだけの要件定義を作る: grillingで合意形成し、domain-modelingでドキュメント化し、受け入れ条件をBDD形式にしたspec.mdとして出力する。"
disable-model-invocation: true
---

# Grill Us

機能の概要を、実装に着手できる要件定義(spec.md)に変換する。Skillツールを2回呼び出す: 1回目は「grilling」、2回目は「domain-modeling」。

## プロセス

Skillツールを「grilling」で呼び出し、合意形成する。フロンティアがコードベースの事実を必要とする場合はgrillingの流儀に従いサブエージェントに調べさせ、ユーザーには人にしか決められないことだけを聞く。フロンティアが尽きるまでラウンドを繰り返す。

grillingと並行・事後に、Skillツールを「domain-modeling」で呼び出し、確定した用語を`CONTEXT.md`に、後戻りしにくい決定をADRに反映する。

grillingとdomain-modelingで合意した内容を、実装計画を立てられるだけの粒度で自由記述にまとめる。セクション構成は決め打ちせず、その要件に必要なものを過不足なく書く。ただし**受け入れ条件だけは必ずBDD形式(Given/When/Then)のシナリオで書く**。

```
Scenario: <シナリオ名>
  Given <前提条件>
  When <操作>
  Then <期待される結果>
```

ユーザーに提示して合意を取り、出力先ディレクトリを確認したうえで`spec.md`として書き込む。パスをユーザーに報告する。
