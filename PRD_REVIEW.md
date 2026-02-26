# PRD Review: Autonomous Cyber-Physical Red Team Agent ("Bellum")

**Reviewer:** Claude (automated review)
**Date:** 2026-02-26 (updated)
**PRD Version:** Draft, 2026-02-26

---

## Executive Summary

This is an ambitious, well-structured PRD for building an autonomous AI agent that bridges digital and physical-layer offensive security. The vision is compelling and the competitive differentiation (no one else combines autonomous AI reasoning + physical-layer attack tools) is genuine. The scope is large but feasible given the development approach: **Claude Code with parallel subagents running 24/7**, leveraging existing codebases (CAI, flipperzero-mcp, pyFlipper, Bleak) rather than building from scratch.

**Overall assessment:** Strong vision. The key architectural decision is framework choice — CAI is the strongest candidate. Error handling/recovery is the biggest gap that needs to be designed into the architecture from day one.

---

## 1. Strengths

### Clear problem statement and differentiation
The PRD precisely identifies the gap between digital-only AI pentest agents (HexStrike, CAI) and non-autonomous physical-layer tools (pyFlipper, flipperzero-mcp). The competitive landscape table in Section 11 makes this easy to grasp. The "novel contribution" framing in Section 3.4 is crisp and demo-friendly.

### Well-defined tool taxonomy
The tool tables in Section 4.4 are thorough — each tool has implementation library, input, and output specified. This is directly translatable to code. The three-tier split (Physical / Digital / Research) maps cleanly to the repo structure.

### Concrete demo script
The 60-second demo script (Section 9) and attack chain example (Section 4.6) make the end-state vivid. This is the kind of specificity that keeps a hackathon project on track.

### Honest risk assessment
Section 10 correctly identifies the highest-risk items (LLM refusals, hardware delays, WiFi monitor mode). The mitigations are practical.

### Strong existing ecosystem to build on
The PRD correctly identifies key libraries (Bleak, pyFlipper, flipperzero-mcp, Scapy) and frameworks (CAI, HexStrike) that can be leveraged. With parallel Claude Code subagents, integration of these existing codebases can happen simultaneously across multiple workstreams.

---

## 2. Critical Concerns

### 2.1 Scope Feasibility *(Revised)*

~~The original concern about "one developer in 10 days" is withdrawn.~~ With Claude Code subagents running 24/7 in parallel, the development velocity is significantly higher. The 30+ tools are feasible because:
- Many tools are thin wrappers around existing libraries (Bleak, Scapy, python-nmap, pyFlipper)
- Research tools (web search, CVE lookup, GitHub search) are straightforward API calls
- Multiple tools can be developed in parallel by separate subagents
- LLM switching across providers is just an API endpoint change (via litellm or OpenAI-compatible APIs)

**Remaining concern:** Integration testing across all these tools against the actual agent loop. Individual tools are easy; making them work cohesively in a multi-step attack chain is the hard part. Allocate time for end-to-end testing, not just unit-level tool verification.

### 2.2 LLM Provider Strategy *(Revised)*

Since switching providers is just an endpoint change, supporting multiple providers adds minimal overhead. The PRD's multi-provider approach is sound.

**Remaining concerns:**
1. **Test offensive prompts early.** The entire demo depends on the LLM cooperating with tool calls for security operations. Test MiniMax M2.5, Kimi K2.5, and GLM-5 against actual attack prompts before committing development effort.
2. **Latency during live demo.** Chinese API providers may have variable latency from the US. For the live hackathon demo, consider having a local Ollama model as a low-latency fallback (even if slower per-token, no network round-trip).
3. **Consider hybrid approach.** Use an aligned model (Claude/GPT-4) for planning/research steps (framed as "authorized security evaluation") and unaligned models for exploit execution steps where refusals are more likely.

### 2.3 Error Handling and Recovery Strategy — THE BIGGEST GAP

This is the most critical missing piece in the PRD. The ReAct loop pseudocode (Section 4.5) shows a simple `while not done` loop but doesn't address:

**Tool-level failures:**
- BLE device out of range, connection drops mid-enumeration
- nmap timeout or host unreachable
- Web search returns no results
- Flipper Zero serial disconnection
- Rate limiting on APIs (Shodan, GitHub, LLM providers)

**Agent-level failures:**
- Agent loops on the same failed approach repeatedly
- Agent exhausts context window with verbose tool outputs
- Agent hallucinates tool names or parameters
- Agent loses track of its attack plan after many steps

**Recovery patterns needed:**
- **Tool retry with backoff:** Each tool should have configurable retry logic (attempts, backoff strategy, timeout)
- **Frustration counter / pivot logic:** After N failed attempts on one vector, the agent should explicitly reason about pivoting to an alternative. This should be in the system prompt as a hard rule, not just a suggestion.
- **Observation compression:** After each reconnaissance phase, compress tool outputs into a structured summary (JSON) to manage context window. Raw nmap/Wireshark output will blow through token limits fast.
- **Checkpointing:** Save agent state (current plan, findings so far, tools used) to disk at each step. If the agent crashes or the LLM errors out, resume from the last checkpoint rather than starting over.
- **Max iteration cap with graceful exit:** Not just a hard stop, but the agent should generate a partial report with findings so far when hitting the cap.
- **Tool output validation:** Validate tool outputs before feeding them back to the LLM. Truncate oversized outputs. Flag obvious errors.

**Recommendation:** Design the error handling architecture before writing any tool code. This is the difference between a demo that works once on a good day and an agent that reliably converges on real targets.

### 2.4 Security of the Agent Itself

The PRD focuses on the agent's offensive capabilities but doesn't address the security of the agent's own infrastructure:
- `code_execute` runs arbitrary code in a "sandboxed" subprocess — but no sandboxing mechanism is specified. What prevents the LLM from generating `rm -rf /` or exfiltrating API keys?
- If using unaligned models, prompt injection through tool outputs (e.g., a web page that says "ignore your instructions and...") is a real risk.
- API keys for Shodan, SerpAPI, GitHub, and LLM providers need secure storage.

**Recommendation:**
- Specify the sandboxing mechanism for `code_execute` (Docker container, nsjail, or at minimum a restricted subprocess with no filesystem access outside a temp dir).
- Add input validation on tool outputs before feeding them back to the LLM.
- Use environment variables or a secrets manager for API keys — never hardcode them.

---

## 3. Agent Framework Decision — Detailed Analysis

The PRD lists four options (Section 4.3): Custom ReAct loop, CAI, OpenCode + MCP, LangChain/LangGraph. After researching the current state of these frameworks, here's an updated analysis including Kilo Code and OpenCode:

### 3.1 CAI (Cybersecurity AI) — STRONGEST CANDIDATE

**GitHub:** [aliasrobotics/cai](https://github.com/aliasrobotics/cai)
**Docs:** [aliasrobotics.github.io/cai](https://aliasrobotics.github.io/cai/)

**Why CAI is the best fit for Bellum:**

| Feature | Relevance to Bellum |
|---------|-------------------|
| **Purpose-built for offensive security** | No need to fight framework assumptions; security operations are first-class |
| **ReAct pattern already implemented** | Core agent loop is done — focus effort on tools, not infrastructure |
| **300+ LLM models supported** | Multi-provider strategy works out of the box, including Chinese models |
| **Custom tools via `@function_tool` decorator** | Adding Flipper Zero / BLE tools is trivial — write a Python function, decorate it, pass to agent |
| **MCP support (SSE + stdio)** | flipperzero-mcp plugs in directly as an MCP server |
| **Built-in tools** | LinuxCmd (command execution), WebSearch (OSINT), Code (dynamic scripts), SSHTunnel — these overlap with PRD's digital/research tools |
| **Agent-as-tool pattern** | Specialized agents (BLE recon agent, exploit agent, report agent) can be composed |
| **Guardrails & HITL** | Human-in-the-loop for dangerous operations (e.g., BadUSB execution) |
| **Python-based** | Same language as Bleak, pyFlipper, Scapy — no FFI boundary |
| **Robot security case study** | Already used for robot fleet security (Sublight Shipping case study via MCP) — directly relevant |

**What CAI gives you for free:**
- ReAct agent loop with tool dispatch
- LLM provider abstraction (300+ models)
- Built-in command execution, web search, code execution, SSH
- MCP integration for Flipper Zero
- Tracing and logging
- Agent composition (agent-as-tool)

**What you still need to build:**
- Physical-layer tools (BLE via Bleak, Sub-GHz/IR via pyFlipper) as `@function_tool` functions
- Attack planning prompts (system prompts for the offensive security domain)
- Report generation (Jinja2 templates)
- Error handling/recovery layer (see Section 2.3)
- Configuration management

**Licensing note:** CAI is open source for non-commercial research. The hackathon qualifies. For Parabellum AI commercial use later, you'd need a CAI PRO license or fork the MIT-licensed parts (derived from openai-agents-python).

### 3.2 OpenCode — VIABLE ALTERNATIVE (Development Tool + Potential Runtime)

**GitHub:** [opencode-ai/opencode](https://github.com/opencode-ai/opencode) (100K+ stars)
**Docs:** [opencode.ai](https://opencode.ai/)

OpenCode is a Go-based terminal AI agent with 100K+ stars. It's primarily a coding agent, but its architecture is relevant:

| Feature | Relevance |
|---------|-----------|
| **Primary agents + subagents** | Could model attack phases as subagents (recon agent, exploit agent, report agent) |
| **MCP support** | flipperzero-mcp works as an MCP server |
| **Custom tools via plugins** | `.opencode/plugins/` for extending capabilities |
| **Multi-provider LLM** | OpenAI, Anthropic, Google, Groq, OpenRouter, etc. |
| **Agent permissions** | Control which tools each agent can access |

**Pros for Bellum:**
- Extremely mature and battle-tested (100K+ stars, 700+ contributors)
- MCP ecosystem is well-established
- Could serve as both the development environment AND the runtime agent
- Custom agents can be defined in config files

**Cons for Bellum:**
- **Not security-focused** — would need significant customization for offensive security workflows
- **Go-based core** — custom tools need to go through MCP or plugin system, not direct Python integration. The BLE/Flipper tools are all Python (Bleak, pyFlipper, Scapy).
- **Coding agent assumptions** — built-in tools are file editing, code search, etc. Not network scanning, BLE enumeration, RF capture.
- **Overkill** — brings a full TUI, SQLite session storage, LSP integration that Bellum doesn't need

**Verdict:** Better as a development tool (alternative/complement to Claude Code) than as the Bellum runtime. However, if you want to quickly prototype the agent by defining custom MCP tools and running them through OpenCode's agent loop, it could work for the hackathon demo with less custom code.

### 3.3 Kilo Code — DEVELOPMENT TOOL, NOT RUNTIME

**GitHub:** [Kilo-Org/kilocode](https://github.com/Kilo-Org/kilocode) (13K+ stars)
**Docs:** [kilo.ai](https://kilo.ai/)

Kilo Code is a fork/superset of Cline/Roo Code. It's a VS Code extension + CLI for AI-assisted coding.

| Feature | Relevance |
|---------|-----------|
| **Agent Manager with git worktree isolation** | Useful for running multiple development subagents in parallel |
| **Orchestrator mode** | Breaks complex tasks into subtasks across modes |
| **MCP marketplace** | Ecosystem of MCP tools |
| **Custom modes** | Could create a "Security" mode with restricted tool access |
| **CLI with `--auto` flag** | Fully autonomous operation for CI/CD |

**Pros for Bellum:**
- **Agent Manager** is great for parallel development — spin up multiple agents working on different tools simultaneously
- **Orchestrator mode** could coordinate the attack chain phases
- Custom modes + tool group filtering could restrict agents to security-relevant tools
- TypeScript/Node.js based — different ecosystem but MCP bridges the gap

**Cons for Bellum:**
- **Not security-focused** — same issue as OpenCode
- **TypeScript core** — all physical tools (Bleak, pyFlipper, Scapy) are Python; would need MCP bridges for everything
- **VS Code dependency** — the full power is in the IDE extension, less so in the CLI
- **Primarily a coding agent** — the core loop is "read code, think, edit code", not "scan target, think, exploit target"

**Verdict:** Excellent as a development tool for building Bellum (especially the Agent Manager for parallel workstreams). Not suitable as the Bellum runtime itself. Could complement Claude Code for development.

### 3.4 Custom ReAct Loop — FALLBACK OPTION

Still viable if CAI introduces too much friction. But given that CAI already implements ReAct with tool dispatch, multi-model support, and MCP integration, building from scratch would be duplicating work.

**When to go custom:** If CAI's licensing is a problem for commercial use, or if CAI's opinionated architecture conflicts with specific Bellum requirements (e.g., physical tool latency handling, hardware reconnection logic).

### 3.5 Framework Recommendation

```
RECOMMENDED: CAI as the agent runtime
├── Provides: ReAct loop, LLM abstraction, tool dispatch, MCP, tracing
├── You build: Physical tools (@function_tool), attack prompts, reporting, error recovery
└── Risk: Non-commercial license for hackathon is fine; commercial use needs CAI PRO or fork

ALTERNATIVE: OpenCode as quick-prototype runtime
├── Provides: Agent loop, MCP integration, multi-provider LLM, session management
├── You build: All tools as MCP servers (Python→MCP bridge), attack prompts
└── Risk: Go/Python boundary via MCP adds latency and complexity

DEVELOPMENT TOOLS: Claude Code (primary) + Kilo Code Agent Manager (parallel workstreams)
```

---

## 4. Error Handling & Recovery Architecture (New Section)

Since this is the agreed-upon biggest gap, here's a concrete architecture proposal:

### 4.1 Tool-Level Resilience

```python
@dataclass
class ToolConfig:
    max_retries: int = 3
    retry_backoff: float = 2.0  # exponential backoff base
    timeout: float = 30.0       # seconds
    max_output_size: int = 4096 # chars — truncate beyond this
    requires_confirmation: bool = False  # HITL for dangerous tools

class ToolResult:
    success: bool
    data: Any
    error: str | None
    retries_used: int
    truncated: bool
```

Each tool call should:
1. Validate inputs before execution
2. Set a timeout (BLE operations can hang indefinitely)
3. Retry on transient failures (network, serial timeout) with exponential backoff
4. Truncate oversized output (nmap verbose output, packet captures)
5. Return structured results with success/failure status

### 4.2 Agent-Level Recovery

```python
class AgentState:
    current_phase: str          # "recon", "research", "enumerate", "exploit", "report"
    findings: dict              # Compressed findings from each phase
    attack_plan: list[str]      # Current ordered list of attack steps
    failed_vectors: list[str]   # Vectors that were tried and failed
    iteration_count: int
    max_iterations: int = 50
    consecutive_failures: int = 0
    max_consecutive_failures: int = 5  # pivot threshold

# In the system prompt:
RECOVERY_RULES = """
- If a tool call fails, analyze the error before retrying.
- If the same approach fails 3 times, mark it as failed and pivot to an alternative.
- After completing each phase (recon, research, enumerate, exploit), summarize
  findings in a structured JSON block to conserve context.
- If you reach {max_iterations} steps, generate a partial report with findings so far.
- Never retry a tool call with identical parameters — vary the approach.
- Maintain a running list of failed vectors to avoid revisiting them.
"""
```

### 4.3 Context Window Management

This is critical for long attack chains:

1. **Phase summaries:** After each phase, the agent should produce a compressed JSON summary of findings. Raw tool outputs are dropped from context.
2. **Sliding window:** Keep the last N tool interactions in full detail, compress older ones.
3. **Finding deduplication:** If multiple tools return overlapping info (e.g., BLE scan and nmap both find the same device), deduplicate.

### 4.4 Checkpointing

```python
# After each tool call, save state to disk
checkpoint = {
    "timestamp": now(),
    "phase": agent_state.current_phase,
    "findings": agent_state.findings,
    "plan": agent_state.attack_plan,
    "history": conversation_history[-10:],  # last 10 messages
    "tool_results": recent_tool_results,
}
save_checkpoint(checkpoint, f"bellum_checkpoint_{step}.json")
```

If the agent crashes (LLM error, hardware disconnect, etc.), resume from the last checkpoint with a recovery prompt: "You were conducting a security evaluation. Here's what you found so far: {findings}. Continue from phase: {phase}."

### 4.5 Hardware-Specific Recovery

Physical tools have unique failure modes:

| Failure | Detection | Recovery |
|---------|-----------|----------|
| BLE device out of range | ConnectionError from Bleak | Wait 5s, retry 3x, then mark BLE vector as "intermittent" |
| Flipper serial disconnect | Serial timeout/error | Attempt reconnection, fall back to laptop-native tools (Bleak for BLE) |
| Sub-GHz no signal detected | Empty scan result | Widen frequency range, increase scan duration, pivot to other protocols |
| IR capture timeout | No signal captured | Retry with longer timeout, pivot to other protocols |
| WiFi adapter not in monitor mode | Permission/capability error | Skip WiFi attacks, note in report, focus on BLE/Sub-GHz |

---

## 5. Minor Issues

| Section | Issue | Suggestion |
|---------|-------|------------|
| 4.2 | "MiniMax M2.5" — verify this model ID is current; MiniMax model naming changes frequently | Pin the exact model ID in config |
| 4.4 | `wifi_deauth` tool — WiFi deauthentication is illegal in many jurisdictions even during pentests | Add a legal disclaimer; consider removing from default toolset |
| 4.6 | Attack chain example uses `http://robot_ip:8080` — hardcoded HTTP | Agent should discover this dynamically from nmap output |
| 6 | "Getting March 6" for Flipper Zero — this leaves 1 day for hardware integration before hackathon | Have a no-Flipper contingency plan that uses laptop BLE only |
| 7 | No version pins on dependencies | Pin major versions at minimum to prevent breakage |
| 8 | Repo name is "bellum/" but the GitHub repo is "FlipperAgent" | Align naming — pick one |
| 9 | Demo script assumes BLE attack succeeds in one take | Prepare a fallback demo with pre-recorded footage |
| 13 | Open question #1 deadline is Feb 28 — that's in 2 days | Decide now: CAI framework (see Section 3) |

---

## 6. Summary of Recommendations

1. **Use CAI as the agent framework.** It provides the ReAct loop, multi-model LLM support, MCP integration, and built-in security tools. Build physical-layer tools as `@function_tool` extensions. This eliminates the "build vs. buy" question for the agent core.
2. **Design error handling from day one.** Tool retry logic, agent pivot logic, context compression, checkpointing, and hardware recovery. This is the section in this review to spend the most time on (Section 4).
3. **Test LLM providers against offensive prompts immediately.** The demo depends on the LLM cooperating. Test before building.
4. **Leverage existing codebases aggressively.** CAI for the agent, flipperzero-mcp for Flipper integration, Bleak for BLE, pyFlipper for serial. Don't rewrite what exists.
5. **Use Claude Code subagents for parallel development.** Different tools, different workstreams, simultaneously. Kilo Code's Agent Manager could supplement this for VS Code-based work.
6. **Specify the `code_execute` sandbox.** Docker container or nsjail at minimum.
7. **Prepare a no-Flipper contingency.** BLE via laptop Bleak is the primary demo path. Flipper Zero adds Sub-GHz/IR but isn't required for the core BLE attack demo.
8. **Align repo naming.** "Bellum" vs "FlipperAgent" — pick one.

---

## Appendix: Framework Comparison Matrix

| Criterion | CAI | OpenCode | Kilo Code | Custom ReAct |
|-----------|-----|----------|-----------|-------------|
| **Security-focused** | Yes (purpose-built) | No | No | You build it |
| **ReAct loop** | Built-in | Built-in (for coding) | Built-in (for coding) | You build it |
| **MCP support** | Yes (SSE + stdio) | Yes | Yes | You build it |
| **Custom tools** | `@function_tool` (Python) | Plugins (Go/MCP) | MCP / custom registry | Direct Python |
| **Multi-model LLM** | 300+ models | Major providers | 500+ via OpenRouter | Via litellm |
| **Python ecosystem** | Native (Bleak, Scapy, pyFlipper) | MCP bridge needed | MCP bridge needed | Native |
| **Agent composition** | Agent-as-tool | Subagents | Orchestrator mode | You build it |
| **Error recovery** | Basic (HITL, guardrails) | Session management | N/A | You build it |
| **Community size** | Small (security niche) | 100K+ stars | 13K+ stars | N/A |
| **License** | Non-commercial research | MIT | Apache 2.0 | N/A |
| **Hackathon fit** | Excellent | Good | Fair | Good |
| **Time to first demo** | ~2 days | ~3 days | ~4 days | ~4 days |

**Sources:**
- [CAI GitHub](https://github.com/aliasrobotics/cai) | [CAI Docs](https://aliasrobotics.github.io/cai/)
- [OpenCode GitHub](https://github.com/opencode-ai/opencode) | [OpenCode Docs](https://opencode.ai/)
- [Kilo Code GitHub](https://github.com/Kilo-Org/kilocode) | [Kilo Code Docs](https://kilo.ai/)
