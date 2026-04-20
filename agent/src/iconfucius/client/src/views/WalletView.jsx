import { useState, useEffect, useCallback, useRef } from "react";
import { getWalletStatus, getWalletInfo, setupInit, setupWalletCreate, setupSetBots, setupRegisterBot, setupFundBot, importWallet, walletSend } from "../api";
import LoadingQuote from "../components/LoadingQuote";
import { clearClientCache } from "../hooks";
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

function truncateMiddle(text, head = 8, tail = 8) {
  if (!text || text.length <= head + tail + 3) return text || "";
  return `${text.slice(0, head)}...${text.slice(-tail)}`;
}

function AddressWithCopy({ value }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div className="flex items-center gap-2">
      <span className="text-[0.78rem] font-mono leading-tight" title={value}>
        {truncateMiddle(value)}
      </span>
      <button
        onClick={handleCopy}
        className="shrink-0 px-2 py-0.5 rounded-md text-[0.65rem] font-medium bg-surface-hover border border-border text-dim hover:text-text cursor-pointer transition-colors"
      >
        {copied ? "Copied" : "Copy"}
      </button>
    </div>
  );
}

function DownloadBackupButton({ projectName, className = "" }) {
  const filename = projectName
    ? `iconfucius-${projectName}-wallet-identity-private.pem`
    : "iconfucius-identity-private.pem";
  return (
    <button onClick={() => { const a = document.createElement("a"); a.href = "/api/wallet/backup"; a.download = filename; a.click(); }}
      className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium bg-accent-dim text-accent border border-accent/30 hover:bg-accent/20 transition-colors cursor-pointer ${className}`}>
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
      </svg>
      Download Backup
    </button>
  );
}

function ImportWalletButton({ onImported, className = "" }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function handleFile(file) {
    setLoading(true); setError(null);
    try {
      const text = await file.text();
      await importWallet(text);
      clearClientCache();
      if (onImported) onImported();
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }

  return (
    <span className={className}>
      <label className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium bg-surface border border-border text-dim hover:text-text hover:bg-surface-hover transition-colors cursor-pointer ${loading ? "opacity-50 pointer-events-none" : ""}`}>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
        </svg>
        {loading ? "Importing..." : "Import Wallet"}
        <input type="file" accept=".pem" className="hidden"
          onChange={(e) => { if (e.target.files[0]) handleFile(e.target.files[0]); e.target.value = ""; }} />
      </label>
      {error && <div className="text-xs text-red mt-1">{error}</div>}
    </span>
  );
}

function SetupWizard({ status, onComplete, onCheckBalance, onNavigate, balanceData, balanceLoading, projectName, btcUsd }) {
  const sdkMissing = !status.sdk_available;
  const configExists = status.config_exists;
  const walletExists = status.wallet_exists;
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [isImport, setIsImport] = useState(false);
  const [backupConfirmed, setBackupConfirmed] = useState(false);
  const [fundingConfirmed, setFundingConfirmed] = useState(false);
  const [botsAdded, setBotsAdded] = useState(false);
  const [walletInfo, setWalletInfo] = useState(null);
  const [numBots, setNumBots] = useState(1);
  const [botResult, setBotResult] = useState(null);
  const [botLoading, setBotLoading] = useState(false);
  const [registerProgress, setRegisterProgress] = useState(null); // {current, total, botName}
  const [registerResults, setRegisterResults] = useState([]); // [{botName, status, error?}]
  const [botNames, setBotNames] = useState([]); // saved from step 4 for step 5
  const [botsFunded, setBotsFunded] = useState(false);
  const [fundAmount, setFundAmount] = useState(5000);
  const [fundLoading, setFundLoading] = useState(false);
  const [fundProgress, setFundProgress] = useState(null); // {current, total, botName}
  const [fundResults, setFundResults] = useState([]); // [{botName, status, error?}]
  const [fundResult, setFundResult] = useState(null);
  const fundingBalance = balanceData?.wallet
    ? { balance_sats: balanceData.wallet.ckbtc_sats ?? 0, pending_sats: balanceData.wallet.pending_sats ?? 0 }
    : null;
  const fundingLoading = balanceLoading;

  const walletCreated = (configExists && walletExists) || (result && result.status !== "error");

  // Auto-advance past backup step when wallet already exists from a previous session.
  // Only auto-advance past funding if the wallet actually has funds.
  useEffect(() => {
    if (configExists && walletExists) {
      setBackupConfirmed(true);
      if (status.wallet_funded) setFundingConfirmed(true);
    }
  }, [configExists, walletExists, status.wallet_funded]);

  const activeStep = sdkMissing ? 0
    : !walletCreated ? 1
    : (!backupConfirmed && !isImport) ? 2
    : !fundingConfirmed ? 3
    : !botsAdded ? 4
    : !botsFunded ? 5
    : 6;

  useEffect(() => {
    if (activeStep === 3 && !walletInfo) fetchWalletInfo();
  }, [activeStep, walletInfo]);

  async function fetchWalletInfo() {
    try {
      const info = await getWalletInfo();
      setWalletInfo(info);
    } catch { /* wallet info will show in main dashboard */ }
  }

  async function handleCreateWallet() {
    setLoading(true); setResult(null); setIsImport(false);
    try {
      if (!configExists) {
        await setupInit({ numBots: 0 });
      }
      const res = await setupWalletCreate();
      setResult(res);
      if (res.status !== "error") await fetchWalletInfo();
    } catch (e) { setResult({ status: "error", error: e.message }); }
    finally { setLoading(false); }
  }

  async function handleImport(file) {
    if (loading) return;
    setLoading(true); setResult(null); setIsImport(true);
    try {
      if (!configExists) {
        await setupInit({ numBots: 0 });
      }
      const text = await file.text();
      const res = await importWallet(text);
      setResult(res);
      if (res.status !== "error") await fetchWalletInfo();
    } catch (e) { setResult({ status: "error", error: e.message }); }
    finally { setLoading(false); }
  }

  async function handleAddBots() {
    setBotLoading(true); setBotResult(null);
    setRegisterProgress(null); setRegisterResults([]);
    try {
      // Phase 1: Write bot config (~200ms)
      const res = await setupSetBots({ numBots });
      if (res.status === "error") {
        setBotResult(res);
        setBotLoading(false);
        return;
      }
      const botsToRegister = res.bots_added || [];
      if (botsToRegister.length === 0) {
        setBotResult(res);
        setBotsAdded(true);
        setBotLoading(false);
        return;
      }

      // Phase 2: Sequential SIWB registration
      const results = [];
      for (let i = 0; i < botsToRegister.length; i++) {
        const botName = botsToRegister[i];
        setRegisterProgress({ current: i + 1, total: botsToRegister.length, botName });
        try {
          const regRes = await setupRegisterBot({ botName });
          results.push({ botName, status: "ok", ...regRes });
        } catch (e) {
          results.push({ botName, status: "error", error: e.message });
        }
        setRegisterResults([...results]);
      }
      setRegisterProgress(null);

      // Phase 3: Check results
      const failures = results.filter(r => r.status === "error");
      if (failures.length === 0) {
        setBotResult({ status: "ok", display: `All ${botsToRegister.length} bot(s) registered with Odin.Fun.` });
        setBotNames(botsToRegister);
        setBotsAdded(true);
      } else {
        const failNames = failures.map(f => f.botName).join(", ");
        setBotResult({ status: "error", error: `Registration failed for: ${failNames}. Click Create to retry.` });
      }
    } catch (e) { setBotResult({ status: "error", error: e.message }); }
    finally { setBotLoading(false); }
  }

  useEffect(() => {
    if (activeStep === 6) {
      const t = setTimeout(() => {
        onComplete();
        if (onNavigate) onNavigate("bots");
      }, 1500);
      return () => clearTimeout(t);
    }
  }, [activeStep, onComplete, onNavigate]);

  const ActionBtn = ({ onClick, loading: l, children, className: cls = "" }) => (
    <button onClick={onClick} disabled={l}
      className={`px-5 py-2 rounded-[10px] text-sm bg-surface border border-border text-text hover:bg-surface-hover transition-colors cursor-pointer disabled:opacity-50 ${cls}`}>
      {l ? <><Spinner className="w-3.5 h-3.5 mr-2" /> Running...</> : children}
    </button>
  );

  async function handleFundBots() {
    setFundLoading(true); setFundResult(null);
    setFundProgress(null); setFundResults([]);
    try {
      const results = [];
      for (let i = 0; i < botNames.length; i++) {
        const botName = botNames[i];
        setFundProgress({ current: i + 1, total: botNames.length, botName });
        try {
          await setupFundBot({ botName, amount: fundAmount });
          results.push({ botName, status: "ok" });
        } catch (e) {
          results.push({ botName, status: "error", error: e.message });
        }
        setFundResults([...results]);
      }
      setFundProgress(null);

      const failures = results.filter(r => r.status === "error");
      if (failures.length === 0) {
        setFundResult({ status: "ok", display: `All ${botNames.length} bot(s) funded with ${fundAmount.toLocaleString()} sats each.` });
        setBotsFunded(true);
        onCheckBalance(false);
      } else {
        const failNames = failures.map(f => f.botName).join(", ");
        setFundResult({ status: "error", error: `Funding failed for: ${failNames}. Click Fund to retry.` });
      }
    } catch (e) { setFundResult({ status: "error", error: e.message }); }
    finally { setFundLoading(false); }
  }

  const stepDef = [
    { n: 1, label: "Create or Import Wallet" },
    { n: 2, label: "Download & Backup" },
    { n: 3, label: "Fund Your Wallet" },
    { n: 4, label: "Create Bots (Odin Accounts)" },
    { n: 5, label: "Fund Your Bots" },
    { n: 6, label: "Ready" },
  ];

  const totalFee = numBots * 120;

  return (
    <div className="bg-surface border border-border rounded-[10px] p-6 max-w-xl">
      <div className="flex items-center justify-between mb-1">
        <h3 className="text-lg font-bold">Wallet Setup</h3>
        <button onClick={onComplete}
          className="text-xs text-dim hover:text-text transition-colors cursor-pointer px-2 py-1 rounded hover:bg-surface-hover">
          Already configured? Refresh
        </button>
      </div>
      <p className="text-sm text-dim mb-5">{sdkMissing ? "The iconfucius SDK is required for wallet features." : "Create a wallet to get started. You can add trading bots after funding."}</p>

      {/* Step 0: SDK missing */}
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

      {/* Steps 1-5 */}
      {!sdkMissing && stepDef.map(({ n, label }) => {
        const done = activeStep > n;
        const active = activeStep === n;
        // Skip step 2 for imports
        if (n === 2 && isImport) return null;

        return (
          <div key={n} className={`flex gap-3.5 py-4 ${n < 6 ? "border-b border-border" : ""} ${!done && !active ? "opacity-40" : done ? "opacity-50" : ""}`}>
            <StepCircle number={n} done={done} active={active} />
            <div className="flex-1">
              <div className="font-semibold mb-1">{label}</div>

              {/* Step 1: Create or Import */}
              {n === 1 && active && (
                <div className="text-sm text-dim leading-relaxed">
                  <div className="flex items-center gap-2 mt-2">
                    <ActionBtn onClick={handleCreateWallet} loading={loading}>Create New Wallet</ActionBtn>
                    <span className="text-xs text-dim">or</span>
                    <label className="px-5 py-2 rounded-[10px] text-sm bg-surface border border-border text-text hover:bg-surface-hover transition-colors cursor-pointer inline-flex items-center gap-1.5">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
                      </svg>
                      Import Backup
                      <input type="file" accept=".pem" className="hidden" disabled={loading}
                        onChange={(e) => { if (e.target.files?.[0]) handleImport(e.target.files[0]); e.target.value = ""; }} />
                    </label>
                  </div>
                  <ResultBox result={result} />
                </div>
              )}
              {n === 1 && done && (
                <span className="text-[0.82rem] text-green">Wallet created</span>
              )}

              {/* Step 2: Backup confirmation */}
              {n === 2 && active && (
                <div className="text-sm leading-relaxed">
                  <div className="mt-2 px-3 py-2.5 bg-warning-dim border border-warning rounded-md text-xs text-warning font-medium flex items-start gap-2">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="shrink-0 mt-0.5">
                      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
                    </svg>
                    <span>IMPORTANT: Download and store the backup file. If lost, access to all funds will be gone permanently.</span>
                  </div>
                  <div className="mt-3">
                    <DownloadBackupButton projectName={projectName} />
                  </div>
                  <label className="flex items-center gap-2 mt-3 text-sm text-dim cursor-pointer select-none">
                    <input type="checkbox" checked={backupConfirmed} onChange={(e) => setBackupConfirmed(e.target.checked)}
                      className="w-4 h-4 accent-accent" />
                    I have downloaded and backed up my wallet identity
                  </label>
                </div>
              )}
              {n === 2 && done && (
                <div className="flex items-center gap-3">
                  <span className="text-[0.82rem] text-green">Backup confirmed</span>
                  <DownloadBackupButton projectName={projectName} />
                </div>
              )}

              {/* Step 3: Fund wallet */}
              {n === 3 && active && !walletInfo && (
                <div className="text-sm text-dim flex items-center gap-2 mt-1">
                  <Spinner className="w-3.5 h-3.5" /> Loading wallet addresses...
                </div>
              )}
              {n === 3 && active && walletInfo && (
                <div className="text-sm text-dim leading-relaxed">
                  <div className="mt-2 space-y-3">
                    <div className="bg-surface border border-border rounded-lg p-3">
                      <div className="text-xs mb-1.5">
                        <span className="text-accent font-medium">Option 1</span>
                        <span className="text-text font-semibold"> — Send ckBTC to your Wallet Principal</span>
                      </div>
                      <AddressWithCopy value={walletInfo.principal} />
                      <div className="text-[0.7rem] text-dim mt-1">
                        Use this if you already have ckBTC on the Internet Computer.
                      </div>
                    </div>
                    <div className="bg-surface border border-border rounded-lg p-3">
                      <div className="text-xs mb-1.5">
                        <span className="text-accent font-medium">Option 2</span>
                        <span className="text-text font-semibold"> — Send BTC to your BTC Deposit Address</span>
                      </div>
                      <AddressWithCopy value={walletInfo.btc_address} />
                      <div className="text-[0.7rem] text-dim mt-1">
                        Send native BTC here — after ~6 confirmations it auto-converts to ckBTC.
                      </div>
                    </div>
                  </div>
                  <div className="mt-3 flex items-center gap-2">
                    <button onClick={() => onCheckBalance(false)}
                      disabled={fundingLoading}
                      className="px-4 py-2 rounded-[10px] text-sm bg-surface border border-border text-text hover:bg-surface-hover transition-colors cursor-pointer disabled:opacity-50">
                      {fundingLoading ? <><Spinner className="w-3.5 h-3.5 mr-2" /> Checking...</> : "Check ckBTC"}
                    </button>
                    <button onClick={() => onCheckBalance(true)}
                      disabled={fundingLoading}
                      className="px-4 py-2 rounded-[10px] text-sm bg-surface border border-border text-text hover:bg-surface-hover transition-colors cursor-pointer disabled:opacity-50">
                      {fundingLoading ? <><Spinner className="w-3.5 h-3.5 mr-2" /> Checking...</> : "Check BTC + ckMinter"}
                    </button>
                  </div>
                  {fundingBalance && (
                    <div className="mt-2 text-xs space-x-3">
                      <span className={fundingBalance.balance_sats > 0 ? "text-green" : "text-dim"}>
                        ckBTC: {fundingBalance.balance_sats.toLocaleString()} sats
                      </span>
                      {fundingBalance.pending_sats > 0 && (
                        <span className="text-warning">Pending BTC: {fundingBalance.pending_sats.toLocaleString()} sats</span>
                      )}
                    </div>
                  )}
                  <div className="text-[0.7rem] text-dim mt-2">
                    Minimum deposit: {fmtSats(7500, btcUsd)}
                  </div>
                  <div className="mt-2">
                    <button
                      onClick={() => setFundingConfirmed(true)}
                      disabled={!(fundingBalance?.balance_sats >= 7500)}
                      className="px-5 py-2 rounded-[10px] text-sm bg-surface border border-border text-text hover:bg-surface-hover transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed">
                      Continue
                    </button>
                  </div>
                </div>
              )}
              {n === 3 && done && (
                <span className="text-[0.82rem] text-green">Funding acknowledged</span>
              )}

              {/* Step 4: Create bots */}
              {n === 4 && active && (
                <div className="text-sm text-dim leading-relaxed">
                  {!botLoading && (
                    <>
                      <div className="flex items-center gap-3 mt-2">
                        <label className="text-[0.82rem]">
                          Number of bots:{" "}
                          <input type="number" min={1} max={100} value={numBots}
                            onChange={(e) => {
                              const v = parseInt(e.target.value, 10);
                              setNumBots(Number.isFinite(v) ? Math.min(100, Math.max(1, v)) : 1);
                            }}
                            className="w-14 px-2 py-1 bg-bg border border-border rounded text-text text-sm" />
                        </label>
                      </div>
                      <div className="text-[0.7rem] text-dim mt-2 mb-3 leading-snug">
                        First-time bot registration: {numBots} bot{numBots !== 1 ? "s" : ""} = {fmtSats(totalFee, btcUsd)}.
                      </div>
                      <ActionBtn onClick={handleAddBots} loading={botLoading}>Create</ActionBtn>
                    </>
                  )}
                  {botLoading && (registerResults.length > 0 || registerProgress) && (
                    <div className="mt-2 space-y-1.5">
                      {registerResults.map((r) => (
                        <div key={r.botName} className="flex items-center gap-2 text-[0.82rem]">
                          {r.status === "ok"
                            ? <span className="text-green">{"\u2713"}</span>
                            : <span className="text-red">{"\u2717"}</span>}
                          <span className={r.status === "ok" ? "text-green" : "text-red"}>
                            {r.botName} {r.status === "ok" ? (r.already_registered ? "(already registered)" : "registered") : `failed: ${r.error}`}
                          </span>
                        </div>
                      ))}
                      {registerProgress && (
                        <div className="flex items-center gap-2 text-[0.82rem]">
                          <Spinner className="w-3.5 h-3.5" />
                          <span>Registering {registerProgress.botName} with Odin.Fun... ({registerProgress.current}/{registerProgress.total})</span>
                        </div>
                      )}
                    </div>
                  )}
                  {botLoading && !registerProgress && registerResults.length === 0 && (
                    <div className="flex items-center gap-2 mt-2 text-[0.82rem]">
                      <Spinner className="w-3.5 h-3.5" /> Writing bot configuration...
                    </div>
                  )}
                  <ResultBox result={botResult} />
                </div>
              )}
              {n === 4 && done && (
                <span className="text-[0.82rem] text-green">Bots added</span>
              )}

              {/* Step 5: Fund bots */}
              {n === 5 && active && (
                <div className="text-sm text-dim leading-relaxed">
                  {!fundLoading && (
                    <>
                      <div className="flex items-center gap-3 mt-2">
                        <label className="text-[0.82rem]">
                          Sats per bot:{" "}
                          <input type="number" min={5000} max={1000000} value={fundAmount}
                            onChange={(e) => {
                              const v = parseInt(e.target.value, 10);
                              setFundAmount(Number.isFinite(v) ? Math.max(5000, v) : 5000);
                            }}
                            className="w-20 px-2 py-1 bg-bg border border-border rounded text-text text-sm" />
                        </label>
                      </div>
                      <div className="text-[0.7rem] text-dim mt-2 mb-3 leading-snug">
                        Total: {fmtSats(fundAmount * botNames.length, btcUsd)} for {botNames.length} bot{botNames.length !== 1 ? "s" : ""}, keeping 1,000 sats in wallet for fees.
                      </div>
                      <ActionBtn onClick={handleFundBots} loading={fundLoading}>Fund</ActionBtn>
                    </>
                  )}
                  {fundLoading && (fundResults.length > 0 || fundProgress) && (
                    <div className="mt-2 space-y-1.5">
                      {fundResults.map((r) => (
                        <div key={r.botName} className="flex items-center gap-2 text-[0.82rem]">
                          {r.status === "ok"
                            ? <span className="text-green">{"\u2713"}</span>
                            : <span className="text-red">{"\u2717"}</span>}
                          <span className={r.status === "ok" ? "text-green" : "text-red"}>
                            {r.botName} {r.status === "ok" ? `funded ${fundAmount.toLocaleString()} sats` : `failed: ${r.error}`}
                          </span>
                        </div>
                      ))}
                      {fundProgress && (
                        <div className="flex items-center gap-2 text-[0.82rem]">
                          <Spinner className="w-3.5 h-3.5" />
                          <span>Funding {fundProgress.botName}... ({fundProgress.current}/{fundProgress.total})</span>
                        </div>
                      )}
                    </div>
                  )}
                  {fundLoading && !fundProgress && fundResults.length === 0 && (
                    <div className="flex items-center gap-2 mt-2 text-[0.82rem]">
                      <Spinner className="w-3.5 h-3.5" /> Preparing fund transfer...
                    </div>
                  )}
                  <ResultBox result={fundResult} />
                </div>
              )}
              {n === 5 && done && (
                <span className="text-[0.82rem] text-green">Bots funded</span>
              )}

              {/* Step 6: Ready */}
              {n === 6 && active && (
                <div className="text-sm text-green">Setup complete! Switching to Tokens view...</div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function ConfigureBotsCard({ funded, onRefresh, btcUsd }) {
  const [numBots, setNumBots] = useState(1);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [registerProgress, setRegisterProgress] = useState(null);
  const [registerResults, setRegisterResults] = useState([]);

  async function handleAddBots() {
    setLoading(true); setResult(null);
    setRegisterProgress(null); setRegisterResults([]);
    try {
      const res = await setupSetBots({ numBots });
      if (res.status === "error") {
        setResult(res);
        setLoading(false);
        return;
      }
      const botsToRegister = res.bots_added || [];
      if (botsToRegister.length === 0) {
        setResult(res);
        clearClientCache();
        if (onRefresh) onRefresh();
        setLoading(false);
        return;
      }

      const results = [];
      for (let i = 0; i < botsToRegister.length; i++) {
        const botName = botsToRegister[i];
        setRegisterProgress({ current: i + 1, total: botsToRegister.length, botName });
        try {
          const regRes = await setupRegisterBot({ botName });
          results.push({ botName, status: "ok", ...regRes });
        } catch (e) {
          results.push({ botName, status: "error", error: e.message });
        }
        setRegisterResults([...results]);
      }
      setRegisterProgress(null);

      const failures = results.filter(r => r.status === "error");
      if (failures.length === 0) {
        setResult({ status: "ok", display: `All ${botsToRegister.length} bot(s) registered with Odin.Fun.` });
        clearClientCache();
        if (onRefresh) onRefresh();
      } else {
        const failNames = failures.map(f => f.botName).join(", ");
        setResult({ status: "error", error: `Registration failed for: ${failNames}. Click Create to retry.` });
      }
    } catch (e) { setResult({ status: "error", error: e.message }); }
    finally { setLoading(false); }
  }

  const totalFee = numBots * 120;
  const disabled = !funded;

  return (
    <div className={`border rounded-[10px] p-5 mb-5 ${funded ? "bg-accent-dim border-accent/30" : "bg-surface border-border"}`}>
      <h4 className="text-sm font-bold mb-1">{funded ? "Ready to start trading?" : "Next step: Add trading bots"}</h4>
      <p className="text-xs text-dim mb-3">
        {funded
          ? "Configure your trading bots to start buying and selling Runes on Odin.fun."
          : "Fund your wallet first, then add bots to start trading. Each bot gets its own trading identity on Odin.fun."}
      </p>
      {!loading && (
        <>
          <div className={`flex items-center gap-3 mb-2 ${disabled ? "opacity-50" : ""}`}>
            <label className="text-[0.82rem]">
              Number of bots:{" "}
              <input type="number" min={1} max={100} value={numBots} disabled={disabled}
                onChange={(e) => {
                  const n = parseInt(e.target.value, 10);
                  setNumBots(Number.isFinite(n) ? Math.min(100, Math.max(1, n)) : 1);
                }}
                className="w-14 px-2 py-1 bg-bg border border-border rounded text-text text-sm disabled:opacity-50" />
            </label>
          </div>
          <div className="text-[0.7rem] text-dim mb-3 leading-snug">
            First-time bot registration: {numBots} bot{numBots !== 1 ? "s" : ""} = {fmtSats(totalFee, btcUsd)}.
          </div>
          <button onClick={handleAddBots} disabled={disabled || loading}
            className="px-5 py-2 rounded-[10px] text-sm bg-surface border border-border text-text hover:bg-surface-hover transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed">
            {disabled ? "Fund wallet first" : "Create"}
          </button>
        </>
      )}
      {loading && (registerResults.length > 0 || registerProgress) && (
        <div className="space-y-1.5">
          {registerResults.map((r) => (
            <div key={r.botName} className="flex items-center gap-2 text-[0.82rem]">
              {r.status === "ok"
                ? <span className="text-green">{"\u2713"}</span>
                : <span className="text-red">{"\u2717"}</span>}
              <span className={r.status === "ok" ? "text-green" : "text-red"}>
                {r.botName} {r.status === "ok" ? (r.already_registered ? "(already registered)" : "registered") : `failed: ${r.error}`}
              </span>
            </div>
          ))}
          {registerProgress && (
            <div className="flex items-center gap-2 text-[0.82rem]">
              <Spinner className="w-3.5 h-3.5" />
              <span>Registering {registerProgress.botName} with Odin.Fun... ({registerProgress.current}/{registerProgress.total})</span>
            </div>
          )}
        </div>
      )}
      {loading && !registerProgress && registerResults.length === 0 && (
        <div className="flex items-center gap-2 text-[0.82rem]">
          <Spinner className="w-3.5 h-3.5" /> Writing bot configuration...
        </div>
      )}
      <ResultBox result={result} />
    </div>
  );
}

function WalletSendCard({ onRefresh, ckbtcSats }) {
  const [expanded, setExpanded] = useState(false);
  const [address, setAddress] = useState("");
  const [amount, setAmount] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  async function handleSend() {
    setLoading(true); setResult(null);
    try {
      const res = await walletSend({ amount, address });
      setResult(res);
      if (res.status === "ok" && onRefresh) onRefresh();
    } catch (e) { setResult({ status: "error", error: e.message }); }
    finally { setLoading(false); }
  }

  function handleCancel() {
    setExpanded(false); setAddress(""); setAmount(""); setResult(null);
  }

  return (
    <div className="mb-5">
      <button onClick={() => { setExpanded((e) => !e); setResult(null); }}
        className="px-4 py-2 rounded-[10px] text-sm bg-surface border border-border text-text hover:bg-surface-hover transition-colors cursor-pointer inline-flex items-center gap-2">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <line x1="12" y1="5" x2="12" y2="19"/><polyline points="19 12 12 19 5 12"/>
        </svg>
        Send ckBTC / BTC
      </button>
      {expanded && (
        <div className="mt-2 bg-surface border border-border rounded-[10px] p-4">
          <div className="space-y-2">
            <label className="block text-[0.82rem]">
              Address (IC principal or BTC address)
              <input type="text" value={address} onChange={(e) => setAddress(e.target.value)}
                placeholder="bc1q... or xxxxx-xxxxx-..."
                className="mt-1 w-full px-3 py-1.5 bg-bg border border-border rounded text-text text-sm font-mono" />
            </label>
            <label className="block text-[0.82rem]">
              <span className="flex items-center gap-2">
                Amount (sats)
                {ckbtcSats > 0 && (
                  <button type="button"
                    onClick={() => setAmount("all")}
                    className="text-accent text-xs hover:underline cursor-pointer">
                    all
                  </button>
                )}
              </span>
              <input type="text" value={amount} onChange={(e) => setAmount(e.target.value)}
                placeholder="10000 or all"
                className="mt-1 w-32 px-3 py-1.5 bg-bg border border-border rounded text-text text-sm" />
            </label>
          </div>
          <div className="flex items-center gap-2 mt-3">
            <button onClick={handleSend} disabled={loading || !address || !amount}
              className="px-4 py-1.5 rounded-[10px] text-sm bg-surface border border-border text-text hover:bg-surface-hover transition-colors cursor-pointer disabled:opacity-50">
              {loading ? <><Spinner className="w-3.5 h-3.5 mr-2" /> Sending...</> : "Send"}
            </button>
            <button onClick={handleCancel} disabled={loading}
              className="px-4 py-1.5 rounded-[10px] text-sm text-dim hover:text-text transition-colors cursor-pointer disabled:opacity-50">
              Cancel
            </button>
          </div>
          <ResultBox result={result} />
        </div>
      )}
    </div>
  );
}

function WalletInfoCards({ btcUsd, data }) {
  if (!data) return <LoadingQuote message="Fetching your wallet from the Internet Computer..." />;

  return (
    <>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-base font-semibold">Wallet</h3>
      </div>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-3 mb-6">
        <StatCard
          label="ckBTC Balance"
          value={fmtSats(data.ckbtc_sats, btcUsd)}
          sub={data.ckbtc_usd != null ? `$${data.ckbtc_usd.toFixed(3)}` : null}
          help="Your trading funds. ckBTC is a 1:1 Bitcoin-backed token used for all trading on Odin.fun."
        />
        {data.pending_sats > 0 && (
          <StatCard label="Pending BTC" value={fmtSats(data.pending_sats, btcUsd)} sub="Awaiting ~6 Bitcoin confirmations" />
        )}
        <StatCard
          label="Wallet Principal"
          value={<AddressWithCopy value={data.principal} />}
          help="Your Internet Computer identity. Use this to receive ckBTC directly."
        />
        <StatCard
          label="BTC Deposit Address"
          value={<AddressWithCopy value={data.btc_address} />}
          sub={<a href={`https://mempool.space/address/${data.btc_address}`} target="_blank" rel="noopener noreferrer">View on mempool.space</a>}
          help="Send native BTC here to fund your wallet. After ~6 confirmations it auto-converts to ckBTC."
        />
      </div>
    </>
  );
}

export default function WalletView({ btcUsd, data: balanceData, loading: balanceLoading, onRefresh, onCheckBalance, onNavigate, projectRoot, onSetupComplete }) {
  const projectName = projectRoot ? (projectRoot.split("/").pop() || "") : "";
  const [setupDone, setSetupDone] = useState(null);
  const [status, setStatus] = useState(null);
  const [statusError, setStatusError] = useState(null);
  const prevSetupDone = useRef(null);

  const checkStatus = useCallback(() => {
    setStatusError(null);
    getWalletStatus()
      .then((s) => {
        setStatus(s);
        const done = s.sdk_available && s.config_exists && s.wallet_exists && (s.bot_count || 0) > 0;
        setSetupDone(done);
      })
      .catch((e) => { setStatus(null); setSetupDone(false); setStatusError(e?.message || "Unable to reach wallet status endpoint."); });
  }, []);
  useEffect(() => { checkStatus(); }, [checkStatus]);

  // Notify parent when setup transitions to complete
  useEffect(() => {
    if (prevSetupDone.current === false && setupDone === true) {
      onSetupComplete?.();
    }
    prevSetupDone.current = setupDone;
  }, [setupDone, onSetupComplete]);

  if (setupDone === null) return <LoadingQuote message="Checking setup..." />;
  if (statusError) return (
    <div className="bg-red-dim border border-red rounded-[10px] px-4 py-3 text-sm text-red">
      {statusError}
      <button className="ml-3 underline cursor-pointer" onClick={checkStatus}>retry</button>
    </div>
  );
  if (!setupDone && status) return <SetupWizard status={status} onComplete={checkStatus} onCheckBalance={onCheckBalance} onNavigate={onNavigate} balanceData={balanceData} balanceLoading={balanceLoading} projectName={projectName} btcUsd={btcUsd} />;

  const walletFunded = (balanceData?.wallet?.ckbtc_sats || 0) > 0;
  const botCount = (balanceData?.bots || []).length;

  return (
    <>
      <WalletInfoCards btcUsd={btcUsd} data={balanceData?.wallet} />

      {botCount === 0 && <ConfigureBotsCard funded={walletFunded} onRefresh={onRefresh} btcUsd={btcUsd} />}

      <WalletSendCard onRefresh={onRefresh} ckbtcSats={balanceData?.wallet?.ckbtc_sats} />

      <div className="bg-surface border border-border rounded-[10px] p-4 mb-5">
        <h4 className="text-sm font-semibold mb-2">How funding works</h4>
        <div className="text-xs text-dim leading-relaxed space-y-1">
          <div><span className="text-accent font-medium">1.</span> Send BTC to your <span className="text-text">BTC Deposit Address</span> above (min 10,000 sats). After ~6 confirmations it becomes ckBTC in your wallet.</div>
          <div><span className="text-accent font-medium">2.</span> Use the <span className="text-text">Chat</span> tab to fund your bots: <code className="text-accent">"fund bot-1 with 10000 sats"</code></div>
          <div><span className="text-accent font-medium">3.</span> Trade via Chat: <code className="text-accent">"buy 5000 sats of ICONFUCIUS on bot-1"</code></div>
        </div>
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <DownloadBackupButton projectName={projectName} />
        <ImportWalletButton onImported={checkStatus} />
        <span className="text-xs text-dim">Keep your wallet backup in a safe place</span>
      </div>
    </>
  );
}
