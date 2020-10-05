import os
import os.path
from typing import (Any, Iterable, List, Mapping, Optional, Sequence, Tuple,
                    Union, cast)

import yaml
from nixops import known_hosts
from nixops.backends import MachineDefinition, MachineOptions, MachineState
from nixops.nix_expr import RawValue, nix2py
from nixops.resources import ResourceEval, ResourceOptions
from nixops.util import attr_property, create_key_pair
from nixops_hcloud.hcloud_util import HcloudContextOptions, get_access_token
from nixops_hcloud.resources.hcloud_sshkey import HcloudSshKeyState
from nixops_hcloud.resources.hcloud_volume import HcloudVolumeState

import hcloud
from hcloud.actions.client import BoundAction
from hcloud.images.domain import Image
from hcloud.server_types.domain import ServerType
from hcloud.servers.client import BoundServer
from hcloud.servers.domain import Server
from hcloud.ssh_keys.domain import SSHKey
from hcloud.volumes.domain import Volume

HOST_KEY_TYPE = "ed25519"


class VolumeOptions(ResourceOptions):
    volume: Union[str, ResourceEval]
    mountPoint: Optional[str]
    fileSystem: Mapping[str, Any]


class HcloudVmOptions(HcloudContextOptions):
    image: Optional[int]
    # TODO validate image_selector
    image_selector: str
    location: str
    serverType: str
    upgradeDisk: bool
    sshKeys: Sequence[Union[str, ResourceEval]]
    volumes: Sequence[VolumeOptions]


class HcloudOptions(MachineOptions):
    hcloud: HcloudVmOptions


class HcloudDefinition(MachineDefinition):
    config: HcloudOptions

    @classmethod
    def get_type(cls) -> str:
        return "hcloud"


class HcloudState(MachineState[HcloudDefinition]):
    definition_type = HcloudDefinition

    state = attr_property("state", MachineState.MISSING, int)  # override
    public_ipv4 = attr_property("publicIpv4", None, str)
    token = attr_property("hcloud.token", None, str)
    image_id = attr_property("hcloud.image", None, int)
    location = attr_property("hcloud.location", None, str)
    server_type = attr_property("hcloud.serverType", None, str)
    upgrade_disk = attr_property("hcloud.upgradeDisk", False, bool)
    hw_info = attr_property("hcloud.hardwareInfo", None, str)
    ssh_keys = attr_property("hcloud.sshKeys", None, "json")
    volume_ids = attr_property("hcloud.volumeIds", None, "json")
    filesystems = attr_property("hcloud.filesystems", None, "json")
    _ssh_private_key = attr_property("hcloud.sshPrivateKey", None, str)
    _ssh_public_key = attr_property("hcloud.sshPublicKey", None, str)
    _public_host_key = attr_property("hcloud.publicHostKey", None, str)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._cached_client: Optional[hcloud.Client] = None
        self._cached_server: Optional[BoundServer] = None

    @classmethod
    def get_type(cls) -> str:
        return "hcloud"

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

    def create(self, defn: HcloudDefinition, check, allow_reboot, allow_recreate):
        assert isinstance(defn, HcloudDefinition)
        hetzner = defn.config.hcloud
        self.token = get_access_token(hetzner)
        if self.state not in (MachineState.RESCUE, MachineState.UP) or check:
            self.check()

        self.set_common_state(defn)
        self.upgrade_disk = hetzner.upgradeDisk

        # TODO maybe bootstrap can be automated with vncdotool
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
            # TODO Check if server can be upgraded before hitting the Hetzner API
            # https://docs.hetzner.cloud/#server-actions-change-the-type-of-a-server
            do_upgrade = True
            # Only confirm if upgrade_disk is True because then the upgrade can't be undone
            if self.upgrade_disk:
                do_upgrade = self.depl.logger.confirm(
                    f"are you sure you want to change Hetzner server {self.name} type from "
                    + f"{self.server_type} to {hetzner.serverType}?"
                )
            if do_upgrade:
                self.log_start("Changing Hetzner server type...")
                self._server.shutdown().wait_until_finished()
                self.wait_for_down(callback=lambda: self.log_continue("."))
                self._server.change_type(
                    ServerType(name=hetzner.serverType), upgrade_disk=self.upgrade_disk
                ).wait_until_finished()
                self._server.power_on()
                self.wait_for_up(callback=lambda: self.log_continue("."))
                self.log_end("")
        self.server_type = hetzner.serverType

        ssh_keys = [
            k.name if isinstance(k, ResourceEval) else k for k in hetzner.sshKeys
        ]
        if self.state != MachineState.MISSING and ssh_keys != self.ssh_keys:
            self.logger.warn(f"SSH keys cannot be changed after the server is created.")

        volume_ids = []
        filesystems = {}
        for volumeopts in hetzner.volumes:
            volume = volumeopts.volume
            if isinstance(volume, str):
                volume_model = self._client.volumes.get_by_name(volume)
                volume_name = volume
                volume_id = volume_model.id
                volume_loc = volume_model.location.name
            else:
                volume_res = self.depl.get_typed_resource(
                    volume._name, "hcloud-volume", HcloudVolumeState
                )
                volume_name = volume_res.name
                volume_id = volume_res.hcloud_id
                assert volume_id is not None
                volume_loc = volume_res.location
            if volume_loc != self.location:
                raise Exception(
                    f"Volume {volume_name!r} is in a different location from server {self.name!r}"
                )
            volume_ids.append(volume_id)
            if volumeopts.mountPoint is not None:
                fs = dict(volumeopts.fileSystem)
                fs["device"] = f"/dev/disk/by-id/scsi-0HC_Volume_{volume_id}"
                filesystems[volumeopts.mountPoint] = fs

        has_priv = self._ssh_private_key is not None
        has_pub = self._ssh_public_key is not None
        assert has_priv == has_pub
        if not has_priv:
            self.log("Generating SSH keypair...")
            (self._ssh_private_key, self._ssh_public_key) = create_key_pair()
        if self.vm_id:
            if self.volume_ids != volume_ids:
                current = set(self.volume_ids)
                new = set(volume_ids)
                volumes_client = self._client.volumes
                self.log_start("Updating volumes...")
                for v in current - new:
                    volumes_client.detach(Volume(id=v))
                    self.log_continue(".")
                for v in new - current:
                    volumes_client.attach(
                        Volume(id=v), self._server, automount=False
                    ).wait_until_finished()
                    self.log_continue(".")
                self.log_end("")
                self.volume_ids = volume_ids
        else:
            self.log_start(
                "Creating Hetzner Cloud VM ("
                + f"image '{image_id}', type '{hetzner.serverType}', location '{hetzner.location}'"
                + ")..."
            )
            response = self._client.servers.create(
                name=self.name,
                ssh_keys=[SSHKey(name=k) for k in ssh_keys],
                volumes=[Volume(id=v) for v in volume_ids],
                server_type=ServerType(self.server_type),
                image=Image(id=self.image_id),
                # Set labels so we can find the instance if nixops crashes before writing vm_id
                labels=dict(self._server_labels()),
                user_data=None
                if self._ssh_public_key is None
                else yaml.dump({"public-keys": [self._ssh_public_key]}),
            )
            self.log_end("")
            self.public_ipv4 = response.server.public_net.ipv4.ip
            self.log_start("waiting for SSH...")
            self.wait_for_up(callback=lambda: self.log_continue("."))
            self.log_end("")
            with self.depl._db:
                self.vm_id = response.server.id
                # TODO get state from creation response
                self.state = MachineState.STARTING
                self.ssh_keys = ssh_keys
                self.volume_ids = volume_ids
                self._detect_hardware()
                self._update_host_keys()
        self.filesystems = filesystems

    def destroy(self, wipe=False):
        if self.vm_id is None:
            return True
        if wipe:
            self.warn("Wipe is not supported")
        if not self.depl.logger.confirm(
            f"are you sure you want to destroy Hetzner server {self.name}?"
        ):
            return False
        self.log_start("destroying Hetzner Cloud VM...")
        self._client.servers.delete(Server(id=self.vm_id))
        self.log_end("")
        self._reset()
        return True

    def get_ssh_flags(self, *args, **kwargs) -> List[str]:
        key_file = self.get_ssh_private_key_file()
        assert key_file is not None
        flags = super().get_ssh_flags(*args, **kwargs) + [
            "-i",
            key_file,
        ]
        # TODO set host keys with cloud-init se we don't need to disable host key checking on first
        # deploy
        if self._public_host_key is None:
            flags.extend(
                [
                    "-o",
                    "UserKnownHostsFile=/dev/null",
                    "-o",
                    "GlobalKnownHostsFile=/dev/null",
                    "-o",
                    "StrictHostKeyChecking=accept-new",
                ]
            )
        return flags

    def get_ssh_private_key_file(self) -> Optional[str]:
        if self._ssh_private_key_file:
            return self._ssh_private_key_file
        if self._ssh_private_key:
            return self.write_ssh_private_key(self._ssh_private_key)
        return None

    def get_ssh_name(self):
        assert self.public_ipv4
        return self.public_ipv4

    def get_physical_spec(self):
        spec = super().get_physical_spec()
        if self.hw_info:
            spec.setdefault("imports", []).append(nix2py(self.hw_info))
        if self.filesystems is not None:
            fs = spec.setdefault("config", {}).setdefault("fileSystems", {})
            fs.update(self.filesystems)
        return spec

    def _check(self, res):
        self.log_start("Looking up server...")
        if self.vm_id is None:
            label_selector = ",".join(f"{k}={v}" for k, v in self._server_labels())
            servers, _ = self._client.servers.get_list(label_selector=label_selector,)
            if len(servers) > 1:
                self.warn(f"Multiple servers matching {self.name} by labels")
            if len(servers) == 0:
                self.log_end("not found")
                res.exists = False
                return
            server: BoundServer = servers[0]
            self.vm_id = server.id
        else:
            try:
                server = self._client.servers.get_by_id(self.vm_id)
            except hcloud.APIException as e:
                if e.code == "not_found":
                    self.log_end("not found")
                    self._reset()
                    res.exists = False
                    return
                raise
        self.log_end("found")
        res.exists = True
        self._cached_server = server
        with self.depl._db:
            if self._public_host_key is None:
                self._update_host_keys()
            self.state = self._hcloud_status_to_machine_status(server.status)
            self.image_id = server.image.id
            self.volume_ids = [v.id for v in server.volumes]
            self.location = server.datacenter.location.name
            self.public_ipv4 = server.public_net.ipv4.ip
            self.server_type = server.server_type.name
        res.is_up = self.state == MachineState.UP
        if res.is_up:
            super()._check(res)

    def create_after(self, resources, defn):
        return {
            r
            for r in resources
            if isinstance(r, (HcloudSshKeyState, HcloudVolumeState))
        }

    def _detect_hardware(self) -> None:
        self.log_start("detecting hardware...")
        cmd = "nixos-generate-config --show-hardware-config"
        hardware = self.run_command(cmd, capture_stdout=True)
        self.hw_info = "\n".join(
            [
                line
                for line in hardware.splitlines()
                if not line.lstrip().startswith("#")
            ]
        )
        self.log_end("")

    def _update_host_keys(self) -> None:
        self.log_start("updating host keys...")
        cmd = f"cat /etc/ssh/ssh_host_{HOST_KEY_TYPE}_key.pub"
        self._public_host_key = str(self.run_command(cmd, capture_stdout=True)).strip()
        known_hosts.add(self.public_ipv4, self._public_host_key)
        self.log_end("")

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
        if all((self.public_ipv4, self._public_host_key)):
            known_hosts.remove(self.public_ipv4, self._public_host_key)
        with self.depl._db:
            self.state = self.MISSING
            self.vm_id = None
            self.image_id = None
            self.location = None
            self.public_ipv4 = None
            self.server_type = None
            self.hw_info = None
            self._ssh_public_key = None
            self._ssh_private_key = None
            self._public_host_key = None
