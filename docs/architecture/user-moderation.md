# User Moderation — Architecture & Design Specification

This document covers the end-to-end moderation system for the Vibe Dating app: ban enforcement, user reporting, automatic profile restrictions, block relationships, and the frontend flows for denied login and in-app reporting.

**Related:** [System architecture](./system-architecture.md), [Chat architecture](./chat-architecture.md), [Moderation dashboard](./moderation-dashboard.md)

---

## Confirmed Design Decisions


| #                             | Decision                                                                                                                                                                                                                                                                                                                       |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Report deduplication**      | Once per `(reporterUserId, subjectUserId)` pair per 7-day window; a second report from the same reporter within that window is silently dropped                                                                                                                                                                                |
| **Appeals**                   | No in-app appeal mechanism; banned user sees a Telegram support handle only                                                                                                                                                                                                                                                    |
| **Ban message**               | Generic only — "account suspended for violating community guidelines"; `banReason` is never exposed to the client                                                                                                                                                                                                              |
| **Chat during feed-hidden**   | Feed visibility only is affected; existing chat conversations continue uninterrupted                                                                                                                                                                                                                                           |
| **Auto-ban timing**           | Immediate — ban fires the moment the threshold is crossed; moderators can reverse via dashboard                                                                                                                                                                                                                                |
| **Block → restriction score** | No relationship; blocking is a personal feed filter only and carries zero weight toward moderation thresholds                                                                                                                                                                                                                  |
| **Reporter rate limit**       | 20 reports per user per day; excess silently discarded with no error shown to reporter                                                                                                                                                                                                                                         |
| **Ban scope**                 | All moderation actions (`feed_hidden`, `chat_limited`, ban) are applied at `userId` level — all profiles belonging to that user are affected simultaneously. Reporting in the app is done via `profileId` (the only identity visible to users); the backend resolves `profileId → userId` before applying any moderation logic |
| **Auto-ban lift**             | Temporary bans auto-restore at `banTo` expiry per existing `UserManager.is_banned()` logic; moderators can lift early via dashboard                                                                                                                                                                                            |
| **Block direction**           | Bi-directional — when P1 blocks Q1, both sides are hidden from each other                                                                                                                                                                                                                                                      |
| **Block scope**               | Strictly profile-to-profile; only the exact P1↔Q1 pair is affected                                                                                                                                                                                                                                                             |
| **Chat on block**             | Hard delete — the shared chat thread and all messages are permanently deleted from both sides on block                                                                                                                                                                                                                         |
| **Logout WebSocket**     | Backend-only message type (`logout`); cannot be sent by clients. When received, frontend clears the JWT and navigates to SplashPage. Intended for kicking online users immediately when a ban is applied                                                                                                                  |


---

## 1. System Overview

```
┌──────────────────────────────────────────────────────┐
│                    App Users                          │
│  Report profile/post/chat  │  Block  │  Login attempt │
└────────────┬───────────────┴────┬────┴───────┬────────┘
             │                   │            │
  POST /report              POST /block   POST /auth/platform
             │                   │            │
             ▼                   ▼            ▼
   ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐
   │ user_report_mgmt │  │ user_profile_mgmt │  │  auth_platform       │
   │     Lambda       │  │     Lambda        │  │  (ban check on login)│
   └────────┬─────────┘  └──────────────────┘  └──────────────────────┘
            │ DynamoDB write (REPORT#)
            │ Streams trigger
            ▼
   ┌────────────────────┐
   │ moderation_auto_   │  ← evaluates weighted restriction rules
   │ engine Lambda      │    writes restriction, may set UserType.banned
   └────────────────────┘
            │
            ▼
   ┌────────────────────┐
   │  vibe-dating-{env} │  ← USER#, PROFILE#, REPORT#, BLOCK#
   └────────────────────┘
            ▲
   ┌────────┴────────────┐
   │ admin_api Lambda    │  ← Moderation dashboard: review, ban/unban, resolve reports
   └─────────────────────┘
```

**Identity resolution principle:** Users only ever see `profileId`. All backend moderation logic operates on `userId`. When a report or block arrives with a `profileId`, the backend resolves it to `userId` via `ProfileRecord.userId` before writing any moderation state.

---

## 2. Data Model Extensions

All new entities live in the existing `vibe-dating-{env}` single-table unless noted.

### 2.1 Extensions to existing types

#### `UserModeration` (`backend/src/common/aws_lambdas/core_types/user.py`)

Add restriction tracking alongside existing ban fields:

```python
class RestrictionType(str, Enum):
    FEED_HIDDEN  = "feed_hidden"   # hidden from nearby feed; chats unaffected
    CHAT_LIMITED = "chat_limited"  # can reply to existing chats but not initiate new ones

class UserRestriction(msgspec.Struct):
    type: RestrictionType
    reason: Optional[str] = None
    appliedAt: Optional[str] = None     # ISO timestamp
    expiresAt: Optional[str] = None     # ISO timestamp; None = until lifted
    appliedBySystem: bool = True        # True = auto-engine; False = moderator
    linkedReportIds: List[str] = msgspec.field(default_factory=list)

class UserModeration(msgspec.Struct):
    # --- existing fields (unchanged) ---
    banFrom: Optional[str] = None
    banTo: Optional[str] = None
    banReason: Optional[str] = None
    banHistory: Optional[List[Dict[str, Any]]] = None
    banCount: int = 0
    reportedCount: int = 0
    # --- new fields ---
    restriction: Optional[UserRestriction] = None          # current non-ban restriction
    restrictionHistory: List[Dict[str, Any]] = msgspec.field(default_factory=list)
    openReportCount: int = 0   # count of unresolved reports; decremented on resolution
```

**Invariant:** `restriction` holds the current non-ban restriction only. When a full ban is applied, `restriction` is cleared and `UserType` becomes `banned`. History accumulates in `restrictionHistory`.

#### `MediaAttributes` (`backend/src/common/aws_lambdas/core_types/profile.py`)

Add moderation overlay without altering pipeline `MediaStatus`:

```python
class MediaModerationStatus(str, Enum):
    APPROVED       = "approved"
    REJECTED       = "rejected"
    PENDING_REVIEW = "pending_review"

class MediaAttributes(msgspec.Struct):
    # --- existing fields (unchanged) ---
    mimeType: Optional[str] = None
    status: MediaStatus = MediaStatus.PENDING
    privacy: Optional[str] = None
    association: Optional[str] = None
    dimensions: Optional[Dict[str, int]] = None
    flags: Optional[str] = None
    # --- new fields ---
    moderationStatus: Optional[MediaModerationStatus] = None
    moderationReason: Optional[str] = None
    moderatedAt: Optional[str] = None
    moderatedByStaffId: Optional[str] = None  # Cognito sub of moderator
```

`feed_query` and chat surfaces must exclude media where `moderationStatus == "rejected"`.

---

### 2.2 Report entity (new)

**DynamoDB keys:**

```
PK  = PROFILE#{subjectProfileId}     # the profile being reported
SK  = REPORT#{reporterProfileId}     # the reporter's active profile
```

The composite key enforces natural deduplication: one record per (reporter, subject) pair. A re-report from the same reporter simply overwrites the existing record with an updated `updatedAt` timestamp.

**GSIs used:**

```
GSI1PK = REPORT#{reporterProfileId}   # find all reports filed by a reporter
GSI1SK = PROFILE#{subjectProfileId}

GSI2PK = REPORT#ALL                   # global report queue (moderator dashboard)
GSI2SK = REPORT#{reporterProfileId}

GSI3PK = REPORT#{reporterProfileId}   # per-reporter time index (rate-limit queries)
GSI3SK = {epochSeconds}               # enables key-condition range queries over time
```

**Python type (`backend/src/common/aws_lambdas/core_types/report.py`):**

```python
class ReportSubjectType(str, Enum):
    PROFILE = "profile"
    POST    = "post"
    MEDIA   = "media"
    CHAT    = "chat"       # reports the full conversation with the target profile

class ReportCategory(str, Enum):
    HARASSMENT            = "harassment"
    SPAM                  = "spam"
    UNDERAGE              = "underage"
    INAPPROPRIATE_CONTENT = "inappropriate_content"
    IMPERSONATION         = "impersonation"
    FAKE_PROFILE          = "fake_profile"
    SOLICITATION          = "solicitation"   # requesting money for sexual services
    CHILD_SAFETY          = "child_safety"   # content violating child safety / CSAM
    OTHER                 = "other"

class ReportStatus(str, Enum):
    OPEN                  = "open"
    IN_REVIEW             = "in_review"
    RESOLVED_DISMISSED    = "resolved_dismissed"
    RESOLVED_ACTION_TAKEN = "resolved_action_taken"
    RESOLVED_AUTO         = "resolved_auto"   # closed by auto-engine without manual review

class ReportRecord(msgspec.Struct):
    status:   ReportStatus   = ReportStatus.OPEN
    category: ReportCategory = ReportCategory.OTHER
    context:  Optional[str]  = None    # max 500 chars
    weight:   int            = 1       # resolved from CoreSettings.report_category_weights
                                       # at write time; immutable after creation
    ttl:      Optional[int]  = None    # DynamoDB TTL epoch; set by auto-engine
```

Reporter identity (`reporterProfileId`, `reporterUserId`) and subject identity (`subjectProfileId`, `subjectUserId`) are encoded in the item's PK/SK and GSI keys — they are **not** duplicated inside the record payload. The backend resolves `subjectProfileId → subjectUserId` at write time for moderation logic; the resolved userId is not stored in the report item.

**Counter update on new report (on `subjectUserId` USER record):**

- Increment `moderation.reportedCount` (lifetime total)
- Increment `moderation.openReportCount` (decremented when report is resolved)

---

### 2.3 Block entity (new)

Blocking is **profile-to-profile and bi-directional**: when Profile P1 blocks Profile Q1, both sides are immediately hidden from each other. The block affects only the exact P1↔Q1 pair; all other profile combinations are unaffected.

Blocking carries no weight toward moderation thresholds.

**Storage: two mirrored records written as separate `PutItem` calls.**

```
# Record 1 — written from P1's perspective
PK = PROFILE#{P1}
SK = BLOCK#{Q1}

# Record 2 — mirror
PK = PROFILE#{Q1}
SK = BLOCK#{P1}
```

Both records carry the same `BlockRecord` payload:

```python
class BlockRecord(msgspec.Struct):
    createdByProfileId: str   # who triggered the block (P1)
    blockedProfileId:   str   # the blocked profile (Q1)
```

`createdByProfileId` lets the UI distinguish "You blocked this profile" vs "This profile is unavailable", and is checked by `BlockManager.delete()` to prevent the non-initiating side from lifting the block.

Additional metadata (`createdAt`) is written alongside the record but is not part of `BlockRecord`.

**GSIs used:**

```
GSI1PK = BLOCK#{otherProfileId}   # reverse lookup
GSI1SK = PROFILE#{myProfileId}

GSI2PK = BLOCK#ALL                # global block list (admin)
GSI2SK = BLOCK#{otherProfileId}

GSI3PK = TIME#{YYYYMMDDHH}#{myProfileId[:2]}
GSI3SK = {epochSeconds}#{myProfileId}
```

**Why two records:**

- Feed check for Profile P: single point-read `PROFILE#{P}/BLOCK#{Q}` — no GSI needed
- Chat send check: same single point-read
- P's blocked list: prefix scan on `PROFILE#{P}/BLOCK#`*
- No reverse lookup GSI needed — the mirror record covers it

**On block: hard delete of shared chat history.**

As part of the same block operation (after the DynamoDB transaction commits):

1. Look up the chat thread between P1 and Q1 in `vibe-dating-chat`
2. Batch-delete all message items in the thread
3. Delete the thread metadata record

This is permanent and non-recoverable. Both parties lose the full chat history simultaneously. If the block is later lifted, they start with an empty history.

---

### 2.4 Auto-restriction state (embedded)

No separate entity. The current active restriction lives in `user.moderation.restriction` (see §2.1). The auto-engine writes this field and archives the prior value to `restrictionHistory` on each change.

---

## 3. Ban & Restriction System

### 3.1 Restriction levels and effects

All levels are `**userId`-scoped** — they affect the user's entire account and all their profiles simultaneously. There are no profile-level bans or restrictions.


| Level          | DynamoDB state                             | All profiles on feed | Initiate chat | Reply in chat | Login |
| -------------- | ------------------------------------------ | -------------------- | ------------- | ------------- | ----- |
| None           | `type=basic`, no restriction               | ✓                    | ✓             | ✓             | ✓     |
| `feed_hidden`  | `moderation.restriction.type=feed_hidden`  | Hidden               | ✓             | ✓             | ✓     |
| `chat_limited` | `moderation.restriction.type=chat_limited` | Hidden               | Blocked       | ✓             | ✓     |
| Banned (temp)  | `type=banned`, `banTo` set                 | Blocked              | Blocked       | Blocked       | 403   |
| Banned (perm)  | `type=banned`, no `banTo`                  | Blocked              | Blocked       | Blocked       | 403   |


`feed_query` filters by the **owner's** restriction state:

- Resolve each candidate profile's `userId`
- Skip all profiles whose `userId` has `moderation.restriction` set
- Skip all profiles whose `userId` has `type == banned`

`chat_websocket_msgs` enforces `chat_limited`:

- On `sendMessage`, check the sender's restriction; if `chat_limited` and this is a new thread (no prior messages from sender), return `USER_CHAT_LIMITED`

### 3.2 Applying a ban (manual or auto)

Bans are always at `userId` level — never at `profileId`. All profiles belonging to the user are affected simultaneously.

```python
def apply_ban(user_id, reason, ban_to=None, applied_by_staff_id=None, is_system=False):
    # 1. Read current UserRecord
    # 2. Archive current restriction to restrictionHistory
    # 3. Set:
    #      user.type = UserType.BANNED
    #      user.moderation.banFrom = now_iso
    #      user.moderation.banTo = ban_to        (None = permanent)
    #      user.moderation.banReason = reason
    #      user.moderation.restriction = None    (restriction superseded by ban)
    #      user.moderation.banCount += 1
    #      append to banHistory: {banFrom, banTo, reason, appliedBy, appliedAt, isSystem}
    # 4. Write back to DynamoDB
    # 5. Write audit record
```

### 3.3 Unban

```python
def unban(user_id, restore_type=UserType.BASIC, unban_note=None, staff_id=None):
    # 1. Set user.type = restore_type
    # 2. Clear banFrom, banTo, banReason (preserve banHistory)
    # 3. Write audit record
```

Temporary bans also auto-lift at `banTo` expiry per existing `UserManager.is_banned()` logic — no cron job required.

### 3.4 Ban enforcement at login

In `auth_platform` Lambda, after Telegram auth succeeds, **before** issuing JWT:

```python
user = UserManager.get_by_platform(platform, platform_id)
if user and UserManager.is_banned(user):
    return generate_response(403, {
        "error": "USER_BANNED",
        "banTo": user.moderation.banTo,       # None if permanent
        "permanent": user.moderation.banTo is None,
    })
```

The JWT is **never issued** for a banned user. Existing JWTs expire by natural TTL. **Recommended MVP approach:** short JWT TTL (≤15 min) — no ban-list needed, minimal latency overhead.

### 3.5 Kicking online users via Logout

When a ban is applied to a user who currently has an active WebSocket connection, the backend can push a `logout` message to disconnect them immediately without waiting for JWT expiry:

```python
# After apply_ban() — send Logout to all active connections of this userId
logout_msg = {"messageType": MessageType.LOGOUT.value}
for connection_id in ChatManager.get_connections_for_user(subject_user_id):
    apigw_mgmt.post_to_connection(ConnectionId=connection_id, Data=json.dumps(logout_msg))
```

This message type is **server-initiated only** — it is not a valid `action` value in client-to-server messages and must not be routed by the `chat_websocket_msgs` handler. See §8.6 for the frontend behaviour.

---

## 4. Reporting System

### 4.1 Report submission flow

The frontend sends both the reporter's `profileId` and the subject's `profileId`. The backend resolves the subject to `userId` before any moderation logic runs.

```
Frontend                    user_report_mgmt Lambda              DynamoDB
   │                                  │                              │
   │  POST /profile/{reporterProfileId}/report/{subjectProfileId}    │
   │  { category, context? }          │                              │
   │─────────────────────────────────►│                              │
   │                                  │  1. resolve subjectProfileId │
   │                                  │     → subjectUserId          │
   │                                  │     GET PROFILE#{profileId}  │
   │                                  │─────────────────────────────►│
   │                                  │◄─────────────────────────────│
   │                                  │  if unknown or self → discard│
   │                                  │                              │
   │                                  │  2. resolve weight from      │
   │                                  │     CoreSettings             │
   │                                  │                              │
   │                                  │  3. PUT PROFILE#{subjectProfileId}
   │                                  │        / REPORT#{reporterProfileId}
   │                                  │     (overwrites prior report │
   │                                  │      from same reporter)     │
   │                                  │─────────────────────────────►│
   │  200 OK (always)                 │                              │
   │◄─────────────────────────────────│                              │
```

Always returns 200 regardless of outcome — avoids leaking information to bad actors.

**Deduplication** is enforced by the key structure: one `PutItem` per (reporterProfileId, subjectProfileId) pair. A repeat report from the same reporter overwrites the existing record with a fresh `updatedAt`. There is no separate quota counter.

### 4.2 What can be reported


| Subject           | Entry point                                     | `subjectType` |
| ----------------- | ----------------------------------------------- | ------------- |
| Profile           | Dedicated report button on feed profile card    | `profile`     |
| Profile           | Overflow menu on profile detail page → "Report" | `profile`     |
| Feed post         | Overflow on post card → "Report post"           | `post`        |
| Profile media     | Overflow → "Report"                             | `media`       |
| Chat conversation | `more...` menu in chat → "Report"               | `chat`        |


All reports use the same endpoint: `POST /profile/{reporterProfileId}/report/{subjectProfileId}`

Chat reports target the other party's profile — not a single message. Moderators can pull the full thread from the chat table using the two profile IDs.

### 4.3 Categories and weights

Each category has a **weight** stored in `CoreSettings`. The weight is resolved and written into `ReportRecord.weight` at creation time — it is immutable after that, so future weight changes do not retroactively affect existing reports.

The auto-restriction engine sums weights from unique reporters (not raw report count).


| Category                      | Value                   | Weight | Description                                             |
| ----------------------------- | ----------------------- | ------ | ------------------------------------------------------- |
| Harassment or threats         | `harassment`            | 1      | Threatening, abusive, or intimidating behaviour         |
| Spam or fake account          | `spam`                  | 1      | Unsolicited commercial content or clearly fake identity |
| Inappropriate content         | `inappropriate_content` | 1      | Explicit or offensive material outside community norms  |
| Underage user                 | `underage`              | 1      | User appears to be under the minimum age                |
| Impersonation                 | `impersonation`         | 1      | Pretending to be a specific real person                 |
| Fake profile                  | `fake_profile`          | 1      | Fabricated identity not impersonating a specific person |
| Asking money for sex services | `solicitation`          | 1      | Requesting payment for sexual services                  |
| Child safety concern          | `child_safety`          | 1      | Content violating child safety — CSAM or grooming       |
| Other                         | `other`                 | 1      | Does not fit any of the above                           |


```python
# CoreSettings additions
report_category_weights: Dict[str, int] = {
    "harassment":             1,
    "spam":                   1,
    "inappropriate_content":  1,
    "underage":               1,
    "impersonation":          1,
    "fake_profile":           1,
    "solicitation":           1,
    "child_safety":           1,
    "other":                  1,
}
```

---

## 5. Automatic Restriction Engine

### 5.1 Lambda: `moderation_auto_engine`

Triggered by **DynamoDB Streams** on `vibe-dating-{env}` for new report items.

Report items have `SK` beginning with `REPORT#`, so the stream filter targets those:

```yaml
# CloudFormation event source mapping filter
FilterCriteria:
  Filters:
    - Pattern: '{"dynamodb":{"NewImage":{"SK":{"S":[{"prefix":"REPORT#"}]},"status":{"S":["open"]}}}}'
```

### 5.2 Evaluation algorithm

Thresholds compare against the **weighted sum** of reports from unique reporters in the rolling 7-day window — not a raw reporter count. Because deduplication is enforced by the PK/SK structure (one record per reporter–subject pair), each reporter contributes its `weight` exactly once regardless of how many times they re-report.

```python
def evaluate_restrictions(subject_user_id: str):
    # 1. Sum weights from unique reporters in past 7 days (open + in_review)
    recent_weight_sum = sum_report_weights_7d(subject_user_id)

    # 2. Sum weights across all lifetime reports (any status)
    lifetime_weight_sum = sum_report_weights_lifetime(subject_user_id)

    # 3. No-op if already banned
    user = UserManager.get(subject_user_id)
    if user.type == UserType.BANNED:
        return

    # 4. Escalating restrictions
    if recent_weight_sum >= settings.moderation_auto_temp_ban_threshold:
        apply_temp_ban(
            subject_user_id,
            reason="Multiple reports from users",
            ban_to=now + timedelta(hours=settings.moderation_auto_temp_ban_hours),
            is_system=True,
        )
    elif recent_weight_sum >= settings.moderation_auto_chat_limited_threshold:
        apply_restriction(subject_user_id, RestrictionType.CHAT_LIMITED, is_system=True)
        escalate_to_mod_queue(subject_user_id)
    elif recent_weight_sum >= settings.moderation_auto_feed_hidden_threshold:
        apply_restriction(subject_user_id, RestrictionType.FEED_HIDDEN, is_system=True)

    # 5. Lifetime flag — escalate for manual review, do not auto-ban
    if lifetime_weight_sum >= settings.moderation_lifetime_escalation_threshold:
        escalate_to_mod_queue(subject_user_id, priority="high")
```

**Examples with current weights (all = 1):**


| Unique reporters (7d) | Weight sum | Action                                 |
| --------------------- | ---------- | -------------------------------------- |
| 3                     | 3          | `feed_hidden`                          |
| 5                     | 5          | `chat_limited` + escalate to mod queue |
| 10                    | 10         | 72h temp ban                           |


**Example after future weight increase (`child_safety = 5`):**

- 2 `child_safety` reports → weight sum = 10 → immediate temp ban

### 5.3 Thresholds (configurable via `CoreSettings`)

```python
moderation_auto_feed_hidden_threshold: int = 3
moderation_auto_chat_limited_threshold: int = 5
moderation_auto_temp_ban_threshold: int = 10
moderation_auto_temp_ban_hours: int = 72
moderation_lifetime_escalation_threshold: int = 15
```

### 5.4 Escalation record

When the engine escalates to the mod queue it writes:

```
PK     = REPORT#ESCALATION#{escalationId}
SK     = METADATA
GSI4PK = REPORT#STATUS#open
GSI4SK = PRIORITY#high#{createdAt}#{escalationId}
```

Fields: `subjectUserId`, `triggerType` (`auto_restriction` | `lifetime_threshold`), `recentWeightSum`, `lifetimeWeightSum`, `appliedRestriction`.

---

## 6. Block System

### 6.1 Block relationship

Blocking is **profile-to-profile and bi-directional**. When P1 blocks Q1:

- P1 is hidden from Q1's feed; Q1 is hidden from P1's feed
- Neither can send messages to the other
- Only the exact P1↔Q1 pair is affected; all other profile combinations remain independent

### 6.2 Feed filtering

`feed_query` does a single point-read per candidate: `PROFILE#{viewer}/BLOCK#{candidate}`. Because two mirrored records are written on block, this single read covers both directions with no GSI.

### 6.3 Chat enforcement

On `sendMessage`, `chat_websocket_msgs` checks `PROFILE#{sender}/BLOCK#{recipient}`. If the item exists (regardless of who initiated the block), return `USER_BLOCKED` and discard the message.

### 6.4 Chat deletion on block

As part of the block operation, after the DynamoDB transaction commits:

1. Write `PROFILE#{P1}/BLOCK#{Q1}` and `PROFILE#{Q1}/BLOCK#{P1}` atomically
2. Look up the chat thread between P1 and Q1 in `vibe-dating-chat`
3. Batch-delete all message items
4. Delete the thread metadata record

Hard delete — permanent and non-recoverable. If the block is later lifted, both parties start with an empty chat history.

---

## 7. Backend API (App-Facing)

New `user_report_mgmt` Lambda. JWT-authenticated via existing `auth_jwt_authorizer`.

### 7.1 Report endpoint

`reporterProfileId` must belong to the authenticated `userId` (standard ownership check).

```
POST /profile/{reporterProfileId}/report/{subjectProfileId}
Body: {
  category: ReportCategory,        // required
  subjectType?: ReportSubjectType, // default: "profile"
  mediaId?: string,                // only when subjectType = "media"
  context?: string                 // optional, max 500 chars
}
Response: 200 (always)
```

### 7.2 Block endpoints

`myProfileId` must belong to the authenticated `userId` (standard ownership check).

```
POST   /profile/{myProfileId}/block/{targetProfileId}
       Response: 200 | 409 (already blocked)

DELETE /profile/{myProfileId}/block/{targetProfileId}
       Response: 200 | 404

GET    /profile/{myProfileId}/blocks
       Response: { blockedProfileIds: string[], cursor? }
```

### 7.3 Auth endpoint — ban response

`POST /auth/platform` returns HTTP 403 when user is banned:

```typescript
{
  error: "USER_BANNED",
  permanent: boolean,
  banTo?: string    // ISO timestamp; only present when permanent = false
}
```

No `banReason` is exposed to the client.

### 7.4 Restriction effects on existing endpoints


| Endpoint                        | `feed_hidden`                 | `chat_limited`                |
| ------------------------------- | ----------------------------- | ----------------------------- |
| `GET /profile/{id}/feed`        | All owner's profiles excluded | All owner's profiles excluded |
| `sendMessage` (new thread)      | ✓ allowed                     | 403 `USER_CHAT_LIMITED`       |
| `sendMessage` (existing thread) | ✓ allowed                     | ✓ allowed                     |
| `sendMessage` (blocked pair)    | 403 `USER_BLOCKED`            | 403 `USER_BLOCKED`            |
| All other endpoints             | No change                     | No change                     |


---

## 8. Frontend Interfaces

### 8.1 Denied login screen

Shown when `POST /auth/platform` returns HTTP 403. Replaces the splash screen — no navigation available.

```
┌─────────────────────────────────────┐
│                                     │
│         Account Suspended           │
│                                     │
│  Your account has been suspended    │
│  for violating our community        │
│  guidelines.                        │
│                                     │
│  [If temporary]:                    │
│  Access will be restored on         │
│  {banTo in local date format}.      │
│                                     │
│  [If permanent]:                    │
│  This suspension is permanent.      │
│                                     │
│  ─────────────────────────────────  │
│  If you believe this is a mistake,  │
│  contact support: @VibeSupport      │
│                                     │
└─────────────────────────────────────┘
```

- `banTo` displayed via `Intl.DateTimeFormat` in user's locale
- Support handle configured via `VITE_SUPPORT_TELEGRAM_HANDLE`
- On app resume, re-attempts auth — if ban has expired, proceeds normally

### 8.2 Report UI

**Entry points:**


| Where               | Trigger                   |
| ------------------- | ------------------------- |
| Feed profile card   | Dedicated report button   |
| Profile detail page | Overflow menu → "Report"  |
| Feed post card      | Overflow → "Report post"  |
| Chat screen         | `more...` menu → "Report" |


**Report sheet (bottom drawer):**

```
┌──────────────────────────────────┐
│  Report [Profile / Post / Chat]  │
│  ─────────────────────────────── │
│  Why are you reporting this?     │
│                                  │
│  ○ Harassment or threats         │
│  ○ Spam or fake account          │
│  ○ Inappropriate content         │
│  ○ Underage user                 │
│  ○ Impersonation                 │
│  ○ Fake profile                  │
│  ○ Asking money for sex services │
│  ○ Child safety concern          │
│  ○ Other                         │
│                                  │
│  Additional context (optional)   │
│  ┌──────────────────────────┐    │
│  │ Tell us more...          │    │
│  └──────────────────────────┘    │
│                                  │
│  [Cancel]        [Submit Report] │
└──────────────────────────────────┘
```

Category is **required**. Context is optional (max 500 chars). Sheet title adapts: "Report Profile", "Report Post", "Report Chat".

After submit: toast — "Report submitted. Thank you for keeping Vibe safe."

**TypeScript types:**

```typescript
type ReportCategory =
  | 'harassment'
  | 'spam'
  | 'inappropriate_content'
  | 'underage'
  | 'impersonation'
  | 'fake_profile'
  | 'solicitation'
  | 'child_safety'
  | 'other';

type ReportSubjectType = 'profile' | 'post' | 'media' | 'chat';

interface SubmitReportParams {
  myProfileId: string;
  subjectProfileId: string;
  subjectType: ReportSubjectType;
  category: ReportCategory;
  context?: string;
  mediaId?: string;   // only when subjectType = 'media'
}

// API call — same endpoint for all report types
await api.post(`/profile/${myProfileId}/report/${subjectProfileId}`, {
  category,
  subjectType,
  ...(mediaId && { mediaId }),
  ...(context && { context }),
});
```

### 8.3 Block UI

**Entry:** Profile detail overflow → "Block [nickname]"

**Confirmation dialog:**

```
Block [Nickname]?

You will no longer see each other on the
feed or be able to message each other.
Your chat history will be permanently deleted.
Your other profiles are not affected.

[Cancel]  [Block]
```

**After block:**

- Target profile removed from feed immediately (local state update)
- Shared chat thread removed from inbox on both sides
- Blocked profiles list: Settings → Privacy → Blocked Profiles (scoped to active profile)

**Blocked profiles list (`/profile/{myProfileId}/blocks`):**

```
Blocked Profiles  [active profile name]

[avatar]  [Nickname]    [Unblock]
[avatar]  [Nickname]    [Unblock]
```

### 8.4 Chat-limited restriction

When `sendMessage` returns `USER_CHAT_LIMITED`, show inline in the chat input area:

```
Your account is currently restricted.
You can reply to existing conversations but cannot start new ones.
```

### 8.5 Feed-hidden restriction

Users under `feed_hidden` are not notified — their profiles simply stop appearing in others' feeds. This is intentional.

### 8.6 Logout WebSocket message

`messageType: "logout"` is a server-initiated message that carries no payload fields. When `WebSocketContext` receives it, it:

1. Calls `logout()` (clears the JWT from localStorage and wipes auth state)
2. Navigates to SplashPage (`window.location.hash = '/'`)

The message is intercepted before being forwarded to background or foreground chat handlers — no chat handler sees it.

**Security note:** the `logout` message type must never be accepted as a valid `action` in the client→server direction. The `chat_websocket_msgs` dispatcher rejects any unrecognised action with a 400 error, so a client attempting to spoof this message toward another user's connection simply gets an error back — it has no effect on other connections.

```typescript
// WebSocketContext.tsx — message listener (simplified)
client.addMessageListener((message) => {
  if (message.messageType === 'logout') {
    void logout().finally(() => { window.location.hash = '/'; });
    return;  // not forwarded to inbox or chat page handlers
  }
  backgroundHandlerRef.current?.(message);
  messageHandlerRef.current?.(message);
});
```

---

## 9. CloudFormation Changes

### 9.1 `02-dynamodb.yaml` — Add GSI4

```yaml
GlobalSecondaryIndexes:
  # ... existing GSI1, GSI2, GSI3 ...
  - IndexName: GSI4
    KeySchema:
      - AttributeName: GSI4PK
        KeyType: HASH
      - AttributeName: GSI4SK
        KeyType: RANGE
    Projection:
      ProjectionType: ALL
AttributeDefinitions:
  # append:
  - AttributeName: GSI4PK
    AttributeType: S
  - AttributeName: GSI4SK
    AttributeType: S
```

### 9.2 New Lambda stacks


| Stack                       | Lambda                   | Purpose                                            |
| --------------------------- | ------------------------ | -------------------------------------------------- |
| `06-reports.yaml`           | `user_report_mgmt`       | Report submission, block CRUD, rate limiting       |
| `07-moderation-engine.yaml` | `moderation_auto_engine` | DynamoDB Streams → weighted restriction evaluation |


`moderation_auto_engine` IAM needs: `dynamodb:GetRecords`, `GetShardIterator`, `DescribeStream`, `ListStreams` on the table stream ARN.

---

## 10. Phased Delivery


| Phase  | Scope                                                                                                                                                                                      |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **P0** | `UserModeration` type extensions; ban check in `auth_platform`; denied login screen                                                                                                        |
| **P1** | `user_report_mgmt` Lambda; report submission API + rate limiting; GSI4 CloudFormation; frontend report UI                                                                                  |
| **P2** | Block system — DynamoDB storage, `POST/DELETE/GET` endpoints, feed filter, chat enforcement, chat hard-delete on block; frontend block UI                                                  |
| **P3** | `moderation_auto_engine` — Streams trigger, weighted threshold evaluation, restriction writes, escalation records; `chat_limited` enforcement in chat Lambda; feed filter for restrictions |
| **P4** | Media moderation overlay (`MediaAttributes` extension); `feed_query` media filtering; moderator dashboard integration (see moderation-dashboard.md)                                        |


---

## 11. Implementation Pointers


| Concern                              | Location                                                                         |
| ------------------------------------ | -------------------------------------------------------------------------------- |
| Ban state read/write                 | `backend/src/common/aws_lambdas/core/user_utils.py` (`UserManager`)              |
| Ban check at login                   | `backend/src/services/auth/` — `auth_platform` Lambda                            |
| New core types                       | `backend/src/common/aws_lambdas/core_types/report.py` (new file)                 |
| `UserModeration` extension           | `backend/src/common/aws_lambdas/core_types/user.py`                              |
| `MediaAttributes` extension          | `backend/src/common/aws_lambdas/core_types/profile.py`                           |
| Feed filtering                       | `backend/src/services/feed/` — `feed_query` Lambda                               |
| Chat restriction + block enforcement | `backend/src/services/chat/` — `chat_websocket_msgs` Lambda                      |
| Report + block Lambda                | `backend/src/services/user/` — `user_report_mgmt` (new)                          |
| Auto-engine Lambda                   | `backend/src/services/admin/` — `moderation_auto_engine` (new)                   |
| Frontend report sheet                | New `ReportSheet` component; entry in `ProfileCard`, `ProfileDetail`, `ChatPage` |
| Frontend denied login                | New `BannedScreen` replacing splash on 403 from auth                             |
| Frontend block list                  | New page at `/profile/{id}/blocks` in Settings                                   |
| Backend conventions                  | `.cursor/rules/backend-coding-rules.mdc`, `backend-cloudformation.mdc`           |


