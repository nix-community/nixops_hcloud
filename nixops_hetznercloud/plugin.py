import os.path

import nixops.plugins
from nixops.plugins import Plugin


class HetznerCloudPlugin(Plugin):
    @staticmethod
    def nixexprs():
        return [os.path.dirname(os.path.abspath(__file__)) + "/nix"]

    @staticmethod
    def load():
        return [
            "nixops_hetznercloud.backends.hetznercloud",
            "nixops_hetznercloud.resources",
        ]


@nixops.plugins.hookimpl
def plugin() -> Plugin:
    return HetznerCloudPlugin()
