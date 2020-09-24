import os
import os.path
from typing import Optional

import hcloud
from hcloud.images.domain import Image
from hcloud.server_types.domain import ServerType
from hcloud.servers.domain import Server
from hcloud.ssh_keys.domain import SSHKey
from nixops.backends import MachineDefinition, MachineOptions, MachineState
from nixops.resources import ResourceOptions
from nixops.util import attr_property


class HetznerCloudVmOptions(ResourceOptions):
    image: Optional[int]
    # TODO validate image_selector
    image_selector: str
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
    public_ipv4 = attr_property("publicIpv4", None, str)
    token = attr_property("hetznercloud.token", None, str)
    image_id = attr_property("hetznercloud.image_id", None, int)
    location = attr_property("hetznercloud.location", None, str)
    server_type = attr_property("hetznercloud.server_type", None, str)

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
        image_id = self._fetch_image_id(hetzner.image, hetzner.image_selector)
        if self.image_id is None:
            self.image_id = image_id
        elif self.image_id != image_id:
            self.warn(
                f"image_id changed from {self.image_id} to {image_id} but can't update image of a VM."
            )
        if self.location is None:
            self.location = hetzner.location
        elif self.location != hetzner.location:
            self.warn(
                f"location changed from {self.location} to {hetzner.location} but can't update location of a VM."
            )
        if hetzner.serverType != self.server_type:
            # TODO update server type
            pass
        self.server_type = hetzner.serverType

        if not self.vm_id:
            self.log(
                "Creating Hetzner Cloud VM ("
                + f"image '{hetzner.image}', type '{hetzner.serverType}', location '{hetzner.location}'"
                + ")..."
            )
            response = client.servers.create(
                name=self.name,
                # TODO manage SSH keys correcly
                keys=SSHKey(name="admin"),
                server_type=ServerType(self.server_type),
                image=Image(id=self.image_id),
                # Set labels so we can find the instance if nixops crashes before writing vm_id
                labels={
                    "nixops_hetznercloud/name": self.name,
                    "nixops_hetznercloud/deployment": self.depl.uuid,
                },
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
        self.log("destroying Hetzner Cloud VM...")
        client = self._client()
        client.servers.delete(Server(id=self.vm_id))
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
        # TODO better state checking
        if self.vm_id is None:
            res.exists = False
            return
        res.exists = True
        res.is_up = self.ping()
        if res.is_up:
            super()._check(res)

    def _fetch_image_id(self, image: Optional[int], image_selector: str) -> int:
        client = self._client()
        if image is None:
            self.log(f"Finding image matching {image_selector}...")
            matches, _ = client.images.get_list(
                label_selector=image_selector, sort="created:desc",
            )
            if len(matches) == 0:
                raise Exception(f"No images found matching {image_selector}")
            return matches[0].image.id
        else:
            return image
