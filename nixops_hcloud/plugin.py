import os.path

import nixops.plugins
from nixops.plugins import Plugin


class HcloudPlugin(Plugin):
    @staticmethod
    def nixexprs():
        return [os.path.dirname(os.path.abspath(__file__)) + "/nix"]

    @staticmethod
    def load():
        return [
            "nixops_hcloud.backends.hcloud",
            "nixops_hcloud.resources",
        ]


@nixops.plugins.hookimpl
def plugin() -> Plugin:
    return HcloudPlugin()
