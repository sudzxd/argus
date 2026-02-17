# Argus

**AI-powered pull request reviews that understand your codebase.**

---

## The Problem

Code review is one of the most important parts of the development process — and one of the most neglected by current tooling. Existing AI review tools treat every pull request as an isolated diff. They scan line-by-line, flag surface-level style issues, and miss what actually matters: whether the change makes sense in the context of *your* codebase.

They don't know your architecture. They don't know your patterns. They don't know that the function being modified is called by three critical services, or that a similar bug was introduced and fixed two months ago.

## What Argus Does

Argus is a GitHub Action that reviews pull requests with deep understanding of your codebase.

It builds and maintains a semantic map of your repository — the structure, the dependencies, the patterns, the intent behind the code. When a pull request is opened, Argus doesn't just read the diff. It understands what changed, why it matters, and what it affects.

Reviews are posted directly on the pull request as bot comments: a summary of findings, inline annotations on specific lines, and actionable suggestions — not noise.

## Key Capabilities

- **Codebase-aware reviews** — Every review is grounded in the full context of your repository, not just the changed lines.
- **Smart retrieval** — A hybrid retrieval system that combines structural analysis, sparse search, and LLM-driven reasoning to find exactly the right context for each review.
- **Multi-provider LLM support** — Bring your own model. Supports Claude, OpenAI, Ollama, and any OpenAI-compatible API endpoint.
- **Incremental context** — The codebase map updates incrementally with each pull request. No expensive full re-indexing on every run.
- **Checkpointed context** — Codebase understanding is versioned and stored as GitHub Actions artifacts. Context builds on itself over time.
- **Zero infrastructure** — No databases, no servers, no external services beyond the LLM API. Everything runs inside GitHub Actions.

## Status

Core pipeline complete — 233 tests passing, 91% coverage. All layers (shared, domain, infrastructure, application, interfaces) are implemented. Pending final quality sign-off.

---

*Named after Argus Panoptes — the many-eyed giant of Greek mythology.*
