import { useState, useEffect } from "react";

const QUOTES = [
  "The patient trader profits twice — once in wisdom, once in sats.",
  "A journey of a thousand trades begins with a single canister call.",
  "He who chases green candles catches only smoke.",
  "To know what you hold and what you do not hold — that is true knowledge.",
  "The blockchain does not hurry, yet everything is confirmed.",
  "Buy when there is blood in the mempool, sell when there are tweets.",
  "Before you trade a rune, first understand the rune. Then trade it anyway.",
  "The wise bot waits for the dip. The wiser bot was already in.",
  "It does not matter how slowly your transaction goes, as long as you do not get MEV'd.",
  "When the market is red, the sage is accumulating.",
  "A sats saved is a sats earned. A sats spent on runes is a lifestyle.",
  "Study the past candles if you would define the future candles.",
  "The superior trader is modest in his speech but exceeds in his PnL.",
  "Real knowledge is to know the extent of one's rug-pull exposure.",
  "Choose a rune you love, and you will never work a day in your life.",
];

function pickQuote(prev) {
  let idx;
  do { idx = Math.floor(Math.random() * QUOTES.length); }
  while (QUOTES.length > 1 && QUOTES[idx] === prev);
  return QUOTES[idx];
}

export default function LoadingQuote({ message = "Loading..." }) {
  const [quote, setQuote] = useState(() => pickQuote(""));

  useEffect(() => {
    const interval = setInterval(() => {
      setQuote((prev) => pickQuote(prev));
    }, 4500);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex flex-col items-center justify-center py-16 gap-4 max-w-md mx-auto text-center">
      <div className="text-4xl opacity-20 leading-none">&#x5B54;</div>
      <div className="flex items-center gap-2 text-dim text-sm">
        <span className="inline-block w-4 h-4 border-2 border-border border-t-accent rounded-full animate-spin" />
        {message}
      </div>
      <p className="text-xs text-dim/70 italic leading-relaxed transition-opacity duration-500">
        "{quote}"
      </p>
      <p className="text-[0.6rem] text-dim/40">— iConfucius</p>
    </div>
  );
}
