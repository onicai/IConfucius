# Debug Investigation: "Sorry, I am having trouble" error

## Symptom

When asking "What do you think of ICONFUCIUS right now?", the user sees:
1. Token price data (correct)
2. "Sorry, I am having trouble with that. Please try again in a few minutes."
3. A rephrased cancellation message
4. A follow-up wisdom quote

## Root cause

The Anthropic API rejects the advisory sub-agent's LLM call because the
conversation history ends with an assistant message (the token_price output):

```
AnthropicException - "This model does not support assistant message prefill.
The conversation must end with a user message."
```

## Exact sequence of events (from debug logs)

### 1. Command generator starts BOTH flows

The CompactLLMCommandGenerator produces:

```
start flow token_price
set slot query ICONFUCIUS
start flow advisory
```

Both flows are placed on the CALM dialogue stack.

### 2. token_price runs first and completes

```
flow.execution.loop  flow_id=token_price  previous_step_id=START
action_name=action_token_price
BotUttered('IConfucius (ICONFUCIUS) — 29m8 Price: 13.911 sats...')
flow.step.run.flow_end  flow_id=token_price  step_id=END
```

The `BotUttered` event adds the price data as an **assistant message** in
the conversation history.

### 3. advisory flow starts

```
flow.execution.loop  flow_id=advisory  previous_step_id=START
Agent advisory_agent started
```

### 4. Rasa constructs conversation history for the sub-agent

The `agent_input.conversation_history` field contains:

```
USER: Reply with a single profound quote about Trust...
AI: 🤠 Trust is the slowest bridge to build...
USER: What do you think of ICONFUCIUS token right now
AI: IConfucius (ICONFUCIUS) — 29m8 Price: 13.911 sats ($0.00987)...
```

### 5. Rasa sends messages to the Anthropic API

The message array sent to the LLM:

```json
[
  {"role": "system",  "content": "You are IConfucius...Conversation history:...AI: IConfucius..."},
  {"role": "user",      "content": "Reply with a single profound quote about Trust..."},
  {"role": "assistant", "content": "🤠 Trust is the slowest bridge..."},
  {"role": "user",      "content": "What do you think of ICONFUCIUS token right now"},
  {"role": "assistant", "content": "IConfucius (ICONFUCIUS) — 29m8 Price:..."}
]
```

**The last message is `assistant` → Anthropic API rejects it.**

### 6. Error cascade

```
AnthropicException - "This model does not support assistant message prefill..."
agent_response.status = AgentStatus.fatal_error
→ pattern_internal_error → utter_internal_error_rasa ("Sorry...")
→ pattern_cancel_flow → utter_flow_cancelled_rasa ("Okay, stopping advisory")
→ pattern_completed → utter_flow_follow_up (wisdom quote)
```

Each of these utters triggers a summarize + rephrase LLM call, wasting
~1,600 tokens on error messages.

## Langfuse trace summary (9 LLM calls total)

| Timestamp | Component                          | Tokens         | Purpose                     |
| --------- | ---------------------------------- | -------------- | --------------------------- |
| 23:16:48  | CompactLLMCommandGenerator         | 2,607 → 21     | Route to flows              |
| 23:16:51  | AdvisoryAgent                      | 3,252 → 92     | Sub-agent (FAILS)           |
| 23:16:54  | Summarizer                         | 95 → 38        | Summarize for "Sorry"       |
| 23:16:57  | ContextualResponseRephraser        | 143 → 17       | Rephrase "Sorry"            |
| 23:17:00  | Summarizer                         | 311 → 82       | Summarize for cancel msg    |
| 23:17:00  | Summarizer                         | 259 → 106      | Summarize for follow-up     |
| 23:17:05  | ContextualResponseRephraser        | 272 → 54       | Rephrase follow-up          |

## Open questions

1. **Is it valid CALM behavior to start two flows from one command?**
   The command generator produced `start flow token_price` AND
   `start flow advisory` in a single action list. Is this by design, or
   should the command generator only pick one?

2. **Is this a Rasa bug?** When constructing `AgentInput` for a sub-agent,
   should Rasa ensure the conversation history ends with a user message?
   The `BotUttered` from token_price should arguably not be included as
   an assistant message in the sub-agent's context.

3. **Would preventing dual flow start fix it?** If only `advisory` starts
   (without `token_price`), the conversation history would end with the
   user message and the API call would succeed. The advisory agent has
   `token_price` as an MCP tool and would fetch the data itself.

4. **Is there a Rasa config to control this?** Perhaps a flow attribute
   that prevents it from being started alongside other flows, or a way
   to mark a flow as "exclusive".
