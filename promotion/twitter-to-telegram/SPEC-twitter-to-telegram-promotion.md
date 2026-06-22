# Twitter → Telegram Channel Promotion

Specification for `twitter_to_telegram_promotion.py` — a config-driven CLI that downloads media from a shared resource store and publishes content to one or more Telegram channels, with per-post delete control. **Production scheduling** runs on **AWS Fargate** (EventBridge every 6 hours); the CLI is used for manual runs and validation.

---

## 1. Overview

### Purpose

Automate promotional posting to Telegram channels. Each **promotion run** for a channel walks the configured `posts` list in order. For each entry:

1. If `delete_previous` is enabled, delete that entry’s **previous** Telegram message (if any).
2. Post the entry — static text/image, or media from the **resource store**.

When `"resource": "media1"`, the app selects the next available row where `**class == "media1"`** and `**date` is empty**, downloads the item (via the row’s `source` — currently `twitter`), and posts it to Telegram — **video with audio** via `sendVideo`, or **image** via `sendPhoto`. Optional `text` becomes the caption (supports placeholders).

Each resource post consumes **one** row from the shared resource store. Multiple posts may reference the same or different classes.

On any failure (resource load, download, or post), the process **stops immediately** with exit code `1`. There is **no rollback** of messages or CSV rows already committed in the same run.

### Design principles

- **No hardcoded settings** — resource backend, channels, posts, and `chat_id` live in `config.json`.
- **Pluggable resource backend** — v1 uses a single CSV file (`csvfile`); future backends use the same `resource` config shape with a different `type`.
- **Class-based filtering** — one resource file/table; posts select rows by `class` column.
- **Secrets in `.env` only** — bot tokens and Twitter cookies; `config.json` references env var *names* only.
- **Simple CSV (v1)** — load, read, update, save with `pandas`; `date` column tracks when a row was used (empty = available).
- **Extensible `source` column** — each row declares its download backend (`twitter` in v1).
- **Per-post delete control** — `delete_previous` on each `posts` entry independently.

### Non-goals

- SQL / MySQL resource backend (designed for, not implemented).
- Resource `source` values other than `twitter`.
- Scraping tweet text from Twitter.
- Posting Twitter content as MP3 or audio-only.
- Posting multiple media items from one tweet.
- Polls, quizzes, pinning, or Telegram-native scheduling.
- Web UI.
- Concurrent writers to the same resource CSV (single process assumed; see §8).

---

## 2. Confirmed design decisions


| Topic                     | Decision                                                                              |
| ------------------------- | ------------------------------------------------------------------------------------- |
| Resource config           | **Singular `resource`** — `{ "type": "csvfile", "url": "file://…" }`                  |
| Resource backend (v1)     | `**csvfile**` — single CSV at `url`                                                   |
| Resource backend (future) | `**sql**` — same config key, different `type` + connection `url`                      |
| Post resource ref         | `**"resource": "<class>"**` — matches rows where CSV `class` column equals this value |
| Posts list                | `**posts**` per channel                                                               |
| CSV columns               | `url`, `**date**`, `source`, `**class**`                                              |
| Availability              | `**date` empty** = available; **non-empty ISO datetime** = used (when posted)         |
| `chat_id`                 | **Inline in `config.json`** per channel                                               |
| Bot token                 | `**.env` only** via `bot_token_env`                                                   |
| Twitter media             | Video → **MP4 + audio** (`sendVideo`); image tweets → `**sendPhoto`**                 |
| Mid-run failure           | **No rollback** — abort immediately; prior posts in run remain                        |
| CSV schema                | `**validate` fails** if required columns missing — no auto-creation                   |
| `delete_previous`         | **Per entry** in `posts`                                                              |
| `silent`                  | **Per entry** — applies to static and resource posts                                  |
| Manual run                | **`run --channel <key>`** — one full pass over `posts`                                |
| Production scheduler      | **AWS EventBridge Scheduler** → ECS Fargate task every 6 hours (see §5.5)              |
| State persistence         | **`state.json` updated after each successful post entry** (not only at end of run)    |
| Production channels       | **`GayCheckMeOut`** (class `O`), **`GayCheckMyAss`** (class `A`) — see `config.json`    |
| Path resolution           | Relative paths (images, CSV) resolved from **config file directory**                  |


---

## 3. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                  twitter_to_telegram_promotion.py               │
│                  run │ delete │ status │ validate               │
└────────────┬───────────────────────────────┬────────────────────┘
             │                               │
    ┌────────▼────────┐              ┌───────▼────────┐
    │  ConfigLoader   │              │  RunState      │
    │  resource       │              │  state.json    │
    │  channels       │              └───────┬────────┘
    └────────┬────────┘                      │
             │                       ┌───────▼────────┐
    ┌────────▼────────┐              │  PromotionRun  │
    │ ResourceBackend │──────────────│  (per channel) │
    │ csvfile │ sql*  │              └───────┬────────┘
    └─────────────────┘                      │
                              ┌──────────────┼─────────────┐
                    ┌─────────▼────┐  ┌──────▼─────┐ ┌────▼─────────┐
                    │SourceClient  │  │ Telegram   │ │ PostRenderer │
                    │ twitter …    │  │ Client     │ │ (templates)  │
                    └──────────────┘  └────────────┘ └──────────────┘

Production (AWS):
  EventBridge Scheduler (rate 6h) → ECS Fargate task → entrypoint.sh
    → run GayCheckMyAss, run GayCheckMeOut
    → S3 Files mount at /promotion (config, CSV, state, optional app/)
    → Secrets Manager (Telegram + Twitter cookies)

* sql backend — future
```

### Module layout

```
promotion/
├── twitter_to_telegram_promotion.py
├── SPEC-twitter-to-telegram-promotion.md
├── config.json                      # local dev (relative paths)
├── config.fargate.json              # AWS paths for S3 Files mount
├── config.example.json
├── .env                             # gitignored — local secrets
├── state.json                       # gitignored — local run state
├── requirements.txt
├── resources/
│   ├── resources.csv                # shared row store (classes A, D, O, …)
│   └── shoss_screen_capture_anon.jpg
├── lib/
│   ├── config.py
│   ├── resource/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── csvfile.py
│   │   └── seed.py                  # CSV validation helpers
│   ├── run_state.py
│   ├── durable_write.py            # single in-place writes (S3 Files safe)
│   ├── sources/
│   │   └── twitter.py
│   ├── telegram.py
│   ├── media.py
│   ├── promotion.py
│   ├── status.py
│   └── validate.py
├── utils/
│   ├── twitter_downloader.py        # standalone CLI
│   └── telegram_post.py             # standalone CLI
├── downloads/                       # gitignored
└── aws/
    └── fargate/
        ├── Dockerfile
        ├── entrypoint.sh
        ├── deploy.sh
        └── cloudformation/
            └── promotion-fargate.yaml
```

Shared download/post logic lives in `lib/`; standalone scripts in `utils/` remain usable.

---

## 4. Configuration files

### 4.1 Config files

Two config variants share the same schema; only paths differ:

| File | Use |
| ---- | --- |
| `config.json` | Local development — relative paths from `promotion/` |
| `config.fargate.json` | AWS — absolute paths under S3 Files mount `/promotion` |

On deploy, `config.fargate.json` is copied to `s3://<bucket>/config.json` and read by the Fargate task at `/promotion/config.json`.

#### Local example (`config.json`)

Production channels use classes **`O`** (GayCheckMeOut) and **`A`** (GayCheckMyAss). `config.example.json` shows a generic template with placeholder channel keys.

```json
{
  "downloads": {
    "dir": "./downloads",
    "keep_files": true
  },
  "run_state": {
    "path": "./state.json"
  },
  "resource": {
    "type": "csvfile",
    "url": "file://resources/resources.csv"
  },
  "twitter": {
    "auth_token_env": "X_AUTH_TOKEN",
    "ct0_env": "X_CT0"
  },
  "channels": {
    "GayCheckMeOut": {
      "enabled": true,
      "telegram": {
        "bot_token_env": "TELEGRAM_BOT_TOKEN",
        "chat_id": -1003932979730
      },
      "posts": [
        { "resource": "O", "delete_previous": false, "silent": false },
        {
          "text": "Shoss Discrete Gay Dating App\n\n…",
          "image": "resources/shoss_screen_capture_anon.jpg",
          "delete_previous": true
        },
        {
          "text": "https://t.me/BerlinerGay\n\n Gays in Berlin? Join the group.",
          "delete_previous": true
        }
      ]
    },
    "GayCheckMyAss": {
      "enabled": true,
      "telegram": {
        "bot_token_env": "TELEGRAM_BOT_TOKEN",
        "chat_id": -1003766170059
      },
      "posts": [
        { "resource": "A", "delete_previous": false, "silent": false },
        {
          "text": "Shoss Discrete Gay Dating App\n\n…",
          "image": "resources/shoss_screen_capture_anon.jpg",
          "delete_previous": true
        },
        {
          "text": "https://t.me/BerlinerGay\n\n Gays in Berlin? Join the group.",
          "delete_previous": true
        }
      ]
    }
  }
}
```

#### AWS example (`config.fargate.json`)

Same channel/post structure; paths point at the S3 Files mount:

| Setting | Local | Fargate |
| ------- | ----- | ------- |
| `downloads.dir` | `./downloads` | `/tmp/downloads` |
| `downloads.keep_files` | `true` | `false` |
| `run_state.path` | `./state.json` | `/promotion/state/state.json` |
| `resource.url` | `file://resources/resources.csv` | `file:///promotion/resources/resources.csv` |
| Static `image` | `resources/…` | `/promotion/resources/…` |

#### Generic template (`config.example.json`)

Placeholder channels `shoss_en` / `shoss_media` with example classes `media1` / `media2` — useful when bootstrapping a new deployment.

#### Global fields


| Field                    | Required | Description                                                                                     |
| ------------------------ | -------- | ----------------------------------------------------------------------------------------------- |
| `downloads.dir`          | yes      | Where downloaded media files are saved                                                          |
| `downloads.keep_files`   | no       | Default `true`; if `false`, delete file after successful post                                   |
| `run_state.path`         | yes      | Path to per-post message ID state file                                                          |
| `resource`               | yes      | Resource backend configuration (see §4.2)                                                       |
| `twitter.auth_token_env` | yes*     | Env var for Twitter cookie (*required if any `posts` entry uses `resource` or CSV is non-empty) |
| `twitter.ct0_env`        | yes*     | Env var for Twitter CSRF token (*same condition)                                                |


#### Channel fields


| Field                    | Required | Description                                                                                                |
| ------------------------ | -------- | ---------------------------------------------------------------------------------------------------------- |
| `enabled`                | no       | Default `true`; disabled channels skipped by `run` and `validate` (warn)                   |
| `telegram.bot_token_env` | yes      | Env var name for bot token (production uses one `TELEGRAM_BOT_TOKEN` for both channels)     |
| `telegram.chat_id`       | yes      | Telegram channel/group ID (integer or numeric string)                                                      |
| `posts`                  | yes      | Non-empty ordered list of posts (see §4.3)                                                                 |


### 4.2 `resource` (top-level backend config)

Pluggable backend for all promotion media rows. Posts reference a `**class`** value; the backend returns rows from the shared store.

#### v1: `csvfile`

```json
"resource": {
  "type": "csvfile",
  "url": "file://resources/resources.csv"
}
```


| Field  | Required | Description                            |
| ------ | -------- | -------------------------------------- |
| `type` | yes      | `"csvfile"`                            |
| `url`  | yes      | `file://` URI pointing to the CSV path |


**Path resolution:** strip `file://` prefix; resolve relative paths from the **config file directory**; absolute paths used as-is.

#### Future: `sql`

```json
"resource": {
  "type": "sql",
  "url": "mysql://user:pass@host:3306/promotion"
}
```

Expected table schema (equivalent to CSV columns):


| Column   | Description                                                    |
| -------- | -------------------------------------------------------------- |
| `url`    | Resource URL                                                   |
| `date`   | Nullable timestamp — `NULL`/empty = available; set when posted |
| `source` | Download backend (`twitter`, …)                                |
| `class`  | Class tag matched by `"resource": "<class>"` in posts          |


SQL backend is **not implemented in v1**; `validate` rejects unknown `type` values.

#### `ResourceBackend` interface


| Method                                   | Description                                                      |
| ---------------------------------------- | --------------------------------------------------------------- |
| `reload() → None`                        | Re-read from disk (used at run start)                           |
| `select_next(class_name: str) → Row\|None` | First available row for the class, or `None`                  |
| `mark_used(row) → None`                  | Set `date` to current local datetime (ISO); durable in-place save |
| `counts() → dict[str, {pending, used}]`  | Per-class row counts                                            |
| `validate_schema() → list[str]`          | Return list of schema errors (empty if ok)                     |
| `classes_in_store() → set[str]`          | Distinct `class` values present in the store                   |


### 4.3 `posts` entries

An entry is **static** (no `resource` field) or **resource** (`resource` is a **class name string**).

#### Common fields


| Field             | Required | Description                                                                                                 |
| ----------------- | -------- | ----------------------------------------------------------------------------------------------------------- |
| `resource`        | no       | **Class name** — must match a `class` value in the resource store; omit for static posts                    |
| `text`            | no       | Message or caption text (placeholders on resource posts only; caption for both `sendPhoto` and `sendVideo`) |
| `image`           | no       | Local image path, relative to config file directory (*static only*)                                         |
| `delete_previous` | no       | Default `false`                                                                                             |
| `silent`          | no       | Default `false`; sets Telegram `disable_notification` on this message                                       |


#### Entry types


| Type                    | Condition                           | Telegram API                                    |
| ----------------------- | ----------------------------------- | ----------------------------------------------- |
| Static — text           | no `resource`, `text` only          | `sendMessage`                                   |
| Static — image          | no `resource`, `image` only         | `sendPhoto`                                     |
| Static — text + image   | no `resource`, both set             | `sendPhoto` (caption = `text`)                  |
| Resource — media        | `"resource": "<class>"`, no `text`  | `sendVideo` or `sendPhoto` (by downloaded type) |
| Resource — media + text | `"resource": "<class>"`, `text` set | `sendVideo` or `sendPhoto` with caption         |


#### Validation rules


| Rule            | Detail                                                                                                |
| --------------- | ----------------------------------------------------------------------------------------------------- |
| Static entry    | At least one of `text` or `image`; `resource` must be absent (not empty string)                       |
| Resource entry  | `resource` is a non-empty string; `image` must not be set                                             |
| `posts`         | Non-empty array per channel                                                                           |
| Class existence | `validate` warns if a referenced class has zero rows in the store                                     |
| Pending rows    | `validate` warns if available rows for a class < resource posts referencing that class in the channel |
| Caption length  | Resource `text` and static photo captions ≤ 1024 chars                                                |


#### Text placeholders (resource posts only)

> **Note:** Placeholder names are distinct from the CSV `**date`** column. `{post_date}` is the time of posting; the CSV `date` column stores when a row was consumed.


| Placeholder       | Value                                            |
| ----------------- | ------------------------------------------------ |
| `{url}`           | URL from selected row                            |
| `{tweet_id}`      | Numeric ID parsed from URL (twitter rows)        |
| `{channel}`       | Channel key                                      |
| `{class}`         | Class name from post’s `resource` field          |
| `{post_date}`     | Local date at post time (`YYYY-MM-DD`)           |
| `{post_datetime}` | Local datetime at post time (`YYYY-MM-DD HH:MM`) |


Static posts: literal text only (no placeholder expansion).

#### Example: mixed posts, two classes

```json
"posts": [
  {
    "text": "Weekly highlights!",
    "image": "channels/shoss_en/assets/banner.png",
    "delete_previous": true
  },
  {
    "resource": "media1",
    "text": "Clip A 🎬\n{url}",
    "delete_previous": true
  },
  {
    "resource": "media2",
    "delete_previous": false
  }
]
```

Consumes one available `media1` row and one available `media2` row from the shared CSV.

#### `delete_previous` behavior (per entry)

Each entry is identified by its **index** in the `posts` array (0-based).

For entry `i` with `delete_previous: true`:

1. Look up `state.channels.<key>.post_message_ids["i"]`.
2. If set, call `deleteMessage` (log warning on failure; continue).
3. Post new content.
4. Store new `message_id` at `post_message_ids["i"]` and **persist state immediately**.

---

### 4.4 `.env`

```env
X_AUTH_TOKEN=...
X_CT0=...

TELEGRAM_BOT_TOKEN=...
```

Production uses a single bot token for all channels. `config.example.json` may reference per-channel token env names for illustration.

`validate` fails if any referenced env var is missing.

---

### 4.5 Resource file schema (csvfile backend)

Single CSV at the path from `resource.url`.

#### Standard format

```csv
url,date,source,class
https://x.com/user/status/1234567890,,twitter,media1
https://x.com/user/status/2345678901,,twitter,media1
https://x.com/user/status/3456789012,,twitter,media2
https://x.com/user/status/4567890123,2026-06-16T14:30:00,twitter,media1
```


| Column   | Required | Description                                                 |
| -------- | -------- | ----------------------------------------------------------- |
| `url`    | yes      | Resource URL                                                |
| `date`   | yes      | When posted — **empty** = available; ISO datetime when used |
| `source` | yes      | Download backend (`twitter` in v1)                          |
| `class`  | yes      | Class tag — matched by `"resource": "<class>"` in posts     |


`validate` **fails** if any of these columns is missing. Columns are never auto-created.

**Availability:** row is available when `date` is `NaN`, empty string, or whitespace-only.

#### Supported `source` values (v1)


| `source`  | Downloader                                                         | Telegram method            |
| --------- | ------------------------------------------------------------------ | -------------------------- |
| `twitter` | yt-dlp — video: merged MP4 (video + audio); image: best image file | `sendVideo` or `sendPhoto` |


#### CSV lifecycle

```python
import pandas as pd

df = pd.read_csv(path, dtype={"date": "string"})
available = df["date"].isna() | (df["date"].astype(str).str.strip() == "")
row = df[available & (df["class"] == "media1")].iloc[0]

# After successful resource post:
df.loc[row.name, "date"] = pd.Timestamp.now().isoformat(timespec="seconds")
# durable save: write the whole file in place (single open/write/close).
# Do NOT use a temp file + os.replace() — see "Durable writes" note below.
```


| Rule              | Detail                                                                  |
| ----------------- | ----------------------------------------------------------------------- |
| Row selection     | First available row in **file order** matching `class`                  |
| Mark used         | Set `date` immediately after successful resource post; durable save     |
| Failed post       | Row `date` stays empty                                                  |
| No available rows | See §8 (`no_pending_rows` vs partial run)                          |
| Dry run           | Read only; no CSV or state writes                                  |
| Re-post a row     | Operator clears `date` manually                                    |


The DataFrame is loaded once at run start; saved after each successful resource post.

**Concurrency:** only one writer should update the CSV at a time. Do not run overlapping Fargate tasks or parallel manual `run` commands against the same resource file.

#### Durable writes (`resources.csv` and `state.json`)

Both files are saved with a **single in-place write** (open → write whole file → close) via `lib/durable_write.py`. The classic "write a temp file then `os.replace()`" atomic-rename pattern is **deliberately not used**.

Reason: in production these files live on the **S3 Files (NFS-over-S3) mount** at `/promotion`. Renaming onto an existing key surfaces at the S3 object layer as **DELETE + PUT**, so an interrupted save leaves a dangling delete marker and the file silently disappears (and a brand-new file may never durably land). A single open/write/close maps to one atomic `PutObject`, which is the only safe write shape on these mounts. On a normal local filesystem it is likewise a single write — safe for this single-writer, low-frequency workload.

> Exception: video re-mux in `lib/media.py` still uses a temp file + `os.replace()`, because it operates only on `downloads.dir` (local/ephemeral container disk), never on the S3 mount.

---

### 4.6 `state.json` (per-post message IDs)

```json
{
  "version": 5,
  "channels": {
    "shoss_en": {
      "post_message_ids": {
        "0": 4821,
        "1": 4822,
        "2": 4823
      },
      "last_posted_at": "2026-06-16T14:30:00",
      "last_resources": [
        { "class": "media1", "url": "https://x.com/user/status/1234567890", "post_index": 2 }
      ]
    }
  }
}
```


| Field              | Purpose                                                                                |
| ------------------ | -------------------------------------------------------------------------------------- |
| `post_message_ids` | `posts` index (string key) → last successful Telegram `message_id`                     |
| `last_posted_at`   | Updated when **all** entries in a run complete successfully                            |
| `last_resources`   | Class, URL, and post index for each resource post in the last **fully successful** run |


**Persistence:** `post_message_ids` is written after **each** successful entry. `last_posted_at` / `last_resources` are written only when the full `posts` sequence completes without error.

State is written with a **single in-place write** (see "Durable writes" in §4.5) — not temp file + rename.

---

## 5. Operations (CLI)

Run from the `promotion/` directory (or pass `--config` with an absolute path).

```
python twitter_to_telegram_promotion.py [--config PATH] <command> [options]
```


| Flag       | Default         | Description         |
| ---------- | --------------- | ------------------- |
| `--config` | `./config.json` | Path to config file |


#### Exit codes


| Code | Meaning                                                                                                                 |
| ---- | ----------------------------------------------------------------------------------------------------------------------- |
| `0`  | Success; or `no_pending_rows` when the first failing condition is an exhausted resource class at the point it is needed |
| `1`  | Validation error, post/download failure, missing config/env, or `delete` found nothing to delete                        |


---

### 5.1 `run`

```
python twitter_to_telegram_promotion.py run --channel GayCheckMeOut
python twitter_to_telegram_promotion.py run --channel GayCheckMeOut --dry-run
```


| Flag        | Description                                                     |
| ----------- | --------------------------------------------------------------- |
| `--channel` | **Required.** Channel key from `config.channels`                |
| `--dry-run` | Print planned actions; no download, post, CSV, or state changes |


**Flow:**

```
run --channel X
  │
  ├─ Load config + env + state; skip if channel disabled
  ├─ Init ResourceBackend; reload CSV
  │     └─ on load/parse error → exit 1
  ├─ For each entry i in posts (in order):
  │     ├─ If dry-run → log planned action; continue
  │     ├─ If delete_previous → delete post_message_ids[i] if set
  │     ├─ If static → sendMessage / sendPhoto (honor silent)
  │     └─ If resource == "<class>":
  │           ├─ backend.select_next(class) → row
  │           │     └─ if none → see §8 (no_pending_rows / partial run)
  │           ├─ download by row.source (twitter → see §6)
  │           ├─ render caption placeholders (if text set)
  │           └─ sendVideo or sendPhoto by file type (+ caption; honor silent)
  │     ├─ On success → post_message_ids[i] = message_id; persist state
  │     └─ On resource success → backend.mark_used(row)
  │     └─ On any failure → exit 1 immediately (no rollback)
  ├─ If all entries succeeded → update last_posted_at, last_resources
  └─ Print summary
```

**Success output:**

```
channel=GayCheckMeOut
chat_id=-1003932979730
resources=O:https://x.com/user/status/1234567890
message_ids=4821,4822,4823
posts_sent=3
status=posted
```

Multiple resource posts: comma-separated `resources=<class>:<url>,...`.

---

### 5.2 `delete`

```
python twitter_to_telegram_promotion.py delete --channel GayCheckMeOut
python twitter_to_telegram_promotion.py delete --channel GayCheckMeOut --post-index 2
```


| Flag           | Description                                                                                              |
| -------------- | -------------------------------------------------------------------------------------------------------- |
| `--channel`    | **Required.** Channel key                                                                                |
| `--post-index` | Optional. Delete only that entry’s stored message. If omitted, delete **all** IDs in `post_message_ids`. |


Does **not** clear `date` in the resource CSV. Clears deleted IDs from `post_message_ids` in state on success.

---

### 5.3 `status`

Per channel:

- Each `posts` index: stored `message_id`, `delete_previous`, `resource` class (if any), `silent`

Resource store (global):

- Per-**class** pending (empty `date`) / used (non-empty `date`) counts
- Backend `type` and resolved path

Last run: `last_posted_at`, `last_resources` (if last run fully succeeded)

---

### 5.4 `validate`

- Config JSON loads; at least one enabled channel
- `resource.type` supported (`csvfile` in v1); `resource.url` resolves; CSV exists
- CSV columns: `url`, `date`, `source`, `class` — **all required**; fail if any missing
- All row `source` values supported (v1: `twitter` only)
- Every `"resource": "<class>"` in enabled channels — class has ≥1 row (warn if 0)
- Static/resource entry rules; image paths exist on disk
- Per channel/class: available rows ≥ resource posts referencing that class (warn)
- Twitter env vars set if any resource posts exist
- Bot token env vars set for enabled channels
- Tools on PATH: yt-dlp, gallery-dl; ffmpeg (required for video tweets; warned if missing)
- Python package: pandas

---

### 5.5 AWS production deployment

Scheduled promotion runs on **ECS Fargate** in `us-east-1` (`AWS_PROFILE=vibe-dev`). There is no in-process `cron` CLI command; scheduling is external.

#### Stack

| Item | Value |
| ---- | ----- |
| CloudFormation stack | `shoss-promotion-fargate-dev` |
| Template | `aws/fargate/cloudformation/promotion-fargate.yaml` |
| ECS cluster | `shoss-promotion-dev` |
| Schedule | EventBridge Scheduler — `rate(6 hours)` |
| ECR repo | `shoss-promotion-dev` |
| Logs | `/ecs/shoss-promotion-dev` |
| Secrets | `shoss/promotion/dev/credentials` (JSON: `TELEGRAM_BOT_TOKEN`, `X_AUTH_TOKEN`, `X_CT0`) |

#### S3 bucket + S3 Files

Data lives in **`s3://shoss-promotion/`** (name configurable via `PROMOTION_BUCKET`). The bucket is **created by `deploy.sh`**, not CloudFormation (avoids name-conflict early validation). S3 Files mounts the bucket at **`/promotion`** inside the task.

**Bucket prerequisites** (applied by `deploy.sh` before stack deploy):

- S3 Versioning **enabled** (required by S3 Files)
- SSE-S3 encryption (`AES256`)

**S3 layout:**

```
s3://shoss-promotion/
  config.json              ← from config.fargate.json
  resources/
    resources.csv          ← live state (date column); do not overwrite on redeploy
    shoss_screen_capture_anon.jpg
  app/                     ← optional code overlay (overrides image copy when present)
  state/state.json         ← written by task via S3 Files sync
```

`deploy.sh` syncs resources with `--exclude resources.csv` so redeploys preserve the live CSV. The CSV is seeded only on first deploy when absent in the bucket.

#### Deploy

From WSL (Docker required):

```bash
cd promotion
chmod +x aws/fargate/deploy.sh
AWS_PROFILE=vibe-dev ./aws/fargate/deploy.sh
```

Steps: build/push Docker image → ensure bucket + versioning + encryption → sync config/resources/app to S3 → deploy CloudFormation → update Secrets Manager from local `.env`.

#### Task entrypoint

`aws/fargate/entrypoint.sh` runs each channel sequentially:

1. Prefer code at `/promotion/app/` if present; else use image copy at `/opt/promotion`
2. Read config from `/promotion/config.json`
3. `run --channel GayCheckMyAss`, then `run --channel GayCheckMeOut`
4. Exit `1` if either channel failed (both are attempted)

Override channels via `PROMOTION_CHANNELS` env var.

#### Update without image rebuild

```bash
aws s3 cp config.fargate.json s3://shoss-promotion/config.json
# Do NOT overwrite resources/resources.csv — it holds live posting state
aws s3 sync resources/ s3://shoss-promotion/resources/ --exclude "resources.csv"
```

#### Manual task run

Use the `RunTaskCommand` output from the stack, or:

```bash
aws ecs run-task --cluster shoss-promotion-dev \
  --task-definition shoss-promotion-dev \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[...],securityGroups=[...],assignPublicIp=ENABLED}"
```

#### Logs

```bash
aws logs tail /ecs/shoss-promotion-dev --follow
```

---

## 6. Download behavior by `source`

### `twitter` (v1)

Twitter media needs **two** downloaders, because yt-dlp's Twitter extractor handles **only video/GIF** — it cannot download still photos (it errors `No video could be found in this tweet`). The downloader tries video first, then falls back to images:

1. **Video** → `yt-dlp` (merges video + audio to MP4).
2. **Image** → if yt-dlp reports no video, `gallery-dl` downloads the first photo (authenticated; works for sensitive/adult tweets that the public syndication API tombstones).

Both read auth from a temporary **Netscape cookie file** (`auth_token` + `ct0` under `.x.com` / `.twitter.com`), written from the `twitter.*_env` vars and deleted after the download. This also avoids yt-dlp's "cookies as a header" deprecation warning. After download, media type is detected by file extension / MIME.

#### Video tweets (yt-dlp)


| Setting   | Value                                                            |
| --------- | ---------------------------------------------------------------- |
| Format    | `bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best` |
| Merge     | `--merge-output-format mp4`                                      |
| Extractor | `twitter:legacy_api=true`                                        |
| Auth      | `--cookies <tmpfile>`                                            |
| Output    | `{downloads.dir}/{class}_{tweet_id}.mp4`                         |
| Telegram  | `sendVideo` (with audio when present)                            |


**Requires ffmpeg** for video+audio merge.

#### Image tweets (gallery-dl)


| Setting   | Value                                                |
| --------- | ---------------------------------------------------- |
| Selection | `--range 1` (first media item; multi-image is a non-goal) |
| Auth      | `--cookies <tmpfile>` (dotted-domain cookies required) |
| Output    | `{downloads.dir}/{class}_{tweet_id}.{extension}`     |
| Telegram  | `sendPhoto`                                          |


Image-only tweets are **supported** via gallery-dl. If a tweet has no downloadable media (text-only), both downloaders fail, the row is not marked used, and the process exits with code `1`.

Tweet ID parsed from `x.com` / `twitter.com` status URLs.

---

## 7. Telegram post behavior


| Content                     | API method                 |
| --------------------------- | -------------------------- |
| Text only                   | `sendMessage`              |
| Image (no caption)          | `sendPhoto`                |
| Image + text                | `sendPhoto` with `caption` |
| Resource video (with audio) | `sendVideo`                |
| Resource image (twitter)    | `sendPhoto`                |


`chat_id` from `channels.<key>.telegram.chat_id`. Uses stdlib `urllib` (same approach as `telegram_post.py`).

Caption limit: 1024 characters — fail at validate/post time if exceeded.

---

## 8. Error handling


| Scenario                                    | `run`                                                                                          | Fargate task                  |
| ------------------------------------------- | ---------------------------------------------------------------------------------------------- | ----------------------------- |
| Resource CSV load/parse fails               | Exit 1                                                                                         | Channel fails; task exit 1    |
| Channel disabled                            | Exit 1 with message                                                                            | Skipped (not in entrypoint)   |
| No available rows when resource entry runs  | Exit `0` if **no** posts succeeded yet in this run; exit `1` if earlier entries already posted | Same per channel              |
| `delete_previous` fails                     | Log warning; continue                                                                          | Same                          |
| Static post fails                           | Exit 1 immediately                                                                             | Channel fails                 |
| Resource download/post fails                | Exit 1 immediately; row `date` stays empty                                                     | Same                          |
| CSV/state save fails                        | Log critical; exit 1                                                                           | Same                          |
| Unsupported `resource.type` or row `source` | Fail at `validate`                                                                             | N/A                           |
| Missing CSV columns                         | Fail at `validate`                                                                             | N/A                           |


**No rollback:** on failure, the process stops. Messages already sent and resource rows already marked in the current run **stay as-is**. Operator cleans up manually via `delete --channel` and by clearing CSV `date` if needed.

---

## 9. Example session

```bash
cd promotion
cp config.example.json config.json
# Create .env with TELEGRAM_BOT_TOKEN, X_AUTH_TOKEN, X_CT0

python twitter_to_telegram_promotion.py validate
python twitter_to_telegram_promotion.py status
python twitter_to_telegram_promotion.py run --channel GayCheckMeOut
python twitter_to_telegram_promotion.py run --channel GayCheckMyAss

# Production deploy (see §5.5)
AWS_PROFILE=vibe-dev ./aws/fargate/deploy.sh
```

Example CSV row classes in production: **`A`**, **`D`**, **`O`** (matched by `"resource": "A"` etc. in channel posts).

```csv
url,date,source,class
https://x.com/i/status/2059278577388912765,2026-06-16T23:32:55,twitter,A
https://x.com/i/status/1986073460515467636,,twitter,D
https://x.com/i/status/2031792833351360859,,twitter,O
```

---

## 10. Implementation phases

### Phase 1 — Core (MVP) ✅

- [x] `lib/resource/base.py`, `lib/resource/csvfile.py`
- [x] `lib/config.py` — `file://` resolution, env loading
- [x] `lib/sources/twitter.py`, `lib/telegram.py`, `lib/promotion.py`, `lib/run_state.py`, `lib/validate.py`, `lib/status.py`
- [x] CLI: `validate`, `status`, `run`, `delete`
- [x] `config.example.json`, `config.json`, `config.fargate.json`, `requirements.txt`, `resources/resources.csv`

### Phase 2 — AWS production ✅

- [x] Docker image (`aws/fargate/Dockerfile`) — Python 3.11, ffmpeg, yt-dlp, gallery-dl
- [x] S3 bucket + S3 Files mount + Fargate task (`promotion-fargate.yaml`)
- [x] EventBridge Scheduler every 6 hours
- [x] Secrets Manager for credentials
- [x] `deploy.sh` — build, sync, deploy, preserve live CSV state

### Phase 3 — Hardening

- [ ] `--force-url` / `--class` for manual row selection
- [ ] File lock on CSV for multi-process safety
- [ ] Unit tests: class filter, date availability, image vs video twitter posts, placeholders

### Phase 4 — Optional enhancements

- [ ] `lib/resource/sql.py` (MySQL or other SQL backend)
- [ ] Additional `source` backends (non-twitter)
- [ ] `--reset-url` to clear CSV `date`
- [ ] Structured JSON logging

---

## 11. Resolved decisions


| #   | Question                          | Decision                                                                    |
| --- | --------------------------------- | --------------------------------------------------------------------------- |
| 1   | Auto-rollback on mid-run failure? | **No.** Fail immediately; operator cleans up manually.                      |
| 2   | Image-only tweets?                | **Supported via gallery-dl** (yt-dlp can't fetch Twitter photos); post via `sendPhoto`. |
| 3   | Auto-create missing CSV columns?  | **No.** `validate` fails if `url`, `date`, `source`, or `class` is missing. |


---

## 12. Dependencies


| Dependency        | Purpose                                                        |
| ----------------- | -------------------------------------------------------------- |
| Python 3.11+      | Runtime (local + Docker)                                       |
| pandas            | CSV resource backend (`requirements.txt`)                      |
| yt-dlp            | Twitter **video** download (installed in Docker image; local PATH) |
| gallery-dl        | Twitter **image** download (`requirements.txt`; provides `gallery-dl` on PATH) |
| ffmpeg            | Merge video + audio for **video** tweets (Docker + system)     |
| stdlib (`urllib`) | Telegram Bot API                                               |
| Docker            | Build/push Fargate image                                       |
| AWS CLI v2        | Deploy stack, sync S3, run tasks                               |

---

## 13. Security & gitignore

**Gitignore:** `.env`, `state.json`, `downloads/`

- Bot tokens and Twitter cookies never in logs or `config.json`.
- On AWS, credentials live in **Secrets Manager** (`shoss/promotion/dev/credentials`), injected as container env vars.
- `chat_id` is not secret; safe to commit in private repos.
- Resource CSV may be committed locally; in production the S3 copy is **live state** — do not overwrite on redeploy.
- SQL `resource.url` will contain credentials — use env interpolation or secrets manager when implemented.

---

## Appendix A — Review changelog

Corrections applied during spec review:


| Issue                                               | Fix                                                                                |
| --------------------------------------------------- | ---------------------------------------------------------------------------------- |
| `{date}` placeholder clashed with CSV `date` column | Renamed to `{post_date}` / `{post_datetime}`                                       |
| Cron section truncated ("Same as before")           | Restored flags, scheduler code, behavior table                                     |
| State save timing ambiguous                         | Clarified: per-entry `post_message_ids` immediately; `last_`* only on full success |
| `silent` not applied to static posts in docs        | Documented for all entry types                                                     |
| `dry-run` missing from run flow                     | Added to flow and flags                                                            |
| `no_pending_rows` vs partial run                    | Defined exit 0 vs 1 depending on prior posts in run                                |
| Twitter env vars always required                    | Conditional on resource posts existing                                             |
| Path resolution for images                          | Explicit: relative to config file directory                                        |
| CSV concurrency                                     | Documented single-writer assumption                                                |
| Missing exit codes, delete flags, enabled channels  | Added                                                                              |
| No rollback / fail-fast on resource errors          | Documented in §1, §8, §11                                                          |
| Image-only twitter tweets                           | `sendPhoto` path in §6–§7                                                          |
| CSV columns must exist at validate                  | No auto-creation                                                                   |
| `last_resources` missing post index                 | Added `post_index`                                                                 |
| Missing `.env.example`, `requirements.txt`, cwd     | Added                                                                              |


---

## Appendix B — Fargate deployment changelog

| Issue | Fix |
| ----- | --- |
| CFN `ResourceExistenceCheck` on bucket create | Bucket created by `deploy.sh`; template references existing bucket by name only |
| S3 Files requires versioning | `deploy.sh` enables versioning + SSE-S3 before stack deploy |
| Live CSV state lost on redeploy | `deploy.sh` excludes `resources.csv` from sync; seeds only if missing in S3 |
| In-process cron removed | Scheduling via EventBridge → Fargate; entrypoint runs both channels per task |
| Local vs AWS paths | Split into `config.json` and `config.fargate.json` |
| `resources.csv` / `state.json` vanished on S3 Files | Atomic temp-file + `os.replace()` becomes DELETE+PUT on the mount (dangling delete marker). Replaced with single in-place writes via `lib/durable_write.py` |
| One channel failure skipped the other | `entrypoint.sh` runs each channel independently; task exits 1 only after attempting both |
| `mysql` resource backend | Removed (unused); `csvfile` only, SQL remains a future non-goal |
