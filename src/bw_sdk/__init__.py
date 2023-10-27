import dataclasses
import enum
from datetime import datetime
from typing import Annotated, Any, Generic, Literal, NewType, Protocol, TypeVar, Union

import httpx
import pydantic
from pydantic import BaseModel
from pydantic import SecretStr as SecretStr

T = TypeVar("T")

ItemID = NewType("ItemID", str)
CollID = NewType("CollID", str)
OrgID = NewType("OrgID", str)
FolderID = NewType("FolderID", str)
GroupID = NewType("GroupID", str)
UserID = NewType("UserID", str)


class DBStatus(enum.StrEnum):
    Locked = "locked"
    Unlocked = "unlocked"


class ValidResponse(pydantic.BaseModel, Generic[T]):
    success: Literal[True] = pydantic.Field(repr=False)
    data: T


class ErrorResponse(pydantic.BaseModel):
    success: Literal[False] = pydantic.Field(repr=False)
    message: str


class StrObj(pydantic.BaseModel):
    object: Literal["string"] = pydantic.Field(repr=False)
    data: str


class TemplateObj(pydantic.BaseModel, Generic[T]):
    object: Literal["template"] = pydantic.Field(repr=False)
    template: T


class DataList(pydantic.BaseModel, Generic[T]):
    object: Literal["list"] = pydantic.Field(repr=False)
    data: list[T]


class UnlockData(pydantic.BaseModel):
    noColor: bool
    object: str
    title: str
    message: str
    raw: str


class BaseObj(pydantic.BaseModel):
    name: str


class GroupLink(BaseModel):
    id: GroupID
    readOnly: bool = False
    hidePasswords: bool = False


class FieldBase(pydantic.BaseModel):
    name: str | None


class FieldText(FieldBase):
    value: str | None
    type: Literal[0] = pydantic.Field(default=0, repr=False)


class FieldHidden(FieldBase):
    value: SecretStr | None
    type: Literal[1] = pydantic.Field(default=1, repr=False)

    @pydantic.field_validator("value", mode="before")
    @classmethod
    def must_be_secret(cls, value: str | SecretStr | None):
        if value is None or isinstance(value, SecretStr):
            return value
        return SecretStr(value)

    @pydantic.field_serializer("value", when_used="json-unless-none")
    def dump_secret(self, v: SecretStr):
        return v.get_secret_value()


class FieldBool(FieldBase):
    value: bool
    type: Literal[2] = pydantic.Field(default=2, repr=False)

    @pydantic.field_serializer("value", when_used="json")
    def dump_bool(self, v: bool):
        return "true" if v else "false"


class LinkTarget(enum.IntEnum):
    Username = 100
    Password = 101


class FieldLink(FieldBase):
    value: None = pydantic.Field(default=None, repr=False)
    type: Literal[3] = pydantic.Field(default=3, repr=False)
    linkedId: LinkTarget


Field = Annotated[
    Union[FieldText, FieldHidden, FieldBool, FieldLink],
    pydantic.Field(discriminator="type"),
]


class PasswordHist(pydantic.BaseModel):
    lastUsedDate: datetime
    password: SecretStr

    @pydantic.field_validator("password", mode="before")
    @classmethod
    def must_be_secret(cls, value: str | SecretStr):
        if isinstance(value, SecretStr):
            return value
        return SecretStr(value)

    @pydantic.field_serializer("password", when_used="json")
    def dump_secret(self, v: SecretStr):
        return v.get_secret_value()


class ItemTemplate(BaseObj):
    model_config = pydantic.ConfigDict(extra="forbid")
    object: Literal["item"] = pydantic.Field(repr=False)

    passwordHistory: list[PasswordHist] | None
    revisionDate: datetime
    creationDate: datetime
    deletedDate: datetime | None
    id: ItemID
    organizationId: OrgID | None
    collectionIds: list[CollID]
    folderId: FolderID | None
    notes: str | None
    favorite: bool
    reprompt: int
    fields: list[Field] | None = None


class LoginData(pydantic.BaseModel):
    uris: list[Any] | None = None
    username: str | None = None
    password: SecretStr | None = None
    totp: str | None = None

    @pydantic.field_validator("password", mode="before")
    @classmethod
    def must_be_secret(cls, value: str | SecretStr | None):
        if value is None or isinstance(value, SecretStr):
            return value
        return SecretStr(value)

    @pydantic.field_serializer("password", when_used="json-unless-none")
    def dump_secret(self, value: SecretStr):
        return value.get_secret_value()


class SecureNoteData(pydantic.BaseModel):
    type: Literal[0] = pydantic.Field(repr=False)


class ItemLogin(ItemTemplate):
    type: Literal[1] = pydantic.Field(repr=False)
    login: LoginData


class ItemSecureNote(ItemTemplate):
    type: Literal[2] = pydantic.Field(repr=False)
    secureNote: SecureNoteData


class ItemCard(ItemTemplate):
    type: Literal[3] = pydantic.Field(repr=False)
    card: Any


class ItemIdentity(ItemTemplate):
    type: Literal[4] = pydantic.Field(repr=False)
    identity: Any


Item = Annotated[
    Union[ItemLogin, ItemSecureNote, ItemCard, ItemIdentity],
    pydantic.Field(discriminator="type"),
]


class NewItemBase(pydantic.BaseModel):
    name: str
    organizationId: str | None = None
    collectionIds: list[str] = pydantic.Field(default_factory=list)
    folderId: str | None = None
    notes: str | None = None
    favorite: bool = False
    reprompt: int = 0
    fields: list[Field] | None = None


class NewItemLogin(NewItemBase):
    type: Literal[1] = pydantic.Field(default=1, repr=False)
    login: LoginData = pydantic.Field(default_factory=LoginData)


class NewItemSecureNote(NewItemBase):
    type: Literal[2] = pydantic.Field(default=2, repr=False)
    secureNote: SecureNoteData


class Folder(BaseObj):
    object: Literal["folder"] = pydantic.Field(default="folder", repr=False)
    id: FolderID


class NewFolder(BaseObj):
    pass


class Organization(BaseObj):
    object: Literal["organization"] = pydantic.Field(default="organization", repr=False)
    id: OrgID
    status: int
    type: int
    enabled: bool


class Collection(BaseObj):
    object: Literal["collection"] | Literal["org-collection"] = pydantic.Field(repr=False)
    id: CollID
    organizationId: OrgID
    externalId: str | None
    groups: list[GroupLink] | None = None


class NewCollection(BaseObj):
    organizationId: OrgID
    externalId: str | None = None
    groups: list[GroupLink] | None = None


class ServerStatus(BaseModel):
    serverUrl: str | None
    lastSync: datetime
    userEmail: str
    userId: UserID
    status: DBStatus


StrResp = pydantic.TypeAdapter(
    Annotated[
        Union[ValidResponse[StrObj], ErrorResponse],
        pydantic.Field(discriminator="success"),
    ]
)

StatusResp = pydantic.TypeAdapter(
    Annotated[
        Union[ValidResponse[TemplateObj[ServerStatus]], ErrorResponse],
        pydantic.Field(discriminator="success"),
    ]
)

OrgResp = pydantic.TypeAdapter(
    Annotated[
        Union[ValidResponse[Organization], ErrorResponse],
        pydantic.Field(discriminator="success"),
    ]
)
OrgsResp = pydantic.TypeAdapter(
    Annotated[
        Union[ValidResponse[DataList[Organization]], ErrorResponse],
        pydantic.Field(discriminator="success"),
    ]
)

CollResp = pydantic.TypeAdapter(
    Annotated[
        Union[ValidResponse[Collection], ErrorResponse],
        pydantic.Field(discriminator="success"),
    ]
)
CollsResp = pydantic.TypeAdapter(
    Annotated[
        Union[ValidResponse[DataList[Collection]], ErrorResponse],
        pydantic.Field(discriminator="success"),
    ]
)


FolderResp = pydantic.TypeAdapter(
    Annotated[
        Union[ValidResponse[Folder], ErrorResponse],
        pydantic.Field(discriminator="success"),
    ]
)
FoldersResp = pydantic.TypeAdapter(
    Annotated[
        Union[ValidResponse[DataList[Folder]], ErrorResponse],
        pydantic.Field(discriminator="success"),
    ]
)

NewItem = NewItemLogin | NewItemSecureNote
UnlockResp = pydantic.TypeAdapter(
    Annotated[
        Union[ValidResponse[UnlockData], ErrorResponse],
        pydantic.Field(discriminator="success"),
    ]
)
LockResp = pydantic.TypeAdapter(
    Annotated[
        Union[ValidResponse[Any], ErrorResponse],
        pydantic.Field(discriminator="success"),
    ]
)
ItemResp = pydantic.TypeAdapter(
    Annotated[
        Union[ValidResponse[Item], ErrorResponse],
        pydantic.Field(discriminator="success"),
    ]
)
ItemsResp = pydantic.TypeAdapter(
    Annotated[
        Union[ValidResponse[DataList[Item]], ErrorResponse],
        pydantic.Field(discriminator="success"),
    ]
)

BaseObjT = TypeVar("BaseObjT", bound=BaseObj)


class ValidateObj(Protocol[BaseObjT]):
    def validate_json(
        self, __data: str | bytes, *, strict: bool | None = None, context: dict[str, Any] | None = None
    ) -> ValidResponse[BaseObjT] | ErrorResponse:
        ...


class ValidateList(Protocol[BaseObjT]):
    def validate_json(
        self, __data: str | bytes, *, strict: bool | None = None, context: dict[str, Any] | None = None
    ) -> ValidResponse[DataList[BaseObjT]] | ErrorResponse:
        ...


@dataclasses.dataclass
class Client:
    http_client: httpx.Client = dataclasses.field(
        default_factory=lambda: httpx.Client(base_url="http://localhost:8087")
    )

    def unlock(self, password: pydantic.SecretStr):
        res = self.http_client.post("/unlock", json={"password": password.get_secret_value()})
        resp = UnlockResp.validate_json(res.content)

        if isinstance(resp, ErrorResponse):
            raise Exception(f"Could not unlock bitwarden [{resp.message}]")

        return resp.data.raw

    def lock(self):
        res = self.http_client.post("/lock")
        resp = LockResp.validate_json(res.content)

        if isinstance(resp, ErrorResponse):
            raise Exception("Could not lock bitwarden")

    def sync(self):
        res = self.http_client.post("/sync")
        res.raise_for_status()

    def get_status(self):
        res = self.http_client.get("/status")
        resp = StatusResp.validate_json(res.content)

        if isinstance(resp, ErrorResponse):
            raise Exception(f"Could not get obj [{resp.message}]")

        return resp.data.template

    def get_fingerprint(self):
        return self._get_str("/object/fingerprint/me")

    # region Internal

    def _get_str(self, path: str) -> str:
        res = self.http_client.get(path)
        resp = StrResp.validate_json(res.content)

        if isinstance(resp, ErrorResponse):
            raise Exception(f"Could not get obj [{resp.message}]")

        return resp.data.data

    def _get_object(self, validator: ValidateObj[BaseObjT], obj_type: str, obj_id: str) -> BaseObjT:
        res = self.http_client.get(f"/object/{obj_type}/{obj_id}")
        resp = validator.validate_json(res.content)

        if isinstance(resp, ErrorResponse):
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

        if isinstance(resp, ErrorResponse):
            raise Exception(f"Could not get objs [{resp.message}]")

        if exact:
            return [x for x in resp.data.data if x.name == search]
        return resp.data.data

    # endregion

    # region Items

    def get_item(self, item: Item | ItemID):
        obj_id = item if isinstance(item, str) else item.id
        return self._get_object(ItemResp, "item", obj_id)

    def get_items(
        self,
        search: str | None = None,
        orgID: OrgID | None = None,
        collID: CollID | None = None,
        folderID: FolderID | None = None,
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
        orgID: OrgID | None = None,
        collID: CollID | None = None,
        folderID: FolderID | None = None,
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

    def put_item(self, item: Item):
        res = self.http_client.put(f"/object/item/{item.id}", json=item.model_dump(mode="json"))

        resp = ItemResp.validate_json(res.content)

        if isinstance(resp, ErrorResponse):
            raise Exception(f"Could not get items [{resp.message}]")

        return resp.data

    def post_item(self, item: NewItem):
        res = self.http_client.post("/object/item", json=item.model_dump(mode="json"))
        resp = ItemResp.validate_json(res.content)

        if isinstance(resp, ErrorResponse):
            raise Exception(f"Could not get items [{resp.message}]")

        return resp.data

    def del_item(self, item: Item | ItemID):
        item_id = item if isinstance(item, str) else item.id
        r = self.http_client.delete(f"/object/item/{item_id}")
        r.raise_for_status()

    def restore_item(self, item: Item | ItemID):
        item_id = item if isinstance(item, str) else item.id
        r = self.http_client.post(f"/restore/item/{item_id}")
        r.raise_for_status()

    # endregion

    # region Folders

    def get_folder(self, folder: Folder | FolderID):
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

    def put_folder(self, folder: Folder):
        res = self.http_client.put(f"/object/folder/{folder.id}", json=folder.model_dump(mode="json"))
        resp = FolderResp.validate_json(res.content)

        if isinstance(resp, ErrorResponse):
            raise Exception(f"Could not get items [{resp.message}]")

        return resp.data

    def post_folder(self, folder: NewFolder):
        res = self.http_client.post("/object/folder", json=folder.model_dump(mode="json"))
        resp = FolderResp.validate_json(res.content)

        if isinstance(resp, ErrorResponse):
            raise Exception(f"Could not get items [{resp.message}]")

        return resp.data

    def del_folder(self, folder: Folder):
        r = self.http_client.delete(f"/object/folder/{folder.id}")
        r.raise_for_status()

    # endregion

    # region Organization

    def get_organization(self, org: Organization | OrgID):
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

    def get_collection(self, coll: Collection | CollID):
        obj_id = coll if isinstance(coll, str) else coll.id
        return self._get_object(CollResp, "collection", obj_id)

    def get_collections(self, search: str | None = None, orgID: OrgID | None = None, exact: bool = False):
        params = {
            "organizationId": orgID,
            "search": search,
        }
        endpoint = "collections" if orgID is None else "org-collections"
        return self._get_list(CollsResp, endpoint, params, exact)

    def find_collection(
        self,
        search: str | None = None,
        orgID: OrgID | None = None,
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

    def post_collection(self, coll: NewCollection):
        params = {
            "organizationId": coll.organizationId,
        }
        res = self.http_client.post("/object/org-collection", json=coll.model_dump(mode="json"), params=params)
        resp = CollResp.validate_json(res.content)

        if isinstance(resp, ErrorResponse):
            raise Exception(f"Could not create obj [{resp.message}]")

        return resp.data

    def put_collection(self, coll: Collection):
        params = {
            "organizationId": coll.organizationId,
        }
        res = self.http_client.put(
            f"/object/org-collection/{coll.id}", json=coll.model_dump(mode="json"), params=params
        )
        resp = CollResp.validate_json(res.content)

        if isinstance(resp, ErrorResponse):
            raise Exception(f"Could not get items [{resp.message}]")

        return resp.data

    def del_collection(self, coll: Collection):
        params = {
            "organizationId": coll.organizationId,
        }
        res = self.http_client.delete(f"/object/org-collection/{coll.id}", params=params)
        res.raise_for_status()

    # endregion
