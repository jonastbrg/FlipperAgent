# OpenCode Setup Guide for FlipperAgent

> Compiled from official docs (opencode.ai/docs/) and source code verification.
> Last updated: 2026-03-22

---

## 1. Setting a Default Model in opencode.jsonc

The `model` field at the top level sets the default model. Format is always `provider_id/model_id`.

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "model": "anthropic/claude-sonnet-4-5"
}
```

You can also set a lightweight model for background tasks (title generation, summaries):

```jsonc
{
  "model": "anthropic/claude-sonnet-4-5",
  "small_model": "anthropic/claude-haiku-4-5"
}
```

**Model selection priority (first match wins):**
1. CLI flag: `--model` / `-m` (format: `provider_id/model_id`)
2. Config file `model` key
3. Previously used model (remembered from last session)
4. Internal priority heuristic (first available model)

**There is no hardcoded default model.** If no model is configured and no provider is authenticated, OpenCode will prompt you to connect a provider.

---

## 2. Running OpenCode Non-Interactively

Use the `run` subcommand. The prompt is passed as positional arguments (NOT via a `--prompt` flag):

```bash
# Basic non-interactive execution
opencode run "Explain the use of context in Go"

# With a specific model
opencode run --model anthropic/claude-sonnet-4-5 "Your prompt here"

# With a specific agent
opencode run --agent build "Fix the failing tests"

# With file attachments
opencode run -f src/main.ts "Review this file"

# JSON output format (for scripting/automation)
opencode run --format json "List all TODO comments"

# Piping stdin
echo "What does this code do?" | opencode run -f src/main.ts ""
```

**Key `run` flags:**

| Flag | Alias | Description |
|------|-------|-------------|
| `[message..]` | (positional) | The prompt text |
| `--model` | `-m` | Model in `provider/model` format |
| `--agent` | | Agent to use (must be a primary agent) |
| `--command` | | Run a custom command, message becomes args |
| `--continue` | `-c` | Continue last session |
| `--session` | `-s` | Continue specific session ID |
| `--fork` | | Fork session (requires `--continue` or `--session`) |
| `--file` | `-f` | Attach file(s) to the message |
| `--format` | | Output format: `default` or `json` |
| `--title` | | Session title |
| `--attach` | | Attach to running server (e.g., `http://localhost:4096`) |
| `--dir` | | Directory to run in |
| `--port` | | Port for local server |
| `--variant` | | Reasoning effort variant (e.g., `high`, `max`) |
| `--thinking` | | Show thinking blocks |
| `--share` | | Share the session |

**IMPORTANT:** The `--prompt` flag exists only for TUI mode (interactive), NOT for `run`. For non-interactive use, always use `opencode run "your prompt"`.

**Permission behavior in `run` mode:** All permission requests are **auto-rejected** by default. The `run` command injects rules that deny `question`, `plan_enter`, and `plan_exit` permissions. If a tool requires permission (e.g., bash, edit), it will be rejected and logged. To allow tools in non-interactive mode, configure permissions in `opencode.jsonc`:

```jsonc
{
  "permission": {
    "bash": "allow",
    "edit": "allow"
  }
}
```

---

## 3. MCP Server Configuration

MCP servers are configured under the `mcp` key. Two types: `local` (stdio) and `remote` (HTTP/SSE).

### Local MCP Server (our FlipperAgent setup)

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "flipper": {
      "type": "local",
      "enabled": true,
      "timeout": 15000,
      "command": [
        "./flipperzero-mcp/.venv/bin/python",
        "-m", "flipper_mcp.cli.main"
      ],
      "environment": {
        "PYTHONUNBUFFERED": "1",
        "FLIPPER_TRANSPORT": "usb"
      }
    }
  }
}
```

### Local MCP Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `type` | `"local"` | Yes | | Must be `"local"` |
| `command` | `string[]` | Yes | | Command and arguments to launch server |
| `environment` | `object` | No | `{}` | Environment variables for the process |
| `enabled` | `boolean` | No | `true` | Enable/disable on startup |
| `timeout` | `number` | No | `5000` | Tool fetch timeout in milliseconds |

### Remote MCP Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `type` | `"remote"` | Yes | | Must be `"remote"` |
| `url` | `string` | Yes | | Remote server endpoint URL |
| `headers` | `object` | No | `{}` | HTTP headers (e.g., API keys) |
| `oauth` | `object\|false` | No | | OAuth config or `false` to disable |
| `enabled` | `boolean` | No | `true` | Enable/disable on startup |
| `timeout` | `number` | No | `5000` | Tool fetch timeout in milliseconds |

### Remote MCP Example

```jsonc
{
  "mcp": {
    "context7": {
      "type": "remote",
      "url": "https://mcp.context7.com/mcp",
      "headers": {
        "CONTEXT7_API_KEY": "{env:CONTEXT7_API_KEY}"
      }
    }
  }
}
```

---

## 4. Default Model if None Specified

There is **no hardcoded default model**. OpenCode's model selection priority:

1. `--model` CLI flag
2. `model` field in config
3. Previously used model (stored per-project in session state)
4. First model from an internal priority list based on available/authenticated providers

If no provider is authenticated, OpenCode will prompt the user to run `/connect`.

---

## 5. The --prompt Flag vs `run`

**They are different things:**

- **`opencode --prompt "text"`** — TUI (interactive) mode. Opens the full terminal UI with a pre-filled prompt. The TUI is interactive; the user can see the agent work and approve permissions.

- **`opencode run "text"`** — Non-interactive (headless) mode. Runs the prompt without a TUI, outputs results to stdout, and exits. All permission requests are auto-rejected unless configured to `"allow"` in config.

**For automation/scripting, always use `opencode run`.**

A model does NOT need to be set explicitly if:
- You have authenticated via `/connect` (credentials in `~/.local/share/opencode/auth.json`)
- OR you have a `model` field in your `opencode.jsonc`
- OR you have used OpenCode before (remembers last model)

---

## 6. Environment Variables

### Authentication

OpenCode uses its own credential store, NOT standard env vars like `ANTHROPIC_API_KEY`:

- **Credentials file:** `~/.local/share/opencode/auth.json`
- **Setup method:** Run `opencode` interactively, then use `/connect` to authenticate with providers
- **Supported auth:** API key entry, OAuth (Claude Pro/Max), browser-based

However, you CAN reference env vars in provider config using `{env:VAR_NAME}` syntax:

```jsonc
{
  "provider": {
    "anthropic": {
      "options": {
        "apiKey": "{env:ANTHROPIC_API_KEY}"
      }
    }
  }
}
```

### Provider-Specific Env Vars

| Provider | Environment Variable | Purpose |
|----------|---------------------|---------|
| Amazon Bedrock | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION` | AWS auth |
| Azure OpenAI | `AZURE_RESOURCE_NAME` | Resource name |
| Google Vertex | `GOOGLE_CLOUD_PROJECT`, `GOOGLE_APPLICATION_CREDENTIALS` | GCP auth |
| Cloudflare | `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN` | CF auth |
| GitLab | `GITLAB_TOKEN`, `GITLAB_INSTANCE_URL` | GitLab auth |

### OpenCode-Specific Env Vars

| Variable | Purpose |
|----------|---------|
| `OPENCODE_CONFIG` | Custom config file path |
| `OPENCODE_CONFIG_CONTENT` | Inline JSON config content |
| `OPENCODE_EXPERIMENTAL_LSP_TOOL=true` | Enable LSP tool |
| `OPENCODE_ENABLE_EXA=1` | Enable web search tool |
| `OPENCODE_AUTO_SHARE` | Auto-share sessions |
| `OPENCODE_SERVER_PASSWORD` | Basic auth for server mode |
| `OPENCODE_DISABLE_CLAUDE_CODE=1` | Disable Claude Code compatibility |

---

## 7. Verifying MCP Server Status

```bash
# List all configured MCP servers and their connection status
opencode mcp list

# Alternative alias
opencode mcp ls
```

Output shows for each server:
- Connection status icon: `checkmark` (connected), `circle` (not initialized/disabled), `warning` (needs auth), `x` (failed)
- Status text: `connected`, `not initialized`, `disabled`, `needs authentication`, `failed`
- Server type/command info

Additional MCP commands:
```bash
# Add a new MCP server interactively
opencode mcp add

# Authenticate with OAuth-enabled remote server
opencode mcp auth <server-name>

# Debug OAuth connection issues
opencode mcp debug <server-name>

# List OAuth auth status
opencode mcp auth list

# Remove OAuth credentials
opencode mcp logout <server-name>
```

---

## 8. Complete FlipperAgent Configuration

### Recommended opencode.jsonc

```jsonc
{
  "$schema": "https://opencode.ai/config.json",

  // Default model - requires authenticated provider
  "model": "anthropic/claude-sonnet-4-5",
  "small_model": "anthropic/claude-haiku-4-5",

  // MCP: Flipper Zero hardware bridge
  "mcp": {
    "flipper": {
      "type": "local",
      "enabled": true,
      "timeout": 15000,
      "command": [
        "./flipperzero-mcp/.venv/bin/python",
        "-m", "flipper_mcp.cli.main"
      ],
      "environment": {
        "PYTHONUNBUFFERED": "1",
        "FLIPPER_TRANSPORT": "usb"
      }
    }
  },

  // Permissions: allow tools in non-interactive mode
  "permission": {
    "bash": "allow",
    "edit": "allow",
    "read": "allow",
    "webfetch": "allow",
    "external_directory": "deny"
  },

  // Project rules
  "instructions": ["AGENTS.md", "docs/CONTRIBUTING.md"]
}
```

### Non-Interactive Execution Examples

```bash
# Run a prompt against the Flipper agent
opencode run --model anthropic/claude-sonnet-4-5 \
  "Use the flipper MCP tools to get device info"

# Run with a specific agent
opencode run --agent build "Scan for nearby sub-GHz signals"

# Pipe a script for execution
echo "List all Flipper tools available" | opencode run ""

# Continue a previous session
opencode run --continue "Now try reading the NFC tag"

# Run with JSON output for scripting
opencode run --format json "Get Flipper battery status"
```

### First-Time Setup Checklist

1. **Install OpenCode:** `curl -fsSL https://opencode.ai/install | bash` (or `npm i -g opencode`, `brew install opencode`)
2. **Authenticate provider:** Run `opencode` then `/connect` and select Anthropic (or OpenRouter)
3. **Verify auth:** `opencode auth list`
4. **Create config:** Place `opencode.jsonc` in project root (see above)
5. **Verify MCP:** `opencode mcp list` -- should show `flipper` as `connected`
6. **Test non-interactive:** `opencode run "List available MCP tools"`

---

## 9. Agent Configuration

Custom agents are defined under the `agent` key:

```jsonc
{
  "agent": {
    "flipper-operator": {
      "mode": "primary",
      "description": "Operates the Flipper Zero device via MCP tools",
      "model": "anthropic/claude-sonnet-4-5",
      "prompt": "{file:./docs/system_prompt.md}",
      "permission": {
        "bash": "allow",
        "edit": "allow"
      }
    }
  },
  "default_agent": "flipper-operator"
}
```

**Agent fields:**

| Field | Type | Description |
|-------|------|-------------|
| `mode` | `"primary"\|"subagent"\|"all"` | Primary agents are user-facing; subagents are invoked by primary agents |
| `description` | `string` | Required. Explains agent purpose |
| `model` | `string` | Override model (format: `provider/model`) |
| `prompt` | `string` | System prompt. Use `{file:path}` to load from file |
| `temperature` | `number` | 0.0-1.0 |
| `top_p` | `number` | 0.0-1.0 |
| `steps` | `number` | Max agentic iterations |
| `color` | `string` | UI color (hex or theme) |
| `permission` | `object` | Tool access controls |
| `disable` | `boolean` | Disable agent |
| `hidden` | `boolean` | Hide from autocomplete |

**Built-in agents:** `build` (primary, all tools), `plan` (primary, read-only analysis), `general` (subagent), `explore` (subagent, read-only).

Agents can also be defined as Markdown files in `.opencode/agents/` or `~/.config/opencode/agents/`.

---

## 10. Custom Commands

```jsonc
{
  "command": {
    "scan": {
      "template": "Use the Flipper MCP tools to scan for $1 signals. $ARGUMENTS",
      "description": "Scan for signals using Flipper",
      "agent": "flipper-operator"
    },
    "device-info": {
      "template": "Get complete device information from the connected Flipper Zero",
      "description": "Show Flipper device info"
    }
  }
}
```

Template placeholders: `$ARGUMENTS` (all args), `$1`/`$2`/`$3` (positional), `` !`cmd` `` (bash output), `@file` (file content).

---

## 11. Rules and AGENTS.md

OpenCode reads `AGENTS.md` (or `CLAUDE.md`) files automatically:

- **Project-level:** `./AGENTS.md` in project root and parent dirs
- **Global:** `~/.config/opencode/AGENTS.md`
- **Claude Code compat:** `~/.claude/CLAUDE.md` (disable with `OPENCODE_DISABLE_CLAUDE_CODE=1`)

The `instructions` config field can reference additional rule files:
```jsonc
{
  "instructions": ["CONTRIBUTING.md", "docs/guidelines.md", ".cursor/rules/*.md"]
}
```

Generate initial rules: `/init` command in TUI.

---

## 12. Built-in Tools Reference

| Tool | Description | Default Permission |
|------|-------------|--------------------|
| `bash` | Execute shell commands | `allow` |
| `edit` | Modify files (exact string replace) | `allow` |
| `write` | Create/overwrite files | shares `edit` |
| `read` | Read file contents | `allow` |
| `grep` | Search file contents (regex) | `allow` |
| `glob` | Find files by pattern | `allow` |
| `list` | List directory contents | `allow` |
| `webfetch` | Fetch web page content | `allow` |
| `websearch` | Web search via Exa | `allow` (needs `OPENCODE_ENABLE_EXA=1`) |
| `skill` | Load SKILL.md instructions | `allow` |
| `todowrite` | Create/update task lists | `allow` |
| `todoread` | Read task lists | `allow` |
| `task` | Spawn subagent | `allow` |
| `question` | Ask user questions | `allow` |
| `lsp` | LSP queries (experimental) | `allow` (needs env var) |
| `patch` | Apply patch files | shares `edit` |

Disable a tool: `"tools": { "bash": false }` in config or agent.

---

## 13. Permissions (YOLO Mode)

Allow everything (no approval prompts):

```jsonc
{
  "permission": "allow"
}
```

Selective allow with granular bash patterns:

```jsonc
{
  "permission": {
    "bash": {
      "*": "ask",
      "git *": "allow",
      "python *": "allow",
      "rm -rf *": "deny"
    },
    "edit": "allow",
    "read": "allow"
  }
}
```

Defaults: most tools are `"allow"`, except `doom_loop` and `external_directory` which are `"ask"`.

---

## 14. Config File Locations & Precedence

Configs are **merged** (not replaced). Later sources override earlier ones:

1. Remote config (`.well-known/opencode`) -- lowest priority
2. Global config (`~/.config/opencode/opencode.json`)
3. Custom path (`OPENCODE_CONFIG` env var)
4. Project config (`opencode.json` or `opencode.jsonc` in project root)
5. `.opencode/` directory config
6. Inline config (`OPENCODE_CONFIG_CONTENT` env var) -- highest priority

Both `.json` and `.jsonc` (JSON with comments) are supported.
