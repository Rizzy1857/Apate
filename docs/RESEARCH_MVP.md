# Mirage Research MVP specification

Version 1.0 — 2026-09-25. Authority: [plan index](PLAN_INDEX.md).

## Purpose and workflow

Mirage Research is a contained SSH deception environment for observing command attempts and supported filesystem interactions, preserving evidence and evaluating controlled decoy artifacts. Researchers and analysts inspect the evidence; authorized red teams can supply interactions. The academic contribution must be measured rather than assumed.

The operator selects a profile/run, checks collection readiness, admits sessions, inspects attempts and effects, closes or reconciles sessions and exports reproducible evidence. Active-session exports are provisional. The release operates without inference; validated prepared AI artifacts form a separate experimental treatment. A negative AI result is acceptable when measured honestly.

## Scope

Included: one documented Ubuntu-like profile; SSH authentication observations; interactive emulation; recorded rejected exec/subsystem/forwarding requests where observable; isolated state; lifecycle; durable outbox; PostgreSQL history; Rust console; private raw and separately redacted exports; deterministic and optional prepared-AI modes; repeatable validation.

Excluded: arbitrary execution, real service exploitation, malware detonation, all attack types, network-wide monitoring, automatic blocking of real devices, attacker identity/expertise estimation, public production deployment, cloud multi-tenancy and Home distribution. A service depicted in the profile is not necessarily a real listening endpoint.

## Requirements

| ID | Required behavior | Acceptance evidence |
|---|---|---|
| R1 | Publish supported commands, flags, operands and error behavior | Versioned contract with fixtures per supported combination |
| R2 | Correct quoting, expansion and ordered redirects within the contract; reject unsupported syntax | Differential parser/output/effect tests |
| R3 | Session isolation and restricted emulator execution | Cross-session and Linux containment tests |
| R4 | Stable identities for admitted attempts, stages and supported effects | Ground-truth, retry and crash reconciliation |
| R5 | Distinct unsupported, denied, failed, completed and uncertain outcomes | Explicit fixtures and UI/export agreement |
| R6 | Separate input, generated response and locally transmitted output | Bounded transcript, short-write/disconnect tests |
| R7 | Explicit lifecycle and reconciliation after crashes | Interrupted sessions visible; no fabricated completion |
| R8 | Live sessions, paginated history and collection health | Running UI with over 100 sessions and 1,000 events |
| R9 | Complete selected committed evidence export with configuration/hashes | Independent reconstruction and storage comparison |
| R10 | Separate redacted sharing with disclosed omissions | Seeded-secret tests and versioned redaction policy |
| R11 | No-model operation independent of inference availability | Fresh no-model startup and failure tests |
| R12 | Approved AI artifacts only, with budgets, validation and provenance | Per-artifact evaluation and write-protection tests |
| R13 | Bounded sessions, resources and storage, visible saturation | Limit, exhaustion and recovery tests |
| R14 | Explainable evidence-linked pattern labels | Benign/quoted/failed command fixtures; no expertise claims |
| R15 | Reproducible release and accurate operator documentation | Fresh setup and frozen evidence bundle |

## Command contract work

Current handler inventory: `cd`, `pwd`, `export`, `env`, `printenv`, `unset`, `echo`, `whoami`, `id`, `hostname`, `uname`, `free`, `top`, `ps`, `ss`, `df`, `ls`, `cat`, `find`, `grep`, `head`, `tail`, `stat`, `touch`, `mkdir`, `rm`, `rmdir`, `cp`, `mv`.

The versioned behavior, flags, limits, statuses, mutation semantics and unsupported combinations are specified in [COMMAND_CONTRACT_V1.md](COMMAND_CONTRACT_V1.md). Its executable reference matrix covers composition, quotes, expansion, redirects, option rejection, resource bounds and representative effects. Together with the real SSH/FUSE handler procedure, G1 passes for this bounded contract; this does not claim GNU/POSIX compatibility.

Record blocked download/interpreter attempts; supporting real downloads or execution is outside v1. Rejected SSH request types need structured outcomes. Supported compound commands need stage results: the final status of a pipeline does not prove every stage succeeded.

## Interpretation boundaries

Tool mentions do not establish tool use; attempted actions do not establish completed techniques. A source address may represent NAT/relays. Session counts are not attacker counts. Technique annotations identify whether they derive from text, stage results or file effects and retain rule/version references. Metadata probes are not necessarily deliberate interest in a file.

## Definition of done

R1–R15 and all mandatory [verification gates](VERIFICATION_PLAN.md) pass on a frozen candidate. No unresolved issue may undermine isolation, supported semantics, attribution or declared completeness. Remaining limitations must be visible and reproducible. Human studies and broader protocols are optional extensions.

Deliver source/configuration, command contract, schema, console, operator guide, raw/redacted example bundles, test/benchmark records and research report. Compilation, a screenshot, model connectivity or a test count alone is insufficient.
