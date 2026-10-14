# チーム固有レビューガイドライン

> チームの技術スタックと規約に固有の観点。チームに合わせて追記・削除する。
> 変更ファイルに関係するセクションだけを適用する。

---

## Rails: データベース・パフォーマンス

- [ ] N+1クエリが発生していないか（includes, preload, eager_load の適切な使い分け）
- [ ] joins使用時の想定レコード数が適切か
- [ ] delete_all, update_all などの処理件数が適切か（大量データ処理時のタイムアウト回避）
- [ ] レコード数が多い場合に `find_each`, `find_in_batches` を使用しているか
- [ ] インデックスが適切に設定されているか（migration含む）
- [ ] 必要なカラムのみ取得しているか
- [ ] countよりもexists?を使用すべき場面で適切に使い分けているか
- [ ] whereクエリで配列を渡す際、空配列チェックが実装されているか
- [ ] 一覧を取得する際にはorderをつけているか（データの順序保証）

---

## Rails: アーキテクチャ・設計パターン

- [ ] Fat Controllerになっていないか（ビジネスロジックの適切な配置）
- [ ] アプリケーションロジックとビジネスロジックが明確に区別されているか
- [ ] ロジックの肥大化に対して適切なパターンが適用されているか
  - アプリケーションロジックの肥大化 → Service Object / Form Object の活用
  - ビジネスロジックの肥大化 → Concern（モジュール）の活用
- [ ] Concernが適切に活用されているか
- [ ] 責務の適切な分離（Model-View-Controller の役割分担）
- [ ] RESTfulな設計になっているか
- [ ] DRY原則が守られているか
- [ ] SOLID原則の遵守

---

## Rails: セキュリティ

- [ ] SQLインジェクション対策が実装されているか
- [ ] Strong Parametersが適切に設定されているか
- [ ] アクセスするリソースに対する制限は適切に定義されているか
- [ ] XSS対策が適切に実装されているか（エスケープ処理）

---

## Rails: バリデーション・データ整合性

- [ ] モデルのValidationが適切に設定されているか
- [ ] データベースレベルの制約も設定されているか（NOT NULL, UNIQUE等）
- [ ] 関連データの整合性が保たれているか（dependent: :destroy等）
- [ ] enum の適切な使用と値の管理

---

## Rails: トランザクション・例外処理

- [ ] トランザクション処理が適切に実装されているか
- [ ] rollback条件が適切に設定されているか
- [ ] 例外処理が適切に実装されているか（rescue, ensure）

---

## Rails: テスト・品質保証

- [ ] RSpecのテストが適切に実装されているか
- [ ] FactoryBotの適切な使用
- [ ] factory_botのtraitを使って書く負担を減らしているか
- [ ] テストカバレッジが適切に保たれているか
- [ ] AAAパターン（Arrange-Act-Assert）に遵守していること

---

## Rails: マイグレーション

- [ ] マイグレーションが適切に実装されているか
- [ ] ダウンマイグレーションが実装されているか
- [ ] 本番環境での安全な実行を考慮しているか

---

## Rails: コールバック

- [ ] 大前提として、コールバックはなるべく利用しないこと
- [ ] モデルコールバックの濫用を避けているか

---

## Rails: ビュー・表示層

- [ ] ビューに複雑なロジックを書いていないか（ヘルパーメソッドやDecoratorの活用）

---


## Next.js: アーキテクチャ・設計

- [ ] Container / Presentational パターンが適切に活用されているか
- [ ] 責務分離が適切に行われているか（UI・ロジック・データ取得の分離）
- [ ] 型安全性（TypeScript）が保たれているか
- [ ] Pages Router の規約に従ったディレクトリ構成（pages/ components/ lib/）
- [ ] pages/ ディレクトリの適切な構造化
- [ ] Context API の適切な使用（過度なネストの回避）
- [ ] Custom Hooks の適切な抽象化
- [ ] getServerSideProps / getStaticProps / getInitialProps の適切な使い分け
- [ ] API routes の適切な設計と配置（pages/api/）

---

## Next.js: パフォーマンス・最適化

- [ ] 時間がかかる処理は、useMemo, useCallbackによる適切なメモ化が行われているか（乱用はしない）
- [ ] 不要なre-renderが発生していないか
- [ ] Image optimization が活用されているか（next/image）
- [ ] Font optimization が実装されているか（next/font または Google Fonts）
- [ ] getStaticProps + getStaticPaths による Static generation の活用
- [ ] Incremental Static Regeneration（ISR）の適切な使用（revalidate）
- [ ] getServerSideProps のパフォーマンス最適化

---

## Next.js: データフェッチング・状態管理

- [ ] getServerSideProps でのデータフェッチングが適切に実装されているか
- [ ] getStaticProps でのデータフェッチングが適切に実装されているか
- [ ] getStaticPaths による動的ルーティングの実装
- [ ] Form handling の実装（React Hook Form / Formik等）
- [ ] バリデーションの実装（Zod / Yup等）

---

## Next.js: デザインライブラリの準拠

- [ ] 直接的な色指定（#ffffff, variables.$color等）を避け、デザイントークンやテーマ関数を使用しているか
- [ ] 直接的なサイズ指定（16px, 1rem等）を避け、デザイントークンやテーマ関数を使用しているか
- [ ] プロジェクト固有のスタイル変数より、デザインシステムのライブラリを優先しているか
- [ ] デザイントークンの一貫性が保たれているか

---

## Next.js: ルーティング・ナビゲーション

- [ ] Pages Router の規約に従ったファイル配置
- [ ] Dynamic routing の適切な実装（[id].js, [...slug].js）
- [ ] Optional catch-all routes の適切な使用
- [ ] next/link による Client-side navigation の実装
- [ ] next/router の適切な活用（useRouter）
- [ ] Shallow routing の適切な使用
- [ ] Middleware の適切な活用
- [ ] リダイレクト処理の適切な実装（next.config.js, getServerSideProps）
- [ ] 404 / エラーページの実装（404.js, _error.js）

---

## Next.js: 認証・認可

- [ ] 認証フローが適切に実装されているか（NextAuth.js等）
- [ ] Protected routes の実装
- [ ] CSRF対策が実装されているか
- [ ] Session management の適切な実装
- [ ] JWT token の適切な管理
- [ ] Role-based access control の実装

---

## Next.js: 数値処理・計算ロジック

- [ ] 数値フォーマット関数で境界値テストが適切に実装されているか
- [ ] 数学的計算のコメントと実装が一致しているか
- [ ] 異常値（NaN、Infinity、負数）の処理が適切に実装されているか
- [ ] 大きな数値の処理でオーバーフローが発生しないか

---

## Next.js: パフォーマンス最適化（React特有）

- [ ] メモ化が必要な処理にuseMemo/useCallbackが適用されているか
- [ ] useMemo / useCallback を使いすぎていないか
  - [ ] メモ化のオーバーヘッドが計算コストより大きくなっていないか
  - [ ] シンプルな値や軽量関数に無理に使っていないか
- [ ] 重い計算処理が不要なre-renderを引き起こさないか

---

## Next.js: セキュリティ

- [ ] XSS対策が適切に実装されているか
- [ ] Content Security Policy（CSP）の設定
- [ ] HTTPS redirect の実装
- [ ] Secure headers の設定
- [ ] Environment variables の適切な管理
- [ ] Secrets の適切な保護

---

## Next.js: ユーザビリティ・SEO

- [ ] デザインシステムのライブラリが活用されているか
- [ ] エラーバウンダリーが実装されているか
- [ ] SEOに配慮したmeta情報が設定されているか
- [ ] レスポンシブデザインの適切な実装

---

## Next.js: 依存関係クリーンアップ

- [ ] 新しいコンポーネント導入時、既存の重複コードが削除されているか
- [ ] 未使用のimport文・変数・型定義が残っていないか
- [ ] 新旧コンポーネントの責務分離が適切に行われているか
- [ ] Container/Presentationalパターンが維持されているか

---

## Next.js: テスト・品質保証

- [ ] Unit tests が適切に実装されているか（Jest / Vitest）
- [ ] Component testing の実装（React Testing Library）
- [ ] テストカバレッジが適切に保たれているか

---

## Next.js: 監視・分析

- [ ] Error monitoring の設定（Sentry等）
- [ ] ログレベルの適切な設定
- [ ] センシティブ情報のログ出力回避
