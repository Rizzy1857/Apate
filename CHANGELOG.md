# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased] - 2026-07-08

### Changed
- **Ubuntu-Only Architecture:** Completely refactored the AI intelligence layer to focus exclusively on emulating Ubuntu 24.04. Removed support and configurations for multiple personas (e.g., vulnerable_db, iot_device, Debian).
- **Inference Runtime:** Replaced cloud LLM providers (OpenAI, Anthropic) and Mock providers with a local-only, air-gapped `InferenceRuntime` pointing to Ollama. Removed the old `ModelRouter` which relied on Debian-era routing (`sql_dump`).
- **Configuration:** Cleaned up `config.example.json` to remove IoT ports and cloud API keys. Updated to point to `config/ubuntu.yaml` and `config/generation_policy.yaml`.
- **Documentation:** Extensively updated `README.md`, `docs/ONBOARDING.md`, `docs/STATUS.md`, `docs/AI_ROADMAP.md`, `docs/AI_ARCHITECTURE.md`, and `docs/AI_LOGIC.md` to reflect the new deterministic, constraint-driven, Ubuntu-only architecture. Removed mentions of persona engines, fidelity tier selectors, and cloud LLMs.
- **Testing:** Rewrote `verify_phase3.py` to validate the new Ubuntu-only components (`UbuntuProfile`, `ArtifactPolicyEngine`, `PromptBuilder`, `SemanticValidator`). It now strictly rejects non-Ubuntu patterns (Windows, PowerShell, yum, dnf, zypper).
- **Integration Demo:** Rewrote `tests/integration/demo_integration.py` to remove `PersonaEngine` dependencies and showcase the new Ubuntu artifact policy pipeline. Updated `tests/README.md`.

### Fixed
- Fixed lingering `root@honeypot:~#` prompt in the SSH gateway `Ctrl+C` handler to correctly reflect the Ubuntu hostname and primary user.
- Fixed stale export of `ModelRouter` in `src/chronos/intelligence/__init__.py`.
