"""
iconfucius.candid — Candid interface strings for IC canister calls

Centralizes all inline Candid interface definitions used across the package.
Each string defines the subset of a canister's interface that iconfucius uses.
"""

# ---------------------------------------------------------------------------
# Generic ICRC-1 interface (works with any ICRC-1 token ledger)
# ---------------------------------------------------------------------------

ICRC1_CANDID = """
service : {
    icrc1_balance_of : (record { owner : principal; subaccount : opt blob }) -> (nat) query;
    icrc1_transfer : (record {
        to : record { owner : principal; subaccount : opt blob };
        amount : nat;
        fee : opt nat;
        memo : opt blob;
        from_subaccount : opt blob;
        created_at_time : opt nat64;
    }) -> (variant { Ok : nat; Err : variant {
        BadFee : record { expected_fee : nat };
        BadBurn : record { min_burn_amount : nat };
        InsufficientFunds : record { balance : nat };
        TooOld;
        CreatedInFuture : record { ledger_time : nat64 };
        Duplicate : record { duplicate_of : nat };
        TemporarilyUnavailable;
        GenericError : record { error_code : nat; message : text };
    }});
}
"""

# ---------------------------------------------------------------------------
# ckBTC ledger (mxzaz-hqaaa-aaaar-qaada-cai)
# ---------------------------------------------------------------------------

CKBTC_LEDGER_CANDID = """
service : {
    icrc1_balance_of : (record { owner : principal; subaccount : opt blob }) -> (nat) query;
    icrc1_decimals : () -> (nat8) query;
    icrc1_symbol : () -> (text) query;
    icrc1_transfer : (record {
        to : record { owner : principal; subaccount : opt blob };
        amount : nat;
        fee : opt nat;
        memo : opt blob;
        from_subaccount : opt blob;
        created_at_time : opt nat64;
    }) -> (variant { Ok : nat; Err : variant {
        BadFee : record { expected_fee : nat };
        BadBurn : record { min_burn_amount : nat };
        InsufficientFunds : record { balance : nat };
        TooOld;
        CreatedInFuture : record { ledger_time : nat64 };
        Duplicate : record { duplicate_of : nat };
        TemporarilyUnavailable;
        GenericError : record { error_code : nat; message : text };
    }});
    icrc2_approve : (record {
        spender : record { owner : principal; subaccount : opt blob };
        amount : nat;
        fee : opt nat;
        memo : opt blob;
        from_subaccount : opt blob;
        created_at_time : opt nat64;
        expected_allowance : opt nat;
        expires_at : opt nat64;
    }) -> (variant {
        Ok : nat;
        Err : variant {
            BadFee : record { expected_fee : nat };
            InsufficientFunds : record { balance : nat };
            AllowanceChanged : record { current_allowance : nat };
            Expired : record { ledger_time : nat64 };
            TooOld;
            CreatedInFuture : record { ledger_time : nat64 };
            Duplicate : record { duplicate_of : nat };
            TemporarilyUnavailable;
            GenericError : record { error_code : nat; message : text };
        }
    });
}
"""

# ---------------------------------------------------------------------------
# Odin.fun trading canister (z2vm5-gaaaa-aaaaj-azw6q-cai)
# ---------------------------------------------------------------------------

ODIN_TRADING_CANDID = """
type TradeType = variant { buy; sell };
type TradeAmount = variant { btc : nat; token : nat };
type TradeSettings = record { slippage : opt record { nat; nat } };
type TradeRequest = record {
    tokenid : text;
    typeof : TradeType;
    amount : TradeAmount;
    settings : opt TradeSettings;
};
type TradeResponse = variant { ok; err : text };

type TransferResponse = variant { ok; err : text };
type TransferRequest = record {
    amount   : nat;
    to       : text;
    tokenid  : text;
};

type WithdrawProtocol = variant { btc; ckbtc; volt };
type WithdrawRequest = record {
    protocol : WithdrawProtocol;
    tokenid  : text;
    address  : text;
    amount   : nat;
};
type WithdrawResponse = variant { ok : bool; err : text };

service : {
    getBalance : (text, text) -> (nat) query;
    token_trade : (TradeRequest) -> (TradeResponse);
    token_transfer : (TransferRequest) -> (TransferResponse);
    token_withdraw : (WithdrawRequest) -> (WithdrawResponse);
}
"""

# ---------------------------------------------------------------------------
# Odin.fun ckBTC deposit helper (ztwhb-qiaaa-aaaaj-azw7a-cai)
# ---------------------------------------------------------------------------

ODIN_DEPOSIT_CANDID = """
type DepositResult = variant { ok : nat; err : text };
service : {
    ckbtc_deposit : (opt blob, nat) -> (DepositResult);
}
"""

# ---------------------------------------------------------------------------
# Odin.fun SIWB canister (bcxqa-kqaaa-aaaak-qotba-cai)
# ---------------------------------------------------------------------------

ODIN_SIWB_CANDID = """
service : {
    siwb_prepare_login : (text) -> (variant { Ok : text; Err : text });
    siwb_login : (text, text, text, blob, variant { ECDSA; Bip322Simple }) -> (variant {
        Ok : record { expiration : nat64; user_canister_pubkey : blob };
        Err : text
    });
    siwb_get_delegation : (text, blob, nat64) -> (variant {
        Ok : record {
            delegation : record { pubkey : blob; expiration : nat64; targets : opt vec principal };
            signature : blob
        };
        Err : text
    }) query;
}
"""

# ---------------------------------------------------------------------------
# onicai ckSigner canister (g7qkb-iiaaa-aaaar-qb3za-cai)
# ---------------------------------------------------------------------------

ONICAI_CKSIGNER_CANDID = """
type ApiError = variant {
    Unauthorized;
    InvalidId;
    ZeroAddress;
    FailedOperation;
    Other : text;
    StatusCode : nat16;
    InsuffientCycles : nat;
};

type PublicKeyRecord = record {
    botName : text;
    publicKeyHex : text;
    address : text;
};

type SignRecord = record {
    botName : text;
    signatureHex : text;
};

type Bip322SignRecord = record {
    botName : text;
    signatureHex : text;
    witnessB64 : text;
    address : text;
};

type Payment = record {
    tokenName : text;
    tokenLedger : principal;
    amount : nat;
};

type FeeToken = record {
    tokenName : text;
    tokenLedger : principal;
    fee : nat;
};

type Treasury = record {
    treasuryName : text;
    treasuryPrincipal : principal;
};

type FeeTokensRecord = record {
    canisterId : principal;
    treasury : Treasury;
    feeTokens : vec FeeToken;
    usage : text;
};

service : {
    getPublicKeyQuery : (record { botName : text }) -> (variant { Ok : PublicKeyRecord; Err : ApiError }) query;
    getPublicKey : (record { botName : text; payment : opt Payment }) -> (variant { Ok : PublicKeyRecord; Err : ApiError });
    sign : (record { botName : text; message : blob; payment : opt Payment }) -> (variant { Ok : SignRecord; Err : ApiError });
    signBip322 : (record { botName : text; message : text; payment : opt Payment }) -> (variant { Ok : Bip322SignRecord; Err : ApiError });
    getFeeTokens : () -> (variant { Ok : FeeTokensRecord; Err : ApiError }) query;
}
"""
