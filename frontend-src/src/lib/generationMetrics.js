// Request throughput includes prompt processing and waiting. It is not decode speed.
function positive(value) {
  const number = Number(value);
  return Number.isFinite(number) && number > 0 ? number : null;
}

function rate(value) {
  const number = positive(value);
  if (number === null) return "Unavailable";
  if (number < 0.01) return "<0.01 tok/s";
  return number.toFixed(number < 1 ? 2 : 1) + " tok/s";
}

function seconds(value) {
  const number = positive(value);
  if (number === null) return "Unavailable";
  return number < 0.01 ? "<0.01 s" : number.toFixed(2) + " s";
}

export function formatGenerationMetrics(metrics) {
  const source = metrics?.tokenCountSource === "exact" ? "exact" : "estimated";
  const outputTokens = positive(metrics?.outputTokens);
  const throughput = rate(metrics?.tokensPerSecond);
  return {
    tokensPerSecond: throughput === "Unavailable" ? throughput : throughput + " (" + source + ")",
    decodeSpeed: rate(metrics?.lastDecodeTokensPerSecond),
    firstToken: seconds(metrics?.lastTimeToFirstTokenSeconds),
    promptTime: seconds(metrics?.lastPromptSeconds),
    requestTime: seconds(metrics?.lastGenerationSeconds),
    outputTokens: outputTokens === null ? "Unavailable" : (source === "estimated" ? "~" : "") + outputTokens.toLocaleString(),
  };
}
