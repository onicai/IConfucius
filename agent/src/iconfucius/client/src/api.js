const ODIN = "/api/odin";
const WALLET = "/api/wallet";

async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || `API ${res.status}: ${res.statusText}`);
  }
  return res.json();
}

async function postJSON(url, body = {}) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.error || `API ${res.status}`);
    if (data.status_url) err.statusUrl = data.status_url;
    throw err;
  }
  return data;
}

// Odin.fun endpoints
export async function getTokens({ sort = "volume:desc", limit = 20 } = {}) {
  return fetchJSON(`${ODIN}/tokens?limit=${limit}&sort=${sort}`);
}

export async function getToken(id) {
  return fetchJSON(`${ODIN}/token/${id}`);
}

export async function getTrades({ limit = 20 } = {}) {
  return fetchJSON(`${ODIN}/trades?limit=${limit}`);
}

export async function searchTokens(query) {
  return fetchJSON(`${ODIN}/search?q=${encodeURIComponent(query)}`);
}

// Wallet endpoints
export async function getWalletInfo({ refresh = false, ckbtcMinter = false } = {}) {
  const params = [];
  if (refresh) params.push("refresh");
  if (ckbtcMinter) params.push("ckbtc_minter");
  const qs = params.length ? `?${params.join("&")}` : "";
  return fetchJSON(`${WALLET}/info${qs}`);
}

export async function getWalletBalances({ refresh = false, ckbtcMinter = false } = {}) {
  const params = [];
  if (refresh) params.push("refresh");
  if (ckbtcMinter) params.push("ckbtc_minter");
  const qs = params.length ? `?${params.join("&")}` : "";
  return fetchJSON(`${WALLET}/balances${qs}`);
}

export async function getWalletTrades() {
  return fetchJSON(`${WALLET}/trades`);
}

export async function importWallet(pemText) {
  return postJSON(`${WALLET}/import`, { pem: pemText });
}

export async function getWalletStatus() {
  return fetchJSON(`${WALLET}/status`);
}

// Setup action endpoints
export async function setupInit({ numBots = 3, force = false } = {}) {
  return postJSON("/api/setup/init", { num_bots: numBots, force });
}

export async function setupWalletCreate({ force = false } = {}) {
  return postJSON("/api/setup/wallet-create", { force });
}

export async function setupSetBots({ numBots, force = false }) {
  return postJSON("/api/setup/set-bots", { num_bots: numBots, force });
}

export async function setupRegisterBot({ botName }) {
  return postJSON("/api/setup/register-bot", { bot_name: botName });
}

export async function setupFundBot({ botName, amount }) {
  return postJSON("/api/setup/fund-bot", { bot_name: botName, amount });
}

export async function walletWithdraw({ botName, amount }) {
  return postJSON("/api/wallet/withdraw", { bot_name: botName, amount });
}

export async function walletSend({ amount, address }) {
  return postJSON("/api/wallet/send", { amount, address });
}

// Chat endpoints
export async function chatStart({ apiKey, persona, model } = {}) {
  return postJSON("/api/chat/start", { api_key: apiKey, persona, model });
}

export async function chatResume({ apiKey, persona, model } = {}) {
  return postJSON("/api/chat/resume", { api_key: apiKey, persona, model });
}

export async function chatMessage({ sessionId, text }) {
  return postJSON("/api/chat/message", { session_id: sessionId, text });
}

export async function chatConfirm({ sessionId, approved }) {
  return postJSON("/api/chat/confirm", { session_id: sessionId, approved });
}

export async function chatSettings({ apiKey }) {
  return postJSON("/api/chat/settings", { api_key: apiKey });
}

export async function getChatHealth() {
  return fetchJSON("/api/chat/health");
}

export async function getOdinHealth() {
  return fetchJSON("/api/odin/health");
}

// External
export async function getBtcPrice() {
  const res = await fetch(
    "https://api.coinbase.com/v2/exchange-rates?currency=BTC",
  );
  if (!res.ok) return null;
  try {
    const data = await res.json();
    const usd = data?.data?.rates?.USD;
    return usd ? parseFloat(usd) : null;
  } catch {
    return null;
  }
}
