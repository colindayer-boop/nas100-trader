---
type: incident
date: 2026-07-05
severity: high
status: resolved
tags: [incident, postmortem]
---
# Timezone bar mislabel

**Impact:** Asian high/low and ORB bars computed on mis-timestamped bars (~2% off), suppressing signals.\n\n**Root cause:** MT5 bar timestamps are server time (UTC+2/3), treated as UTC -> ~3h shift.\n\n**Fix:** detect server-UTC offset from a live tick; rebase bars to true UTC then ET. Verified 9:00 ET + Asian bars present (`diag_live.py`).\n\n**Lesson:** never assume a broker feed is UTC.

Back: [[08-Incidents-and-Postmortems/_index|Incidents]]
