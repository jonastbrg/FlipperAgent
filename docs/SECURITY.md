# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| Latest `main` branch | Yes |
| Older commits / tags | Best effort |

FlipperAgent does not use semantic versioning yet. The `main` branch is the only officially supported version. Security fixes will be applied to `main` and announced in release notes.

## Reporting a Vulnerability

If you discover a security vulnerability in FlipperAgent, **report it responsibly**.

### Do NOT

- Open a public GitHub issue for security vulnerabilities
- Post vulnerability details on social media or forums before a fix is available
- Include exploit code in public discussions

### Do

1. **Report via GitHub Security Advisories**: Use the repository's [private vulnerability reporting](../../security/advisories/new) to submit a detailed report.

2. **Include in your report**:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact (what an attacker could do)
   - Affected component (MCP server, CLI bridge, transport, specific module)
   - Suggested fix, if you have one

3. **Allow time**: Give maintainers 90 days to investigate and release a fix before public disclosure.

We will acknowledge receipt within 48 hours and provide a timeline for the fix.

## Security Architecture

FlipperAgent is a security tool that controls physical attack hardware. The security architecture is designed to prevent the AI agent from taking unauthorized or unintended actions.

### Risk Classification

Every MCP tool call is classified before execution:

| Level | Count | Behavior | Examples |
|-------|-------|----------|---------|
| **LOW** | 27 | Execute immediately | `ble_scan`, `subghz_rx`, `storage_list`, `audit_query` |
| **MEDIUM** | 16 | Execute with logging | `ir_tx`, `gpio_set`, `ble_enumerate`, `storage_write` |
| **HIGH** | 8 | Execute with safety-gate warning | `subghz_tx`, `ble_write_char`, `badusb_execute`, `rfid_write` |
| **BLOCKED** | n/a | Reject automatically | Protected file paths (`/int/`, `.key`, `.priv`, `.secret`) |

Classification is a static lookup in `core/risk.py` -- less than 1ms latency, no runtime bypass.

### Audit Logging

Two independent audit systems capture every tool call:

1. **Server-side** (`core/audit.py`): In-memory ring buffer (1000 entries) plus optional JSONL file (`FLIPPER_AUDIT_LOG`). Records tool name, sanitized arguments, risk level, result summary, duration, and success/failure.

2. **Plugin-side** (`engagement-logger.ts`): Appends to `findings/tool_calls.jsonl` at the OpenCode plugin layer. Captures calls even if the MCP server process crashes.

Both systems sanitize logged data: arguments containing `key`, `token`, `secret`, or `password` are redacted. Values longer than 200 characters are truncated.

### Input Sanitization

All CLI commands sent to the Flipper Zero pass through `core/sanitize.py`:

- **Shell metacharacters stripped**: `;`, `&`, `|`, `` ` ``, `$`, `(`, `)`, `{`, `}`, `[`, `]`, `\`, `<`, `>`, `!`, `#`
- **Maximum length enforced**: 512 bytes (Flipper buffer limit)
- **Empty commands rejected**: After sanitization, empty strings raise `ValueError`

This prevents command injection through the serial interface, even if the AI agent constructs malicious input.

### Path Validation

All Flipper filesystem operations go through `core/risk.py:validate_flipper_path()`:

- **Traversal blocked**: `..` in any path component is rejected
- **Internal flash blocked**: `/int/` prefix and bare `/int` are rejected
- **Sensitive files blocked**: Paths ending in `.key`, `.priv`, `.secret` are rejected
- **SD card required**: All paths must start with `/ext/`

### Scope Enforcement

Engagement scope is defined at the orchestration layer:

- `SCOPE` environment variable in ralph-loop skill
- `scope_description`, `scope_targets`, and `out_of_scope` fields in campaign state
- Phase prompts inject scope into every AI context window

Scope enforcement is advisory (the AI agent must respect it), not programmatic at the MCP tool level. This is a known limitation.

### Transport Security

- USB serial is local-only (no network exposure)
- WiFi transport (to Flipper WiFi dev board) communicates over local network TCP
- Auto-reconnect logic prevents dangling connections
- Port lock prevents concurrent serial access from multiple processes

## In-Scope Vulnerabilities

We consider the following types of issues security vulnerabilities:

- **Prompt injection** leading to unauthorized tool calls or scope bypass
- **CLI command injection** bypassing `sanitize_cli_input()`
- **Path traversal** bypassing `validate_flipper_path()` to access internal flash or sensitive files
- **Risk classification bypass** -- executing a HIGH-risk action without proper classification
- **Audit log evasion** -- executing tool calls without them being logged
- **Transport hijacking** -- unauthorized access to the Flipper serial connection
- **Credential leakage** -- API keys, passwords, or tokens appearing in logs, reports, or findings files
- **Arbitrary code execution** via the MCP server or its dependencies

## Out-of-Scope Vulnerabilities

The following are **not** considered FlipperAgent security vulnerabilities:

- **Flipper Zero firmware bugs** -- report these to [Flipper Devices](https://docs.flipper.net/development/firmware/security)
- **Vulnerabilities in target devices** discovered during authorized testing -- these are findings, not FlipperAgent bugs
- **Physical access attacks** -- someone with physical access to your laptop can do anything
- **Social engineering** against FlipperAgent users
- **Denial of service** against third-party APIs (Shodan, OpenRouter, etc.)
- **AI model hallucinations** -- the AI agent may generate incorrect tool arguments; this is an AI limitation, not a security vulnerability, unless it bypasses a safety control
- **RF interference** from authorized testing -- this is an expected consequence of the tool's purpose

## Responsible Disclosure

We appreciate security researchers who help keep FlipperAgent safe. With your permission, we will credit you in release notes when a reported vulnerability is fixed. We do not offer monetary bounties at this time.
