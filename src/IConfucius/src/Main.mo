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
import HashMap "mo:base/HashMap";
import Iter "mo:base/Iter";
import List "mo:base/List";
import Int "mo:base/Int";
import Float "mo:base/Float";
import Time "mo:base/Time";
import { print } = "mo:base/Debug";
import { setTimer; recurringTimer } = "mo:base/Timer";
import Timer "mo:base/Timer";

import Types "../../common/Types";
import Utils "Utils";

actor class IConfuciusCtrlbCanister() {
    
    // Orthogonal Persisted Data storage

    // Flag to pause IConfucius (eg. for maintenance)
    stable var PAUSE_ICONFUCIUS : Bool = true;

    public shared (msg) func togglePauseIconfuciusFlagAdmin() : async Types.AuthRecordResult {
        if (Principal.isAnonymous(msg.caller)) {
            return #Err(#StatusCode(401));
        };
        if (not Principal.isController(msg.caller)) {
            return #Err(#Unauthorized);
        };
        PAUSE_ICONFUCIUS := not PAUSE_ICONFUCIUS;
        let authRecord = { auth = "You set the flag to " # debug_show(PAUSE_ICONFUCIUS) };
        return #Ok(authRecord);
    };

    public query func getPauseIconfuciusFlag() : async Types.FlagResult {
        return #Ok({ flag = PAUSE_ICONFUCIUS });
    };

    // timer ID, so we can stop it after starting
    stable var recurringTimerId : ?Timer.TimerId = null;

    // Open topics for Quotes to be generated
    stable var openQuoteTopicsStorageStable : [(Text, Types.QuoteTopic)] = [];
    var openQuoteTopicsStorage : HashMap.HashMap<Text, Types.QuoteTopic> = HashMap.HashMap(0, Text.equal, Text.hash);

    private func putOpenQuoteTopic(quoteTopicId : Text, quoteTopicEntry : Types.QuoteTopic) : Bool {
        openQuoteTopicsStorage.put(quoteTopicId, quoteTopicEntry);
        return true;
    };

    private func getOpenQuoteTopic(quoteTopicId : Text) : ?Types.QuoteTopic {
        switch (openQuoteTopicsStorage.get(quoteTopicId)) {
            case (null) { return null; };
            case (?quoteTopicEntry) { return ?quoteTopicEntry; };
        };
    };

    private func getOpenQuoteTopics() : [Types.QuoteTopic] {
        return Iter.toArray(openQuoteTopicsStorage.vals());
    };

    private func getRandomQuoteTopic(challengeTopicStatus : Types.QuoteTopicStatus) : async ?Types.QuoteTopic {
        D.print("IConfucius: getRandomQuoteTopic - challengeTopicStatus: " # debug_show(challengeTopicStatus));
        switch (challengeTopicStatus) {
            case (#Open) {
                let topicIds : [Text] = Iter.toArray(openQuoteTopicsStorage.keys());
                let numberOfTopics : Nat = topicIds.size();
                let randomInt : ?Int = await Utils.nextRandomInt(0, numberOfTopics-1);
                switch (randomInt) {
                    case (?intToUse) {
                        return getOpenQuoteTopic(topicIds[Int.abs(intToUse)]);
                    };
                    case (_) { return null; };
                };
            };
            case (_) { return null; };
        };
    };

    public shared (msg) func setInitialQuoteTopics() : async Types.StatusCodeRecordResult {
        if (Principal.isAnonymous(msg.caller)) {
            return #Err(#StatusCode(401));
        };
        if (not Principal.isController(msg.caller)) {
            return #Err(#Unauthorized);
        };
        D.print("IConfucius: setInitialQuoteTopics - entered");
        // Start with some initial topics
        let initialTopics : [Text] = [
            "crypto",     "nature",      "space", "history", "science", 
            "technology", "engineering", "math",  "art",     "music"
        ];
        for (initialTopic in Iter.fromArray(initialTopics)) {
            let quoteTopicId : Text = await Utils.newRandomUniqueId();

            let quoteTopic : Types.QuoteTopic = {
                quoteLanguage : Text = "en";
                quoteTopic : Text = initialTopic;
                quoteTopicId : Text = quoteTopicId;
                quoteTopicCreationTimestamp : Nat64 = Nat64.fromNat(Int.abs(Time.now()));
                quoteTopicStatus : Types.QuoteTopicStatus = #Open;
            };

            D.print("IConfucius: init - Adding quoteTopic: " # debug_show(quoteTopic));
            let _ = putOpenQuoteTopic(quoteTopicId, quoteTopic);
        };
        return #Ok({ status_code = 200 });
    };

    // Record of all generated quotes
    stable var generatedQuotes : List.List<Types.GeneratedQuote> = List.nil<Types.GeneratedQuote>();

    private func putGeneratedQuote(quoteEntry : Types.GeneratedQuote) : Bool {
        generatedQuotes := List.push<Types.GeneratedQuote>(quoteEntry, generatedQuotes);
        return true;
    };

    private func getGeneratedQuote(generationId : Text) : ?Types.GeneratedQuote {
        return List.find<Types.GeneratedQuote>(generatedQuotes, func(quoteEntry : Types.GeneratedQuote) : Bool { quoteEntry.generationId == generationId });
    };

    private func getGeneratedQuotes() : [Types.GeneratedQuote] {
        return List.toArray<Types.GeneratedQuote>(generatedQuotes);
    };

    private func removeGeneratedQuote(generationId : Text) : Bool {
        generatedQuotes := List.filter(generatedQuotes, func(quoteEntry : Types.GeneratedQuote) : Bool { quoteEntry.generationId != generationId });
        return true;
    };

    public shared query (msg) func getQuotesAdmin() : async Types.GeneratedQuotesResult {
        if (Principal.isAnonymous(msg.caller)) {
            return #Err(#StatusCode(401));
        };
        if (not Principal.isController(msg.caller)) {
            return #Err(#Unauthorized);
        };
        let quotes : [Types.GeneratedQuote] = getGeneratedQuotes();
        return #Ok(quotes);
    };

    public shared query (msg) func getNumQuotesAdmin() : async Types.NatResult {
        if (Principal.isAnonymous(msg.caller)) {
            return #Err(#StatusCode(401));
        };
        if (not Principal.isController(msg.caller)) {
            return #Err(#Unauthorized);
        };
        let quotes : [Types.GeneratedQuote] = getGeneratedQuotes();
        return #Ok(quotes.size());
    };

    // TODO: change return type to a Result
    public query (msg) func getQuotesListAdmin() : async List.List<Types.GeneratedQuote> {
        if (Principal.isAnonymous(msg.caller)) {
            return List.nil<Types.GeneratedQuote>();
        };
        if (not Principal.isController(msg.caller)) {
            return List.nil<Types.GeneratedQuote>();
        };
        return generatedQuotes;
    };

    // -------------------------------------------------------------------------------
    // The C++ LLM canisters that can be called
    stable var llmCanisterIdsStable : [Text] = [];
    private var llmCanisters : Buffer.Buffer<Types.LLMCanister> = Buffer.fromArray([]);

    // Round-robin load balancer for LLM canisters to call
    private var roundRobinIndex : Nat = 0;
    private var roundRobinUseAll : Bool = true;
    private var roundRobinLLMs : Nat = 0; // Only used when roundRobinUseAll is false

    public shared query (msg) func get_llm_canisters() : async Types.LlmCanistersRecordResult {
        if (Principal.isAnonymous(msg.caller)) {
            return #Err(#StatusCode(401));
        };
        if (not Principal.isController(msg.caller)) {
            return #Err(#StatusCode(401));
        };
        let llmCanisterIds : [Types.CanisterAddress] = Buffer.toArray(
            Buffer.map<Types.LLMCanister, Text>(llmCanisters, func (llm : Types.LLMCanister) : Text {
                Principal.toText(Principal.fromActor(llm))
            })
        );
        return #Ok({ 
            llmCanisterIds = llmCanisterIds;
            roundRobinUseAll = roundRobinUseAll;
            roundRobinLLMs = roundRobinLLMs;
        });
    };

    public shared (msg) func reset_llm_canisters() : async Types.StatusCodeRecordResult {
        if (Principal.isAnonymous(msg.caller)) {
            return #Err(#StatusCode(401));
        };
        if (not Principal.isController(msg.caller)) {
            return #Err(#StatusCode(401));
        };
        D.print("IConfucius: reset_llm_canisters - Resetting all LLM canisters & round-robin state");
        llmCanisters.clear();
        resetRoundRobinLLMs_();
        return #Ok({ status_code = 200 });
    };

    public shared (msg) func add_llm_canister(llmCanisterIdRecord : Types.CanisterIDRecord) : async Types.StatusCodeRecordResult {
        if (Principal.isAnonymous(msg.caller)) {
            return #Err(#StatusCode(401));
        };
        if (not Principal.isController(msg.caller)) {
            return #Err(#StatusCode(401));
        };
        D.print("IConfucius: add_llm_canister - Adding llm: " # llmCanisterIdRecord.canister_id);
        let llmCanister = actor (llmCanisterIdRecord.canister_id) : Types.LLMCanister;
        llmCanisters.add(llmCanister);
        return #Ok({ status_code = 200 });
    };

    public shared (msg) func remove_llm_canister(llmCanisterIdRecord : Types.CanisterIDRecord) : async Types.StatusCodeRecordResult {
        if (Principal.isAnonymous(msg.caller)) {
            return #Err(#StatusCode(401));
        };
        if (not Principal.isController(msg.caller)) {
            return #Err(#StatusCode(401));
        };

        let targetCanisterText = llmCanisterIdRecord.canister_id;
        let targetCanisterPrincipal = Principal.fromText(targetCanisterText);

        // Remove the LLM canister if found
        for (i in Iter.range(0, llmCanisters.size())) {
            let existing = llmCanisters.getOpt(i);
            switch (existing) {
                case (?item) {
                    let principalText = Principal.toText(Principal.fromActor(item));
                    if (principalText == targetCanisterText) {
                        ignore llmCanisters.remove(i);
                        D.print("IConfucius: remove_llm_canister - Removed llm: " # targetCanisterText);
                        return #Ok({ status_code = 200 });
                    };
                };
                case null {}; // Skip if none
            };
        };
        D.print("IConfucius: remove_llm_canister - Cannot find llm in the list: " # targetCanisterText);
        return #Err(#StatusCode(404)); // Not found
    };


    // Admin function to reset roundRobinLLMs
    public shared (msg) func resetRoundRobinLLMs() : async Types.StatusCodeRecordResult {
        if (Principal.isAnonymous(msg.caller)) {
            return #Err(#StatusCode(401));
        };
        if (not Principal.isController(msg.caller)) {
            return #Err(#StatusCode(401));
        };
        resetRoundRobinLLMs_();
        return #Ok({ status_code = 200 });
    };
    private func resetRoundRobinLLMs_() {
        roundRobinUseAll := true;
        roundRobinLLMs := 0; // Use all LLMs
        roundRobinIndex := 0;
    };

    // Admin function to set roundRobinLLMs
    public shared (msg) func setRoundRobinLLMs(_roundRobinLLMs : Nat) : async Types.StatusCodeRecordResult {
        if (Principal.isAnonymous(msg.caller)) {
            return #Err(#StatusCode(401));
        };
        if (not Principal.isController(msg.caller)) {
            return #Err(#StatusCode(401));
        };
        roundRobinUseAll := false;
        roundRobinLLMs := _roundRobinLLMs;
        roundRobinIndex := 0;

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
        if (Principal.isAnonymous(msg.caller)) {
            return #Err(#StatusCode(401));
        };
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
        if (Principal.isAnonymous(msg.caller)) {
            return #Err(#StatusCode(401));
        };
        if (not Principal.isController(msg.caller)) {
            return #Err(#StatusCode(401));
        };
        return #Ok({ status_code = 200 });
    };

    // Admin function to verify that iconfucius_ctrlb_canister is a controller of all the llm canisters
    public shared (msg) func checkAccessToLLMs() : async Types.StatusCodeRecordResult {
        if (Principal.isAnonymous(msg.caller)) {
            return #Err(#StatusCode(401));
        };
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

    

    // Endpoint to generate a new quote
    public shared (msg) func IConfuciusSays(quoteLanguage : Types.QuoteLanguage, topic : Text) : async Types.TextResult {
        // TODO: restore access control
        // if (not Principal.isController(msg.caller)) {
        //     return #Err(#Unauthorized);
        // };
        if (Principal.isAnonymous(msg.caller)) {
            return #Err(#Unauthorized);
        };
        if (PAUSE_ICONFUCIUS) {
            return #Err(#Other("IConfucius is currently paused"));
        };

        // TODO: pass in quoteLanguage variant instead of Text
        let language : Text = switch (quoteLanguage) {
            case (#English) { "en" };
            case (#Chinese) { "cn" };
            // case (#Dutch) { "nl" };
            // case (#German) { "de" };
        };
        let generatedQuoteResult : Types.GeneratedQuoteResult = await generateQuote(language, ?topic);
        switch (generatedQuoteResult) {
            case (#Err(error)) {
                D.print("IConfucius: generateQuote generatedQuoteOutput error");
                print(debug_show (error));
                return #Err(error);
            };
            case (#Ok(generatedQuote)) {
                return #Ok(generatedQuote.generatedQuoteText);
            };
        }
    };

    private func generateQuote(quoteLanguage : Text, topic : ?Text) : async Types.GeneratedQuoteResult {
        let quoteTopicResult : ?Types.QuoteTopic = switch (topic) {
            case (?t) {
                D.print("IConfucius: generateQuote - caller provided topic: " # t);
                let quoteTopicEntry : Types.QuoteTopic = {
                    quoteLanguage : Text = quoteLanguage;
                    quoteTopic : Text = t;
                    quoteTopicId : Text = await Utils.newRandomUniqueId();
                    quoteTopicCreationTimestamp : Nat64 = Nat64.fromNat(Int.abs(Time.now()));
                    quoteTopicStatus : Types.QuoteTopicStatus = #Open;
                };
                ?quoteTopicEntry;
            };
            case null {
                await getRandomQuoteTopic(#Open);
            };
        };
        D.print("IConfucius: generateQuote - received quoteResult from getQuoteTopicFromIConfuciusCanister: " # debug_show (quoteTopicResult));
        switch (quoteTopicResult) {
            case (?quoteTopic) {
                D.print("IConfucius: generateQuote - quoteTopic = " # debug_show(quoteTopic));

                let generatedQuoteOutput : Types.GeneratedQuoteResult = await quoteGenerationDoIt_(quoteTopic.quoteLanguage, quoteTopic.quoteTopic);

                D.print("IConfucius: generateQuote generatedQuoteOutput");
                print(debug_show (generatedQuoteOutput));
                switch (generatedQuoteOutput) {
                    case (#Err(error)) {
                        D.print("IConfucius: generateQuote generatedQuoteOutput error");
                        print(debug_show (error));
                        return #Err(error);
                    };
                    case (#Ok(generatedQuote)) {
                        // Store quote
                        let pushResult = putGeneratedQuote(generatedQuote);

                        // Add quote to Game State canister
                        let newQuote : Types.NewQuoteInput = {
                            quoteLanguage : Text = quoteTopic.quoteLanguage;
                            quoteTopic : Text = quoteTopic.quoteTopic;
                            quoteTopicId : Text = quoteTopic.quoteTopicId;
                            quoteTopicCreationTimestamp : Nat64 = quoteTopic.quoteTopicCreationTimestamp;
                            quoteTopicStatus : Types.QuoteTopicStatus = quoteTopic.quoteTopicStatus;
                            quoteText : Text = generatedQuote.generatedQuoteText;
                            quoteTextSeed : Nat32 = generatedQuote.generationSeed;
                        };

                        return generatedQuoteOutput;
                    };
                }
            };
            case (_) { 
                D.print("IConfucius: generateQuote - there is no quoteTopicResult." );
                return #Err(#FailedOperation); 
            };
        };
    };

    private func getPromptForQuote(quoteLanguage : Text, quoteTopic : Text) : Types.PromptForQuoteResult {
        var systemPrompt : Text = "";
        var userPromptRepetitive : Text = "";
        var userPromptVarying : Text = "";      
        var promptRepetitive : Text = "";
        var prompt : Text = "";

        if (quoteLanguage == "en") {
            systemPrompt := "You are Confucius, the ancient philosopher. You finish quotes in a profound and compassionate manner.";
            userPromptRepetitive := "Write a profound and thought provoking quote about ";
            userPromptVarying := quoteTopic # ". Provide only the quote, nothing else.";
        
            promptRepetitive := "<|im_start|>system\n" # systemPrompt # "<|im_end|>\n" #
            "<|im_start|>user\n" # userPromptRepetitive;
            prompt := promptRepetitive # userPromptVarying # 
            "<|im_end|>\n" # 
            "<|im_start|>assistant\n";
        } else if (quoteLanguage == "cn") {
            systemPrompt := "你是孔子，古代哲学家。你以一种深刻而富有同情心的方式结束引用。";
            userPromptRepetitive := "写一句关于 ";
            userPromptVarying := quoteTopic # " 只提供名言，其他不作提供。";
        
            promptRepetitive := "<|im_start|>system\n" # systemPrompt # "<|im_end|>\n" #
            "<|im_start|>user\n" # userPromptRepetitive;
            prompt := promptRepetitive # userPromptVarying # 
            "<|im_end|>\n" # 
            "<|im_start|>assistant\n";
        } else if (quoteLanguage == "nl") {
            systemPrompt := "Je bent Confucius, de oude filosoof. Je eindigt citaten op een diepgaande en medelevende manier.";
            userPromptRepetitive := "Schrijf een diepzinnig en inspirerend citaat over ";
            userPromptVarying := quoteTopic # ". Geef alleen het citaat op, niets anders.";
        
            promptRepetitive := "<|im_start|>system\n" # systemPrompt # "<|im_end|>\n" #
            "<|im_start|>user\n" # userPromptRepetitive;
            prompt := promptRepetitive # userPromptVarying # 
            "<|im_end|>\n" # 
            "<|im_start|>assistant\n";
        } else if (quoteLanguage == "de") {
            systemPrompt := "Du bist Konfuzius, der antike Philosoph. Du beendest Zitate auf eine tiefgründige und mitfühlende Weise.";
            userPromptRepetitive := "Schreibe ein tiefgründiges und nachdenkliches Zitat über ";
            userPromptVarying := quoteTopic # ". Gib nur das Zitat an, nichts anderes.";
        
            promptRepetitive := "<|im_start|>system\n" # systemPrompt # "<|im_end|>\n" #
            "<|im_start|>user\n" # userPromptRepetitive;
            prompt := promptRepetitive # userPromptVarying # 
            "<|im_end|>\n" # 
            "<|im_start|>assistant\n";
            return #Err(#Other("Unsupported language: " # quoteLanguage));
        };
        
        return #Ok({
            quoteLanguage : Text = quoteLanguage;
            systemPrompt : Text = systemPrompt;
            userPromptRepetitive : Text = userPromptRepetitive;
            userPromptVarying : Text = userPromptVarying;
            promptRepetitive : Text = promptRepetitive;
            prompt : Text = prompt;
        });

    };

    private func quoteGenerationDoIt_(quoteLanguage: Text, quoteTopic : Text) : async Types.GeneratedQuoteResult {
        let maxContinueLoopCount : Nat = 30; // After this many calls to run_update, we stop.
        let num_tokens : Nat64 = 1024;
        let temp : Float = 0.7;
        let repeat_penalty : Float = 1.1;
        let cache_type_k = "q8_0";

        var promptRepetitive : Text = "";
        var prompt : Text = "";  
        let promptForQuoteResult : Types.PromptForQuoteResult = getPromptForQuote(quoteLanguage, quoteTopic);
        switch (promptForQuoteResult) {
            case (#Err(error)) {
                return #Err(error);
            };
            case (#Ok(promptForQuote)) {
                promptRepetitive := promptForQuote.promptRepetitive;
                prompt := promptForQuote.prompt;
                D.print("IConfucius: prompt (" # quoteLanguage # "): " # prompt);
            };
        };

        let llmCanister = _getRoundRobinCanister();

        D.print("IConfucius: quoteGenerationDoIt_ - llmCanister = " # Principal.toText(Principal.fromActor(llmCanister)));

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
        D.print("IConfucius: quoteGenerationDoIt_ - seed = " # debug_show(seed));

        var generationOutput : Text = "";
        let generationPrompt : Text = prompt;

        // The prompt cache file
        let promptCache : Text = generationId # ".cache";

        // Start the generation for this quote
        var num_update_calls : Nat64 = 0;

        // data returned from new_chat
        var status_code : Nat16 = 0;
        var output : Text = "";
        var conversation : Text = "";
        var error : Text = "";
        var prompt_remaining : Text = "";
        var generated_eog : Bool = false;

        // ----------------------------------------------------------------------
        // Step 0
        // Restore a previously saved prompt cache file
        let promptSaveCache : Text = Nat32.toText(Text.hash(promptRepetitive)) # ".cache";
        var foundPromptSaveCache : Bool = false;

        try {
            let copyPromptCacheInputRecord : Types.CopyPromptCacheInputRecord = { 
                from = promptSaveCache; 
                to =  promptCache
            };
            D.print("IConfucius:  calling copy_prompt_cache to restore a previously saved promptCache if it exists. promptSaveCache: " # promptSaveCache);
            num_update_calls += 1;
            let statusCodeRecordResult : Types.StatusCodeRecordResult = await llmCanister.copy_prompt_cache(copyPromptCacheInputRecord);
            D.print("IConfucius:  returned from copy_prompt_cache with statusCodeRecordResult: " # debug_show (statusCodeRecordResult));
            switch (statusCodeRecordResult) {
                case (#Err(_)) {
                    foundPromptSaveCache := false;
                };
                case (#Ok(_)) {
                    foundPromptSaveCache := true;
                };
            };
        } catch (error : Error) {
            // Handle errors, such as llm canister not responding
            D.print("IConfucius:  catch error when calling copy_prompt_cache : ");
            D.print("IConfucius:  error: " # Error.message(error));
            return #Err(
                #Other(
                    "Failed call to copy_prompt_cache of " # Principal.toText(Principal.fromActor(llmCanister)) #
                    " with error: " # Error.message(error)
                )
            );
        };

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
        //      (-) The first part of the quote will be generated too.
        // (B) Generate rest of quote, using multiple update calls
        //      (-) Repeat call with empty prompt until `generated_eog` in the response is `true`.
        //      (-) The rest of the quote will be generated.

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
                    "--repeat-penalty",
                    Float.toText(repeat_penalty),
                    "--cache-type-k",
                    cache_type_k,
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

                            // -----
                            // Prompt ingestion is finished. If it was not yet there, save the prompt cache for reuse with next submission
                            if (not foundPromptSaveCache) {
                                try {
                                    let copyPromptCacheInputRecord : Types.CopyPromptCacheInputRecord = { 
                                        from = promptCache; 
                                        to =  promptSaveCache
                                    };
                                    D.print("IConfucius:  calling copy_prompt_cache to save the promptCache to promptSaveCache: " # promptSaveCache);
                                    num_update_calls += 1;
                                    let statusCodeRecordResult : Types.StatusCodeRecordResult = await llmCanister.copy_prompt_cache(copyPromptCacheInputRecord);
                                    D.print("IConfucius:  returned from copy_prompt_cache with statusCodeRecordResult: " # debug_show (statusCodeRecordResult));
                                    // We do not care what the result is, as it is just a possible optimization operation
                                } catch (error : Error) {
                                    // Handle errors, such as llm canister not responding
                                    D.print("IConfucius:  catch error when calling copy_prompt_cache : ");
                                    D.print("IConfucius:  error: " # Error.message(error));
                                    return #Err(
                                        #Other(
                                            "Failed call to copy_prompt_cache of " # Principal.toText(Principal.fromActor(llmCanister)) #
                                            " with error: " # Error.message(error)
                                        )
                                    );
                                };
                            };
                        };
                        if (generated_eog) {
                            break continueLoop; // Exit the loop - the quote is generated.
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

        // trim leading '"' and trailing '"' from generationOutput 
        let trimmedOutput = Text.trim(generationOutput, #char '\"');

        // Return the generated quote
        let quoteOutput : Types.GeneratedQuote = {
            generationId : Text = generationId;
            generationLanguage : Text = quoteLanguage;
            generationTopic : Text = quoteTopic;
            generationSeed : Nat32 = seed;
            generatedTimestamp : Nat64 = Nat64.fromNat(Int.abs(Time.now()));
            generatedByLlmId : Text = Principal.toText(Principal.fromActor(llmCanister));
            generationPrompt : Text = generationPrompt;
            generatedQuoteText : Text = trimmedOutput;
        };
        return #Ok(quoteOutput);
    };

    public shared query (msg) func getRoundRobinCanister() : async Types.CanisterIDRecordResult {
        if (Principal.isAnonymous(msg.caller)) {
            return #Err(#StatusCode(401));
        };
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

    // TODO: rotate languages...
    private func triggerRecurringAction() : async () {
        D.print("IConfucius: Recurring action was triggered for 'en' language");
        let result = await generateQuote("en", null);
        D.print("IConfucius: Recurring action result");
        D.print(debug_show (result));
        D.print("IConfucius: Recurring action result");
    };

    public shared (msg) func startTimerExecutionAdmin() : async Types.AuthRecordResult {
        if (Principal.isAnonymous(msg.caller)) {
            return #Err(#StatusCode(401));
        };
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
        if (Principal.isAnonymous(msg.caller)) {
            return #Err(#StatusCode(401));
        };
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

    // Upgrade Hooks
    system func preupgrade() {
        openQuoteTopicsStorageStable := Iter.toArray(openQuoteTopicsStorage.entries());
        llmCanisterIdsStable := Buffer.toArray(
            Buffer.map<Types.LLMCanister, Text>(llmCanisters, func (llm : Types.LLMCanister) : Text {
                Principal.toText(Principal.fromActor(llm))
            })
        );
    };

    system func postupgrade() {
        openQuoteTopicsStorage := HashMap.fromIter(Iter.fromArray(openQuoteTopicsStorageStable), openQuoteTopicsStorageStable.size(), Text.equal, Text.hash);
        openQuoteTopicsStorageStable := [];
        llmCanisters := Buffer.fromArray(Array.map<Text, Types.LLMCanister>(llmCanisterIdsStable, func(p: Text): Types.LLMCanister {actor (p) : Types.LLMCanister}));
        llmCanisterIdsStable := [];
    };
};
