# Repository Layout and Conventions

This document describes the folder structure, naming conventions, and architectural patterns for the AI DJ monorepo.

## Folder Structure
```
/
├── frontend/           - Client SPA application
├── backend/            - Server-side API and services
├── docs/               - Documentation and shared contracts
├── .env.example        - Template for environment variables
├── README.md           - High-level project and run instructions
├── .gitignore          - Git ignores for all parts of the repo
```

## Conventions
- Use TypeScript for frontend code.
- Use Python with FastAPI for backend.
- Define all shared types and contracts explicitly in `/docs/contracts.md`.
- Documentation must be kept updated with architectural decisions and contracts.
- Environment variables for local development should be defined in `.env` files.
- Commit messages should follow Conventional Commits format.

## Important Notes
- Frontend uses Vite; ensure Node.js 18+ is installed.
- Backend uses FastAPI and serves WebSocket endpoints but WS routes are not in OpenAPI specs.
- Follow documentation-driven development strictly.


