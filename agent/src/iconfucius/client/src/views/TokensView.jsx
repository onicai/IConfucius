import { useState } from "react";
import { getTokens } from "../api";
import { useFetch } from "../hooks";
import { useI18n } from "../i18n";
import { fmtUsd, fmtNumber } from "../utils";

const tabCls = (active) =>
  `px-4 py-2 rounded-[10px] text-sm cursor-pointer transition-all border ${
    active ? "bg-surface border-border text-text" : "bg-transparent border-transparent text-dim hover:text-text hover:bg-surface"
  }`;

export default function TokensView({ btcUsd }) {
  const { t } = useI18n();
  const SORT_OPTIONS = [
    { value: "volume:desc", label: t("tokens.sort_volume") },
    { value: "created_time:desc", label: t("tokens.sort_newest") },
    { value: "holder_count:desc", label: t("tokens.sort_holders") },
  ];

  const [sort, setSort] = useState("volume:desc");
  const { data, loading, error, refetch } = useFetch(
    () => getTokens({ sort, limit: 30 }),
    [sort],
  );
  const tokens = data?.data || [];

  const headers = [
    t("tokens.col_rank"), t("tokens.col_token"), t("tokens.col_price"),
    t("tokens.col_mcap"), t("tokens.col_volume"), t("tokens.col_holders"), t("tokens.col_status"),
  ];

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
          {loading ? "..." : t("tokens.refresh")}
        </button>
      </div>

      {error && <div className="bg-red-dim border border-red rounded-[10px] px-4 py-3 mb-4 text-sm text-red">{error}</div>}

      {loading && !tokens.length ? (
        <div className="text-center py-16 text-dim">
          <span className="inline-block w-5 h-5 border-2 border-border border-t-accent rounded-full animate-spin mr-2 align-middle" />
          {t("tokens.loading")}
        </div>
      ) : (
        <div className="bg-surface border border-border rounded-[10px] overflow-hidden">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr>
                {headers.map((h, i) => (
                  <th key={h} className={`${i >= 2 && i <= 5 ? "text-right" : "text-left"} px-4 py-3 font-semibold text-xs uppercase tracking-wide text-dim border-b border-border whitespace-nowrap`}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tokens.map((tk, i) => (
                <tr key={tk.id} className="border-b border-border last:border-b-0 transition-colors hover:bg-surface-hover">
                  <td className="px-4 py-3 text-dim tabular-nums whitespace-nowrap">{i + 1}</td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <a className="text-accent hover:underline" href={`https://odin.fun/token/${tk.id}`} target="_blank" rel="noopener noreferrer">
                      <span className="font-semibold text-text">{tk.ticker || tk.name}</span>
                    </a>
                    {tk.ticker && tk.name !== tk.ticker && <div className="text-dim text-xs">{tk.name}</div>}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums whitespace-nowrap">{tk.price != null ? fmtUsd(tk.price / 1e3, btcUsd) : "—"}</td>
                  <td className="px-4 py-3 text-right tabular-nums whitespace-nowrap">{tk.marketcap != null ? fmtUsd(tk.marketcap / 1e3, btcUsd) : "—"}</td>
                  <td className="px-4 py-3 text-right tabular-nums whitespace-nowrap">{tk.volume_24 != null ? fmtUsd(tk.volume_24 / 1e3, btcUsd) : "—"}</td>
                  <td className="px-4 py-3 text-right tabular-nums whitespace-nowrap">{tk.holder_count != null ? fmtNumber(tk.holder_count) : "—"}</td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    {tk.bonded && <span className="inline-block px-2 py-0.5 rounded-full text-[0.7rem] font-semibold bg-green-dim text-green">{t("tokens.bonded")}</span>}{" "}
                    {tk.twitter_verified && <span className="inline-block px-2 py-0.5 rounded-full text-[0.7rem] font-semibold bg-accent-dim text-accent">{t("tokens.verified")}</span>}
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
