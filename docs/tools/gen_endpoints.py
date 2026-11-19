"""Writes the HTTP endpoints page from the API's OpenAPI description (data/openapi.json)."""
import json

from urllib.parse import urlsplit

from common import DATA, OPENAPI_URL, SOURCE, documented_types, generated_note, write_if_changed

FORMATS = {
    "uuid": "id (GUID)", "date": "date", "date-time": "date and time", "int32": "whole number",
    "int64": "whole number (64-bit)", "double": "decimal number",
}
# What a status code means in general. The description's own words are used for any other code.
MEANING = {
    "200": "OK", "201": "Created", "202": "Accepted", "204": "Done, nothing to send back", "400": "The request is not valid",
    "401": "The caller is not known", "403": "Forbidden", "404": "Not found", "409": "Conflict",
    "422": "Request understood but not valid", "500": "Something went wrong in the API",
}


def kind(schema):
    """Describe one OpenAPI schema in a few plain words."""
    if not schema:
        return ""
    if "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        return f"[{name}](#{name.lower()})"
    if "enum" in schema:
        return "one of " + ", ".join(f"`{v}`" for v in schema["enum"])
    type_ = schema.get("type")
    # "May be empty" is written as a list of types in OpenAPI 3.1 and as nullable: true in 3.0.
    nullable = isinstance(type_, list) and "null" in type_ or schema.get("nullable") is True
    if isinstance(type_, list):  # OpenAPI 3.1 lists every allowed type, for example ["null", "string"]
        type_ = next((t for t in type_ if t not in ("null", "string")), None) or "string"
    if type_ == "array":
        text = "list of " + kind(schema.get("items"))
    else:
        text = FORMATS.get(schema.get("format"), type_ or "object")
    for alternative in schema.get("oneOf", []) + schema.get("anyOf", []):
        if "$ref" in alternative:
            text = kind(alternative)
    return text + (" or null" if nullable else "")


def body_kind(content):
    for media in (content or {}).values():
        if media.get("schema"):
            return kind(media["schema"])
    return ""


def main(openapi_file=DATA / "openapi.json", saved_on_file=DATA / "openapi.saved-on.txt"):
    doc = json.loads(openapi_file.read_text(encoding="utf-8"))
    saved_on = saved_on_file.read_text(encoding="utf-8").strip() if saved_on_file.is_file() else "an unknown date"
    schemas = doc.get("components", {}).get("schemas", {})
    groups = {}
    for path, operations in doc["paths"].items():
        for method, operation in operations.items():
            groups.setdefault((operation.get("tags") or ["Other"])[0], []).append((path, method.upper(), operation))
    count = sum(len(items) for items in groups.values())

    lines = [
        "# HTTP endpoints", "",
        f"Generated from the OpenAPI description the API publishes at `{urlsplit(OPENAPI_URL).path}` ({count} endpoints, "
        f"OpenAPI {doc['openapi']}). This copy was saved on {saved_on}; each build refreshes it when the API is running.", "",
        "An *OpenAPI description* is a file in which an API lists its own addresses, what each one takes and what it "
        "answers. This page repeats what that file says and adds nothing to it.",
    ]
    # Say what the description leaves out only when that is true of the file that was just read.
    operations = [operation for items in groups.values() for _, _, operation in items]
    if operations and not any(response.get("content") for operation in operations
                              for response in operation.get("responses", {}).values()):
        lines += ["", "```{note}",
                  "The description names no data shape for any answer, so the *Returns* column below is empty everywhere. "
                  "That is what a description looks like when the code does not say which type an action sends back.",
                  "```"]
    lines.append("")
    controllers = {name.rsplit(".", 1)[-1] for name in documented_types()}
    for tag, items in sorted(groups.items()):
        lines += [f"## {tag}", ""]
        if f"{tag}Controller" in controllers:   # the API names each group after its controller class
            lines += [f"Handled by {{cs:type}}`{tag}Controller`.", ""]
        for path, method, operation in items:
            lines += [f"### {method} {path}", ""]
            if operation.get("summary"):
                lines += [operation["summary"], ""]
            parameters = operation.get("parameters", [])
            if parameters or "requestBody" in operation:
                lines += ["| Input | Where | Type | Required |", "|---|---|---|---|"]
                lines += [f"| `{p['name']}` | {p['in']} | {kind(p.get('schema'))} | {'yes' if p.get('required') else 'no'} |"
                          for p in parameters]
                if "requestBody" in operation:
                    body = operation["requestBody"]   # "required" is left out by some tools; then the page says so
                    lines.append(f"| request body | JSON | {body_kind(body.get('content'))} "
                                 f"| {'yes' if body.get('required') else 'not said'} |")
                lines.append("")
            lines += ["| Status | Meaning | Returns |", "|---|---|---|"]
            lines += [f"| {code} | {MEANING.get(code, response.get('description', ''))} | {body_kind(response.get('content'))} |"
                      for code, response in operation.get("responses", {}).items()]
            lines.append("")

    lines += ["## Data shapes", ""]
    for name, schema in sorted(schemas.items()):
        lines += [f"({name.lower()})=", f"### {name}", ""]
        if "enum" in schema:
            lines += [kind(schema), ""]
            continue
        required = set(schema.get("required", []))
        lines += ["| Field | Type | Always present |", "|---|---|---|"]
        lines += [f"| `{field}` | {kind(s)} | {'yes' if field in required else 'no'} |"
                  for field, s in schema.get("properties", {}).items()]
        lines.append("")

    write_if_changed(SOURCE / "http" / "index.md", generated_note("gen_endpoints.py") + "\n".join(lines))
    print(f"   {count} endpoints, {len(schemas)} data shapes (description saved on {saved_on})")


if __name__ == "__main__":
    main()
