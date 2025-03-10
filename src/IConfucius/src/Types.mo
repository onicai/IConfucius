import Nat64 "mo:base/Nat64";

module Types {
    public type GeneratedChallenge = {
        generationId : Text;
        generationSeed : Nat32;
        generatedTimestamp : Nat64;
        generatedByLlmId : Text;
        generationPrompt : Text;
        generatedChallengeText : Text;
    };

    public type GeneratedChallengeResult = Result<GeneratedChallenge, ApiError>;
    public type GeneratedChallengesResult = Result<[GeneratedChallenge], ApiError>;

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

    public type LLMCanister = actor {
        health : () -> async StatusCodeRecordResult;
        ready : () -> async StatusCodeRecordResult;
        check_access : () -> async StatusCodeRecordResult;
        new_chat : (InputRecord) -> async OutputRecordResult;
        run_update : (InputRecord) -> async OutputRecordResult;
        remove_prompt_cache : (InputRecord) -> async OutputRecordResult;
    };

    // Game State canister
    type CanisterAddress = Text;

    public type ChallengeTopicStatus = {
        #Open;
        #Closed;
        #Archived;
        #Other : Text;
    };

    type ChallengeStatus = {
        #Open;
        #Closed;
        #Archived;
        #Other : Text;
    };

    public type ChallengeTopicInput = {
        challengeTopic : Text;
    };
    public type ChallengeTopic = ChallengeTopicInput and {
        challengeTopicId : Text;
        challengeTopicCreationTimestamp : Nat64;
        challengeTopicStatus : ChallengeTopicStatus;
    };
    public type ChallengeTopicResult = Result<ChallengeTopic, ApiError>;

    public type NewChallengeInput = ChallengeTopic and {
        challengeQuestion : Text;
        challengeQuestionSeed : Nat32;
    };

    public type Challenge = NewChallengeInput and {
        challengeId : Text;
        challengeCreationTimestamp : Nat64;
        challengeCreatedBy : CanisterAddress;
        challengeStatus : ChallengeStatus;
        challengeClosedTimestamp : ?Nat64;
        submissionCyclesRequired : Nat;
    };

    public type ChallengeAdditionResult = Result<Challenge, ApiError>;

    public type GameStateCanister_Actor = actor {
        getRandomOpenChallengeTopic : () -> async ChallengeTopicResult;
        addChallenge : (NewChallengeInput) -> async ChallengeAdditionResult;
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
