# Tradeoffs

## Why I picked this problem

I chose return/refund triage because it is realistic for Mumzworld, high-volume, multilingual, and policy-sensitive. It also has clear success criteria: the assistant should classify the case correctly, ground its decision in policy, and escalate when there is risk or uncertainty.

## Alternatives I considered

### Gift finder

Useful and customer-facing, but harder to evaluate objectively in 5 hours.

### Product description generator

Good for catalog operations, but higher risk of hallucinating product claims.

### Review summarizer

Valuable, but less operationally urgent than return/refund triage and requires a larger review dataset.

## Architecture

The system uses:

1. Mock order table
2. Mock return policy
3. Lightweight policy retrieval
4. LLM structured generation
5. Pydantic validation
6. Deterministic fallback for demo reliability

## Why RAG

The model should not invent return policy rules. Retrieval gives it the relevant policy sections before making a decision.

## Why structured output

Customer support triage should feed downstream systems. Free text is hard to automate. JSON with schema validation makes the output usable for dashboards, ticket routing, and human review.

## Uncertainty handling

The assistant returns `uncertain` when:

- order ID is missing
- order ID is unknown
- the message lacks a clear return reason
- the request is unrelated
- the user tries to override instructions

The assistant returns `escalate` when:

- the message mentions rash, allergy, choking, injury, smoke, electrical issues, or safety risk
- the case is late but potentially serious
- human review is required

## What I cut

To keep the prototype within 5 hours, I did not build:

- real Mumzworld integrations
- authentication
- agent dashboard
- ticketing system integration
- multilingual voice input
- fine-tuning
- production monitoring
- human feedback loop

## What I would build next

Given more time, I would:

- connect to real return policy and order APIs
- add human feedback to improve decisions
- calibrate confidence scores
- add analytics by country, product category, and return reason
- add admin review workflow
- improve Arabic brand tone
- replace TF-IDF retrieval with multilingual embeddings or a vector database