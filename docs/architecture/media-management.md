# Media Management Backend Implementation Specification

## Overview

This document specifies the backend implementation for media upload, processing, and serving functionality within the User Service. The implementation handles image and video upload requests, automatically processes uploaded media, generates thumbnails, stores metadata, and serves media through CloudFront CDN with signed URLs for security.

## Architecture Components

### Service Location
- **Media Management**: User Service (`src/services/user/aws_lambdas/user_media_mgmt/`)
- **Media Processing**: User Service (`src/services/user/aws_lambdas/user_media_processing/`)

### AWS Resources
- **S3 Bucket**: `shoss-media-{environment}` (configured via `MEDIA_S3_BUCKET` env var)
- **CloudFront Distribution**: Media delivery CDN with signed URL authentication
- **Lambda Functions**:
  - `user_media_mgmt` - Media upload URL generation and management
  - `user_media_processing` - Automated media processing triggered by S3 events
- **DynamoDB**: Metadata storage in main table
- **S3 Event Notifications**: Trigger media processing automatically on upload

### Supported Media Types
- **Images**: JPEG, JPG, PNG, WebP
- **Videos**: MP4, MOV, WebM (when `video_clips_enabled = true`)
- **Maximum Image File Size**: Configurable via `CoreSettings().media_max_file_size` (default 10MB)
- **Maximum Video File Size**: Configurable via `CoreSettings().video_max_file_size`
- **Maximum Media per Profile/Post/Chat**: Configurable via `CoreSettings()`

## S3 Path Structure

All paths include `privacy` and `association` segments for fine-grained access control.

| Location | Path Pattern |
|----------|-------------|
| Upload (temporary) | `uploads/{date}/{user_id}/{profile_id}/{privacy}/{association}/{media_id}.{ext}` |
| Processed image | `media/{profile_id}/{privacy}/{association}/{media_id}.jpg` |
| Processed thumbnail | `media/{profile_id}/{privacy}/{association}/{media_id}-tb.jpg` |
| Processed video | `media/{profile_id}/{privacy}/{association}/{media_id}.mp4` |
| Video poster | `media/{profile_id}/{privacy}/{association}/{media_id}-poster.jpg` |

- **privacy**: `public` | `protected`
- **association**: `profile` | `post` | `chat`

## API Endpoints

### 1. Create Media (Request Upload URL)

**Endpoint**: `POST /profile/{profileId}/media`

**Purpose**: Allocate media ID and provide presigned S3 upload URL

**Request Headers**:
```
Authorization: Bearer <jwt_token>
Content-Type: application/json
```

**Request Body**:
```json
{
  "mediaType": "image/jpeg",
  "mediaBlob": "base64_encoded_metadata",
  "mediaSize": 2048576,
  "mediaAssociation": "profile",
  "mediaPrivacy": "public"
}
```

- `mediaAssociation` (optional): `profile` (default) | `post` | `chat`
- `mediaPrivacy` (optional): `public` (default) | `protected`

**Metadata Format** (base64 encoded `mediaBlob`):
```json
{
  "dimensions": {
    "width": 1440,
    "height": 1920
  }
}
```

**Response**:
```json
{
  "mediaId": "aB3cD4eF",
  "uploadUrl": "https://s3.amazonaws.com/shoss-media-prd/",
  "uploadMethod": "POST",
  "uploadHeaders": {
    "Content-Type": "image/jpeg",
    "key": "uploads/20240101/user_id/profile_id/public/profile/aB3cD4eF.jpg",
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

**Error Responses**:
```json
{"statusCode": 400, "body": "{\"error\": \"Unsupported image format: gif\"}"}
{"statusCode": 400, "body": "{\"error\": \"File size exceeds limit: 10MB for image\"}"}
{"statusCode": 400, "body": "{\"error\": \"Maximum profile media limit of 5 exceeded\"}"}
```

### 2. List Media

**Endpoint**: `GET /profile/{profileId}/media`

**Response**:
```json
{
  "media": [
    {
      "mediaId": "aB3cD4eF",
      "mimeType": "image/jpeg",
      "status": "ready",
      "privacy": "public",
      "association": "profile",
      "properties": {},
      "dimensions": {"width": 1920, "height": 1080, "size": 204800}
    }
  ]
}
```

Note: `dimensions.size` holds the processed file size in bytes.

### 3. Media Access (Integrated with Profile GET)

**Endpoint**: `GET /profile/{profileId}`

**Purpose**: Retrieve profile data including wildcard signed URL for media access

The response includes profile data and a CloudFront wildcard signed URL. Each `mediaRecord` entry in the response includes `privacy` and `association` so the client can construct the correct CDN URL.

**Example mediaRecords in profile response**:
```json
{
  "mediaRecords": {
    "aB3cD4eF": {
      "mimeType": "image/jpeg",
      "privacy": "public",
      "association": "profile",
      "flags": ""
    }
  }
}
```

**Client URL construction**:
```
https://{cloudfront_domain}/media/{profileId}/{privacy}/{association}/{mediaId}.jpg
https://{cloudfront_domain}/media/{profileId}/{privacy}/{association}/{mediaId}-tb.jpg
```

### 4. Delete Media

**Endpoint**: `DELETE /profile/{profileId}/media/{mediaId}`

**Purpose**: Delete media files from S3 and remove the record

**Response**:
```json
{
  "mediaId": "aB3cD4eF",
  "deleted": true,
  "deletedAt": "2024-01-01T12:10:00Z"
}
```

## Data Models

### DynamoDB Schema — Media Record

```
PK: PROFILE#{profileId}
SK: MEDIA#{mediaId}
GSI1PK: MEDIA#{mediaId}
GSI1SK: PROFILE#{profileId}
```

**Fields**:
```json
{
  "mimeType": "image/jpeg",
  "status": "pending | processing | ready | error",
  "privacy": "public | protected",
  "association": "profile | post | chat",
  "properties": {},
  "dimensions": {"width": 1920, "height": 1080, "size": 204800},
  "ttl": 1704000000,
  "createdAt": "2024-01-01T12:00:00Z",
  "processedAt": "2024-01-01T12:01:00Z"
}
```

Note: `dimensions.size` stores the processed file size in bytes (set after processing, not at upload time).

### Profile mediaRecords (compact, stored on profile item)

```json
{
  "mediaRecords": {
    "aB3cD4eF": {
      "mimeType": "image/jpeg",
      "status": "ready",
      "privacy": "public",
      "association": "profile",
      "dimensions": {"width": 1920, "height": 1080, "size": 204800},
      "flags": ""
    }
  },
  "mediaIds": ["aB3cD4eF"]
}
```

### Python Data Classes

```python
class MediaStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"

class MediaAssociation(str, Enum):
    PROFILE = "profile"
    POST = "post"
    CHAT = "chat"

class MediaPrivacy(str, Enum):
    PUBLIC = "public"
    PROTECTED = "protected"

class MediaRecord(msgspec.Struct):
    mimeType: str = "image/jpeg"
    status: MediaStatus = MediaStatus.PENDING
    privacy: MediaPrivacy = MediaPrivacy.PUBLIC
    association: MediaAssociation = MediaAssociation.PROFILE
    properties: Dict[str, Any] = {}
    dimensions: Dict[str, int] = {}  # keys: width, height, duration, size
    ttl: Optional[int] = None
```

## Media Management Flow

### Upload Process

1. **Request Upload URL** (`POST /profile/{profileId}/media`)
   - Client sends `mediaType`, `mediaBlob` (base64 metadata), `mediaSize`, optional `mediaAssociation`, `mediaPrivacy`
   - Server validates format, file size, association limits
   - Server allocates new media ID
   - Server generates presigned S3 POST URL to `uploads/{date}/{user_id}/{profile_id}/{privacy}/{association}/{media_id}.{ext}`
   - Server creates DynamoDB media record with status `PENDING`
   - Server adds media entry to profile's `mediaRecords` map

2. **Client Direct Upload**
   - Client uploads file directly to S3 using presigned POST URL
   - URL expires in 15 minutes (`CoreSettings().media_upload_expiry_hours`)
   - **No completion call required** — S3 event triggers processing automatically

3. **Automatic Processing** (S3 Event → `user_media_processing` Lambda)
   - S3 key parsed: `uploads/{date}/{user_id}/{profile_id}/{privacy}/{association}/{media_id}.{ext}`
   - Status set to `PROCESSING`
   - **Images**: validated, converted to RGB JPEG, resized, thumbnail generated, stored at `media/{profile_id}/{privacy}/{association}/{media_id}.jpg` and `…-tb.jpg`
   - **Videos**: probed with ffprobe, transcoded to H.264/MP4 (first N seconds, center-crop 3:4), poster and thumbnail extracted, stored at `media/{profile_id}/{privacy}/{association}/{media_id}.mp4`, `….jpg`, `…-tb.jpg`
   - CloudFront cache invalidated for processed paths
   - Original upload file deleted from S3
   - Status set to `READY` with `dimensions.size` = actual processed file size
   - On failure: status set to `ERROR`

4. **Media Serving**
   - Served via CloudFront CDN
   - Client constructs URL: `https://{cloudfront_domain}/media/{profileId}/{privacy}/{association}/{mediaId}.jpg`
   - Wildcard signed URLs scoped to profile provide access with configurable TTL

## Image Processing & Optimization

- **Format Conversion**: PNG/WebP/RGBA → RGB JPEG
- **Progressive JPEG** encoding for better web loading
- **Chroma Subsampling** for reduced file size
- **Quality Settings** (configurable):
  - Original: `media_original_quality` (default 80%)
  - Thumbnail: `media_thumbnail_quality` (default 75%)
- **Max Size**: originals capped at `media_max_original_size` pixels on longest edge (default 1920px)
- **Thumbnail**: fixed `media_thumbnail_width × media_thumbnail_height` (default 320×240) with white padding

## Video Processing

- **Codec**: H.264 (libx264), AAC audio, MP4 container
- **Duration**: Clipped to `video_max_duration_seconds` (first N seconds)
- **Crop**: Center-crop to `video_target_width × video_target_height` (default 720×960, 3:4 ratio)
- **Bitrate**: `video_output_bitrate` (default 1.5M)
- **Poster Frame**: extracted at 0.5s, stored as JPEG
- **Thumbnail**: generated from poster frame at standard thumbnail dimensions

## Validation & Security

### File Validation
- **Format**: checked against `CoreSettings().media_allowed_formats` / `video_allowed_formats`
- **File Size**: checked against `media_max_file_size` / `video_max_file_size`
- **Image Dimensions**: min 100×100, max 4000×4000 (validated during processing)
- **Media ID**: validated as allocated for the profile before processing

### S3 Security
- Presigned POST conditions enforce: correct content type, file size range, user/profile metadata, upload path prefix, AES256 encryption
- Original uploads are deleted after successful processing
- All processed files stored with `ServerSideEncryption: AES256`, `CacheControl: public, max-age=31536000`

### Access Control
- CloudFront wildcard signed URLs scoped per profile
- Profile ownership verified via JWT user ID

## Configuration

### CoreSettings Reference

```python
# Media limits
max_medias_for_profile: int = 5
max_medias_for_post: int = 10
max_medias_for_chat: int = 1

# Upload
media_upload_expiry_hours: float = 0.25  # 15 minutes

# Image formats
media_allowed_formats: list = ["jpeg", "jpg", "png", "webp"]
media_max_file_size: int = 10485760  # 10MB

# Image processing
media_original_quality: int = 80
media_thumbnail_quality: int = 75
media_max_original_size: int = 1920
media_thumbnail_width: int = 320
media_thumbnail_height: int = 240

# Video
video_clips_enabled: bool = False
video_allowed_formats: list = ["mp4", "mov", "webm"]
video_max_file_size: int = 104857600  # 100MB
video_max_duration_seconds: int = 5
video_target_width: int = 720
video_target_height: int = 960
video_output_bitrate: str = "1.5M"
video_poster_quality: int = 85

# TTL (days)
media_ttl_for_profile_days: int = 3650  # 10 years
media_ttl_for_post_days: int = 365
media_ttl_for_chat_days: int = 30
```

## Error Handling

```python
class ResponseError(Exception):
    def __init__(self, status_code: int, body: Dict[str, Any]):
        self.status_code = status_code
        self.body = body

    def to_dict(self) -> Dict[str, Any]:
        return {
            "statusCode": self.status_code,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(self.body)
        }
```

## Implementation Status

### Media Management Lambda (`user_media_mgmt`)
- [x] Create Lambda function handler
- [x] S3 presigned URL generation with `{privacy}/{association}` path structure
- [x] Upload request validation (format, size, association limits)
- [x] ~~Upload completion handling~~ (Obsoleted — S3 event handles processing)
- [x] Media deletion (removes S3 files using correct privacy/association paths)
- [x] Media listing
- [x] Privacy and association support in all paths
- [x] Error handling and logging
- [ ] Rate limiting for upload requests

### Media Processing Lambda (`user_media_processing`)
- [x] S3 event-triggered processing
- [x] Parse `{privacy}/{association}` from upload path
- [x] Image validation, optimization, thumbnail generation
- [x] Video transcoding (H.264/MP4), poster and thumbnail extraction
- [x] Store processed files at `media/{profile_id}/{privacy}/{association}/{media_id}.*`
- [x] Update `dimensions.size` with actual processed file size
- [x] CloudFront cache invalidation
- [x] Delete original upload after processing
- [x] Status lifecycle: `pending → processing → ready | error`
- [ ] Retry mechanism for transient failures

### Infrastructure & Security
- [x] S3 bucket policies with user-scoped presigned URLs
- [x] AES256 server-side encryption enforced
- [x] S3 lifecycle policies for incomplete uploads
- [ ] Configure S3 event notifications for processing triggers
- [ ] Set up CloudFront distribution with signed URL authentication
- [ ] Unit tests
- [ ] Integration tests
- [ ] Security headers for CloudFront responses

## Testing Strategy

### Unit Tests
- Upload request validation (format, size, association, privacy)
- Media ID allocation with per-association limits
- S3 presigned URL generation with correct path structure
- Error handling scenarios

### Integration Tests
- End-to-end upload flow (mgmt → S3 → processing)
- S3 operations with privacy/association paths
- DynamoDB create/update/delete
- Profile ownership validation
- CloudFront signed URL authentication

### Security Tests
- Unauthorized profile access
- Presigned URL scope enforcement (user/profile isolation)
- Path structure validation
- Encryption enforcement
