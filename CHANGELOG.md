# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.12] - 2026-03-15

### Changed
- Updated org references from GeoMarceauOrg to NexteraLabs

## [0.1.11] - 2026-03-14

### Added
- SRE deploy config (`.deploy.yaml`, `.sre-support.md`)
- CI pipeline with Docker build and push

### Changed
- Docker Compose: replace named volume with bind mount for `/app/brain`
- Health check endpoint updated to use `/channels`

## [0.1.10] - 2026-02-13

### Added
- Secure token handling with Pydantic `SecretStr`
- Token redaction from logs via regex filtering
- Token format validation in configuration

### Changed
- Migrated from Poetry to `uv` for dependency management
- Switched from ULID to simple counter IDs (`#123` format) for user-facing prompt references

## [0.1.0] - 2026-01-09

### Added
- FastAPI application with Prompt API and Channel Gateway
- Long polling via aiogram (no webhook required)
- PostgreSQL persistence for prompts and channels
- Button and text-pattern (`ID:#123 response`) answer modes
- HMAC-signed callback notifications with Tenacity retry logic
- Typer CLI: `init_db`, `init_channels`, `run_api`, `list_channels`, `fresh_start`
- Docker Compose deployment
- Per-channel polling with auto-restore on startup
- TTL-based prompt expiration

[Unreleased]: https://github.com/NexteraLabs/tg_tunnel/compare/v0.1.12...HEAD
[0.1.12]: https://github.com/NexteraLabs/tg_tunnel/compare/v0.1.11...v0.1.12
[0.1.11]: https://github.com/NexteraLabs/tg_tunnel/compare/v0.1.10...v0.1.11
[0.1.10]: https://github.com/NexteraLabs/tg_tunnel/compare/v0.1.0...v0.1.10
[0.1.0]: https://github.com/NexteraLabs/tg_tunnel/releases/tag/v0.1.0
