import { useState, useEffect, useCallback, useRef, useMemo, Component } from "react";
import { getBtcPrice, getChatHealth, getOdinHealth, getToken, getWalletStatus, getWalletBalances } from "./api";
import { clearClientCache } from "./hooks";
import { fmtSats } from "./utils";
import { useI18n, AVAILABLE_LOCALES } from "./i18n";
import TokensView from "./views/TokensView";
import TradesView from "./views/TradesView";
import SearchView from "./views/SearchView";
import WalletView from "./views/WalletView";
import BotsView from "./views/BotsView";
import ChatPanel from "./views/ChatPanel";

class ViewErrorBoundary extends Component {
  constructor(props) { super(props); this.state = { error: null }; }
  static getDerivedStateFromError(e) { return { error: e }; }
  render() {
    if (this.state.error) return (
      <div className="bg-red-dim border border-red rounded-xl px-4 py-3 text-sm text-red">
        {this.state.error.message}
        <button className="ml-3 underline cursor-pointer" onClick={() => this.setState({ error: null })}>{this.props.retryLabel || "retry"}</button>
      </div>
    );
    return this.props.children;
  }
}

const ICONS = {
  trades: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>
    </svg>
  ),
  bots: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="11" width="18" height="10" rx="2"/><circle cx="12" cy="5" r="3"/><path d="M8 16h.01"/><path d="M16 16h.01"/>
    </svg>
  ),
  wallet: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="6" width="20" height="14" rx="2"/><path d="M2 10h20"/><path d="M16 14h2"/>
    </svg>
  ),
  tokens: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/><path d="M12 6v12"/><path d="M8 10h8"/><path d="M8 14h8"/>
    </svg>
  ),
  search: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
    </svg>
  ),
};

const GRID_COLS = { 2: "grid-cols-2", 3: "grid-cols-3", 5: "grid-cols-5" };
const CHAT_WIDTH_KEY = "iconfucius_chat_panel_width";
const DEFAULT_CHAT_WIDTH = 380;
const MIN_CHAT_WIDTH = 320;

function renderTileGroup(items, active, onToggle) {
  const hasActive = active !== null;
  const colsCls = hasActive ? (GRID_COLS[items.length] || "grid-cols-3") : "grid-cols-2 sm:grid-cols-3";
  return (
    <div className={`grid gap-2 mb-3 ${colsCls}`}>
      {items.map((s) => {
        const isActive = active === s.id;
        return (
          <button
            key={s.id}
            onClick={() => onToggle(s.id)}
            className={`group relative flex items-center gap-2.5 rounded-xl border transition-all duration-200 cursor-pointer text-left
              ${hasActive && !isActive
                ? "px-3 py-3 bg-surface/50 border-border/50 hover:bg-surface hover:border-border"
                : isActive
                  ? "px-3 py-3 bg-accent-dim border-accent text-accent shadow-[0_0_12px_rgba(247,147,26,0.08)]"
                  : "flex-col px-4 py-4 bg-surface border-border hover:border-accent/40 hover:bg-surface-hover"
              }`}
          >
            <span className={`shrink-0 ${isActive ? "text-accent" : "text-dim group-hover:text-accent"} transition-colors`}>
              {s.icon}
            </span>
            <div className="min-w-0">
              <div className={`font-semibold truncate ${hasActive ? "text-xs" : "text-sm"}`}>{s.label}</div>
              {!hasActive && <div className="text-[0.65rem] text-dim mt-0.5 leading-tight">{s.desc}</div>}
              {hasActive && s.liveDesc && <div className="text-[0.65rem] font-medium truncate" style={{ color: "#3b82f6" }}>{s.liveDesc}</div>}
            </div>
          </button>
        );
      })}
    </div>
  );
}

function StatusDot({ ok }) {
  const cls = ok === true ? "bg-green shadow-[0_0_6px_var(--color-green)]"
    : ok === false ? "bg-red shadow-[0_0_6px_var(--color-red)]" : "bg-border";
  return <span className={`inline-block w-1.5 h-1.5 rounded-full ${cls}`} />;
}

function LanguageToggle() {
  const { locale, setLocale } = useI18n();
  return (
    <div className="flex items-center border border-border rounded-lg overflow-hidden text-xs bg-surface" title="Language / 语言">
      {AVAILABLE_LOCALES.map((l) => (
        <button
          key={l.code}
          onClick={() => setLocale(l.code)}
          className={`px-2.5 py-1 cursor-pointer transition-colors font-medium ${
            locale === l.code ? "bg-accent text-bg" : "text-dim hover:text-text hover:bg-surface-hover"
          }`}
        >
          {l.label}
        </button>
      ))}
    </div>
  );
}

export default function App() {
  const { t } = useI18n();
  const [active, setActive] = useState("trades");
  const [btcUsd, setBtcUsd] = useState(null);
  const [odinOk, setOdinOk] = useState(null);
  const [sdkOk, setSdkOk] = useState(null);
  const [chatOpen, setChatOpen] = useState(false);
  const [projectRoot, setProjectRoot] = useState(null);
  const [icfPriceUsd, setIcfPriceUsd] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [portfolioSats, setPortfolioSats] = useState(null);
  const [botsSats, setBotsSats] = useState(null);
  const [walletSats, setWalletSats] = useState(null);
  const [hasBotErrors, setHasBotErrors] = useState(false);
  const [balanceData, setBalanceData] = useState(null);
  const [balanceLoading, setBalanceLoading] = useState(false);
  const [chatOk, setChatOk] = useState(null);
  const [chatFocusTick, setChatFocusTick] = useState(0);
  const [chatWidth, setChatWidth] = useState(() => {
    if (typeof window === "undefined") return DEFAULT_CHAT_WIDTH;
    const saved = Number(window.localStorage.getItem(CHAT_WIDTH_KEY));
    return Number.isFinite(saved) ? saved : DEFAULT_CHAT_WIDTH;
  });
  const [isResizingChat, setIsResizingChat] = useState(false);
  const userSelectedTabRef = useRef(false);

  const clampChatWidth = useCallback((w) => {
    if (typeof window === "undefined") return Math.max(MIN_CHAT_WIDTH, w);
    const max = Math.max(420, Math.floor(window.innerWidth * 0.62));
    return Math.min(max, Math.max(MIN_CHAT_WIDTH, w));
  }, []);

  const handleAction = useCallback(() => {
    clearClientCache();
    setRefreshKey((k) => k + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;

    getBtcPrice()
      .then((rate) => {
        if (cancelled) return null;
        setBtcUsd(rate);
        return getToken("29m8").then((tok) => {
          if (cancelled) return;
          if (tok?.price && rate) {
            const sats = tok.price / 1000;
            setIcfPriceUsd((sats / 1e8) * rate);
          }
        });
      })
      .catch(() => {});
    getOdinHealth()
      .then((h) => setOdinOk(h.ok))
      .catch(() => setOdinOk(false));

    (async () => {
      try {
        const s = await getWalletStatus();
        if (cancelled) return;
        setSdkOk(s.sdk_available);
        if (s.project_root) setProjectRoot(s.project_root);
        if (s.ai_operational === true) setChatOk(true);
        else if (s.ai_operational === false) setChatOk(false);

        if (!s.sdk_available || !s.ready) {
          if (!userSelectedTabRef.current) setActive("wallet");
          return;
        }

        const b = await getWalletBalances();
        if (cancelled) return;
        const totals = b?.totals || {};
        const tradableSats =
          Number(totals.wallet_sats || 0) +
          Number(totals.odin_sats || 0) +
          Number(totals.token_value_sats || 0);

        if (tradableSats <= 0 && !userSelectedTabRef.current) {
          setActive("wallet");
        }
      } catch {
        if (cancelled) return;
        setSdkOk(false);
        if (!userSelectedTabRef.current) setActive("wallet");
      }
    })();

    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    if (refreshKey > 0) {
      setPortfolioSats(null);
      setBotsSats(null);
      setWalletSats(null);
    }
    setBalanceLoading(true);
    getWalletBalances({ refresh: refreshKey > 0 }).then((b) => {
      if (cancelled) return;
      setBalanceData(b);
      setBalanceLoading(false);
      const totals = b?.totals || {};
      const oSats = Number(totals.odin_sats || 0);
      const tSats = Number(totals.token_value_sats || 0);
      const wSats = Number(b?.wallet?.ckbtc_sats || 0);
      setPortfolioSats(oSats + tSats + wSats);
      setBotsSats(oSats + tSats);
      setWalletSats(wSats);
      setHasBotErrors((b?.bots || []).some((bot) => !!bot.note));
    }).catch(() => { if (!cancelled) setBalanceLoading(false); });
    return () => { cancelled = true; };
  }, [refreshKey]);

  useEffect(() => {
    setChatWidth((w) => clampChatWidth(w));
    window.localStorage.setItem(CHAT_WIDTH_KEY, String(clampChatWidth(chatWidth)));
  }, [chatWidth, clampChatWidth]);

  useEffect(() => {
    function onWindowResize() {
      setChatWidth((w) => clampChatWidth(w));
    }
    window.addEventListener("resize", onWindowResize);
    return () => window.removeEventListener("resize", onWindowResize);
  }, [clampChatWidth]);

  useEffect(() => {
    if (chatOk !== false) return;
    let cancelled = false;
    const poll = () => {
      getChatHealth()
        .then((h) => { if (!cancelled && h.ok !== false) setChatOk(h.ok ?? true); })
        .catch(() => {});
    };
    poll();
    const id = setInterval(poll, 30_000);
    return () => { cancelled = true; clearInterval(id); };
  }, [chatOk]);

  useEffect(() => {
    if (odinOk !== false) return;
    let cancelled = false;
    const poll = () => {
      getOdinHealth()
        .then((h) => { if (!cancelled && h.ok === true) setOdinOk(true); })
        .catch(() => {});
    };
    const id = setInterval(poll, 30_000);
    return () => { cancelled = true; clearInterval(id); };
  }, [odinOk]);

  function toggleService(id) {
    userSelectedTabRef.current = true;
    setActive((prev) => prev === id ? null : id);
    setChatFocusTick((val) => val + 1);
  }

  const beginResizeChat = useCallback((e) => {
    e.preventDefault();
    setIsResizingChat(true);

    function onMove(ev) {
      const next = window.innerWidth - ev.clientX;
      setChatWidth(clampChatWidth(next));
    }

    function onUp() {
      setIsResizingChat(false);
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    }

    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }, [clampChatWidth]);

  const PRIMARY = useMemo(() => [
    { id: "trades", label: t("nav.trades"), icon: ICONS.trades, desc: t("nav.trades_desc") },
    { id: "bots", label: t("nav.bots"), icon: ICONS.bots, desc: t("nav.bots_desc") },
    { id: "wallet", label: t("nav.wallet"), icon: ICONS.wallet, desc: t("nav.wallet_desc") },
  ], [t]);

  const EXPLORE = useMemo(() => [
    { id: "tokens", label: t("nav.tokens"), icon: ICONS.tokens, desc: t("nav.tokens_desc") },
    { id: "search", label: t("nav.search"), icon: ICONS.search, desc: t("nav.search_desc") },
  ], [t]);

  const primaryTiles = useMemo(() => PRIMARY.map((tile) => {
    if (tile.id === "bots" && botsSats != null && btcUsd) {
      const val = fmtSats(botsSats, btcUsd);
      return { ...tile, desc: val, liveDesc: val };
    }
    if (tile.id === "wallet" && walletSats != null && btcUsd) {
      const val = fmtSats(walletSats, btcUsd);
      return { ...tile, desc: val, liveDesc: val };
    }
    return tile;
  }), [PRIMARY, botsSats, walletSats, btcUsd]);

  const renderView = () => {
    switch (active) {
      case "wallet": return <WalletView btcUsd={btcUsd} data={balanceData} loading={balanceLoading} onRefresh={handleAction} />;
      case "bots":   return <BotsView btcUsd={btcUsd} data={balanceData} loading={balanceLoading} onRefresh={handleAction} />;
      case "tokens":  return <TokensView btcUsd={btcUsd} />;
      case "trades":  return <TradesView btcUsd={btcUsd} refreshKey={refreshKey} />;
      case "search":  return <SearchView btcUsd={btcUsd} />;
      default: return null;
    }
  };

  const odinLabel = odinOk === false ? "Odin Error" : hasBotErrors ? "Odin Degraded" : "Odin";
  const chatLabel = sdkOk === false ? t("status.no_sdk") : chatOk === false ? "Chat Error" : "Chat";

  return (
    <div className={`h-full flex flex-col ${isResizingChat ? "select-none" : ""}`}>
      {/* Header */}
      <header className="shrink-0 flex items-center justify-between px-4 py-3 border-b border-border lg:px-6">
        <h1 className="text-lg font-bold flex items-center gap-2.5">
          <img src="/icon.webp" alt={t("app.title")} className="w-8 h-8 rounded-full object-cover ring-1 ring-accent/30" />
          <div className="flex flex-col leading-tight">
            <span className="text-accent">{t("app.title")}</span>
            <span className="text-[0.6rem] text-dim font-normal -mt-0.5">
              {projectRoot ? (projectRoot.split("/").pop() || projectRoot) : t("app.subtitle")}
            </span>
          </div>
          {portfolioSats != null ? (
            <span className="text-sm font-semibold ml-1" style={{ color: "#3b82f6" }}>
              {fmtSats(portfolioSats, btcUsd)}
            </span>
          ) : (
            <span className="text-[0.65rem] text-dim ml-1 flex items-center gap-1.5">
              <span className="inline-block w-3 h-3 border-2 border-dim/40 border-t-dim rounded-full animate-spin" />
            </span>
          )}
        </h1>
        <div className="flex items-center gap-3 text-[0.7rem] text-dim">
          {btcUsd && <span className="hidden sm:inline">BTC ${Math.round(btcUsd).toLocaleString()}</span>}
          {icfPriceUsd != null && <span className="hidden sm:inline">ICONFUCIUS ${icfPriceUsd < 0.01 ? icfPriceUsd.toFixed(4) : icfPriceUsd.toFixed(2)}</span>}
          <span className="flex items-center gap-1"><StatusDot ok={odinOk === false ? false : hasBotErrors ? false : odinOk} />{odinLabel}</span>
          <span className="flex items-center gap-1"><StatusDot ok={sdkOk === false ? false : chatOk === false ? false : sdkOk === true && chatOk === true ? true : null} />{chatLabel}</span>
          <LanguageToggle />
          {/* Mobile chat toggle */}
          <button
            onClick={() => setChatOpen((o) => !o)}
            className="lg:hidden flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-accent/10 text-accent border border-accent/20 cursor-pointer hover:bg-accent/20 transition-colors"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>
            {t("app.chat_btn")}
          </button>
        </div>
      </header>

      {odinOk === false && (
        <div className="shrink-0 bg-red-dim border-b border-red px-4 py-2 text-xs text-red">
          {t("app.proxy_offline")} <code className="font-mono">npm run proxy</code>
        </div>
      )}

      {/* Main body */}
      <div className="flex-1 flex min-h-0">
        {/* Left content area */}
        <main className="flex-1 min-w-0 flex flex-col overflow-y-auto scrollbar-thin p-4 lg:p-6">
          {/* Service tiles */}
          {renderTileGroup(primaryTiles, active, toggleService)}
          <div className="flex items-center gap-2 mb-3 mt-1">
            <div className="h-px flex-1 bg-border/50" />
            <span className="text-[0.6rem] uppercase tracking-widest text-dim/50 font-medium">{t("app.explore")}</span>
            <div className="h-px flex-1 bg-border/50" />
          </div>
          {renderTileGroup(EXPLORE, active, toggleService)}

          {/* Expanded view */}
          {active && (
            <div className="flex-1 min-h-0">
              <ViewErrorBoundary key={active} retryLabel={t("app.error_retry")}>
                {renderView()}
              </ViewErrorBoundary>
            </div>
          )}

          {/* Empty state */}
          {!active && (
            <div className="flex-1 flex items-center justify-center text-dim text-sm">
              <div className="text-center">
                <div className="text-3xl mb-3 opacity-30">&#x5b54;</div>
                <div>{t("app.empty_title")}</div>
                <div className="text-xs mt-1 text-dim/60">{t("app.empty_sub")}</div>
              </div>
            </div>
          )}
        </main>

        {/* Chat panel — desktop: always visible + resizable */}
        <div
          className={`hidden lg:flex w-2 shrink-0 items-center justify-center cursor-col-resize ${
            isResizingChat ? "bg-accent/10" : "hover:bg-surface-hover"
          }`}
          onMouseDown={beginResizeChat}
          title={t("app.chat_resize")}
        >
          <div className="w-px h-full bg-border" />
        </div>
        <aside className="hidden lg:flex shrink-0 border-l border-border" style={{ width: `${chatWidth}px` }}>
          <ChatPanel onAction={handleAction} focusSignal={chatFocusTick} onChatStatus={setChatOk} />
        </aside>
      </div>

      {/* Chat panel — mobile: slide-up sheet */}
      {chatOpen && (
        <div className="lg:hidden fixed inset-0 z-50 flex flex-col">
          <div className="flex-1 bg-black/60 backdrop-blur-sm" onClick={() => setChatOpen(false)} />
          <div className="h-[75vh] bg-bg border-t border-border rounded-t-2xl flex flex-col overflow-hidden animate-[slideUp_200ms_ease-out]">
            <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
              <span className="font-semibold text-sm">{t("app.chat_mobile_title")}</span>
              <button onClick={() => setChatOpen(false)}
                className="text-dim hover:text-text cursor-pointer p-1">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
              </button>
            </div>
            <ChatPanel onAction={handleAction} focusSignal={chatFocusTick} onChatStatus={setChatOk} />
          </div>
        </div>
      )}
    </div>
  );
}
