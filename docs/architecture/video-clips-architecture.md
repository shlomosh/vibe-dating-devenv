# Video Clips Architecture (Profile and Post Media)

This document defines the end-to-end design for short video clips in profile and post media: product rules, data flow, backend processing, frontend UX, and operations.

---

## 1. Scope and Goals

- **Clip duration**: Final clip is **5 seconds** (or less if the uploaded video is shorter). The backend always uses the **first** 5 seconds; no user-selected segment.
- **Display aspect ratio**: **3:4** (e.g. 720×960). The backend **center-crops** the video to 3:4 (no user-selected crop/zoom).
- **Contexts**: Profile media and post media.
- **Formats**: Frontend and backend support **MP4, MOV, and QuickTime**. Backend converts all to **MP4** (H.264 + AAC) for storage and playback.
- **Flow**: Upload → backend processing (first 5s, center 3:4 crop, transcode) → CDN → playback in feed with autoplay on scroll.

---

## 2. Requirements

### Functional

- Users upload a clip from device gallery/camera for profile or post.
- **Frontend**: On video selection, show a simple preview (optional) and an upload action. No trim or crop editing.
- **Backend**: Accept any supported video; use the **first 5 seconds** (or full duration if &lt; 5s); **center-crop** to 3:4; transcode to H.264/MP4.
- Feed cards autoplay visible clips (muted, inline, looped).

### Non-Functional

- Backward compatible with existing image records and clients.
- Processing is idempotent and resilient to retries.
- CDN caching and signed access unchanged.
- Mobile performance remains smooth in Telegram WebView.

---

## 3. End-to-End Flow

### 3.1 Upload (Frontend → API → S3)

1. User selects a video file (MP4, MOV, QuickTime).
2. Frontend may show a simple preview (e.g. first 5s in a 3:4 frame) and an Upload button; no trim/crop controls.
3. Frontend calls `POST /profile/{profileId}/media` with:
   - `mediaType` (e.g. `video/mp4`, `video/quicktime`).
   - `mediaSize`, `mediaBlob` (base64 JSON), `mediaAssociation`.
4. **mediaBlob** for video: `mediaClass: "video"` (and optionally `sourceDurationMs` for logging). No trim or crop parameters.
5. Backend validates format/size, returns presigned POST.
6. Frontend uploads file to `uploads/.../{mediaId}.{ext}`.
7. Backend stores media record with `properties` = decoded mediaBlob.
8. S3 event triggers processing Lambda.

### 3.2 Processing (S3 → Lambda)

1. Parse S3 key; identify media as video by extension (mp4, mov, quicktime).
2. Mark record `processing`.
3. **FFprobe**: Read duration and dimensions. Allow source duration &gt; 5s.
4. **Trim**: Always use the **first 5 seconds** (or full duration if shorter). No parameters from frontend.
5. **Crop**: Always **center-crop** to 3:4 (720×960). No pan/zoom parameters.
6. **FFmpeg**: Trim from start (0 to min(5s, source duration)), scale/crop to 720×960, transcode to H.264 + AAC, strip metadata.
7. Generate poster and thumbnail; upload to `media/...`.
8. Update DynamoDB (status `ready`, URLs, dimensions, durationMs); invalidate CloudFront; delete upload object.

On failure: set status `error`, store error code, log with request ID.

### 3.3 Serving

- Private S3 + CloudFront OAC + signed access.
- Serve: `media/{profileId}/{bin}/{mediaId}.mp4`, `...-poster.jpg`, `...-tb.jpg`.
- Long TTL for immutable keys.

### 3.4 Viewing (Frontend)

- Unified media slide: image or video by `mediaClass`.
- Feed autoplay: one active clip at a time; play when visibility ≥ 60%, pause when &lt; 30%.
- `<video>` uses `muted`, `loop`, `playsInline`, `poster`, `preload="metadata"`.

---

## 4. Data Model

### Backend MediaRecord

- `mediaClass`: `image` | `video`.
- `posterUrl`: video poster URL.
- `durationMs`: clip duration in ms.
- `properties`: stores mediaBlob from create (e.g. `mediaClass`; no trim/crop).

### Frontend types

- Media record: `mediaClass`, `urlPoster`, `durationMs`.
- URL resolution: for video use `.mp4` and `-poster.jpg` / `-tb.jpg`; for image use `.jpg` / `-tb.jpg`.

### API contract (video create)

**mediaBlob (video)**:

- `mediaClass`: `"video"`.
- `sourceDurationMs`: optional (for logging); not used for processing.

No trim or crop fields.

---

## 5. Backend Design

### 5.1 Settings (`core/settings.py`)

- `video_clips_enabled`, `video_max_file_size`, `video_allowed_formats`: `["mp4", "mov", "quicktime"]`.
- `video_max_duration_seconds`: 5 (output clip length).
- `video_target_width`, `video_target_height`: 720, 960 (3:4).

### 5.2 Processing Lambda (`user_media_processing`)

- **process_video**:
  - Download object (any supported video format).
  - FFprobe (with timeout); allow source duration &gt; 5s.
  - **Trim**: from 0 to `min(5, source_duration)` seconds.
  - **Crop**: center-crop to 720×960 (no pan/zoom).
  - Transcode to MP4 (H.264 + AAC), `-movflags +faststart`, strip metadata.
  - Extract poster; generate thumbnail; upload artifacts; update record; invalidate; delete upload.
- **Formats**: FFmpeg reads MP4, MOV, QuickTime; output always `.mp4`.

---

## 6. Frontend Design

### 6.1 Video upload flow

- User selects video file → optional simple preview (e.g. video in 3:4 container with `object-cover` to suggest center crop) → Upload.
- No trim or crop controls; backend applies first 5s and center 3:4 crop.
- File input `accept`: `image/*,video/mp4,video/quicktime`.

### 6.2 Playback

- `VideoClipPlayer`: muted, loop, playsInline, poster; play when active (visibility), pause when not.
- URL resolution uses `mediaClass` for correct extension (mp4, poster, tb).

---

## 7. Validation and Security

- **Format**: Backend allowlist mp4, mov, quicktime; reject others. All outputs MP4.
- **Size**: Enforce `video_max_file_size`; presigned POST conditions include Content-Type and content-length-range.
- **Metadata**: Strip in FFmpeg (`-map_metadata -1`, `-map_chapters -1`).

---

## 8. Reliability and Operations

- DLQ for processing Lambda; alarm on depth.
- Structured error codes in media record for UX.
- Idempotency: if record already `ready`, skip reprocessing.

---

## 9. Rollout and Compatibility

- Feature flag `video_clips_enabled`.
- Existing records without `mediaClass` treated as image.

---

## 10. Out of Scope (Current Phase)

- Audio-enabled playback UX.
- HLS/DASH.
- User-selectable trim or crop.

This document is the single reference for video clips behaviour and implementation.
