import { Actor, HttpAgent } from '@icp-sdk/core/agent';
import { Ed25519KeyIdentity } from '@icp-sdk/core/identity';

const CANISTER_ID =
  import.meta.env.VITE_ICONFUCIUS_CANISTER_ID ?? 'dpljb-diaaa-aaaaa-qafsq-cai';
const HOST = 'https://icp0.io';

// Minimal hand-written subset of the iconfucius_ctrlb_canister interface.
// Shapes mirror src/common/Types.mo; Candid structural subtyping makes a
// partial service definition valid against the deployed canister.
const idlFactory = ({ IDL }) => {
  const ApiError = IDL.Variant({
    Unauthorized: IDL.Null,
    InvalidId: IDL.Null,
    ZeroAddress: IDL.Null,
    FailedOperation: IDL.Null,
    Other: IDL.Text,
    StatusCode: IDL.Nat16,
    InsuffientCycles: IDL.Nat, // sic — must match the backend spelling
  });
  const QuoteLanguage = IDL.Variant({ English: IDL.Null, Chinese: IDL.Null });
  const TextResult = IDL.Variant({ Ok: IDL.Text, Err: ApiError });
  const StatusCodeRecordResult = IDL.Variant({
    Ok: IDL.Record({ status_code: IDL.Nat16 }),
    Err: ApiError,
  });
  const FlagResult = IDL.Variant({
    Ok: IDL.Record({ flag: IDL.Bool }),
    Err: ApiError,
  });
  return IDL.Service({
    IConfuciusSays: IDL.Func([QuoteLanguage, IDL.Text], [TextResult], []),
    getPauseIconfuciusFlag: IDL.Func([], [FlagResult], ['query']),
    health: IDL.Func([], [StatusCodeRecordResult], ['query']),
    whoami: IDL.Func([], [IDL.Principal], ['query']),
  });
};

// Ephemeral non-anonymous identity, regenerated on every page load.
// IConfuciusSays rejects anonymous callers but accepts any principal.
const identity = Ed25519KeyIdentity.generate();

const agent = HttpAgent.createSync({ host: HOST, identity });

export const actor = Actor.createActor(idlFactory, {
  agent,
  canisterId: CANISTER_ID,
});

const ERROR_STRINGS = {
  English: {
    unauthorized: 'The canister rejected this caller.',
    statusCode: (code) => `The canister returned status ${code}.`,
    insufficientCycles: 'IConfucius is out of cycles. Please try again later.',
    unexpected: (variant) => `Unexpected error: ${variant}`,
  },
  Chinese: {
    unauthorized: '容器拒绝了此调用者。',
    statusCode: (code) => `容器返回状态码 ${code}。`,
    insufficientCycles: 'IConfucius 的 cycles 已耗尽，请稍后再试。',
    unexpected: (variant) => `意外错误：${variant}`,
  },
};

export function apiErrorToMessage(err, language) {
  const t = ERROR_STRINGS[language] ?? ERROR_STRINGS.English;
  if ('Other' in err) return err.Other;
  if ('Unauthorized' in err) return t.unauthorized;
  if ('StatusCode' in err) return t.statusCode(err.StatusCode);
  if ('InsuffientCycles' in err) return t.insufficientCycles;
  // Nat values decode as BigInt, so avoid JSON.stringify here.
  return t.unexpected(Object.keys(err)[0]);
}
