"""Durable file writes that work on both local disks and S3-backed mounts.

In the Fargate deployment, resources.csv and state.json live on an S3 Files
(NFS-over-S3) volume. The usual "write a temp file then os.replace()" atomic-save
trick is unsafe there: renaming onto an existing key surfaces at the S3 object
layer as DELETE + PUT, so an interrupted save leaves a dangling delete marker and
the file silently disappears (and a fresh file may never durably land at all).

Writing the destination in a single open/write/close instead maps to one atomic
S3 PutObject — the only write shape these mounts actually support. On a normal
filesystem it is likewise a single write, which is safe for this single-writer,
low-frequency workload.
"""

from __future__ import annotations

from pathlib import Path


def write_text_durable(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)
