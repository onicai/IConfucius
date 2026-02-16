import Nat64 "mo:base/Nat64";
import Principal "mo:base/Principal";

module Types {
    public type NatResult = Result<Nat, ApiError>;
    public type TextResult = Result<Text, ApiError>;

    public type FlagRecord = {
        flag : Bool;
    };
    public type FlagResult = Result<FlagRecord, ApiError>;

    public type PromptForQuote = {
        quoteLanguage : Text;
        systemPrompt : Text;
        userPromptRepetitive : Text;
        userPromptVarying : Text;
        promptRepetitive : Text;
        prompt : Text;
    };

    public type PromptForQuoteResult = Result<PromptForQuote, ApiError>;

    public type GeneratedQuote = {
        generationId : Text;
        generationLanguage : Text;
        generationTopic : Text;
        generationSeed : Nat32;
        generatedTimestamp : Nat64;
        generatedByLlmId : Text;
        generationPrompt : Text;
        generatedQuoteText : Text;
    };

    public type GeneratedQuoteResult = Result<GeneratedQuote, ApiError>;
    public type GeneratedQuotesResult = Result<[GeneratedQuote], ApiError>;

    public type CanisterIDRecordResult = Result<CanisterIDRecord, ApiError>;
    public type CanisterIDRecord = {
        canister_id : Text;
    };

    public type InputRecord = {
        args : [Text]; // the CLI args of llama.cpp/examples/main, as a list of strings
    };

    public type OutputRecordResult = Result<OutputRecord, OutputRecord>;
    public type OutputRecord = {
        status_code : Nat16;
        output : Text;
        conversation : Text;
        error : Text;
        prompt_remaining : Text;
        generated_eog : Bool;
    };

    public type CopyPromptCacheInputRecord = {
        from : Text;
        to : Text;
    };

    public type LLMCanister = actor {
        health : () -> async StatusCodeRecordResult;
        ready : () -> async StatusCodeRecordResult;
        check_access : () -> async StatusCodeRecordResult;
        new_chat : (InputRecord) -> async OutputRecordResult;
        run_update : (InputRecord) -> async OutputRecordResult;
        remove_prompt_cache : (InputRecord) -> async OutputRecordResult;
        copy_prompt_cache : (CopyPromptCacheInputRecord) -> async StatusCodeRecordResult;
    };

    public type LlmCanistersRecordResult = Result<LlmCanistersRecord, ApiError>;
    public type LlmCanistersRecord = {
        llmCanisterIds : [CanisterAddress]; // List of LLM canister IDs as text
        roundRobinUseAll : Bool; // If true, use all canisters in round-robin fashion
        roundRobinLLMs : Nat; // number of LLMs to use - Only used when roundRobinUseAll is false
    };
    public type CanisterAddress = Text;

    public type QuoteTopicStatus = {
        #Open;
        #Closed;
        #Archived;
        #Other : Text;
    };

    public type QuoteLanguage = {
        #English;
        #Chinese;
        // #Dutch;
        // #German;
    };

    public type QuoteLanguageInput = {
        quoteLanguage : Text;
    };
    public type QuoteTopicInput = {
        quoteTopic : Text;
    };
    public type QuoteTopic = QuoteLanguageInput and QuoteTopicInput and {
        quoteTopicId : Text;
        quoteTopicCreationTimestamp : Nat64;
        quoteTopicStatus : QuoteTopicStatus;
    };
    public type QuoteTopicResult = Result<QuoteTopic, ApiError>;

    public type NewQuoteInput = QuoteTopic and {
        quoteText : Text;
        quoteTextSeed : Nat32;
    };

    public type Quote = NewQuoteInput and {
        quoteId : Text;
        quoteCreationTimestamp : Nat64;
        quoteCreatedBy : CanisterAddress;
        quoteClosedTimestamp : ?Nat64;
        submissionCyclesRequired : Nat;
    };

    //--
    public type ApiError = {
        #Unauthorized;
        #InvalidId;
        #ZeroAddress;
        #FailedOperation;
        #Other : Text;
        #StatusCode : StatusCode;
        #InsuffientCycles : Nat; // Returns the required cycles to perform the operation
    };

    public type StatusCode = Nat16;

    //--
    public type Result<S, E> = {
        #Ok : S;
        #Err : E;
    };

    // --
    public type StatusCodeRecordResult = Result<StatusCodeRecord, ApiError>;
    public type StatusCodeRecord = { status_code : Nat16 };

    public type AuthRecord = {
        auth : Text;
    };

    public type AuthRecordResult = Result<AuthRecord, ApiError>;

    //-------------------------------------------------------------------------
    // Admin RBAC Types
    public type AdminRole = {
        #AdminUpdate; // Access to Admin endpoints requiring #AdminUpdate or #AdminQuery roles
        #AdminQuery;  // Access to Admin endpoints requiring #AdminQuery role only
    };

    public type AdminRoleAssignment = {
        principal  : Text;
        role       : AdminRole;
        assignedBy : Text;
        assignedAt : Nat64;
        note       : Text;
    };

    public type AssignAdminRoleInputRecord = {
        principal : Text;
        role      : AdminRole;
        note      : Text;
    };

    public type AdminRoleAssignmentResult = Result<AdminRoleAssignment, ApiError>;
    public type AdminRoleAssignmentsResult = Result<[AdminRoleAssignment], ApiError>;

    //-------------------------------------------------------------------------
    // IC Management Canister — Schnorr subset
    public type schnorr_algorithm = { #ed25519; #bip340secp256k1 };
    public type schnorr_aux = { #bip341 : { merkle_root_hash : Blob } };

    public type schnorr_public_key_args = {
        key_id          : { algorithm : schnorr_algorithm; name : Text };
        canister_id     : ?Principal;
        derivation_path : [Blob];
    };

    public type schnorr_public_key_result = {
        public_key : Blob;
        chain_code : Blob;
    };

    public type sign_with_schnorr_args = {
        key_id          : { algorithm : schnorr_algorithm; name : Text };
        derivation_path : [Blob];
        message         : Blob;
        aux             : ?schnorr_aux;
    };

    public type sign_with_schnorr_result = { signature : Blob };

    public type IC_Management = actor {
        schnorr_public_key : shared schnorr_public_key_args -> async schnorr_public_key_result;
        sign_with_schnorr  : shared sign_with_schnorr_args -> async sign_with_schnorr_result;
    };

    //-------------------------------------------------------------------------
    // OdinBot Schnorr Signing Types
    public type OdinBotPublicKeyRecord = {
        publicKeyHex   : Text;
        publicKeyBytes : Blob;
        derivationPath : Text;
    };

    public type OdinBotPublicKeyResult = Result<OdinBotPublicKeyRecord, ApiError>;

    public type OdinBotSignatureRecord = {
        signature    : Blob;
        signatureHex : Text;
    };

    public type OdinBotSignatureResult = Result<OdinBotSignatureRecord, ApiError>;

    public type OdinBotAccountRecord = {
        principalId    : Text;
        bitcoinAddress : Text;
    };

    public type OdinBotAccountResult = Result<OdinBotAccountRecord, ApiError>;
};
