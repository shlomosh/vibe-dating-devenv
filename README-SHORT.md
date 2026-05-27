# Shoss - Short AI Context

Shoss is a location-based LGBTQ+ dating Telegram Mini-App.

## Mission

Deliver a fast, privacy-aware social discovery experience inside Telegram.

## Product Essentials

- Users can create 1-3 profiles
- Profile types:
  - `public`: visible in nearby profile feed
  - `anonymous`: profile hidden, posts can still appear
- Each profile can have up to 5 media assets
- Each profile can have one active feed post (text and/or media)

## Current State

- Working: auth, profiles, media, location, nearby feed, posts
- Partial: chat/inbox frontend still uses mock data in places
- Deployed backend includes WebSocket chat infrastructure
- Missing/incomplete: full chat history APIs, match/block system, push notifications, moderation

## Tech Stack

- Frontend: React 18, TypeScript, Vite, Tailwind v4, shadcn/ui, Telegram SDK
- Backend: Python 3.11+, AWS Lambda, API Gateway (REST + WebSocket)
- Data: DynamoDB (`shoss-{env}`, `shoss-chat-{env}`)
- Media/Hosting: S3 + CloudFront (`tma.shoss.io`)
- Auth: Telegram WebApp auth -> JWT

## AI Guidance

- Preserve privacy and visibility rules (`public` vs `anonymous`)
- Keep changes aligned with current React + TypeScript and Lambda + CloudFormation architecture
- Assume chat/safety features are active roadmap items, not fully complete
