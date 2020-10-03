from typing import Optional

import hcloud
from hcloud.locations.domain import Location
from hcloud.volumes.client import BoundVolume, VolumesClient
from nixops.resources import ResourceDefinition, ResourceState
from nixops.util import attr_property
from nixops_hcloud.hcloud_resources import (EntityResource, entity_check,
                                            entity_create, entity_destroy,
                                            get_by_name)
from nixops_hcloud.hcloud_util import HcloudContextOptions, get_access_token


class HcloudVolumeOptions(HcloudContextOptions):
    name: str
    size: int
    location: str


class HcloudVolumeDefinition(ResourceDefinition):
    config: HcloudVolumeOptions

    @classmethod
    def get_type(cls) -> str:
        return "hcloud-volume"

    @classmethod
    def get_resource_type(cls) -> str:
        return "hcloudVolumes"


class HcloudVolumeState(
    ResourceState[HcloudVolumeDefinition],
    EntityResource[HcloudVolumeDefinition, BoundVolume],
):
    definition_type = HcloudVolumeDefinition

    state = attr_property("state", ResourceState.MISSING, int)
    token = attr_property("hcloud.token", None, str)
    hcloud_id = attr_property("hcloud.id", None, int)
    hcloud_name = attr_property("hcloud.name", None, str)
    size = attr_property("hcloud.size", None, int)
    location = attr_property("hcloud.location", None, str)
    _cached_client: Optional[hcloud.Client] = None

    @classmethod
    def get_type(cls) -> str:
        return "hcloud-volume"

    def prefix_definition(self, attr):
        return {("resources", "hcloudVolumes"): attr}

    @property
    def resource_id(self) -> str:
        return self.hcloud_id

    def create(
        self,
        defn: HcloudVolumeDefinition,
        check: bool,
        allow_reboot: bool,
        allow_recreate: bool,
    ):
        return entity_create(self, defn, check)

    def destroy(self, wipe=False) -> bool:
        return entity_destroy(self)

    def _check(self) -> bool:
        return entity_check(self)

    def entity_client(self) -> VolumesClient:
        if self._cached_client is None:
            self._cached_client = hcloud.Client(self.token)
        return self._cached_client.volumes

    def do_create_new(self, defn: HcloudVolumeDefinition) -> BoundVolume:
        self.size = defn.config.size
        self.location = defn.config.location
        resp = self.entity_client().create(
            name=self.hcloud_name, size=self.size, location=Location(name=self.location)
        )
        resp.action.wait_until_finished()
        return resp.volume

    def update(self, defn: HcloudVolumeDefinition, model: BoundVolume) -> None:
        if defn.config.location != model.location.name:
            self.logger.error("Cannot update the location of a Hetzner Cloud volume")
        if defn.config.size < model.size:
            self.logger.error("Cannot shrink volume")
        elif defn.config.size > model.size:
            if not self.depl.logger.confirm(f"Resize volume {self.name!r}?"):
                return
            model.resize(defn.config.size).wait_until_finished()
            self.size = defn.config.size

    def should_update(self, defn: HcloudVolumeDefinition) -> bool:
        return self.location != defn.config.location or self.size != defn.config.size

    def update_unchecked(self, defn: HcloudVolumeDefinition) -> None:
        if defn.config.location != self.location:
            self.logger.error("Cannot update the location of a Hetzner Cloud volume")
        if defn.config.size < self.size:
            self.logger.error("Cannot shrink volume")
        elif defn.config.size > self.size:
            if not self.depl.logger.confirm(f"Resize volume {self.name!r}?"):
                return
            model = get_by_name(self)
            if model is None:
                self.logger.error("Volume missing")
                return
            model.resize(defn.config.size).wait_until_finished()
            self.size = defn.config.size

    def check_model(self, model: BoundVolume) -> None:
        self.location = model.location.name
        self.size = model.size
