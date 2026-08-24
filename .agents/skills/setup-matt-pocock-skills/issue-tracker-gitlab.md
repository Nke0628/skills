# Issue tracker: GitLab

このリポジトリのイシューとスペックはGitLabイシューとして存在する。すべての操作に[`glab`](https://gitlab.com/gitlab-org/cli) CLIを使う。

## 慣習

- **イシューを作成する**: `glab issue create --title "..." --description "..."`。複数行の説明にはヒアドキュメントを使う。`--description -`を渡すとエディタが開く。
- **イシューを読む**: `glab issue view <number> --comments`。機械可読な出力には`-F json`を使う。
- **イシューを一覧する**: 適切な`--label`フィルタとともに`glab issue list -F json`。
- **イシューにコメントする**: `glab issue note <number> --message "..."`。GitLabではコメントを「ノート」と呼ぶ。
- **ラベルの付与・削除**: `glab issue update <number> --label "..."` / `--unlabel "..."`。複数のラベルはカンマ区切りにするか、フラグを繰り返す。
- **クローズする**: `glab issue close <number>`。`glab issue close`はクローズ時のコメントを受け付けないので、先に`glab issue note <number> --message "..."`で説明を投稿してからクローズする。
- **マージリクエスト**: GitLabではPRを「マージリクエスト」と呼ぶ。`glab mr create`、`glab mr view`、`glab mr note`などを使う。形は`gh pr ...`と同じで、`pr`の代わりに`mr`、`comment`/`--body`の代わりに`note`/`--message`を使う。

リポジトリは`git remote -v`から推測する。クローンの中で実行すれば`glab`が自動的にこれを行う。

## トリアージ窓口としてのマージリクエスト

**リクエスト窓口としてのMR: いいえ。**_(このリポジトリが外部からのマージリクエストを機能リクエストとして扱う場合は`yes`に設定する。`/triage`がこのフラグを読む。)_

`yes`に設定すると、MRはイシューと同じラベルと状態を通り、`glab mr`の等価コマンドを使う。

- **MRを読む**: `glab mr view <number> --comments`、差分には`glab mr diff <number>`。
- **トリアージ対象の外部MRを一覧する**: `glab mr list -F json`、その後、作者がプロジェクトメンバー/オーナーでないMRのみを残す(コントリビューターのMRであって、メンテナー自身の進行中の作業ではないもの)。
- **コメント/ラベル付け/クローズ**: `glab mr note`、`glab mr update --label`/`--unlabel`、`glab mr close`。

GitHubと異なり、GitLabはイシューとMRの番号空間を別々に持つので、メンテナーがどちらの窓口を指しているか分かれば`#42`は曖昧にならない。

## スキルが「イシュートラッカーに公開する」と言っている場合

GitLabイシューを作成する。

## スキルが「関連チケットを取得する」と言っている場合

`glab issue view <number> --comments`を実行する。

## Wayfindingの操作

`/wayfinder`が使う。**マップ**はチケットとしての**子**イシューを持つ単一のイシューである。

- **マップ**: `wayfinder:map`ラベルが付いた単一のイシューで、Notes / Decisions-so-far / Fogの本文を保持する。`glab issue create --label wayfinder:map`。(ネイティブのエピック機能があるGitLabのティアでは、エピックがマップを保持してもよい。ラベル付きイシューはどのティアでも動作する。)
- **子チケット**: 説明の先頭に`Part of #<map>`を持ち、`wayfinder:<type>`(`research`/`prototype`/`grilling`/`task`)ラベルを持つイシュー。クレームされると、そのチケットは担当開発者にアサインされる。
- **ブロッキング**: GitLabの**ネイティブブロッキングリンク**が、標準的でUI上に表示される表現である。`/blocked_by #<n>`クイックアクションで追加し、ノートとして投稿する(`glab issue note <child> --message "/blocked_by #<blocker>"`)。ネイティブブロッキングリンクはPremium/Ultimate機能である。無料ティア(または利用できない場合)では、説明の先頭に`Blocked by: #<n>, #<n>`という行を書くフォールバックを使う。すべてのブロッカーがクローズされるとチケットのブロックは解除される。
- **フロンティアクエリ**: マップの子に絞った`glab issue list -F json`で、オープンなブロッカーを持つもの(オープンなイシューへのネイティブな`blocked_by`リンク、`glab api projects/:id/issues/:iid/links`)、または`Blocked by`行にオープンなイシューがあるもの、あるいはアサイニーがいるものを除外する。マップ順で最初のものが勝つ。
- **クレーム**: `glab issue update <n> --assignee @me`、セッションの最初の書き込み。
- **解決**: `glab issue note <n> --message "<answer>"`、続けて`glab issue close <n>`、それからマップのDecisions-so-farにコンテキストポインタ(gistとリンク)を追記する。
