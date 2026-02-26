import { getWalletTrades } from "../api";
import { useFetch } from "../hooks";

const Spinner = ({ className = "" }) => (
  <span className={`inline-block w-5 h-5 border-2 border-border border-t-accent rounded-full animate-spin align-middle ${className}`} />
);

function TradeEntry({ heading, body }) {
  const isBuy = /\bbuy\b/i.test(heading) || /\bbought\b/i.test(heading);
  const isSell = /\bsell\b/i.test(heading) || /\bsold\b/i.test(heading);
  const isFund = /\bfund\b/i.test(heading) || /\bdeposit\b/i.test(heading);
  const isWithdraw = /\bwithdraw\b/i.test(heading);

  const tagColor = isBuy ? "bg-green-dim text-green border-green/30"
    : isSell ? "bg-red-dim text-red border-red/30"
    : isFund ? "bg-accent-dim text-accent border-accent/30"
    : isWithdraw ? "bg-accent-dim text-accent border-accent/30"
    : "bg-surface-hover text-dim border-border";

  const tagLabel = isBuy ? "BUY" : isSell ? "SELL" : isFund ? "FUND" : isWithdraw ? "WITHDRAW" : "ACTION";

  return (
    <div className="bg-surface border border-border rounded-xl p-3.5 hover:border-border/80 transition-colors">
      <div className="flex items-start gap-2 mb-1">
        <span className={`shrink-0 px-1.5 py-0.5 rounded text-[0.6rem] font-bold border ${tagColor}`}>
          {tagLabel}
        </span>
        <span className="text-sm font-semibold leading-snug">{heading}</span>
      </div>
      {body && (
        <div className="text-xs text-dim leading-relaxed whitespace-pre-wrap mt-1.5 pl-[calc(theme(spacing.1.5)+theme(spacing.2)+3ch)]">
          {body}
        </div>
      )}
    </div>
  );
}

export default function TradesView({ btcUsd, refreshKey = 0 }) {
  const { data, loading, error, refetch } = useFetch(
    () => getWalletTrades(),
    [refreshKey], { cacheKey: "wallet_trades" },
  );
  const trades = data?.trades || [];

  if (loading && !data) return <div className="text-center py-16 text-dim"><Spinner className="mr-2" /> Loading trade history...</div>;

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
            <TradeEntry key={i} heading={t.heading} body={t.body} />
          ))}
        </div>
      )}
    </>
  );
}
