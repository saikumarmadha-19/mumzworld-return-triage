# Mumzworld Multilingual Return Triage Assistant

## Summary

I built a multilingual AI prototype for Mumzworld customer support. It triages return, refund, exchange, and escalation requests in English and Arabic using mock order data and a mock return policy. The assistant returns a validated structured JSON decision with confidence, policy basis, missing information, risk flags, and customer replies in both English and Arabic.

## Why this problem

Returns and refund requests are high-volume, policy-sensitive, and multilingual in the GCC. A support triage assistant can reduce manual workload while making sure risky cases, such as health or safety issues involving babies, are escalated to a human.

## Features

- English and Arabic customer messages
- Mock order lookup
- Lightweight RAG over mock return policy
- LLM-based classification through OpenRouter
- Pydantic schema validation
- Explicit uncertainty handling
- Safety escalation for rash, allergy, injury, smoke, electrical risk, etc.
- Deterministic fallback mode when no API key is available
- 12 eval cases including Arabic and adversarial prompt injection

## Setup

```bash
git clone YOUR_REPO_URL
cd mumzworld-return-triage

python -m venv venv
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env