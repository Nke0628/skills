#!/usr/bin/env bash
# 人間参加型(HITL)の再現ループ。
# このファイルをコピーし、下のステップを編集して実行する。
# エージェントがこのスクリプトを実行し、ユーザーは自分の端末でプロンプトに従う。
#
# 使い方:
#   bash hitl-loop.template.sh
#
# 2つのヘルパー:
#   step "<instruction>"          → 指示を表示し、Enterキーを待つ
#   capture VAR "<question>"      → 質問を表示し、回答をVARに読み込む
#
# 最後に、取得した値がエージェントが解析できるようKEY=VALUE形式で出力される。
#
# `capture`はその値を端末に出力し、それをエージェントが読み取る。
# だから観測結果は`capture`で取得し、サインインのような操作は`step`に任せる。

set -euo pipefail

step() {
  printf '\n>>> %s\n' "$1"
  read -r -p "    [Enter when done] " _
}

capture() {
  local var="$1" question="$2" answer
  printf '\n>>> %s\n' "$question"
  read -r -p "    > " answer
  printf -v "$var" '%s' "$answer"
}

# --- ここから下を編集する ---------------------------------------------------------

step "http://localhost:3000 でアプリを開き、サインインする。"

capture ERRORED "「Export」ボタンをクリックする。エラーは出たか?(y/n)"

capture ERROR_MSG "エラーメッセージを貼り付けてください(なければ'none'):"

# --- ここまでを編集する ---------------------------------------------------------

printf '\n--- Captured ---\n'
printf 'ERRORED=%s\n' "$ERRORED"
printf 'ERROR_MSG=%s\n' "$ERROR_MSG"
