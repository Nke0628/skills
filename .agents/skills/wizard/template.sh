#!/usr/bin/env bash
#
# ウィザードは、人間を手順に沿って一歩ずつ導く。
# /wizard スキルによって生成された。
#
# "STAGES" マーカーより上の部分はウィザードライブラリであり、手で編集しては
# ならない。マーカーより下に、各ステップのステージを記述すること。

set -euo pipefail

# ──────────────────────────────────────────────────────────────────────────
# ウィザードライブラリ: あらゆるウィザードで共通の、快適で一貫したUX。
# ──────────────────────────────────────────────────────────────────────────

if [[ -t 1 ]] && command -v tput >/dev/null 2>&1 && [[ "$(tput colors 2>/dev/null || echo 0)" -ge 8 ]]; then
  BOLD=$(tput bold); DIM=$(tput dim); RESET=$(tput sgr0)
  BLUE=$(tput setaf 4); GREEN=$(tput setaf 2); YELLOW=$(tput setaf 3); RED=$(tput setaf 1)
else
  BOLD=""; DIM=""; RESET=""; BLUE=""; GREEN=""; YELLOW=""; RED=""
fi

# 作者がステージセクションの先頭でこれを設定する。
TOTAL_STAGES=0

_STAGE_INDEX=0
ENV_FILE="${ENV_FILE:-.env}"
WRITTEN_ENV=()    # 今回のセッションで ENV_FILE に書き込んだ KEY
WRITTEN_SECRET=() # 今回のセッションで設定した secret の NAME
SKIPPED=()        # 実行できなかった項目（例: gh が見つからない）

# _clear は現在のステップだけが画面に残るよう、端末をクリアする。出力が端末
# でない場合は何もしないため、パイプされたログは読みやすいまま保たれる。
_clear() {
  [[ -t 1 ]] || return 0
  if command -v tput >/dev/null 2>&1; then tput clear; else printf '\033[2J\033[3J\033[H'; fi
}

# banner "Title" は冒頭のフレーム、つまりこのウィザードが何をするかを表示する。
banner() {
  _clear
  printf '\n%s%s  %s%s\n' "$BOLD" "$BLUE" "$1" "$RESET"
  printf '%s  %s ステージ%s\n\n' "$DIM" "$TOTAL_STAGES" "$RESET"
  printf '%s  ブラウザの操作はあなたが行う。このウィザードは何をすべきかを正確に指示し、\n' "$DIM"
  printf '  コピーして貼り付けた値を記録する。Ctrl-C でいつでも中断でき、保存済みの値を\n'
  printf '  記憶しているので後で再実行できる。%s\n' "$RESET"
  pause "準備はいいか？"
}

# stage "Name" は画面をクリアしてからステージを告知し、進捗を表示する。
# クリアすることで、現在のステップだけが画面に残る。
stage() {
  _clear
  _STAGE_INDEX=$((_STAGE_INDEX + 1))
  printf '\n%s%s▸ ステージ %s/%s · %s%s\n' \
    "$BOLD" "$BLUE" "$_STAGE_INDEX" "$TOTAL_STAGES" "$1" "$RESET"
}

# say "..." はプレーンな指示行を出力する。
say()  { printf '  %s\n' "$1"; }
# step "..." は、人間がブラウザ上で行う番号付きっぽいアクション。
step() { printf '  %s•%s %s\n' "$BLUE" "$RESET" "$1"; }
note() { printf '  %s%s%s\n' "$DIM" "$1" "$RESET"; }
warn() { printf '  %s⚠ %s%s\n' "$YELLOW" "$1" "$RESET"; }

# open_url URL は、人間のブラウザでURLを開く。WSLを含めクロスプラットフォーム対応。
open_url() {
  local url="$1"
  printf '  %s↗ 開いています%s %s\n' "$GREEN" "$RESET" "$url"
  { if   command -v wslview     >/dev/null 2>&1; then wslview "$url"
    elif command -v explorer.exe >/dev/null 2>&1; then explorer.exe "$url"
    elif command -v xdg-open    >/dev/null 2>&1; then xdg-open "$url"
    elif command -v open        >/dev/null 2>&1; then open "$url"
    else warn "ブラウザを開けなかった。手動でアクセスすること: $url"; fi
  } >/dev/null 2>&1 || warn "ブラウザを開けなかったため、手動でアクセスすること: $url"
}

# pause "msg" は、人間が手動の作業を終えたことを確認するまで待つ。
pause() {
  printf '  %s%s%s ' "$DIM" "${1:-続けるには Enter を押す}" "$RESET"
  read -r _ || true
}

# confirm "question" は y/N のゲートであり、yes の場合に成功を返す。
confirm() {
  local reply=""
  printf '  %s? %s [y/N] ' "$YELLOW" "$1"
  read -r reply || true
  [[ "$reply" =~ ^[Yy] ]]
}

# _existing KEY: ENV_FILE 内にある KEY の現在値（存在する場合）。
_existing() {
  [[ -f "$ENV_FILE" ]] || return 1
  local line; line=$(grep -E "^${1}=" "$ENV_FILE" | tail -n1) || return 1
  printf '%s' "${line#*=}"
}

# ask KEY "Prompt" は値を読み取って $KEY に格納する。再実行時には既存の .env
# の値をデフォルトとして提示する（Enter でそのまま維持）。非シークレットの
# 可視入力。
ask() {
  local key="$1" prompt="$2" current input
  current=$(_existing "$key" || true)
  if [[ -n "$current" ]]; then
    printf '  %s%s%s %s[Enter で現在値を維持]%s ' "$BOLD" "$prompt" "$RESET" "$DIM" "$RESET"
  else
    printf '  %s%s%s ' "$BOLD" "$prompt" "$RESET"
  fi
  read -r input || true
  [[ -z "$input" && -n "$current" ]] && input="$current"
  printf -v "$key" '%s' "$input"
}

# ask_secret KEY "Prompt" は ask と同様だが、入力が非表示になる。
ask_secret() {
  local key="$1" prompt="$2" current input
  current=$(_existing "$key" || true)
  if [[ -n "$current" ]]; then
    printf '  %s%s%s %s[Enter で現在値を維持]%s ' "$BOLD" "$prompt" "$RESET" "$DIM" "$RESET"
  else
    printf '  %s%s%s ' "$BOLD" "$prompt" "$RESET"
  fi
  read -rs input || true
  printf '\n'
  [[ -z "$input" && -n "$current" ]] && input="$current"
  printf -v "$key" '%s' "$input"
}

# write_env KEY VALUE は KEY=VALUE を ENV_FILE に upsert する（ファイルを
# 作成し、既存の行があれば置き換える）。冪等。
write_env() {
  local key="$1" value="$2" tmp
  touch "$ENV_FILE"
  tmp=$(mktemp)
  grep -vE "^${key}=" "$ENV_FILE" > "$tmp" || true
  printf '%s=%s\n' "$key" "$value" >> "$tmp"
  mv "$tmp" "$ENV_FILE"
  WRITTEN_ENV+=("$key")
  printf '  %s✓ 書き込み完了%s %s → %s\n' "$GREEN" "$RESET" "$key" "$ENV_FILE"
}

# set_secret NAME VALUE は gh 経由で GitHub Actions のリポジトリシークレット
# を設定する。gh が利用できない、または未認証の場合は警告にフォールバック
# する（その旨を記録する）。
set_secret() {
  local name="$1" value="$2"
  if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    if printf '%s' "$value" | gh secret set "$name" >/dev/null 2>&1; then
      WRITTEN_SECRET+=("$name")
      printf '  %s✓ 設定完了%s GitHub secret %s\n' "$GREEN" "$RESET" "$name"
      return
    fi
  fi
  SKIPPED+=("GitHub secret $name（手動で設定: gh secret set $name）")
  warn "GitHub secret $name をスキップした: gh の準備ができていない。後で設定すること"
}

# set_var NAME VALUE は GitHub Actions のリポジトリ変数（非シークレット）を設定する。
set_var() {
  local name="$1" value="$2"
  if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    if gh variable set "$name" --body "$value" >/dev/null 2>&1; then
      printf '  %s✓ 設定完了%s GitHub variable %s\n' "$GREEN" "$RESET" "$name"
      return
    fi
  fi
  SKIPPED+=("GitHub variable $name")
  warn "GitHub variable $name をスキップした。gh の準備ができていない。後で設定すること"
}

# finish は画面をクリアしてから、設定した内容すべての締めくくりのサマリーを表示する。
finish() {
  _clear
  printf '\n%s%s  ✓ セットアップ完了%s\n' "$BOLD" "$GREEN" "$RESET"
  (( ${#WRITTEN_ENV[@]} ))    && note "${#WRITTEN_ENV[@]} 個の値を $ENV_FILE に書き込んだ: ${WRITTEN_ENV[*]}"
  (( ${#WRITTEN_SECRET[@]} )) && note "${#WRITTEN_SECRET[@]} 個の GitHub secret を設定した: ${WRITTEN_SECRET[*]}"
  if (( ${#SKIPPED[@]} )); then
    printf '\n'; warn "手動での残作業:"
    for s in "${SKIPPED[@]}"; do note "  - $s"; done
  fi
  printf '\n'
}

# ──────────────────────────────────────────────────────────────────────────
# STAGES: このセクションを作成する。人間が行う各ステップにつき stage() を
# 1つ。以下の例を置き換えること。記述したステージ数に合わせて TOTAL_STAGES
# を設定する。
# ──────────────────────────────────────────────────────────────────────────

TOTAL_STAGES=1

banner "Stripeのセットアップ"

# ── サンプルステージ: 実際のステップに置き換えること ──────────────────────
stage "Stripe: APIキー"
say "Stripe のテストキーを取得し、ローカル開発用と CI 用に保存する。"
open_url "https://dashboard.stripe.com/test/apikeys"
step "API keys ページで、Publishable key（pk_test_ で始まる）をコピーする。"
ask STRIPE_PUBLISHABLE_KEY "publishable key を貼り付け:"
step "Secret key の行にある「Reveal test key」をクリックし、それをコピーする。"
ask_secret STRIPE_SECRET_KEY "secret key を貼り付け:"
write_env STRIPE_PUBLISHABLE_KEY "$STRIPE_PUBLISHABLE_KEY"
write_env STRIPE_SECRET_KEY "$STRIPE_SECRET_KEY"
set_secret STRIPE_SECRET_KEY "$STRIPE_SECRET_KEY"   # CI にはこれが必要
# ──────────────────────────────────────────────────────────────────────────

finish
