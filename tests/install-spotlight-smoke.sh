#!/usr/bin/env bash
# Smoke test: run install-spotlight.sh --headless --dry-run against four
# fixture configs covering the cartesian product the installer must support.
# Assertions check that each combo prints the right key install actions
# without touching the filesystem or running brew/npm/curl.
#
# The headless path reads pre-exported env vars directly (the retired
# SPOTLIGHT_CONFIG base64 blob is a contract-checked hard error below), so
# each combo is passed as KEY=VAL pairs through env(1). SPOTLIGHT_DIR is
# pinned to a sandbox dir because the installer cd's there even in dry-run,
# and because expand_path's ${input#~/} does not strip ~/ on bash 3.2
# (pre-existing body behavior, deliberately characterized, not fixed).
#
# Usage: bash tests/install-spotlight-smoke.sh

set -euo pipefail

cd "$(dirname "$0")/.."
INSTALLER="$(pwd)/install-spotlight.sh"
[ -f "$INSTALLER" ] || { echo "install-spotlight.sh not found at $INSTALLER" >&2; exit 1; }

SANDBOX="$(mktemp -d -t spotlight-install-smoke.XXXXXX)"
trap 'rm -rf "$SANDBOX"' EXIT
SANDBOX_DIR="$SANDBOX/spotlight-test"
mkdir -p "$SANDBOX_DIR"

PASS=0
FAIL=0

# Every combo must print the headless notice and open the configurator's
# getting-started guide (dry-run prints the action instead).
COMMON_ASSERTIONS=(
  "→ Headless install: reading configuration from pre-exported environment variables."
  "DRY-RUN: open $HOME/.config/spotlight/getting-started.html"
)

check_combo() {
  local label="$1"; shift
  local out
  if ! out=$(env -u SPOTLIGHT_INGEST_TARGET -u SPOTLIGHT_SOVEREIGNTY_INHERITS_MYCROFT \
                 -u SPOTLIGHT_VAULT_PATH -u OSINT_NAV_API_KEY \
                 SPOTLIGHT_DIR="$SANDBOX_DIR" "$@" \
                 bash "$INSTALLER" --headless --dry-run 2>&1); then
    echo "✗ $label  installer exited non-zero"
    echo "$out" | tail -10 | sed 's/^/    /'
    FAIL=$((FAIL + 1))
    return
  fi
  # Run the per-combo assertions passed via global ASSERTIONS array.
  local missing=()
  for needle in "${COMMON_ASSERTIONS[@]}" "${ASSERTIONS[@]}"; do
    if ! printf '%s' "$out" | grep -qF "$needle"; then
      missing+=("$needle")
    fi
  done
  if [ ${#missing[@]} -ne 0 ]; then
    echo "✗ $label  missing expected output:"
    for m in "${missing[@]}"; do echo "    - $m"; done
    FAIL=$((FAIL + 1))
  else
    echo "✓ $label  $(( ${#ASSERTIONS[@]} + ${#COMMON_ASSERTIONS[@]} )) assertions matched"
    PASS=$((PASS + 1))
  fi
}

# Common base config — every combo needs these vars.
BASE=(
  SPOTLIGHT_DIR_INPUT='~/Code/spotlight-test'
  SPOTLIGHT_VAULT_INPUT='~/Vaults/spotlight-test'
  SPOTLIGHT_VAULT_APP='obsidian'
  SPOTLIGHT_INT_DEVBROWSER='false'
  SPOTLIGHT_INT_JUNKIPEDIA='false'
  SPOTLIGHT_INT_UNPAYWALL='false'
  FIRECRAWL_API_KEY='fc-test'
  OSINT_NAV_API_KEY='nav-test'
)

# --- 1. cloud / claude ---
ASSERTIONS=(
  "━━ Prerequisites ━━"
  "━━ Claude Code ━━"
  "AGENTS.md linked as CLAUDE.md"
  "DRY-RUN: write .env"
  "DRY-RUN: write spotlight-doctor"
  "Spotlight installed"
)
check_combo "cloud/claude" "${BASE[@]}" \
  SPOTLIGHT_MODE=cloud SPOTLIGHT_RUNTIME=claude

# --- 2. cloud / opencode-openrouter ---
ASSERTIONS=(
  "━━ OpenCode (provider: openrouter) ━━"
  "DRY-RUN: symlink"
  ".config/opencode/skills/"
  "DRY-RUN: write .env"
  "Spotlight installed"
)
check_combo "cloud/opencode-openrouter" "${BASE[@]}" \
  SPOTLIGHT_MODE=cloud SPOTLIGHT_RUNTIME=opencode \
  SPOTLIGHT_OPENCODE_PROVIDER=openrouter \
  SPOTLIGHT_CLOUD_KEY_VAR=OPENROUTER_API_KEY \
  SPOTLIGHT_CLOUD_KEY=sk-or-test

# --- 3. local / llamacpp / opencode ---
ASSERTIONS=(
  "━━ Local inference (llama-server) ━━"
  "━━ Agent harness (opencode CLI) ━━"
  "DRY-RUN: merge llamacpp provider into"
  "127.0.0.1:8080/v1"
  "DRY-RUN: write ~/.local/bin/spotlight-local for llamacpp/opencode"
  "Spotlight installed"
)
check_combo "local/llamacpp/opencode" "${BASE[@]}" \
  SPOTLIGHT_MODE=local SPOTLIGHT_RUNTIME=local \
  SPOTLIGHT_LOCAL_SERVER=llamacpp SPOTLIGHT_LOCAL_MODEL=qwen27b \
  SPOTLIGHT_AGENT=opencode SPOTLIGHT_OPENCODE_INTERFACE=cli \
  SPOTLIGHT_MODEL_REPO='tomvaillant/qwen3.6-27b-abliterated-journalist-GGUF'

# --- 4. local / llamacpp / pi ---
# The Pi branch prompts interactively (read -r ans </dev/tty), so we feed "y"
# on stdin via process substitution to confirm proceeding past the warning.
# But under --dry-run the prompt is skipped. Verify the warning still prints.
ASSERTIONS=(
  "━━ Local inference (llama-server) ━━"
  "Pi has no native sub-agents."
  "weakening the verification independence guarantee"
  "━━ Agent harness (Pi) ━━"
  "DRY-RUN: write"
  "spotlight-local for llamacpp/pi"
  "Spotlight installed"
)
check_combo "local/llamacpp/pi" "${BASE[@]}" \
  SPOTLIGHT_MODE=local SPOTLIGHT_RUNTIME=local \
  SPOTLIGHT_LOCAL_SERVER=llamacpp SPOTLIGHT_LOCAL_MODEL=qwen9b \
  SPOTLIGHT_AGENT=pi SPOTLIGHT_OPENCODE_INTERFACE=cli \
  SPOTLIGHT_MODEL_REPO='tomvaillant/qwen3.5-9b-abliterated-journalist-GGUF'

# --- Contract: retired SPOTLIGHT_CONFIG channel fails loud ---
out=$(SPOTLIGHT_CONFIG=x bash "$INSTALLER" --dry-run 2>&1) && rc=0 || rc=$?
if [ "$rc" -eq 1 ] && printf '%s' "$out" | grep -qF "no longer accepts SPOTLIGHT_CONFIG"; then
  echo "✓ SPOTLIGHT_CONFIG retirement  exit 1 + retirement message"
  PASS=$((PASS + 1))
else
  echo "✗ SPOTLIGHT_CONFIG retirement  expected exit 1 + retirement message (rc=$rc)"
  echo "$out" | tail -5 | sed 's/^/    /'
  FAIL=$((FAIL + 1))
fi

# --- Contract: headless run without FIRECRAWL_API_KEY hits the :? guard ---
NOKEY=()
for kv in "${BASE[@]}"; do
  case "$kv" in FIRECRAWL_API_KEY=*) ;; *) NOKEY+=("$kv") ;; esac
done
out=$(env -u SPOTLIGHT_INGEST_TARGET -u SPOTLIGHT_SOVEREIGNTY_INHERITS_MYCROFT \
          -u SPOTLIGHT_VAULT_PATH -u OSINT_NAV_API_KEY -u FIRECRAWL_API_KEY \
          SPOTLIGHT_DIR="$SANDBOX_DIR" "${NOKEY[@]}" \
          SPOTLIGHT_MODE=cloud SPOTLIGHT_RUNTIME=claude \
          bash "$INSTALLER" --headless --dry-run 2>&1) && rc=0 || rc=$?
if [ "$rc" -ne 0 ] && printf '%s' "$out" | grep -qF "FIRECRAWL_API_KEY"; then
  echo "✓ headless missing-key guard  :? failure names FIRECRAWL_API_KEY"
  PASS=$((PASS + 1))
else
  echo "✗ headless missing-key guard  expected non-zero exit naming FIRECRAWL_API_KEY (rc=$rc)"
  echo "$out" | tail -5 | sed 's/^/    /'
  FAIL=$((FAIL + 1))
fi

echo ""
echo "$PASS passed, $FAIL failed"
exit "$FAIL"
