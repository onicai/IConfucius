import Nat64 "mo:base/Nat64";

module Types {
    public type NatResult = Result<Nat, ApiError>;

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

    public type OutputRecordResult = Result<OutputRecord, ApiError>;
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

    type CanisterAddress = Text;

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
};
