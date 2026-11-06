---
doc_id: OPS-03
title: Order status reference
category: internal_operations
doc_type: sop
language: en
version: 1.0
effective_date: 2026-09-01
owner: NovaShop
sensitivity: internal
source_type: synthetic
---

# Order status reference

**Internal document — reference for support and for the order tracking simulation.**

## 1. Order lifecycle

```
created → pending_payment → paid → preparing
        → shipped → out_for_delivery → delivered
                                   ↘ return_pending → return_received → refunded
        ↘ cancelled
```

## 2. Status table

| Technical code | Customer label | Description | Possible actions |
| --- | --- | --- | --- |
| `created` | Order registered | Order created, payment not initiated | Pay, cancel |
| `pending_payment` | Awaiting payment | Payment not confirmed | Pay, cancel |
| `paid` | Payment confirmed | Payment validated, preparation pending | Cancel, modify |
| `preparing` | In preparation | Parcel being prepared | Cancel if not sealed |
| `shipped` | Shipped | Parcel handed to the carrier | Track, request a return |
| `out_for_delivery` | Out for delivery | Parcel on the delivery round | Track |
| `delivered` | Delivered | Parcel handed over | Return, after-sales, invoice |
| `delivery_failed` | Attempt failed | Customer absent or unreachable | Reschedule |
| `return_pending` | Return requested | Return authorisation issued | Drop off the parcel |
| `return_in_transit` | Return in progress | Parcel being returned | Wait for inspection |
| `return_received` | Return received | Parcel received at the warehouse | Wait for quality inspection |
| `refunded` | Refunded | Refund issued | Wait for the bank credit |
| `cancelled` | Cancelled | Order cancelled | Refund according to POL-02 |
| `on_hold` | Under review | Anti-fraud check | Contact support |

## 3. Transition rules

- `created → pending_payment`: as soon as payment is initialised.
- `pending_payment → paid`: confirmation from the payment provider.
- `paid → preparing`: taken over by the warehouse, within 24 business hours.
- `preparing → shipped`: handed to the carrier, tracking generated.
- `shipped → delivered`: delivery confirmed by the carrier.
- `delivered → return_pending`: return request validated (POL-01).
- Every transition is timestamped and logged.

## 4. Alert thresholds

| Status | Alert threshold |
| --- | --- |
| `paid` | 24 h without moving to `preparing` |
| `preparing` | 48 h without moving to `shipped` |
| `shipped` | 3 business days without an update |
| `return_received` | 48 h without quality inspection |
| `refunded` | 8 business days without bank confirmation |

Exceeding a threshold automatically creates a supervision task.

## 5. Correspondence with order data

Each order has: `order_id` (`ORD-` + 6 digits), `customer_id` (`CUST-` + 4 digits), `product_id` (`PROD-` or catalogue reference), `status`, `created_at`, `estimated_delivery`, `tracking_number`.

## 6. Special cases

- **Multi-parcel order**: the overall status is that of the least advanced parcel. Per-parcel detail is available in the customer account.
- **Order cancelled after payment**: the status moves to `cancelled` then to `refunded` once the refund is issued.
- **Order disputed by the bank**: moves to `on_hold` until the dispute is resolved.

## 7. Use by SupportAI

The assistant may read the current status and explain it. It may not modify a status. Any modification request is transferred to an agent (OPS-01).
