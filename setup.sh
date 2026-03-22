#!/usr/bin/env bash
# setup.sh — FlipperAgent first-time setup
# Safe to run multiple times.

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

ok()   { echo -e "  ${GREEN}✓${NC} $*"; }
warn() { echo -e "  ${YELLOW}!${NC} $*"; }
fail() { echo -e "  ${RED}✗${NC} $*"; }
info() { echo -e "  ${CYAN}→${NC} $*"; }

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MCP_DIR="$REPO_DIR/flipperzero-mcp"
VENV_DIR="$MCP_DIR/.venv"

echo -e "\n${BOLD}FlipperAgent Setup${NC}"
echo "────────────────────────────────────"

# ── 1. Check brew ────────────────────────────────────────────────────────────
echo -e "\n${BOLD}System dependencies${NC}"
if command -v brew &>/dev/null; then
  ok "brew found ($(brew --version | head -1))"
  HAVE_BREW=1
else
  warn "brew not found — some optional tools may need manual install"
  HAVE_BREW=0
fi

# ── 2. Check jq ──────────────────────────────────────────────────────────────
if command -v jq &>/dev/null; then
  ok "jq found"
else
  if [[ $HAVE_BREW -eq 1 ]]; then
    info "Installing jq via brew..."
    brew install jq
    ok "jq installed"
  else
    warn "jq not found — install manually: https://stedolan.github.io/jq/"
  fi
fi

# ── 3. Check Python 3.10+ ────────────────────────────────────────────────────
PYTHON=""
for cmd in python3.12 python3.11 python3.10 python3; do
  if command -v "$cmd" &>/dev/null; then
    ver=$("$cmd" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    major=${ver%%.*}; minor=${ver##*.}
    if [[ $major -ge 3 && $minor -ge 10 ]]; then
      PYTHON="$cmd"; ok "Python $ver found ($cmd)"; break
    fi
  fi
done
if [[ -z "$PYTHON" ]]; then
  fail "Python 3.10+ required but not found"
  echo -e "     Install via: brew install python@3.12  (or pyenv, asdf, etc.)"
  exit 1
fi

# ── 4. Create venv ───────────────────────────────────────────────────────────
echo -e "\n${BOLD}Python environment${NC}"
if [[ -d "$VENV_DIR" ]]; then
  ok "venv already exists at flipperzero-mcp/.venv"
else
  info "Creating venv at flipperzero-mcp/.venv..."
  "$PYTHON" -m venv "$VENV_DIR"
  ok "venv created"
fi

# ── 5. Install MCP package ───────────────────────────────────────────────────
info "Installing flipper-mcp (editable)..."
"$VENV_DIR/bin/pip" install -q --upgrade pip
"$VENV_DIR/bin/pip" install -q -e "$MCP_DIR"
ok "flipper-mcp installed"

# ── 6. Check Flipper USB connection ─────────────────────────────────────────
echo -e "\n${BOLD}Hardware${NC}"
FLIPPER_PORT=""
# shellcheck disable=SC2206
FLIPPER_PORTS=( $(ls /dev/cu.usbmodemflip_* 2>/dev/null || true) )
if [[ ${#FLIPPER_PORTS[@]} -gt 0 ]]; then
  FLIPPER_PORT="${FLIPPER_PORTS[0]}"
  ok "Flipper Zero detected: $FLIPPER_PORT"
else
  warn "No Flipper Zero found at /dev/cu.usbmodemflip_*"
  warn "Connect via USB and re-run, or use WiFi transport"
fi

# ── 7. Summary ───────────────────────────────────────────────────────────────
echo -e "\n${BOLD}Summary${NC}"
echo "────────────────────────────────────"
[[ -n "$FLIPPER_PORT" ]] && ok "Flipper Zero USB: $FLIPPER_PORT" || warn "Flipper Zero USB: not connected"
ok "MCP server:  $VENV_DIR/bin/flipper-mcp"
ok "Python env:  $VENV_DIR"

# ── 8. Next steps ────────────────────────────────────────────────────────────
echo -e "\n${BOLD}Next steps${NC}"
echo "────────────────────────────────────"
info "Run the MCP server manually:"
echo "       $VENV_DIR/bin/flipper-mcp"
echo ""
info "Add to Claude Desktop (~/Library/Application Support/Claude/claude_desktop_config.json):"
echo '       {
         "mcpServers": {
           "flipper-zero": {
             "command": "'"$VENV_DIR/bin/python"'",
             "args": ["-m", "flipper_mcp.cli.main"],
             "env": { "FLIPPER_TRANSPORT": "usb" }
           }
         }
       }'
echo ""
info "Docs: $MCP_DIR/docs/index.md"
echo ""

# ── 9. Install 'flipper' command ──────────────────────────────────────────
echo -e "${BOLD}Shell command${NC}"
echo "────────────────────────────────────"
SHELL_RC=""
if [[ -f "$HOME/.zshrc" ]]; then
  SHELL_RC="$HOME/.zshrc"
elif [[ -f "$HOME/.bashrc" ]]; then
  SHELL_RC="$HOME/.bashrc"
elif [[ -f "$HOME/.bash_profile" ]]; then
  SHELL_RC="$HOME/.bash_profile"
fi

ALIAS_LINE="alias flipper='$REPO_DIR/flipper'"

if [[ -n "$SHELL_RC" ]] && grep -qF "alias flipper=" "$SHELL_RC" 2>/dev/null; then
  ok "'flipper' alias already in $SHELL_RC"
elif [[ -n "$SHELL_RC" ]]; then
  echo "" >> "$SHELL_RC"
  echo "# FlipperAgent" >> "$SHELL_RC"
  echo "$ALIAS_LINE" >> "$SHELL_RC"
  ok "'flipper' alias added to $SHELL_RC"
  info "Run: source $SHELL_RC  (or open a new terminal)"
else
  warn "Could not find shell rc file. Add manually:"
  echo "       $ALIAS_LINE"
fi
echo ""
