from __future__ import annotations

import enum
from datetime import datetime
from typing import Annotated, Any, Callable, Generic, Literal, NewType, TypeVar, Union

import pydantic
from pydantic import SecretStr as SecretStr

T = TypeVar("T")

# region Type Values

ItemID = NewType("ItemID", str)
CollID = NewType("CollID", str)
OrgID = NewType("OrgID", str)
FolderID = NewType("FolderID", str)
GroupID = NewType("GroupID", str)
UserID = NewType("UserID", str)


class DBStatus(enum.StrEnum):
    Locked = "locked"
    Unlocked = "unlocked"


class LinkTarget(enum.IntEnum):
    Username = 100
    Password = 101


class Match(enum.IntEnum):
    BaseDomain = 0
    Host = 1
    StartsWith = 2
    Regexp = 3
    Excact = 4
    Never = 5


# endregion


class BaseModel(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(populate_by_name=True)


# region Submodels


class GroupLink(BaseModel):
    id: GroupID
    readOnly: bool = False
    hidePasswords: bool = False


class PasswordHist(BaseModel):
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


class UriMatch(BaseModel):
    match: Match | None
    uri: str | None


# region Item Data


class LoginData(BaseModel):
    uris: list[UriMatch] | None = None
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


class SecureNoteData(BaseModel):
    type: Literal[0] = pydantic.Field(repr=False)


class CardData(BaseModel):
    cardholderName: str | None
    brand: str | None
    number: str | None
    expMonth: str | None
    expYear: str | None
    code: str | None


class IdentityData(BaseModel):
    title: str | None
    firstName: str | None
    middleName: str | None
    lastName: str | None
    address1: str | None
    address2: str | None
    address3: str | None
    city: str | None
    state: str | None
    postalCode: str | None
    country: str | None
    company: str | None
    email: str | None
    phone: str | None
    ssn: str | None
    username: str | None
    passportNumber: str | None
    licenseNumber: str | None


# endregion


# region Fields


class FieldBase(BaseModel):
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


class FieldLink(FieldBase):
    value: None = pydantic.Field(default=None, repr=False)
    type: Literal[3] = pydantic.Field(default=3, repr=False)
    linkedId: LinkTarget


Field = Annotated[
    Union[FieldText, FieldHidden, FieldBool, FieldLink],
    pydantic.Field(discriminator="type"),
]


# endregion


# endregion

# region Responses


class ValidResponse(BaseModel, Generic[T]):
    success: Literal[True] = pydantic.Field(repr=False)
    data: T


class ErrorResponse(BaseModel):
    success: Literal[False] = pydantic.Field(repr=False)
    message: str


# endregion

# region Generic Objects


class StrObj(BaseModel):
    object: Literal["string"] = pydantic.Field(repr=False)
    data: str


class TemplateObj(BaseModel, Generic[T]):
    object: Literal["template"] = pydantic.Field(repr=False)
    template: T


class DataList(BaseModel, Generic[T]):
    object: Literal["list"] = pydantic.Field(repr=False)
    data: list[T]


class MessageObj(BaseModel):
    object: Literal["message"] = pydantic.Field(repr=False)
    no_color: bool = pydantic.Field(alias=str("noColor"))
    title: str
    message: str | None


# endregion


class UnlockData(MessageObj):
    raw: str


class BaseObj(BaseModel):
    name: str


class ItemTemplate(BaseObj):
    object: Literal["item"] = pydantic.Field(repr=False)

    password_history: list[PasswordHist] | None = pydantic.Field(exclude=True, alias=str("passwordHistory"))
    revised_at: datetime = pydantic.Field(exclude=True, alias=str("revisionDate"))
    created_at: datetime = pydantic.Field(exclude=True, alias=str("creationDate"))
    deleted_at: datetime | None = pydantic.Field(exclude=True, alias=str("deletedDate"))

    id: ItemID
    org_id: OrgID | None = pydantic.Field(alias=str("organizationId"))
    coll_ids: list[CollID] = pydantic.Field(alias=str("collectionIds"))
    folder_id: FolderID | None = pydantic.Field(alias=str("folderId"))
    notes: str | None
    favorite: bool
    reprompt: int
    fields: list[Field] = pydantic.Field(default_factory=list)

    @pydantic.model_serializer(mode="wrap")
    def serialize(self, fn: Callable[[ItemTemplate], dict[str, Any]]):
        dct = fn(self)
        if not (len(dct["fields"]) > 0):
            del dct["fields"]
        return dct


class ItemLogin(ItemTemplate):
    type: Literal[1] = pydantic.Field(repr=False)
    login: LoginData


class ItemSecureNote(ItemTemplate):
    type: Literal[2] = pydantic.Field(repr=False)
    secureNote: SecureNoteData


class ItemCard(ItemTemplate):
    type: Literal[3] = pydantic.Field(repr=False)
    card: CardData


class ItemIdentity(ItemTemplate):
    type: Literal[4] = pydantic.Field(repr=False)
    identity: IdentityData


Item = Annotated[
    Union[ItemLogin, ItemSecureNote, ItemCard, ItemIdentity],
    pydantic.Field(discriminator="type"),
]
ItemT = TypeVar("ItemT", ItemLogin, ItemSecureNote, ItemCard, ItemIdentity)


class NewItemBase(BaseObj):
    org_id: OrgID | None = pydantic.Field(default=None, alias=str("organizationId"))
    coll_ids: list[CollID] = pydantic.Field(default_factory=list, alias=str("collectionIds"))
    folder_id: FolderID | None = pydantic.Field(default=None, alias=str("folderId"))
    notes: str | None = None
    favorite: bool = False
    reprompt: int = 0
    fields: list[Field] = pydantic.Field(default_factory=list)


class NewItemLogin(NewItemBase):
    type: Literal[1] = pydantic.Field(default=1, repr=False)

    login: LoginData = pydantic.Field(default_factory=LoginData)


class NewItemSecureNote(NewItemBase):
    type: Literal[2] = pydantic.Field(default=2, repr=False)

    secure_note: SecureNoteData = pydantic.Field(alias=str("secureNote"))


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
    org_id: OrgID = pydantic.Field(alias=str("organizationId"))
    ext_id: str | None = pydantic.Field(alias=str("externalId"))
    groups: list[GroupLink] = pydantic.Field(default_factory=list)

    @pydantic.model_serializer(mode="wrap")
    def serialize(self, fn: Callable[[Collection], dict[str, Any]]):
        dct = fn(self)
        if not (len(dct["groups"]) > 0):
            del dct["groups"]
        return dct


class NewCollection(BaseObj):
    org_id: OrgID = pydantic.Field(alias=str("organizationId"))
    ext_id: str | None = pydantic.Field(alias=str("externalId"))
    groups: list[GroupLink] = pydantic.Field(default_factory=list)

    @pydantic.model_serializer(mode="wrap")
    def serialize(self, fn: Callable[[NewCollection], dict[str, Any]]):
        dct = fn(self)
        if not (len(dct["groups"]) > 0):
            del dct["groups"]
        return dct


class ServerStatus(BaseModel):
    serverUrl: str | None
    lastSync: datetime
    userEmail: str
    userId: UserID
    status: DBStatus


# region Payload
class Payload(BaseModel):
    pass


class Query(BaseModel):
    pass


class SearchQuery(Query):
    search: str | None = None


class UnlockPayload(Payload):
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


class FoldersQuery(SearchQuery):
    pass


class OrgCollectionQuery(Query):
    org_id: OrgID | None = pydantic.Field(default=None, alias=str("organizationId"))


class OrganizationsQuery(SearchQuery):
    pass


class CollectionsQuery(SearchQuery):
    org_id: OrgID | None = pydantic.Field(default=None, alias=str("organizationId"))


class ItemQuery(SearchQuery):
    org_id: OrgID | None = pydantic.Field(default=None, alias=str("organizationId"))
    coll_id: CollID | None = pydantic.Field(default=None, alias=str("collectionId"))
    folder_id: FolderID | None = pydantic.Field(default=None, alias=str("folderid"))
    url: str | None = None
    trash: bool = False
    search: str | None = None

    @pydantic.model_serializer(mode="wrap")
    def serialize(self, fn: Callable[[ItemQuery], dict[str, Any]]):
        dct = fn(self)
        if dct["trash"] is False:
            del dct["trash"]
        return dct


# endregion
