---
doc_id: OPS-01
title: Escalation matrix and support levels
category: internal_operations
doc_type: sop
language: en
version: 1.0
effective_date: 2026-09-01
owner: NovaShop
sensitivity: internal
source_type: synthetic
---

# Escalation matrix and support levels

**Internal document — not to be shared with customers.**

## 1. Purpose of this document

This matrix defines who handles which type of request, within which timeframe, and according to which criteria a case changes level. It serves as the reference for SupportAI to decide when to offer a transfer to a human agent.

## 2. Levels

### L1 — Support advisor

Handles: product information, order tracking, return conditions, delivery times, common payment questions, creation of after-sales cases.

Target time: immediate answer, resolution within 24 business hours.

### L2 — Specialist

Handles: refund disputes, lost parcels, disagreements over an after-sales diagnosis, goodwill gestures up to 500 MAD, carrier incidents.

Target time: 48 business hours.

### L3 — Support manager

Handles: goodwill gestures above 500 MAD, legal threats, formal complaints, reputational incidents, suspected organised fraud.

Target time: 5 business days.

## 3. Automatic escalation criteria

| Criterion | Target level |
| --- | --- |
| Amount at stake > 3 000 MAD | L2 |
| Customer dissatisfied after 2 answers | L2 |
| Resolution time exceeded by 48 h | L2 then L3 |
| Mention of a lawyer, court or consumer association | L3 |
| Suspected fraud or false claim | L3 |
| Personal data compromised | L3 + DPO |
| Request outside support scope | L1 → redirect |

## 4. Transfer to a human agent

SupportAI must offer a human transfer, without waiting for the customer to ask, in the following cases:

1. The customer expresses distress or urgency (stolen parcel, compromised data).
2. The request concerns an amount above 3 000 MAD.
3. The customer contests a decision already communicated.
4. The question falls outside the documentary scope and no reliable source is found.
5. The customer explicitly asks for a person.
6. The topic is legal, medical or safety-related.

## 5. Traceability rules

Every escalation must contain: order identifier, two-line summary of the problem, actions already attempted, target level, escalation reason. A case without these elements is returned to the previous level.

## 6. Tracked indicators

- Escalation rate by level.
- Average first response time.
- First-contact resolution rate.
- Reopening rate within 7 days.
- Satisfaction after escalation.

## 7. Interaction with SupportAI

The assistant can resolve documented L1 requests. It must never:

- promise a refund outside policy;
- confirm a warranty decision before diagnosis;
- disclose information from another order;
- commit to a deadline not confirmed by the carrier.

When in doubt, the assistant cites the documentary source and offers a human transfer.
