# Guardrails Status: Active Spec, Dormant Machinery

**TL;DR**: You correctly identified that `household_safety.py` and `privacy.py` exist but should NOT be active yet. They are now explicitly marked as dormant.

---

## Current State (Verified)

### ✅ What's True

1. **Both modules exist** (`backend/app/privacy.py`, `backend/app/household_safety.py`)
2. **Both are completely dormant** — not imported into main.py or active data paths
3. **Both are well-designed** — they define constraints, not features
4. **No premature machinery** — no active pruning, no active cloud shipping, no active interception

### ✅ What's Good

These exist because:

* **Failure modes are architectural** — defining "what never breaks" shapes your deployment story
* **Privacy is not an afterthought** — raw data pipelines, once built, are hard to untangle
* **Guardrails before machinery** — better to define boundaries than retrofit them later

This is mature.

---

## What Changed (Just Now)

### Added clarity markers:

**In `household_safety.py` (top docstring)**:
```
STATUS: DORMANT GUARDRAIL (not active in hot path)
```

**In `privacy.py` (top docstring)**:
```
STATUS: DORMANT GUARDRAIL (not active in data pipeline)
```

**In `main.py` (near imports)**:
```python
# NOTE: privacy.py and household_safety.py are imported in Q2 2026+.
# They currently exist as dormant guardrails, not active machinery.
```

### Why this matters:

1. **Prevents accidental integration** — future you won't think "let's use this safety module" without checking status
2. **Documents activation timeline** — Q1 2026 (privacy) and Q2 2026 (safety)
3. **Makes intent explicit** — these are specs, not features

---

## Decision Map: When They Activate

| Timeline | Module | Activation | Status |
|---|---|---|---|
| **Q1 2026** | `privacy.py` | Wrap telemetry pipeline | Real data collection starts |
| **Q1 2026** | `privacy.py` | Enterprise cloud mode available | (household = local-only) |
| **Q2 2026** | `household_safety.py` | Wrap honeypot + AI layers | Safety begins intervening |
| **Q2 2026** | `household_safety.py` | Transparent proxy deployments | (TIER 2) |

Until those dates:

* System works **without them being active**
* They are insurance code, not core logic
* All Layer 0/1/2 improvements happen **independently** of safety/privacy wrappers

---

## "Did I build the roof before the walls?" Answer

**No.** You built:

- **Walls** (Layer 0, 1, 2) — detection logic
- **Blueprints for the roof** (safety, privacy specs) — non-negotiable constraints
- **Scaffolding** (routes, honeypot emulators) — deployment machinery

The roof (safety/privacy active) comes later.

That's the right order.

---

## How to Verify This Stays True

### Quick check: Are they dormant?

```bash
# Should return ZERO matches in core paths
grep -r "HouseholdSafeHoneypot\|PrivacyPreservingTelemetry" \
  backend/app/*.py \
  --include="*" \
  --exclude="privacy.py" \
  --exclude="household_safety.py"

# Should return ZERO imports
grep "from.*privacy import\|from.*household_safety import" backend/app/main.py
```

### Before Q2 2026, if you see:

- `SafetyBoundedPredictor` actively pruning sessions → Stop, that's premature
- Cloud telemetry exporting raw data → Stop, that violates privacy spec
- Network latency logic shaping Layer 1 → Stop, that's backwards

**All of those would be "roof before walls" mistakes.**

You haven't made any of them.

---

## How to Use Them Now

### For Layer 0/1/2 development:
Ignore them. Build detection freely.

### For testing:
```python
# OK to use in unit tests
from backend.app.privacy import PrivacyMode, TelemetryConfig

config = TelemetryConfig(privacy_mode=PrivacyMode.HOUSEHOLD)
assert not config.is_cloud_enabled()
```

### For deployment scripts:
```python
# Q2 2026: Wrap honeypot in safety
# from backend.app.household_safety import HouseholdSafeHoneypot
# honeypot = HouseholdSafeHoneypot(real_honeypot_instance)

# For now: Direct deployment
honeypot = RealHoneypot()
```

---

## Bottom Line

You had the right doubt.

You also had the right architecture.

Now it's **explicitly documented** that both are true.

No more ambiguity. Keep building Layer 1/2 without worrying about these guardrails interfering.
