# Good and Bad Tests

## Good Tests

**統合スタイル**: 内部の一部をモックするのではなく、実際のインターフェースを通してテストする。

```typescript
// GOOD: 観測可能な振る舞いをテストしている
test("user can checkout with valid cart", async () => {
  const cart = createCart();
  cart.add(product);
  const result = await checkout(cart, paymentMethod);
  expect(result.status).toBe("confirmed");
});
```

特徴:

- ユーザー/呼び出し元が気にする振る舞いをテストする
- 公開APIのみを使う
- 内部のリファクタに耐える
- HOW(どうやって)ではなくWHAT(何を)を記述する
- 1テストにつき論理的なアサーションは1つ

## Bad Tests

**実装詳細テスト**: 内部構造に結合している。

```typescript
// BAD: 実装詳細をテストしている
test("checkout calls paymentService.process", async () => {
  const mockPayment = jest.mock(paymentService);
  await checkout(cart, payment);
  expect(mockPayment.process).toHaveBeenCalledWith(cart.total);
});
```

危険信号:

- 内部の協調オブジェクトをモックしている
- プライベートメソッドをテストしている
- 呼び出し回数/順序をアサーションしている
- 振る舞いが変わっていないのにリファクタでテストが壊れる
- テスト名がWHAT(何を)ではなくHOW(どうやって)を記述している
- インターフェースではなく外部の手段を通して検証している

```typescript
// BAD: 検証のためにインターフェースを迂回している
test("createUser saves to database", async () => {
  await createUser({ name: "Alice" });
  const row = await db.query("SELECT * FROM users WHERE name = ?", ["Alice"]);
  expect(row).toBeDefined();
});

// GOOD: インターフェースを通して検証している
test("createUser makes user retrievable", async () => {
  const user = await createUser({ name: "Alice" });
  const retrieved = await getUser(user.id);
  expect(retrieved.name).toBe("Alice");
});
```

**同語反復的なテスト**: 期待値が実装をそのまま言い換えているだけなので、テストは構造上必ず通ってしまう。

```typescript
// BAD: 期待値がコードと同じ方法で再計算されている
test("calculateTotal sums line items", () => {
  const items = [{ price: 10 }, { price: 5 }];
  const expected = items.reduce((sum, i) => sum + i.price, 0);
  expect(calculateTotal(items)).toBe(expected);
});

// GOOD: 期待値が独立した既知のリテラルである
test("calculateTotal sums line items", () => {
  expect(calculateTotal([{ price: 10 }, { price: 5 }])).toBe(15);
});
```
