# Shoss App - System Architecture & Data Design

## Application Overview

Shoss is a location-based dating application designed as a Telegram Mini-App for the gay community. The app focuses on profile-based interactions, location-aware features, and real-time communication.

## Core Architecture

### Frontend Stack
- **Platform**: Telegram Mini-App
- **Framework**: React with TypeScript
- **Styling**: Tailwind CSS + shadcn/ui components
- **Build Tool**: Modern bundler (Vite)
- **State Management**: React hooks + Context API
- **Mobile-First**: Responsive design for mobile devices
- **Media Processing**: Client-side crop/zoom/EXIF handling for images, video compression for short videos

### Backend Stack
- **Architecture**: AWS Serverless
- **API**: REST API via AWS API Gateway
- **Compute**: AWS Lambda functions
- **Database**: DynamoDB (single-table design)
- **Storage**: AWS S3 for media files
- **CDN**: CloudFront for media delivery
- **Authentication**: Telegram-based authentication with JWT tokens
- **Framework**: Python 3.11+ with msgspec for data validation
- **Media Processing**: Automatic thumbnail generation and metadata extraction

### External Services
- **Chat & Communication**: AWS API Gateway WebSocket-based chat (custom) for real-time messaging and typing indicators
- **Maps/Location**: Browser GEOHASH + geohash encoding
- **Media Processing**: Frontend handles initial processing, backend generates thumbnails and video previews

### Service Architecture

The backend is organized into several microservices, each deployed as separate Lambda functions:

#### Authentication Service
- **Platform Authentication**: `auth_platform` Lambda - Handles Telegram WebApp authentication
- **JWT Authorization**: `auth_jwt_authorizer` Lambda - Validates JWT tokens for API Gateway
- **User Management**: Creates and manages user records with platform integration

#### User Service
- **Profile Management**: `user_profile_mgmt` Lambda - CRUD operations for user profiles
- **Media Management**: `user_media_mgmt` Lambda - Media upload URL generation and management
- **Media Processing**: `user_media_processing` Lambda - Automated media processing triggered by S3 events
- **Location Management**: `user_location_mgmt` Lambda - Profile location tracking and updates

#### Feed Service
- **Feed Query**: `feed_query` Lambda - Location-based profile discovery and feed generation; returns full profile objects which the frontend splits into the Peers Profile DB (profile data) and the feed's ordered ID list

#### Chat Service
- **WebSocket Management**: `chat_websocket_mgmt` Lambda — handles `$connect`/`$disconnect`
- **WebSocket Messages**: `chat_websocket_msgs` Lambda — `$default` route with actions: `sendMessage`, `typingStatus`, `flashQueue`
- **WebSocket API**: `wss://chat.shoss.io/{environment}` (e.g., `dev`, `prd`)
- **Auth**: JWT via `token` query parameter; authorizer injects `userId` in request context

#### Hosting Service
- **Frontend Deployment**: AWS CloudFront + S3
- **Custom Domain**: `tma.shoss.io`
- **SSL/TLS**: AWS Certificate Manager

## Core Infrastructure

### AWS CloudFormation Stacks

The core service provides foundational AWS infrastructure deployed in order:

1. **S3 Stack** (`01-s3.yaml`) - Creates the Lambda code bucket
2. **DynamoDB Stack** (`02-dynamodb.yaml`) - Creates the main database table and KMS key
3. **IAM Stack** (`03-iam.yaml`) - Creates execution roles (depends on S3 and DynamoDB)
4. **Auth Stack** (`04-auth.yaml`) - Creates API Gateway, Lambda authorizer, and authentication resources
5. **User Service Stack** (`05-apigateway.yaml`) - Creates user service API Gateway resources and methods

#### Stack Details

**S3 Stack**
- **Bucket Name**: `shoss-code-{environment}-{deployment-uuid}`
- **Features**: Versioning, encryption, public access blocking

**DynamoDB Stack**
- **Table Name**: `shoss-{environment}`
- **Features**: Single-table design with 4 GSIs, KMS encryption, point-in-time recovery, pay-per-request billing

**IAM Stack**
- **LambdaExecutionRole**: For Lambda functions with DynamoDB, KMS, S3, and Secrets Manager access
- **ApiGatewayAuthorizerRole**: For API Gateway to invoke Lambda authorizers

**User Service Stack (05-apigateway.yaml)**
- **API Gateway Resources**: Profile and media endpoint resources with path parameters
- **Methods**: CRUD operations for profiles and media with custom authorizer
- **CORS Support**: OPTIONS methods for all endpoints with proper headers
- **Lambda Permissions**: API Gateway permissions to invoke user profile and media Lambda functions
- **CloudWatch Logging**: Dedicated log groups for access and execution logs with 30-day retention
- **Custom Authorizer**: JWT token validation for all protected endpoints

### API Gateway Architecture

The User Service API Gateway provides RESTful endpoints for profile and media management:

#### Profile Endpoints
- `POST /profile` - Create new profile
- `GET /profile/{profileId}` - Get profile with media access URLs
- `PUT /profile/{profileId}` - Update existing profile
- `DELETE /profile/{profileId}` - Delete profile and associated media

#### Media Endpoints
- `POST /profile/{profileId}/media` - Request upload URL for new media
- `GET /profile/{profileId}/media` - List profile media
- `DELETE /profile/{profileId}/media/{mediaId}` - Delete specific media item

#### Location Endpoints
- `PUT /profile/{profileId}/location` - Update profile location
- `DELETE /profile/{profileId}/location` - Clear profile location

#### Feed Endpoints
- `GET /profile/{profileId}/feed` - Get nearby profiles feed

#### Security & Integration
- **Authentication**: Custom JWT authorizer validates tokens for all endpoints except OPTIONS
- **CORS**: Full CORS support with OPTIONS methods for all endpoints
- **Lambda Integration**: AWS_PROXY integration for all methods
- **Monitoring**: CloudWatch access and execution logging with 30-day retention
- **Rate Limiting**: Configurable throttling at API Gateway level

#### CORS Configuration
- **Allowed Origins**: `*` (wildcard for development)
- **Allowed Headers**: `Content-Type,Authorization`
- **Allowed Methods**: Endpoint-specific (GET,POST for creation endpoints; GET,PUT,DELETE for resource endpoints)
- **Credentials**: Enabled for authenticated requests
- **Preflight Support**: OPTIONS methods on all resources

## Data Model & Database Schema

### ID System
- All application IDs are **8-character base64 strings**
- User ID: Generated from hash of Telegram user ID (1:1 mapping)
- Profile ID: Unique per profile (max 3 per user)
- Media ID: Unique per media item (max 5 per profile)

### Entity Relationships
```
User (1) -> Profiles (1-3) -> Media (0-5) [images only]
User (1) -> Profiles (1-3) -> Location History (many)
User (1) -> Agora Chat ID (1)
```

### DynamoDB Schema

#### Single Table Design: `shoss`

**Partition Key (PK) and Sort Key (SK) Structure**
```
PK: EntityType#{ID}
SK: MetadataType#{Timestamp/ID}
```

#### Core Entity Types

**1. User Entity**
```json
{
  "PK": "USER#{userId}",
  "SK": "METADATA",
  "platform": "telegram",
  "platformId": "123456789",
  "platformMetadata": {
    "username": "username",
    "first_name": "John",
    "last_name": "Doe",
    "language_code": "en",
    "is_premium": false,
    "added_to_attachment_menu": false
  },
  "profileIds": ["profileId1", "profileId2"],
  "activeProfileId": "profileId1",
  "type": "basic",
  "moderation": {
    "banFrom": null,
    "banTo": null,
    "banReason": null,
    "banHistory": [],
    "banCount": 0,
    "reportedCount": 0
  },
  "preferences": {},
  "limits": {
    "maxProfilesCount": 3,
    "maxMediasPerProfile": 5,
    "maxMediaFileSize": 10485760,
    "maxMediaAllowedFormats": "jpeg,jpg,png,webp",
  },
  "lastActiveAt": "2024-01-01T12:00:00Z",
  "createdAt": "2024-01-01T00:00:00Z",
  "updatedAt": "2024-01-01T12:00:00Z",
  "loginCount": 1
}
```

**User Type Values:**
- `basic`: Standard user account
- `admin`: Administrative privileges
- `banned`: Account banned (see `moderation` for details and expiry)
- `developer`: Internal/developer account

**2. Profile Entity**
```json
{
  "PK": "PROFILE#{profileId}",
  "SK": "METADATA",
  "userId": "userId",
  "profileName": "Profile Name",
  "nickName": "Display Name",
  "aboutMe": "Profile description or bio text",
  "age": "25",
  "sexualPosition": "top",
  "bodyType": "athletic",
  "eggplantSize": "medium",
  "peachShape": "round",
  "healthPractices": "condoms",
  "hivStatus": "negative",
  "preventionPractices": "prep",
  "hosting": "hostAndTravel",
  "travelDistance": "city",
  "mediaIds": ["media_id_1", "media_id_2"],
  "mediaRecords": {
    "media_id_1": {"status": "ready", "fileSize": 2048576, "dimensions": {"width": 1920, "height": 1080}},
    "media_id_2": {"status": "ready", "fileSize": 1536000, "dimensions": {"width": 1440, "height": 1920}}
  },
  "lastLocation": {
    "latitude": 40.7128,
    "longitude": -74.0060,
    "geohash": "dr5ru",
    "precision": 5
  },
  "lastSeen": 1704110400,
  "createdAt": "2024-01-01T00:00:00Z",
  "updatedAt": "2024-01-01T12:00:00Z",
  "TTL": 1735689600
}
```

**3. User-Profile Lookup (GSI)**
```json
{
  "PK": "USER#{userId}",
  "SK": "PROFILE#{profileId}",
  "profileId": "profileId",
  "isActive": true,
  "createdAt": "2024-01-01T00:00:00Z"
}
```

**4. Location History**
```json
{
  "PK": "PROFILE#{profileId}",
  "SK": "LOCATION#{timestamp}",
  "latitude": 40.7128,
  "longitude": -74.0060,
  "geohash": "dr5ru",
  "precision": 5,
  "timestamp": "2024-01-01T12:00:00Z",
  "TTL": 604800
}
```

**5. Profile Media Record (for media processing pipeline)**
```json
{
  "PK": "PROFILE#{profileId}",
  "SK": "MEDIA#{mediaId}",
  "mimeType": "image/jpeg",
  "fileSize": 2048576,
  "originalUrl": "https://media.shoss.io/media/profileId/0/mediaId.jpg",
  "thumbnailUrl": "https://media.shoss.io/media/profileId/0/mediaId-tb.jpg",
  "status": "ready",
  "properties": {
    "width": 1920,
    "height": 1080,
    "format": "jpeg"
  },
  "dimensions": {
    "width": 1920,
    "height": 1080
  },
  "createdAt": "2024-01-01T00:00:00Z",
  "updatedAt": "2024-01-01T12:00:00Z",
  "processedAt": "2024-01-01T12:05:00Z"
}
```

**Media Status Values:**
- `pending`: Media upload requested, awaiting client upload
- `processing`: Media uploaded and being processed
- `ready`: Media processed successfully and ready for use
- `error`: Media processing failed

### Global Secondary Indexes (GSIs)

**GSI1 - User-based Queries**
- PK: `USER#{userId}`
- SK: `PROFILE#{profileId}` or `LOCATION#{profileId}`
- Use Case: Query all profiles and locations for a specific user

**GSI2 - Location-based Queries**
- PK: `GEOHASH#{geohashPrefix}` or `PROFILE#ALL`
- SK: `{timestamp}#{profileId}` or `PROFILE#{profileId}`
- Use Case: Find nearby profiles, profile discovery queries

**GSI3 - Time-based Queries with Distributed Partitioning**
- PK: `TIME#{YYYYMMDD}`
- SK: `{timestamp}#{entityType}#{entityId}`
- Use Case: Time-based queries for activity, creation times, updates with reduced hot partitions

## Core Features

### 1. Profile Management
- **Multi-Profile Support**: Up to 3 profiles per user
- **Dynamic Profile Allocation**: Profile IDs are generated on-demand
- **Active Profile Tracking**: Tracks the most recently used profile
- **Comprehensive Attributes**: Dating-specific profile fields with enum validation
- **Media Gallery**: Images only (max 5 per profile)
- **Location Integration**: Profile-based location tracking with geohash precision

### 2. Location Services
- Real-time location tracking per profile
- Geohash-based proximity calculations
- Location privacy (precision-controlled)
- Historical location data with TTL

### 3. Communication & Social Features
- **Chat**: AWS API Gateway WebSocket-based chat service with action-based messaging (`sendMessage`, `typingStatus`)
- **Profile Context**: Frontend passes profile IDs in chat messages; display data resolved from Peers Profile DB
- **Lazy Profile Fetching**: When a message arrives from an unknown peer, the frontend calls `GET /profile/{profileId}` and inserts the result into the Peers Profile DB before rendering
- **Local Storage**: Chat history stored on device

### 4. Media Management
- **Upload Flow**: Frontend requests upload URL with base64-encoded metadata -> Backend validates and provides presigned S3 URL -> Client uploads directly to S3 -> S3 events trigger automatic processing
- **Backend Processing**: Media status management, S3 operations, and automatic thumbnail generation
- **Storage**: S3 with organized directory structure (`uploads/`, `original/`, `thumb/`)
- **Security**: Presigned URLs with expiration, content validation, and profile ownership verification
- **Supported Formats**: JPEG, JPG, PNG, WebP images only

## Security & Privacy

### Data Protection
- Profile data isolation
- Location precision control
- Media access validation
- GDPR compliance with TTL

### API Security
- Input validation and sanitization
- Rate limiting
- CORS configuration
- SQL injection prevention (NoSQL)
- User authentication and authorization

### Platform Compliance
- Telegram Mini-App guidelines
- App store requirements (if applicable)
- Regional privacy laws (GDPR, CCPA)
- Content moderation policies
- User safety regulations
- Media content guidelines

### Infrastructure Security
- All resources are tagged with Environment and Service
- DynamoDB uses KMS encryption
- S3 bucket blocks public access
- IAM roles follow least privilege principle
- KMS key policies restrict access appropriately

## Design Principles

### 1. Single Table Design
- All related data stored in one table
- Reduces complexity and improves performance
- Enables efficient joins and queries

### 2. Access Pattern Optimization
- Primary keys designed for most common queries
- GSIs support additional query patterns
- Minimizes data duplication

### 3. Consistent Naming Convention
- **PK Format**: `{ENTITY_TYPE}#{ID}`
- **SK Format**: `{SUBTYPE}` or `{ENTITY_TYPE}#{ID}`
- **GSI Format**: `{QUERY_PATTERN}#{VALUE}`

### 4. Efficient Data Distribution
- Hash keys ensure even distribution across partitions
- Sort keys provide ordering and filtering within partitions
- GSIs enable alternative access patterns

## Frontend Data Models

### Profile System
```typescript
interface MediaRecord {
  mimeType: string;
  fileSize: number;
  originalUrl?: string;
  thumbnailUrl?: string;
  status: 'pending' | 'processing' | 'ready' | 'error' | 'error/invalid-format' | 'error/invalid-size';
  properties: Record<string, any>;
  dimensions: Record<string, any>;
  createdAt: string;
  updatedAt: string;
  processedAt?: string;
}

interface ProfileRecord {
  profileName?: string;
  nickName?: string;
  aboutMe?: string;
  age?: string;
  sexualPosition?: SexualPositionType;
  bodyType?: BodyType;
  sexualityType?: SexualityType;
  eggplantSize?: EggplantSizeType;
  peachShape?: PeachShapeType;
  healthPractices?: HealthPracticesType;
  hivStatus?: HivStatusType;
  preventionPractices?: PreventionPracticesType;
  hosting?: HostingType;
  travelDistance?: TravelDistanceType;
  media: Record<string, MediaAttributes>;
}

interface MediaAttributes {
  status?: 'pending' | 'processing' | 'ready' | 'error' | 'error/invalid-format' | 'error/invalid-size';
  fileSize?: number;
  dimensions?: Record<string, number>;
  flags?: string;
}

interface ProfileDB {
  activeProfile: ProfileRecord;
  profileRecords: Record<ProfileId, ProfileRecord>;
}
```

### Peers Profile DB

The frontend maintains a global, in-memory store of peer profiles available to all components via React Context. This decouples profile data from any single feature so that the feed, chat, and inbox all share one source of truth.

```typescript
// The full peer profile shape returned by GET /profile/{profileId}
interface PeerProfile {
  profileId: string;
  profileName?: string;
  nickName?: string;
  aboutMe?: string;
  age?: string;
  sexualPosition?: SexualPositionType;
  bodyType?: BodyType;
  mediaIds: string[];
  mediaRecords: Record<string, MediaRecord>;
  lastSeen?: number;
}

// Context value exposed by PeersProfileProvider
interface PeersProfileContextValue {
  // Look up a peer profile; undefined means not yet loaded
  getProfile: (profileId: string) => PeerProfile | undefined;
  // Bulk-upsert profiles (called by the nearby/feed API response handler)
  upsertProfiles: (profiles: PeerProfile[]) => void;
  // Fetch a single profile from the backend and insert it into the store;
  // no-op if already present. Used by chat/inbox when a sender is unknown.
  ensureProfile: (profileId: string) => Promise<PeerProfile>;
}
```

**Population rules:**

| Event | Action |
|---|---|
| Nearby (feed) API response | Call `upsertProfiles` with all returned profile objects |
| Incoming chat message from unknown peer | Call `ensureProfile(senderProfileId)` → `GET /profile/{profileId}` |
| Profile already in store | `ensureProfile` is a no-op; no network request |

### Feed

The feed context and page hold **only a list of profile IDs**. All rendering is done by looking up each ID in the Peers Profile DB.

```typescript
interface FeedContextValue {
  // Ordered list of profile IDs to display
  profileIds: string[];
  isLoading: boolean;
  hasMore: boolean;
  // Triggers GET /profile/{activeProfileId}/feed, upserts results into
  // PeersProfileContext, and appends the returned IDs to profileIds
  loadMore: () => Promise<void>;
  refresh: () => Promise<void>;
}
```

**Feed API flow:**
1. Frontend calls `GET /profile/{activeProfileId}/feed` (nearby endpoint).
2. Response contains full profile objects for nearby peers.
3. Frontend calls `upsertProfiles(results)` to populate the Peers Profile DB.
4. Feed context appends only the `profileId` values to its `profileIds` list.
5. Feed page renders each card by calling `getProfile(profileId)` from context.

### Chat System
```typescript
interface Message {
  id: number;
  text: string;
  isMe: boolean;
  timestamp: Date;
}

interface Conversation {
  profileId: string;          // key into PeersProfileDB — no profile data embedded
  lastMessage: string;
  lastTime: number;
  unreadCount: number;
}
```

Chat and inbox components resolve display data (name, avatar) by calling `getProfile(profileId)` from `PeersProfileContext`. When an incoming message arrives for an unknown peer, the WebSocket handler calls `ensureProfile(senderProfileId)` before updating the inbox.

## Core Configuration

### CoreSettings Configuration

The application uses a centralized configuration system defined in `CoreSettings` class:

```python
@dataclass
class CoreSettings:
    # System Configuration
    record_id_length: int = 8  # Length of all generated IDs

    # User Settings
    max_profiles_count: int = 3  # Maximum profiles per user
    max_medias_per_profile: int = 5  # Maximum media items per profile
    user_ttl_days: int = 365  # TTL for user records in days (1 year)
    profile_ttl_days: int = 365  # TTL for profile records in days (1 year)

    # Media Settings
    media_max_file_size: int = 20971520  # 20MB in bytes
    media_allowed_formats: list[str] = ["jpeg", "jpg", "png", "webp"]
    media_upload_expiry_hours: float = 0.25  # 15 minutes
    media_cache_ttl: int = 21600  # 6 hours for browser caching
    media_original_quality: int = 80  # Quality for original processed images (0-100)
    media_thumbnail_quality: int = 75  # Quality for thumbnail images (0-100)
    media_max_original_size: int = 1920  # Maximum width/height for original images
    media_thumbnail_width: int = 320  # Thumbnail width
    media_thumbnail_height: int = 240  # Thumbnail height
    media_ttl_days: int = 365  # TTL for media records in days (1 year)

    # Location Settings
    location_geohash_precision: int = 4
    location_ttl_days: int = 2  # TTL for location records in days
    location_time_window_hours: int = 4  # Time partition window size in hours
    location_max_precision: int = 7  # Maximum geohash precision for fine-grained searches
    location_min_precision: int = 4  # Minimum geohash precision for broad searches

    # Feed Settings
    feed_pagination_ttl_minutes: int = 15  # TTL for feed pagination records in minutes
```

#### Configuration Details

**ID System:**
- All IDs are 8-character base64 strings derived from UUID v5
- User IDs: Generated from platform-specific user identifiers
- Profile IDs: Randomly generated for new profiles
- Media IDs: Randomly generated for media uploads

**Profile Limits:**
- Maximum 3 profiles per user
- Maximum 5 media items per profile
- Media validation enforced at upload time

**Media Processing:**
- Automatic format conversion to optimized JPG
- Progressive JPEG encoding for better web performance
- Configurable quality settings for size optimization
- Thumbnail generation with aspect ratio preservation
- S3 event-driven processing pipeline

**Security & Performance:**
- Presigned URLs expire in 15 minutes
- CloudFront signed URLs for media access with 6-hour TTL
- Automatic cleanup of incomplete uploads
- TTL-based data expiration for GDPR compliance

## Deployment

### Prerequisites
- AWS CLI installed and configured
- Appropriate AWS credentials/permissions
- Python 3.11+ with boto3

### Deployment Process
```bash
# Deploy to dev environment (default)
python deploy.py

# Deploy to specific environment
python deploy.py --environment prd

# Deploy with specific parameters
python deploy.py --region us-east-1 --profile shoss
```

### Stack Outputs
After successful deployment:
- **LambdaCodeBucketName**: S3 bucket for Lambda code
- **DynamoDBTableName**: Main database table name
- **DynamoDBKMSKeyArn**: KMS key ARN for encryption
- **LambdaExecutionRoleArn**: Lambda execution role ARN
- **ApiGatewayAuthorizerRoleArn**: API Gateway authorizer role ARN

---

*This document provides a comprehensive overview of the Shoss application's system architecture and data design. For specific implementation details, refer to the service-specific documentation.*