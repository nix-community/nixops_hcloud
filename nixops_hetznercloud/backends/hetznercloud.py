import os
import os.path
from typing import Iterable, Optional, Tuple, cast

import hcloud
from hcloud.images.domain import Image
from hcloud.server_types.domain import ServerType
from hcloud.servers.client import BoundServer
from hcloud.servers.domain import Server
from hcloud.ssh_keys.domain import SSHKey
from nixops.backends import MachineDefinition, MachineOptions, MachineState
from nixops.nix_expr import RawValue
from nixops.resources import ResourceOptions
from nixops.util import attr_property
from nixops_hetznercloud.hcloud_util import (HetznerCloudContextOptions,
                                             get_access_token)


class HetznerCloudVmOptions(HetznerCloudContextOptions):
    image: Optional[int]
    # TODO validate image_selector
    image_selector: str
    location: str
    serverType: str


class HetznerCloudOptions(MachineOptions):
    hetznercloud: HetznerCloudVmOptions


class HetznerCloudDefinition(MachineDefinition):
    config: HetznerCloudOptions

    @classmethod
    def get_type(cls) -> str:
        return "hetznercloud"


class HetznerCloudState(MachineState[HetznerCloudDefinition]):
    definition_type = HetznerCloudDefinition

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._cached_client: Optional[hcloud.Client] = None
        self._cached_server: Optional[BoundServer] = None

    @classmethod
    def get_type(cls) -> str:
        return "hetznercloud"

    state = attr_property("state", MachineState.MISSING, int)  # override
    public_ipv4 = attr_property("publicIpv4", None, str)
    token = attr_property("hetznercloud.token", None, str)
    image_id = attr_property("hetznercloud.image_id", None, int)
    location = attr_property("hetznercloud.location", None, str)
    server_type = attr_property("hetznercloud.server_type", None, str)

    @property
    def resource_id(self):
        return self.vm_id

    @property
    def _client(self) -> hcloud.Client:
        assert self.token
        if self._cached_client is None:
            self._cached_client = hcloud.Client(self.token)
        return self._cached_client

    @property
    def _server(self) -> BoundServer:
        if self.vm_id is None:
            raise Exception("Server not created yet")
        if self._cached_server is None or self._cached_server.id != self.vm_id:
            self._cached_server = self._client.servers.get_by_id(self.vm_id)
        return cast(BoundServer, self._cached_server)

    def create(self, defn: HetznerCloudDefinition, check, allow_reboot, allow_recreate):
        assert isinstance(defn, HetznerCloudDefinition)
        hetzner = defn.config.hetznercloud
        self.token = get_access_token(hetzner)
        if self.state not in (MachineState.RESCUE, MachineState.UP) or check:
            self.check()

        self.set_common_state(defn)

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
        if self.vm_id is not None and hetzner.serverType != self.server_type:
            # TODO configure upgrade_disk
            self._server.change_type(
                ServerType(name=self.server_type), upgrade_disk=True
            ).wait_until_finished()
        self.server_type = hetzner.serverType

        if not self.vm_id:
            self.log(
                "Creating Hetzner Cloud VM ("
                + f"image '{image_id}', type '{hetzner.serverType}', location '{hetzner.location}'"
                + ")..."
            )
            response = self._client.servers.create(
                name=self.name,
                # TODO manage SSH keys correcly
                ssh_keys=[SSHKey(name="admin")],
                server_type=ServerType(self.server_type),
                image=Image(id=self.image_id),
                # Set labels so we can find the instance if nixops crashes before writing vm_id
                labels=dict(self._server_labels()),
            )
            with self.depl._db:
                self.vm_id = response.server.id
                self.public_ipv4 = response.server.public_net.ipv4.ip
                # TODO get state from creation response
                self.state = self.STARTING

    def destroy(self, wipe=False):
        if self.vm_id is None:
            return True
        if wipe:
            self.warn("Wipe is not supported")
        self.log("destroying Hetzner Cloud VM...")
        self._client.servers.delete(Server(id=self.vm_id))
        return True

    def get_ssh_flags(self, *args, **kwargs):
        # TODO manage known hosts and ssh keys
        return super().get_ssh_flags(*args, **kwargs) + [
            "-o",
            "StrictHostKeyChecking=accept-new",
            # TODO these are for testing
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-o",
            "StrictHostKeyChecking=accept-new",
        ]

    def get_ssh_name(self):
        assert self.public_ipv4
        return self.public_ipv4

    def get_physical_spec(self):
        # TODO manage SSH keys
        spec = super().get_physical_spec()
        with open("id_rsa.pub") as f:
            pubkey = f.read()
        spec["config"] = {
            ("users", "users", "root", "openssh", "authorizedKeys", "keys"): [pubkey],
        }
        return spec

    def _check(self, res):
        if self.vm_id is None:
            self.log("Looking up server by labels...")
            label_selector = ",".join(f"{k}={v}" for k, v in self._server_labels())
            servers, _ = self._client.servers.get_list(label_selector=label_selector,)
            if len(servers) > 1:
                self.warn(f"Multiple servers matching {self.name} by labels")
            if len(servers) == 0:
                res.exists = False
                return
            server: BoundServer = servers[0]
            self.vm_id = server.id
        else:
            try:
                server = self._client.servers.get_by_id(self.vm_id)
            except hcloud.APIException as e:
                if e.code == 404:
                    self._reset()
                    res.exists = False
                    return
                raise
        res.exists = True
        self._cached_server = server
        with self.depl._db:
            self.state = self._hcloud_status_to_machine_status(server.status)
            self.image_id = server.image.id
            self.location = server.datacenter.location.name
            self.public_ipv4 = server.public_net.ipv4.ip
            self.server_type = server.server_type.name
        res.is_up = self.state == MachineState.UP
        if res.is_up:
            super()._check(res)

    @staticmethod
    def _hcloud_status_to_machine_status(status: str) -> int:
        # TODO check for rescue and unreachable
        try:
            return {
                Server.STATUS_OFF: MachineState.STOPPED,
                Server.STATUS_STOPPING: MachineState.STOPPING,
                Server.STATUS_STARTING: MachineState.STARTING,
                Server.STATUS_INIT: MachineState.STARTING,
                Server.STATUS_RUNNING: MachineState.UP,
                Server.STATUS_UNKNOWN: MachineState.UNKNOWN,
                Server.STATUS_DELETING: MachineState.STOPPING,
                Server.STATUS_MIGRATING: MachineState.STARTING,
                Server.STATUS_REBUILDING: MachineState.STARTING,
            }[status]
        except KeyError as e:
            raise Exception(f"Invalid server status {status!r}") from e

    def _fetch_image_id(self, image: Optional[int], image_selector: str) -> int:
        if image is None:
            self.log(f"Finding image matching {image_selector}...")
            matches, _ = self._client.images.get_list(
                label_selector=image_selector, sort="created:desc",
            )
            if len(matches) == 0:
                raise Exception(f"No images found matching {image_selector}")
            return matches[0].id
        else:
            return image

    def _server_labels(self) -> Iterable[Tuple[str, str]]:
        assert self.depl
        yield "nixops/name", self.name
        yield "nixops/deployment", self.depl.uuid

    def _reset(self) -> None:
        assert self.depl
        with self.depl._db:
            self.state = self.MISSING
            self.vm_id = None
            self.image_id = None
            self.location = None
            self.public_ipv4 = None
            self.server_type = None
