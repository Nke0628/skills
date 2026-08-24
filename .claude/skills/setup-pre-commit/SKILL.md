---
name: setup-pre-commit
description: 現在のリポジトリにHuskyのpre-commitフックをlint-staged(Prettier)、型チェック、テストとともにセットアップする。ユーザーがpre-commitフックの追加、Huskyのセットアップ、lint-stagedの設定、コミット時のフォーマット/型チェック/テストの追加を望むときに使う。
---

# Setup Pre-Commit Hooks

## これがセットアップするもの

- **Husky** pre-commitフック
- ステージ済みの全ファイルにPrettierを実行する**lint-staged**
- **Prettier**の設定(存在しない場合)
- pre-commitフック内の**typecheck**と**test**スクリプト

## 手順

### 1. パッケージマネージャを検出する

`package-lock.json`(npm)、`pnpm-lock.yaml`(pnpm)、`yarn.lock`(yarn)、`bun.lockb`(bun)を確認する。存在する方を使う。不明な場合はnpmをデフォルトとする。

### 2. 依存関係をインストールする

devDependenciesとしてインストールする。

```
husky lint-staged prettier
```

### 3. Huskyを初期化する

```bash
npx husky init
```

これにより`.husky/`ディレクトリが作成され、package.jsonに`prepare: "husky"`が追加される。

### 4. `.husky/pre-commit`を作成する

このファイルを書く(Husky v9+ではシバンは不要):

```
npx lint-staged
npm run typecheck
npm run test
```

**適応させる**: `npm`を検出したパッケージマネージャに置き換える。リポジトリのpackage.jsonに`typecheck`や`test`スクリプトがない場合は、該当する行を省略し、ユーザーにその旨を伝える。

### 5. `.lintstagedrc`を作成する

```json
{
  "*": "prettier --ignore-unknown --write"
}
```

### 6. `.prettierrc`を作成する(存在しない場合)

Prettierの設定が既に存在しない場合のみ作成する。以下のデフォルトを使う。

```json
{
  "useTabs": false,
  "tabWidth": 2,
  "printWidth": 80,
  "singleQuote": false,
  "trailingComma": "es5",
  "semi": true,
  "arrowParens": "always"
}
```

### 7. 検証する

- [ ] `.husky/pre-commit`が存在し、実行可能である
- [ ] `.lintstagedrc`が存在する
- [ ] package.jsonの`prepare`スクリプトが`"husky"`である
- [ ] Prettierの設定が存在する
- [ ] `npx lint-staged`を実行して動作を確認する

### 8. コミットする

変更・作成したファイルをすべてステージし、次のメッセージでコミットする: `Add pre-commit hooks (husky + lint-staged + prettier)`

これにより新しいpre-commitフックが実行される。すべてが機能しているかどうかの良いスモークテストになる。

## 注記

- Husky v9+はフックファイルにシバンを必要としない
- `prettier --ignore-unknown`はPrettierが解析できないファイル(画像など)をスキップする
- pre-commitはまずlint-staged(高速でステージ済みファイルのみ)を実行し、その後フルの型チェックとテストを実行する
