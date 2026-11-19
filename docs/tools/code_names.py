"""Which C# name a piece of text in code font means.

The dev docs writes `CreatePersonHandler` or `CreatePersonHandler.Handle()` in code font. Such a
name becomes a link into the code reference, and the code reference lists, under a type, the
sections of the companion that mention it. Both directions ask this module what a piece of text
means, so they cannot disagree.

What is understood (resolve() below):

  a full name                                `StargateAPI.Business.Data.Person`
  the short name of a type                   `Person`, `Result<T>`
      but only when one type has that name:  a name that two types share is left alone
  a member written with its type             `CreatePersonHandler.Handle()`, `OrderStatus.Failed`

A member on its own (`Handle`, `Id`) is not understood: many types have a member of that name, and
the text does not say which one is meant.

Names are kept the way the code reference files them. A generic type carries the number of its
type parameters there: Result<T> is "Shop.Common.Result-1".
"""
import re
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree

NAME = re.compile(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*")
CALL = re.compile(r"\(.*\)$")                                   # "(reason, now)" at the end
GENERIC_ARGUMENTS = re.compile(r"\s*<[^<>]*(?:<[^<>]*>[^<>]*)*>")   # "<T>", "<List<Order>>", "< T >"
ARITY = re.compile(r"-\d+")                                     # the "-1" of "Result-1"

TYPE_ROLES = ("cs:class", "cs:struct", "cs:record", "cs:interface", "cs:enum")
MEMBER_ROLES = ("cs:function", "cs:property", "cs:var", "cs:enumerator", "cs:event")


class CodeNames:
    def __init__(self):
        self.written = {}                 # a full name as people write it ("A.B.Result") -> as it is filed ("A.B.Result-1")
        self.types = set()                # the filed names of all types
        self.short = defaultdict(set)     # "Result" -> the types with that short name
        self.members = defaultdict(set)   # "Result.NotFound" -> the members written like that
        self.owners = {}                  # a member -> the type it belongs to

    def add_namespace(self, name):
        self.written.setdefault(name, name)

    def add_type(self, name):
        plain = ARITY.sub("", name)
        self.written[plain] = name        # a type goes before a member with the same full name (its constructor)
        self.types.add(name)
        self.short[plain.rsplit(".", 1)[-1]].add(name)

    def add_member(self, name, owner=None):
        plain = ARITY.sub("", name)
        self.written.setdefault(plain, name)
        self.members[".".join(plain.split(".")[-2:])].add(name)
        self.owners[name] = owner or name.rsplit(".", 1)[0]

    def resolve(self, text):
        """The filed name that `text` means, or None when it is not a name or not clear which one."""
        text = GENERIC_ARGUMENTS.sub("", CALL.sub("", text.strip())).rstrip("?")
        if not NAME.fullmatch(text):
            return None
        if text in self.written:
            return self.written[text]
        parts = text.split(".")
        if len(parts) == 1:
            found = self.short.get(text, ())
        elif len(parts) == 2:
            # "Type.Member", or a type inside a type: "Outer.Inner".
            inner = {name for name in self.short.get(parts[1], ())
                     if ARITY.sub("", name).split(".")[-2:-1] == [parts[0]] and name.rsplit(".", 1)[0] in self.types}
            found = set(self.members.get(text, ())) | inner
        else:
            found = ()
        return next(iter(found)) if len(found) == 1 else None

    def owner(self, name):
        """The type a filed name belongs to: the type itself, or the type of a member. None for a namespace."""
        return name if name in self.types else self.owners.get(name)


def means_typescript(text, section, typescript):
    """True when `text` in code font means a TypeScript type and not the C# type of the same name.

    A web app in the repository can have types named like the C# ones (Order, Customer). `typescript` lists
    those names ("names") and the sections of the dev docs that are about the web app
    ("sections"). In such a section the name is left alone.
    """
    name = text.strip().split("<")[0].rstrip("?").split(".")[0]
    return section in typescript["sections"] and name in typescript["names"]


def from_inventory(inventory):
    """The names in the inventory of the built code reference (objects.inv), and the address of each.

    `inventory` is what sphinx.util.inventory.InventoryFile.load() returns. A method is filed
    once per overload, with its parameters in brackets, and usually once more without them; the
    entry without brackets stands for the method here.
    """
    names, addresses = CodeNames(), {}
    for name, item in inventory.get("cs:namespace", {}).items():
        names.add_namespace(name)
        addresses.setdefault(name, item.uri)
    for role in TYPE_ROLES:
        for name, item in inventory.get(role, {}).items():
            names.add_type(name)
            addresses.setdefault(name, item.uri)
    for role in MEMBER_ROLES:
        entries = sorted(inventory.get(role, {}).items(), key=lambda entry: "(" in entry[0])   # without brackets first
        for name, item in entries:
            name = GENERIC_ARGUMENTS.sub("", name.split("(")[0])    # "A.Order.Map<T>(Func<Order,T>)" -> "A.Order.Map"
            if name not in names.types:
                names.add_member(name)
                addresses.setdefault(name, item.uri)
    return names, addresses


def from_doxygen(xml_dir):
    """The same names from Doxygen's XML. That exists before the code reference is built."""
    names = CodeNames()
    index = Path(xml_dir) / "index.xml"
    if not index.is_file():
        return names
    for compound in ElementTree.parse(index).getroot().iter("compound"):
        kind = compound.get("kind")
        if kind not in ("namespace", "class", "struct", "interface"):
            continue
        # Doxygen writes A.B.Result<T> as "A::B::Result-1-g".
        name = re.sub(r"-(\d+)-g", r"-\1", compound.findtext("name")).replace("::", ".")
        if kind == "namespace":
            names.add_namespace(name)
        else:
            names.add_type(name)
        enums = {}                        # the id of an enum -> its name
        for member in compound.iter("member"):
            member_kind, member_id = member.get("kind"), member.get("refid", "")
            member_name = f"{name}.{GENERIC_ARGUMENTS.sub('', member.findtext('name')).strip()}"
            if member_kind == "enum":
                enums[member_id] = member_name
                names.add_type(member_name)
            elif member_kind == "enumvalue":
                # The id of a value starts with the id of its enum.
                owner = max((enum for enum in enums if member_id.startswith(enum)), key=len, default=None)
                if owner:
                    names.add_member(f"{enums[owner]}.{member_name.rsplit('.', 1)[-1]}", enums[owner])
            elif kind == "namespace" and member_kind == "function":
                # C# has no functions outside a type. Doxygen reports a record written on one line,
                # such as "record OrderQuery(Guid CustomerId);", as a function of its namespace.
                names.add_type(member_name)
            elif kind != "namespace":
                names.add_member(member_name, name)
    return names
