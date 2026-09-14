import { Actor, HttpAgent } from '@icp-sdk/core/agent';
import { Ed25519KeyIdentity } from '@icp-sdk/core/identity';

export const CANISTER_ID =
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
export const identity = Ed25519KeyIdentity.generate();

const agent = HttpAgent.createSync({ host: HOST, identity });

export const actor = Actor.createActor(idlFactory, {
  agent,
  canisterId: CANISTER_ID,
});

export function apiErrorToMessage(err) {
  if ('Other' in err) return err.Other;
  if ('Unauthorized' in err) return 'The canister rejected this caller.';
  if ('StatusCode' in err) return `The canister returned status ${err.StatusCode}.`;
  if ('InsuffientCycles' in err)
    return 'IConfucius is out of cycles. Please try again later.';
  // Nat values decode as BigInt, so avoid JSON.stringify here.
  return `Unexpected error: ${Object.keys(err)[0]}`;
}
