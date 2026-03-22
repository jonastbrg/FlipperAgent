import type { Plugin } from "@opencode-ai/plugin"
import { appendFileSync, mkdirSync, existsSync } from "fs"
import { join } from "path"

export default (async (ctx) => {
  const findingsDir = join(process.cwd(), "findings")
  const logPath = join(findingsDir, "tool_calls.jsonl")

  // Ensure findings directory exists
  if (!existsSync(findingsDir)) {
    mkdirSync(findingsDir, { recursive: true })
  }

  return {
    'tool.call': async (tool, output) => {
      const entry = {
        timestamp: new Date().toISOString(),
        tool: tool.name,
        parameters: tool.parameters ?? {},
        success: output?.error == null,
        error: output?.error ?? null,
        duration_ms: output?.duration_ms ?? null
      }

      try {
        appendFileSync(logPath, JSON.stringify(entry) + "\n", "utf-8")
      } catch (err) {
        // If we can't write the log, emit to stderr but don't crash the agent
        console.error(`[ENGAGEMENT-LOGGER] Failed to write audit log: ${err}`)
      }
    }
  }
}) satisfies Plugin
