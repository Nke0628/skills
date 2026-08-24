# Issue tracker: GitHub

このリポジトリのイシューとスペックはGitHubイシューとして存在する。すべての操作に`gh` CLIを使う。

## 慣習

- **イシューを作成する**: `gh issue create --title "..." --body "..."`。複数行の本文にはヒアドキュメントを使う。
- **イシューを読む**: `gh issue view <number> --comments`。`jq`でコメントをフィルタし、ラベルも取得する。
- **イシューを一覧する**: 適切な`--label`と`--state`フィルタとともに`gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'`。
- **イシューにコメントする**: `gh issue comment <number> --body "..."`
- **ラベルの付与・削除**: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **クローズする**: `gh issue close <number> --comment "..."`

リポジトリは`git remote -v`から推測する。クローンの中で実行すれば`gh`が自動的にこれを行う。

## トリアージ窓口としてのプルリクエスト

**リクエスト窓口としてのPR: いいえ。**_(このリポジトリが外部からのPRを機能リクエストとして扱う場合は`yes`に設定する。`/triage`がこのフラグを読む。)_

`yes`に設定すると、PRはイシューと同じラベルと状態を通り、`gh pr`の等価コマンドを使う。

- **PRを読む**: `gh pr view <number> --comments`、差分には`gh pr diff <number>`。
- **トリアージ対象の外部PRを一覧する**: `gh pr list --state open --json number,title,body,labels,author,authorAssociation,comments`、その後`authorAssociation`が`CONTRIBUTOR`、`FIRST_TIME_CONTRIBUTOR`、`NONE`のものだけを残す(`OWNER`/`MEMBER`/`COLLABORATOR`は除外)。
- **コメント/ラベル付け/クローズ**: `gh pr comment`、`gh pr edit --add-label`/`--remove-label`、`gh pr close`。

GitHubはイシューとPRで1つの番号空間を共有するので、単なる`#42`はどちらかを指す可能性がある。`gh pr view 42`で解決を試み、だめなら`gh issue view 42`にフォールバックする。

## スキルが「イシュートラッカーに公開する」と言っている場合

GitHubイシューを作成する。

## スキルが「関連チケットを取得する」と言っている場合

`gh issue view <number> --comments`を実行する。

## Wayfindingの操作

`/wayfinder`が使う。**マップ**はチケットとしての**子**イシューを持つ単一のイシューである。

- **マップ**: `wayfinder:map`ラベルが付いた単一のイシューで、Notes / Decisions-so-far / Fogの本文を保持する。`gh issue create --label wayfinder:map`。
- **子チケット**: GitHubのサブイシューとしてマップにリンクされたイシュー(サブイシューエンドポイントへの`gh api`)。サブイシューが有効でない場合は、マップ本文のタスクリストに子を追加し、子の本文の先頭に`Part of #<map>`を置く。ラベル: `wayfinder:<type>`(`research`/`prototype`/`grilling`/`task`)。クレームされると、そのチケットは担当開発者にアサインされる。
- **ブロッキング**: GitHubの**ネイティブなイシュー依存関係**が、標準的でUI上に表示される表現である。`gh api --method POST repos/<owner>/<repo>/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>`でエッジを追加する。ここで`<blocker-db-id>`はブロッカーの数値の**データベースID**であり(`gh api repos/<owner>/<repo>/issues/<n> --jq .id`、`#number`や`node_id`ではない)、GitHubは`issue_dependencies_summary.blocked_by`(オープンなブロッカーのみ、生きたゲート)を報告する。依存関係機能が利用できない場合は、子の本文の先頭に`Blocked by: #<n>, #<n>`という行を書くフォールバックを使う。すべてのブロッカーがクローズされるとチケットのブロックは解除される。
- **フロンティアクエリ**: マップのオープンな子を一覧し(マップのサブイシュー/タスクリストに絞った`gh issue list --state open`)、オープンなブロッカーを持つもの(`issue_dependencies_summary.blocked_by > 0`、または`Blocked by`行にオープンなイシュー)、あるいはアサイニーがいるものを除外する。マップ順で最初のものが勝つ。
- **クレーム**: `gh issue edit <n> --add-assignee @me`、セッションの最初の書き込み。
- **解決**: `gh issue comment <n> --body "<answer>"`、続けて`gh issue close <n>`、それからマップのDecisions-so-farにコンテキストポインタ(gistとリンク)を追記する。
