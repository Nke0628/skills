# When to Mock

**システム境界**でのみモックする:

- 外部API(決済、メールなど)
- データベース(場合による。テスト用DBを優先する)
- 時刻/乱数
- ファイルシステム(場合による)

モックしないもの:

- 自分自身のクラス/モジュール
- 内部の協調オブジェクト
- 自分がコントロールしているもの全般

## モック可能性を意識した設計

システム境界では、モックしやすいインターフェースを設計する。

**1. 依存性注入を使う**

外部依存を内部で生成するのではなく、渡す。

```typescript
// モックしやすい
function processPayment(order, paymentClient) {
  return paymentClient.charge(order.total);
}

// モックしにくい
function processPayment(order) {
  const client = new StripeClient(process.env.STRIPE_KEY);
  return client.charge(order.total);
}
```

**2. 汎用フェッチャーよりSDKスタイルのインターフェースを優先する**

条件分岐を含む1つの汎用関数の代わりに、外部操作ごとに専用の関数を作る。

```typescript
// GOOD: 各関数を独立してモックできる
const api = {
  getUser: (id) => fetch(`/users/${id}`),
  getOrders: (userId) => fetch(`/users/${userId}/orders`),
  createOrder: (data) => fetch('/orders', { method: 'POST', body: data }),
};

// BAD: モックにはモック内部で条件分岐が必要になる
const api = {
  fetch: (endpoint, options) => fetch(endpoint, options),
};
```

SDKアプローチの利点:
- 各モックが1つの具体的な形状を返す
- テストセットアップに条件分岐がない
- どのエンドポイントをテストが使っているか見やすい
- エンドポイントごとの型安全性
