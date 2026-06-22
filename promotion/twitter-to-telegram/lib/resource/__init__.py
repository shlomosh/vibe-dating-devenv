from lib.config import AppConfig
from lib.resource.base import ResourceBackend
from lib.resource.csvfile import CsvfileBackend


def create_backend(resource_cfg: dict, config_dir) -> ResourceBackend:
    rtype = resource_cfg.get("type")
    dummy = AppConfig(raw={}, path=config_dir / "config.json", config_dir=config_dir)

    if rtype == "csvfile":
        path = dummy.resolve_file_url(resource_cfg["url"])
        return CsvfileBackend(path)
    raise ValueError(f"Unsupported resource type: {rtype!r}")
