---
name: ai-tool-creator
description: Assess whether an AI-powered product idea has real, defensible value and sound unit economics - the chatbot substitution test, cost per task of model calls, accuracy requirements, dependency on model providers, and the first paying customers. Use when reviewing a startup idea built on language models, generative AI or machine learning, or when someone asks whether an AI tool or 'GPT wrapper' can be a business.
---

# Screening an AI product idea

Most AI product ideas fail for one of three reasons: a general-purpose
assistant already does the job, the model costs eat the margin, or the product
needs an accuracy the model cannot deliver. Check all three before anything else.

## 1. The substitution test

Ask what a target user gets by typing the same request into a general-purpose
assistant (ChatGPT, Claude, Gemini, Copilot built into their existing tools).
The product has real value only if it adds something the chat window does not:

- **Proprietary or private data**: the customer's own documents, systems or
  history, or a dataset others do not have.
- **Workflow integration**: it runs where the work happens (inside the
  customer's tools, on a schedule, triggered by events) instead of on request.
- **Guaranteed output quality** for a narrow task: validation, domain rules,
  human review, a format the next system accepts.
- **Distribution or trust** the general assistants lack in that niche.

If the honest answer is "a good prompt", the product is a feature the platforms
will ship, and the moat is only as long as that takes.

## 2. Unit economics of model calls

Estimate the cost per task and per customer per month, and show the math:
tokens per task (input + output, including any documents sent), times the
model's price per token, times tasks per customer. Then compare with the price.

- Long inputs (documents, transcripts, codebases) usually dominate the cost.
- Agentic products that loop many times per task cost many times a single call.
- Heavy users on a flat subscription can cost more than they pay; say where
  the price needs usage limits or usage-based tiers.
- Model prices fall over time, but a plan that is unprofitable at today's
  prices depends on that fall.

## 3. Accuracy and liability

Ask what happens when the model is wrong. Where an error is cheap and visible
(a draft email) the product works with today's models. Where it is expensive or
silent (legal, medical, financial advice, automated actions on the customer's
behalf) the product needs verification, human review or narrow scope, and that
cost belongs in the plan.

## 4. Platform dependency

The product depends on one or a few model providers: their prices, rate
limits, policies and the chance that they build the same feature. Say what
switching providers would take.

## 5. The first ten customers

Name where they are and why they would pay now: communities, a niche the
founder knows, existing clients. "Post on Product Hunt" is a launch, not a
customer list.
