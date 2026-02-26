# PRD Review: Autonomous Cyber-Physical Red Team Agent ("Bellum")

**Reviewer:** Claude (automated review)
**Date:** 2026-02-26
**PRD Version:** Draft, 2026-02-26

---

## Executive Summary

This is an ambitious, well-structured PRD for building an autonomous AI agent that bridges digital and physical-layer offensive security. The vision is compelling and the competitive differentiation (no one else combines autonomous AI reasoning + physical-layer attack tools) is genuine. However, the scope is **extremely aggressive for a 10-day timeline**, and several architectural and practical decisions need tightening before implementation begins.

**Overall assessment:** Strong vision, needs scope reduction and sharper prioritization to ship for March 7.

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

---

## 2. Critical Concerns

### 2.1 Scope vs. Timeline Mismatch

The PRD specifies **30+ distinct tools** across three categories, three LLM provider integrations, a ReAct agent loop, a reporting engine, mock implementations, and hardware integration — all in 10 calendar days with one developer.

**Phase 1 alone** (Feb 27 - Mar 3, ~5 days) includes:
- Project scaffolding
- ReAct agent loop + tool dispatch
- 3 LLM backend integrations
- Mock tools for all physical tools
- Real implementations for all research tools
- Real implementations for all digital tools
- End-to-end testing
- Logging/replay system

This is too much. A single developer cannot ship ~15 real tool integrations + 12 mock tool integrations + an agent framework + 3 LLM backends in 5 days.

**Recommendation:** Ruthlessly cut to a "critical path" for the demo:
- **1 LLM backend** (MiniMax M2.5, the recommended one). Add others only if time permits.
- **5-7 tools maximum** for Phase 1: `ble_scan`, `ble_enumerate`, `ble_write_char`, `web_search`, `nmap_scan`, `http_request`, `code_execute`. These are sufficient for the demo attack chain.
- Defer `subghz_*`, `ir_*`, `badusb_*`, `gpio_*`, `wifi_deauth`, `wifi_capture`, `shodan_*`, `ssh_connect`, `fcc_lookup`, `firmware_analyze` to stretch goals.
- Skip the replay/logging system until after the hackathon.

### 2.2 LLM Provider Strategy is Risky

The PRD relies entirely on "unaligned/weakly-aligned" Chinese LLM providers (MiniMax, Kimi, GLM-5) with a fallback to local Ollama models. This introduces multiple risks:

1. **API reliability:** These are smaller providers compared to OpenAI/Anthropic. Downtime or rate limits during the hackathon could be fatal.
2. **Tool-calling quality:** While MiniMax benchmarks well on tool calling, real-world performance with 30+ tools and multi-step chains is unproven. The gap between benchmark performance and production reliability can be large.
3. **Latency:** Chinese API providers may have high latency from the US. A 5-second round-trip per reasoning step means a 10-step attack chain takes nearly a minute of just LLM time.
4. **Ollama fallback is not free:** Running Qwen2.5 or DeepSeek-V3 locally on a MacBook requires significant RAM and will be slow. This is not a reliable fallback for a live demo.

**Recommendation:**
- Test all three providers against actual offensive security prompts **before Feb 28** (the PRD's own deadline for framework choice).
- Have a concrete, tested fallback. Consider using Claude or GPT-4 with carefully crafted prompts that frame actions as "security evaluation" rather than "attack" — many aligned models will cooperate with authorized pentest framing.
- Consider a hybrid approach: use an aligned model for planning/research (where refusals are less likely) and an unaligned model only for exploit execution steps.

### 2.3 No Error Handling or Recovery Strategy

The ReAct loop pseudocode (Section 4.5) shows a simple `while not done` loop but doesn't address:
- What happens when a tool call fails (e.g., BLE device out of range, nmap timeout)?
- How the agent decides when to give up on an attack vector and try another?
- How to prevent the agent from getting stuck in loops (the risk assessment mentions this but the architecture doesn't address it).
- Context window management — a 10+ step attack chain with tool outputs could easily exceed token limits.

**Recommendation:** Add to the architecture:
- Tool call retry logic with exponential backoff
- A "frustration counter" — after N failed attempts on one vector, the agent should pivot
- Max iteration cap (mentioned in risk assessment, but should be in the architecture)
- Observation summarization to manage context window — after each phase, compress findings into a structured summary

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

## 3. Architectural Feedback

### 3.1 Agent Framework Choice

The PRD recommends a custom ReAct loop with MCP tool integration, and this is the right call for a hackathon. However:

- **MCP may be overkill.** MCP (Model Context Protocol) is designed for LLM-to-tool server communication. For a single-developer hackathon project, direct Python function calls with a simple tool registry (dict mapping tool names to functions) is faster to build and debug. MCP adds a server layer that's unnecessary when everything runs on one machine.
- The existing `flipperzero-mcp` is useful as a reference implementation but could also be called directly via its Python API without the MCP protocol overhead.

**Recommendation:** Start with a simple Python dict-based tool registry. Each tool is an async function with a typed input/output schema. If MCP is needed later for interoperability, the function-based tools can be wrapped in MCP handlers with minimal effort.

### 3.2 Repo Structure is Over-Engineered for Day 1

The proposed structure (Section 8) has 30+ files across deeply nested directories. For a hackathon sprint:

**Recommendation:** Start flat, refactor later:
```
bellum/
├── pyproject.toml
├── bellum/
│   ├── agent.py          # ReAct loop + tool dispatch (start here)
│   ├── llm.py            # Single LLM backend
│   ├── tools.py          # All tool implementations in one file
│   └── report.py         # Report generation
├── tests/
│   └── test_agent.py
└── scripts/
    └── run.py
```
Split files when they exceed ~300 lines or when you need to work on them in parallel.

### 3.3 Missing: Configuration and Environment Setup

The PRD lists software dependencies (Section 7) but doesn't specify:
- How to configure API keys and endpoints
- How to specify the Flipper Zero serial port
- How to switch between mock and real tool implementations
- How to select the LLM provider

**Recommendation:** Add a `config.py` or `.env`-based configuration system. A simple approach:
```python
# .env
LLM_PROVIDER=minimax
LLM_API_KEY=...
FLIPPER_SERIAL_PORT=/dev/tty.usbmodemXXXX
SHODAN_API_KEY=...
USE_MOCK_PHYSICAL_TOOLS=true
```

---

## 4. Timeline Recommendations

Given the March 7 hackathon deadline and March 6 a16z deadline, here's a tighter schedule:

### Phase 1A: Skeleton (Feb 27-28) — 2 days
- Project scaffolding (pyproject.toml, basic structure)
- Simple ReAct agent loop with tool dispatch
- Single LLM backend (MiniMax M2.5)
- 3 tools: `ble_scan` (mock), `web_search` (real), `code_execute` (real)
- Verify the agent can reason and chain tools end-to-end

### Phase 1B: Core Tools (Mar 1-3) — 3 days
- Add remaining critical tools: `ble_enumerate`, `ble_write_char`, `nmap_scan`, `http_request`
- Mock implementations for all physical tools
- Basic report generation
- Test against own BLE devices (AirPods, smart bulbs, etc.)

### Phase 2: Hardware (Mar 4-5) — 2 days
- Replace BLE mocks with real Bleak implementation
- Flipper Zero serial integration (Sub-GHz scan only — don't try to integrate everything)
- End-to-end test with real hardware

### Phase 3: Polish (Mar 6) — 1 day
- Record demo video
- Write README for a16z application
- Submit a16z application
- Bug fixes and hardening

### Phase 4: Hackathon (Mar 7-8)
- Deploy against hackathon targets
- Extended demo recording
- Iterate based on real-world results

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
| 13 | Open question #1 deadline is Feb 28 — that's in 2 days | Decide now: custom ReAct loop (the PRD already recommends this) |

---

## 6. Summary of Recommendations

1. **Cut scope aggressively.** Target 5-7 tools for Phase 1, not 30+. One LLM backend, not three.
2. **Test LLM providers immediately.** The entire project depends on unaligned models cooperating with offensive security tool use. Verify this before writing any framework code.
3. **Start with a flat, simple architecture.** Dict-based tool registry, single-file implementations, refactor only when needed.
4. **Add error handling to the agent loop.** Retry logic, frustration counters, context summarization, and max iteration caps.
5. **Specify the `code_execute` sandbox.** This is the highest security risk in the agent itself.
6. **Prepare a no-hardware fallback.** BLE via laptop Bleak works without Flipper Zero. If the Flipper arrives late or doesn't cooperate, the demo still works.
7. **Align repo naming.** "Bellum" vs "FlipperAgent" — pick one.
8. **Resolve open questions now.** Most of them have obvious answers already implicit in the PRD.
