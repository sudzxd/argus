<p align="center">
  <img src="website/public/argus-logo.svg" alt="Argus" width="80">
</p>

<h1 align="center">Argus</h1>

<p align="center">
  AI-powered code reviews that understand your entire codebase.
</p>

<p align="center">
  <a href="https://github.com/sudzxd/argus/actions/workflows/ci.yml"><img src="https://github.com/sudzxd/argus/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI"></a>
  <img src="https://img.shields.io/badge/python-3.12+-blue" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/coverage-80%25-brightgreen" alt="Coverage">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-green" alt="License"></a>
  <a href="https://sudzxd.github.io/argus/"><img src="https://img.shields.io/badge/docs-website-e8a838" alt="Website"></a>
  <a href="https://github.com/marketplace/actions/argus-pr-reviewer"><img src="https://img.shields.io/badge/marketplace-GitHub%20Actions-2088FF" alt="Marketplace"></a>
</p>

---

Argus indexes your repository into a semantic map, retrieves relevant context for every diff, and delivers precise inline review comments on your pull requests. It learns your codebase's patterns and conventions over time.

## Quick Start

```yaml
# .github/workflows/argus-review.yml
name: Argus PR Review
on:
  pull_request:
    types: [opened, synchronize]

permissions:
  contents: read
  pull-requests: write

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: sudzxd/argus@v0
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
```

See the [getting started guide](https://sudzxd.github.io/argus/docs/getting-started) for bootstrap and indexing setup.

## Features

- **Codebase-aware** — Reviews grounded in your full repository, not just the diff
- **Hybrid retrieval** — Structural analysis, BM25 lexical search, optional semantic embeddings, and agentic exploration
- **PR context-aware** — Incorporates CI status, git health, prior comments, and related issues into reviews
- **Pattern memory** — Learns conventions and anti-patterns through incremental analysis
- **Multi-provider** — Anthropic, OpenAI, Google Gemini, or any OpenAI-compatible endpoint
- **Zero infrastructure** — Runs entirely in GitHub Actions with artifacts on an orphan branch

---

<p align="center">
  <em>Named after Argus Panoptes — the many-eyed giant of Greek mythology.</em>
</p>
