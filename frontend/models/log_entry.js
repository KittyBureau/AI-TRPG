let sequence = 0;

export function createLogEntry({
  round,
  actor,
  narrative,
  delta,
  status,
  raw,
}) {
  sequence += 1;
  return {
    id: `log_${Date.now()}_${sequence}`,
    round,
    actor,
    narrative: typeof narrative === "string" ? narrative : "",
    delta: delta || null,
    status: status || "unknown",
    raw: raw || null,
  };
}
