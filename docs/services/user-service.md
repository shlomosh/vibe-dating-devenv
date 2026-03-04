# User Service - ID Hashing & Management

This document explains how Telegram user IDs are converted into Vibe user IDs using a deterministic hashing process.

## Overview

The system uses a two-step process to convert Telegram user IDs into Vibe user IDs:
1. Create a platform-specific identifier string
2. Hash the string using UUID v5 and convert to Base64

## Implementation

### Step 1: Platform Identifier Creation

```python
platform = 'telegram'  # Platform identifier for Telegram
platform_id = telegram_user.id  # The Telegram user ID
platform_id_string = f"{platform}:{platform_id}"
```

This creates a string in the format: `telegram:123456789` where:
- `telegram` is the platform identifier for Telegram
- `123456789` is the actual Telegram user ID

### Step 2: Hashing Process

The platform identifier string is then hashed using the following process:

```python
def hash_string_to_id(platform_id_string: str) -> str:
    """
    Convert platform ID string to Vibe user ID using UUID v5

    Args:
        platform_id_string: String in format "telegram:123456789"
        length: Length of the final user ID (default: 8)

    Returns:
        str: Base64 encoded user ID
    """
    # Get UUID namespace from AWS Secrets Manager
    uuid_namespace_arn = os.environ.get("UUID_NAMESPACE_SECRET_ARN")
    if not uuid_namespace_arn:
        raise Exception("UUID_NAMESPACE_SECRET_ARN environment variable not set")

    uuid_namespace = get_secret_from_aws_secrets_manager(uuid_namespace_arn)
    if not uuid_namespace:
        raise Exception("Failed to retrieve UUID namespace from Secrets Manager")

    # Create UUID v5 with namespace from Secrets Manager
    namespace_uuid = uuid.UUID(uuid_namespace)
    user_uuid = uuid.uuid5(namespace_uuid, platform_id_string)

    # Convert UUID to base64
    uuid_bytes = user_uuid.bytes
    base64_string = base64.b64encode(uuid_bytes).decode("utf-8")

    # Remove padding and return first N characters
    return base64_string.rstrip("=")[:core_settings.record_id_length]
```

#### UUID v5 Generation
- Uses UUID v5 algorithm with a namespace UUID retrieved from AWS Secrets Manager
- Input: The platform identifier string (e.g., `telegram:123456789`)
- Output: A deterministic UUID

#### Base64 Conversion
```python
# Convert UUID to base64
uuid_bytes = user_uuid.bytes
base64_string = base64.b64encode(uuid_bytes).decode("utf-8")

# Remove padding and return first N characters
return base64_string.rstrip("=")[:core_settings.record_id_length]
```

This converts the UUID to Base64 by:
1. Converting UUID to bytes
2. Converting bytes to Base64 using `base64.b64encode()`
3. Removing padding characters (`=`)
4. Taking the first N characters (default: 8)

### Step 3: Final User ID

The final Vibe user ID is created by taking the first 8 characters of the Base64 string:

```python
user_id = hash_string_to_id(platform_id_string)
// Result: e.g., "aB3cD4eF"
```

## Example

```python
# Input
telegram_user = {"id": 123456789}

# Process
platform = 'telegram'
platform_id = telegram_user["id"]
platform_id_string = f"{platform}:{platform_id}"  # "telegram:123456789"
user_id = hash_string_to_id(platform_id_string)  # e.g., "aB3cD4eF"

# Output
print(user_id)  # 8-character Base64 string
```

## Key Properties

1. **Deterministic**: The same Telegram user ID will always produce the same Vibe user ID
2. **Collision Resistant**: Uses UUID v5 with a namespace from AWS Secrets Manager to minimize collisions
3. **Compact**: Final user ID is only 8 characters long
4. **Platform Agnostic**: The same process can be used for other platforms by changing the platform identifier
5. **Secure**: UUID namespace is stored in AWS Secrets Manager for enhanced security

## Dependencies

- `uuid`: For generating deterministic UUIDs
- `base64`: For Base64 encoding
- `boto3`: For AWS Secrets Manager integration
- AWS Secrets Manager: For storing the UUID namespace securely

## Security Considerations

- The namespace UUID is stored in AWS Secrets Manager and retrieved at runtime
- The process is deterministic, so the same input will always produce the same output
- The 8-character limit provides 48 bits of entropy (6 bits per character)
- Consider increasing the ID length if higher collision resistance is needed
- AWS Secrets Manager provides automatic encryption and access control for the namespace UUID 