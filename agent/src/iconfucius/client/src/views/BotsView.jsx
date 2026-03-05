import LoadingQuote from "../components/LoadingQuote";
import { useI18n } from "../i18n";
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
  const { t } = useI18n();
  const hasAccount = bot.has_odin_account;

  return (
    <div className="bg-surface border border-border rounded-[10px] p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <h4 className="text-sm font-bold">{bot.name}</h4>
          {hasAccount ? (
            <span className="px-1.5 py-0.5 text-[0.65rem] font-medium rounded bg-green-dim text-green border border-green/30">{t("bots.active")}</span>
          ) : (
            <span className="px-1.5 py-0.5 text-[0.65rem] font-medium rounded bg-surface-hover text-dim border border-border">{t("bots.not_registered")}</span>
          )}
        </div>
        {bot.odin_sats != null && (
          <div className="text-right">
            <div className="text-sm font-bold tabular-nums">{fmtSats(bot.odin_sats, btcUsd)}</div>
            <div className="text-[0.65rem] text-dim">{t("bots.odin_balance")}</div>
          </div>
        )}
      </div>

      {bot.note && (
        <div className="bg-red-dim border border-red/30 rounded px-3 py-2 mb-3">
          <p className="text-xs text-red font-medium">{t("bots.odin_error_message")}</p>
          <details className="mt-1">
            <summary className="text-[0.65rem] text-red/70 cursor-pointer">{t("bots.odin_error_details")}</summary>
            <p className="text-[0.65rem] text-red/70 mt-1 break-all">{bot.note}</p>
          </details>
        </div>
      )}

      {bot.principal && (
        <div className="text-[0.65rem] text-dim font-mono break-all mb-3 bg-bg rounded px-2 py-1 border border-border">
          {bot.principal}
        </div>
      )}

      {bot.tokens && bot.tokens.length > 0 ? (
        <div>
          <div className="text-[0.7rem] text-dim mb-1.5 font-medium">{t("bots.token_holdings")}</div>
          <div className="flex flex-wrap gap-1.5">
            {bot.tokens.map((tk) => (
              <TokenBadge key={tk.id || tk.ticker} ticker={tk.ticker} tokenId={tk.id} balance={tk.balance} valueSats={tk.value_sats} btcUsd={btcUsd} />
            ))}
          </div>
        </div>
      ) : hasAccount ? (
        <div className="text-xs text-dim">{t("bots.no_holdings")}</div>
      ) : (
        <div className="text-xs text-dim">
          {t("bots.register_hint")} <code className="text-accent">&quot;{t("bots.register_cmd", { name: bot.name })}&quot;</code>
        </div>
      )}
    </div>
  );
}

function TokenTotals({ tokens, btcUsd }) {
  const { t } = useI18n();
  if (!tokens || Object.keys(tokens).length === 0) return null;
  const sorted = Object.entries(tokens).sort((a, b) => b[1].value_sats - a[1].value_sats);
  return (
    <div className="bg-surface border border-border rounded-[10px] p-4 mb-6">
      <div className="text-xs uppercase tracking-wide text-dim mb-2">{t("bots.token_totals")}</div>
      <div className="flex flex-wrap gap-1.5">
        {sorted.map(([ticker, tk]) => (
          <TokenBadge key={tk.id || ticker} ticker={ticker} tokenId={tk.id}
            balance={tk.balance} valueSats={tk.value_sats} btcUsd={btcUsd} />
        ))}
      </div>
    </div>
  );
}

function PortfolioSummary({ totals, btcUsd }) {
  const { t } = useI18n();
  if (!totals) return null;
  const odinSats = Number(totals.odin_sats || 0);
  const tokenSats = Number(totals.token_value_sats || 0);

  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(180px,1fr))] gap-3 mb-6">
      <div className="bg-surface border border-border rounded-[10px] p-4">
        <div className="text-xs uppercase tracking-wide text-dim mb-1">{t("bots.summary.bots_total")}</div>
        <div className="text-xl font-bold tabular-nums">{fmtSats(odinSats + tokenSats, btcUsd)}</div>
      </div>
      <div className="bg-surface border border-border rounded-[10px] p-4">
        <div className="text-xs uppercase tracking-wide text-dim mb-1">{t("bots.summary.odin_tokens")}</div>
        <div className="text-xl font-bold tabular-nums">{fmtSats(tokenSats, btcUsd)}</div>
      </div>
      <div className="bg-surface border border-border rounded-[10px] p-4">
        <div className="text-xs uppercase tracking-wide text-dim mb-1">{t("bots.summary.odin_btc")}</div>
        <div className="text-xl font-bold tabular-nums">{fmtSats(odinSats, btcUsd)}</div>
      </div>
    </div>
  );
}

export default function BotsView({ btcUsd, data, loading, onRefresh }) {
  const { t } = useI18n();
  if (!data) return <LoadingQuote message={t("bots.loading")} />;

  const bots = data.bots || [];
  const totals = data.totals;

  return (
    <>
      <PortfolioSummary totals={totals} btcUsd={btcUsd} />
      <TokenTotals tokens={totals?.tokens} btcUsd={btcUsd} />

      <div className="flex items-center justify-between mb-4">
        <h3 className="text-base font-semibold">{t("bots.title")} ({bots.length})</h3>
        <button onClick={onRefresh} disabled={loading}
          className="px-3 py-1.5 rounded-lg text-xs bg-surface border border-border text-dim hover:text-text hover:bg-surface-hover transition-colors cursor-pointer disabled:opacity-50">
          {loading ? <><Spinner className="w-3 h-3 mr-1" /> {t("bots.refreshing")}</> : t("bots.refresh")}
        </button>
      </div>

      {bots.length === 0 ? (
        <div className="text-center py-8 text-dim text-sm">{t("bots.empty")}</div>
      ) : (
        <div className="grid grid-cols-1 gap-3">
          {bots.map((bot) => (
            <BotCard key={bot.name} bot={bot} btcUsd={btcUsd} />
          ))}
        </div>
      )}

      <div className="bg-surface border border-border rounded-[10px] p-4 mt-6">
        <h4 className="text-sm font-semibold mb-2">{t("bots.commands_title")}</h4>
        <div className="text-xs text-dim leading-relaxed space-y-1">
          <div>{t("bots.cmd_fund")}</div>
          <div>{t("bots.cmd_buy")}</div>
          <div>{t("bots.cmd_sell")}</div>
          <div>{t("bots.cmd_withdraw")}</div>
        </div>
      </div>
    </>
  );
}
