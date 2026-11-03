#!/bin/sh
# Install the demo-video skill for Claude Code, Codex and/or OpenCode.
#
#   ./install.sh                 # every agent found on this machine
#   ./install.sh claude codex    # only these (claude | codex | opencode)
#   ./install.sh --link ...      # symlink instead of copying (follows `git pull`)
#
# Where each agent looks for user skills:
#   Claude Code  ~/.claude/skills/
#   Codex        ~/.agents/skills/
#   OpenCode     ~/.config/opencode/skills/, and also ~/.claude/skills/ and ~/.agents/skills/
set -eu

SRC="$(cd "$(dirname "$0")" && pwd)/demo-video"
MODE=copy
AGENTS=""
for arg in "$@"; do
  case "$arg" in
    --link) MODE=link ;;
    claude|codex|opencode) AGENTS="$AGENTS $arg" ;;
    -h|--help) sed -n '2,11p' "$0"; exit 0 ;;
    *) echo "unknown argument: $arg (try --help)" >&2; exit 2 ;;
  esac
done

if [ -z "$AGENTS" ]; then
  command -v claude   >/dev/null 2>&1 || [ -d "$HOME/.claude" ]          && AGENTS="$AGENTS claude"
  command -v codex    >/dev/null 2>&1 || [ -d "$HOME/.codex" ]           && AGENTS="$AGENTS codex"
  command -v opencode >/dev/null 2>&1 || [ -d "$HOME/.config/opencode" ] && AGENTS="$AGENTS opencode"
  [ -n "$AGENTS" ] || { echo "no agent found; name one: ./install.sh claude|codex|opencode" >&2; exit 1; }
fi

install_to() {  # $1 = skills directory
  dest="$1/demo-video"
  mkdir -p "$1"
  if [ -e "$dest" ] || [ -L "$dest" ]; then
    echo "  $dest exists: leaving it (remove it first to reinstall)"
    return
  fi
  if [ "$MODE" = link ]; then ln -s "$SRC" "$dest"; else cp -R "$SRC" "$dest"; fi
  echo "  $dest ($MODE)"
}

DONE=""
for agent in $AGENTS; do
  case "$agent" in
    claude)   dir="$HOME/.claude/skills" ;;
    codex)    dir="$HOME/.agents/skills" ;;
    # OpenCode also reads ~/.claude/skills and ~/.agents/skills: reuse one of those if already installed
    opencode) case "$DONE" in *skills*) echo "opencode: uses$DONE"; continue ;; esac
              dir="$HOME/.config/opencode/skills" ;;
  esac
  echo "$agent:"
  install_to "$dir"
  DONE="$DONE $dir"
done
