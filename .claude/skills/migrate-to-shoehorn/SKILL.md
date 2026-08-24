---
name: migrate-to-shoehorn
description: テストファイルの `as` 型アサーションを @total-typescript/shoehorn に移行する。ユーザーがshoehornに言及したとき、テスト内の `as` を置き換えたいとき、あるいは部分的なテストデータが必要なときに使用する。
---

# Migrate to Shoehorn

## なぜshoehornなのか

`shoehorn` を使うと、TypeScriptを満足させたまま、テストで部分的なデータを渡せるようになる。`as` アサーションを型安全な代替手段に置き換える。

**テストコード専用。** shoehornを本番コードで使ってはならない。

テストにおける `as` の問題点:

- 使わないよう訓練されている
- 対象の型を手動で指定しなければならない
- 意図的に誤ったデータを渡すための二重as(`as unknown as Type`)

## インストール

```bash
npm i @total-typescript/shoehorn
```

## 移行パターン

### 必要なプロパティが少ない大きなオブジェクト

移行前:

```ts
type Request = {
  body: { id: string };
  headers: Record<string, string>;
  cookies: Record<string, string>;
  // ...他に20個のプロパティ
};

it("gets user by id", () => {
  // body.idだけが必要だが、Request全体を偽装しなければならない
  getUser({
    body: { id: "123" },
    headers: {},
    cookies: {},
    // ...20個すべてのプロパティを偽装
  });
});
```

移行後:

```ts
import { fromPartial } from "@total-typescript/shoehorn";

it("gets user by id", () => {
  getUser(
    fromPartial({
      body: { id: "123" },
    }),
  );
});
```

### `as Type` → `fromPartial()`

移行前:

```ts
getUser({ body: { id: "123" } } as Request);
```

移行後:

```ts
import { fromPartial } from "@total-typescript/shoehorn";

getUser(fromPartial({ body: { id: "123" } }));
```

### `as unknown as Type` → `fromAny()`

移行前:

```ts
getUser({ body: { id: 123 } } as unknown as Request); // 意図的に誤った型
```

移行後:

```ts
import { fromAny } from "@total-typescript/shoehorn";

getUser(fromAny({ body: { id: 123 } }));
```

## 使い分け

| 関数             | ユースケース                                       |
| --------------- | -------------------------------------------------- |
| `fromPartial()` | 型チェックを通したまま部分的なデータを渡す           |
| `fromAny()`     | 意図的に誤ったデータを渡す(オートコンプリートは維持) |
| `fromExact()`   | 完全なオブジェクトを強制する(あとでfromPartialに置き換え) |

## ワークフロー

1. **要件を集める** - ユーザーに尋ねる:
   - `as` アサーションが問題を起こしているテストファイルはどれか?
   - 一部のプロパティしか重要でない大きなオブジェクトを扱っているか?
   - エラーテストのために意図的に誤ったデータを渡す必要があるか?

2. **インストールと移行**:
   - [ ] インストール: `npm i @total-typescript/shoehorn`
   - [ ] `as` アサーションのあるテストファイルを探す: `grep -r " as [A-Z]" --include="*.test.ts" --include="*.spec.ts"`
   - [ ] `as Type` を `fromPartial()` に置き換える
   - [ ] `as unknown as Type` を `fromAny()` に置き換える
   - [ ] `@total-typescript/shoehorn` からのimportを追加する
   - [ ] 型チェックを実行して検証する
