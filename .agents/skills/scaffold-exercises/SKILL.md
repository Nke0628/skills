---
name: scaffold-exercises
description: セクション、problem、solution、explainerを含む、lintを通過する演習ディレクトリ構造を作成する。ユーザーが演習のスキャフォールディング、演習スタブの作成、あるいは新しいコースセクションの設定を望んでいるときに使用する。
---

# Scaffold Exercises

`pnpm ai-hero-cli internal lint` を通過する演習ディレクトリ構造を作成し、その後 `git commit` でコミットする。

## ディレクトリ命名規則

- **セクション**: `exercises/` 内の `XX-section-name/`(例: `01-retrieval-skill-building`)
- **演習**: セクション内の `XX.YY-exercise-name/`(例: `01.03-retrieval-with-bm25`)
- セクション番号 = `XX`、演習番号 = `XX.YY`
- 名前はdash-case(小文字、ハイフン区切り)

## 演習のバリアント

各演習には、以下のサブフォルダのうち少なくとも一つが必要である。

- `problem/` - TODOを含む学生用ワークスペース
- `solution/` - リファレンス実装
- `explainer/` - TODOのない概念的な資料

スタブを作成する際は、計画に指定がない限り`explainer/`をデフォルトとする。

## 必須ファイル

各サブフォルダ(`problem/`、`solution/`、`explainer/`)には以下を満たす`readme.md`が必要である。

- **空でない**こと(実質的な内容が必要。タイトル行一つでも可)
- リンク切れがないこと

スタブを作成する際は、タイトルと説明を持つ最小限のreadmeを作成する。

```md
# 演習タイトル

ここに説明
```

サブフォルダにコードがある場合は、`main.ts`(1行超)も必要である。ただし、スタブについてはreadmeのみの演習でも問題ない。

## ワークフロー

1. **計画を解析する** - セクション名、演習名、バリアントの種類を抽出する
2. **ディレクトリを作成する** - 各パスに対して`mkdir -p`
3. **スタブreadmeを作成する** - バリアントフォルダごとにタイトル付きの`readme.md`を一つ
4. **lintを実行する** - `pnpm ai-hero-cli internal lint`で検証する
5. **エラーを修正する** - lintが通るまで繰り返す

## lintルールの概要

リンター(`pnpm ai-hero-cli internal lint`)は以下をチェックする。

- 各演習にサブフォルダ(`problem/`、`solution/`、`explainer/`)があること
- `problem/`、`explainer/`、`explainer.1/`のうち少なくとも一つが存在すること
- 主要なサブフォルダに`readme.md`が存在し、空でないこと
- `.gitkeep`ファイルがないこと
- `speaker-notes.md`ファイルがないこと
- readme内にリンク切れがないこと
- readme内に`pnpm run exercise`コマンドがないこと
- readmeのみの場合を除き、サブフォルダごとに`main.ts`が必要

## 演習の移動・リネーム

演習の番号変更や移動を行う際は以下の手順に従う。

1. ディレクトリのリネームには`mv`ではなく`git mv`を使う - git履歴を保持できる
2. 順序を保つよう数値の接頭辞を更新する
3. 移動後に再度lintを実行する

例:

```bash
git mv exercises/01-retrieval/01.03-embeddings exercises/01-retrieval/01.04-embeddings
```

## 例: 計画からのスタブ作成

以下のような計画が与えられたとする。

```
Section 05: Memory Skill Building
- 05.01 Introduction to Memory
- 05.02 Short-term Memory (explainer + problem + solution)
- 05.03 Long-term Memory
```

以下を作成する。

```bash
mkdir -p exercises/05-memory-skill-building/05.01-introduction-to-memory/explainer
mkdir -p exercises/05-memory-skill-building/05.02-short-term-memory/{explainer,problem,solution}
mkdir -p exercises/05-memory-skill-building/05.03-long-term-memory/explainer
```

続けてreadmeスタブを作成する。

```
exercises/05-memory-skill-building/05.01-introduction-to-memory/explainer/readme.md -> "# Introduction to Memory"
exercises/05-memory-skill-building/05.02-short-term-memory/explainer/readme.md -> "# Short-term Memory"
exercises/05-memory-skill-building/05.02-short-term-memory/problem/readme.md -> "# Short-term Memory"
exercises/05-memory-skill-building/05.02-short-term-memory/solution/readme.md -> "# Short-term Memory"
exercises/05-memory-skill-building/05.03-long-term-memory/explainer/readme.md -> "# Long-term Memory"
```
