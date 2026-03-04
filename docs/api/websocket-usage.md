# WebSocket Integration Guide

This document explains how to use the WebSocket integration for real-time chat in the Vibe Dating application.

## Overview

The WebSocket infrastructure is implemented according to `docs/backend/chat-architecture.md` specification. It provides real-time messaging capabilities through AWS API Gateway WebSockets with auto-reconnection support.

## Architecture

- **WebSocket Client**: `src/api/websocket.ts` - Low-level WebSocket connection management
- **WebSocket Context**: `src/contexts/WebSocketContext.tsx` - React context for managing socket connections
- **WebSocket Types**: `src/types/websocket.ts` - TypeScript interfaces for messages and actions

## Integration

The WebSocket provider is already integrated into the application hierarchy:

```tsx
// src/components/App.tsx
<WebSocketProvider>
  {/* Rest of the app */}
</WebSocketProvider>
```

## Usage in Components

### Basic Usage

```tsx
import { useWebSocket } from '@/contexts/WebSocketContext';
import type { WebSocketMessage } from '@/types/websocket';

function ChatPage() {
  const {
    status,           // 'connecting' | 'connected' | 'disconnected' | 'error'
    isConnected,      // boolean
    error,            // string | null
    sendMessage,      // Send a message
    sendTypingStatus, // Send typing indicator
    flashQueue,       // Request queued messages
    onMessage,        // Current message handler
    setOnMessage      // Set message handler
  } = useWebSocket();

  // Set up message handler
  useEffect(() => {
    const handleMessage = (message: WebSocketMessage) => {
      console.log('Received message:', message);
      // Process incoming message
    };

    setOnMessage(handleMessage);
  }, [setOnMessage]);

  // Send a message
  const handleSend = async (recipientProfileId: string, content: string) => {
    const success = await sendMessage(recipientProfileId, content, 'text');
    if (!success) {
      console.error('Failed to send message');
    }
  };

  return (
    <div>
      {!isConnected && <div>Connecting...</div>}
      {error && <div>Error: {error}</div>}
      {/* Your chat UI */}
    </div>
  );
}
```

### Example: ChatPage Integration

Here's how to integrate WebSocket into ChatPage:

```tsx
import { useWebSocket } from '@/contexts/WebSocketContext';
import type { WebSocketMessage } from '@/types/websocket';

export const ChatPage: React.FC = () => {
  const { profileId } = useParams<{ profileId: string }>();
  const [messages, setMessages] = useState<Message[]>([]);
  const { sendMessage, status, error, setOnMessage } = useWebSocket();

  // Set up message handler
  useEffect(() => {
    setOnMessage((wsMessage: WebSocketMessage) => {
      // Convert WebSocket message to local Message format
      const localMessage: Message = {
        id: Date.now(),
        text: typeof wsMessage.content === 'string'
          ? wsMessage.content
          : wsMessage.content.data,
        isMe: wsMessage.senderProfileId === profileId, // You need to get your profile ID
        timestamp: new Date(wsMessage.createdAt)
      };
      setMessages(prev => [...prev, localMessage]);
    });
  }, [setOnMessage, profileId]);

  // Update handleSendMessage to use WebSocket
  const handleSendMessage = async (text: string) => {
    if (!profileId) return;

    // Send via WebSocket
    const success = await sendMessage(profileId, text, 'text');

    if (success) {
      // Optimistically add message to UI
      const newMessage: Message = {
        id: Date.now(),
        text,
        isMe: true,
        timestamp: new Date()
      };
      setMessages(prev => [...prev, newMessage]);
    }
  };

  // Rest of the component...
};
```

## Message Structure

### WebSocket Message

```typescript
interface WebSocketMessage {
  messageId: string;
  chatId: string;
  senderProfileId: string;
  recipientProfileId: string;
  content: MessageContent | string;
  contentType: 'text' | 'image';
  status?: 'sent' | 'delivered' | 'read';
  createdAt: number;
}
```

### Content Types

**Text Message**:
```json
{
  "action": "sendMessage",
  "messageId": "abc12345",
  "senderProfileId": "profileA",
  "recipientProfileId": "profileB",
  "content": "Hello!",
  "contentType": "text"
}
```

**Image Message**:
```json
{
  "action": "sendMessage",
  "messageId": "abc12345",
  "senderProfileId": "profileA",
  "recipientProfileId": "profileB",
  "content": "https://media.vibe-dating.io/...",
  "contentType": "image"
}
```

**Typing Indicator**:
```json
{
  "action": "typingStatus",
  "messageId": "msg12345",
  "senderProfileId": "profileA",
  "recipientProfileId": "profileB",
  "typing": true
}
```

## Configuration

### Environment Variables

Set these in your environment:

- `VITE_WEBSOCKET_URL`: Custom WebSocket URL (optional)
- `VITE_ENVIRONMENT`: Environment (dev/staging/prod)

Default WebSocket URL: `wss://chat.vibe-dating.io/{environment}`

### Authentication

WebSocket authentication is handled automatically:
1. JWT token is retrieved from `authApi.getAuthentication()`
2. Active profile ID is retrieved from auth data
3. Connection parameters are passed as query string: `?token={jwt}&profileId={profileId}`
4. API Gateway authorizer validates the token and injects `userId` into context

## Connection Management

The WebSocket client automatically:
- Reconnects on connection loss
- Retries with exponential backoff
- Maintains connection pool
- Handles authentication refresh
- Cleans up on unmount

## Error Handling

```tsx
const { error, status, isConnected } = useWebSocket();

useEffect(() => {
  if (status === 'error') {
    console.error('WebSocket error:', error);
    // Handle error (show notification, retry logic, etc.)
  }
}, [status, error]);
```

## Testing

See `chat_test_app.py` for a Python-based test client that demonstrates:
- WebSocket connection
- Message sending and receiving
- Action-based message routing
- Authentication flow

## Next Steps

1. **Update ChatPage**: Replace mock messages with WebSocket integration
2. **Image Support**: Implement image upload for chat messages
3. **Typing Indicators**: Add typing status display
4. **Read Receipts**: Implement message status tracking
5. **Offline Support**: Add message queuing for offline users

## API Reference

### WebSocketClient

Low-level WebSocket client with auto-reconnection.

```typescript
class WebSocketClient {
  constructor(jwtToken: string, profileId: string);

  connect(): Promise<void>;
  disconnect(): void;
  sendMessage(recipientProfileId: string, content: string, type?: ChatMessageType): Promise<boolean>;
  sendTypingStatus(recipientProfileId: string, typing: boolean): Promise<boolean>;
  flashQueue(): Promise<boolean>;
  isConnected(): boolean;

  addMessageListener(listener: (message: WebSocketMessage) => void): () => void;
  addStatusListener(listener: (status: ConnectionStatus) => void): () => void;
  addErrorListener(listener: (error: string) => void): () => void;
}
```

### useWebSocket Hook

React hook for WebSocket access.

```typescript
function useWebSocket(): WebSocketContextValue {
  return {
    status: ConnectionStatus;
    isConnected: boolean;
    error: string | null;
    sendMessage: (recipientProfileId: string, content: string, type?: ChatMessageType) => Promise<boolean>;
    sendTypingStatus: (recipientProfileId: string, typing: boolean) => Promise<boolean>;
    flashQueue: () => Promise<boolean>;
    connect: () => Promise<void>;
    disconnect: () => void;
    onMessage?: (message: WebSocketMessage) => void;
    setOnMessage: (handler: (message: WebSocketMessage) => void) => void;
  };
}
```

## Security

- JWT token authentication via API Gateway authorizer
- Profile-based authorization
- Encrypted WebSocket connections (WSS)
- Message content validation
- Rate limiting at API Gateway level

## Performance

- Auto-reconnection prevents message loss
- Connection pooling reduces overhead
- Message batching (future enhancement)
- Efficient reconnection timing (exponential backoff)
- Sub-100ms latency for real-time messages

