import { useState, useMemo } from "react";
import { getTokens } from "../api";
import { useFetch } from "../hooks";
import { fmtUsd, fmtNumber, fmtSatsCompact, fmtAge, fmtBtc, pctChange } from "../utils";

const API_SORT_KEYS = new Set(["created_time", "marketcap", "power_holder_count", "volume_24"]);
const ICONFUCIUS_ID = "29m8";

const COLUMNS = [
  { key: "ticker",             label: "TOKEN",   align: "left" },
  { key: "created_time",       label: "AGE",     align: "left" },
  { key: "marketcap",          label: "MKT CAP", align: "right" },
  { key: "power_holder_count", label: "HOLDERS", align: "right" },
  { key: "pct_5m",             label: "5M",      align: "right" },
  { key: "pct_1h",             label: "1H",      align: "right" },
  { key: "pct_6h",             label: "6H",      align: "right" },
  { key: "pct_24h",            label: "24H",     align: "right" },
  { key: "volume_24",          label: "24H VOL", align: "right" },
];

function apiSortParam(sort) {
  if (API_SORT_KEYS.has(sort.key)) return `${sort.key}:${sort.dir}`;
  return "volume:desc";
}

function PctCell({ pct }) {
  const cls = pct > 0 ? "text-green" : pct < 0 ? "text-red" : "text-dim";
  return (
    <td className="px-3 py-3 text-right tabular-nums whitespace-nowrap">
      <span className={cls}>
        {pct != null ? `${pct >= 0 ? "+" : ""}${pct.toFixed(1)}%` : "\u2014"}
      </span>
    </td>
  );
}

function TokenRow({ t, btcUsd }) {
  const mcapSats = t.marketcap != null ? t.marketcap / 1e3 : null;
  const priceSats = t.price != null ? t.price / 1e3 : null;
  const volSats = t.volume_24 != null ? t.volume_24 / 1e3 : null;
  return (
    <tr className="border-b border-border last:border-b-0 transition-colors hover:bg-surface-hover">
      {/* TOKEN */}
      <td className="px-3 py-3 whitespace-nowrap">
        <div className="flex items-center gap-2">
          <img
            src={`/api/odin/token/${t.id}/image`}
            className="w-8 h-8 rounded-full object-cover shrink-0 bg-border"
            alt=""
            onError={(e) => { e.target.style.display = "none"; }}
          />
          <a href={`https://odin.fun/token/${t.id}`} target="_blank" rel="noopener noreferrer">
            <span className="font-semibold text-text">{t.ticker || t.name}</span>
            {t.bonded && <span className="ml-1.5 inline-block px-1.5 py-0.5 rounded-full text-[0.6rem] font-semibold bg-green-dim text-green align-middle">Bonded</span>}
            {t.twitter_verified && <span className="ml-1 inline-block px-1.5 py-0.5 rounded-full text-[0.6rem] font-semibold bg-accent-dim text-accent align-middle">Verified</span>}
          </a>
        </div>
      </td>
      {/* AGE */}
      <td className="px-3 py-3 whitespace-nowrap text-dim">
        {t.created_time ? fmtAge(t.created_time) : "\u2014"}
      </td>
      {/* MKT CAP */}
      <td className="px-3 py-3 text-right whitespace-nowrap">
        <div className="font-semibold tabular-nums">{mcapSats != null ? fmtUsd(mcapSats, btcUsd) : "\u2014"}</div>
        <div className="text-dim text-xs tabular-nums">{priceSats != null ? fmtSatsCompact(priceSats) : ""}</div>
      </td>
      {/* HOLDERS */}
      <td className="px-3 py-3 text-right whitespace-nowrap">
        <div className="font-semibold tabular-nums">{t.power_holder_count != null ? fmtNumber(t.power_holder_count) : "\u2014"}</div>
        <div className="text-dim text-xs tabular-nums">{t.holder_count != null ? fmtNumber(t.holder_count) : ""}</div>
      </td>
      {/* 5M / 1H / 6H / 24H */}
      <PctCell pct={t.pct_5m} />
      <PctCell pct={t.pct_1h} />
      <PctCell pct={t.pct_6h} />
      <PctCell pct={t.pct_24h} />
      {/* 24H VOL */}
      <td className="px-3 py-3 text-right whitespace-nowrap">
        <div className="font-semibold tabular-nums">{volSats != null ? fmtBtc(volSats) : "\u2014"}</div>
        <div className="text-dim text-xs tabular-nums">{volSats != null ? fmtUsd(volSats, btcUsd) : ""}</div>
      </td>
      <td />
    </tr>
  );
}

export default function TokensView({ btcUsd }) {
  const [sort, setSort] = useState({ key: "pct_24h", dir: "desc" });
  const [collapsed, setCollapsed] = useState(true);

  const apiSort = apiSortParam(sort);
  const { data, loading, error, refetch } = useFetch(
    () => getTokens({ sort: apiSort, limit: 100 }),
    [apiSort],
  );

  const enriched = useMemo(() => {
    const tokens = data?.data || [];
    return tokens.map((t) => ({
      ...t,
      pct_5m: pctChange(t.price, t.price_5m),
      pct_1h: pctChange(t.price, t.price_1h),
      pct_6h: pctChange(t.price, t.price_6h),
      pct_24h: pctChange(t.price, t.price_1d),
    }));
  }, [data]);

  const sorted = useMemo(() => {
    if (API_SORT_KEYS.has(sort.key)) return enriched;
    const arr = [...enriched];
    const dir = sort.dir === "desc" ? -1 : 1;
    arr.sort((a, b) => {
      const av = a[sort.key] ?? -Infinity;
      const bv = b[sort.key] ?? -Infinity;
      if (sort.key === "ticker") return dir * String(av).localeCompare(String(bv));
      return dir * (av - bv);
    });
    return arr;
  }, [enriched, sort]);

  const segments = useMemo(() => {
    const idx = sorted.findIndex((t) => t.id === ICONFUCIUS_ID);
    if (idx < 0 || idx < 7) return { top: sorted, hidden: [], pinned: null, rest: [] };
    return {
      top:    sorted.slice(0, 5),
      hidden: sorted.slice(5, idx),
      pinned: sorted[idx],
      rest:   sorted.slice(idx + 1),
    };
  }, [sorted]);

  function handleSort(key) {
    setCollapsed(true);
    setSort((prev) =>
      prev.key === key
        ? { key, dir: prev.dir === "desc" ? "asc" : "desc" }
        : { key, dir: "desc" },
    );
  }

  return (
    <>
      {error && <div className="bg-red-dim border border-red rounded-[10px] px-4 py-3 mb-4 text-sm text-red">{error}</div>}

      {loading && !sorted.length ? (
        <div className="text-center py-16 text-dim">
          <span className="inline-block w-5 h-5 border-2 border-border border-t-accent rounded-full animate-spin mr-2 align-middle" />
          Loading tokens...
        </div>
      ) : (
        <div className="bg-surface border border-border rounded-[10px] overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr>
                {COLUMNS.map((col) => {
                  const isActive = sort.key === col.key;
                  const arrow = isActive ? (sort.dir === "desc" ? "\u2193" : "\u2191") : "\u2195";
                  return (
                    <th
                      key={col.key}
                      className={`${col.align === "right" ? "text-right" : "text-left"} px-3 py-3 font-semibold text-xs uppercase tracking-wide text-dim border-b border-border whitespace-nowrap cursor-pointer select-none hover:text-text transition-colors`}
                      onClick={() => handleSort(col.key)}
                    >
                      {col.label}{" "}
                      <span className={isActive ? "text-accent" : "text-dim/50"}>{arrow}</span>
                    </th>
                  );
                })}
                <th className="px-3 py-3 text-right border-b border-border">
                  <button
                    className="inline-flex items-center justify-center w-7 h-7 rounded-lg cursor-pointer transition-all text-dim hover:text-text hover:bg-surface-hover disabled:opacity-50"
                    onClick={refetch}
                    disabled={loading}
                    title="Refresh"
                  >
                    <svg className={loading ? "animate-spin" : ""} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
                    </svg>
                  </button>
                </th>
              </tr>
            </thead>
            <tbody>
              {segments.top.map((t) => <TokenRow key={t.id} t={t} btcUsd={btcUsd} />)}
              {segments.pinned && (
                <>
                  <tr className="border-b border-border cursor-pointer hover:bg-surface-hover transition-colors"
                      onClick={() => setCollapsed((c) => !c)}>
                    <td colSpan={COLUMNS.length + 1} className="px-3 py-2 text-center text-xs text-dim">
                      {collapsed
                        ? `\u25B6 ${segments.hidden.length} more tokens...`
                        : `\u25BC ${segments.hidden.length} more tokens`}
                    </td>
                  </tr>
                  {!collapsed && segments.hidden.map((t) => <TokenRow key={t.id} t={t} btcUsd={btcUsd} />)}
                  <TokenRow key={segments.pinned.id} t={segments.pinned} btcUsd={btcUsd} />
                </>
              )}
              {segments.rest.map((t) => <TokenRow key={t.id} t={t} btcUsd={btcUsd} />)}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
