from typing import Optional

import hcloud
import nixops.resources.ssh_keypair
from hcloud.ssh_keys.client import BoundSSHKey, SSHKeysClient
from nixops.resources import ResourceDefinition, ResourceOptions, ResourceState
from nixops.util import attr_property
from nixops_hetznercloud.hcloud_resources import (EntityResource, entity_check,
                                                  entity_create,
                                                  entity_destroy)
from nixops_hetznercloud.hcloud_util import (HetznerCloudContextOptions,
                                             get_access_token)


class HetznerCloudSshKeyOptions(HetznerCloudContextOptions):
    name: str
    publicKey: str


class HetznerCloudSshKeyDefinition(ResourceDefinition):
    config: HetznerCloudSshKeyOptions

    @classmethod
    def get_type(cls) -> str:
        return "hetznercloud-sshkey"

    @classmethod
    def get_resource_type(cls) -> str:
        return "hetznercloudSshKeys"


class HetznerCloudSshKeyState(
    ResourceState[HetznerCloudSshKeyDefinition],
    EntityResource[HetznerCloudSshKeyDefinition, BoundSSHKey],
):
    definition_type = HetznerCloudSshKeyDefinition

    state = attr_property("state", ResourceState.MISSING, int)
    token = attr_property("hetznercloud.token", None, str)
    hcloud_id = attr_property("hetznercloud.id", None, int)
    hcloud_name = attr_property("hetznercloud.name", None, str)
    public_key = attr_property("hetznercloud.publicKey", None, str)
    _cached_client: Optional[hcloud.Client] = None

    @classmethod
    def get_type(cls) -> str:
        return "hetznercloud-sshkey"

    def prefix_definition(self, attr):
        return {("resources", "hetznercloudSshKeys"): attr}

    @property
    def resource_id(self) -> str:
        return self.hcloud_id

    def create(
        self,
        defn: HetznerCloudSshKeyDefinition,
        check: bool,
        allow_reboot: bool,
        allow_recreate: bool,
    ):
        return entity_create(self, defn, check)

    def destroy(self, wipe=False) -> bool:
        return entity_destroy(self)

    def _check(self) -> bool:
        return entity_check(self)

    def entity_client(self) -> SSHKeysClient:
        if self._cached_client is None:
            self._cached_client = hcloud.Client(self.token)
        return self._cached_client.ssh_keys

    def do_create_new(self, defn: HetznerCloudSshKeyDefinition) -> BoundSSHKey:
        self.public_key = defn.config.publicKey
        resp = self.entity_client().create(
            name=self.hcloud_name, public_key=self.public_key
        )
        return resp

    def update(self, defn: HetznerCloudSshKeyDefinition, model: BoundSSHKey) -> None:
        if self.public_key != defn.config.publicKey:
            self.logger.error("Cannot update the public key of a Hetzner Cloud SSH key")

    def check_model(self, model: BoundSSHKey) -> None:
        if self.public_key != model.public_key:
            self.logger.error("Cannot update the public key of a Hetzner Cloud SSH key")
