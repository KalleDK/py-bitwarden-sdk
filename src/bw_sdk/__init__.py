import dataclasses
import enum
from datetime import datetime
from typing import Annotated, Any, Generic, Literal, NewType, TypeVar, Union

import httpx
import pydantic

T = TypeVar("T")

ItemID = NewType("ItemID", str)
CollID = NewType("CollID", str)
OrgID = NewType("OrdID", str)
FolderID = NewType("FolderID", str)

SecretStr = Annotated[pydantic.SecretStr, pydantic.BeforeValidator(lambda v: pydantic.SecretStr(v))]
OptSecretStr = Annotated[
    pydantic.SecretStr | None, pydantic.BeforeValidator(lambda v: None if v is None else pydantic.SecretStr(v))
]


class ValidResponse(pydantic.BaseModel, Generic[T]):
    success: Literal[True]
    data: T


class ErrorResponse(pydantic.BaseModel):
    success: Literal[False]
    message: str


class DataList(pydantic.BaseModel, Generic[T]):
    object: Literal["list"]
    data: list[T]


class UnlockData(pydantic.BaseModel):
    noColor: bool
    object: str
    title: str
    message: str
    raw: str


class FieldBase(pydantic.BaseModel):
    name: str | None


class FieldText(FieldBase):
    value: str | None
    type: Literal[0] = pydantic.Field(default=0, repr=False)


class FieldHidden(FieldBase):
    value: OptSecretStr
    type: Literal[1] = pydantic.Field(default=1, repr=False)

    @pydantic.field_serializer("value", when_used="json")
    def dump_secret(self, v: OptSecretStr):
        if v is None:
            return None
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
    password: OptSecretStr

    @pydantic.field_serializer("password", when_used="json")
    def dump_secret(self, v: OptSecretStr):
        if v is None:
            return None
        return v.get_secret_value()


class ItemTemplate(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")
    object: Literal["item"] = "item"

    passwordHistory: list[PasswordHist] | None
    revisionDate: datetime
    creationDate: datetime
    deletedDate: datetime | None
    id: ItemID
    organizationId: OrgID | None
    collectionIds: list[CollID]
    folderId: FolderID | None
    name: str
    notes: str | None
    favorite: bool
    reprompt: int
    fields: list[Field] | None = None


class LoginData(pydantic.BaseModel):
    uris: list[Any] | None = None
    username: str | None = None
    password: OptSecretStr | None = None
    totp: str | None = None

    @pydantic.field_serializer("password", when_used="json")
    def dump_secret(self, v: OptSecretStr):
        if v is None:
            return None
        return v.get_secret_value()


class SecureNoteData(pydantic.BaseModel):
    type: int


class ItemLogin(ItemTemplate):
    type: Literal[1]
    login: LoginData


class ItemSecureNote(ItemTemplate):
    type: Literal[2]
    secureNote: SecureNoteData


class ItemCard(ItemTemplate):
    type: Literal[3]
    card: Any


class ItemIdentity(ItemTemplate):
    type: Literal[4]
    identity: Any


Item = Annotated[
    Union[ItemLogin, ItemSecureNote, ItemCard, ItemIdentity],
    pydantic.Field(discriminator="type"),
]


class NewItem(pydantic.BaseModel):
    name: str
    organizationId: str | None = None
    collectionIds: list[str] = pydantic.Field(default_factory=list)
    folderId: str | None = None
    notes: str | None = None
    favorite: bool = False
    reprompt: int = 0
    fields: list[FieldBase] | None = None


class NewItemLogin(NewItem):
    type: Literal[1] = 1
    login: LoginData = pydantic.Field(default_factory=LoginData)


class NewItemSecureNote(NewItem):
    type: Literal[2] = 2
    secureNote: SecureNoteData


NewItems = NewItemLogin | NewItemSecureNote
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


@dataclasses.dataclass
class Client:
    http_client: httpx.Client = dataclasses.field(
        default_factory=lambda: httpx.Client(base_url="http://localhost:8087")
    )

    def unlock(self, password: str):
        res = self.http_client.post("/unlock", json={"password": password})
        resp = UnlockResp.validate_json(res.content)

        if isinstance(resp, ErrorResponse):
            raise Exception(f"Could not unlock bitwarden [{resp.message}]")

        return resp.data.raw

    def lock(self):
        res = self.http_client.post("/lock")
        resp = LockResp.validate_json(res.content)

        if isinstance(resp, ErrorResponse):
            raise Exception("Could not lock bitwarden")

    def get_item(self, itemID: str):
        res = self.http_client.get(f"/object/item/{itemID}")
        resp = ItemResp.validate_json(res.content)

        if isinstance(resp, ErrorResponse):
            raise Exception(f"Could not get items [{resp.message}]")

        return resp.data

    def put_item(self, item: Item):
        res = self.http_client.put(f"/object/item/{item.id}", json=item.model_dump(mode="json"))

        resp = ItemResp.validate_json(res.content)

        if isinstance(resp, ErrorResponse):
            raise Exception(f"Could not get items [{resp.message}]")

        return resp.data

    def post_item(self, item: NewItems):
        res = self.http_client.post("/object/item", json=item.model_dump(mode="json"))
        resp = ItemResp.validate_json(res.content)

        if isinstance(resp, ErrorResponse):
            raise Exception(f"Could not get items [{resp.message}]")

        return resp.data

    def find_item(
        self,
        orgID: str | None = None,
        collID: str | None = None,
        folderID: str | None = None,
        url: str | None = None,
        search: str | None = None,
    ):
        res = self.get_items(orgID, collID, folderID, url, search)
        match len(res):
            case 0:
                raise Exception("no item found")
            case 1:
                return res[0]
            case _:
                raise Exception("multiple items matches")

    def get_items(
        self,
        orgID: str | None = None,
        collID: str | None = None,
        folderID: str | None = None,
        url: str | None = None,
        search: str | None = None,
    ):
        params = {
            "organizationId": orgID,
            "collectionId": collID,
            "folderid": folderID,
            "url": url,
            "search": search,
        }
        params = {k: v for k, v in params.items() if v is not None}

        res = self.http_client.get("/list/object/items", params=params)

        resp = ItemsResp.validate_json(res.content)

        if isinstance(resp, ErrorResponse):
            raise Exception(f"Could not get items [{resp.message}]")

        return resp.data.data

    def del_item(self, item: Item):
        r = self.http_client.delete(f"/object/item/{item.id}")
        r.raise_for_status()

    def restore_item(self, itemID: str):
        r = self.http_client.post(f"/restore/item/{itemID}")
        r.raise_for_status()
