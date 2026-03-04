# Frontend Media Access Guide - CloudFront with Wildcard Signed URLs for Swiper

## Overview

This document explains how the frontend application can securely access profile images through CloudFront CDN using a single wildcard signed URL for all media items under a profile’s path, optimized for Swiper integration and browser caching. The Vibe Dating application uses a secure media delivery system that provides a single signed URL per profile, cached in memory on the `ProfileRecord` object, to access all associated media, enabling browser caching and seamless use with Swiper's `<img>` tags.

## Architecture Overview

### Media Storage & Delivery Flow

```
Frontend → API Gateway → Lambda → Wildcard Signed URL Generation → CloudFront CDN → S3 Bucket
```

1. **S3 Storage**: Images are stored in S3 with structured paths.
2. **CloudFront CDN**: Serves images with caching and global distribution.
3. **Wildcard Signed URLs**: Provide authenticated access to all media items under a profile’s path (e.g., `/media/{profileId}/*`) via URL query parameters.
4. **API Gateway**: Manages authentication and wildcard signed URL generation.

### Media URL Structure

Images are accessed through CloudFront using a single wildcard signed URL, with specific image URLs constructed by the frontend:

```
https://{cloudfront-domain}/media/{profile_id}/*?Expires={timestamp}&Signature={signature}&Key-Pair-Id={key-pair-id}
```

**Example URLs**:
- Wildcard Signed URL: `https://d1234567890.cloudfront.net/media/aB3cD4eF/*?Expires=1704214800&Signature=abc123def456...&Key-Pair-Id=APKABC123DEFGHIJKLMN`
- Constructed Original: `https://d1234567890.cloudfront.net/media/aB3cD4eF/xY9wV8uT.jpg?Expires=1704214800&Signature=abc123def456...&Key-Pair-Id=APKABC123DEFGHIJKLMN`
- Constructed Thumbnail: `https://d1234567890.cloudfront.net/media/aB3cD4eF/xY9wV8uT-tb.jpg?Expires=1704214800&Signature=abc123def456...&Key-Pair-Id=APKABC123DEFGHIJKLMN`

## Authentication Flow

### Step 1: Get Profile Data with Wildcard Signed URL

Get profile data and a single wildcard signed URL for accessing all media under the requested profile.

```javascript
// GET /profile/{profileId} - Returns profile + wildcard signed URL for profile media
const response = await fetch('/profile/aB3cD4eF', {
  headers: {
    'Authorization': `Bearer ${jwtToken}`
  }
});

const data = await response.json();
console.log(data.profile.media); // {"xY9wV8uT": {}, "mN5lK3jH": {}}

// Wildcard signed URL is included for profile media access
if (data.signedUrl) {
  console.log('Signed URL received:', data.signedUrl);
  // Store signed URL in ProfileRecord (handled in useMediaAccess hook)
}
```

**Response**:
```json
{
  "profile": {
    "profileId": "aB3cD4eF",
    "userId": "user123",
    "nickName": "Display Name",
    "media": {"xY9wV8uT": {}, "mN5lK3jH": {}},
    // ... other profile fields
  },
  "signedUrl": {
    "url": "https://media.vibe-dating.io/media/aB3cD4eF/*?Expires=1704214800&Signature=abc123def456...&Key-Pair-Id=APKABC123DEFGHIJKLMN",
    "expiresAt": "2024-01-02T13:00:00Z"
  }
}
```

**Note**: The `signedUrl` object is included when requesting a profile, providing a wildcard URL for all media files under the profile’s path (e.g., `/media/aB3cD4eF/*`). Access control is enforced at the CDN level through the signed URL, scoped to the requested profile ID. The URL is valid for 2 hours to enable browser caching.

### Step 2: Construct Image URLs for Swiper

Use the wildcard signed URL stored in `ProfileRecord` to construct specific image URLs for Swiper’s `<img>` tags:

```javascript
const getImageUrl = (signedUrl, mediaId, isThumbnail = false) => {
  if (!signedUrl) return null;
  const suffix = isThumbnail ? '-tb' : '';
  return signedUrl.url.replace('*', `${mediaId}${suffix}.jpg`);
};
```

## Complete Implementation Example

Here's a React hook for managing media access with wildcard signed URLs, caching them in memory on `ProfileRecord`:

```javascript
import { useState, useEffect, useCallback } from 'react';

const useMediaAccess = (profileId, setProfileRecord) => {
  const [signedUrl, setSignedUrl] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const requestMediaAccess = useCallback(async () => {
    if (!profileId) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`/profile/${profileId}`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('jwt_token')}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`Failed to get profile: ${response.status}`);
      }

      const data = await response.json();

      // Check if signed URL is included
      if (data.signedUrl) {
        setSignedUrl(data.signedUrl);

        // Update ProfileRecord in memory with signed URL
        setProfileRecord((prev) => ({
          ...prev,
          [profileId]: {
            ...prev[profileId],
            signedUrl: data.signedUrl
          }
        }));

        // Auto-refresh before expiration (23 hours)
        const refreshTime = new Date(data.signedUrl.expiresAt).getTime() - Date.now() - (60 * 60 * 1000); // 1 hour buffer
        if (refreshTime > 0) {
          setTimeout(() => {
            requestMediaAccess();
          }, refreshTime);
        }
      } else {
        setSignedUrl(null);
        // Clear signedUrl from ProfileRecord if none provided
        setProfileRecord((prev) => ({
          ...prev,
          [profileId]: {
            ...prev[profileId],
            signedUrl: null
          }
        }));
      }

    } catch (err) {
      setError(err.message);
      console.error('Profile/media access error:', err);
    } finally {
      setLoading(false);
    }
  }, [profileId, setProfileRecord]);

  useEffect(() => {
    // Use signedUrl from ProfileRecord if available
    setProfileRecord((prev) => {
      const cachedSignedUrl = prev[profileId]?.signedUrl;
      if (cachedSignedUrl && new Date() < new Date(cachedSignedUrl.expiresAt).getTime() - (60 * 60 * 1000)) {
        setSignedUrl(cachedSignedUrl);
      } else {
        requestMediaAccess();
      }
      return prev;
    });
  }, [requestMediaAccess, setProfileRecord]);

  const getImageUrl = useCallback((mediaId, isThumbnail = false) => {
    if (!signedUrl) return null;
    const suffix = isThumbnail ? '-tb' : '';
    return signedUrl.url.replace('*', `${mediaId}${suffix}.jpg`);
  }, [signedUrl]);

  return {
    signedUrl,
    loading,
    error,
    getImageUrl,
    refreshAccess: requestMediaAccess
  };
};

export default useMediaAccess;
```

## Usage in Components with Swiper

```javascript
import React, { useContext } from 'react';
import { Swiper, SwiperSlide } from 'swiper/react';
import 'swiper/css';
import useMediaAccess from './hooks/useMediaAccess';
import { ProfileContext } from './ProfileContext'; // Assuming Context API for ProfileRecord

const ProfileImages = ({ profile }) => {
  const { profileRecord, setProfileRecord } = useContext(ProfileContext);
  const { signedUrl, loading, error, getImageUrl } = useMediaAccess(profile.profileId, setProfileRecord);

  if (loading) return <div>Loading profile and media...</div>;
  if (error) return <div>Error: {error}</div>;

  return (
    <div className="profile-images">
      {signedUrl ? (
        <Swiper spaceBetween={10} slidesPerView={1} pagination={{ clickable: true }}>
          {profile.media.map((mediaId) => (
            <SwiperSlide key={mediaId}>
              <img
                src={getImageUrl(mediaId)}
                alt="Profile"
                onError={(e) => {
                  // Fallback to thumbnail if original fails
                  e.target.src = getImageUrl(mediaId, true) || '/images/profile-placeholder.jpg';
                }}
                style={{ width: '100%', height: 'auto' }}
              />
            </SwiperSlide>
          ))}
        </Swiper>
      ) : (
        <div className="image-placeholder">
          <span>Profile images not available</span>
        </div>
      )}
    </div>
  );
};

export default ProfileImages;
```

## Security Considerations

### Signed URL Security
- **HTTPS Only**: Signed URLs are transmitted over secure connections.
- **Profile-Scoped**: URLs are scoped to a specific profile’s media path (e.g., `/media/{profileId}/*`).
- **JWT Required**: Initial profile request requires valid JWT authentication.
- **Time-Limited**: URLs expire after 2 hours to balance security and caching.

### Access Control
- **Profile-Based**: Access is granted for all media under a profile’s path.
- **JWT Required**: Initial profile request requires valid JWT authentication.
- **Owner-Only**: Signed URLs are only provided for profiles owned by the authenticated user.

### Error Handling
```javascript
const handleImageError = (event, mediaId, profileId) => {
  console.error(`Failed to load image: ${mediaId} for profile: ${profileId}`);

  // Try refreshing signed URL if expired
  if (signedUrl && new Date() > new Date(signedUrl.expiresAt)) {
    requestMediaAccess();
  }

  // Set fallback image
  event.target.src = '/images/profile-placeholder.jpg';
};
```

## Caching Strategy

### Browser Caching
CloudFront is configured to allow browser caching of signed URLs:
- **Signed URLs**: Cached by browsers for up to 2 hours (based on `Expires` parameter).
- **Cache Headers**: CloudFront sets `Cache-Control: max-age=86400` for signed URLs to enable browser caching.
- **Failed Requests**: Not cached.

### In-Memory Caching
Signed URLs are cached in memory on the `ProfileRecord` object to minimize API calls:
- The `signedUrl` is stored as part of the `ProfileRecord` (e.g., in React Context or state).
- The `useMediaAccess` hook checks the `ProfileRecord` for a valid `signedUrl` before making API requests.
- A refresh mechanism automatically updates the `signedUrl` before expiration (with a 1-hour buffer).

## Environment Configuration

Configure CloudFront domains for different environments:

```javascript
const CLOUDFRONT_DOMAINS = {
  development: 'd1dev123456.cloudfront.net',
  staging: 'd1staging789.cloudfront.net',
  production: 'media.vibe-dating.io'
};

const getCloudFrontDomain = () => {
  const env = process.env.NODE_ENV || 'development';
  return CLOUDFRONT_DOMAINS[env];
};
```

## Troubleshooting

### Common Issues

1. **403 Forbidden**: Signed URL expired or invalid.
   - **Solution**: Refresh profile data to get a new signed URL.

2. **Image Load Failures**: Network issues or invalid URLs.
   - **Solution**: Implement retry logic with exponential backoff.

3. **Invalid Signature**: Incorrect signature or key pair ID.
   - **Solution**: Ensure the backend generates valid signed URLs using the correct CloudFront key pair.

### Debug Logging
```javascript
const debugMediaAccess = (profileId, mediaId, url) => {
  console.log('Media Access Debug:', {
    profileId,
    mediaId,
    url,
    timestamp: new Date().toISOString()
  });
};
```

## Implementation Notes

**✅ Wildcard Signed URL Approach for Swiper**: Media access uses a single wildcard signed URL per profile, cached in memory on `ProfileRecord`, enabling browser caching and compatibility with Swiper's `<img>` tags.

**Benefits**:
- **Browser Caching**: Signed URLs are valid for 2 hours, allowing browsers to cache images.
- **Swiper Compatibility**: URLs work directly in `<img src>` tags without custom headers.
- **Simplified Payload**: A single signed URL reduces response size compared to per-media URLs.
- **In-Memory Caching**: Storing signed URLs in `ProfileRecord` minimizes API calls and simplifies persistence management.

**Frontend Changes Required**:
- Update profile fetching to handle a single `signedUrl` object with a wildcard path.
- Store the `signedUrl` in `ProfileRecord` (e.g., via React Context or state).
- Use `getImageUrl` to construct specific image URLs by replacing the wildcard with media IDs.
- Check signed URL expiration and refresh when needed.
- Ensure Swiper slides use cached URLs for performance.

**Security Model**:
- A single wildcard signed URL is provided when requesting a profile.
- Access control is enforced at the CloudFront CDN level via signed URLs.
- URLs are scoped to the specific profile’s media path (e.g., `/media/{profileId}/*`).
- URLs expire after 24 hours for security, with in-memory caching to optimize performance.

**Backend Considerations**:
- The backend must generate a CloudFront signed URL with a wildcard path (e.g., `/media/{profileId}/*`) using the CloudFront key pair.
- Ensure the CloudFront distribution is configured to allow wildcard paths in signed URLs.
- Validate that the signed URL grants access to both original and thumbnail images under the profile’s path.

---

*This document provides a complete guide for implementing secure media access in the frontend using wildcard signed URLs cached in memory on `ProfileRecord`, optimized for Swiper integration and browser caching. The wildcard signed URL system ensures authenticated users can access all their profile’s media with a single URL while leveraging CloudFront's global CDN and browser caching for optimal performance.*

</