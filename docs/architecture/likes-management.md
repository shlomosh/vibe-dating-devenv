# Likes Management — Architecture & Design Specification

This document describes the Like mechanism for Shoss: how likes are sent, stored, matched, and cleaned up — and the design decisions behind it.

**Related:** [Chat architecture](./chat-architecture.md), [User moderation](./user-moderation.md)

---

## Design Decisions

| # | Decision |
|---|----------|
| **No backend likes table** | Like state is never persisted in a database. The backend only relays like messages through the existing WebSocket/offline-queue infrastructure. |
| **LocalStorage as source of truth** | Each profile keeps its own like state in the browser's LocalStorage — `likesGiven` (likes I sent) and `likesReceived` (likes others sent me). |
| **Boolean `likeState`** | Like messages carry `likeState: boolean` — `true` = like set, `false` = like unset. No string enum. |
| **Offline delivery** | Like messages are queued by the backend for offline delivery using the same SQS/DynamoDB queue as chat messages. This guarantees delivery even when the recipient is disconnected. |
| **Match re-confirmation** | When profile B receives a new like from A and B already liked A (mutual), B re-sends `Like(true)` back to A. This ensures A can detect the match even if A lost its `likesReceived` LocalStorage. |
| **Block clears likes** | When a block event is processed, all like state for the blocked profile is cleared from LocalStorage on both sides. |
| **Unlike removes match** | If an unlike is received for a profile whose inbox entry is a match entry (not yet a real conversation), the match entry is deleted from the inbox. |
| **Match → real chat** | Once the first real chat message is exchanged, the `isMatch` flag is cleared from the inbox entry, converting it to a regular conversation. |

---

## Data Model

### LocalStorage Keys (per active profile)

| Key | Format | Contents |
|-----|--------|----------|
| `vibe/v1/data/likes/given/{activeProfileId}` | `{ v: 1, likes: Record<profileId, unixMs> }` | Profiles I have liked |
| `vibe/v1/data/likes/received/{activeProfileId}` | `{ v: 1, likes: Record<profileId, unixMs> }` | Profiles that have liked me |

### Inbox Entry Extension

Match entries are stored in the standard inbox with an additional flag:

```typescript
interface InboxEntry {
  lastMessage: string;   // '💕' for match entries
  lastTime: number;
  unreadCount: number;
  pinned?: boolean;
  isMatch?: boolean;     // true → this is a mutual-like match, not a real conversation yet
}
```

---

## WebSocket Message

### Outbound (client → backend → peer)

```json
{
  "action": "like",
  "messageId": "<8-char random ID>",
  "senderProfileId": "<sender>",
  "recipientProfileId": "<recipient>",
  "likeState": true
}
```

`likeState: true` = like set, `likeState: false` = like unset.

### Inbound (backend → client)

```json
{
  "messageType": "like",
  "messageId": "<ID>",
  "senderProfileId": "<sender>",
  "recipientProfileId": "<recipient>",
  "likeState": true,
  "timestamp": 1700000000000
}
```

The backend sends an ack (`messageType: "status", status: "sent"`) back to the sender after forwarding.

---

## Backend Handler

**Lambda:** `chat_websocket_msgs` — action route `like`

**Flow:**
1. Validate `likeState` is a boolean.
2. Block check via `ChatManager.check_message_allowed(sender, recipient)` — silently drop if blocked.
3. Forward `ChatMessageLike` to recipient via `send_message` (queued for offline delivery).
4. Send `status: sent` ack back to sender.

**No likes table.** The `ChatMessageLike` struct lives only in the message queue TTL window and is delivered once, then discarded.

---

## Frontend Architecture

### Contexts

```
<WebSocketProvider>
  <PeersProfileProvider>
    <InboxProvider>       ← handles incoming like WS messages (background handler)
      <LikeProvider>      ← manages likesGiven React state, sends outgoing likes
        <App />
```

### LikeContext (`src/contexts/LikeContext.tsx`)

Manages the `likesGiven` map as React state (initialized from LocalStorage on mount).

| Function | Behaviour |
|----------|-----------|
| `isLikedByMe(profileId)` | Reads from React state (O(1) lookup) |
| `toggleLike(profileId)` | Like → add to state + localStorage + send `Like(true)` + check match; Unlike → remove + send `Like(false)` |

Match check on like: if `likesReceived[profileId]` exists at the moment I like them → `trackMatch(profileId)` is called immediately on the inbox.

### InboxContext — background handler additions

The existing background WebSocket handler in `InboxContext` processes `messageType: 'like'` before delegating to the chat parser:

```
receive like message
  ├─ likeState = true
  │   ├─ setLikeReceived(myId, sender)
  │   └─ if NEW like AND hasLikedProfile(myId, sender)
  │       ├─ trackMatch(sender)            → inbox match entry
  │       └─ sendLike(sender, true)        → re-confirmation (match resilience)
  └─ likeState = false
      ├─ clearLikeReceived(myId, sender)
      └─ if inbox entry is isMatch → delete it
```

Block handling (existing `ev.kind === 'block'`): also calls `clearAllLikesForProfile(myId, peer)`.

---

## Like / Unlike Flow

### Profile A likes Profile B

```
A clicks ♥
  → LikeContext.toggleLike(B)
      → likesGiven[B] = now   (localStorage + React state)
      → sendLike(B, true)     (WS → backend → queued for B)
      → if likesReceived[B]   → trackMatch(B) → inbox match entry for A
```

```
B receives like message
  → InboxContext background handler
      → setLikeReceived(B_id, A_id)
      → if hasLikedProfile(B_id, A_id)   (B already liked A)
          → trackMatch(A_id)             → inbox match entry for B
          → sendLike(A_id, true)         → re-confirmation sent to A
```

### Profile A unlikes Profile B

```
A clicks ♥ (already liked)
  → LikeContext.toggleLike(B)
      → delete likesGiven[B]   (localStorage + React state)
      → sendLike(B, false)     (WS → backend → queued for B)
```

```
B receives unlike message
  → InboxContext background handler
      → clearLikeReceived(B_id, A_id)
      → if inbox[A_id].isMatch → delete inbox entry
```

### Match re-confirmation (resilience)

When B receives a **new** like from A and B already had A in `likesGiven`:
- B re-sends `Like(true)` to A.
- A's `InboxContext` processes this as a new incoming like.
- If A has `likesReceived[B]` (just set it moments ago): match detected → match inbox entry for A.
- This prevents match loss if A's `likesReceived` localStorage was cleared between A sending the like and B responding.

---

## UI

### Feed Card — Heart Button

Located in `CardPeerActions` inside `UserProfileCard`. Rendered via the `NavigationBar` component.

| State | Icon appearance |
|-------|----------------|
| Not liked | `HeartIcon` — default foreground colour |
| Liked by me | `HeartIcon` with `fill-rose-500 text-rose-500` classes |

Clicking toggles between like and unlike.

### Inbox — Match Entry

A match entry appears as a conversation in the inbox immediately when mutual like is detected.

| Property | Value |
|----------|-------|
| Avatar | Peer's profile avatar |
| Preview icon | `HeartHandshakeIcon` (rose-400) |
| Preview text | "It's a match! Start chatting" (localised) |
| Unread badge | 1 (new match) |
| Click | Opens `ChatPage` for that peer |

Once the first real message is sent or received, the `isMatch` flag is cleared and the entry becomes a regular conversation.

---

## Block Interaction

When a block event arrives (either side initiates):
1. `clearAllLikesForProfile(myId, peer)` removes both `likesGiven[peer]` and `likesReceived[peer]` from LocalStorage.
2. The inbox entry (match or chat) is deleted.
3. The peer is removed from the feed cache.

The heart icon on the feed card is no longer visible because the profile is removed from the feed immediately after blocking.
