# Security Policy

## Reporting a Vulnerability

**Do not create a public GitHub issue for security vulnerabilities.**

Instead, email **georges.marceau@nexteralabs.ca** with:

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (optional)

We will acknowledge receipt within 48 hours and provide a timeline for addressing the issue.

## Scope

This policy covers the `tg-gateway` service, including:

- The FastAPI application and all endpoints
- The channel gateway and prompt services
- The CLI and Docker configuration
- Callback signing and HMAC verification logic

## Credential Hygiene

This project handles Telegram bot tokens and signing secrets. If you discover a hardcoded credential or a way to extract secrets from the service:

- Report it immediately via email (do not post publicly)
- Include the affected file and line number if known

## Supported Versions

Only the latest release on `main` is actively maintained.
