# DynamoDB Table Structure & Design

## Overview

The Vibe Dating application uses a single-table DynamoDB design with multiple Global Secondary Indexes (GSIs) to support various query patterns efficiently. This document outlines the table structure, indexes, and design principles.

## Table Configuration

- **Table Name**: `vibe-dating-{environment}` (e.g., `vibe-dating-dev`, `vibe-dating-prod`)
- **Billing Mode**: Pay-per-request (on-demand)
- **Encryption**: KMS encryption enabled
- **Point-in-time Recovery**: Enabled for data protection

## Primary Key Structure

### Hash Key (PK)
- **Attribute Name**: `PK`
- **Type**: String
- **Purpose**: Primary partition key for data distribution

### Sort Key (SK)
- **Attribute Name**: `SK`
- **Type**: String
- **Purpose**: Primary sort key for ordering within partitions

## Global Secondary Indexes (GSI)

The table includes 4 Global Secondary Indexes to support various query patterns:

### GSI1 - Profile Lookup
- **Partition Key**: `GSI1PK`
- **Sort Key**: `GSI1SK`
- **Use Case**: Query all profiles for a specific user
- **Example Queries**:
  - All profiles for a user
  - Profile-user relationships
  - User profile management

### GSI2 - Profile Lookup (Alternative)
- **Partition Key**: `GSI2PK`
- **Sort Key**: `GSI2SK`
- **Use Case**: Reverse lookup from profile to user
- **Example Queries**:
  - Find user from profile ID
  - Profile ownership verification
  - Cross-reference profile data

### GSI3 - Time Lookup
- **Partition Key**: `GSI3PK`
- **Sort Key**: `GSI3SK`
- **Use Case**: Query items by time ranges
- **Example Queries**:
  - Recently updated profiles
  - Last active users
  - Time-based analytics

### GSI4 - Location Lookup
- **Partition Key**: `GSI4PK`
- **Sort Key**: `GSI4SK`
- **Use Case**: Query items by location or geographic criteria
- **Example Queries**:
  - Users in specific geographic areas
  - Location-based matching
  - Geographic analytics



## Data Access Patterns

### 1. User Management
```
PK: USER#{user_id}
SK: METADATA
GSI1PK: USER#{user_id}
GSI1SK: METADATA
GSI2PK: TIME#{date}
GSI2SK: {timestamp}
GSI3PK: LOCATION#DEFAULT
GSI3SK: DEFAULT
```

**Queries**:
- Get user by ID: `GetItem(PK="USER#{user_id}", SK="METADATA")`
- Get user via GSI1: `Query(IndexName="GSI1", GSI1PK="USER#{user_id}")`

### 2. Profile Management
```
PK: PROFILE#{profile_id}
SK: METADATA
GSI1PK: USER#{user_id}
GSI1SK: PROFILE#{profile_id}
GSI2PK: TIME#{date}
GSI2SK: {timestamp}
GSI3PK: LOCATION#DEFAULT
GSI3SK: DEFAULT
```

**Queries**:
- Get profile by ID: `GetItem(PK="PROFILE#{profile_id}", SK="METADATA")`
- Get all profiles for user: `Query(IndexName="GSI1", GSI1PK="USER#{user_id}")`
- Get specific profile for user: `Query(IndexName="GSI1", GSI1PK="USER#{user_id}", GSI1SK="PROFILE#{profile_id}")`

### 3. User-Profile Lookup
```
PK: USER#{user_id}
SK: PROFILE#{profile_id}
profileId: {profile_id}
createdAt: {timestamp}
```

**Queries**:
- Get all profiles for user: `Query(PK="USER#{user_id}", SK="begins_with", "PROFILE#")`
- Get specific profile relationship: `GetItem(PK="USER#{user_id}", SK="PROFILE#{profile_id}")`

### 4. Media Management
```
PK: MEDIA#{media_id}
SK: METADATA
GSI1PK: USER#{user_id}
GSI1SK: MEDIA#{media_id}
```

**Queries**:
- Get media by ID: `GetItem(PK="MEDIA#{media_id}", SK="METADATA")`
- Get all media for user: `Query(IndexName="GSI1", GSI1PK="USER#{user_id}")`

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

## Best Practices

### 1. Key Design
- Use consistent prefixes for entity types
- Ensure hash keys provide good distribution
- Design sort keys for meaningful ordering

### 2. GSI Usage
- Only create GSIs for actual query needs
- Monitor GSI costs and performance
- Use GSI projection to minimize storage

### 3. Query Optimization
- Use primary keys when possible
- Leverage GSIs for alternative access patterns
- Avoid table scans for large datasets

### 4. Data Modeling
- Store related data together
- Use composite keys for complex relationships
- Consider access patterns when designing keys

## Security & Compliance

### 1. Encryption
- **At Rest**: KMS encryption enabled
- **In Transit**: TLS encryption for all connections
- **Key Management**: Centralized KMS key management

### 2. Access Control
- IAM policies control access to table
- Least privilege principle applied
- Audit logging enabled

### 3. Data Protection
- Point-in-time recovery enabled
- Backup and restore capabilities
- Compliance with data protection regulations

## Monitoring & Maintenance

### 1. Performance Metrics
- Monitor read/write capacity
- Track GSI performance
- Watch for hot partition issues

### 2. Cost Optimization
- Monitor on-demand billing
- Optimize GSI usage
- Review access patterns regularly

### 3. Maintenance Tasks
- Regular performance reviews
- GSI optimization
- Data lifecycle management

## Example Queries

### Get User with All Profiles
```python
# Get user data
user = table.get_item(
    Key={"PK": f"USER#{user_id}", "SK": "METADATA"}
)

# Get all profiles for user via GSI1
profiles = table.query(
    IndexName="GSI1",
    KeyConditionExpression="GSI1PK = :user_id",
    ExpressionAttributeValues={":user_id": f"USER#{user_id}"}
)
```

### Get Profile with Media
```python
# Get profile data
profile = table.get_item(
    Key={"PK": f"PROFILE#{profile_id}", "SK": "METADATA"}
)

# Get all media for profile owner via GSI1
media = table.query(
    IndexName="GSI1",
    KeyConditionExpression="GSI1PK = :user_id",
    ExpressionAttributeValues={":user_id": f"USER#{user_id}"}
)
```

### Search Active Users
```python
# Query for active users (assuming GSI2 is used for status)
active_users = table.query(
    IndexName="GSI2",
    KeyConditionExpression="GSI2PK = :status",
    ExpressionAttributeValues={":status": "ACTIVE"}
)
```

## Future Considerations

### 1. Additional GSIs
- Monitor query patterns for new GSI needs
- Consider time-series data requirements
- Plan for analytics and reporting needs

### 2. Performance Optimization
- Implement connection pooling
- Use batch operations where possible
- Consider read replicas for read-heavy workloads

### 3. Scaling Strategy
- Monitor partition growth
- Plan for data archiving
- Consider multi-region deployment

---

*This document should be updated as the DynamoDB structure evolves or new access patterns are identified.*
