from typing import Generic, Optional, Protocol, TypeVar

import hcloud
from hcloud.actions.client import BoundAction
from hcloud.core.client import BoundModelBase, ClientEntityBase
from nixops.deployment import Deployment
from nixops.resources import ResourceDefinition, ResourceState

from nixops_hcloud.hcloud_util import HcloudContextOptions, get_access_token

BoundModelType = TypeVar("BoundModelType", bound=BoundModelBase)
ResourceDefinitionType_contra = TypeVar(
    "ResourceDefinitionType_contra", bound=ResourceDefinition, contravariant=True
)


class HcloudDefinition(Protocol):
    config: HcloudContextOptions


# Resources must be direct subclasses of ResourceState, so instead of having a class in the middle
# of the hierarchy we use the top-level functions which recieve an `EntityResource`


class EntityResource(Protocol, Generic[ResourceDefinitionType_contra, BoundModelType]):
    state: int
    token: str
    hcloud_id: Optional[int]
    hcloud_name: str
    depl: Deployment

    def log_start(self, msg: str) -> None:
        raise NotImplementedError()

    def log_end(self, msg: str) -> None:
        raise NotImplementedError()

    def show_type(self) -> str:
        raise NotImplementedError()

    def entity_client(self) -> ClientEntityBase:
        raise NotImplementedError()

    def do_create_new(self, defn: ResourceDefinitionType_contra) -> BoundModelType:
        raise NotImplementedError()

    def update(
        self, defn: ResourceDefinitionType_contra, model: BoundModelType
    ) -> None:
        raise NotImplementedError()

    def check_model(self, model: BoundModelType) -> None:
        raise NotImplementedError()


def entity_create(
    res: EntityResource[ResourceDefinitionType_contra, BoundModelType],
    defn: ResourceDefinitionType_contra,
    check: bool,
):
    res.token = get_access_token(defn.config)  # type: ignore
    res.hcloud_name = defn.config.name  # type: ignore
    if check or res.state != ResourceState.UP:
        model = get_by_name(res)
        if model is None or res.state != ResourceState.UP:
            res.log_start(f"Creating {res.show_type()}...")
            model = res.do_create_new(defn)  # type: ignore
            res.log_end("")
            res.hcloud_id = model.id
            res.state = ResourceState.UP
        else:
            res.hcloud_id = model.id
            res.state = ResourceState.UP
            res.update(defn, model)  # type: ignore


def entity_destroy(
    res: EntityResource[ResourceDefinitionType_contra, BoundModelType]
) -> bool:
    if res.state != ResourceState.UP:
        return True
    if not res.depl.logger.confirm(
        f"are you sure you want to destroy {res.show_type()} {res.hcloud_name!r}?"
    ):
        return False
    model = get_by_name(res)
    if model is None:
        return True
    resp = model.delete()
    if isinstance(resp, BoundAction):
        resp.wait_until_finished()
        return True
    return resp


def entity_check(
    res: EntityResource[ResourceDefinitionType_contra, BoundModelType]
) -> bool:
    model = get_by_name(res)
    if model is None:
        res.hcloud_id = None
        res.state = ResourceState.MISSING
        return False
    res.hcloud_id = model.id
    res.state = ResourceState.UP
    res.check_model(model)
    return True


def get_by_name(
    res: EntityResource[ResourceDefinitionType_contra, BoundModelType],
) -> Optional[BoundModelType]:
    res.log_start(f"looking up {res.show_type()}...")
    try:
        model = res.entity_client().get_by_name(res.hcloud_name)  # type: ignore
        if model is not None:
            res.log_end(f"found {model.id}")
            return model
    except hcloud.APIException as e:
        if e.code != "not_found":
            raise
    res.log_end("not found")
    return None
