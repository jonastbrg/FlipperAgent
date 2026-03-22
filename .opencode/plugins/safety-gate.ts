import type { Plugin } from "@opencode-ai/plugin"

export default (async (ctx) => {
  return {
    'tool.call': async (tool, output) => {
      // HIGH-risk tools: log warning to stderr
      // Synced with core/risk.py TOOL_RISK_MAP HIGH entries
      const HIGH_RISK = [
        'badusb_execute', 'badusb_workflow',
        'ble_write_char',
        'marauder_beacon_spam', 'marauder_deauth', 'marauder_exec', 'marauder_probe_flood',
        'nfc_emulate',
        'rfid_emulate', 'rfid_write',
        'subghz_tx', 'subghz_tx_from_file',
      ]

      const toolName = tool.name.replace(/^flipper_/, '')
      if (HIGH_RISK.includes(toolName)) {
        console.error(`[SAFETY] HIGH-risk tool invoked: ${tool.name}`)
      }
    }
  }
}) satisfies Plugin
