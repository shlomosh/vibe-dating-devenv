from __future__ import annotations

from lib.config import AppConfig
from lib.resource import create_backend
from lib.run_state import load_state


def print_status(cfg: AppConfig) -> None:
    state = load_state(cfg.state_path)

    try:
        backend = create_backend(cfg.resource, cfg.config_dir)
        backend.reload()
        counts = backend.counts()
        store_label = backend.store_label
        resource_type = cfg.resource.get("type")
    except Exception as e:
        counts = {}
        store_label = None
        resource_type = cfg.resource.get("type")
        print(f"Resource store: error loading — {e}")

    for key, channel in cfg.channels.items():
        enabled = channel.get("enabled", True)
        header = f"=== Channel: {key} ==="
        print(f"{header} (disabled)" if not enabled else header)

        ch_state = state.get("channels", {}).get(key, {})
        pids = ch_state.get("post_message_ids", {})
        posts = channel.get("posts") or []

        for i, post in enumerate(posts):
            mid = pids.get(str(i), "-")
            delete_prev = post.get("delete_previous", False)
            resource = post.get("resource", "-")
            silent = post.get("silent", False)
            parts = [
                f"Post {i}: message_id={mid}",
                f"delete_previous={delete_prev}",
                f"resource={resource}",
            ]
            if post.get("resource"):
                parts.append(f"silent={silent}")
            print("  " + " ".join(parts))

        last_at = ch_state.get("last_posted_at")
        if last_at:
            print(f"  Last posted: {last_at}")
        last_res = ch_state.get("last_resources") or []
        if last_res:
            formatted = ",".join(
                f"{r.get('class', '?')}:{r.get('url', '?')}" for r in last_res
            )
            print(f"  Last resources: {formatted}")
        print()

    print("=== Resource store ===")
    print(f"type={resource_type}")
    if store_label:
        print(f"store={store_label}")
    for class_name in sorted(counts.keys()):
        c = counts[class_name]
        print(f"  {class_name}: pending={c['pending']} used={c['used']}")
