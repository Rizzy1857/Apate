# Prepared-AI engineering evaluation — 2026-09-27

## Decision

Keep deterministic generation as the Research MVP default. Prepared AI remains an optional research treatment.

The frozen valid-only prepared-AI run accepted **172/180 artifacts (95.6%)** after at most two attempts, versus **180/180 validator-accepted deterministic renders**. Derived AI generation-plus-validation time had a median of **8.336 s** (p95 **35.959 s**, maximum **60.014 s**). The final schema-2 deterministic generation-plus-validation run had a host-local median of **0.077 ms** (p95 **0.190 ms**). These are treatment-internal engineering timings on one host, not a complete end-to-end deployment comparison. Automated acceptance is not a plausibility judgment, so these results do not establish that AI content is better.

The run also exposed an unfair baseline: four required deterministic artifacts were empty. The baseline templates were corrected before baseline measurement so all six paths now contain coherent, validator-accepted content.

## Frozen procedure

- Source base: commit `a098fe02771802de03b9c64c8fbce52d82defc38` with a dirty working tree. Results cannot be attributed to that commit alone.
- Host: Apple arm64 macOS/Darwin 25.5.0; local Ollama endpoint. CPU/RAM utilization was not instrumented.
- AI artifact interval inferred from retained artifact mtimes: 2026-09-27 19:21:28–20:02:35 IST.
- Reference epoch: `1790467200`; Ubuntu profile and coherent `valid` category fixed for every trial.
- 30 uncached generation trials for each of six required paths; maximum two attempts per trial; 30-second timeout per attempt.
- Models: `llama3.2:3b` digest `a80c4f17acd55265feec403c7aef86be0c25983ab279d83f3bcd3abbcb5b8b72`; `llama3:8b` digest `365c0bd3c000a25d28ddbf732fe1c6add414de7275464c4e4d1c3b5fcb5d8ad1`.
- No seed was set because this runtime path does not expose a frozen seed. Every attempt, including timeout and validator rejection, is retained.
- The deterministic run repeats rendering 30 times per path for comparable timing/validation bookkeeping. Those are timing repetitions, not independent stochastic samples.
- This experiment forces the coherent `valid` category. Production preparation samples the configured category distribution, so 95.6% is not a general production-bundle success rate.
- The original AI schema recorded attempt duration and total trial duration together. Its compute values above are derived by summing retained attempt durations. The schema-2 deterministic rerun measures render plus validation separately; future AI runs use the same split fields.

## Prepared-AI results

| Path | Accepted | Retried trials | Unique accepted outputs | Derived compute median (s) | Derived compute p95 (s) |
|---|---:|---:|---:|---:|---:|
| `/var/log/auth.log` | 30/30 | 3 | 23 | 8.501 | 25.050 |
| `/var/log/syslog` | 30/30 | 1 | 18 | 7.013 | 10.626 |
| `/home/ubuntu/.bash_history` | 30/30 | 4 | 17 | 7.038 | 35.960 |
| `/home/ubuntu/notes.txt` | 22/30 | 14 | 21 | 10.168 | 47.071 |
| `/etc/nginx/nginx.conf` | 30/30 | 1 | 1 | 15.615 | 23.256 |
| `/var/www/html/index.html` | 30/30 | 0 | 4 | 5.801 | 9.129 |

Across 180 trials there were 203 attempts and 23 retried trials. Attempt-level failures comprised 15 transport failures/timeouts, 15 note line-density violations and one Ubuntu-convention violation. Eight trials remained rejected after both attempts, all for `notes.txt`. The nginx model returned the same accepted bytes in every trial; the HTML path produced only four unique outputs. High acceptance therefore must not be interpreted as high diversity.

## Interpretation and limitations

The deterministic treatment is the suitable college-project MVP: it is complete, cheap, reproducible, works without a model service and avoids the observed preparation failure tail. Prepared AI is still valuable as a bounded research comparison, particularly for logs and history where it produced more varied accepted artifacts.

This run answers valid-only engineering reliability, compute cost and validator consistency only. It does not include independent or blinded plausibility ratings, CPU/RAM/energy measurement, participant behavior, cached-read latency, or evidence-path correctness under this treatment. A future human review must use a frozen rubric and blinded randomized samples; until then, no “more realistic” claim is justified. The validator also cannot prove universal semantic correctness.

## Evidence and reproduction

- AI manifest and raw trial records: [`../evidence/prepared_ai_valid_20260927/evaluation.json`](../evidence/prepared_ai_valid_20260927/evaluation.json)
- AI completion hash: [`../evidence/prepared_ai_valid_20260927/complete.json`](../evidence/prepared_ai_valid_20260927/complete.json)
- Final aligned deterministic manifest and timings: [`../evidence/deterministic_valid_aligned_v2_20260928/evaluation.json`](../evidence/deterministic_valid_aligned_v2_20260928/evaluation.json)
- Harnesses: [`../tests/integration/evaluate_prepared_ai.py`](../tests/integration/evaluate_prepared_ai.py) and [`../tests/integration/evaluate_deterministic.py`](../tests/integration/evaluate_deterministic.py)

Both completion manifests' SHA-256 values were verified against their `evaluation.json` files after the runs.
