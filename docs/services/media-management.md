# Media Management Backend Implementation Specification

## Overview

This document specifies the backend implementation for media upload, processing, and serving functionality within the User Service. The implementation handles image upload requests, automatically processes uploaded media, generates thumbnails, stores metadata, and serves images through CloudFront CDN with signed URLs for security.

## Architecture Components

### Service Location
- **Media Management**: User Service (`src/services/user/aws_lambdas/user_media_mgmt/`)
- **Media Processing**: User Service (`src/services/user/aws_lambdas/user_media_processing/`)

### AWS Resources
- **S3 Bucket**: `vibe-dating-media-{environment}` (configured via `MEDIA_S3_BUCKET` env var)
- **CloudFront Distribution**: Media delivery CDN with signed URL authentication
- **Lambda Functions**:
  - `user_media_mgmt` - Media upload URL generation and management
  - `user_media_processing` - Automated media processing triggered by S3 events
- **DynamoDB**: Metadata storage in main table
- **S3 Event Notifications**: Trigger media processing automatically on upload

### Supported Media Types
- **Images Only**: JPEG, JPG, PNG, WebP
- **Maximum File Size**: 20MB (configurable via `CoreSettings().media_max_file_size`)
- **Maximum Media per Profile**: 5 (configurable via `CoreSettings().max_medias_per_profile`)

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

**Response**:
```json
{
  "mediaId": "aB3cD4eF",
  "uploadUrl": "https://s3.amazonaws.com/vibe-dating-media-prod/uploads/20240101/user_id/profile_id/aB3cD4eF.jpg?X-Amz-Algorithm=...",
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

**Error Responses**:
```json
{
  "statusCode": 400,
  "headers": {"Content-Type": "application/json"},
  "body": "{\"error\": \"Only image media class supported\"}"
}
```
```json
{
  "statusCode": 400,
  "headers": {"Content-Type": "application/json"},
  "body": "{\"error\": \"File size exceeds limit: 20MB\"}"
}
```
```json
{
  "statusCode": 400,
  "headers": {"Content-Type": "application/json"},
  "body": "{\"error\": \"Unsupported format: gif\"}"
}
```

**Implementation**:
```python
def create_media(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
    # 1. Validate request and decode metadata
    # 2. Get available media ID
    # 3. Generate presigned S3 upload URL
    # 4. Create media record and store pending upload
    # 5. Return response with expiration
```

### 2. Media Access (Integrated with Profile GET)

**Endpoint**: `GET /profile/{profileId}`

**Purpose**: Retrieve profile data including wildcard signed URL for media access

**Note**: Media access is integrated into the profile GET endpoint. When a user requests any profile, the response includes both profile data and a CloudFront wildcard signed URL for accessing all media files under the profile's path.

**Response includes**:
- Profile information
- `signedUrl` object with wildcard signed URL
- 2-hour expiration for browser caching

**Example Response**:
```json
{
  "profile": {
    "profileId": "aB3cD4eF",
    "userId": "user123",
    "nickName": "Display Name",
    "media": {"xY9wV8uT": {"status": "ready", "fileSize": 2048576, "dimensions": {"width": 1920, "height": 1080}}, "mN5lK3jH": {"status": "ready", "fileSize": 1536000, "dimensions": {"width": 1440, "height": 1920}}},
    // ... other profile fields
  },
  "signedUrl": {
    "url": "https://media.vibe-dating.io/media/aB3cD4eF/0/*?Expires=1704214800&Signature=abc123def456...&Key-Pair-Id=APKABC123DEFGHIJKLMN",
    "expiresAt": "2024-01-02T13:00:00Z"
  }
}
```

**Security Note**: The CloudFront wildcard signed URL provides access to all media files under the profile's path (e.g., `/media/{profileId}/*`). Access control is enforced at the CDN level through the signed URL, which is scoped to the requested profile ID. The URL is valid for 2 hours to enable browser caching.

### 3. Delete Media

**Endpoint**: `DELETE /profile/{profileId}/media/{mediaId}`

**Purpose**: Delete media file and record

**Response**:
```json
{
  "mediaId": "aB3cD4eF",
  "deleted": true,
  "deletedAt": "2024-01-01T12:10:00Z"
}
```

**Error Responses**:
```json
{
  "statusCode": 404,
  "headers": {"Content-Type": "application/json"},
  "body": "{\"error\": \"Media ID not found\"}"
}
```

## Data Models

### DynamoDB Schema

#### Profile Media Record
```json
{
  "PK": "PROFILE#{profileId}",
  "SK": "MEDIA#{mediaId}",
  "mediaId": "aB3cD4eF",
  "profileId": "profile123",
  "userId": "user456",
  "s3Key": "uploads/profile-images/aB3cD4eF.jpg",
  "status": "pending",
  "order": 1,
  "metadata": {
    "size": 2048576,
    "format": "jpeg",
    "width": 1440,
    "height": 1920,
    "extension": "jpg"
  },
  "mediaType": "image",
  "fileSize": 2048576,
  "mimeType": "image/jpeg",
  "dimensions": {
    "width": 1440,
    "height": 1920
  },
  "createdAt": "2024-01-01T12:00:00Z",
  "updatedAt": "2024-01-01T12:00:00Z",
  "thumbnailKey": "media/profile123/0/aB3cD4eF-tb.jpg"
}
```

### Python Data Classes

```python
from enum import Enum
from typing import Any, Dict, Optional
import msgspec

class MediaStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"

class MediaType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"

class MediaRecord(msgspec.Struct):
    """Media record validation using msgspec"""
    mediaId: str
    profileId: str
    userId: str
    s3Key: str
    status: MediaStatus = MediaStatus.PENDING
    order: int = 1
    metadata: Dict[str, Any] = msgspec.field(default_factory=dict)
    mediaType: Optional[MediaType] = None
    fileSize: Optional[int] = None
    mimeType: Optional[str] = None
    dimensions: Optional[Dict[str, int]] = None
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None
    thumbnailKey: Optional[str] = None
```

## Media Management Flow

### Upload Process

1. **Request Upload URL**
   - Client sends upload request with metadata (mediaType, mediaBlob, mediaSize)
   - Server validates request and decodes base64 metadata
   - Server validates file size against `CoreSettings().media_max_file_size` (10MB)
   - Server validates file format against `CoreSettings().media_allowed_formats`
   - Server allocates new media ID using `MediaManager.allocate_media_id()`
   - Server generates presigned S3 upload URL with structured path: `uploads/{date}/{user_id}/{profile_id}/{media_id}.{extension}`
   - Server creates media record in DynamoDB with status **PENDING**
   - Server activates media ID in profile's media dictionary with initial attributes

2. **Client Upload**
   - Client uploads file directly to S3 using presigned URL
   - S3 stores file with metadata (user-id, profile-id) and server-side encryption
   - Upload URL expires in 15 minutes (`CoreSettings().media_upload_expiry_hours`)
   - **No completion call required** - S3 event automatically triggers processing

3. **Automatic Processing** (S3 Event Triggered)
   - S3 upload event triggers `user_media_processing` Lambda automatically
   - Media status updated to **PROCESSING**
   - Image validation using PIL:
     - Format validation against allowed formats
     - Dimension validation (min 100x100, max 4000x4000)
   - Image optimization and format conversion:
     - All formats converted to RGB JPG
     - Progressive JPEG encoding for better web loading
     - Chroma subsampling for smaller file sizes
     - Quality optimization (original: 80%, thumbnail: 75%)
   - Thumbnail generation with aspect ratio preservation:
     - Target dimensions: 320x240 pixels
     - White background padding for consistent sizing
   - Final images stored in optimized structure:
     - Original: `media/{profile_id}/0/{media_id}.jpg`
     - Thumbnail: `media/{profile_id}/0/{media_id}-tb.jpg`
   - CloudFront cache invalidation for immediate availability
   - On success: Media status updated to **READY**, URLs populated
   - On failure: Media status updated to **ERROR**

4. **Media Serving**
   - Images served via CloudFront CDN with signed URLs
   - Wildcard signed URLs provide access to profile's media with 6-hour TTL
   - Secure access pattern prevents unauthorized viewing
   - Browser caching optimized for performance

## Image Processing & Optimization

The system automatically converts all uploaded image formats to optimized JPG with advanced compression:

### Format Conversion
- **PNG**: Transparency removed with white background, converted to RGB
- **WEBP**: Converted to JPG format
- **All formats**: Standardized to JPG for consistent web delivery

### Compression Features
- **Progressive JPEG**: Images load progressively for better user experience
- **Chroma Subsampling**: Reduces file size while maintaining visual quality
- **Quality Optimization**:
  - Original images: Configurable quality (default 80%) for balanced size/quality
  - Thumbnails: Configurable quality (default 75%) for smaller file sizes
- **Automatic Resizing**: Configurable dimensions (default: originals capped at 1920px, thumbnails at 320x240px)

### Performance Benefits
- Reduced bandwidth usage
- Faster page loading
- Consistent format across all media
- Optimized for web delivery

## Validation & Security

### Input Validation

```python
def validate_upload_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate upload request data and decode metadata"""
    required_fields = ["mediaType", "mediaMeta"]

    # Check required fields
    for field in required_fields:
        if field not in request_data:
            raise ResponseError(400, {"error": f"Missing required field: {field}"})

    # Validate media type
    if request_data["mediaType"] != "image":
        raise ResponseError(400, {"error": "Only image type supported"})

    # Decode and validate metadata
    metadata = self._decode_media_metadata(request_data["mediaMeta"])

    # Validate file size, format, and extension
    self._validate_file_size(metadata.get("size", 0))
    self._validate_file_format(metadata.get("format", ""))
    self._validate_file_extension(metadata.get("extension", ""))

    return metadata
```

### File Validation

```python
def _validate_file_size(self, size: int) -> None:
    """Validate file size against limits"""
    if size > self.core_settings.media_max_file_size:
        raise ResponseError(
            413,
            {"error": f"File size exceeds limit: {self.core_settings.media_max_file_size} bytes"}
        )

def _validate_file_format(self, format_str: str) -> None:
    """Validate file format against allowed formats"""
    file_format = format_str.lower()
    if file_format not in self.core_settings.media_allowed_formats:
        raise ResponseError(
            400,
            {"error": f"Unsupported format: {file_format}"}
        )

def _validate_file_extension(self, extension: str) -> None:
    """Validate file extension against allowed extensions"""
    extension = extension.lower()
    if extension not in ["jpg", "jpeg", "png", "webp"]:
        raise ResponseError(
            400,
            {"error": f"Unsupported file extension: {extension}"}
        )
```

### Access Control

```python
def check_profile_ownership(user_id: str, profile_id: str) -> bool:
    """Verify user owns the profile"""
    profile_mgmt = ProfileManager(user_id)
    return profile_mgmt.validate_profile_id(profile_id, is_existing=True)
```

### S3 Security

```python
def generate_presigned_upload_url(self, media_id: str, content_type: str) -> Dict[str, Any]:
    """Generate secure presigned upload URL with enhanced security"""
    date = datetime.utcnow().strftime("%Y%m%d")
    extension = content_type.split('/')[-1]
    s3_key = f"uploads/{date}/{self.user_id}/{self.profile_id}/{media_id}.{extension}"

    presigned_url = self.s3_client.generate_presigned_post(
        Bucket=self.media_bucket,
        Key=s3_key,
        Fields={
            "Content-Type": content_type,
            "x-amz-meta-user-id": self.user_id,
            "x-amz-meta-profile-id": self.profile_id,
            "x-amz-server-side-encryption": "AES256"
        },
        Conditions=[
            {"Content-Type": content_type},
            ["content-length-range", 1024, self.core_settings.media_max_file_size],
            {"x-amz-meta-user-id": self.user_id},
            {"x-amz-meta-profile-id": self.profile_id},
            {"x-amz-server-side-encryption": "AES256"},
            ["starts-with", "$key", f"uploads/{date}/{self.user_id}/{self.profile_id}/"],
        ],
        ExpiresIn=int(self.core_settings.media_upload_expiry_hours * 3600),
    )

    return {
        "uploadUrl": presigned_url["url"],
        "uploadMethod": "POST",
        "uploadHeaders": presigned_url["fields"],
        "s3Key": s3_key,
    }
```

### Enhanced Security Features

- **Short Expiration**: Presigned URLs expire in 15 minutes (0.25 hours)
- **User Isolation**: Each presigned URL is restricted to specific user and profile
- **Path Validation**: Uploads must follow the expected directory structure
- **Metadata Enforcement**: User and profile IDs are embedded in upload metadata
- **Magic Number Validation**: File signatures are validated to prevent malicious uploads
- **Lifecycle Policies**: Incomplete uploads are automatically deleted after 1 day
- **Encryption Enforcement**: All uploads use server-side encryption with AES256
- **Public Access Prevention**: Blocked public read access to uploaded files
- **Bucket Policy**: Restrict access to specific AWS roles and Lambda functions

## CloudFront Wildcard Signed URLs

The system uses CloudFront wildcard signed URLs for secure media access with 2-hour expiration, optimized for browser caching and Swiper integration.

### Implementation

```python
def generate_wildcard_signed_url(self, profile_id: str) -> Dict[str, str]:
    """Generate CloudFront wildcard signed URL for profile media access"""
    if not self.cloudfront_key_pair_id or not self.cloudfront_private_key:
        return {}

    try:
        # Set expiration to 2 hours from now for browser caching
        expire_date = datetime.utcnow() + timedelta(hours=2)

        # Create the wildcard resource URL pattern
        resource_url = f"https://{self.cloudfront_domain}/media/0/{profile_id}/*"

        # Create CloudFront signer
        def rsa_signer(message):
            private_key = rsa.PrivateKey.load_pkcs1(self.cloudfront_private_key.encode())
            return rsa.sign(message, private_key, 'SHA-1')

        cloudfront_signer = CloudFrontSigner(self.cloudfront_key_pair_id, rsa_signer)

        # Generate wildcard signed URL
        signed_url = cloudfront_signer.generate_presigned_url(
            resource_url,
            date_less_than=expire_date
        )

        return {
            'url': signed_url,
            'expiresAt': expire_date.isoformat() + 'Z'
        }

    except Exception as e:
        print(f"Warning: Failed to generate wildcard signed URL: {e}")
        return {}
```

### Usage Pattern

1. Frontend requests profile data
2. Backend generates wildcard signed URL with 2-hour expiration
3. Frontend constructs specific image URLs by replacing `*` with media IDs
4. URLs work directly in `<img>` tags for Swiper compatibility
5. Browser caches images for 2 hours based on URL expiration
6. After expiration, new wildcard signed URL must be requested

## Configuration

### Environment Variables

```python
# S3 Configuration
MEDIA_S3_BUCKET = os.environ.get("MEDIA_S3_BUCKET")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# CloudFront Configuration
CLOUDFRONT_DOMAIN = os.environ.get("CLOUDFRONT_DOMAIN")
CLOUDFRONT_DISTRIBUTION_ID = os.environ.get("CLOUDFRONT_DISTRIBUTION_ID")
CLOUDFRONT_KEY_PAIR_ID = os.environ.get("CLOUDFRONT_KEY_PAIR_ID")
CLOUDFRONT_PRIVATE_KEY = os.environ.get("CLOUDFRONT_PRIVATE_KEY")

# Media Configuration
MEDIA_MAX_FILE_SIZE = int(os.environ.get("MEDIA_MAX_FILE_SIZE", 10485760))  # 10MB
MEDIA_ALLOWED_FORMATS = os.environ.get("MEDIA_ALLOWED_FORMATS", "jpeg,jpg,png,webp").split(",")
MEDIA_UPLOAD_EXPIRY_HOURS = float(os.environ.get("MEDIA_UPLOAD_EXPIRY_HOURS", 0.25))
MAX_MEDIAS_PER_PROFILE = int(os.environ.get("MAX_MEDIAS_PER_PROFILE", 5))
MEDIA_CACHE_TTL = int(os.environ.get("MEDIA_CACHE_TTL", 7200))  # 2 hours
```

### Core Settings

```python
@dataclass
class CoreSettings:
    record_id_length: int = 8
    max_profiles_count: int = 3
    max_medias_per_profile: int = 5
    media_max_file_size: int = 10485760
    media_allowed_formats: list[str] = ["jpeg", "jpg", "png", "webp"]
    media_upload_expiry_hours: float = 0.25  # 15 minutes
    media_cache_ttl: int = 21600  # 6 hours for browser caching

    # Image processing quality settings
    media_original_quality: int = 80  # Quality for original processed images (0-100)
    media_thumbnail_quality: int = 75  # Quality for thumbnail images (0-100)
    media_max_original_size: int = 1920  # Maximum width/height for original images
    media_thumbnail_width: int = 320  # Thumbnail width
    media_thumbnail_height: int = 240  # Thumbnail height
```

## Error Handling

### Error Types

```python
class ResponseError(Exception):
    """Custom response error with status code and message"""
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

### Common Error Responses

```json
{
  "statusCode": 400,
  "headers": {"Content-Type": "application/json"},
  "body": "{\"error\": \"Invalid mediaMeta format: Invalid base64\"}"
}
```
```json
{
  "statusCode": 403,
  "headers": {"Content-Type": "application/json"},
  "body": "{\"error\": \"Unauthorized: User does not own profile\"}"
}
```
```json
{
  "statusCode": 413,
  "headers": {"Content-Type": "application/json"},
  "body": "{\"error\": \"File size exceeds maximum limit of 10MB\"}"
}
```

## Implementation Status

### Media Management Lambda (`user_media_mgmt`)
- [x] Create Lambda function handler
- [x] Implement S3 presigned URL generation with structured paths
- [x] Implement upload request validation
- [x] ~~Implement upload completion handling~~ (Obsoleted - returns HTTP 410)
- [x] Implement media deletion with new folder structure support
- [x] Implement media reordering with batch processing
- [x] Create DynamoDB operations
- [x] Add input validation and security checks
- [x] Implement error handling and logging
- [x] Enhanced security with user-specific presigned URLs
- [x] Added magic number validation for file types
- [ ] Add rate limiting for upload requests

### Media Processing Lambda (`user_media_processing`)
- [x] Implement automatic S3 event-triggered processing
- [x] Set media status to PROCESSING on upload event
- [x] Implement image validation and processing
- [x] Convert all uploaded formats (PNG, WEBP, etc.) to optimized JPG
- [x] Generate thumbnails with new folder structure (`media/{profile_id}/0/{media_id}-tb.jpg`)
- [x] Store processed images with new folder structure (`media/{profile_id}/0/{media_id}.jpg`)
- [x] Implement advanced image compression (progressive JPEG, chroma subsampling)
- [x] Set media status to READY (OK) on successful processing
- [x] Set media status to ERROR on processing failure
- [x] Implement CloudFront cache invalidation
- [x] Add CloudFront wildcard signed URL generation with 2-hour expiry
- [ ] Implement retry mechanism for failed processing

### Infrastructure & Security
- [x] Enhanced S3 bucket policies for security
- [x] Restricted CORS to specific domains
- [x] Implemented S3 lifecycle policies for incomplete uploads
- [x] CloudWatch logging for API Gateway access and execution logs
- [ ] Configure S3 event notifications for processing triggers
- [ ] Set up CloudFront distribution with wildcard signed URL authentication
- [ ] Write unit tests
- [ ] Write integration tests
- [ ] Implement security headers for CloudFront responses

### Documentation
- [x] Updated media-management.md with new workflow
- [x] Documented CloudFront wildcard signed URL implementation
- [x] Updated API documentation to reflect obsolete endpoints
- [ ] Add examples for error handling scenarios

## Testing Strategy

### Unit Tests
- Upload request validation (including edge cases for metadata and extensions)
- Media ID allocation and activation
- S3 presigned URL generation
- Error handling scenarios (invalid formats, sizes, extensions)
- File extension validation
- Batch reordering logic

### Integration Tests
- End-to-end upload flow
- S3 operations (upload, delete, lifecycle policies)
- DynamoDB operations (create, update, delete)
- Profile ownership validation
- CloudFront wildcard signed URL authentication
- S3 event notification triggers

### Load Tests
- Concurrent upload handling (test for 100 simultaneous uploads)
- Media ID allocation performance
- S3 throughput limits
- CloudFront caching performance

### Security Tests
- Test for unauthorized profile access
- Validate presigned URL restrictions (user/profile isolation)
- Test malicious file uploads (invalid magic numbers)
- Verify encryption enforcement
