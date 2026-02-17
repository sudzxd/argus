# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in Argus, please report it responsibly.
**Do not open a public GitHub issue.**

### How to Report

1. Email the maintainers with a description of the vulnerability
2. Include steps to reproduce the issue
3. Provide any relevant logs, screenshots, or proof-of-concept code
4. Specify the affected version(s)

### What to Expect

- **Acknowledgment** within 48 hours of your report
- **Initial assessment** within 5 business days
- **Resolution timeline** communicated after assessment
- **Credit** in the release notes (unless you prefer to remain anonymous)

## Security Considerations

Argus operates as a GitHub Action with access to repository code and GitHub API
tokens. The following security measures are in place:

### Token Handling

- GitHub tokens are passed via environment variables and never logged
- API tokens are scoped to the minimum permissions required
- No tokens or credentials are written to disk or persisted in artifacts

### LLM Provider Communication

- All LLM API calls are made over HTTPS
- API keys are passed via standard authorization headers
- No repository code is cached or stored by Argus beyond the action runtime

### Artifact Storage

- Codebase map artifacts are stored locally using SHA256-hashed filenames
- Artifacts contain structural metadata (symbols, imports) not raw source code
- Storage paths are scoped to prevent directory traversal

### Input Validation

- GitHub event payloads are validated before processing
- Configuration values are type-checked with clear error messages
- Diff parsing handles malformed input gracefully

## Best Practices for Users

- Use GitHub's built-in secrets management for all API keys
- Grant the action minimal repository permissions (`contents: read`,
  `pull-requests: write`)
- Review the action's source code before use in private repositories
- Pin the action to a specific commit SHA rather than a branch tag
