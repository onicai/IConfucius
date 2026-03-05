import { useState, useRef, useEffect, useCallback } from "react";
import { chatStart, chatMessage, chatConfirm, chatSettings, chatResume } from "../api";
import { useI18n } from "../i18n";

const STORAGE_KEY = "iconfucius_chat_messages";
const SESSION_KEY = "iconfucius_chat_session";

const Spinner = ({ className = "" }) => (
  <span className={`inline-block w-4 h-4 border-2 border-border border-t-accent rounded-full animate-spin align-middle ${className}`} />
);

function loadSavedMessages() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]"); }
  catch { return []; }
}
function saveMessages(msgs) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(msgs)); } catch {}
}

function ApiKeyForm({ onSaved }) {
  const { t } = useI18n();
  const [key, setKey] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!key.trim()) return;
    setSaving(true); setError(null);
    try {
      await chatSettings({ apiKey: key.trim() });
      onSaved(key.trim());
    } catch (err) { setError(err.message); }
    finally { setSaving(false); }
  }

  return (
    <div className="flex-1 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <h3 className="text-sm font-bold mb-1">{t("chat.api_title")}</h3>
        <p className="text-xs text-dim mb-3">
          {t("chat.api_desc")}{" "}
          <a href="https://console.anthropic.com/settings/keys" target="_blank" rel="noopener noreferrer">{t("chat.api_link")}</a>
        </p>
        <form onSubmit={handleSubmit} className="flex gap-1.5">
          <input
            type="password" value={key} onChange={(e) => setKey(e.target.value)}
            placeholder={t("chat.api_placeholder")}
            className="flex-1 min-w-0 px-2.5 py-2 bg-bg border border-border rounded-lg text-text text-xs outline-none focus:border-accent"
          />
          <button type="submit" disabled={saving}
            className="px-3 py-2 rounded-lg text-xs bg-accent text-bg font-semibold hover:opacity-90 transition-opacity cursor-pointer disabled:opacity-50 shrink-0">
            {saving ? t("chat.api_saving") : t("chat.api_save")}
          </button>
        </form>
        {error && <div className="mt-2 text-xs text-red">{error}</div>}
      </div>
    </div>
  );
}

function ConfirmBanner({ tools, onConfirm, loading }) {
  const { t } = useI18n();
  return (
    <div className="mx-3 mb-2 bg-accent-dim border border-accent rounded-xl p-3">
      <div className="text-xs font-semibold text-accent mb-1.5">{t("chat.confirm_title")}</div>
      {tools.map((tool, i) => (
        <div key={i} className="text-xs text-text mb-0.5">&bull; {tool.description}</div>
      ))}
      <div className="flex gap-1.5 mt-2">
        <button onClick={() => onConfirm(true)} disabled={loading}
          className="px-3 py-1 rounded-lg text-xs bg-green text-bg font-semibold hover:opacity-90 transition-opacity cursor-pointer disabled:opacity-50">
          {loading ? <><Spinner className="w-3 h-3 mr-1" /> ...</> : t("chat.approve")}
        </button>
        <button onClick={() => onConfirm(false)} disabled={loading}
          className="px-3 py-1 rounded-lg text-xs bg-red text-bg font-semibold hover:opacity-90 transition-opacity cursor-pointer disabled:opacity-50">
          {t("chat.decline")}
        </button>
      </div>
    </div>
  );
}

function MessageBubble({ role, text }) {
  const isUser = role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-2`}>
      <div className={`max-w-[85%] px-3 py-2 rounded-xl text-xs leading-relaxed whitespace-pre-wrap ${
        isUser
          ? "bg-surface-hover text-text rounded-br-sm"
          : "bg-accent-dim text-text border border-accent/15 rounded-bl-sm font-mono"
      }`}>
        {text}
      </div>
    </div>
  );
}

export default function ChatPanel({ onAction, focusSignal = 0, onChatStatus }) {
  const { t } = useI18n();
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState(loadSavedMessages);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [confirmData, setConfirmData] = useState(null);
  const [confirmLoading, setConfirmLoading] = useState(false);
  const [needsKey, setNeedsKey] = useState(null);
  const [error, setError] = useState(null);
  const [statusUrl, setStatusUrl] = useState(null);
  const [starting, setStarting] = useState(false);
  const bottomRef = useRef(null);
  const inputRef = useRef(null);
  const isInitialMount = useRef(true);

  const scrollToBottom = useCallback(() => {
    if (isInitialMount.current) {
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          if (bottomRef.current) {
            bottomRef.current.scrollIntoView({ behavior: "instant" });
            isInitialMount.current = false;
          }
        });
      });
    } else {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, []);

  useEffect(scrollToBottom, [messages, confirmData, starting, scrollToBottom]);
  useEffect(() => { saveMessages(messages); }, [messages]);
  useEffect(() => { if (!loading && !confirmLoading && sessionId) inputRef.current?.focus(); }, [loading, confirmLoading, sessionId]);
  useEffect(() => {
    if (!sessionId || loading || confirmLoading) return;
    requestAnimationFrame(() => inputRef.current?.focus({ preventScroll: true }));
  }, [focusSignal, sessionId, loading, confirmLoading]);

  async function startSession(apiKey) {
    setStarting(true); setError(null); setNeedsKey(false);
    try {
      const res = await chatStart({ apiKey });
      setSessionId(res.session_id);
      onChatStatus?.(true);
      try { sessionStorage.setItem(SESSION_KEY, res.session_id); } catch {}
    } catch (err) {
      if (err.message?.includes("API key") || err.message?.includes("ANTHROPIC_API_KEY")) {
        setNeedsKey(true);
      } else {
        setError(err.message);
        if (err.statusUrl) setStatusUrl(err.statusUrl);
        onChatStatus?.(false);
      }
    } finally { setStarting(false); }
  }

  async function resumeOrStart(apiKey) {
    setStarting(true); setError(null); setNeedsKey(false);
    try {
      const res = await chatResume({ apiKey });
      if (res.resumed) {
        setSessionId(res.session_id);
        if (res.messages?.length) {
          setMessages(res.messages);
          saveMessages(res.messages);
        }
        onChatStatus?.(true);
        try { sessionStorage.setItem(SESSION_KEY, res.session_id); } catch {}
      } else {
        setMessages([]);
        saveMessages([]);
        await startSession(apiKey);
        return;
      }
    } catch (err) {
      if (err.message?.includes("API key") || err.message?.includes("ANTHROPIC_API_KEY")) {
        setNeedsKey(true);
      } else {
        setMessages([]);
        saveMessages([]);
        try { await startSession(apiKey); return; } catch { /* handled by startSession */ }
      }
    } finally { setStarting(false); }
  }

  useEffect(() => {
    const saved = sessionStorage.getItem(SESSION_KEY);
    if (saved) {
      setSessionId(saved);
    } else {
      resumeOrStart();
    }
  }, []);

  function addMessages(newMsgs) {
    setMessages((prev) => {
      const updated = [...prev, ...newMsgs];
      saveMessages(updated);
      return updated;
    });
  }

  function handleResponse(res) {
    if (res.type === "confirm") {
      setConfirmData(res.tools);
    } else if (res.type === "response") {
      addMessages([{ role: "assistant", text: res.text }]);
      setConfirmData(null);
    }
    onChatStatus?.(true);
    setStatusUrl(null);
  }

  async function handleSend(e) {
    e.preventDefault();
    const text = input.trim();
    if (!text || !sessionId || loading) return;
    setInput("");
    addMessages([{ role: "user", text }]);
    setLoading(true); setError(null); setConfirmData(null);
    try {
      const res = await chatMessage({ sessionId, text });
      handleResponse(res);
    } catch (err) {
      if (err.message?.includes("session") || err.message?.includes("Session")) {
        sessionStorage.removeItem(SESSION_KEY);
        setSessionId(null);
        startSession();
        setError(t("chat.session_expired"));
      } else {
        setError(err.message);
        if (err.statusUrl) setStatusUrl(err.statusUrl);
        onChatStatus?.(false);
      }
    }
    finally { setLoading(false); inputRef.current?.focus(); }
  }

  async function handleConfirm(approved) {
    setConfirmLoading(true); setError(null);
    try {
      const res = await chatConfirm({ sessionId, approved });
      handleResponse(res);
      if (approved && onAction) onAction();
    } catch (err) {
      setError(err.message);
      if (err.statusUrl) setStatusUrl(err.statusUrl);
      onChatStatus?.(false);
    }
    finally { setConfirmLoading(false); inputRef.current?.focus(); }
  }

  function handleClear() {
    if (loading || confirmLoading || starting) return;
    setMessages([]);
    setConfirmData(null);
    setError(null);
    setStatusUrl(null);
    setInput("");
    localStorage.removeItem(STORAGE_KEY);
    sessionStorage.removeItem(SESSION_KEY);
    setSessionId(null);
    startSession();
  }

  if (needsKey) return <ApiKeyForm onSaved={(key) => startSession(key)} />;

  if (starting) {
    return (
      <div className="flex-1 flex items-center justify-center text-dim text-xs">
        <Spinner className="mr-2" /> {t("chat.connecting")}
      </div>
    );
  }

  if (!sessionId && error) {
    return (
      <div className="flex-1 flex items-center justify-center p-4">
        <div className="text-center">
          <div className="text-xs text-red mb-2">{error}</div>
          <button onClick={() => startSession()}
            className="px-3 py-1.5 rounded-lg text-xs bg-surface border border-border text-text hover:bg-surface-hover cursor-pointer">
            {t("chat.retry")}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col min-h-0 w-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto scrollbar-thin px-3 py-3">
        {messages.length === 0 && !loading && (
          <div className="text-center py-8 text-dim text-xs leading-relaxed">
            <div className="text-accent text-base mb-2">&#x5b54;</div>
            {t("chat.empty_title")}
            <br />
            <span className="text-[0.65rem]">{t("chat.empty_hint")}</span>
          </div>
        )}
        {messages.map((m, i) => (
          <MessageBubble key={i} role={m.role} text={m.text} />
        ))}
        {loading && (
          <div className="flex justify-start mb-2">
            <div className="bg-accent-dim text-dim border border-accent/15 rounded-xl rounded-bl-sm px-3 py-2 text-xs">
              <Spinner className="w-3 h-3 mr-1.5" /> {t("chat.thinking")}
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Confirmation banner */}
      {confirmData && (
        <ConfirmBanner tools={confirmData} onConfirm={handleConfirm} loading={confirmLoading} />
      )}

      {/* Error */}
      {error && sessionId && (
        <div className="px-3 pb-1 text-xs text-red">
          {error}
          {statusUrl && (
            <>
              {" "}
              <a href={statusUrl} target="_blank" rel="noopener noreferrer"
                className="underline text-accent hover:text-accent/80">
                {t("chat.check_status")}
              </a>
            </>
          )}
        </div>
      )}

      {/* Input */}
      <form onSubmit={handleSend} className="shrink-0 flex gap-1.5 px-3 pb-3 pt-2 border-t border-border">
        <input
          ref={inputRef}
          type="text" value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={t("chat.placeholder")}
          disabled={loading || confirmLoading || !sessionId}
          className="flex-1 min-w-0 px-3 py-2 bg-surface border border-border rounded-lg text-text text-xs outline-none focus:border-accent disabled:opacity-50"
        />
        <button type="submit" aria-label="Send message" disabled={loading || confirmLoading || !sessionId || !input.trim()}
          className="px-3 py-2 rounded-lg text-xs bg-accent text-bg font-semibold hover:opacity-90 transition-opacity cursor-pointer disabled:opacity-50 shrink-0">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
          </svg>
        </button>
      </form>

      {/* New Chat */}
      <div className="shrink-0 text-center pb-2">
        <button onClick={handleClear}
          className="text-[0.65rem] text-dim hover:text-text transition-colors cursor-pointer">
          {t("chat.new_chat")}
        </button>
      </div>
    </div>
  );
}
