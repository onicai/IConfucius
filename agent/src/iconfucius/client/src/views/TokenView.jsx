import { useState } from "react";
import TokensView from "./TokensView";
import SearchView from "./SearchView";
import { fmtSats } from "../utils";

const TABS = ["All Tokens", "My Tokens", "Search"];

const tabCls = (active) =>
  `px-4 py-2 rounded-[10px] text-sm cursor-pointer transition-all border ${
    active ? "bg-surface border-border text-text" : "bg-transparent border-transparent text-dim hover:text-text hover:bg-surface"
  }`;

function MyTokens({ tokens, btcUsd }) {
  if (!tokens || Object.keys(tokens).length === 0) {
    return <div className="text-center py-16 text-dim">No token holdings yet. Use Chat or Bots to buy tokens.</div>;
  }
  const sorted = Object.entries(tokens).sort((a, b) => b[1].value_sats - a[1].value_sats);

  return (
    <div className="bg-surface border border-border rounded-[10px] overflow-hidden">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr>
            {["Token", "Balance", "Value"].map((h, i) => (
              <th key={h} className={`${i > 0 ? "text-right" : "text-left"} px-4 py-3 font-semibold text-xs uppercase tracking-wide text-dim border-b border-border whitespace-nowrap`}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map(([ticker, t]) => (
            <tr key={t.id || ticker} className="border-b border-border last:border-b-0 transition-colors hover:bg-surface-hover">
              <td className="px-4 py-3 whitespace-nowrap">
                <div className="flex items-center gap-2">
                  <img src={`/api/odin/token/${t.id}/image`}
                    className="w-6 h-6 rounded-full object-cover shrink-0 bg-border"
                    alt="" onError={(e) => { e.target.style.display = "none"; }} />
                  <a className="text-accent hover:underline font-semibold" href={`https://odin.fun/token/${t.id}`} target="_blank" rel="noopener noreferrer">
                    {ticker}
                  </a>
                </div>
              </td>
              <td className="px-4 py-3 text-right tabular-nums whitespace-nowrap">
                {typeof t.balance === "number" ? t.balance.toLocaleString(undefined, { maximumFractionDigits: 2 }) : t.balance}
              </td>
              <td className="px-4 py-3 text-right tabular-nums whitespace-nowrap">
                {t.value_sats > 0 ? fmtSats(t.value_sats, btcUsd) : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function TokenView({ btcUsd, balanceData, refreshKey }) {
  const [tab, setTab] = useState("All Tokens");

  return (
    <>
      <div className="flex gap-1 mb-4">
        {TABS.map((t) => (
          <button key={t} className={tabCls(tab === t)} onClick={() => setTab(t)}>
            {t}
          </button>
        ))}
      </div>
      {tab === "My Tokens" && <MyTokens tokens={balanceData?.totals?.tokens} btcUsd={btcUsd} />}
      {tab === "All Tokens" && <TokensView btcUsd={btcUsd} />}
      {tab === "Search" && <SearchView btcUsd={btcUsd} />}
    </>
  );
}
