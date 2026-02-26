# PRD Review: Autonomous Cyber-Physical Red Team Agent ("Bellum")

**Reviewer:** Claude (automated review)
**Date:** 2026-02-26 (updated)
**PRD Version:** Draft, 2026-02-26

---

## Executive Summary

This is an ambitious, well-structured PRD for building an autonomous AI agent that bridges digital and physical-layer offensive security. The vision is compelling and the competitive differentiation (no one else combines autonomous AI reasoning + physical-layer attack tools) is genuine. The scope is large but feasible given the development approach: **Claude Code with parallel subagents running 24/7**, leveraging existing codebases (CAI, flipperzero-mcp, pyFlipper, Bleak) rather than building from scratch.

**Overall assessment:** Strong vision. The key architectural decision is framework choice — **OpenCode is the winner**. It provides the agent loop, MCP integration, multi-model LLM support, Skills system, custom tools, and a polished TUI out of the box — all without writing a single line of framework code. Error handling/recovery is the biggest gap that needs to be designed into the architecture from day one.

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

The PRD lists four options (Section 4.3): Custom ReAct loop, CAI, OpenCode + MCP, LangChain/LangGraph. After deep research on all candidates, including hands-on analysis of architecture, extensibility, and fit for a hackathon with 9 days to demo:

### 3.1 OpenCode — THE WINNER

**GitHub:** [sst/opencode](https://github.com/sst/opencode) (also [anomalyco/opencode](https://github.com/anomalyco/opencode))
**Docs:** [opencode.ai](https://opencode.ai/)
**Stars:** ~111,000 | **License:** MIT | **Latest:** v1.2.14 (Feb 25, 2026) | **Contributors:** 776

OpenCode is an open-source, provider-agnostic AI agent for the terminal — essentially open-source Claude Code. It has a ReAct-style agent loop under the hood, but the key insight is: **you don't need to write any framework code.** Everything Bellum needs is configurable without touching OpenCode's 111K LOC codebase.

**Why OpenCode wins for Bellum:**

| Feature | How It Maps to Bellum |
|---------|----------------------|
| **MCP support (native, first-class)** | `flipperzero-mcp` plugs in directly. Write additional MCP servers for BLE/RF tools. Config-only integration. |
| **Custom tools** (`.opencode/tools/`) | TS/JS files that shell out to Python scripts (Bleak, pyFlipper, Scapy, nmap). Tool = file. |
| **Skills system** (`.opencode/skills/`) | Encode attack chain workflows, recon patterns, exploit templates as SKILL.md files. Agent loads on demand. |
| **Custom agents** (`.opencode/agents/`) | Define `bellum-recon`, `bellum-exploit`, `bellum-report` agents with different LLMs, tools, and system prompts. |
| **75+ LLM providers** | MiniMax, Kimi, Ollama, Claude, DeepSeek, Groq — all via config. Different model per agent. |
| **Non-interactive mode** | `opencode "scan all BLE devices and identify vulnerable GATT services"` — scriptable, demoable. |
| **Polished TUI** | Demo-ready out of the box. Judges see a clean interface, not raw terminal scroll. |
| **Client/server architecture** | Run on laptop, drive from phone via HTTP API if needed. |
| **Plugin hooks** | `tool.execute.before` for audit logging, `permission.ask` for HITL on dangerous operations. |
| **Git-based snapshots** | Every action tracked — critical for red team audit trail. |
| **MIT license** | No commercial restrictions. Clean for Parabellum AI. |

**What OpenCode gives you for free (zero framework code):**
- ReAct agent loop with tool dispatch (battle-tested, 2.5M monthly users)
- LLM provider routing (75+ providers, per-agent model selection)
- MCP protocol handling (local stdio + remote SSE + OAuth)
- Skills system for reusable workflow instructions
- Session management, context compression, subagent delegation
- Polished TUI with real-time streaming
- Non-interactive mode for scripted attack chains

**What you build (your actual IP):**
- MCP servers / custom tools wrapping Flipper Zero, Bleak, nmap, Scapy
- Skills encoding attack chain patterns (BLE recon, RF replay, zero-knowledge assessment)
- Agent definitions with red-team system prompts
- Python scripts that actually talk to hardware

**The play — fork OpenCode, add orchestration layer:**

We don't just extend via config — we fork and add a **ralph loop orchestrator** that drives the attack state machine externally. The LLM does the work within each phase; deterministic code sequences the phases, validates output, and handles pivot logic.

```
bellum/                                   # forked from opencode
├── packages/opencode/src/bellum/         # OUR ADDITIONS (~200 LOC)
│   ├── orchestrator.ts                   # Phase sequencing, ralph loop runner
│   ├── ralph.ts                          # Ralph Wiggum loop implementation
│   ├── state.ts                          # EngagementState types
│   ├── gates.ts                          # Backpressure gate validators
│   └── prompts/                          # Phase prompt templates
├── scripts/                              # Python tools (called via Bash)
│   ├── hardware/                         # ble_scan.py, ble_write.py, subghz_*.py, etc.
│   ├── recon/                            # cve_search.py, shodan_search.py, github_search.py
│   └── util/                             # packet_analyze.py, firmware_analyze.py
├── .opencode/
│   ├── skills/                           # Attack workflow instructions (SKILL.md)
│   ├── plugins/                          # HITL gate, hardware recovery, audit log
│   └── opencode.json                     # MCP servers, model config
├── findings/                             # Runtime output (phase JSONs)
├── checkpoints/                          # Crash recovery
└── reports/                              # Generated pentest reports
```

**Key architecture decisions:**
- **Ralph loops** (from [ralph-wiggum plugin](https://github.com/anthropics/claude-code/blob/main/plugins/ralph-wiggum/README.md)) iterate each phase until completion criteria met. The LLM's previous work persists in files — each iteration sees fresh context + file state.
- **Backpressure gates** block phase transitions until output validates (e.g., recon must produce >= 1 surface before research can start).
- **OpenCode's built-in tools** (Bash, WebSearch, WebFetch, Read/Write, Task, TodoWrite) cover half the PRD's tool list for free. Hardware tools are Python scripts called via Bash.
- **Yolo mode** via three layers: `opencode -p` (auto-approves all permissions in non-interactive mode), global `"permission": { "*": "allow" }` in config, and a `permission.ask` plugin hook as fallback. Full autonomous operation with zero user interaction.
- **Each phase = `opencode -p` invocation** (not nested subagents). Sidesteps three upstream bugs: subagents don't inherit permissions ([#12566](https://github.com/anomalyco/opencode/issues/12566)), can't spawn sub-subagents ([#7296](https://github.com/anomalyco/opencode/issues/7296)), and no async dispatch ([#15069](https://github.com/anomalyco/opencode/issues/15069)).
- **Parallel execution within phases** via OpenCode's Task tool — phase agent fires multiple Task calls in one message (e.g., 4 parallel recon scans, 3 parallel research tasks). This is proven to work in upstream.
- **Files are shared memory.** No token context carries between phases. Each phase reads findings from disk, writes updated findings. Infinite effective context.

**Honest trade-offs:**
- Fork maintenance burden (but additions are isolated: ~20 lines changed in `task.ts`, ~270 LOC additive in `src/bellum/`, ~10 LOC for `--agent` CLI flag)
- Bun runtime dependency (one extra install)
- Python scripts called via Bash (not native OpenCode tools — but simpler, no TS wrappers needed)
- OpenCode's TUI is coding-oriented (but the agent prompts fully override the behavior)
- Three upstream subagent bugs require awareness; architecture sidesteps all three, but fork fixes (~20 LOC in `task.ts`) add robustness
- `--agent` CLI flag and plugin hook field names need validation against actual OpenCode source at implementation time

### 3.2 CAI (Cybersecurity AI) — STRONG RUNNER-UP

**GitHub:** [aliasrobotics/cai](https://github.com/aliasrobotics/cai) (~7,500 stars)
**Docs:** [aliasrobotics.github.io/cai](https://aliasrobotics.github.io/cai/)

CAI is purpose-built for offensive security by a robotics security company (Alias Robotics). It has deep OT/IoT/ROS expertise and has been deployed against industrial robots, MQTT brokers, and fleet management systems. The ReAct loop, 300+ model support, `@function_tool` decorator, and MCP integration are all excellent.

**Why it's the runner-up, not the winner:**

| Concern | Impact |
|---------|--------|
| **Non-commercial license** | Hackathon is fine, but Parabellum AI commercial use requires CAI PRO license or a fork. OpenCode is MIT. |
| **Python-only ecosystem** | Fine for tools, but no polished TUI for demos. Terminal output is raw. |
| **Smaller community** | ~7.5K stars vs 111K. Fewer plugins, less ecosystem support. |
| **More framework to learn** | Patterns, Handoffs, Guardrails, Turns, Tracing — powerful but opinionated. |
| **No Skills system** | Attack workflows need to be hardcoded in system prompts, not loaded on demand. |

**When to choose CAI instead:** If the Python-native tool integration (no TS→Python shell-out) outweighs the UX and licensing advantages of OpenCode. Or if you need CAI's security-specific guardrails and tracing for a production deployment.

### 3.3 Custom ReAct Loop — ELIMINATED

With OpenCode providing the full agent loop, MCP integration, multi-model support, Skills, and custom tools via config-only extension, building a custom ReAct loop is reinventing the wheel. The ~200 LOC simplicity argument doesn't hold when OpenCode gives you all that for zero framework code while also providing a polished TUI, session management, and plugin hooks.

### 3.4 LangChain/LangGraph — ELIMINATED

Heavyweight, not security-focused, abstractions on abstractions. No advantage over OpenCode for this use case.

### 3.5 Framework Recommendation

```
RECOMMENDED: Fork OpenCode + Ralph Wiggum loops
├── Provides: Agent loop, MCP, Skills, subagents, 75+ LLM providers, TUI, Bash/WebSearch/Read/Write
├── We add: Orchestrator (~200 LOC TS), ralph loop runner, backpressure gates
├── We add: Python scripts for hardware (Bleak, pyFlipper, Scapy), recon APIs (Shodan, NVD, GitHub)
├── We add: Skills (attack workflows), plugins (HITL gate, hardware recovery, audit)
├── Architecture: Ralph loops iterate each phase. Files = shared memory. Subagents = parallelism.
└── Time to first demo: ~1-2 days (once scripts are wired)

FALLBACK: CAI as the agent runtime
├── When: If OpenCode fork introduces too much friction, or if native Python tool integration is critical
└── Trade-off: Better Python integration, worse TUI/UX, non-commercial license

DEVELOPMENT: Claude Code (primary) for building the scripts and orchestrator
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

1. **Fork OpenCode + add Ralph Wiggum loop orchestrator.** OpenCode provides the agent loop, subagents, built-in tools (Bash, WebSearch, WebFetch, Read/Write, Task), Skills, MCP, 75+ LLM providers, and TUI. We add ~200 LOC of orchestrator code that drives the attack state machine via ralph loops with backpressure gates. MIT license.
2. **Python scripts via Bash for hardware tools.** No TS tool wrappers needed. BLE (Bleak), Flipper (pyFlipper), network (nmap, Scapy), recon APIs (Shodan, NVD, GitHub) are all Python scripts in `scripts/` called by the agent via OpenCode's Bash tool. Skills encode attack workflows. Plugins enforce HITL gates and hardware recovery.
3. **Design error handling from day one.** Tool retry logic, agent pivot logic, context compression, checkpointing, and hardware recovery. This is the section in this review to spend the most time on (Section 4). OpenCode's plugin hooks (`tool.execute.before/after`) can help implement this.
4. **Test LLM providers against offensive prompts immediately.** The demo depends on the LLM cooperating. Test MiniMax M2.5, Kimi K2.5 against actual attack prompts before committing development effort.
5. **Leverage existing codebases aggressively.** OpenCode for the agent runtime, flipperzero-mcp for Flipper integration, Bleak for BLE, pyFlipper for serial. Don't rewrite what exists.
6. **Use Claude Code for parallel development.** Different tools, different workstreams, simultaneously.
7. **Specify the `code_execute` sandbox.** Docker container or nsjail at minimum.
8. **Prepare a no-Flipper contingency.** BLE via laptop Bleak is the primary demo path. Flipper Zero adds Sub-GHz/IR but isn't required for the core BLE attack demo.
9. **Align repo naming.** "Bellum" vs "FlipperAgent" — pick one.

---

## Appendix: Framework Comparison Matrix

| Criterion | OpenCode | CAI | Custom ReAct |
|-----------|----------|-----|-------------|
| **Security-focused** | No (but fully customizable via agents/skills) | Yes (purpose-built) | You build it |
| **Agent loop** | Built-in (ReAct-style) | Built-in (ReAct) | You build it |
| **MCP support** | First-class (stdio + SSE + OAuth) | Yes (SSE + stdio) | You build it |
| **Custom tools** | `.opencode/tools/` (TS→shell out to Python) | `@function_tool` (native Python) | Direct Python |
| **Skills / workflows** | SKILL.md system (on-demand loading) | None (hardcoded prompts) | You build it |
| **Custom agents** | Config/markdown (per-agent model, tools, prompts) | Agent-as-tool composition | You build it |
| **Multi-model LLM** | 75+ providers (per-agent model selection) | 300+ models via LiteLLM | Via litellm |
| **Python ecosystem** | Shell out from TS tools | Native (Bleak, Scapy, pyFlipper) | Native |
| **Plugin hooks** | 25+ lifecycle hooks (audit, permissions, etc.) | Guardrails + HITL | You build it |
| **Demo UX** | Polished TUI out of the box | Raw terminal output | You build it |
| **Non-interactive mode** | Yes (`opencode "prompt"`) | Yes (`cai --prompt "..."`) | You build it |
| **Community** | 111K stars, 776 contributors, 2.5M users | ~7.5K stars, niche | N/A |
| **License** | MIT | Non-commercial research | N/A |
| **Hackathon fit** | Excellent (config-only extension) | Good (some learning curve) | Fair (build everything) |
| **Time to first demo** | ~1-2 days | ~2-3 days | ~3-4 days |

**Winner: OpenCode.** Best ratio of infrastructure-for-free to custom-code-required. MIT license. Demo-ready TUI. Config-only extension model means all development effort goes into the actual hardware tools and attack workflows — not plumbing.

**Sources:**
- [OpenCode GitHub](https://github.com/sst/opencode) | [OpenCode Docs](https://opencode.ai/)
- [CAI GitHub](https://github.com/aliasrobotics/cai) | [CAI Docs](https://aliasrobotics.github.io/cai/)
- [OpenCode Skills Docs](https://opencode.ai/docs/skills/) | [OpenCode MCP Docs](https://opencode.ai/docs/mcp-servers/)
- [OpenCode Custom Tools Docs](https://opencode.ai/docs/custom-tools/) | [OpenCode Agents Docs](https://opencode.ai/docs/agents/)
- [OpenCode Plugins Docs](https://opencode.ai/docs/plugins/)
