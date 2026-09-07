# Frame: cutoff open, no sandbagging (seats 1–6)

Slug: **`cutoff_open_no_sandbagging`**. Parent: [INDEX.md](INDEX.md) research frames.
Ticket: [../NEXT_STAGE_SANDBAG_AND_CO.md](../NEXT_STAGE_SANDBAG_AND_CO.md).

Seats 1–6 cannot open (0% sandbag). CO (seat 7) holds a legal hand. BN (seat 8)
is behind and, in v1, opens every legal hand if CO passes and calls every legal
hand if CO opens.

**How to point at this work:** `evaluate cutoff_open_no_sandbagging`

Findings (this branch is a stub): the CO tree was solved on
`cursor/cutoff-open-no-sandbagging-6cf1`. Product answers are quoted in
[hijack_slowplay.md](hijack_slowplay.md): **open every legal including JJ**
(EV(open) ≈ +$1.44 vs pass 0); **do not sandbag** two pair+ or aces
(open − best pass ≈ +$1.39–$1.42). Do not re-run that tree here.

## Product questions (unanswered here)

1. Should CO open every legal class, or is JJ (or higher) −EV with BN behind?
2. Should CO ever sandbag (pass the v1 sandbag-set: two pair+, and aces on CO)
   given steal EV when BN has no legal opener vs P(BN is legal)?

## What differs from the BN steal lab

1. **BN behind** can be open-legal (or 2:1).
2. **Draw order** if CO opens and BN calls: CO draws before BN. If BN opened and
   a seat 1–6 2:1 called, that caller draws before BN. Do not reuse the
   BN-opener draw sampler blindly when BN is the caller.

## Aliases in this frame

| Alias | Human-readable name | What it actually is |
| --- | --- | --- |
| **CO JJ open** | Evaluate CO opening jacks with BN behind | Steal vs BN-legal HU vs 2:1; sign vs pass |
| **CO sandbag** | Evaluate CO passing two pair+ / aces | Give up steal when BN is weak; play vs BN open when BN is legal |
