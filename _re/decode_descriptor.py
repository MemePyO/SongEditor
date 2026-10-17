#!/usr/bin/env python3
"""Decode a protobuf FileDescriptorProto embedded in a *.Reflection class.

REA's inspect-managed-members exposes the ldstr literals of a generated
`<Foo>Reflection` type, which include the base64-encoded FileDescriptorProto
(the same bytes passed to FileDescriptor.FromGeneratedCode). This script
reassembles and parses it so the authoritative message/field schema can be
compared against SongEditor's checked-in *_pb2.py modules.

Read-only helper; writes nothing.

Usage:
  python decode_descriptor.py <rea_user_strings.json>
"""
import base64
import json
import re
import sys

from google.protobuf import descriptor_pb2

B64_RE = re.compile(r"^[A-Za-z0-9+/]{16,}={0,2}$")

TYPE_NAMES = {
    1: "double", 2: "float", 3: "int64", 4: "uint64", 5: "int32", 6: "fixed64",
    7: "fixed32", 8: "bool", 9: "string", 10: "group", 11: "message", 12: "bytes",
    13: "uint32", 14: "enum", 15: "sfixed32", 16: "sfixed64", 17: "sint32", 18: "sint64",
}
LABELS = {1: "optional", 2: "required", 3: "repeated"}


def decode(json_path):
    with open(json_path, "r", encoding="utf-8") as fh:
        j = json.load(fh)
    lits = [l["value"] for l in j["normalized_result"]["user_strings"]["literals"]]
    start = None
    for i, v in enumerate(lits):
        if v.startswith("Ch") and B64_RE.match(v) and len(v) >= 40:
            start = i
            break
    if start is None:
        raise SystemExit("no base64 descriptor start chunk found")
    chunks = []
    for v in lits[start:]:
        if B64_RE.match(v):
            chunks.append(v)
        else:
            break
    if not chunks:
        raise SystemExit("no base64 descriptor chunks found")
    raw = base64.b64decode("".join(chunks))
    fd = descriptor_pb2.FileDescriptorProto()
    fd.ParseFromString(raw)
    return fd


def fmt_field(f):
    label = LABELS.get(f.label, str(f.label))
    t = TYPE_NAMES.get(f.type, str(f.type))
    extra = ""
    if f.type in (11, 14) and f.type_name:
        extra = " -> " + f.type_name
    opt = []
    if f.proto3_optional:
        opt.append("proto3_optional")
    if f.HasField("oneof_index"):
        opt.append("oneof#%d" % f.oneof_index)
    if f.options.HasField("deprecated") and f.options.deprecated:
        opt.append("deprecated")
    if f.options.HasField("packed"):
        opt.append("packed=%s" % f.options.packed)
    suffix = (" [" + ",".join(opt) + "]") if opt else ""
    return "  %s %s %s = %d;%s%s" % (label, t, f.name, f.number, extra, suffix)


def fmt_enum(e, pad):
    out = [pad + "enum %s {" % e.name]
    for v in e.value:
        out.append("%s  %s = %d;" % (pad, v.name, v.number))
    out.append(pad + "}")
    return out


def fmt_message(m, pad=""):
    out = [pad + "message %s {" % m.name]
    pad2 = pad + "  "
    for e in m.enum_type:
        out += fmt_enum(e, pad2)
    for o in m.oneof_decl:
        out.append(pad2 + "oneof %s" % o.name)
    for f in m.field:
        out.append(fmt_field(f))
    for n in m.nested_type:
        out.append("")
        out += fmt_message(n, pad2)
    if m.options.HasField("map_entry") and m.options.map_entry:
        out.append(pad2 + "// map entry")
    out.append(pad + "}")
    return out


def main():
    fd = decode(sys.argv[1])
    print("file:", fd.name)
    print("package:", fd.package)
    print("syntax:", fd.syntax)
    print("dependencies:", list(fd.dependency))
    if fd.options.HasField("csharp_namespace"):
        print("csharp_namespace:", fd.options.csharp_namespace)
    if fd.options.HasField("java_package"):
        print("java_package:", fd.options.java_package)
    print()
    for e in fd.enum_type:
        print("\n".join(fmt_enum(e, "")))
    for m in fd.message_type:
        print("\n".join(fmt_message(m)))
        print()


if __name__ == "__main__":
    main()
