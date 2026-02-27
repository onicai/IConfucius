import { useState, useEffect, useCallback, Component } from "react";
import { getBtcPrice, getWalletStatus, getWalletInfo, getWalletBalances } from "./api";
import { clearClientCache, preloadCache } from "./hooks";
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
        <button className="ml-3 underline cursor-pointer" onClick={() => this.setState({ error: null })}>retry</button>
      </div>
    );
    return this.props.children;
  }
}

const PRIMARY = [
  {
    id: "bots", label: "Bots", icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="11" width="18" height="10" rx="2"/><circle cx="12" cy="5" r="3"/><path d="M8 16h.01"/><path d="M16 16h.01"/>
      </svg>
    ), desc: "Bot holdings & portfolio",
  },
  {
    id: "wallet", label: "Wallet", icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <rect x="2" y="6" width="20" height="14" rx="2"/><path d="M2 10h20"/><path d="M16 14h2"/>
      </svg>
    ), desc: "ckBTC balance & addresses",
  },
  {
    id: "trades", label: "Trades", icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>
      </svg>
    ), desc: "Your trade history",
  },
];

const EXPLORE = [
  {
    id: "tokens", label: "Tokens", icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10"/><path d="M12 6v12"/><path d="M8 10h8"/><path d="M8 14h8"/>
      </svg>
    ), desc: "Market data & trending",
  },
  {
    id: "search", label: "Search", icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
      </svg>
    ), desc: "Find tokens by name or ID",
  },
];

const ALL_SERVICES = [...PRIMARY, ...EXPLORE];

const GRID_COLS = { 2: "grid-cols-2", 3: "grid-cols-3", 5: "grid-cols-5" };

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
                ? "px-3 py-2 bg-surface/50 border-border/50 hover:bg-surface hover:border-border"
                : isActive
                  ? "px-3 py-2 bg-accent-dim border-accent text-accent shadow-[0_0_12px_rgba(247,147,26,0.08)]"
                  : "flex-col px-4 py-4 bg-surface border-border hover:border-accent/40 hover:bg-surface-hover"
              }`}
          >
            <span className={`shrink-0 ${isActive ? "text-accent" : "text-dim group-hover:text-accent"} transition-colors`}>
              {s.icon}
            </span>
            <div className="min-w-0">
              <div className={`font-semibold truncate ${hasActive ? "text-xs" : "text-sm"}`}>{s.label}</div>
              {!hasActive && <div className="text-[0.65rem] text-dim mt-0.5 leading-tight">{s.desc}</div>}
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

export default function App() {
  const [active, setActive] = useState("bots");
  const [btcUsd, setBtcUsd] = useState(null);
  const [proxyOk, setProxyOk] = useState(null);
  const [sdkOk, setSdkOk] = useState(null);
  const [chatOpen, setChatOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  const handleAction = useCallback(() => {
    clearClientCache();
    setRefreshKey((k) => k + 1);
  }, []);

  useEffect(() => {
    getBtcPrice().then(setBtcUsd);
    fetch("/api/odin/tokens?limit=1")
      .then((r) => setProxyOk(r.ok))
      .catch(() => setProxyOk(false));
    getWalletStatus()
      .then((s) => setSdkOk(s.sdk_available))
      .catch(() => setSdkOk(false));
    // Eagerly preload slow data so tiles open instantly
    preloadCache("wallet_info", getWalletInfo);
    preloadCache("wallet_balances", getWalletBalances);
  }, []);

  function toggleService(id) {
    setActive((prev) => prev === id ? null : id);
  }

  const renderView = () => {
    switch (active) {
      case "wallet": return <WalletView btcUsd={btcUsd} refreshKey={refreshKey} />;
      case "bots":   return <BotsView btcUsd={btcUsd} refreshKey={refreshKey} />;
      case "tokens":  return <TokensView btcUsd={btcUsd} />;
      case "trades":  return <TradesView btcUsd={btcUsd} refreshKey={refreshKey} />;
      case "search":  return <SearchView btcUsd={btcUsd} />;
      default: return null;
    }
  };

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <header className="shrink-0 flex items-center justify-between px-4 py-3 border-b border-border lg:px-6">
        <h1 className="text-lg font-bold flex items-center gap-2.5">
          <img src="/icon.webp" alt="IConfucius" className="w-8 h-8 rounded-full object-cover ring-1 ring-accent/30" />
          <div className="flex flex-col leading-tight">
            <span className="text-accent">IConfucius</span>
            <span className="text-[0.6rem] text-dim font-normal -mt-0.5">The Runes trading agent</span>
          </div>
        </h1>
        <div className="flex items-center gap-3 text-[0.7rem] text-dim">
          {btcUsd && <span className="hidden sm:inline">BTC ${btcUsd.toLocaleString()}</span>}
          <span className="flex items-center gap-1"><StatusDot ok={proxyOk} />{proxyOk ? "API" : "Offline"}</span>
          <span className="flex items-center gap-1"><StatusDot ok={sdkOk} />{sdkOk ? "SDK" : "No SDK"}</span>
          {/* Mobile chat toggle */}
          <button
            onClick={() => setChatOpen((o) => !o)}
            className="lg:hidden flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-accent/10 text-accent border border-accent/20 cursor-pointer hover:bg-accent/20 transition-colors"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>
            Chat
          </button>
        </div>
      </header>

      {proxyOk === false && (
        <div className="shrink-0 bg-red-dim border-b border-red px-4 py-2 text-xs text-red">
          Proxy server not running. Start with: <code className="font-mono">npm run proxy</code>
        </div>
      )}

      {/* Main body */}
      <div className="flex-1 flex min-h-0">
        {/* Left content area */}
        <main className="flex-1 min-w-0 flex flex-col overflow-y-auto scrollbar-thin p-4 lg:p-6">
          {/* Service tiles */}
          {renderTileGroup(PRIMARY, active, toggleService)}
          <div className="flex items-center gap-2 mb-3 mt-1">
            <div className="h-px flex-1 bg-border/50" />
            <span className="text-[0.6rem] uppercase tracking-widest text-dim/50 font-medium">Explore</span>
            <div className="h-px flex-1 bg-border/50" />
          </div>
          {renderTileGroup(EXPLORE, active, toggleService)}

          {/* Expanded view */}
          {active && (
            <div className="flex-1 min-h-0">
              <ViewErrorBoundary key={active}>
                {renderView()}
              </ViewErrorBoundary>
            </div>
          )}

          {/* Empty state */}
          {!active && (
            <div className="flex-1 flex items-center justify-center text-dim text-sm">
              <div className="text-center">
                <div className="text-3xl mb-3 opacity-30">&#x5b54;</div>
                <div>Select a service above to get started</div>
                <div className="text-xs mt-1 text-dim/60">or use Chat to interact with your trading agent</div>
              </div>
            </div>
          )}
        </main>

        {/* Chat panel — desktop: always visible sidebar */}
        <aside className="hidden lg:flex w-[380px] shrink-0 border-l border-border">
          <ChatPanel onAction={handleAction} />
        </aside>
      </div>

      {/* Chat panel — mobile: slide-up sheet */}
      {chatOpen && (
        <div className="lg:hidden fixed inset-0 z-50 flex flex-col">
          <div className="flex-1 bg-black/60 backdrop-blur-sm" onClick={() => setChatOpen(false)} />
          <div className="h-[75vh] bg-bg border-t border-border rounded-t-2xl flex flex-col overflow-hidden animate-[slideUp_200ms_ease-out]">
            <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
              <span className="font-semibold text-sm">IConfucius Chat</span>
              <button onClick={() => setChatOpen(false)}
                className="text-dim hover:text-text cursor-pointer p-1">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
              </button>
            </div>
            <ChatPanel onAction={handleAction} />
          </div>
        </div>
      )}
    </div>
  );
}
