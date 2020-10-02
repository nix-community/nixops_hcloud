import os
import os.path
from dataclasses import dataclass
from typing import Mapping, Optional

import toml
from nixops.resources import ResourceOptions


class AccessTokenException(Exception):
    pass


class HcloudContextOptions(ResourceOptions):
    """Common authentication settings for Hetzner Cloud resources. Subclass this for resources
       which need Hetzner API access.
    """

    context: Optional[str]
    token: Optional[str]


@dataclass
class HcloudConfig:
    active_context: Optional[str]
    contexts: Mapping[str, str]

    @classmethod
    def load(cls, path: Optional[str] = None) -> "HcloudConfig":
        if path is None:
            xdg_cfg_home = os.environ.get(
                "XDG_CONFIG_HOME", os.path.expanduser("~/.config")
            )
            path = os.path.join(xdg_cfg_home, "hcloud/cli.toml")
        cfg = toml.load(path)
        return HcloudConfig(
            active_context=cfg.get("active_context"),
            contexts={ctx["name"]: ctx["token"] for ctx in cfg.get("contexts", [])},
        )


def get_access_token(
    opt: HcloudContextOptions,
    env: Optional[Mapping[str, str]] = None,
    cfg: HcloudConfig = None,
) -> str:
    """Get Hetzner Cloud API access token.

    Uses the context or token provided in `opt`, if any, else looks up HCLOUD_CONTEXT or
    HCLOUD_TOKEN in `env` and finally uses the current active context. Looks for context
    definitions cli config in `cfg_path`

    Raises
    ------
    `AccessTokenException`
        If there's no token set or there's an error reading the context.
    """
    context = opt.context
    token = opt.token

    env = env or os.environ

    # cfg.context > cfg.token > HCLOUD_CONTEXT > HCLOUD_TOKEN > current context
    if (
        context is not None
        or (not token and "HCLOUD_CONTEXT" in env)
        or "HCLOUD_TOKEN" not in env
    ):
        # Look up context in config
        try:
            if cfg is None:
                cfg = HcloudConfig.load()
            if context is None:
                context = env.get("HCLOUD_CONTEXT", cfg.active_context)
                if context is None:
                    raise AccessTokenException(
                        "Need to be in an hcloud context or have hcloud token or context explicitly set."
                    )
            if context not in cfg.contexts:
                raise AccessTokenException(f"Context {context} not found")
            return cfg.contexts[context]
        except (toml.TomlDecodeError, FileNotFoundError, PermissionError) as e:
            raise AccessTokenException("Failed to read hcloud context.") from e
        raise AccessTokenException("Failed to read hcloud context.")
    try:
        return token or env["HCLOUD_TOKEN"]
    except KeyError as e:
        raise AccessTokenException(
            "Need to be in an hcloud context or have hcloud token or context explicitly set."
        ) from e
