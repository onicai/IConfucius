import Array "mo:base/Array";
import Buffer "mo:base/Buffer";
import D "mo:base/Debug";
import Error "mo:base/Error";
import Principal "mo:base/Principal";
import Text "mo:base/Text";
import Nat "mo:base/Nat";
import Nat32 "mo:base/Nat32";
import Nat64 "mo:base/Nat64";
import Bool "mo:base/Bool";
// import HashMap "mo:base/HashMap";
import List "mo:base/List";
import Int "mo:base/Int";
import Float "mo:base/Float";
import Time "mo:base/Time";
import { print } = "mo:base/Debug";
import { setTimer; recurringTimer } = "mo:base/Timer";
import Timer "mo:base/Timer";

import Types "Types";
import Utils "Utils";

actor class ChallengerCtrlbCanister() {

    stable var GAME_STATE_CANISTER_ID : Text = "b77ix-eeaaa-aaaaa-qaada-cai"; // local dev: "b77ix-eeaaa-aaaaa-qaada-cai";
    
    stable var gameStateCanisterActor = actor (GAME_STATE_CANISTER_ID) : Types.GameStateCanister_Actor;

    public shared (msg) func setGameStateCanisterId(_game_state_canister_id : Text) : async Types.StatusCodeRecordResult {
        if (not Principal.isController(msg.caller)) {
            return #Err(#StatusCode(401));
        };
        GAME_STATE_CANISTER_ID := _game_state_canister_id;
        gameStateCanisterActor := actor (GAME_STATE_CANISTER_ID);
        return #Ok({ status_code = 200 });
    };

    public query (msg) func getGameStateCanisterId() : async Text {
        if (not Principal.isController(msg.caller)) {
            return "#Err(#StatusCode(401))";
        };

        return GAME_STATE_CANISTER_ID;
    };

    // Orthogonal Persisted Data storage

    // timer ID, so we can stop it after starting
    stable var recurringTimerId : ?Timer.TimerId = null;

    // Record of all generated challenges
    stable var generatedChallenges : List.List<Types.GeneratedChallenge> = List.nil<Types.GeneratedChallenge>();

    private func putGeneratedChallenge(challengeEntry : Types.GeneratedChallenge) : Bool {
        generatedChallenges := List.push<Types.GeneratedChallenge>(challengeEntry, generatedChallenges);
        return true;
    };

    private func getGeneratedChallenge(generationId : Text) : ?Types.GeneratedChallenge {
        return List.find<Types.GeneratedChallenge>(generatedChallenges, func(challengeEntry : Types.GeneratedChallenge) : Bool { challengeEntry.generationId == generationId });
    };

    private func getGeneratedChallenges() : [Types.GeneratedChallenge] {
        return List.toArray<Types.GeneratedChallenge>(generatedChallenges);
    };

    private func removeGeneratedChallenge(generationId : Text) : Bool {
        generatedChallenges := List.filter(generatedChallenges, func(challengeEntry : Types.GeneratedChallenge) : Bool { challengeEntry.generationId != generationId });
        return true;
    };

    public shared query (msg) func getChallengesAdmin() : async Types.GeneratedChallengesResult {
        if (not Principal.isController(msg.caller)) {
            return #Err(#Unauthorized);
        };
        let challenges : [Types.GeneratedChallenge] = getGeneratedChallenges();
        return #Ok(challenges);
    };

    public query (msg) func getChallengesListAdmin() : async List.List<Types.GeneratedChallenge> {
        if (not Principal.isController(msg.caller)) {
            return List.nil<Types.GeneratedChallenge>();
        };

        return generatedChallenges;
    };

    // Round-robin load balancer for LLM canisters to call
    private var roundRobinIndex : Nat = 0;
    private var roundRobinUseAll : Bool = true;
    private var roundRobinLLMs : Nat = 0; // Only used when roundRobinUseAll is false

    // -------------------------------------------------------------------------------
    // The C++ LLM canisters that can be called

    private var llmCanisters : Buffer.Buffer<Types.LLMCanister> = Buffer.fromArray([]);

    // Resets llmCanisters
    public shared (msg) func reset_llm_canisters() : async Types.StatusCodeRecordResult {
        if (not Principal.isController(msg.caller)) {
            return #Err(#StatusCode(401));
        };
        llmCanisters.clear();
        return #Ok({ status_code = 200 });
    };

    // Adds an llmCanister
    public shared (msg) func add_llm_canister(llmCanisterIdRecord : Types.CanisterIDRecord) : async Types.StatusCodeRecordResult {
        if (not Principal.isController(msg.caller)) {
            return #Err(#StatusCode(401));
        };
        _add_llm_canister_id(llmCanisterIdRecord);
    };
    private func _add_llm_canister_id(llmCanisterIdRecord : Types.CanisterIDRecord) : Types.StatusCodeRecordResult {
        let llmCanister = actor (llmCanisterIdRecord.canister_id) : Types.LLMCanister;
        D.print("IConfucius: Inside function _add_llm_canister_id. Adding llm: " # Principal.toText(Principal.fromActor(llmCanister)));
        llmCanisters.add(llmCanister);

        // Print content of the llmCanisters Buffer:
        D.print("IConfucius: Content of llmCanisters after addition: ");
        Buffer.iterate(
            llmCanisters,
            func(canister : Types.LLMCanister) : () {
                D.print("IConfucius: Canister ID: " # Principal.toText(Principal.fromActor(canister)));
            },
        );
        return #Ok({ status_code = 200 });
    };

    public shared query (msg) func whoami() : async Principal {
        return msg.caller;
    };

    // Function to verify that canister is up & running
    public shared query func health() : async Types.StatusCodeRecordResult {
        return #Ok({ status_code = 200 });
    };

    // Function to verify that canister is ready for inference
    public shared (msg) func ready() : async Types.StatusCodeRecordResult {
        if (not Principal.isController(msg.caller)) {
            return #Err(#StatusCode(401));
        };
        for (llmCanister in llmCanisters.vals()) {
            try {
                let statusCodeRecordResult : Types.StatusCodeRecordResult = await llmCanister.ready();
                switch (statusCodeRecordResult) {
                    case (#Err(_)) { return statusCodeRecordResult };
                    case (_) {
                        // If it's not an error, do nothing and continue the loop
                    };
                };
            } catch (_) {
                // Handle errors, such as llm canister not responding
                return #Err(#Other("Failed to call ready endpoint of llm canister = " # Principal.toText(Principal.fromActor(llmCanister))));
            };
        };
        return #Ok({ status_code = 200 });
    };

    // Admin function to verify that caller is a controller of this canister
    public shared query (msg) func amiController() : async Types.StatusCodeRecordResult {
        if (not Principal.isController(msg.caller)) {
            return #Err(#StatusCode(401));
        };
        return #Ok({ status_code = 200 });
    };

    // Admin function to verify that iconfucius_ctrlb_canister is a controller of all the llm canisters
    public shared (msg) func checkAccessToLLMs() : async Types.StatusCodeRecordResult {
        if (not Principal.isController(msg.caller)) {
            return #Err(#StatusCode(401));
        };

        // Call all the llm canisters to verify that iconfucius_ctrlb_canister is a controller
        for (llmCanister in llmCanisters.vals()) {
            try {
                let statusCodeRecordResult : Types.StatusCodeRecordResult = await llmCanister.check_access();
                switch (statusCodeRecordResult) {
                    case (#Err(_)) { return statusCodeRecordResult };
                    case (_) {
                        // If it's not an error, do nothing and continue the loop
                    };
                };
            } catch (_) {
                // Handle errors, such as llm canister not responding
                return #Err(#Other("Call failed to llm canister = " # Principal.toText(Principal.fromActor(llmCanister))));
            };
        };
        return #Ok({ status_code = 200 });
    };

    // Admin function to set roundRobinLLMs
    public shared (msg) func setRoundRobinLLMs(_roundRobinLLMs : Nat) : async Types.StatusCodeRecordResult {
        if (not Principal.isController(msg.caller)) {
            return #Err(#StatusCode(401));
        };
        roundRobinUseAll := false;
        roundRobinLLMs := _roundRobinLLMs;
        roundRobinIndex := 0;

        return #Ok({ status_code = 200 });
    };

    // Endpoint to generate a new challenge
    public shared (msg) func generateNewChallenge() : async Types.GeneratedChallengeResult {
        if (not Principal.isController(msg.caller)) {
            return #Err(#StatusCode(401));
        };

        let generatedChallengeOutput : Types.GeneratedChallengeResult = await generateChallenge();
        return generatedChallengeOutput;
    };

    private func getChallengeTopicFromGameStateCanister() : async Types.ChallengeTopicResult {
        D.print("IConfucius:  calling getRandomOpenChallengeTopic of gameStateCanisterActor = " # Principal.toText(Principal.fromActor(gameStateCanisterActor)));
        let result : Types.ChallengeTopicResult = await gameStateCanisterActor.getRandomOpenChallengeTopic();
        D.print("IConfucius:  getRandomOpenChallengeTopic returned.");
        return result;
    };

    private func generateChallenge() : async Types.GeneratedChallengeResult {
        // Get the next topic to generate a Challenge for
        
        D.print("IConfucius: generateChallenge - calling getChallengeTopicFromGameStateCanister.");
        let challengeTopicResult : Types.ChallengeTopicResult = await getChallengeTopicFromGameStateCanister();
        D.print("IConfucius: generateChallenge - received challengeResult from getChallengeTopicFromGameStateCanister: " # debug_show (challengeTopicResult));
        switch (challengeTopicResult) {
            case (#Err(error)) {
                D.print("IConfucius: generateChallenge - challengeTopicResult error : " # debug_show (error));
                return #Err(error);
            };
            case (#Ok(challengeTopic : Types.ChallengeTopic)) {
                D.print("IConfucius: generateChallenge - challengeTopic = " # debug_show(challengeTopic));

                let generatedChallengeOutput : Types.GeneratedChallengeResult = await challengeGenerationDoIt_(challengeTopic.challengeTopic);

                D.print("IConfucius: generateChallenge generatedChallengeOutput");
                print(debug_show (generatedChallengeOutput));
                switch (generatedChallengeOutput) {
                    case (#Err(error)) {
                        D.print("IConfucius: generateChallenge generatedChallengeOutput error");
                        print(debug_show (error));
                        return #Err(error);
                    };
                    case (#Ok(generatedChallenge)) {
                        // Store challenge
                        let pushResult = putGeneratedChallenge(generatedChallenge);

                        // Add challenge to Game State canister
                        let newChallenge : Types.NewChallengeInput = {
                            challengeTopic : Text = challengeTopic.challengeTopic;
                            challengeTopicId : Text = challengeTopic.challengeTopicId;
                            challengeTopicCreationTimestamp : Nat64 = challengeTopic.challengeTopicCreationTimestamp;
                            challengeTopicStatus : Types.ChallengeTopicStatus = challengeTopic.challengeTopicStatus;
                            challengeQuestion : Text = generatedChallenge.generatedChallengeText;
                            challengeQuestionSeed : Nat32 = generatedChallenge.generationSeed;
                        };

                        D.print("IConfucius: calling addChallenge of gameStateCanisterActor = " # Principal.toText(Principal.fromActor(gameStateCanisterActor)));
                        let additionResult : Types.ChallengeAdditionResult = await gameStateCanisterActor.addChallenge(newChallenge);
                        D.print("IConfucius: generateChallenge generatedChallengeOutput Ok additionResult");
                        print(debug_show (additionResult));
                        switch (additionResult) {
                            case (#Err(error)) {
                                // TODO: error handling (e.g. put into queue and try again later)
                            };
                            case (#Ok(addedChallenge)) {
                                // TODO: decide if returned challenge entry should be stored as well
                            };
                        };
                        return generatedChallengeOutput;
                    };
                };
            };
        };
    };

    private func challengeGenerationDoIt_(challengeTopic : Text) : async Types.GeneratedChallengeResult {
        let maxContinueLoopCount : Nat = 30; // After this many calls to run_update, we stop.
        let num_tokens : Nat64 = 1024;
        let temp : Float = 0.7;

        let startsWithOptions : [Text] = [
            "What",
            "Who",
            "Where",
            "When",
            "Why",
            "How",
            "Which",
            "Can",
            "Is",
            "Do",
        ];
        var challengePromptStartsWith : Text = startsWithOptions[0];
        let randomInt : ?Int = await Utils.nextRandomInt(0, startsWithOptions.size()-1);
        switch (randomInt) {
            case (?intToUse) {
                challengePromptStartsWith := startsWithOptions[Int.abs(intToUse)];
            };
            case (_) { // continue with default
            };
        };
        D.print("IConfucius: challengeGenerationDoIt_ - challengePromptStartsWith: " # debug_show(challengePromptStartsWith));

        var prompt : Text = "<|im_start|>user\nAsk a question about " #
        challengeTopic #
        ", that can be answered with common knowledge. Do NOT give the answer. Start the question with " #
        challengePromptStartsWith #
        "\n<|im_end|>\n<|im_start|>assistant\n";

        let llmCanister = _getRoundRobinCanister();

        D.print("IConfucius: challengeGenerationDoIt_ - llmCanister = " # Principal.toText(Principal.fromActor(llmCanister)));

        // Check health of llmCanister
        D.print("IConfucius: calling health endpoint of LLM");
        let statusCodeRecordResult : Types.StatusCodeRecordResult = await llmCanister.health();
        D.print("IConfucius: returned from health endpoint of LLM with : ");
        D.print("IConfucius: statusCodeRecordResult: " # debug_show (statusCodeRecordResult));
        switch (statusCodeRecordResult) {
            case (#Err(error)) {
                return #Err(error);
            };
            case (#Ok(_statusCodeRecord)) {
                D.print("IConfucius: LLM is healthy");
            };
        };

        let generationId : Text = await Utils.newRandomUniqueId();
        
        // Use the generationId to create a highly variable seed or the LLM
        let seed : Nat32 = Utils.getRandomLlmSeed(generationId);
        D.print("IConfucius: challengeGenerationDoIt_ - seed = " # debug_show(seed));

        var generationOutput : Text = "";
        let generationPrompt : Text = prompt;

        // The prompt cache file
        let promptCache : Text = generationId # ".cache";

        // Start the generation for this challenge
        var num_update_calls : Nat64 = 0;

        // data returned from new_chat
        var status_code : Nat16 = 0;
        var output : Text = "";
        var conversation : Text = "";
        var error : Text = "";
        var prompt_remaining : Text = "";
        var generated_eog : Bool = false;

        // ----------------------------------------------------------------------
        // Step 1
        // Call new_chat - this resets the prompt-cache for this conversation
        try {
            let args : [Text] = [
                "--prompt-cache",
                promptCache,
            ];
            let inputRecord : Types.InputRecord = { args = args };
            D.print("IConfucius: calling new_chat...");
            // D.print(debug_show (args));
            num_update_calls += 1;
            let outputRecordResult : Types.OutputRecordResult = await llmCanister.new_chat(inputRecord);
            // D.print("IConfucius: returned from new_chat with outputRecordResult: ");
            // D.print(debug_show (outputRecordResult));

            switch (outputRecordResult) {
                case (#Err(error)) {
                    return #Err(error);
                };
                case (#Ok(outputRecord)) {
                    // the generated tokens
                    status_code := outputRecord.status_code;
                    output := outputRecord.output;
                    conversation := outputRecord.conversation;
                    error := outputRecord.error;
                    prompt_remaining := outputRecord.prompt_remaining;
                    generated_eog := outputRecord.generated_eog;
                    // D.print("IConfucius: status_code      : " # debug_show (status_code));
                    D.print("IConfucius: output           : " # debug_show (output));
                    // D.print("IConfucius: conversation     : " # debug_show (conversation));
                    // D.print("IConfucius: error            : " # debug_show (error));
                    // D.print("IConfucius: prompt_remaining : " # debug_show (prompt_remaining));
                    // D.print("IConfucius: generated_eog    : " # debug_show (generated_eog));
                };
            };
        } catch (error : Error) {
            // Handle errors, such as llm canister not responding
            // D.print("IConfucius: catch error when calling new_chat : ");
            // D.print("IConfucius: error: " # Error.message(error));
            return #Err(
                #Other(
                    "Failed call to new_chat of " # Principal.toText(Principal.fromActor(llmCanister)) #
                    " with error: " # Error.message(error)
                )
            );
        };

        // ----------------------------------------------------------------------
        // Step 2
        // (A) Ingest the prompt into the prompt-cache, using multiple update calls
        //      (-) Repeat call with full prompt until `prompt_remaining` in the response is empty.
        //      (-) The first part of the challenge will be generated too.
        // (B) Generate rest of challenge, using multiple update calls
        //      (-) Repeat call with empty prompt until `generated_eog` in the response is `true`.
        //      (-) The rest of the challenge will be generated.

        // Avoid endless loop by limiting the number of iterations
        var continueLoopCount : Nat = 0;
        label continueLoop while (continueLoopCount < maxContinueLoopCount) {
            try {
                let args = [
                    "--prompt-cache",
                    promptCache,
                    "--prompt-cache-all",
                    "--simple-io",
                    "--no-display-prompt", // only return generated text
                    "-n",
                    Nat64.toText(num_tokens),
                    "--seed",
                    Nat32.toText(seed),
                    "--temp",
                    Float.toText(temp),
                    "-p",
                    prompt,
                ];
                let inputRecord : Types.InputRecord = { args = args };
                D.print("IConfucius: calling run_update...");
                // D.print(debug_show (args));
                num_update_calls += 1;
                if (num_update_calls > 30) {
                    D.print("IConfucius:  too many calls run_update - Breaking out of loop...");
                    break continueLoop; // Protective break for endless loop.
                };
                let outputRecordResult : Types.OutputRecordResult = await llmCanister.run_update(inputRecord);
                // D.print("IConfucius: INGESTING PROMPT:returned from run_update with outputRecordResult: ");
                // D.print(debug_show (outputRecordResult));

                switch (outputRecordResult) {
                    case (#Err(error)) {
                        return #Err(error);
                    };
                    case (#Ok(outputRecord)) {
                        // the generated tokens
                        status_code := outputRecord.status_code;
                        output := outputRecord.output;
                        conversation := outputRecord.conversation;
                        error := outputRecord.error;
                        prompt_remaining := outputRecord.prompt_remaining;
                        generated_eog := outputRecord.generated_eog;
                        // D.print("IConfucius: status_code      : " # debug_show (status_code));
                        D.print("IConfucius: output           : " # debug_show (output));
                        // D.print("IConfucius: conversation     : " # debug_show (conversation));
                        // D.print("IConfucius: error            : " # debug_show (error));
                        // D.print("IConfucius: prompt_remaining : " # debug_show (prompt_remaining));
                        // D.print("IConfucius: generated_eog    : " # debug_show (generated_eog));

                        generationOutput := generationOutput # output;
                        // D.print("IConfucius: generationOutput : " # debug_show (generationOutput));

                        if (prompt_remaining == "") {
                            prompt := ""; // Send empty prompt - the prompt ingestion is done.
                            continueLoopCount += 1; // We count the actual generation steps
                        };
                        if (generated_eog) {
                            break continueLoop; // Exit the loop - the challenge is generated.
                        };
                    };
                };
            } catch (error : Error) {
                // Handle errors, such as llm canister not responding
                D.print("IConfucius: catch error when calling new_chat : ");
                D.print("IConfucius: error: " # Error.message(error));
                return #Err(
                    #Other(
                        "Failed call to run_update of " # Principal.toText(Principal.fromActor(llmCanister)) #
                        " with error: " # Error.message(error)
                    )
                );
            };
        };

        // Delete the prompt cache in the LLM
        try {
            let args : [Text] = [
                "--prompt-cache",
                promptCache,
            ];
            let inputRecord : Types.InputRecord = { args = args };
            // D.print("IConfucius: calling remove_prompt_cache with args: ");
            // D.print("IConfucius: " # debug_show (args));
            num_update_calls += 1;
            let outputRecordResult : Types.OutputRecordResult = await llmCanister.remove_prompt_cache(inputRecord);
            // D.print("IConfucius: returned from remove_prompt_cache with outputRecordResult: ");
            // D.print(debug_show (outputRecordResult));

        } catch (error : Error) {
            // Handle errors, such as llm canister not responding
            D.print("IConfucius: catch error when calling remove_prompt_cache : ");
            D.print("IConfucius: error: " # Error.message(error));
            return #Err(
                #Other(
                    "Failed call to remove_prompt_cache of " # Principal.toText(Principal.fromActor(llmCanister)) #
                    " with error: " # Error.message(error)
                )
            );
        };

        // Return the generated challenge
        let challengeOutput : Types.GeneratedChallenge = {
            generationId : Text = generationId;
            generationSeed : Nat32 = seed;
            generatedTimestamp : Nat64 = Nat64.fromNat(Int.abs(Time.now()));
            generatedByLlmId : Text = Principal.toText(Principal.fromActor(llmCanister));
            generationPrompt : Text = generationPrompt;
            generatedChallengeText : Text = generationOutput;
        };
        return #Ok(challengeOutput);
    };

    public shared query (msg) func getRoundRobinCanister() : async Types.CanisterIDRecordResult {
        if (not Principal.isController(msg.caller)) {
            return #Err(#StatusCode(401));
        };
        let canisterIDRecord : Types.CanisterIDRecord = {
            canister_id = Principal.toText(Principal.fromActor(_getRoundRobinCanister()));
        };
        return #Ok(canisterIDRecord);
    };

    private func _getRoundRobinCanister() : Types.LLMCanister {
        D.print("IConfucius: _getRoundRobinCanister: using roundRobinIndex " # Nat.toText(roundRobinIndex));
        let canister = llmCanisters.get(roundRobinIndex);
        roundRobinIndex += 1;

        var roundRobinIndexTurn = llmCanisters.size();
        if (roundRobinUseAll == false) {
            roundRobinIndexTurn := Utils.minNat(roundRobinIndexTurn, roundRobinLLMs);
        };

        if (roundRobinIndex >= roundRobinIndexTurn) {
            roundRobinIndex := 0;
        };

        return canister;
    };

    // Timer
    let actionRegularityInSeconds = 60;

    private func triggerRecurringAction() : async () {
        D.print("IConfucius: Recurring action was triggered");
        //ignore generateChallenge(); TODO
        let result = await generateChallenge();
        D.print("IConfucius: Recurring action result");
        D.print(debug_show (result));
        D.print("IConfucius: Recurring action result");
    };

    public shared (msg) func startTimerExecutionAdmin() : async Types.AuthRecordResult {
        if (not Principal.isController(msg.caller)) {
            return #Err(#StatusCode(401));
        };
        ignore setTimer<system>(#seconds 5,
            func () : async () {
                D.print("IConfucius: setTimer");
                let id = recurringTimer<system>(#seconds actionRegularityInSeconds, triggerRecurringAction);
                D.print("IConfucius: Successfully start timer with id = " # debug_show (id));
                recurringTimerId := ?id;
                await triggerRecurringAction();
        });
        let authRecord = { auth = "You started the timer." };
        return #Ok(authRecord);
    };

    public shared (msg) func stopTimerExecutionAdmin() : async Types.AuthRecordResult {
        if (not Principal.isController(msg.caller)) {
            return #Err(#StatusCode(401));
        };

        switch (recurringTimerId) {
            case (?id) {
                D.print("IConfucius: Stopping timer with id = " # debug_show (id));
                Timer.cancelTimer(id);
                recurringTimerId := null;
                D.print("IConfucius: Timer stopped successfully.");
                
                return #Ok({ auth = "Timer stopped successfully." });
            };
            case null {
                return #Ok({ auth = "There is no active timer. Nothing to do." });
            };
        };
    };
};
