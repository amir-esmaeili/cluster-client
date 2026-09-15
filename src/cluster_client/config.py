import json
import os
from dataclasses import dataclass


@dataclass
class Config:
    hosts: list[str]
    connect_timeout: float = 5.0
    read_timeout: float = 30.0
    max_retry_attempts: int = 3
    base_backoff_delay: float = 1.0
    treat_create_conflict_as_success: bool = False

    @classmethod
    def from_env(cls) -> "Config":
        hosts_str = os.environ.get("HOSTS", "")
        if not hosts_str:
            raise ValueError("HOSTS environment variable is required")

        try:
            hosts = json.loads(hosts_str)
            if not isinstance(hosts, list):
                raise ValueError("HOSTS JSON must be an array")
        except json.JSONDecodeError:
            hosts = [h.strip() for h in hosts_str.split(",") if h.strip()]

        if not hosts:
            raise ValueError("HOSTS must contain at least one host")

        return cls(
            hosts=hosts,
            connect_timeout=float(os.environ.get("CONNECT_TIMEOUT", "5.0")),
            read_timeout=float(os.environ.get("READ_TIMEOUT", "30.0")),
            max_retry_attempts=int(os.environ.get("MAX_RETRY_ATTEMPTS", "3")),
            base_backoff_delay=float(os.environ.get("BASE_BACKOFF_DELAY", "1.0")),
            treat_create_conflict_as_success=(
                os.environ.get("TREAT_CREATE_CONFLICT_AS_SUCCESS", "false").lower() == "true"
            ),
        )
