---
name: software-architect
description: Assess the technical feasibility and running cost of a software product idea beyond its first version - hardest technical capability, external dependencies, cost per customer, reliability and security obligations, realistic team and timeline. Use when reviewing a SaaS, API, integration, data or connected-device startup idea, or when someone asks what it really takes to build and run a software product.
---

# Technical feasibility beyond the MVP

A demo proves that something can work once. A business needs it to work every
day, for every customer, at a cost below the price. Assess the gap between the
two.

## 1. Find the hardest capability

List what the product's promise depends on and pick the one that is hardest to
do reliably. Typical hard parts:

- **Integrations** with systems the founder does not control (banks, marketplaces,
  social networks, email providers, government portals): access may need
  partnership, approval or a paid tier, and the other side changes without notice.
- **Real-time or high-volume data**: monitoring, streaming, notifications,
  large files. Cost and complexity grow with volume, not with customers.
- **Accuracy promises**: matching, parsing, detection, AI output that customers
  act on. Every error rate needs a handling path.
- **Uptime promises**: a monitoring or payment product that is down when it
  matters loses the customer at once.
- **Security-sensitive data**: credentials, payments, health or financial data
  raise the engineering bar and often bring audits (for example SOC 2 for
  business customers in the US).
- **Hardware**: devices, firmware, logistics, returns.

## 2. External dependencies

For each third-party API or platform: does the needed access exist for a small
company, what does it cost at the planned volume, what are the rate limits and
policy risks, and what happens if it is withdrawn? A product built on one
platform's API has that platform's goodwill as its main risk.

## 3. Cost to run per customer

Estimate monthly infrastructure and third-party costs per customer and show the
math (requests, storage, data transfer, API and AI calls). Point out usage
patterns where one heavy customer costs more than many light ones.

## 4. Team and timeline

Estimate the engineering needed for a production-quality version: people,
skills and months, not the ideal case. Include what founders forget: tests,
monitoring, support tooling, security, data migrations, on-call. Say what a
solo non-technical founder could and could not do, and what outsourcing would
cost.

## Honesty rules

- A no-code or prototype being possible is not evidence that the production
  system is simple; say where the prototype approach stops.
- Distinguish "technically impossible" (rare) from "expensive or slow" (common):
  the second changes the economics, not the verdict on feasibility.
- Name concrete services and their pricing model when you know them, and mark
  numbers you are unsure of as estimates.
