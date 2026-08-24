# Issue tracker: Local Markdown

このリポジトリのイシューとスペックは`.scratch/`配下のmarkdownファイルとして存在する。

## 慣習

- 1機能につき1ディレクトリ: `.scratch/<feature-slug>/`
- スペックは`.scratch/<feature-slug>/spec.md`
- 実装イシューは`.scratch/<feature-slug>/issues/<NN>-<slug>.md`に1チケット1ファイルとして置き、`01`から採番する。単一の統合チケットファイルにはしない。
- トリアージ状態は各イシューファイルの先頭付近にある`Status:`行に記録する(ロール文字列については`triage-labels.md`を参照)
- コメントと会話履歴はファイル末尾の`## Comments`見出しの下に追記する

## スキルが「イシュートラッカーに公開する」と言っている場合

`.scratch/<feature-slug>/`配下に新しいファイルを作成する(必要ならディレクトリも作成する)。

## スキルが「関連チケットを取得する」と言っている場合

参照されているパスのファイルを読む。ユーザーは通常、パスまたはイシュー番号を直接渡してくる。

## Wayfindingの操作

`/wayfinder`が使う。**マップ**はチケットごとに1つの**子**ファイルを持つファイルである。

- **マップ**: `.scratch/<effort>/map.md`(Notes / Decisions-so-far / Fogの本文)。
- **子チケット**: `.scratch/<effort>/issues/NN-<slug>.md`、`01`から採番し、本文に質問を記載する。`Type:`行がチケットの種類(`research`/`prototype`/`grilling`/`task`)を記録し、`Status:`行が`claimed`/`resolved`を記録する。
- **ブロッキング**: 先頭付近の`Blocked by: NN, NN`行。リストされたすべてのファイルが`resolved`になるとチケットのブロックは解除される。
- **フロンティア**: `.scratch/<effort>/issues/`をスキャンし、オープンで、ブロックされておらず、クレームされていないファイルを探す。番号の若い方が勝つ。
- **クレーム**: 作業前に`Status: claimed`を設定して保存する。
- **解決**: `## Answer`見出しの下に回答を追記し、`Status: resolved`を設定し、それから`map.md`のDecisions-so-farにコンテキストポインタ(gistとリンク)を追記する。
