# API Reference - Shoss Backend

## Overview

The Shoss Backend API is a RESTful API deployed on AWS Lambda via API Gateway. It provides endpoints for user authentication, profile management, location-based matching, and nearby profile discovery. The API uses JWT tokens for authentication and supports secure media uploads through S3 presigned URLs.

## Base URL

- **Development**: `https://api-dev.shoss.io`
- **Production**: `https://api.shoss.io`
- **Production**: `https://api.shoss.io`

## Authentication

All API endpoints (except authentication endpoints) require a valid JWT token in the Authorization header:

```
Authorization: Bearer <jwt_token>
```

### JWT Token Format

JWT tokens are issued after successful platform authentication and contain the following claims:

- `uid`: Shoss user ID
- `iat`: Issued at timestamp
- `exp`: Expiration timestamp
- `iss`: Issuer (shoss-app)

## API Endpoints

### Overview

The API provides the following endpoint categories:

**Authentication:**
- `POST /auth/platform` - Platform authentication (Telegram)

**Profile Management:**
- `POST /profile` - Create new profile
- `GET /profile/{profileId}` - Get profile with media access
- `PUT /profile/{profileId}` - Update existing profile
- `DELETE /profile/{profileId}` - Delete profile and media

**Media Management:**
- `POST /profile/{profileId}/media` - Request media upload URL
- `GET /profile/{profileId}/media` - Get profile media list
- `DELETE /profile/{profileId}/media/{mediaId}` - Delete specific media

**Location Management:**
- `PUT /profile/{profileId}/location` - Update profile location
- `DELETE /profile/{profileId}/location` - Clear profile location

**Feed/Discovery:**
- `GET /feed/{profileId}/nearby` - Get nearby profiles feed with pagination

### Authentication

#### POST /auth/platform
Authenticate user with platform-specific data (currently supports Telegram).

**Request Body:**
```json
{
  "platform": "telegram",
  "platformToken": "telegram_init_data_string",
  "platformMetadata": {
    "username": "username",
    "first_name": "First",
    "last_name": "Last",
    "language_code": "en",
    "is_premium": false,
    "photo_url": "https://example.com/photo.jpg"
  }
}
```

**Response:**
```json
{
  "token": "jwt_token_string",
  "userId": "user_id",
  "profileIds": ["profile_id_1", "profile_id_2"],
  "activeProfileId": "profile_id_1",
  "limits": {
    "maxProfilesCount": 3,
    "maxMediasPerProfile": 5,
    "maxMediaFileSize": 20971520,
    "maxMediaAllowedFormats": "jpeg,jpg,png,webp"
  }
}
```



### Profile Management

Profile management endpoints for creating, retrieving, updating, and deleting user profiles.

**Profile Attributes:**
Profiles support various attributes with enumerated values:
- `sexualPosition`: bottom, versBottom, vers, versTop, top, side, blower, blowie
- `bodyType`: petite, slim, average, fit, muscular, stocky, chubby, large
- `eggplantSize`: small, average, large, extraLarge, gigantic
- `peachShape`: small, average, bubble, solid, large
- `healthPractices`: condoms, bb, condomsOrBb, noPenetrations
- `hivStatus`: negative, positive, positiveUndetectable
- `preventionPractices`: none, prep, doxypep, prepAndDoxypep
- `hosting`: hostAndTravel, hostOnly, travelOnly
- `travelDistance`: none, block, neighbourhood, city, metropolitan, state

**Profile Fields:**
- `profileName`: Internal name for the profile (not shown in feed)
- `nickName`: Display name shown to other users
- `aboutMe`: Profile description/bio
- `age`: Age as string
- `mediaIds`: Ordered list of media IDs
- `mediaRecords`: Dictionary of media metadata by ID
- `lastDistance`: Most recent location data
- `lastSeen`: Unix timestamp of last activity

#### GET /profile/{profileId}
Get a specific profile data by profile-id and media access cookies (for accessing the requested profile media)

**Headers:**
```
Authorization: Bearer <jwt_token>
```

**Response**:
```json
{
  "profileId": "profile_id",
  "profile": {
    "profileName": "Profile Name",
    "nickName": "Display Name",
    "aboutMe": "Profile description",
    "age": "25",
    "sexualPosition": "vers",
    "bodyType": "fit",
    "eggplantSize": "average",
    "peachShape": "average",
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
    "mediaSignedUrl": {
      "url": "https://media.shoss.io/media/profile_id/0/*?Expires=1704214800&Signature=abc123def456...&Key-Pair-Id=APKABC123DEFGHIJKLMN",
      "expiresAt": "2024-01-01T18:00:00"
    }
  }
}
```

**Note**: The `mediaSignedUrl` object provides CloudFront signed URL access to all media files under the profile's path (e.g., `/media/{profileId}/0/*`). It contains:
- `url`: The signed CloudFront URL with wildcard access to all profile media
- `expiresAt`: ISO timestamp when the signed URL expires

If CloudFront is not configured, `mediaSignedUrl` will be an empty object `{}`. Access control is enforced at the CDN level through the signed URL, which is scoped to the requested profile ID. The default expiration is configurable via `CoreSettings().media_cache_ttl`.

#### POST /profile
Create a new profile.

**Headers:**
```
Authorization: Bearer <jwt_token>
```

**Request Body:**
```json
{
  "profile": {
    "profileName": "Profile Name",
    "nickName": "Display Name",
    "aboutMe": "Profile description",
    "age": "25",
    "sexualPosition": "vers",
    "bodyType": "fit",
    "eggplantSize": "average",
    "peachShape": "average",
    "healthPractices": "condoms",
    "hivStatus": "negative",
    "preventionPractices": "prep",
    "hosting": "hostAndTravel",
    "travelDistance": "city"
  }
}
```

**Response:**
```json
{
  "profileId": "new_profile_id",
  "profile": {
    "profileName": "Profile Name",
    "nickName": "Display Name",
    "aboutMe": "Profile description",
    "age": "25",
    "sexualPosition": "vers",
    "bodyType": "fit",
    "eggplantSize": "average",
    "peachShape": "average",
    "healthPractices": "condoms",
    "hivStatus": "negative",
    "preventionPractices": "prep",
    "hosting": "hostAndTravel",
    "travelDistance": "city",
    "mediaIds": [],
    "mediaRecords": {},
    "lastSeen": 1704110400,
    "mediaSignedUrl": {
      "url": "https://media.shoss.io/media/new_profile_id/0/*?Expires=1704214800&Signature=abc123def456...&Key-Pair-Id=APKABC123DEFGHIJKLMN",
      "expiresAt": "2024-01-01T18:00:00"
    }
  },
  "created": true
}
```

#### PUT /profile/{profileId}
Update an existing profile.

**Headers:**
```
Authorization: Bearer <jwt_token>
```

**Request Body:**
```json
{
  "profile": {
    "profileName": "Updated Profile Name",
    "nickName": "Updated Display Name",
    "aboutMe": "Updated profile description",
    "age": "26",
    "sexualPosition": "top",
    "bodyType": "muscular",
    "eggplantSize": "large",
    "peachShape": "bubble",
    "healthPractices": "bb",
    "hivStatus": "negative",
    "preventionPractices": "prep",
    "hosting": "hostOnly",
    "travelDistance": "metropolitan"
  }
}
```

**Response:**
```json
{
  "profileId": "existing_profile_id",
  "profile": {
    "profileName": "Updated Profile Name",
    "nickName": "Updated Display Name",
    "aboutMe": "Updated profile description",
    "age": "26",
    "sexualPosition": "top",
    "bodyType": "muscular",
    "eggplantSize": "large",
    "peachShape": "bubble",
    "healthPractices": "bb",
    "hivStatus": "negative",
    "preventionPractices": "prep",
    "hosting": "hostOnly",
    "travelDistance": "metropolitan",
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
    "mediaSignedUrl": {
      "url": "https://media.shoss.io/media/existing_profile_id/0/*?Expires=1704214800&Signature=abc123def456...&Key-Pair-Id=APKABC123DEFGHIJKLMN",
      "expiresAt": "2024-01-01T18:00:00"
    }
  },
  "created": false
}
```

**Response Fields**: The profile object in all responses contains only fields defined in the ProfileRecord schema. Database-specific fields (like `userId`, `createdAt`, `updatedAt`) are automatically filtered out using `ProfileRecord.from_dict()` which validates and serializes the data using msgspec for type safety.

#### DELETE /profile/{profileId}
Delete a profile and associated media.

**Headers:**
```
Authorization: Bearer <jwt_token>
```

**Response:**
```json
{
  "profileId": "profile_id",
  "deleted": true,
  "deletedAt": "2024-01-01T12:10:00Z"
}
```


### Media Management

Media management endpoints for profile image upload, processing, and management.

**Upload Process:**
1. Client requests upload URL with media metadata
2. Server allocates a media ID and generates a presigned S3 POST URL
3. Client uploads directly to S3 using the presigned URL
4. S3 triggers Lambda for automatic processing (resize, thumbnail generation)
5. Media status transitions: `pending` → `processing` → `ready` (or `error`)

**Media Limits:**
- Max medias per profile: 5 (configurable)
- Max file size: 20 MB
- Supported formats: JPEG, JPG, PNG, WebP
- Upload URL expires in 15 minutes

**Media Status Values:**
- `pending`: Media ID allocated, waiting for upload
- `processing`: File uploaded, being processed
- `ready`: Media ready for display
- `error`: Processing failed

#### POST /profile/{profileId}/media
Request upload URL for media.

**Headers:**
```
Authorization: Bearer <jwt_token>
```

**Request Body:**
```json
{
  "mediaType": "image/jpeg",
  "mediaBlob": "base64_encoded_metadata",
  "mediaSize": 2048576
}
```

**Metadata Format** (base64 encoded):
```json
{
  "size": 2048576,
  "format": "jpeg",
  "width": 1440,
  "height": 1920,
  "dimensions": {
    "width": 1440,
    "height": 1920
  }
}
```

**Response:**
```json
{
  "mediaId": "aB3cD4eF",
  "uploadUrl": "https://s3.amazonaws.com/shoss-media-prd/uploads/20240101/user_id/profile_id/aB3cD4eF.jpg?X-Amz-Algorithm=...",
  "uploadMethod": "POST",
  "uploadHeaders": {
    "Content-Type": "image/jpeg",
    "key": "uploads/20240101/user_id/profile_id/aB3cD4eF.jpg",
    "x-amz-meta-user-id": "user_id",
    "x-amz-meta-profile-id": "profile_id",
    "x-amz-server-side-encryption": "AES256",
    "policy": "...",
    "x-amz-algorithm": "AWS4-HMAC-SHA256",
    "x-amz-credential": "...",
    "x-amz-date": "...",
    "x-amz-signature": "..."
  },
  "expiresAt": "2024-01-01T13:00:00Z"
}
```

**Note**: The response includes a presigned S3 URL that expires in 15 minutes (configurable via `CoreSettings().media_upload_expiry_hours`). The upload is processed automatically via S3 event notifications - no completion endpoint is required. Only image formats (JPEG, JPG, PNG, WebP) are supported with a maximum file size of 20MB.

#### DELETE /profile/{profileId}/media/{mediaId}
Delete media file.

**Headers:**
```
Authorization: Bearer <jwt_token>
```

**Response:**
```json
{
  "mediaId": "aB3cD4eF",
  "deleted": true,
  "deletedAt": "2024-01-01T12:10:00Z"
}
```

**Note:** Media upload completion is handled automatically via S3 event notifications. After uploading to the presigned URL, media processing is triggered automatically without requiring a separate completion endpoint.

#### GET /profile/{profileId}/media
Get media list for a profile.

**Headers:**
```
Authorization: Bearer <jwt_token>
```

**Response:**
```json
{
  "media": [
    {
      "mediaId": "media_id_1",
      "status": "ready",
      "mimeType": "image/jpeg",
      "fileSize": 2048576,
      "dimensions": {"width": 1920, "height": 1080}
    },
    {
      "mediaId": "media_id_2",
      "status": "ready",
      "mimeType": "image/jpeg",
      "fileSize": 1536000,
      "dimensions": {"width": 1440, "height": 1920}
    },
    {
      "mediaId": "media_id_3",
      "status": "processing",
      "mimeType": "image/jpeg",
      "fileSize": 3072000,
      "dimensions": {"width": 800, "height": 600}
    }
  ]
}
```

### Location Management

Location management endpoints for profile location tracking and discovery. The system uses geohash-based indexing for efficient proximity queries.

**Key Features:**
- Coordinates are rounded to 4 decimal places (~11 meters precision) for privacy
- Geohashes are automatically generated from coordinates
- The system automatically finds 8 neighboring geohash cells for area searches
- Location updates also update the profile's `lastSeen` timestamp
- Geohash precision is configurable (default: 5 characters, ~5km x 5km cell)

#### PUT /profile/{profileId}/location
Update profile location and last seen timestamp. Returns the updated profile with location information.

**Headers:**
```
Authorization: Bearer <jwt_token>
```

**Request Body:**
```json
{
  "location": {
    "latitude": 40.7128,
    "longitude": -74.0060,
    "precision": 5
  }
}
```

**Response:**
```json
{
  "profileId": "profile_id",
  "profile": {
    "profileName": "Profile Name",
    "nickName": "Display Name",
    "aboutMe": "Profile description",
    "age": "25",
    "sexualPosition": "vers",
    "bodyType": "fit",
    "eggplantSize": "average",
    "peachShape": "average",
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
    "lastSeen": 1704110400
  }
}
```

#### DELETE /profile/{profileId}/location
Clear profile location.

**Headers:**
```
Authorization: Bearer <jwt_token>
```

**Response:**
```json
{
  "profileId": "profile_id",
  "cleared": true,
  "clearedAt": "2024-01-01T12:10:00Z"
}
```

## Feed/Discovery

Feed endpoints provide advanced proximity-based profile discovery with full profile details and media access URLs.

### GET /feed/{profileId}/nearby

Get nearby profiles within geohash area that were online within the last 24 hours. Returns full profile details with signed media access URLs and pagination support. The feed uses the profile's `lastLocation` to find nearby profiles and automatically searches the profile's geohash and its 8 neighboring geohashes.

**Headers:**
```
Authorization: Bearer <jwt_token>
```

**Query Parameters:**
- `nextToken` (optional): Encrypted pagination token from previous request for continued results

**Example Request:**
```
GET /feed/abc12345/nearby?nextToken=encrypted_pagination_token
```

**Response:**
```json
{
  "profileId": "abc12345",
  "profiles": {
    "nearby_profile_id": {
      "nickName": "Display Name",
      "aboutMe": "Profile description",
      "age": "25",
      "sexualPosition": "vers",
      "bodyType": "fit",
      "eggplantSize": "average",
      "peachShape": "average",
      "healthPractices": "condoms",
      "hivStatus": "negative",
      "preventionPractices": "prep",
      "hosting": "hostAndTravel",
      "travelDistance": "city",
      "mediaIds": ["media_id_1", "media_id_2"],
      "mediaRecords": {
          "media_id_1": {
              "flags": "",
              "mimeType": "image/jpeg",
          },
          "media_id_2": {
              "flags": "",
              "mimeType": "image/jpeg",
          }
      },
      "lastDistance": 4071,
      "lastSeen": 1704110400,
      "mediaSignedUrl": {
        "url": "https://media.shoss.io/media/nearby_profile_id/0/*?Expires=1704214800&Signature=abc123...&Key-Pair-Id=APKABC123...",
        "expiresAt": "2024-01-01T18:00:00"
      }
    }
  },
  "nextToken": "encrypted_pagination_token_for_next_page"
}
```

**Note**: The feed response uses a compact profile format (`ProfileRecordBase`) to optimize bandwidth:
- `mediaIds`: Array of media-ids.
- `mediaRecords`: Array of media-records with flag / mimeType.
- `lastDistance`: Last distance from current profile (in meters).
- `profileName`: Omitted from feed responses for privacy
- `mediaSignedUrl`: Object with `url` and `expiresAt` fields for CloudFront signed URL access (or empty object `{}` if CloudFront not configured)

**Error Responses:**
- `400 Bad Request`: Invalid profile ID or pagination token
- `404 Not Found`: Profile not found or no location data available
- `500 Internal Server Error`: Feed service unavailable

## Error Responses

All endpoints return consistent error responses:

```json
{
  "error": "Error message",
  "error_code": "ERROR_CODE",
  "details": {
    "field": "Additional error details"
  }
}
```

### Common HTTP Status Codes

- `200 OK`: Request successful
- `201 Created`: Resource created successfully
- `400 Bad Request`: Invalid request data
- `401 Unauthorized`: Authentication required or invalid
- `403 Forbidden`: Access denied
- `404 Not Found`: Resource not found
- `422 Unprocessable Entity`: Validation error
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

## Rate Limiting

API Gateway enforces throttling limits to prevent abuse:

- **Default burst limit**: 5,000 requests per second
- **Default steady-state limit**: 10,000 requests per second

These limits are enforced at the AWS account level and can be adjusted per environment. Individual Lambda functions may have additional concurrency limits. When rate limits are exceeded, the API returns a `429 Too Many Requests` error.

## Pagination

The feed endpoints use encrypted pagination tokens for secure and efficient pagination across distributed data:

- **Feed endpoints** (`/feed/{profileId}/nearby`): Use `nextToken` parameter with encrypted pagination tokens
  - Tokens are encrypted and include expiration timestamps for security
  - Tokens are scoped to the specific query and cannot be reused across different searches
  - Default TTL for pagination tokens is configurable via settings
  
**Example pagination flow:**
```
GET /feed/{profileId}/nearby
→ Returns: { "profiles": {...}, "nextToken": "encrypted_token_123" }

GET /feed/{profileId}/nearby?nextToken=encrypted_token_123
→ Returns: { "profiles": {...}, "nextToken": "encrypted_token_456" }
```

**Pagination errors:**
- If a token is expired or invalid, the API returns a `400 Bad Request` error
- Clients should restart pagination from the beginning if a token becomes invalid

## Domain Configuration

The API is configured with custom domains for each environment:

### Development Environment
- **Domain**: `api-dev.shoss.io`
- **SSL**: AWS Certificate Manager certificate
- **DNS**: Route53 hosted zone

### Production Environment
- **Domain**: `api.shoss.io`
- **SSL**: AWS Certificate Manager certificate
- **DNS**: Route53 hosted zone

### Production Environment
- **Domain**: `api.shoss.io`
- **SSL**: AWS Certificate Manager certificate
- **DNS**: Route53 hosted zone

### Media Domain
- **Domain**: `media.shoss.io` (production only)
- **CDN**: CloudFront distribution
- **Storage**: S3 bucket with CloudFront origin

## CORS Configuration

The API Gateway is configured with CORS support for cross-origin requests:

### CORS Headers
```http
Access-Control-Allow-Origin: *
Access-Control-Allow-Headers: Content-Type,Authorization
Access-Control-Allow-Methods: GET,POST,PUT,DELETE,OPTIONS
Access-Control-Allow-Credentials: true
```

### OPTIONS Methods
All endpoints support preflight OPTIONS requests for CORS compliance:
- `OPTIONS /profile` - Profile creation preflight (POST)
- `OPTIONS /profile/{profileId}` - Profile operations preflight (GET,PUT,DELETE)
- `OPTIONS /profile/{profileId}/media` - Media operations preflight (GET,POST)
- `OPTIONS /profile/{profileId}/media/{mediaId}` - Media deletion preflight (DELETE)
- `OPTIONS /profile/{profileId}/location` - Location operations preflight (PUT,DELETE)
- `OPTIONS /feed/{profileId}/nearby` - Feed discovery preflight (GET)
- `OPTIONS /auth/platform` - Authentication preflight (POST)

## SSL/TLS Configuration

All custom domains use SSL certificates managed by AWS Certificate Manager:

- **Certificate Type**: Regional certificate for API Gateway
- **Validation Method**: DNS validation
- **Security Policy**: TLS 1.2
- **Auto-renewal**: Enabled

## DNS Configuration

The infrastructure uses Route53 for DNS management:

- **Hosted Zone**: `shoss.io`
- **A Records**: Point to API Gateway custom domain
- **CNAME Records**: For SSL certificate validation
- **Nameservers**: Route53 nameservers for the domain
