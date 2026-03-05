import { useState, useEffect, useCallback } from "react";
import { getWalletStatus, setupInit, setupWalletCreate, importWallet } from "../api";
import LoadingQuote from "../components/LoadingQuote";
import { useI18n } from "../i18n";
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

function ResultBox({ result, doneLabel }) {
  if (!result) return null;
  const err = result.status === "error";
  return (
    <div className={`mt-2.5 px-3.5 py-2.5 rounded-md text-[0.82rem] whitespace-pre-wrap leading-relaxed border ${err ? "bg-red-dim text-red border-red" : "bg-green-dim text-green border-green"}`}>
      {result.display || result.error || doneLabel || "Done"}
    </div>
  );
}

function truncateMiddle(text, head = 8, tail = 8) {
  if (!text || text.length <= head + tail + 3) return text || "";
  return `${text.slice(0, head)}...${text.slice(-tail)}`;
}

function AddressWithCopy({ value }) {
  const { t } = useI18n();
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
        {copied ? t("wallet.copied") : t("wallet.copy")}
      </button>
    </div>
  );
}

function DownloadBackupButton({ className = "" }) {
  const { t } = useI18n();
  return (
    <button onClick={() => { const a = document.createElement("a"); a.href = "/api/wallet/backup"; a.download = "iconfucius-identity-private.pem"; a.click(); }}
      className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium bg-accent-dim text-accent border border-accent/30 hover:bg-accent/20 transition-colors cursor-pointer ${className}`}>
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
      </svg>
      {t("wallet.download_backup")}
    </button>
  );
}

function ImportWalletButton({ onImported, className = "" }) {
  const { t } = useI18n();
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
        {loading ? t("wallet.importing") : t("wallet.import_wallet")}
        <input type="file" accept=".pem" className="hidden"
          onChange={(e) => { if (e.target.files[0]) handleFile(e.target.files[0]); e.target.value = ""; }} />
      </label>
      {error && <div className="text-xs text-red mt-1">{error}</div>}
    </span>
  );
}

function SetupWizard({ status, onComplete }) {
  const { t } = useI18n();
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
  async function handleImport(file) {
    if (walletLoading) return;
    setWalletLoading(true); setWalletResult(null);
    try {
      const text = await file.text();
      setWalletResult(await importWallet(text));
    } catch (e) { setWalletResult({ status: "error", error: e.message }); }
    finally { setWalletLoading(false); }
  }

  useEffect(() => {
    if (configDone && walletDone && !sdkMissing) {
      const timer = setTimeout(onComplete, 1500);
      return () => clearTimeout(timer);
    }
  }, [configDone, walletDone, sdkMissing, onComplete]);

  const ActionBtn = ({ onClick, loading: l, children }) => (
    <button onClick={onClick} disabled={l}
      className="mt-3 px-5 py-2 rounded-[10px] text-sm bg-surface border border-border text-text hover:bg-surface-hover transition-colors cursor-pointer disabled:opacity-50">
      {l ? <><Spinner className="w-3.5 h-3.5 mr-2" /> {t("setup.running")}</> : children}
    </button>
  );

  return (
    <div className="bg-surface border border-border rounded-[10px] p-6 max-w-xl">
      <div className="flex items-center justify-between mb-1">
        <h3 className="text-lg font-bold">{t("setup.title")}</h3>
        <button onClick={onComplete}
          className="text-xs text-dim hover:text-text transition-colors cursor-pointer px-2 py-1 rounded hover:bg-surface-hover">
          {t("setup.refresh")}
        </button>
      </div>
      <p className="text-sm text-dim mb-5">{sdkMissing ? t("setup.sdk_desc") : t("setup.steps_desc")}</p>

      {sdkMissing && (
        <div className="flex gap-3.5 py-4 border-b border-border">
          <StepCircle number={0} done={false} active />
          <div>
            <div className="font-semibold mb-1">{t("setup.install_sdk")}</div>
            <div className="text-sm text-dim leading-relaxed">
              {t("setup.run_from_root")}
              <pre className="bg-bg border border-border rounded-md px-3.5 py-2.5 text-[0.82rem] mt-2 text-accent">pip install -e agent/</pre>
              {t("setup.restart_proxy")}
            </div>
          </div>
        </div>
      )}

      {!sdkMissing && (
        <div className={`flex gap-3.5 py-4 border-b border-border ${configDone && activeStep !== 1 ? "opacity-50" : ""}`}>
          <StepCircle number={1} done={configDone} active={activeStep === 1} />
          <div className="flex-1">
            <div className="font-semibold mb-1">{t("setup.step_init")}</div>
            {activeStep === 1 && (
              <div className="text-sm text-dim leading-relaxed">
                {t("setup.init_desc")}
                <div className="flex items-center gap-3 mt-2.5">
                  <label className="text-[0.82rem]">
                    {t("setup.bots_label")}{" "}
                    <input type="number" min={1} max={100} value={numBots}
                      onChange={(e) => {
                        const n = parseInt(e.target.value, 10);
                        setNumBots(Number.isFinite(n) ? Math.min(100, Math.max(1, n)) : 1);
                      }}
                      className="w-14 px-2 py-1 bg-bg border border-border rounded text-text text-sm" />
                  </label>
                </div>
                <ActionBtn onClick={handleInit} loading={initLoading}>{t("setup.init_btn")}</ActionBtn>
                <ResultBox result={initResult} doneLabel={t("setup.done")} />
              </div>
            )}
            {configDone && activeStep !== 1 && <div className="text-[0.82rem] text-green">{t("setup.init_done")}</div>}
          </div>
        </div>
      )}

      {!sdkMissing && (
        <div className={`flex gap-3.5 py-4 border-b border-border ${activeStep < 2 ? "opacity-40" : walletDone && activeStep !== 2 ? "opacity-50" : ""}`}>
          <StepCircle number={2} done={walletDone} active={activeStep === 2} />
          <div className="flex-1">
            <div className="font-semibold mb-1">{t("setup.step_wallet")}</div>
            {activeStep === 2 && (
              <div className="text-sm text-dim leading-relaxed">
                <div className="mt-2 px-3 py-2 bg-red-dim border border-red rounded-md text-xs text-red font-medium">
                  {t("setup.wallet_warning")}
                </div>
                <div className="flex items-center gap-2 mt-3">
                  <ActionBtn onClick={handleWalletCreate} loading={walletLoading}>{t("setup.create_btn")}</ActionBtn>
                  <span className="text-xs text-dim">{t("setup.or")}</span>
                  <label className="mt-3 px-5 py-2 rounded-[10px] text-sm bg-surface border border-border text-text hover:bg-surface-hover transition-colors cursor-pointer inline-flex items-center gap-1.5">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
                    </svg>
                    {t("setup.import_btn")}
                    <input type="file" accept=".pem" className="hidden" disabled={walletLoading}
                      onChange={(e) => { if (e.target.files?.[0]) handleImport(e.target.files[0]); e.target.value = ""; }} />
                  </label>
                </div>
                <ResultBox result={walletResult} doneLabel={t("setup.done")} />
                {walletDone && <DownloadBackupButton className="mt-2" />}
              </div>
            )}
            {walletDone && activeStep !== 2 && (
              <div className="flex items-center gap-3">
                <span className="text-[0.82rem] text-green">{t("setup.wallet_ready")}</span>
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
            <div className="font-semibold mb-1">{t("setup.step_ready")}</div>
            {activeStep === 3 && <div className="text-sm text-green">{t("setup.complete")}</div>}
          </div>
        </div>
      )}
    </div>
  );
}

function WalletInfoCards({ btcUsd, data, loading, onRefresh }) {
  const { t } = useI18n();
  if (!data) return <LoadingQuote message={t("wallet.loading")} />;

  return (
    <>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-base font-semibold">{t("wallet.title")}</h3>
        <button onClick={onRefresh} disabled={loading}
          className="px-3 py-1.5 rounded-lg text-xs bg-surface border border-border text-dim hover:text-text hover:bg-surface-hover transition-colors cursor-pointer disabled:opacity-50">
          {loading ? <><Spinner className="w-3 h-3 mr-1" /> {t("wallet.refreshing")}</> : t("wallet.refresh")}
        </button>
      </div>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-3 mb-6">
        <StatCard
          label={t("wallet.ckbtc_balance")}
          value={fmtSats(data.ckbtc_sats, btcUsd)}
          sub={data.ckbtc_usd != null ? `$${data.ckbtc_usd.toFixed(3)}` : null}
          help={t("wallet.ckbtc_help")}
        />
        {data.pending_sats > 0 && (
          <StatCard label={t("wallet.pending_btc")} value={fmtSats(data.pending_sats, btcUsd)} sub={t("wallet.pending_sub")} />
        )}
        <StatCard
          label={t("wallet.principal")}
          value={<AddressWithCopy value={data.principal} />}
          help={t("wallet.principal_help")}
        />
        <StatCard
          label={t("wallet.btc_address")}
          value={<AddressWithCopy value={data.btc_address} />}
          sub={<a href={`https://mempool.space/address/${data.btc_address}`} target="_blank" rel="noopener noreferrer">{t("wallet.btc_link")}</a>}
          help={t("wallet.btc_help")}
        />
      </div>
    </>
  );
}

export default function WalletView({ btcUsd, data: balanceData, loading: balanceLoading, onRefresh }) {
  const { t } = useI18n();
  const [setupDone, setSetupDone] = useState(null);
  const [status, setStatus] = useState(null);
  const [statusError, setStatusError] = useState(null);

  const checkStatus = useCallback(() => {
    setStatusError(null);
    getWalletStatus()
      .then((s) => { setStatus(s); setSetupDone(s.sdk_available && s.config_exists && s.wallet_exists); })
      .catch((e) => { setStatus(null); setSetupDone(false); setStatusError(e?.message || "Error"); });
  }, []);
  useEffect(() => { checkStatus(); }, [checkStatus]);

  if (setupDone === null) return <LoadingQuote message={t("wallet.checking")} />;
  if (statusError) return (
    <div className="bg-red-dim border border-red rounded-[10px] px-4 py-3 text-sm text-red">
      {statusError}
      <button className="ml-3 underline cursor-pointer" onClick={checkStatus}>{t("app.error_retry")}</button>
    </div>
  );
  if (!setupDone && status) return <SetupWizard status={status} onComplete={checkStatus} />;

  return (
    <>
      <WalletInfoCards btcUsd={btcUsd} data={balanceData?.wallet} loading={balanceLoading} onRefresh={onRefresh} />

      <div className="bg-surface border border-border rounded-[10px] p-4 mb-5">
        <h4 className="text-sm font-semibold mb-2">{t("wallet.funding_title")}</h4>
        <div className="text-xs text-dim leading-relaxed space-y-1">
          <div><span className="text-accent font-medium">1.</span> {t("wallet.funding_1")}</div>
          <div><span className="text-accent font-medium">2.</span> {t("wallet.funding_2")}</div>
          <div><span className="text-accent font-medium">3.</span> {t("wallet.funding_3")}</div>
        </div>
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <DownloadBackupButton />
        <ImportWalletButton onImported={checkStatus} />
        <span className="text-xs text-dim">{t("wallet.backup_reminder")}</span>
      </div>
    </>
  );
}
