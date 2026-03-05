import { useState, useEffect } from "react";
import { useI18n } from "../i18n";

function pickQuote(quotes, prev) {
  if (!quotes.length) return "";
  let idx;
  do { idx = Math.floor(Math.random() * quotes.length); }
  while (quotes.length > 1 && quotes[idx] === prev);
  return quotes[idx];
}

export default function LoadingQuote({ message }) {
  const { t, tArray } = useI18n();
  const quotes = tArray("loading.quote");
  const [quote, setQuote] = useState(() => pickQuote(quotes, ""));

  useEffect(() => {
    const interval = setInterval(() => {
      setQuote((prev) => pickQuote(quotes, prev));
    }, 4500);
    return () => clearInterval(interval);
  }, [quotes]);

  return (
    <div className="flex flex-col items-center justify-center py-16 gap-4 max-w-md mx-auto text-center">
      <div className="text-4xl opacity-20 leading-none">&#x5B54;</div>
      <div className="flex items-center gap-2 text-dim text-sm">
        <span className="inline-block w-4 h-4 border-2 border-border border-t-accent rounded-full animate-spin" />
        {message || t("loading.default")}
      </div>
      <p className="text-xs text-dim/70 italic leading-relaxed transition-opacity duration-500">
        &ldquo;{quote}&rdquo;
      </p>
      <p className="text-[0.6rem] text-dim/40">{t("loading.signature")}</p>
    </div>
  );
}
