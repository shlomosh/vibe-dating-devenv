# Chat Infrastructure Specification for Vibe Dating Mini-App

## Document Information

- **Document Title**: Specification for Real-Time Chat Infrastructure on AWS
- **Version**: 3.0
- **Date**: January 2025
- **Author**: AI Assistant (Merged from versions 2.0 and 2.1)
- **Purpose**: This document outlines a comprehensive specification for implementing a real-time chat feature in the Vibe Dating Mini-App, a Telegram-based dating platform for the gay community. It details the architecture, features, design, components, and implementation strategies, integrating with the existing AWS serverless backend (API Gateway, Lambdas, DynamoDB, S3, CloudFront) and React/TypeScript frontend as defined in the Vibe Dating App System Architecture. The system uses profile-ids (8-character base64 strings) for identification, leverages the existing DynamoDB `vibe-dating` table for profiles and media, and uses a separate DynamoDB table `vibe-dating-chat` for chat data. Media handling uses S3 with signed URLs. Authentication is handled by API Gateway using JWT for both REST and WebSocket; WebSocket clients pass the JWT as query parameter `token`. Backend implementation uses Python 3.11+ with internal `core_types` dataclasses for data validation, consistent with the existing codebase.

## 1. Introduction

### 1.1 Overview

This specification defines the infrastructure for a scalable, real-time chat feature within the Vibe Dating Mini-App, replacing third-party services (e.g., Agora.io) with a custom AWS-based solution. The feature supports one-to-one text and image messaging, persists messages for offline delivery, and integrates seamlessly with the existing AWS-based infrastructure. The design prioritizes serverless architecture for cost efficiency, scalability, and minimal maintenance, leveraging Python 3.11+ with msgspec for data validation, consistent with the existing codebase. Authentication is managed at the API Gateway level using the existing JWT and `initData` authorizers, eliminating the need for Lambda-level authentication logic.

Key differentiators:

- **Dedicated Chat Storage**: Separate `vibe-dating-chat` DynamoDB table for chat data, distinct from `vibe-dating` table for better separation of concerns.
- **Full integration** with existing AWS stack (API Gateway, Lambdas, DynamoDB, S3, CloudFront).
- **Use of profile-ids** as 8-character base64 strings for privacy and matching logic, consistent with Vibe's ID system.
- **Cost-effective**, pay-per-use pricing without MAU-based tiers.
- **Secure media handling** via existing S3/CloudFront infrastructure with signed URLs.
- **Python-based backend** for consistency; authentication offloaded to API Gateway.
- **Consistent with existing data models** and validation patterns using `msgspec`.

### 1.2 Scope

- **In Scope**: Real-time 1:1 text/image messaging, offline message delivery, message history, basic read receipts, integration with Telegram WebApp API, and JWT/`initData`-based authentication for REST endpoints handled by API Gateway.
- **Out of Scope**: Group chats, video/voice calls, end-to-end encryption (extensible via AWS KMS), advanced AI moderation, or push notifications outside Telegram's ecosystem.

### 1.3 Assumptions

- **API Gateway authorizer** validates JWT for both WebSocket and REST API calls. WebSocket clients pass `token` (JWT) and `profileId` as query parameters; the authorizer populates `userId` in the Lambda context.
- **Existing DynamoDB table**: `vibe-dating` (single-table design for profiles, media, etc.).
- **New DynamoDB table**: `vibe-dating-chat` for chat and connection data.
- **S3 bucket** `vibe-dating-media-dev` for all media (profile images and chat images); served via CloudFront (`media.vibe-dating.io`). **Note**: There is no separate chat-specific S3 bucket; chat images use the same media bucket as profile images.
- **Frontend runs** in Telegram's webview, supporting WebSockets.
- **Compliance**: GDPR-compliant with TTL; minimal PII in chat data.
- **Integration** with existing media management system for image sharing.

## 2. Requirements and Features

### 2.1 Functional Requirements

1. **Real-Time Messaging**: Users can send/receive text messages instantly when both are online (matched profiles only).
2. **Offline Messaging**: Messages to offline users are stored in `vibe-dating-chat` and delivered upon reconnection.
3. **Image Sharing**: Users upload images to the existing media S3 bucket (`vibe-dating-media-dev`), served via signed CloudFront URLs (`media.vibe-dating.io`).
4. **Message History**: Load chat history (e.g., last 100 messages per chat) via REST API.
5. **Read Receipts**: Track message status (sent, delivered, read) in `vibe-dating-chat`.
6. **Chat Initiation**: Chats require mutual match (verified via `PROFILE` entity in `vibe-dating`).
7. **Blocking/Reporting**: Integrate with `USER` entity in `vibe-dating` for blocking/reporting.
8. **Notifications**: In-app unread message indicators; leverage Telegram bot for notifications if available.

### 2.2 Non-Functional Requirements

- **Performance**: <100ms latency for real-time messages; support 10K concurrent connections.
- **Scalability**: Auto-scale to 1M+ users via serverless design.
- **Reliability**: 99.99% uptime; message durability via DynamoDB.
- **Security**: API Gateway handles JWT/`initData` authentication; signed S3 URLs (15-minute expiry, per `CoreSettings`).
- **Cost**: Target < $0.05/user/month at scale.
- **Usability**: Mobile-optimized React UI; Telegram theme support (e.g., dark mode via `window.Telegram.WebApp.themeParams`).
- **Accessibility**: ARIA-compliant chat UI; support for Telegram's dynamic theming.

### 2.3 User Stories

- As User A, I can send a text or image to User B in real-time if we're matched.
- As User B (offline), I receive all pending messages when I open the app.
- As a developer, I can extend the system for future features (e.g., typing indicators).

## 3. Architecture Overview

### 3.1 High-Level Diagram

(Conceptual; implement in Draw.io or Lucidchart)

- **Clients**: React/TypeScript frontend in Telegram webview.
- **Real-Time Layer**: API Gateway WebSocket API (`wss://chat.vibe-dating.io`) for bidirectional messaging.
- **Backend Processing**: Python 3.11+ Lambdas: `chat_websocket_mgmt` for `$connect`/`$disconnect` and `chat_websocket_msgs` for `$default` (action-based messages).
- **Storage**: DynamoDB `vibe-dating-chat` table (chat and connection data); `vibe-dating` table (profiles, media).
- **Media**: Existing S3 bucket (`vibe-dating-media-dev`) for all images including chat; CloudFront (`media.vibe-dating.io`) for delivery.
- **REST API**: Existing API Gateway (`https://api.vibe-dating.io`) for JWT-validated presigned S3 URLs and history queries.

**Flow**:

1. Client connects via WebSocket (passes `token` (JWT) and `profileId`; API Gateway authorizer validates; `userId` is available in Lambda).
2. On connect: `chat_websocket_mgmt` stores the connection and may push queued/unread messages.
3. Messaging: Client sends JSON payloads to `$default` with an `action` field; `chat_websocket_msgs` persists and delivers messages (`sendMessage`), typing indicators (`typingStatus`), or flushes queued messages (`flashQueue`).
4. Image upload: Client requests presigned S3 URL (existing REST API with JWT), uploads to the existing media bucket (`vibe-dating-media-dev`), sends the resulting URL in a chat message.
5. History: Planned REST API for older messages; not yet implemented.

### 3.2 Design Principles

- **Serverless**: Use Lambdas, API Gateway, DynamoDB for zero server management.
- **Dedicated Chat Table**: Store chat data in `vibe-dating-chat` to separate concerns from `vibe-dating`.
- **Event-Driven**: WebSocket routes trigger Python Lambdas; DynamoDB Streams for future extensions.
- **Separation of Concerns**: Chat records within dedicated table; separate business logic in Python Lambda layers.
- **Idempotency**: Use 8-character base64 message-ids (UUID v5-derived) to prevent duplicates.
- **Security-First**: API Gateway handles authentication; Lambdas focus on business logic.
- **Consistency**: Use `msgspec` for data validation, matching system architecture.

## 4. Backend Components

### 4.1 AWS Services

- **API Gateway (WebSocket API)**: Manages WebSocket connections; routes: `$connect`, `$disconnect`, `sendMessage`. Authentication via API Gateway authorizer (Telegram `initData`).
- **API Gateway (REST API)**: Existing (`api.vibe-dating.io`); adds `/profile/{profileId}/chat` and `/chat/presigned-url` endpoints (JWT-authenticated).
- **Lambdas**: Python 3.11+ with `msgspec`; handle WebSocket logic, message persistence, S3 URL generation.
- **DynamoDB**: `vibe-dating-chat` table for chat data; `vibe-dating` table for profiles/media.
- **S3**: Existing media bucket (`vibe-dating-media-dev`) for all images including chat images; private access.
- **CloudFront**: CDN (`media.vibe-dating.io`) for image delivery.
- **IAM**: Roles for Lambdas (DynamoDB read/write, S3 put/get, API Gateway Management API).
- **CloudWatch**: Logs, metrics, alarms (30-day retention).
- **KMS**: Existing key for DynamoDB encryption.

### 4.2 Data Models (DynamoDB)

#### vibe-dating-chat Table

**Chat Message Records**:

**Primary Record Pattern**:
```
PK: "CHAT#{chatId}" (chatId: sorted profileIdA_profileIdB, 8-char base64 each)
SK: "MESSAGE#{timestamp}" (timestamp: Unix epoch in ms)
```

**Chat Message Entity**:
```json
{
  "PK": "CHAT#{chatId}",
  "SK": "MESSAGE#{timestamp}",
  "messageId": "aB3cD4eF",
  "chatId": "profileA_profileB",
  "senderProfileId": "profileA",
  "recipientProfileId": "profileB",
  "content": {
    "type": "text|image",
    "data": "message text or S3 URL"
  },
  "status": "sent|delivered|read",
  "createdAt": 1704067200000,
  "TTL": 1735689600
}
```

**Connection Records**:

**Primary Record Pattern**:
```
PK: "CONNECTION#{profileId}" (String; 8-char base64)
SK: "METADATA"
```

**Connection Entity**:
```json
{
  "PK": "CONNECTION#{profileId}",
  "SK": "METADATA",
  "connectionId": "websocket_connection_id",
  "lastConnected": 1704067200,
  "createdAt": 1704067200
}
```

#### Global Secondary Indexes (GSIs)

**GSI1 - Message Queries by Recipient**:
- PK: `PROFILE#{recipientProfileId}`
- SK: `CHAT#{timestamp}`
- Use Case: Query unread messages for a specific recipient

**GSI2 - Message Queries by Sender**:
- PK: `SENDER#{senderProfileId}`
- SK: `MESSAGE#{timestamp}`
- Use Case: Query sent message history for a specific sender

**GSI3 - Chat History Queries**:
- PK: `CHAT#{chatId}`
- SK: `MESSAGE#{timestamp}`
- Use Case: Query message history for a specific chat

#### Integration with Existing Records

**vibe-dating Table** (Existing):
- **User**: `PK: USER#{userId}`, `SK: METADATA` (validate user existence)
- **Profile**: `PK: PROFILE#{profileId}`, `SK: METADATA` (validate matches)
- **Media**: `PK: PROFILE#{profileId}`, `SK: MEDIA#{mediaId}` (optional; for chat image metadata)

### 4.3 Lambdas (Python)

1. **chat_websocket_mgmt** (`$connect`, `$disconnect`):
   - Extracts `userId` via `extract_user_id_from_context(event)` and reads `profileId` from query string.
   - On `$connect`: registers the connection via `ChatManager.connect()` and may flush queued messages.
   - On `$disconnect`: deregisters the connection via `ChatManager.disconnect()`.

2. **chat_websocket_msgs** (`$default` with action-based routing):
   - Supports the following actions in the JSON payload:
     - `sendMessage`: persists and forwards a message, and acks back to the sender with status `SENT` (or `FAILED` on error).
     - `typingStatus`: forwards typing indicators to the recipient.
     - `flashQueue`: instructs the server to resend any queued messages for the sender.

   Example payloads:

   ```json
   { "action": "sendMessage", "messageId": "abcd1234", "senderProfileId": "pAAAAAAA", "recipientProfileId": "pBBBBBBB", "content": "hi", "contentType": "text" }
   ```

   ```json
   { "action": "typingStatus", "messageId": "efgh5678", "senderProfileId": "pAAAAAAA", "recipientProfileId": "pBBBBBBB", "typing": true }
   ```

   ```json
   { "action": "flashQueue", "senderProfileId": "pAAAAAAA" }
   ```

### 4.4 Security

- **Authentication**:
  - WebSocket: API Gateway authorizer validates Telegram `initData`; passes `profileId`.
  - REST API: API Gateway authorizer validates JWT; passes `profileId`.
- **Authorization**: Check `vibe-dating` table (`PROFILE` entity) for match before allowing chat.
- **Data**: Minimal PII in `vibe-dating-chat` (profile-ids, content only).
- **Media**: S3 bucket private; signed URLs (15-minute expiry).
- **Network**: HTTPS for REST; WSS for WebSockets; CloudFront enforces SSL.

## 5. Frontend Components

### 5.1 Tech Stack

- **React/TypeScript**: For UI; hooks for state/logic (consistent with existing frontend).
- **ReconnectingWebSocket**: Library (`npm i reconnecting-websocket`) for robust WebSocket connections.
- **Axios**: For REST API calls (consistent with existing API integration).
- **React Context**: Manage chat state (messages, unread counts) - consistent with existing state management.
- **Tailwind CSS + shadcn/ui**: Styling; matches Telegram themes (consistent with existing styling).
- **idb-keyval**: Cache messages locally (`npm i idb-keyval`).

### 5.2 Components

1. **ChatWindow**:
   - Displays message history (scrollable `<div>`).
   - Renders text (`<p>`) or images using CloudFront signed URLs.
   - Unread indicator (badge); scroll-to-bottom button.

2. **MessageInput**:
   - Text input (`<input type="text">`) for messages.
   - Image upload integration with existing media management system.
   - Send button triggers WebSocket `sendMessage`.

3. **WebSocket Hook** (`useWebSocket.ts`):

   ```typescript
   import { useEffect, useRef } from 'react';
   import ReconnectingWebSocket from 'reconnecting-websocket';

   interface Message {
     messageId: string;
     chatId: string;
     senderProfileId: string;
     recipientProfileId: string;
     content: { type: 'text' | 'image'; data: string };
     status: 'sent' | 'delivered' | 'read';
     createdAt: number;
   }

   export const useWebSocket = (
     profileId: string,
     jwtToken: string,
     onMessage: (msg: Message) => void
   ) => {
     const wsRef = useRef<ReconnectingWebSocket | null>(null);

     useEffect(() => {
       const initData = window.Telegram.WebApp.initData;
       const ws = new ReconnectingWebSocket(
         `wss://chat.vibe-dating.io/prod?profileId=${profileId}&initData=${encodeURIComponent(initData)}`
       );
       wsRef.current = ws;

       ws.onopen = () => console.log('Connected');
       ws.onmessage = (event) => {
         const data: Message = JSON.parse(event.data);
         onMessage(data);
       };
       ws.onclose = () => console.log('Disconnected');
       ws.onerror = (error) => console.error('WebSocket error:', error);

       return () => ws.close();
     }, [profileId, onMessage]);

     const sendMessage = (
       recipientProfileId: string,
       content: string,
       type: 'text' | 'image'
     ) => {
       if (wsRef.current?.readyState === WebSocket.OPEN) {
         wsRef.current.send(
           JSON.stringify({ action: 'sendMessage', recipientProfileId, content, type })
         );
       }
     };

     return { sendMessage };
   };
   ```

4. **Image Upload Integration** (`useImageUpload.ts`):

   ```typescript
   import axios from 'axios';

   // Note: Chat images use the existing media upload endpoint
   // POST /profile/{profileId}/media
   // This ensures all media (profile and chat) uses the same S3 bucket and management system
   
   const uploadImageForChat = async (file: File, profileId: string, jwtToken: string) => {
     try {
       // Use the existing media upload endpoint
       const { data: { uploadUrl, mediaUrl } } = await axios.post(
         `https://api.vibe-dating.io/prod/profile/${profileId}/media`,
         { fileType: file.type, mediaType: 'chat_image' },
         { headers: { Authorization: `Bearer ${jwtToken}` } }
       );
       
       await axios.put(uploadUrl, file, { 
         headers: { 'Content-Type': file.type } 
       });
       
       return mediaUrl; // Return CloudFront URL to use in chat message
     } catch (error) {
       console.error('Image upload failed:', error);
       throw error;
     }
   };

   export { uploadImageForChat };
   ```

### 5.3 Integration with System Architecture

- **Profile Context**: Use `ProfileRecord` from system architecture to display sender/recipient details.
- **Media Validation**: Enforce `media_allowed_formats` (`jpeg,jpg,png,webp`) and `media_max_file_size` (20MB) client-side.
- **Local Storage**: Cache messages in `idb-keyval` for offline resilience, synced with `vibe-dating-chat`.

## 6. API Endpoints

### 6.1 WebSocket Endpoints

- `$connect` - Establish WebSocket connection (Telegram `initData` authenticated)
- `$disconnect` - Handle connection cleanup
- `sendMessage` - Send chat message to recipient

### 6.2 REST Endpoints

- `GET /profile/{profileId}/chat/{chatId}/history` - Get chat message history with pagination
- `POST /profile/{profileId}/chat/{chatId}/read` - Mark messages as read

### 6.3 Integration with Existing Endpoints

- `POST /profile/{profileId}/media` - Request media upload URL for both profile and chat images (existing endpoint, reused for chat)
- `GET /profile/{profileId}` - Get profile with media access URLs (existing)

**Note**: Chat images use the existing media upload endpoint (`POST /profile/{profileId}/media`) instead of a separate chat-specific endpoint. This ensures all media uses the same S3 bucket (`vibe-dating-media-dev`) and management system.

## 7. Implementation Plan

### 7.1 Phase 1: Core Infrastructure (Week 1-2)
1. **DynamoDB Schema**: Create `vibe-dating-chat` table with GSI for chat queries
2. **Lambda Functions**: Implement WebSocket handlers (`chat_connect`, `chat_disconnect`, `chat_send_message`)
3. **API Gateway**: Configure WebSocket API with Telegram `initData` authorizer
4. **Core Utilities**: Create ChatManager and ConnectionManager classes

### 7.2 Phase 2: Frontend Integration (Week 3-4)
1. **WebSocket Hook**: Implement real-time messaging with `reconnecting-websocket`
2. **Chat Components**: Build chat UI components (ChatWindow, MessageInput)
3. **Media Integration**: Integrate with existing media management system
4. **State Management**: Add chat state to existing React Context

### 7.3 Phase 3: Advanced Features (Week 5)
1. **Message History**: Implement pagination and caching with IndexedDB
2. **Read Receipts**: Add message status tracking
3. **Notifications**: Integrate with Telegram bot notifications
4. **Performance**: Optimize for mobile and low-bandwidth scenarios

## 8. Configuration

### 8.1 Environment Variables

```python
# DynamoDB Configuration
CHAT_TABLE_NAME = os.environ.get("CHAT_TABLE_NAME", "vibe-dating-chat")
PROFILE_TABLE_NAME = os.environ.get("PROFILE_TABLE_NAME", "vibe-dating")

# WebSocket Configuration
WEBSOCKET_ENDPOINT = os.environ.get("WEBSOCKET_ENDPOINT")

# Media Configuration
# Note: Chat uses the existing media bucket, not a separate bucket
MEDIA_S3_BUCKET = os.environ.get("MEDIA_S3_BUCKET", "vibe-dating-media-dev")
CLOUDFRONT_DOMAIN = os.environ.get("CLOUDFRONT_DOMAIN", "media.vibe-dating.io")

# Chat Settings
CHAT_MESSAGE_TTL_DAYS = int(os.environ.get("CHAT_MESSAGE_TTL_DAYS", 365))
CHAT_HISTORY_LIMIT = int(os.environ.get("CHAT_HISTORY_LIMIT", 50))
CHAT_MAX_MESSAGE_LENGTH = int(os.environ.get("CHAT_MAX_MESSAGE_LENGTH", 1000))
```

### 8.2 Core Settings Integration

```python
@dataclass
class CoreSettings:
    # Existing settings...
    
    # Chat Settings
    chat_message_ttl_days: int = 365
    chat_history_limit: int = 50
    chat_max_message_length: int = 1000
    # Note: Chat uses the existing media_s3_bucket, not a separate bucket
    # media_s3_bucket: str = "vibe-dating-media-dev"  # Already defined in CoreSettings
    cloudfront_domain: str = "media.vibe-dating.io"
```

## 9. Monitoring & Observability

### 9.1 CloudWatch Metrics
- WebSocket connection count
- Message throughput and latency
- Error rates by endpoint
- DynamoDB performance metrics

### 9.2 CloudWatch Logs
- WebSocket connection events
- Message delivery tracking
- Error context and stack traces
- Performance metrics

### 9.3 Alerts
- High WebSocket disconnection rates
- Message delivery failures
- DynamoDB throttling
- Lambda timeout alerts

## 10. Security Considerations

### 10.1 Data Protection
- Message content encryption at rest (DynamoDB encryption)
- Secure WebSocket connections (WSS)
- JWT/`initData` token validation for all operations
- Profile-based access control

### 10.2 Privacy Compliance
- GDPR-compliant message retention (TTL-based deletion)
- Minimal PII storage (only profile IDs)
- User data export capabilities
- Right to deletion implementation

### 10.3 Content Moderation
- Integration with existing profile moderation system
- Message content validation
- User reporting capabilities
- Automated content filtering (future enhancement)

## 11. Performance Optimization

### 11.1 Scalability
- Serverless architecture for automatic scaling
- DynamoDB on-demand billing
- WebSocket connection pooling
- Efficient GSI design for query patterns

### 11.2 Caching Strategy
- Local message caching with IndexedDB
- CloudFront caching for media (6-hour TTL)
- DynamoDB DAX for sub-millisecond reads (future)
- Connection state caching

### 11.3 Mobile Optimization
- Progressive message loading
- Image compression and lazy loading
- Offline message queuing
- Bandwidth-aware features

## 12. Cost Analysis

### 12.1 Cost Breakdown
- **DynamoDB**: On-demand mode; ~$0.25/million writes (1KB/message)
- **WebSocket**: ~$1/million messages; $0.25/GB data transfer
- **S3/CloudFront**: ~$0.09/GB storage; $0.085/GB transfer
- **Lambda**: ~$0.20/million requests

### 12.2 Cost Optimization
- **Total**: ~$0.01-0.05/user/month for 10K users (100 messages/day/user)
- Batch DynamoDB writes where possible
- Use CloudFront for image caching
- Implement message TTL to reduce storage costs

## 13. Future Extensions

### 13.1 Planned Features
- **Typing Indicators**: Add WebSocket `typing` action
- **Read Receipts**: Add `read` action to update message status
- **Notifications**: Integrate Telegram bot for offline push notifications
- **Moderation**: Use AWS Comprehend for toxicity detection

### 13.2 Advanced Features
- **Video Messages**: Extend with AWS Chime SDK
- **Message Reactions**: Add emoji reactions to messages
- **Message Search**: Implement full-text search using DynamoDB
- **Group Chats**: Extend architecture for multi-user conversations

## 14. Risks and Mitigations

### 14.1 Technical Risks
- **Risk**: WebSocket disconnects in Telegram webview
  - **Mitigation**: Use `reconnecting-websocket`; cache in IndexedDB
- **Risk**: High DynamoDB costs for write-heavy chats
  - **Mitigation**: Optimize writes; consider reserved capacity for predictable loads
- **Risk**: Authorizer misconfiguration
  - **Mitigation**: Test with mock `initData`/JWT; log failures

### 14.2 Business Risks
- **Risk**: Message delivery failures
  - **Mitigation**: Implement retry logic and offline queuing
- **Risk**: Content moderation challenges
  - **Mitigation**: Integrate with existing moderation systems

## 15. References

- AWS Docs: API Gateway WebSocket, DynamoDB, S3 Presigned URLs
- Telegram WebApp API: `initData` validation
- Libraries: `reconnecting-websocket`, `axios`, `idb-keyval`, `msgspec`
- Vibe Dating System Architecture: Integration patterns and data models

---

*This document provides a comprehensive specification for implementing real-time chat functionality within the existing Vibe Dating infrastructure. The design prioritizes integration with existing systems while maintaining scalability, security, and performance requirements. The merged specification combines the best practices from both versions, ensuring consistency with the current system architecture and providing a clear path for implementation.*
