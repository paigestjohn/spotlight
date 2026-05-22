#!/usr/bin/env bash
# Spotlight patch for low-RAM Macs (≤16 GB).
#
# The default spotlight install pulls a 17 GB MoE (gemma-4-26B-A4B Q4_K_M)
# that won't load on machines with 16 GB or less. This script swaps the
# spotlight-gemma4-q4 alias to point at the 8B dense journalist model
# (~5.3 GB) so opencode.json keeps working without edits.
#
# Usage:
#   bash patch-spotlight-low-ram.sh           # patch + verify
#   bash patch-spotlight-low-ram.sh --purge   # also remove the old 17 GB blob

set -euo pipefail

SMALL_MODEL="hf.co/tomvaillant/gemma4-e4b-abliterated-journalist-GGUF:Q4_K_M"
OLD_MODEL="hf.co/unsloth/gemma-4-26B-A4B-it-GGUF:UD-Q4_K_M"
ALIAS="spotlight-gemma4-q4"
PURGE=0
[ "${1:-}" = "--purge" ] && PURGE=1

c_green=$'\033[32m'; c_red=$'\033[31m'; c_dim=$'\033[2m'; c_reset=$'\033[0m'
step() { printf '\n→ %s\n' "$1"; }
ok()   { printf '%s✓%s %s\n' "$c_green" "$c_reset" "$1"; }
die()  { printf '%s✗%s %s\n' "$c_red" "$c_reset" "$1" >&2; exit 1; }

command -v ollama >/dev/null || die "ollama not found on PATH"

# Sanity: is the daemon up?
if ! curl -sf http://127.0.0.1:11434/api/tags >/dev/null; then
  die "Ollama daemon not reachable at 127.0.0.1:11434 — start the Ollama app first."
fi

step "Pulling $SMALL_MODEL (~5.3 GB)…"
ollama pull "$SMALL_MODEL"
ok "blob present"

step "Re-pointing alias '$ALIAS' at the smaller model…"
TMP_MODELFILE=$(mktemp)
trap 'rm -f "$TMP_MODELFILE"' EXIT
printf 'FROM %s\n' "$SMALL_MODEL" > "$TMP_MODELFILE"
ollama create "$ALIAS" -f "$TMP_MODELFILE"
ok "alias '$ALIAS' now resolves to $SMALL_MODEL"

step "Smoke-test load (one short generation)…"
# `ollama run` with stdin emits a token stream; we only care that loading
# succeeds without the 500/unable-to-load error.
if ! printf 'ping\n' | ollama run "$ALIAS" >/dev/null 2>&1; then
  die "Model loaded but generation failed — check 'ollama logs' (~/.ollama/logs/server.log)"
fi
ok "model loads and generates"

if [ "$PURGE" -eq 1 ]; then
  step "Removing oversized $OLD_MODEL (~17 GB)…"
  if ollama show "$OLD_MODEL" >/dev/null 2>&1; then
    ollama rm "$OLD_MODEL"
    ok "old MoE removed; disk reclaimed"
  else
    printf '%s(already gone)%s\n' "$c_dim" "$c_reset"
  fi
else
  printf '\n%sTip:%s the old 17 GB MoE is still on disk. To reclaim space:\n' "$c_dim" "$c_reset"
  printf "     ollama rm '%s'\n" "$OLD_MODEL"
  printf '     (or re-run this script with --purge)\n'
fi

cat <<EOF

${c_green}Done.${c_reset} Spotlight should now work without changes to opencode.json.

Quick sanity check end-to-end:
  opencode  # then ask anything that triggers spotlight; logs should show
            # POST /v1/chat/completions → 200, not 500.

EOF
