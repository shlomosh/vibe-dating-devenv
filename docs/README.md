# Shoss - Project Documentation

Consolidated documentation for the Shoss application (Telegram Mini-App).

## Quick Links

- **[Project Status](./PROJECT-STATUS.md)** - What is implemented and what is not
- **[System Architecture](./architecture/system-architecture.md)** - Full-stack architecture and data model
- **[Chat Architecture](./architecture/chat-architecture.md)** - Real-time chat specification
- **[API Reference](./api/api-reference.md)** - REST API endpoints
- **[WebSocket Guide](./api/websocket-usage.md)** - WebSocket integration for chat

## Documentation Structure

```
docs/
├── PROJECT-STATUS.md              # Implementation status report
├── architecture/
│   ├── system-architecture.md     # System overview, data model, infrastructure
│   └── chat-architecture.md       # Chat spec (WebSocket, DynamoDB, REST)
├── api/
│   ├── api-reference.md           # REST API endpoints reference
│   └── websocket-usage.md         # WebSocket client integration guide
├── services/
│   ├── authentication.md          # Auth flow, JWT, Telegram integration
│   ├── profile-management.md      # Profile CRUD, enums, validation
│   ├── media-management.md        # Media upload, processing, CloudFront
│   └── hosting.md                 # Frontend hosting (CloudFront + S3)
├── guides/
│   ├── development-guide.md       # Dev setup and workflow
│   ├── deployment-guide.md        # Deployment procedures
│   └── build-system.md            # Build system (Poetry, scripts)
├── legal/
│   └── terms-and-conditions.md    # Legal terms
├── legacy/                        # Archived older documentation
└── examples/
    └── frontend/auth.js           # Frontend auth example
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS v4, shadcn/ui, Telegram SDK |
| Backend | Python 3.11+, AWS Lambda, API Gateway, DynamoDB, S3, CloudFront |
| Auth | Telegram WebApp + JWT |
| IaC | AWS CloudFormation |
| Chat | AWS API Gateway WebSocket |
