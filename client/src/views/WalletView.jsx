import { useState, useEffect, useCallback } from "react";
import { getWalletInfo, getWalletStatus, setupInit, setupWalletCreate } from "../api";
import { useFetch } from "../hooks";
import { fmtSats } from "../utils";

const Spinner = ({ className = "" }) => (
  <span className={`inline-block w-5 h-5 border-2 border-border border-t-accent rounded-full animate-spin align-middle ${className}`} />
);

function StatCard({ label, value, sub, help }) {
  return (
    <div className="bg-surface border border-border rounded-[10px] p-4">
      <div className="text-xs uppercase tracking-wide text-dim mb-1">{label}</div>
      <div className="text-xl font-bold tabular-nums">{value}</div>
      {sub && <div className="text-xs text-dim mt-0.5">{sub}</div>}
      {help && <div className="text-[0.7rem] text-dim mt-1.5 leading-snug">{help}</div>}
    </div>
  );
}

function StepCircle({ number, done, active }) {
  const cls = done ? "bg-green-dim text-green border-green"
    : active ? "bg-accent-dim text-accent border-accent"
    : "bg-surface text-dim border-border";
  return (
    <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold shrink-0 border ${cls}`}>
      {done ? "\u2713" : number}
    </div>
  );
}

function ResultBox({ result }) {
  if (!result) return null;
  const err = result.status === "error";
  return (
    <div className={`mt-2.5 px-3.5 py-2.5 rounded-md text-[0.82rem] whitespace-pre-wrap leading-relaxed border ${err ? "bg-red-dim text-red border-red" : "bg-green-dim text-green border-green"}`}>
      {result.display || result.error || "Done"}
    </div>
  );
}

function DownloadBackupButton({ className = "" }) {
  return (
    <button onClick={() => { const a = document.createElement("a"); a.href = "/api/wallet/backup"; a.download = "iconfucius-identity-private.pem"; a.click(); }}
      className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium bg-accent-dim text-accent border border-accent/30 hover:bg-accent/20 transition-colors cursor-pointer ${className}`}>
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
      </svg>
      Download Backup
    </button>
  );
}

function SetupWizard({ status, onComplete }) {
  const sdkMissing = !status.sdk_available;
  const configExists = status.config_exists;
  const walletExists = status.wallet_exists;
  const [numBots, setNumBots] = useState(3);
  const [initLoading, setInitLoading] = useState(false);
  const [initResult, setInitResult] = useState(null);
  const [walletLoading, setWalletLoading] = useState(false);
  const [walletResult, setWalletResult] = useState(null);

  const configDone = configExists || (initResult && initResult.status !== "error");
  const walletDone = walletExists || (walletResult && walletResult.status !== "error");
  const activeStep = sdkMissing ? 0 : !configDone ? 1 : !walletDone ? 2 : 3;

  async function handleInit() {
    setInitLoading(true); setInitResult(null);
    try { setInitResult(await setupInit({ numBots })); }
    catch (e) { setInitResult({ status: "error", error: e.message }); }
    finally { setInitLoading(false); }
  }
  async function handleWalletCreate() {
    setWalletLoading(true); setWalletResult(null);
    try { setWalletResult(await setupWalletCreate()); }
    catch (e) { setWalletResult({ status: "error", error: e.message }); }
    finally { setWalletLoading(false); }
  }

  useEffect(() => {
    if (configDone && walletDone && !sdkMissing) {
      const t = setTimeout(onComplete, 1500);
      return () => clearTimeout(t);
    }
  }, [configDone, walletDone, sdkMissing, onComplete]);

  const ActionBtn = ({ onClick, loading: l, children }) => (
    <button onClick={onClick} disabled={l}
      className="mt-3 px-5 py-2 rounded-[10px] text-sm bg-surface border border-border text-text hover:bg-surface-hover transition-colors cursor-pointer disabled:opacity-50">
      {l ? <><Spinner className="w-3.5 h-3.5 mr-2" /> Running...</> : children}
    </button>
  );

  return (
    <div className="bg-surface border border-border rounded-[10px] p-6 max-w-xl">
      <div className="flex items-center justify-between mb-1">
        <h3 className="text-lg font-bold">Wallet Setup</h3>
        <button onClick={onComplete}
          className="text-xs text-dim hover:text-text transition-colors cursor-pointer px-2 py-1 rounded hover:bg-surface-hover">
          Already configured? Refresh ↻
        </button>
      </div>
      <p className="text-sm text-dim mb-5">{sdkMissing ? "The iconfucius SDK is required for wallet features." : "Complete these steps to set up your trading wallet."}</p>

      {sdkMissing && (
        <div className="flex gap-3.5 py-4 border-b border-border">
          <StepCircle number={0} done={false} active />
          <div>
            <div className="font-semibold mb-1">Install iconfucius SDK</div>
            <div className="text-sm text-dim leading-relaxed">
              Run from the project root:
              <pre className="bg-bg border border-border rounded-md px-3.5 py-2.5 text-[0.82rem] mt-2 text-accent">pip install -e agent/</pre>
              Then restart the proxy server.
            </div>
          </div>
        </div>
      )}

      {!sdkMissing && (
        <div className={`flex gap-3.5 py-4 border-b border-border ${configDone && activeStep !== 1 ? "opacity-50" : ""}`}>
          <StepCircle number={1} done={configDone} active={activeStep === 1} />
          <div className="flex-1">
            <div className="font-semibold mb-1">Initialize Project</div>
            {activeStep === 1 && (
              <div className="text-sm text-dim leading-relaxed">
                Sets up the project configuration and bot accounts.
                <div className="flex items-center gap-3 mt-2.5">
                  <label className="text-[0.82rem]">
                    Bots:{" "}
                    <input type="number" min={1} max={100} value={numBots}
                      onChange={(e) => setNumBots(Math.max(1, parseInt(e.target.value) || 1))}
                      className="w-14 px-2 py-1 bg-bg border border-border rounded text-text text-sm" />
                  </label>
                </div>
                <ActionBtn onClick={handleInit} loading={initLoading}>Initialize Project</ActionBtn>
                <ResultBox result={initResult} />
              </div>
            )}
            {configDone && activeStep !== 1 && <div className="text-[0.82rem] text-green">Project initialized</div>}
          </div>
        </div>
      )}

      {!sdkMissing && (
        <div className={`flex gap-3.5 py-4 border-b border-border ${activeStep < 2 ? "opacity-40" : walletDone && activeStep !== 2 ? "opacity-50" : ""}`}>
          <StepCircle number={2} done={walletDone} active={activeStep === 2} />
          <div className="flex-1">
            <div className="font-semibold mb-1">Create Wallet</div>
            {activeStep === 2 && (
              <div className="text-sm text-dim leading-relaxed">
                Creates a new trading identity for your wallet.
                <div className="mt-2 px-3 py-2 bg-red-dim border border-red rounded-md text-xs text-red font-medium">
                  After creation, download and store the backup file in a safe place. If lost, access to all funds is gone permanently.
                </div>
                <ActionBtn onClick={handleWalletCreate} loading={walletLoading}>Create Wallet</ActionBtn>
                <ResultBox result={walletResult} />
                {walletDone && <DownloadBackupButton className="mt-2" />}
              </div>
            )}
            {walletDone && activeStep !== 2 && (
              <div className="flex items-center gap-3">
                <span className="text-[0.82rem] text-green">Wallet created</span>
                <DownloadBackupButton />
              </div>
            )}
          </div>
        </div>
      )}

      {!sdkMissing && (
        <div className={`flex gap-3.5 py-4 ${activeStep < 3 ? "opacity-40" : ""}`}>
          <StepCircle number={3} done={configDone && walletDone} active={activeStep === 3} />
          <div>
            <div className="font-semibold mb-1">Ready</div>
            {activeStep === 3 && <div className="text-sm text-green">Setup complete! Loading wallet dashboard...</div>}
          </div>
        </div>
      )}
    </div>
  );
}

function WalletInfoCards({ btcUsd, refreshKey = 0 }) {
  const refreshRef = { current: false };
  const { data, loading, error, refetch } = useFetch(
    () => { const r = refreshRef.current || refreshKey > 0; refreshRef.current = false; return getWalletInfo({ refresh: r }); },
    [refreshKey], { cacheKey: "wallet_info" },
  );
  const hardRefresh = () => { refreshRef.current = true; refetch(); };
  if (loading && !data) return <div className="text-center py-16 text-dim"><Spinner className="mr-2" /> Loading wallet...</div>;
  if (error && !data) return <div className="bg-red-dim border border-red rounded-[10px] px-4 py-3 mb-4 text-sm text-red">{error}</div>;
  if (!data) return null;

  return (
    <>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-base font-semibold">Wallet</h3>
        <button onClick={hardRefresh} disabled={loading}
          className="px-3 py-1.5 rounded-lg text-xs bg-surface border border-border text-dim hover:text-text hover:bg-surface-hover transition-colors cursor-pointer disabled:opacity-50">
          {loading ? <><Spinner className="w-3 h-3 mr-1" /> Refreshing...</> : "Refresh Balances"}
        </button>
      </div>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-3 mb-6">
        <StatCard
          label="ckBTC Balance"
          value={fmtSats(data.balance_sats, btcUsd)}
          sub={data.balance_usd != null ? `$${data.balance_usd.toFixed(3)}` : null}
          help="Your trading funds. ckBTC is a 1:1 Bitcoin-backed token used for all trading on Odin.fun."
        />
        {data.pending_sats > 0 && (
          <StatCard label="Pending BTC" value={fmtSats(data.pending_sats, btcUsd)} sub="Awaiting ~6 Bitcoin confirmations" />
        )}
        <StatCard
          label="Wallet Principal"
          value={<span className="text-[0.7rem] break-all leading-tight">{data.principal}</span>}
          help="Your Internet Computer identity. Use this to receive ckBTC directly."
        />
        <StatCard
          label="BTC Deposit Address"
          value={<span className="text-[0.7rem] break-all leading-tight">{data.btc_address}</span>}
          sub={<a href={`https://mempool.space/address/${data.btc_address}`} target="_blank" rel="noopener noreferrer">View on mempool.space</a>}
          help="Send native BTC here to fund your wallet. After ~6 confirmations it auto-converts to ckBTC."
        />
      </div>
    </>
  );
}

export default function WalletView({ btcUsd, refreshKey = 0 }) {
  const [setupDone, setSetupDone] = useState(null);
  const [status, setStatus] = useState(null);

  const checkStatus = useCallback(() => {
    getWalletStatus()
      .then((s) => { setStatus(s); setSetupDone(s.sdk_available && s.config_exists && s.wallet_exists); })
      .catch(() => { setStatus({ sdk_available: false }); setSetupDone(false); });
  }, []);
  useEffect(() => { checkStatus(); }, [checkStatus]);

  if (setupDone === null) return <div className="text-center py-16 text-dim"><Spinner className="mr-2" /> Checking setup...</div>;
  if (!setupDone && status) return <SetupWizard status={status} onComplete={checkStatus} />;

  return (
    <>
      <WalletInfoCards btcUsd={btcUsd} refreshKey={refreshKey} />

      <div className="bg-surface border border-border rounded-[10px] p-4 mb-5">
        <h4 className="text-sm font-semibold mb-2">How funding works</h4>
        <div className="text-xs text-dim leading-relaxed space-y-1">
          <div><span className="text-accent font-medium">1.</span> Send BTC to your <span className="text-text">BTC Deposit Address</span> above (min 10,000 sats). After ~6 confirmations it becomes ckBTC in your wallet.</div>
          <div><span className="text-accent font-medium">2.</span> Use the <span className="text-text">Chat</span> tab to fund your bots: <code className="text-accent">"fund bot-1 with 10000 sats"</code></div>
          <div><span className="text-accent font-medium">3.</span> Trade via Chat: <code className="text-accent">"buy 5000 sats of ODINDOG on bot-1"</code></div>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <DownloadBackupButton />
        <span className="text-xs text-dim">Keep your wallet backup in a safe place</span>
      </div>
    </>
  );
}
