from __future__ import annotations

import contextlib
import dataclasses
from typing import Annotated, TypeVar, Union
from urllib.parse import urlunsplit

import httpx
import pydantic
from pydantic import SecretStr as SecretStr
from pydantic import TypeAdapter

import bw_sdk.model as _m
from bw_sdk.model import DBStatus, LinkTarget, Match

T = TypeVar("T")


type RespT[T] = Annotated[
    Union[_m.ValidResponse[T], _m.ErrorResponse],
    pydantic.Field(discriminator="success"),
]

type TmplRespT[T] = Annotated[
    Union[_m.ValidResponse[_m.TemplateObj[T]], _m.ErrorResponse],
    pydantic.Field(discriminator="success"),
]

type ListRespT[T] = Annotated[
    Union[_m.ValidResponse[_m.DataList[T]], _m.ErrorResponse],
    pydantic.Field(discriminator="success"),
]

StrResp = pydantic.TypeAdapter(RespT[_m.StrObj])

UnlockResp = pydantic.TypeAdapter(RespT[_m.UnlockData])
LockResp = pydantic.TypeAdapter(RespT[_m.MessageObj])
SyncResp = pydantic.TypeAdapter(RespT[_m.MessageObj])
StatusResp = pydantic.TypeAdapter(TmplRespT[_m.ServerStatus])

OrgResp = pydantic.TypeAdapter(RespT[_m.Organization])
OrgsResp = pydantic.TypeAdapter(ListRespT[_m.Organization])
CollResp = pydantic.TypeAdapter(RespT[_m.Collection])
CollsResp = pydantic.TypeAdapter(ListRespT[_m.Collection])
FolderResp = pydantic.TypeAdapter(RespT[_m.Folder])
FoldersResp = pydantic.TypeAdapter(ListRespT[_m.Folder])
ItemResp = pydantic.TypeAdapter(RespT[_m.Item])
ItemsResp = pydantic.TypeAdapter(ListRespT[_m.Item])

NewItem = _m.NewItemLogin | _m.NewItemSecureNote

BaseObjT = TypeVar("BaseObjT", bound=_m.BaseObj)


@dataclasses.dataclass
class Client:
    http_client: httpx.Client = dataclasses.field(
        default_factory=lambda: httpx.Client(base_url="http://localhost:8087")
    )

    @contextlib.contextmanager
    def session(self, password: SecretStr | None, sync: bool = True):
        org_status = self.get_status()
        if org_status.status == DBStatus.Locked:
            if password is None:
                raise Exception("locked bw and no password")
            self.unlock(password)
        if sync:
            self.sync()
        yield self
        if org_status.status == DBStatus.Locked:
            self.lock()

    # region Internal

    def _put(
        self,
        validator: TypeAdapter[RespT[T]],
        path: str,
        params: _m.Query | None,
        payload: _m.Payload | _m.BaseObj | None,
    ):
        _params = None if params is None else params.model_dump(mode="json", by_alias=True, exclude_none=True)
        _payload = None if payload is None else payload.model_dump(mode="json", by_alias=True)

        res = self.http_client.put(path, params=_params, json=_payload)

        resp = validator.validate_json(res.content)

        if isinstance(resp, _m.ErrorResponse):
            raise Exception(f"Could not get obj [{resp.message}]")

        return resp.data

    def _post(self, path: str, params: _m.Query | None, payload: _m.Payload | _m.BaseObj | None):
        _params = None if params is None else params.model_dump(mode="json", by_alias=True, exclude_none=True)
        _payload = None if payload is None else payload.model_dump(mode="json", by_alias=True)

        res = self.http_client.post(path, params=_params, json=_payload)
        return res

    def _post_object(
        self,
        validator: TypeAdapter[RespT[T]],
        path: str,
        params: _m.Query | None,
        payload: _m.Payload | _m.BaseObj | None,
    ):
        res = self._post(path, params, payload)

        resp = validator.validate_json(res.content)

        if isinstance(resp, _m.ErrorResponse):
            raise Exception(f"Could not get obj [{resp.message}]")

        return resp.data

    def _delete(self, path: str, params: _m.Query | None):
        _params = None if params is None else params.model_dump(mode="json", by_alias=True, exclude_none=True)
        res = self.http_client.delete(path, params=_params)
        res.raise_for_status()

    def _get(self, validator: TypeAdapter[RespT[T]], path: str, params: _m.Query | None):
        _params = None if params is None else params.model_dump(mode="json", by_alias=True, exclude_none=True)

        res = self.http_client.get(path, params=_params)
        resp = validator.validate_json(res.content)

        if isinstance(resp, _m.ErrorResponse):
            raise Exception(f"Could not get obj [{resp.message}]")

        return resp.data

    def _get_str(self, path: str, params: _m.Query | None) -> str:
        return self._get(StrResp, path, params).data

    def _get_object(
        self, validator: TypeAdapter[RespT[BaseObjT]], obj_type: str, obj_id: str, params: _m.Query | None
    ) -> BaseObjT:
        return self._get(validator, f"/object/{obj_type}/{obj_id}", params)

    def _get_tmpl(self, validator: TypeAdapter[TmplRespT[T]], path: str, params: _m.Query | None) -> T:
        return self._get(validator, path, params).template

    def _get_list(
        self,
        validator: TypeAdapter[ListRespT[T]],
        path: str,
        params: _m.Query | None,
    ) -> list[T]:
        return self._get(validator, path, params).data

    def _get_object_list(
        self,
        validator: TypeAdapter[ListRespT[BaseObjT]],
        obj_type: str,
        params: _m.SearchQuery | None,
        exact: bool,
    ) -> list[BaseObjT]:
        search = None if params is None else params.search

        path = f"/list/object/{obj_type}"

        result = self._get_list(validator, path, params)

        if exact:
            return [x for x in result if x.name == search]
        return result

    # endregion

    # region Misc

    def unlock(self, password: SecretStr):
        payload = _m.UnlockPayload(password=password)
        return self._post_object(UnlockResp, "/unlock", params=None, payload=payload)

    def lock(self):
        return self._post_object(LockResp, "/lock", params=None, payload=None)

    def sync(self):
        return self._post_object(SyncResp, "/sync", params=None, payload=None)

    def get_status(self):
        return self._get_tmpl(StatusResp, "/status", None)

    def get_fingerprint(self):
        return self._get_str("/object/fingerprint/me", None)

    # endregion

    # region Items

    def get_item(self, item: _m.Item | _m.ItemID):
        obj_id = item if isinstance(item, str) else item.id
        return self._get_object(ItemResp, "item", obj_id, None)

    def _get_specific_item(self, item: _m.Item | _m.ItemID, typ: type[_m.ItemT]) -> _m.ItemT:
        obj = self.get_item(item)
        if not isinstance(obj, typ):
            raise Exception("invalid item type")
        return obj

    def get_item_login(self, item: _m.Item | _m.ItemID):
        return self._get_specific_item(item, _m.ItemLogin)

    def get_item_card(self, item: _m.Item | _m.ItemID):
        return self._get_specific_item(item, _m.ItemCard)

    def get_item_securenote(self, item: _m.Item | _m.ItemID):
        return self._get_specific_item(item, _m.ItemSecureNote)

    def get_item_identity(self, item: _m.Item | _m.ItemID):
        return self._get_specific_item(item, _m.ItemIdentity)

    def get_items(
        self,
        search: str | None = None,
        org_id: _m.OrgID | None = None,
        coll_id: _m.CollID | None = None,
        folder_id: _m.FolderID | None = None,
        url: str | None = None,
        trash: bool = False,
        exact: bool = False,
    ):
        params = _m.ItemQuery(
            search=search,
            coll_id=coll_id,
            org_id=org_id,
            folder_id=folder_id,
            url=url,
            trash=trash,
        )

        return self._get_object_list(ItemsResp, "items", params, exact)

    def _get_specific_items(
        self,
        search: str | None,
        org_id: _m.OrgID | None,
        coll_id: _m.CollID | None,
        folder_id: _m.FolderID | None,
        url: str | None,
        trash: bool,
        exact: bool,
        typ: type[_m.ItemT],
    ) -> list[_m.ItemT]:
        objs = self.get_items(search, org_id, coll_id, folder_id, url, trash, exact)
        return [obj for obj in objs if isinstance(obj, typ)]

    def get_item_logins(
        self,
        search: str | None = None,
        org_id: _m.OrgID | None = None,
        coll_id: _m.CollID | None = None,
        folder_id: _m.FolderID | None = None,
        url: str | None = None,
        trash: bool = False,
        exact: bool = False,
    ):
        return self._get_specific_items(search, org_id, coll_id, folder_id, url, trash, exact, _m.ItemLogin)

    def get_item_cards(
        self,
        search: str | None = None,
        org_id: _m.OrgID | None = None,
        coll_id: _m.CollID | None = None,
        folder_id: _m.FolderID | None = None,
        url: str | None = None,
        trash: bool = False,
        exact: bool = False,
    ):
        return self._get_specific_items(search, org_id, coll_id, folder_id, url, trash, exact, _m.ItemCard)

    def get_item_identities(
        self,
        search: str | None = None,
        org_id: _m.OrgID | None = None,
        coll_id: _m.CollID | None = None,
        folder_id: _m.FolderID | None = None,
        url: str | None = None,
        trash: bool = False,
        exact: bool = False,
    ):
        return self._get_specific_items(search, org_id, coll_id, folder_id, url, trash, exact, _m.ItemIdentity)

    def get_item_securenotes(
        self,
        search: str | None = None,
        org_id: _m.OrgID | None = None,
        coll_id: _m.CollID | None = None,
        folder_id: _m.FolderID | None = None,
        url: str | None = None,
        trash: bool = False,
        exact: bool = False,
    ):
        return self._get_specific_items(search, org_id, coll_id, folder_id, url, trash, exact, _m.ItemSecureNote)

    def find_item(
        self,
        search: str | None = None,
        org_id: _m.OrgID | None = None,
        coll_id: _m.CollID | None = None,
        folder_id: _m.FolderID | None = None,
        url: str | None = None,
        trash: bool = False,
        exact: bool = False,
    ):
        res = self.get_items(search, org_id, coll_id, folder_id, url, trash, exact)
        match len(res):
            case 0:
                raise Exception("no item found")
            case 1:
                return res[0]
            case _:
                raise Exception("multiple items matches")

    def _find_specific_item(
        self,
        search: str | None,
        org_id: _m.OrgID | None,
        coll_id: _m.CollID | None,
        folder_id: _m.FolderID | None,
        url: str | None,
        trash: bool,
        exact: bool,
        typ: type[_m.ItemT],
    ) -> _m.ItemT:
        res = self._get_specific_items(search, org_id, coll_id, folder_id, url, trash, exact, typ)
        match len(res):
            case 0:
                raise Exception("no item found")
            case 1:
                return res[0]
            case _:
                raise Exception("multiple items matches")

    def find_item_login(
        self,
        search: str | None,
        org_id: _m.OrgID | None,
        coll_id: _m.CollID | None,
        folder_id: _m.FolderID | None,
        url: str | None,
        trash: bool,
        exact: bool,
    ):
        return self._find_specific_item(search, org_id, coll_id, folder_id, url, trash, exact, _m.ItemLogin)

    def find_item_card(
        self,
        search: str | None,
        org_id: _m.OrgID | None,
        coll_id: _m.CollID | None,
        folder_id: _m.FolderID | None,
        url: str | None,
        trash: bool,
        exact: bool,
    ):
        return self._find_specific_item(search, org_id, coll_id, folder_id, url, trash, exact, _m.ItemCard)

    def find_item_identity(
        self,
        search: str | None,
        org_id: _m.OrgID | None,
        coll_id: _m.CollID | None,
        folder_id: _m.FolderID | None,
        url: str | None,
        trash: bool,
        exact: bool,
    ):
        return self._find_specific_item(search, org_id, coll_id, folder_id, url, trash, exact, _m.ItemIdentity)

    def find_item_securenote(
        self,
        search: str | None,
        org_id: _m.OrgID | None,
        coll_id: _m.CollID | None,
        folder_id: _m.FolderID | None,
        url: str | None,
        trash: bool,
        exact: bool,
    ):
        return self._find_specific_item(search, org_id, coll_id, folder_id, url, trash, exact, _m.ItemSecureNote)

    def put_item(self, item: _m.ItemT):
        return self._put(ItemResp, f"/object/item/{item.id}", params=None, payload=item)

    def post_item(self, item: NewItem):
        return self._post_object(ItemResp, "/object/item", params=None, payload=item)

    def del_item(self, item: _m.Item | _m.ItemID):
        obj_id = item if isinstance(item, str) else item.id
        self._delete(f"/object/item/{obj_id}", params=None)

    def restore_item(self, item: _m.Item | _m.ItemID):
        obj_id = item if isinstance(item, str) else item.id
        res = self._post(f"/restore/item/{obj_id}", params=None, payload=None)
        res.raise_for_status()

    # endregion

    # region Folders

    def get_folder(self, folder: _m.Folder | _m.FolderID):
        obj_id = folder if isinstance(folder, str) else folder.id
        return self._get_object(FolderResp, "folder", obj_id, None)

    def get_folders(self, search: str | None = None, exact: bool = False):
        params = _m.FoldersQuery(search=search)

        return self._get_object_list(FoldersResp, "folders", params, exact)

    def find_folder(self, search: str | None = None, exact: bool = False):
        res = self.get_folders(search, exact)
        match len(res):
            case 0:
                raise Exception("no folder found")
            case 1:
                return res[0]
            case _:
                raise Exception("multiple folders matches")

    def put_folder(self, obj: _m.Folder):
        return self._put(FolderResp, f"/object/folder/{obj.id}", params=None, payload=obj)

    def post_folder(self, obj: _m.NewFolder):
        return self._post_object(FolderResp, "/object/folder", params=None, payload=obj)

    def del_folder(self, obj: _m.Folder | _m.FolderID):
        obj_id = obj if isinstance(obj, str) else obj.id
        self._delete(f"/object/folder/{obj_id}", params=None)

    # endregion

    # region Organization

    def get_organization(self, obj: _m.Organization | _m.OrgID):
        obj_id = obj if isinstance(obj, str) else obj.id
        return self._get_object(OrgResp, "organization", obj_id, None)

    def get_organizations(self, search: str | None = None, exact: bool = False):
        params = _m.OrganizationsQuery(search=search)
        return self._get_object_list(OrgsResp, "organizations", params, exact)

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

    def get_collection(self, obj: _m.Collection | _m.CollID):
        obj_id = obj if isinstance(obj, str) else obj.id
        return self._get_object(CollResp, "collection", obj_id, None)

    def get_collections(self, search: str | None = None, org_id: _m.OrgID | None = None, exact: bool = False):
        params = _m.CollectionsQuery(search=search, org_id=org_id)
        endpoint = "collections" if params.org_id is None else "org-collections"
        return self._get_object_list(CollsResp, endpoint, params, exact)

    def find_collection(
        self,
        search: str | None = None,
        org_id: _m.OrgID | None = None,
        exact: bool = False,
    ):
        res = self.get_collections(search, org_id, exact)
        match len(res):
            case 0:
                raise Exception("no collection found")
            case 1:
                return res[0]
            case _:
                raise Exception("multiple collections matches")

    def post_collection(self, obj: _m.NewCollection):
        params = _m.OrgCollectionQuery(org_id=obj.org_id)
        return self._post_object(CollResp, "/object/org-collection", params=params, payload=obj)

    def put_collection(self, obj: _m.Collection):
        params = _m.OrgCollectionQuery(org_id=obj.org_id)
        return self._put(CollResp, f"/object/org-collection/{obj.id}", params=params, payload=obj)

    def del_collection(self, obj: _m.Collection):
        params = _m.OrgCollectionQuery(org_id=obj.org_id)
        self._delete(f"/object/org-collection/{obj.id}", params=params)

    # endregion


def NewClient(scheme: str = "http", host: str = "localhost", port: int = 8087, path: str = ""):
    base_url = urlunsplit((scheme, f"{host}:{port}", path, "", ""))
    return Client(http_client=httpx.Client(base_url=base_url))


__all__ = ["DBStatus", "Client", "LinkTarget", "Match"]
