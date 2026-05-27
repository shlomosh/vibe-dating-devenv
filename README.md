# Shoss - AI Model Context

## Project

Shoss is a location-based dating app for the LGBTQ+ community, delivered as a Telegram Mini-App.
The product is mobile-first and runs inside Telegram WebApp, with a React frontend and a Python serverless backend on AWS.

Core value proposition:

- Help users discover nearby people in a safer, privacy-aware way
- Support both visible and anonymous participation modes
- Enable lightweight social discovery through profiles and short feed posts

---

## Objective

The main objective is to provide a fast, inclusive, and privacy-aware dating/discovery experience inside Telegram.

Product goals:

- Make onboarding and profile setup quick and simple
- Let users control visibility with `public` and `anonymous` profile types
- Show relevant nearby content using location-based feed queries
- Support media-rich profiles/posts with optimized upload and delivery
- Evolve toward real-time chat, safety controls, and moderation capabilities

---

## About Us

Shoss is being built as a community-focused LGBTQ+ product with emphasis on:

- Inclusion and identity safety
- User privacy and visibility control
- Mobile-native UX inside Telegram
- Iterative delivery of practical, high-impact features

Tone and product direction prioritize respectful interactions, low friction, and trust.

---

## Technical Architecture

- Frontend: React 18, TypeScript, Vite, Tailwind CSS v4, shadcn/ui, Telegram SDK
- Backend: Python 3.11+, AWS Lambda, API Gateway (REST + WebSocket)
- Data: DynamoDB single-table design (`shoss-{env}`) and chat table (`shoss-chat-{env}`)
- Media: S3 + processing pipeline + CloudFront delivery
- Auth: Telegram WebApp authentication -> JWT
- IaC: CloudFormation templates
- Hosting domain: `tma.shoss.io`

Backend services (high level):

- Authentication and JWT authorizer
- Profile management
- Media upload and processing
- Location management
- Nearby feed query
- Chat WebSocket connection and message handlers

---

## Current Product State

Implemented and working in production-like flow:

- Telegram auth + JWT flow
- Multi-profile management (up to 3 profiles)
- Profile types: `public` and `anonymous`
- Profile media uploads and processing
- Location update/clear
- Nearby feed retrieval
- Feed post creation (text and optional media)

Partially implemented / pending:

- Chat and inbox UI currently rely on mock data in frontend
- WebSocket backend exists, but full frontend integration is incomplete
- Chat history REST APIs are not fully implemented
- Match/block system not complete
- Push notifications and moderation are planned

---

## Domain Rules (Important for AI Tasks)

- A user can have 1 to 3 profiles
- A profile can have 0 to 5 media assets
- Profile type affects discoverability:
  - `public`: visible in nearby profile feed
  - `anonymous`: hidden as a profile but can appear via posts
- A profile can create one active feed post at a time
- Media records use association type: `profile` or `post`

---

## Guidance for AI Assistants

When generating code, docs, or product suggestions for this repository:

- Keep compatibility with Telegram Mini-App constraints
- Respect privacy and visibility rules (`public` vs `anonymous`)
- Prefer extending existing service boundaries over adding new ad-hoc services
- Keep backend changes aligned with Lambda + CloudFormation patterns
- Keep frontend changes aligned with current React + TypeScript architecture
- Treat chat, moderation, and safety as active roadmap areas (not fully complete)

If uncertain, prioritize consistency with existing docs:

- `docs/PROJECT-STATUS.md`
- `docs/architecture/system-architecture.md`
- `docs/architecture/chat-architecture.md`
- `docs/api/api-reference.md`

