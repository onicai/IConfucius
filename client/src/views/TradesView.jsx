import { getWalletTrades } from "../api";
import { useFetch } from "../hooks";
import { fmtSats } from "../utils";
import LoadingQuote from "../components/LoadingQuote";

const Spinner = ({ className = "" }) => (
  <span className={`inline-block w-5 h-5 border-2 border-border border-t-accent rounded-full animate-spin align-middle ${className}`} />
);

function fmtTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function TradeCard({ trade, btcUsd }) {
  const action = (trade.action || "").toUpperCase();
  const isBuy = action === "BUY";
  const isSell = action === "SELL";

  const tagColor = isBuy ? "bg-green-dim text-green border-green/30"
    : isSell ? "bg-red-dim text-red border-red/30"
    : "bg-accent-dim text-accent border-accent/30";

  const bots = (trade.bots || []).join(", ");

  let detail = "";
  if (isBuy && trade.amount_sats) {
    detail = fmtSats(trade.amount_sats, btcUsd);
    if (trade.est_tokens) detail += ` → ~${trade.est_tokens.toLocaleString()} tokens`;
  } else if (isSell) {
    if (trade.tokens_sold === "all") detail = "all tokens";
    else if (trade.tokens_sold) detail = `${Number(trade.tokens_sold).toLocaleString()} tokens`;
    if (trade.est_sats_received) detail += ` → ~${fmtSats(trade.est_sats_received, btcUsd)}`;
  }

  return (
    <div className="bg-surface border border-border rounded-xl p-3.5 hover:border-border/80 transition-colors">
      <div className="flex items-center gap-2 flex-wrap">
        <span className={`shrink-0 px-1.5 py-0.5 rounded text-[0.6rem] font-bold border ${tagColor}`}>
          {action || "TRADE"}
        </span>
        <a href={`https://odin.fun/token/${trade.token_id}`} target="_blank" rel="noopener noreferrer"
          className="text-sm font-semibold text-accent hover:underline">
          {trade.ticker || trade.token_id}
        </a>
        {detail && <span className="text-xs text-dim">{detail}</span>}
        <span className="ml-auto text-[0.65rem] text-dim tabular-nums">{fmtTime(trade.ts)}</span>
      </div>
      <div className="flex items-center gap-3 mt-1.5 text-[0.7rem] text-dim">
        {bots && <span>Bot: <span className="text-text">{bots}</span></span>}
        {trade.price_sats != null && <span>Price: <span className="text-text tabular-nums">{trade.price_sats.toLocaleString()} sats</span></span>}
      </div>
    </div>
  );
}

export default function TradesView({ btcUsd, refreshKey = 0 }) {
  const { data, loading, error, refetch } = useFetch(
    () => getWalletTrades(),
    [refreshKey], { cacheKey: "wallet_trades" },
  );
  const trades = data?.trades || [];

  if (loading && !data) return <LoadingQuote message="Reviewing your trade scrolls..." />;

  return (
    <>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-base font-semibold">Trade History</h3>
        <button onClick={refetch} disabled={loading}
          className="px-3 py-1.5 rounded-lg text-xs bg-surface border border-border text-dim hover:text-text hover:bg-surface-hover transition-colors cursor-pointer disabled:opacity-50">
          {loading ? <><Spinner className="w-3 h-3 mr-1" /> Refreshing...</> : "Refresh"}
        </button>
      </div>

      {error && <div className="bg-red-dim border border-red rounded-xl px-4 py-3 mb-4 text-sm text-red">{error}</div>}

      {trades.length === 0 && !loading ? (
        <div className="text-center py-12 text-dim text-sm">
          <div className="text-2xl mb-2 opacity-30">&#8709;</div>
          No trades yet. Use Chat to execute trades.
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {trades.map((t, i) => (
            <TradeCard key={i} trade={t} btcUsd={btcUsd} />
          ))}
        </div>
      )}
    </>
  );
}
