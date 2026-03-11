export function fmtSats(sats, btcUsd) {
  const s = Number(sats).toLocaleString();
  if (!btcUsd) return `${s} sats`;
  const usd = (sats / 1e8) * btcUsd;
  return `${s} sats ($${usd.toFixed(2)})`;
}

export function fmtUsd(sats, btcUsd) {
  if (!btcUsd) return "—";
  const usd = (sats / 1e8) * btcUsd;
  if (usd >= 1e6) return `$${(usd / 1e6).toFixed(2)}M`;
  if (usd >= 1e3) return `$${(usd / 1e3).toFixed(1)}K`;
  if (usd >= 0.01) return `$${usd.toFixed(2)}`;
  if (usd >= 0.0001) return `$${usd.toFixed(4)}`;
  return "<$0.0001";
}

export function fmtNumber(n) {
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}K`;
  return n.toLocaleString();
}

export function fmtChange(pct) {
  if (pct == null) return "—";
  const sign = pct >= 0 ? "+" : "";
  return `${sign}${pct.toFixed(1)}%`;
}

export function timeAgo(isoString) {
  const now = Date.now();
  const then = new Date(isoString).getTime();
  const diffMs = now - then;
  const mins = Math.floor(diffMs / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

export function fmtSatsCompact(sats) {
  if (sats >= 1e6) return `${(sats / 1e6).toFixed(1)}M sats`;
  if (sats >= 1e3) return `${(sats / 1e3).toFixed(1)}K sats`;
  return `${Math.round(sats).toLocaleString()} sats`;
}

export function fmtAge(isoString) {
  const diffMs = Date.now() - new Date(isoString).getTime();
  const days = Math.floor(diffMs / 86400000);
  if (days < 1) return "<1d";
  if (days < 30) return `${days}d`;
  const months = Math.floor(days / 30);
  if (months < 12) return `${months}mo`;
  const years = Math.floor(months / 12);
  return `${years}y`;
}

export function fmtBtc(sats) {
  const btc = sats / 1e8;
  if (btc >= 0.01) return `${btc.toFixed(2)} BTC`;
  return `${btc.toFixed(4)} BTC`;
}

export function pctChange(current, previous) {
  if (!previous || previous === 0) return null;
  return ((current - previous) / previous) * 100;
}
