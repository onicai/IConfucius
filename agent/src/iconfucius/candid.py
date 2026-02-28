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

# ---------------------------------------------------------------------------
# ckBTC minter (mqygn-kiaaa-aaaar-qaadq-cai)
# Subset of methods used by iconfucius.  Full .did file stored at:
#   candid_files/ckbtc_minter_candid/mqygn-kiaaa-aaaar-qaadq-cai.did
# ---------------------------------------------------------------------------

CKBTC_MINTER_CANDID = """
type Account = record { owner : principal; subaccount : opt blob };

type Utxo = record {
    outpoint : record { txid : vec nat8; vout : nat32 };
    value : nat64;
    height : nat32;
};

type PendingUtxo = record {
    outpoint : record { txid : vec nat8; vout : nat32 };
    value : nat64;
    confirmations : nat32;
};

type SuspendedReason = variant {
    ValueTooSmall;
    Quarantined;
};

type SuspendedUtxo = record {
    utxo : Utxo;
    reason : SuspendedReason;
    earliest_retry : nat64;
};

type UtxoStatus = variant {
    ValueTooSmall : Utxo;
    Tainted : Utxo;
    Checked : Utxo;
    Minted : record {
        block_index : nat64;
        minted_amount : nat64;
        utxo : Utxo;
    };
};

type UpdateBalanceError = variant {
    NoNewUtxos : record {
        current_confirmations : opt nat32;
        required_confirmations : nat32;
        pending_utxos : opt vec PendingUtxo;
        suspended_utxos : opt vec SuspendedUtxo;
    };
    AlreadyProcessing;
    TemporarilyUnavailable : text;
    GenericError : record { error_message : text; error_code : nat64 };
};

type RetrieveBtcArgs = record {
    address : text;
    amount : nat64;
};

type RetrieveBtcOk = record {
    block_index : nat64;
};

type RetrieveBtcError = variant {
    MalformedAddress : text;
    AlreadyProcessing;
    AmountTooLow : nat64;
    InsufficientFunds : record { balance : nat64 };
    TemporarilyUnavailable : text;
    GenericError : record { error_message : text; error_code : nat64 };
};

type ReimbursementReason = variant {
    CallFailed;
    TaintedDestination : record {
        kyt_fee : nat64;
        kyt_provider : principal;
    };
};

type ReimbursedDeposit = record {
    account : Account;
    mint_block_index : nat64;
    amount : nat64;
    reason : ReimbursementReason;
};

type ReimbursementRequest = record {
    account : Account;
    amount : nat64;
    reason : ReimbursementReason;
};

type WithdrawalReimbursementReason = variant {
    invalid_transaction : record {
        too_many_inputs : record {
            num_inputs : nat64;
            max_num_inputs : nat64;
        };
    };
};

type RetrieveBtcStatusV2 = variant {
    Unknown;
    Pending;
    Signing;
    Sending : record { txid : blob };
    Submitted : record { txid : blob };
    AmountTooLow;
    Confirmed : record { txid : blob };
    Reimbursed : ReimbursedDeposit;
    WillReimburse : ReimbursementRequest;
};

service : {
    get_btc_address : (record { owner : opt principal; subaccount : opt blob }) -> (text);
    get_known_utxos : (record { owner : opt principal; subaccount : opt blob }) -> (vec Utxo) query;
    update_balance : (record { owner : opt principal; subaccount : opt blob }) -> (variant { Ok : vec UtxoStatus; Err : UpdateBalanceError });
    get_withdrawal_account : () -> (Account);
    estimate_withdrawal_fee : (record { amount : opt nat64 }) -> (record { bitcoin_fee : nat64; minter_fee : nat64 }) query;
    retrieve_btc : (RetrieveBtcArgs) -> (variant { Ok : RetrieveBtcOk; Err : RetrieveBtcError });
    retrieve_btc_status_v2 : (record { block_index : nat64 }) -> (RetrieveBtcStatusV2) query;
}
"""
