# Profile Management Backend

## Overview

The Profile Management Backend provides comprehensive CRUD operations for user profiles in the Vibe Dating application. It handles profile creation, updates, retrieval, and deletion with strong validation and security controls.

## Profile Management Scheme

The system uses a dynamic profile allocation approach where:

- **User Record**: Contains `profileIds` (list of profile IDs with DB records) and `activeProfileId` (most recently used profile)
- **Profile Creation**: Frontend sends profile record without profile ID, backend generates new profile ID and adds to `profileIds`
- **Profile Update**: Frontend sends profile record with existing profile ID, backend updates record and sets as `activeProfileId`
- **Profile Deletion**: Backend removes profile ID from `profileIds` and updates `activeProfileId` to first remaining profile (or null if none)
- **Profile Limit**: Enforced at backend level (max 3 profiles per user via `CoreSettings().max_profiles_count`)

## Implementation Status

✅ **Fully Implemented**:
- Profile CRUD operations with dynamic ID allocation
- Comprehensive data validation using msgspec
- Authentication and authorization
- DynamoDB storage with transactions
- Profile ownership verification
- Profile limit enforcement (max 3 profiles per user)
- Active profile tracking
- Media management integration
- Location tracking integration
- Signed URL generation for media access

✅ **Completed Features**:
- Media upload and processing pipeline
- Location-based services
- Feed/discovery functionality

## Architecture

### Service Location
- **Module**: User Service (`src/services/user/`)
- **Handler**: `aws_lambdas/user_profile_mgmt/lambda_function.py`
- **API Gateway**: `/profile/{profileId}` endpoints
- **Data Layer**: `src/common/aws_lambdas/core/profile_utils.py`

### Data Models

#### ProfileRecord Structure

```python
class ProfileRecord(msgspec.Struct):
    """Profile record validation using msgspec - matches frontend interface"""
    profileName: Optional[str] = None
    nickName: Optional[str] = None
    aboutMe: Optional[str] = None
    age: Optional[str] = None
    sexualPosition: Optional[SexualPosition] = None
    bodyType: Optional[BodyType] = None
    eggplantSize: Optional[EggplantSizeType] = None
    peachShape: Optional[PeachShapeType] = None
    healthPractices: Optional[HealthPracticesType] = None
    hivStatus: Optional[HivStatusType] = None
    preventionPractices: Optional[PreventionPracticesType] = None
    hosting: Optional[HostingType] = None
    travelDistance: Optional[TravelDistanceType] = None
    # Media management
    mediaIds: list[str] = msgspec.field(default_factory=list)
    mediaRecords: Dict[str, Dict[str, Any]] = msgspec.field(default_factory=dict)
    # Location and activity tracking
    lastLocation: Optional[LocationRecord] = None
    lastSeen: Optional[int] = None
    # TTL for data expiration
    ttl: Optional[int] = None
```

### Available Enums

#### Sexual Preferences
```python
class SexualPosition(str, Enum):
    BOTTOM = "bottom"
    VERS_BOTTOM = "versBottom"
    VERS = "vers"
    VERS_TOP = "versTop"
    TOP = "top"
    SIDE = "side"
    BLOWER = "blower"
    BLOWIE = "blowie"
```

#### Physical Attributes
```python
class BodyType(str, Enum):
    PETITE = "petite"
    SLIM = "slim"
    AVERAGE = "average"
    FIT = "fit"
    MUSCULAR = "muscular"
    STOCKY = "stocky"
    CHUBBY = "chubby"
    LARGE = "large"

class EggplantSizeType(str, Enum):
    SMALL = "small"
    AVERAGE = "average"
    LARGE = "large"
    EXTRA_LARGE = "extraLarge"
    GIGANTIC = "gigantic"

class PeachShapeType(str, Enum):
    SMALL = "small"
    AVERAGE = "average"
    BUBBLE = "bubble"
    SOLID = "solid"
    LARGE = "large"
```

#### Health & Safety
```python
class HealthPracticesType(str, Enum):
    CONDOMS = "condoms"
    BB = "bb"
    CONDOMS_OR_BB = "condomsOrBb"
    NO_PENETRATIONS = "noPenetrations"

class HivStatusType(str, Enum):
    NEGATIVE = "negative"
    POSITIVE = "positive"
    POSITIVE_UNDETECTABLE = "positiveUndetectable"

class PreventionPracticesType(str, Enum):
    NONE = "none"
    PREP = "prep"
    DOXYPEP = "doxypep"
    PREP_AND_DOXYPEP = "prepAndDoxypep"
```

#### Logistics
```python
class HostingType(str, Enum):
    HOST_AND_TRAVEL = "hostAndTravel"
    HOST_ONLY = "hostOnly"
    TRAVEL_ONLY = "travelOnly"

class TravelDistanceType(str, Enum):
    NONE = "none"
    BLOCK = "block"
    NEIGHBOURHOOD = "neighbourhood"
    CITY = "city"
    METROPOLITAN = "metropolitan"
    STATE = "state"
```

## API Endpoints

### POST /profile

**Purpose**: Create a new profile

**Authentication**: JWT Bearer token required

**Request Body**: ProfileRecord fields (profileId is auto-generated)

**Response**:
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
    "lastSeen": 1704110400
  },
  "created": true
}
```

### GET /profile/{profileId}

**Purpose**: Retrieve a specific profile by ID with media access

**Authentication**: JWT Bearer token required

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
    "media": {"media_id_1": {"status": "ready", "fileSize": 2048576, "dimensions": {"width": 1920, "height": 1080}}, "media_id_2": {"status": "ready", "fileSize": 1536000, "dimensions": {"width": 1440, "height": 1920}}, "media_id_3": {"status": "processing", "fileSize": 3072000, "dimensions": {"width": 800, "height": 600}}, "media_id_4": {}, "media_id_5": {}}
    "mediaSignedUrl": {
      "url": "https://media.vibe-dating.io/media/profile_id/0/*?Expires=1704214800&Signature=abc123def456...&Key-Pair-Id=APKABC123DEFGHIJKLMN",
      "expiresAt": "2024-01-02T13:00:00Z"
    }
  },
}
```

**Note**: The `mediaSignedUrl` object is included when requesting a profile. The CloudFront wildcard signed URL provides access to all media files under the profile's path (e.g., `/media/{profileId}/*`). Access control is enforced at the CDN level through the signed URL, which is scoped to the requested profile ID. The URL is valid for the duration specified in `CoreSettings().media_cache_ttl` to enable browser caching.

### PUT /profile/{profileId}

**Purpose**: Update an existing profile

**Authentication**: JWT Bearer token required

**Request Body**: Any subset of ProfileRecord fields

**Response**:
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
    "media": {"media_id_1": {"status": "ready", "fileSize": 2048576, "dimensions": {"width": 1920, "height": 1080}}, "media_id_2": {"status": "ready", "fileSize": 1536000, "dimensions": {"width": 1440, "height": 1920}}, "media_id_3": {"status": "processing", "fileSize": 3072000, "dimensions": {"width": 800, "height": 600}}, "media_id_4": {}, "media_id_5": {}}
  },
  "created": false
}
```

### DELETE /profile/{profileId}

**Purpose**: Delete a profile and associated media

**Authentication**: JWT Bearer token required

**Response**:
```json
{}
```

## Implementation Details

### ProfileManager Class

```python
class ProfileManager(CommonManager):
    def upsert(self, profile_id: str, profile_record: Dict[str, Any]) -> bool
    def delete(self, profile_id: str) -> bool
    def get(self, profile_id: str) -> Dict[str, Any]
    def validate_profile_record(self, profile_record: Dict[str, Any]) -> ProfileRecord
    def validate_profile_id(self, profile_id: str, is_existing: bool = False) -> bool
    def _update_user_profile_tracking(self, profile_id: str, action: str) -> bool
```

### ProfileRecord Class

```python
class ProfileRecord(msgspec.Struct):
    """Profile record validation using msgspec - matches frontend interface"""
    # ... field definitions with validation ...

    def __post_init__(self):
        """Additional validation after struct creation"""
        # Validate and strip string fields
        # Validate media format and length

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Optional["ProfileRecord"]:
        """
        Convert profile data to ProfileRecord and back to dict to ensure only valid fields

        Args:
            profile_data: Raw profile data from database

        Returns:
            ProfileRecord fields with proper validation
        """

    def to_dict(self) -> dict:
        """
        Convert ProfileRecord to dict
        """
```

### UserManager Class

```python
class UserManager(CommonManager):
    def add_profile_id(self, profile_id: str) -> bool
    def remove_profile_id(self, profile_id: str) -> bool
    def set_active_profile_id(self, profile_id: str) -> bool
```

### Data Storage

**DynamoDB Table**: `vibe-dating-{environment}`

**Primary Record Pattern**:
```
PK: "PROFILE#{profileId}"
SK: "METADATA"
```

**User-Profile Lookup Pattern**:
```
PK: "USER#{userId}"
SK: "PROFILE#{profileId}"
```

### Validation & Security

#### Input Validation
- **msgspec**: Strongly typed validation for all profile fields
- **Enum Validation**: All categorical fields validated against predefined enums
- **Media Limits**: Maximum 5 media items per profile (via `CoreSettings().max_medias_per_profile`)
- **Response Filtering**: ProfileRecord validation ensures only valid fields are returned in API responses using `ProfileRecord.from_dict()` and `to_dict()` methods

#### Access Control
- **JWT Authentication**: All endpoints require valid JWT token
- **Profile Ownership**: Users can only modify their own profiles
- **User-Profile Validation**: Ensures profile belongs to authenticated user

#### Data Integrity
- **DynamoDB Transactions**: Atomic operations for create/delete
- **Optimistic Locking**: Prevents concurrent modification conflicts
- **Relationship Consistency**: User-profile relationships maintained automatically

## Error Handling

### Standard Error Response
```json
{
  "error": "Error message",
  "error_code": "ERROR_CODE",
  "details": {
    "field": "Additional error details"
  }
}
```

### Common Error Codes
- `400 Bad Request`: Invalid request data or validation failure
- `401 Unauthorized`: Missing or invalid JWT token
- `403 Forbidden`: User doesn't own the profile
- `404 Not Found`: Profile doesn't exist
- `422 Unprocessable Entity`: Data validation error
- `500 Internal Server Error`: Server error

## Media Integration (Planned)

The profile system is designed to integrate with the media service for image handling:

### Planned Features
- **S3 Presigned URLs**: Direct client-to-S3 upload
- **Automatic Processing**: Thumbnail generation and optimization
- **CDN Delivery**: CloudFront distribution for fast image delivery
- **Image Validation**: Format, size, and content validation
- **Processing Pipeline**: Async image processing with status tracking

### Storage Architecture
```
Profile Images (planned):
PK: "PROFILE#{profileId}"     SK: "MEDIA#{mediaId}"
PK: "UPLOAD#{mediaId}"        SK: "PENDING"
```

## Performance Considerations

- **Single-Item Operations**: O(1) profile retrieval by ID
- **Batch Operations**: Support for querying multiple profiles efficiently
- **Caching**: DynamoDB DAX for sub-millisecond response times
- **Pagination**: Built-in support for large result sets
- **Indexes**: GSI for user-to-profile lookups

## Testing Strategy

### Unit Tests
- Profile validation logic
- CRUD operations
- Error handling
- Security controls

### Integration Tests
- End-to-end API workflows
- DynamoDB operations
- JWT authentication
- Cross-service communication

## Configuration

### Environment Variables
```python
# DynamoDB Configuration
DYNAMODB_TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# JWT Configuration
JWT_SECRET_ARN = os.environ.get("JWT_SECRET_ARN")

# CloudFront Configuration
CLOUDFRONT_DOMAIN = os.environ.get("CLOUDFRONT_DOMAIN")
CLOUDFRONT_KEY_PAIR_ID_ARN = os.environ.get("CLOUDFRONT_KEY_PAIR_ID_ARN")
CLOUDFRONT_PRIVATE_KEY_ARN = os.environ.get("CLOUDFRONT_PRIVATE_KEY_ARN")

# Profile Limits (via CoreSettings)
MAX_PROFILES_COUNT = 3  # Maximum profiles per user
MAX_MEDIAS_PER_PROFILE = 5  # Maximum media items per profile
```

## Monitoring & Observability

### CloudWatch Metrics
- Request volume and latency
- Error rates by endpoint
- DynamoDB performance metrics
- Lambda function duration and memory usage

### CloudWatch Logs
- **Access Logs**: `/aws/apigateway/${ApiGatewayId}/access-logs` - API Gateway access patterns and client information
- **Execution Logs**: `/aws/apigateway/${ApiGatewayId}/execution-logs` - Detailed request/response logging
- **Retention**: 30 days for both log groups
- **Tags**: Environment and Service tagging for cost allocation

### Logging
- Structured JSON logging
- Request/response correlation IDs
- User action audit trails
- Error context and stack traces

### Alerts
- High error rate alerts
- Performance degradation alerts
- DynamoDB throttling alerts
- Lambda timeout alerts
