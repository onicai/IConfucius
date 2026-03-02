import { useState } from "react";
import { getTokens } from "../api";
import { useFetch } from "../hooks";
import { fmtUsd, fmtNumber } from "../utils";

const SORT_OPTIONS = [
  { value: "volume:desc", label: "Volume (24h)" },
  { value: "created_time:desc", label: "Newest" },
  { value: "holder_count:desc", label: "Holders" },
];

const tabCls = (active) =>
  `px-4 py-2 rounded-[10px] text-sm cursor-pointer transition-all border ${
    active ? "bg-surface border-border text-text" : "bg-transparent border-transparent text-dim hover:text-text hover:bg-surface"
  }`;

export default function TokensView({ btcUsd }) {
  const [sort, setSort] = useState("volume:desc");
  const { data, loading, error, refetch } = useFetch(
    () => getTokens({ sort, limit: 30 }),
    [sort],
  );
  const tokens = data?.data || [];

  return (
    <>
      <div className="flex justify-between items-center mb-4">
        <div className="flex gap-1">
          {SORT_OPTIONS.map((s) => (
            <button key={s.value} className={tabCls(sort === s.value)} onClick={() => setSort(s.value)}>
              {s.label}
            </button>
          ))}
        </div>
        <button className={tabCls(false)} onClick={refetch} disabled={loading}>
          {loading ? "..." : "Refresh"}
        </button>
      </div>

      {error && <div className="bg-red-dim border border-red rounded-[10px] px-4 py-3 mb-4 text-sm text-red">{error}</div>}

      {loading && !tokens.length ? (
        <div className="text-center py-16 text-dim">
          <span className="inline-block w-5 h-5 border-2 border-border border-t-accent rounded-full animate-spin mr-2 align-middle" />
          Loading tokens...
        </div>
      ) : (
        <div className="bg-surface border border-border rounded-[10px] overflow-hidden">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr>
                {["#", "Token", "Price", "Market Cap", "Volume (24h)", "Holders", "Status"].map((h, i) => (
                  <th key={h} className={`${i >= 2 && i <= 5 ? "text-right" : "text-left"} px-4 py-3 font-semibold text-xs uppercase tracking-wide text-dim border-b border-border whitespace-nowrap`}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tokens.map((t, i) => (
                <tr key={t.id} className="border-b border-border last:border-b-0 transition-colors hover:bg-surface-hover">
                  <td className="px-4 py-3 text-dim tabular-nums whitespace-nowrap">{i + 1}</td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <a className="text-accent hover:underline" href={`https://odin.fun/token/${t.id}`} target="_blank" rel="noopener noreferrer">
                      <span className="font-semibold text-text">{t.ticker || t.name}</span>
                    </a>
                    {t.ticker && t.name !== t.ticker && <div className="text-dim text-xs">{t.name}</div>}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums whitespace-nowrap">{t.price != null ? fmtUsd(t.price / 1e3, btcUsd) : "—"}</td>
                  <td className="px-4 py-3 text-right tabular-nums whitespace-nowrap">{t.marketcap ? fmtUsd(t.marketcap / 1e3, btcUsd) : "—"}</td>
                  <td className="px-4 py-3 text-right tabular-nums whitespace-nowrap">{t.volume_24 ? fmtUsd(t.volume_24 / 1e3, btcUsd) : "—"}</td>
                  <td className="px-4 py-3 text-right tabular-nums whitespace-nowrap">{t.holder_count ? fmtNumber(t.holder_count) : "—"}</td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    {t.bonded && <span className="inline-block px-2 py-0.5 rounded-full text-[0.7rem] font-semibold bg-green-dim text-green">Bonded</span>}{" "}
                    {t.twitter_verified && <span className="inline-block px-2 py-0.5 rounded-full text-[0.7rem] font-semibold bg-accent-dim text-accent">Verified</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
