from __future__ import annotations

import dataclasses
from typing import Annotated, Any, Protocol, TypeVar, Union

import httpx
import pydantic
from pydantic import SecretStr as SecretStr

import bw_sdk.model as _m

StrRespT = Annotated[
    Union[_m.ValidResponse[_m.StrObj], _m.ErrorResponse],
    pydantic.Field(discriminator="success"),
]
StrResp = pydantic.TypeAdapter(StrRespT)

StatusResp = pydantic.TypeAdapter(
    Annotated[
        Union[_m.ValidResponse[_m.TemplateObj[_m.ServerStatus]], _m.ErrorResponse],
        pydantic.Field(discriminator="success"),
    ]
)

OrgResp = pydantic.TypeAdapter(
    Annotated[
        Union[_m.ValidResponse[_m.Organization], _m.ErrorResponse],
        pydantic.Field(discriminator="success"),
    ]
)
OrgsResp = pydantic.TypeAdapter(
    Annotated[
        Union[_m.ValidResponse[_m.DataList[_m.Organization]], _m.ErrorResponse],
        pydantic.Field(discriminator="success"),
    ]
)

CollResp = pydantic.TypeAdapter(
    Annotated[
        Union[_m.ValidResponse[_m.Collection], _m.ErrorResponse],
        pydantic.Field(discriminator="success"),
    ]
)
CollsResp = pydantic.TypeAdapter(
    Annotated[
        Union[_m.ValidResponse[_m.DataList[_m.Collection]], _m.ErrorResponse],
        pydantic.Field(discriminator="success"),
    ]
)


FolderResp = pydantic.TypeAdapter(
    Annotated[
        Union[_m.ValidResponse[_m.Folder], _m.ErrorResponse],
        pydantic.Field(discriminator="success"),
    ]
)
FoldersResp = pydantic.TypeAdapter(
    Annotated[
        Union[_m.ValidResponse[_m.DataList[_m.Folder]], _m.ErrorResponse],
        pydantic.Field(discriminator="success"),
    ]
)

NewItem = _m.NewItemLogin | _m.NewItemSecureNote
UnlockResp = pydantic.TypeAdapter(
    Annotated[
        Union[_m.ValidResponse[_m.UnlockData], _m.ErrorResponse],
        pydantic.Field(discriminator="success"),
    ]
)
LockResp = pydantic.TypeAdapter(
    Annotated[
        Union[_m.ValidResponse[Any], _m.ErrorResponse],
        pydantic.Field(discriminator="success"),
    ]
)
ItemResp = pydantic.TypeAdapter(
    Annotated[
        Union[_m.ValidResponse[_m.Item], _m.ErrorResponse],
        pydantic.Field(discriminator="success"),
    ]
)
ItemsResp = pydantic.TypeAdapter(
    Annotated[
        Union[_m.ValidResponse[_m.DataList[_m.Item]], _m.ErrorResponse],
        pydantic.Field(discriminator="success"),
    ]
)

BaseObjT = TypeVar("BaseObjT", bound=_m.BaseObj)


class ValidateObj(Protocol[BaseObjT]):
    def validate_json(
        self, __data: str | bytes, *, strict: bool | None = None, context: dict[str, Any] | None = None
    ) -> _m.ValidResponse[BaseObjT] | _m.ErrorResponse:
        ...


class ValidateList(Protocol[BaseObjT]):
    def validate_json(
        self, __data: str | bytes, *, strict: bool | None = None, context: dict[str, Any] | None = None
    ) -> _m.ValidResponse[_m.DataList[BaseObjT]] | _m.ErrorResponse:
        ...


@dataclasses.dataclass
class Client:
    http_client: httpx.Client = dataclasses.field(
        default_factory=lambda: httpx.Client(base_url="http://localhost:8087")
    )

    def unlock(self, password: pydantic.SecretStr):
        res = self.http_client.post("/unlock", json={"password": password.get_secret_value()})
        resp = UnlockResp.validate_json(res.content)

        if isinstance(resp, _m.ErrorResponse):
            raise Exception(f"Could not unlock bitwarden [{resp.message}]")

        return resp.data.raw

    def lock(self):
        res = self.http_client.post("/lock")
        resp = LockResp.validate_json(res.content)

        if isinstance(resp, _m.ErrorResponse):
            raise Exception("Could not lock bitwarden")

    def sync(self):
        res = self.http_client.post("/sync")
        res.raise_for_status()

    def get_status(self):
        res = self.http_client.get("/status")
        resp = StatusResp.validate_json(res.content)

        if isinstance(resp, _m.ErrorResponse):
            raise Exception(f"Could not get obj [{resp.message}]")

        return resp.data.template

    def get_fingerprint(self):
        return self._get_str("/object/fingerprint/me")

    # region Internal

    def _get_str(self, path: str) -> str:
        res = self.http_client.get(path)
        resp: StrRespT = StrResp.validate_json(res.content)

        if isinstance(resp, _m.ErrorResponse):
            raise Exception(f"Could not get obj [{resp.message}]")

        return resp.data.data

    def _get_object(self, validator: ValidateObj[BaseObjT], obj_type: str, obj_id: str) -> BaseObjT:
        res = self.http_client.get(f"/object/{obj_type}/{obj_id}")
        resp = validator.validate_json(res.content)

        if isinstance(resp, _m.ErrorResponse):
            raise Exception(f"Could not get obj [{resp.message}]")

        return resp.data

    def _get_list(
        self,
        validator: ValidateList[BaseObjT],
        obj_type: str,
        params: dict[str, str | None] | None,
        exact: bool,
    ) -> list[BaseObjT]:
        search = None if params is None else params.get("search", None)
        params_cleaned = None if params is None else {k: v for k, v in params.items() if v is not None}

        url = f"/list/object/{obj_type}"
        # print(url)

        res = self.http_client.get(url, params=params_cleaned)

        # print(res.content)

        resp = validator.validate_json(res.content)

        if isinstance(resp, _m.ErrorResponse):
            raise Exception(f"Could not get objs [{resp.message}]")

        if exact:
            return [x for x in resp.data.data if x.name == search]
        return resp.data.data

    # endregion

    # region Items

    def get_item(self, item: _m.Item | _m.ItemID):
        obj_id = item if isinstance(item, str) else item.id
        return self._get_object(ItemResp, "item", obj_id)

    def get_items(
        self,
        search: str | None = None,
        orgID: _m.OrgID | None = None,
        collID: _m.CollID | None = None,
        folderID: _m.DirID | None = None,
        url: str | None = None,
        trash: bool = False,
        exact: bool = False,
    ):
        params = {
            "organizationId": orgID,
            "collectionId": collID,
            "folderid": folderID,
            "url": url,
            "trash": "true" if trash else None,
            "search": search,
        }
        return self._get_list(ItemsResp, "items", params, exact)

    def find_item(
        self,
        search: str | None = None,
        orgID: _m.OrgID | None = None,
        collID: _m.CollID | None = None,
        folderID: _m.DirID | None = None,
        url: str | None = None,
        exact: bool = False,
    ):
        res = self.get_items(search, orgID, collID, folderID, url, exact)
        match len(res):
            case 0:
                raise Exception("no item found")
            case 1:
                return res[0]
            case _:
                raise Exception("multiple items matches")

    def put_item(self, item: _m.Item):
        res = self.http_client.put(f"/object/item/{item.id}", json=item.model_dump(mode="json"))

        resp = ItemResp.validate_json(res.content)

        if isinstance(resp, _m.ErrorResponse):
            raise Exception(f"Could not get items [{resp.message}]")

        return resp.data

    def post_item(self, item: NewItem):
        res = self.http_client.post("/object/item", json=item.model_dump(mode="json"))
        resp = ItemResp.validate_json(res.content)

        if isinstance(resp, _m.ErrorResponse):
            raise Exception(f"Could not get items [{resp.message}]")

        return resp.data

    def del_item(self, item: _m.Item | _m.ItemID):
        item_id = item if isinstance(item, str) else item.id
        r = self.http_client.delete(f"/object/item/{item_id}")
        r.raise_for_status()

    def restore_item(self, item: _m.Item | _m.ItemID):
        item_id = item if isinstance(item, str) else item.id
        r = self.http_client.post(f"/restore/item/{item_id}")
        r.raise_for_status()

    # endregion

    # region Folders

    def get_folder(self, folder: _m.Folder | _m.DirID):
        obj_id = folder if isinstance(folder, str) else folder.id
        return self._get_object(FolderResp, "folder", obj_id)

    def get_folders(self, search: str | None = None, exact: bool = False):
        params = {
            "search": search,
        }
        return self._get_list(FoldersResp, "folders", params, exact)

    def find_folder(self, search: str | None = None, exact: bool = False):
        res = self.get_folders(search, exact)
        match len(res):
            case 0:
                raise Exception("no folder found")
            case 1:
                return res[0]
            case _:
                raise Exception("multiple folders matches")

    def put_folder(self, folder: _m.Folder):
        res = self.http_client.put(f"/object/folder/{folder.id}", json=folder.model_dump(mode="json"))
        resp = FolderResp.validate_json(res.content)

        if isinstance(resp, _m.ErrorResponse):
            raise Exception(f"Could not get items [{resp.message}]")

        return resp.data

    def post_folder(self, folder: _m.NewFolder):
        res = self.http_client.post("/object/folder", json=folder.model_dump(mode="json"))
        resp = FolderResp.validate_json(res.content)

        if isinstance(resp, _m.ErrorResponse):
            raise Exception(f"Could not get items [{resp.message}]")

        return resp.data

    def del_folder(self, folder: _m.Folder):
        r = self.http_client.delete(f"/object/folder/{folder.id}")
        r.raise_for_status()

    # endregion

    # region Organization

    def get_organization(self, org: _m.Organization | _m.OrgID):
        obj_id = org if isinstance(org, str) else org.id
        return self._get_object(OrgResp, "organization", obj_id)

    def get_organizations(self, search: str | None = None, exact: bool = False):
        params = {
            "search": search,
        }
        return self._get_list(OrgsResp, "organizations", params, exact)

    def find_organization(
        self,
        search: str | None = None,
        exact: bool = False,
    ):
        res = self.get_organizations(search, exact)
        match len(res):
            case 0:
                raise Exception("no organization found")
            case 1:
                return res[0]
            case _:
                raise Exception("multiple organizations matches")

    # endregion

    # region Collections

    def get_collection(self, coll: _m.Collection | _m.CollID):
        obj_id = coll if isinstance(coll, str) else coll.id
        return self._get_object(CollResp, "collection", obj_id)

    def get_collections(self, search: str | None = None, orgID: _m.OrgID | None = None, exact: bool = False):
        params = {
            "organizationId": orgID,
            "search": search,
        }
        endpoint = "collections" if orgID is None else "org-collections"
        return self._get_list(CollsResp, endpoint, params, exact)

    def find_collection(
        self,
        search: str | None = None,
        orgID: _m.OrgID | None = None,
        exact: bool = False,
    ):
        res = self.get_collections(search, orgID, exact)
        match len(res):
            case 0:
                raise Exception("no collection found")
            case 1:
                return res[0]
            case _:
                raise Exception("multiple collections matches")

    def post_collection(self, coll: _m.NewCollection):
        params = {
            "organizationId": coll.org_id,
        }
        res = self.http_client.post("/object/org-collection", json=coll.model_dump(mode="json"), params=params)
        resp = CollResp.validate_json(res.content)

        if isinstance(resp, _m.ErrorResponse):
            raise Exception(f"Could not create obj [{resp.message}]")

        return resp.data

    def put_collection(self, coll: _m.Collection):
        params = {
            "organizationId": coll.org_id,
        }
        res = self.http_client.put(
            f"/object/org-collection/{coll.id}", json=coll.model_dump(mode="json"), params=params
        )
        resp = CollResp.validate_json(res.content)

        if isinstance(resp, _m.ErrorResponse):
            raise Exception(f"Could not get items [{resp.message}]")

        return resp.data

    def del_collection(self, coll: _m.Collection):
        params = {
            "organizationId": coll.org_id,
        }
        res = self.http_client.delete(f"/object/org-collection/{coll.id}", params=params)
        res.raise_for_status()

    # endregion
