import { getTrades } from "../api";
import { useFetch } from "../hooks";
import { fmtSats, timeAgo } from "../utils";

const tabCls = "px-4 py-2 rounded-[10px] text-sm cursor-pointer transition-all border bg-transparent border-transparent text-dim hover:text-text hover:bg-surface";

export default function TradesView({ btcUsd }) {
  const { data, loading, error, refetch } = useFetch(() => getTrades({ limit: 30 }), []);
  const trades = data?.data || [];

  return (
    <>
      <div className="flex justify-end mb-4">
        <button className={tabCls} onClick={refetch} disabled={loading}>
          {loading ? "..." : "Refresh"}
        </button>
      </div>

      {error && <div className="bg-red-dim border border-red rounded-[10px] px-4 py-3 mb-4 text-sm text-red">{error}</div>}

      {loading && !trades.length ? (
        <div className="text-center py-16 text-dim">
          <span className="inline-block w-5 h-5 border-2 border-border border-t-accent rounded-full animate-spin mr-2 align-middle" />
          Loading trades...
        </div>
      ) : (
        <div className="bg-surface border border-border rounded-[10px] overflow-hidden">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr>
                {["Time", "Type", "Token", "Amount", "BTC Value"].map((h, i) => (
                  <th key={h} className={`${i >= 3 ? "text-right" : "text-left"} px-4 py-3 font-semibold text-xs uppercase tracking-wide text-dim border-b border-border whitespace-nowrap`}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {trades.map((t) => (
                <tr key={t.id || `${t.created_time}-${t.token_id}`} className="border-b border-border last:border-b-0 transition-colors hover:bg-surface-hover">
                  <td className="px-4 py-3 text-dim tabular-nums whitespace-nowrap">{t.created_time ? timeAgo(t.created_time) : "—"}</td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <span className={t.type === "buy" ? "text-green font-semibold" : "text-red font-semibold"}>
                      {t.type?.toUpperCase() || "—"}
                    </span>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <a className="text-accent hover:underline" href={`https://odin.fun/token/${t.token_id}`} target="_blank" rel="noopener noreferrer">
                      {t.token_ticker || t.token_id}
                    </a>
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums whitespace-nowrap">{t.token_amount ? Number(t.token_amount).toLocaleString() : "—"}</td>
                  <td className="px-4 py-3 text-right tabular-nums whitespace-nowrap">{t.btc_amount ? fmtSats(t.btc_amount, btcUsd) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
