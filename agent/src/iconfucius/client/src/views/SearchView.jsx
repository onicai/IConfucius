import { useState } from "react";
import { searchTokens, getToken } from "../api";
import { fmtUsd, fmtNumber } from "../utils";

export default function SearchView({ btcUsd }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState(null);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function handleSearch(e) {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true); setError(null); setDetail(null);
    try {
      const data = await searchTokens(query.trim());
      const raw = data?.data || data || [];
      const tokens = raw.map((r) => r.entity ? { ...r.entity, _type: r.type } : r);
      tokens.sort((a, b) => {
        const ab = a.bonded ? 1 : 0;
        const bb = b.bonded ? 1 : 0;
        if (bb !== ab) return bb - ab;
        if ((b.marketcap || 0) !== (a.marketcap || 0)) return (b.marketcap || 0) - (a.marketcap || 0);
        if ((b.holder_count || 0) !== (a.holder_count || 0)) return (b.holder_count || 0) - (a.holder_count || 0);
        const av = a.twitter_verified ? 1 : 0;
        const bv = b.twitter_verified ? 1 : 0;
        return bv - av;
      });
      setResults(tokens);
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  }

  async function handleDetail(tokenId) {
    try { setDetail(await getToken(tokenId)); }
    catch (err) { setError(err.message); }
  }

  return (
    <>
      <form onSubmit={handleSearch} className="flex gap-2 mb-5">
        <input
          autoFocus
          type="text" value={query} onChange={(e) => setQuery(e.target.value)}
          placeholder="Search by name, ticker, or token ID..."
          className="flex-1 px-3.5 py-2.5 bg-surface border border-border rounded-[10px] text-text text-sm outline-none focus:border-accent"
        />
        <button type="submit" disabled={loading}
          className="px-5 py-2.5 rounded-[10px] text-sm cursor-pointer bg-surface border border-border text-text hover:bg-surface-hover transition-colors">
          {loading ? "..." : "Search"}
        </button>
      </form>

      {error && <div className="bg-red-dim border border-red rounded-[10px] px-4 py-3 mb-4 text-sm text-red">{error}</div>}

      {detail && (
        <div className="bg-surface border border-border rounded-[10px] p-4 mb-4 cursor-pointer" onClick={() => setDetail(null)}>
          <div className="text-xs uppercase tracking-wide text-dim mb-2">Token Detail (click to close)</div>
          <pre className="text-xs text-dim whitespace-pre-wrap">{JSON.stringify(detail, null, 2)}</pre>
        </div>
      )}

      {results && Array.isArray(results) && (
        <div className="bg-surface border border-border rounded-[10px] overflow-hidden">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr>
                {["Token", "ID", "Market Cap", "Holders", "Status", ""].map((h, i) => (
                  <th key={h} className={`${i === 2 || i === 3 ? "text-right" : "text-left"} px-4 py-3 font-semibold text-xs uppercase tracking-wide text-dim border-b border-border whitespace-nowrap`}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {results.length === 0 ? (
                <tr><td colSpan={6} className="text-center py-8 text-dim">No results found</td></tr>
              ) : results.map((t) => (
                <tr key={t.id} className="border-b border-border last:border-b-0 transition-colors hover:bg-surface-hover">
                  <td className="px-4 py-3 whitespace-nowrap">
                    <span className="font-semibold text-text">{t.ticker || t.name}</span>
                    {t.ticker && t.name !== t.ticker && <div className="text-dim text-xs">{t.name}</div>}
                  </td>
                  <td className="px-4 py-3 text-dim whitespace-nowrap">{t.id}</td>
                  <td className="px-4 py-3 text-right tabular-nums whitespace-nowrap">{t.marketcap ? fmtUsd(t.marketcap / 1e3, btcUsd) : "—"}</td>
                  <td className="px-4 py-3 text-right tabular-nums whitespace-nowrap">{t.holder_count ? fmtNumber(t.holder_count) : "—"}</td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    {t.bonded && <span className="inline-block px-2 py-0.5 rounded-full text-[0.7rem] font-semibold bg-green-dim text-green">Bonded</span>}{" "}
                    {t.twitter_verified && <span className="inline-block px-2 py-0.5 rounded-full text-[0.7rem] font-semibold bg-accent-dim text-accent">Verified</span>}
                  </td>
                  <td className="px-4 py-3">
                    <button className="px-2.5 py-1 rounded-[10px] text-xs border border-transparent text-dim hover:text-text hover:bg-surface cursor-pointer" onClick={() => handleDetail(t.id)}>
                      Details
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!results && !loading && (
        <div className="text-center py-16 text-dim">Search for tokens on Odin.fun by name, ticker, or ID</div>
      )}
    </>
  );
}
