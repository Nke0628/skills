---
name: git-guardrails-claude-code
description: 危険なgitコマンド(push、reset --hard、clean、branch -Dなど)が実行される前にブロックするClaude Codeフックをセットアップする。破壊的なgit操作を防ぎたい、gitの安全フックを追加したい、Claude Codeでgit push/resetをブロックしたいときに使用する。
---

# Gitガードレールのセットアップ

Claudeが危険なgitコマンドを実行する前にそれを捕捉してブロックする、PreToolUseフックをセットアップする。

## ブロックされるもの

- `git push`(`--force`を含む全バリエーション)
- `git reset --hard`
- `git clean -f` / `git clean -fd`
- `git branch -D`
- `git checkout .` / `git restore .`

ブロックされると、Claudeにはこれらのコマンドを実行する権限がないことを伝えるメッセージが表示される。

## 手順

### 1. 適用範囲を確認する

ユーザーに尋ねる: **このプロジェクトのみ**(`.claude/settings.json`)にインストールするか、**全プロジェクト**(`~/.claude/settings.json`)にインストールするか?

### 2. フックスクリプトをコピーする

同梱されているスクリプトの場所: [scripts/block-dangerous-git.sh](scripts/block-dangerous-git.sh)

適用範囲に応じて、以下の場所にコピーする:

- **プロジェクト**: `.claude/hooks/block-dangerous-git.sh`
- **グローバル**: `~/.claude/hooks/block-dangerous-git.sh`

`chmod +x`で実行可能にする。

### 3. 設定にフックを追加する

適切な設定ファイルに追加する:

**プロジェクト**(`.claude/settings.json`):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/block-dangerous-git.sh"
          }
        ]
      }
    ]
  }
}
```

**グローバル**(`~/.claude/settings.json`):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/block-dangerous-git.sh"
          }
        ]
      }
    ]
  }
}
```

設定ファイルが既に存在する場合は、既存の`hooks.PreToolUse`配列にフックをマージする。他の設定を上書きしないこと。

### 4. カスタマイズについて確認する

ブロックリストにパターンを追加・削除したいかユーザーに確認する。それに応じてコピーしたスクリプトを編集する。

### 5. 検証する

簡単なテストを実行する:

```bash
echo '{"tool_input":{"command":"git push origin main"}}' | <path-to-script>
```

終了コード2で終了し、stderrにBLOCKEDメッセージが出力されるはずだ。
