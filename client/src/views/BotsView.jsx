import { getWalletBalances } from "../api";
import { useFetch } from "../hooks";
import { fmtSats, fmtUsd } from "../utils";

const Spinner = ({ className = "" }) => (
  <span className={`inline-block w-5 h-5 border-2 border-border border-t-accent rounded-full animate-spin align-middle ${className}`} />
);

function TokenBadge({ ticker, tokenId, balance, valueSats, btcUsd }) {
  return (
    <a href={`https://odin.fun/token/${tokenId}`} target="_blank" rel="noopener noreferrer"
      className="inline-flex items-center gap-1.5 px-2.5 py-1.5 bg-bg border border-border rounded-lg text-xs hover:border-accent/40 transition-colors no-underline">
      <span className="text-accent font-semibold">{ticker}</span>
      <span className="text-dim">{typeof balance === "number" ? balance.toLocaleString(undefined, { maximumFractionDigits: 2 }) : balance}</span>
      {valueSats > 0 && <span className="text-dim/70">({fmtSats(valueSats, btcUsd)})</span>}
    </a>
  );
}

function BotCard({ bot, btcUsd }) {
  const hasAccount = bot.has_odin_account;

  return (
    <div className="bg-surface border border-border rounded-[10px] p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <h4 className="text-sm font-bold">{bot.name}</h4>
          {hasAccount ? (
            <span className="px-1.5 py-0.5 text-[0.65rem] font-medium rounded bg-green-dim text-green border border-green/30">Active</span>
          ) : (
            <span className="px-1.5 py-0.5 text-[0.65rem] font-medium rounded bg-surface-hover text-dim border border-border">Not registered</span>
          )}
        </div>
        {bot.odin_sats > 0 && (
          <div className="text-right">
            <div className="text-sm font-bold tabular-nums">{fmtSats(bot.odin_sats, btcUsd)}</div>
            <div className="text-[0.65rem] text-dim">Odin balance</div>
          </div>
        )}
      </div>

      {bot.principal && (
        <div className="text-[0.65rem] text-dim font-mono break-all mb-3 bg-bg rounded px-2 py-1 border border-border">
          {bot.principal}
        </div>
      )}

      {bot.tokens && bot.tokens.length > 0 ? (
        <div>
          <div className="text-[0.7rem] text-dim mb-1.5 font-medium">Token Holdings</div>
          <div className="flex flex-wrap gap-1.5">
            {bot.tokens.map((t) => (
              <TokenBadge key={t.id || t.ticker} ticker={t.ticker} tokenId={t.id} balance={t.balance} valueSats={t.value_sats} btcUsd={btcUsd} />
            ))}
          </div>
        </div>
      ) : hasAccount ? (
        <div className="text-xs text-dim">No token holdings</div>
      ) : (
        <div className="text-xs text-dim">
          Register this bot on Odin.fun via Chat: <code className="text-accent">"register bot-1 on odin"</code>
        </div>
      )}
    </div>
  );
}

function PortfolioSummary({ totals, btcUsd }) {
  if (!totals) return null;

  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(180px,1fr))] gap-3 mb-6">
      <div className="bg-surface border border-border rounded-[10px] p-4">
        <div className="text-xs uppercase tracking-wide text-dim mb-1">Portfolio Total</div>
        <div className="text-xl font-bold tabular-nums">{fmtSats(totals.portfolio_sats, btcUsd)}</div>
        {totals.portfolio_usd != null && <div className="text-xs text-dim mt-0.5">{fmtUsd(totals.portfolio_sats, btcUsd)}</div>}
      </div>
      <div className="bg-surface border border-border rounded-[10px] p-4">
        <div className="text-xs uppercase tracking-wide text-dim mb-1">Bots Total (Odin + Tokens)</div>
        <div className="text-xl font-bold tabular-nums">{fmtSats(totals.odin_sats + totals.token_value_sats, btcUsd)}</div>
      </div>
      <div className="bg-surface border border-border rounded-[10px] p-4">
        <div className="text-xs uppercase tracking-wide text-dim mb-1">Wallet (ckBTC)</div>
        <div className="text-xl font-bold tabular-nums">{fmtSats(totals.wallet_sats, btcUsd)}</div>
      </div>
    </div>
  );
}

export default function BotsView({ btcUsd, refreshKey = 0 }) {
  const refreshRef = { current: false };
  const { data, loading, error, refetch } = useFetch(
    () => { const r = refreshRef.current || refreshKey > 0; refreshRef.current = false; return getWalletBalances({ refresh: r }); },
    [refreshKey], { cacheKey: "wallet_balances" },
  );
  const hardRefresh = () => { refreshRef.current = true; refetch(); };

  if (loading && !data) return <div className="text-center py-16 text-dim"><Spinner className="mr-2" /> Loading bot data...</div>;
  if (error) return (
    <div className="text-center py-16">
      <div className="bg-red-dim border border-red rounded-[10px] px-4 py-3 mb-4 text-sm text-red inline-block">{error}</div>
      <div><button onClick={refetch} className="text-sm text-accent hover:underline cursor-pointer mt-2">Retry</button></div>
    </div>
  );
  if (!data) return null;

  const bots = data.bots || [];
  const totals = data.totals;

  return (
    <>
      <PortfolioSummary totals={totals} btcUsd={btcUsd} />

      <div className="flex items-center justify-between mb-4">
        <h3 className="text-base font-semibold">Bots ({bots.length})</h3>
        <button onClick={hardRefresh} disabled={loading}
          className="px-3 py-1.5 rounded-lg text-xs bg-surface border border-border text-dim hover:text-text hover:bg-surface-hover transition-colors cursor-pointer disabled:opacity-50">
          {loading ? <><Spinner className="w-3 h-3 mr-1" /> Refreshing...</> : "Refresh"}
        </button>
      </div>

      {bots.length === 0 ? (
        <div className="text-center py-8 text-dim text-sm">No bots configured. Use the Chat tab to set up bots.</div>
      ) : (
        <div className="grid grid-cols-1 gap-3">
          {bots.map((bot) => (
            <BotCard key={bot.name} bot={bot} btcUsd={btcUsd} />
          ))}
        </div>
      )}

      <div className="bg-surface border border-border rounded-[10px] p-4 mt-6">
        <h4 className="text-sm font-semibold mb-2">Bot Commands (via Chat)</h4>
        <div className="text-xs text-dim leading-relaxed space-y-1">
          <div><code className="text-accent">"fund bot-1 with 10000 sats"</code> — Transfer ckBTC from wallet to a bot</div>
          <div><code className="text-accent">"buy 5000 sats of ODINDOG on bot-1"</code> — Buy a token on Odin.fun</div>
          <div><code className="text-accent">"sell all ODINDOG on bot-1"</code> — Sell token holdings</div>
          <div><code className="text-accent">"withdraw bot-1"</code> — Move funds back to wallet</div>
        </div>
      </div>
    </>
  );
}
