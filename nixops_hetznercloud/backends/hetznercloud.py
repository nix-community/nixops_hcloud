import os
import os.path
from typing import Optional

import hcloud
from hcloud.images.domain import Image
from hcloud.server_types.domain import ServerType
from hcloud.servers.domain import Server
from nixops.backends import MachineDefinition, MachineOptions, MachineState
from nixops.resources import ResourceOptions
from nixops.util import attr_property


class HetznerCloudVmOptions(ResourceOptions):
    image: int
    location: str
    serverType: str
    token: Optional[str]


class HetznerCloudOptions(MachineOptions):
    hetznercloud: HetznerCloudVmOptions


class HetznerCloudDefinition(MachineDefinition):
    config: HetznerCloudOptions

    @classmethod
    def get_type(cls) -> str:
        return "hetznercloud"


class HetznerCloudState(MachineState[HetznerCloudDefinition]):
    definition_type = HetznerCloudDefinition

    @classmethod
    def get_type(cls) -> str:
        return "hetznercloud"

    state = attr_property("state", MachineState.MISSING, int)  # override
    public_ipv4 = attr_property("publicIpv4", None)
    token = attr_property("hetznercloud.token", None)

    def __init__(self, depl, name, id):
        super().__init__(depl, name, id)

    @property
    def resource_id(self):
        return self.vm_id

    def _client(self) -> hcloud.Client:
        assert self.token
        return hcloud.Client(self.token)

    def create(self, defn: HetznerCloudDefinition, check, allow_reboot, allow_recreate):
        assert isinstance(defn, HetznerCloudDefinition)
        if self.state not in (self.RESCUE, self.UP) or check:
            self.check()
        self.set_common_state(defn)

        if defn.config.hetznercloud.token is None:
            token = os.environ["HCLOUD_TOKEN"]
        else:
            token = defn.config.hetznercloud.token
        if token is None:
            raise Exception("No token configured and HCLOUD_TOKEN not set")
        self.token = token

        client = self._client()
        hetzner = defn.config.hetznercloud
        if not self.vm_id:
            self.log(
                "Creating Hetzner Cloud VM ("
                + f"image '{hetzner.image}', type '{hetzner.serverType}', location '{hetzner.location}'"
                + ")..."
            )
            response = client.servers.create(
                name=self.name,
                server_type=ServerType(hetzner.serverType),
                image=Image(id=hetzner.image, type="snapshot"),
            )
            with self.depl._db:
                self.vm_id = response.server.id
                self.public_ipv4 = response.server.public_net.ipv4.ip
                self.state = self.STARTING

    def destroy(self, wipe=False):
        if self.vm_id is None:
            return True
        if wipe:
            self.warn("Wipe is not supported")
        self.log_start("destroying Hetzner Cloud VM...")
        client = self._client()
        client.servers.delete(Server(id=self.vm_id))
        self.log_end("")
        return True

    def get_ssh_flags(self, *args, **kwargs):
        # TODO manage known hosts and ssh keys
        return super().get_ssh_flags(*args, **kwargs) + [
            "-o",
            "StrictHostKeyChecking=accept-new",
        ]

    def get_ssh_name(self):
        assert self.public_ipv4
        return self.public_ipv4

    def _check(self, res):
        if not self.vm_id:
            res.exists = False
            return
        res.exists = True
        res.is_up = self.ping()
        if res.is_up:
            super()._check(res)
