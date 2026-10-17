#!/usr/bin/env python3
"""Minimal .NET (PE/CLI) metadata reader.

Enumerates TypeDef rows (namespace + name + flags) and MethodDef names owned by
each type, straight from the file-backed metadata. No assembly is loaded or
executed. Read-only helper used for REA cross-checking of naming.

Usage:
  python pe_typedefs.py <assembly.dll> [regex] [--methods] [--json]
"""
import json
import re
import struct
import sys


def u2(b, o):
    return struct.unpack_from("<H", b, o)[0]


def u4(b, o):
    return struct.unpack_from("<I", b, o)[0]


# table column schema: list of (name, kind)
#   kinds: 'u2','u4', 'String', 'Guid', 'Blob', (tableindex name), (coded name)
TABLES = {
    0x00: [("Generation", "u2"), ("Name", "String"), ("Mvid", "Guid"), ("EncId", "Guid"), ("EncBaseId", "Guid")],
    0x01: [("ResolutionScope", "ResolutionScope"), ("Name", "String"), ("Namespace", "String")],
    0x02: [("Flags", "u4"), ("Name", "String"), ("Namespace", "String"), ("Extends", "TypeDefOrRef"),
           ("FieldList", "Field"), ("MethodList", "MethodDef")],
    0x03: [("Field", "Field")],
    0x04: [("Flags", "u2"), ("Name", "String"), ("Signature", "Blob")],
    0x05: [("Method", "MethodDef")],
    0x06: [("RVA", "u4"), ("ImplFlags", "u2"), ("Flags", "u2"), ("Name", "String"),
           ("Signature", "Blob"), ("ParamList", "Param")],
    0x07: [("Param", "Param")],
    0x08: [("Flags", "u2"), ("Sequence", "u2"), ("Name", "String")],
    0x09: [("Class", "TypeDef"), ("Interface", "TypeDefOrRef")],
    0x0A: [("Class", "MemberRefParent"), ("Name", "String"), ("Signature", "Blob")],
    0x0B: [("Type", "u2"), ("Parent", "HasConstant"), ("Value", "Blob")],
    0x0C: [("Parent", "HasCustomAttribute"), ("Type", "CustomAttributeType"), ("Value", "Blob")],
    0x0D: [("Parent", "HasFieldMarshal"), ("NativeType", "Blob")],
    0x0E: [("Action", "u2"), ("Parent", "HasDeclSecurity"), ("PermissionSet", "Blob")],
    0x0F: [("PackingSize", "u2"), ("ClassSize", "u4"), ("Parent", "TypeDef")],
    0x10: [("Offset", "u4"), ("Field", "Field")],
    0x11: [("Signature", "Blob")],
    0x12: [("Parent", "TypeDef"), ("EventList", "Event")],
    0x13: [("Event", "Event")],
    0x14: [("EventFlags", "u2"), ("Name", "String"), ("EventType", "TypeDefOrRef")],
    0x15: [("Parent", "TypeDef"), ("PropertyList", "Property")],
    0x16: [("Property", "Property")],
    0x17: [("Flags", "u2"), ("Name", "String"), ("Type", "Blob")],
    0x18: [("Semantics", "u2"), ("Method", "MethodDef"), ("Association", "HasSemantics")],
    0x19: [("Class", "TypeDef"), ("MethodBody", "MethodDefOrRef"), ("MethodDeclaration", "MethodDefOrRef")],
    0x1A: [("Name", "String")],
    0x1B: [("Signature", "Blob")],
    0x1C: [("MappingFlags", "u2"), ("MemberForwarded", "MemberForwarded"), ("ImportName", "String"),
           ("ImportScope", "ModuleRef")],
    0x1D: [("RVA", "u4"), ("Field", "Field")],
    0x1E: [("Token", "u4"), ("FuncCode", "u4")],
    0x1F: [("Token", "u4")],
    0x20: [("HashAlgId", "u4"), ("MajorVersion", "u2"), ("MinorVersion", "u2"), ("BuildNumber", "u2"),
           ("RevisionNumber", "u2"), ("Flags", "u4"), ("PublicKey", "Blob"), ("Name", "String"), ("Culture", "String")],
    0x21: [("Processor", "u4")],
    0x22: [("OSPlatformID", "u4"), ("OSMajorVersion", "u4"), ("OSMinorVersion", "u4")],
    0x23: [("MajorVersion", "u2"), ("MinorVersion", "u2"), ("BuildNumber", "u2"), ("RevisionNumber", "u2"),
           ("Flags", "u4"), ("PublicKeyOrToken", "Blob"), ("Name", "String"), ("Culture", "String"), ("HashValue", "Blob")],
    0x24: [("Processor", "u4"), ("AssemblyRef", "AssemblyRef")],
    0x25: [("OSPlatformID", "u4"), ("OSMajorVersion", "u4"), ("OSMinorVersion", "u4"), ("AssemblyRef", "AssemblyRef")],
    0x26: [("Flags", "u4"), ("Name", "String"), ("HashValue", "Blob")],
    0x27: [("Flags", "u4"), ("TypeDefId", "u4"), ("TypeName", "String"), ("TypeNamespace", "String"),
           ("Implementation", "Implementation")],
    0x28: [("Offset", "u4"), ("Flags", "u4"), ("Name", "String"), ("Implementation", "Implementation")],
    0x29: [("NestedClass", "TypeDef"), ("EnclosingClass", "TypeDef")],
    0x2A: [("Number", "u2"), ("Flags", "u2"), ("Owner", "TypeOrMethodDef"), ("Name", "String")],
    0x2B: [("Method", "MethodDefOrRef"), ("Instantiation", "Blob")],
    0x2C: [("Owner", "GenericParam"), ("Constraint", "TypeDefOrRef")],
}

CODED = {
    "TypeDefOrRef": (2, [0x02, 0x01, 0x1B]),
    "HasConstant": (2, [0x04, 0x08, 0x17]),
    "HasCustomAttribute": (5, [0x06, 0x04, 0x01, 0x02, 0x08, 0x09, 0x0A, 0x00, 0x0E, 0x17, 0x14, 0x11, 0x1A,
                               0x1B, 0x20, 0x23, 0x26, 0x27, 0x28, 0x2A, 0x2C, 0x2B]),
    "HasFieldMarshal": (1, [0x04, 0x08]),
    "HasDeclSecurity": (2, [0x02, 0x06, 0x20]),
    "MemberRefParent": (3, [0x02, 0x01, 0x1A, 0x06, 0x1B]),
    "HasSemantics": (1, [0x14, 0x17]),
    "MethodDefOrRef": (1, [0x06, 0x0A]),
    "MemberForwarded": (1, [0x04, 0x06]),
    "Implementation": (2, [0x26, 0x23, 0x27]),
    "CustomAttributeType": (3, [None, None, 0x06, 0x0A, None]),
    "ResolutionScope": (2, [0x00, 0x1A, 0x23, 0x01]),
    "TypeOrMethodDef": (1, [0x02, 0x06]),
}


class Metadata:
    def __init__(self, path):
        self.data = open(path, "rb").read()
        b = self.data
        e_lfanew = u4(b, 0x3C)
        assert b[e_lfanew:e_lfanew + 4] == b"PE\x00\x00", "not a PE"
        coff = e_lfanew + 4
        n_sections = u2(b, coff + 2)
        opt_size = u2(b, coff + 16)
        opt = coff + 20
        magic = u2(b, opt)
        assert magic in (0x10B, 0x20B), "unknown PE magic 0x%x" % magic
        dd = opt + (112 if magic == 0x20B else 96)
        num_dd = u4(b, opt + (108 if magic == 0x20B else 92))
        cli_rva = u4(b, dd + 14 * 8)
        sections = []
        sp = opt + opt_size
        for i in range(n_sections):
            s = sp + i * 40
            sections.append((u4(b, s + 12), u4(b, s + 8), u4(b, s + 20)))  # VA, VSize, RawPtr
        self.sections = sections

        def rva2off(rva):
            for va, vsize, raw in sections:
                if va <= rva < va + max(vsize, u4(b, sp + 0) if False else vsize) or va <= rva < va + 0x1000000:
                    if va <= rva < va + vsize or (rva - va) < (len(b) - raw):
                        if raw <= rva - va + raw and rva - va < 0x10000000:
                            if raw > 0:
                                return raw + (rva - va)
            for va, vsize, raw in sections:
                if raw and va <= rva < va + 0x10000000:
                    return raw + (rva - va)
            raise ValueError("rva 0x%x not mapped" % rva)

        cli = rva2off(cli_rva)
        md_rva = u4(b, cli + 8)
        md_off = rva2off(md_rva)
        assert u4(b, md_off) == 0x424A5342, "bad metadata signature"
        ver_len = u4(b, md_off + 12)
        p = md_off + 16 + ver_len
        flags = u2(b, p)
        n_streams = u2(b, p + 2)
        p += 4
        streams = {}
        for _ in range(n_streams):
            off = u4(b, p)
            size = u4(b, p + 4)
            nstart = p + 8
            nend = b.index(b"\x00", nstart)
            name = b[nstart:nend].decode("ascii")
            streams[name] = (md_off + off, size)
            p = nstart + ((nend - nstart) // 4 + 1) * 4
        self.streams = streams
        self._strings = streams.get("#Strings")
        tab = streams.get("#~") or streams.get("#-")
        self.rows = {}
        self.table_off = {}
        self._read_tables(tab[0])

    def s(self, off):
        end = self.data.index(b"\x00", off)
        return self.data[off:end].decode("utf-8", "replace")

    def _read_tables(self, p):
        b = self.data
        p += 4  # reserved
        major = b[p]; p += 1
        minor = b[p]; p += 1
        heap = b[p]; p += 1
        p += 1
        valid = struct.unpack_from("<Q", b, p)[0]; p += 8
        p += 8  # sorted
        self.str_size = 4 if (heap & 0x01) else 2
        self.guid_size = 4 if (heap & 0x02) else 2
        self.blob_size = 4 if (heap & 0x04) else 2
        rows = {}
        for i in range(64):
            if valid & (1 << i):
                rows[i] = u4(b, p); p += 4
        self.rows = rows
        self.tables_start = p
        # compute offsets
        off = p
        self.table_off = {}
        for i in range(64):
            if i in rows:
                self.table_off[i] = off
                off += rows[i] * self.row_size(i, rows)
        self.tables_end = off

    def simple_size(self, table, rows):
        return 4 if rows.get(table, 0) >= 0x10000 else 2

    def coded_size(self, name, rows):
        bits, tabs = CODED[name]
        m = 0
        for t in tabs:
            if t is not None:
                m = max(m, rows.get(t, 0))
        return 4 if m >= (1 << (16 - bits)) else 2

    def col_size(self, kind, rows):
        if kind == "u2":
            return 2
        if kind == "u4":
            return 4
        if kind == "String":
            return self.str_size
        if kind == "Guid":
            return self.guid_size
        if kind == "Blob":
            return self.blob_size
        if kind in CODED:
            return self.coded_size(kind, rows)
        return self.simple_size(int(kind, 16) if isinstance(kind, str) and kind.startswith("0x") else kind, rows)

    def row_size(self, table, rows):
        return sum(self.col_size(k, rows) for _, k in TABLES[table])

    def read_table(self, table):
        b = self.data
        base = self.table_off[table]
        rows = self.rows
        cols = TABLES[table]
        sizes = [self.col_size(k, rows) for _, k in cols]
        stride = sum(sizes)
        out = []
        for r in range(rows.get(table, 0)):
            p = base + r * stride
            vals = {}
            for (cname, ckind), cs in zip(cols, sizes):
                raw = int.from_bytes(b[p:p + cs], "little")
                if ckind == "String":
                    vals[cname] = self.s(self._strings[0] + raw)
                elif ckind == "Guid":
                    vals[cname] = raw
                elif ckind == "Blob":
                    vals[cname] = raw
                else:
                    vals[cname] = raw
                p += cs
            out.append(vals)
        return out


def main():
    path = sys.argv[1]
    pattern = None
    show_methods = "--methods" in sys.argv
    as_json = "--json" in sys.argv
    for a in sys.argv[2:]:
        if not a.startswith("--"):
            pattern = a
    md = Metadata(path)
    typedefs = md.read_table(0x02)
    methods = md.read_table(0x06) if show_methods else []
    out = []
    for i, t in enumerate(typedefs):
        full = (t["Namespace"] + "." + t["Name"]) if t["Namespace"] else t["Name"]
        entry = {"index": i + 1, "full_name": full, "namespace": t["Namespace"], "name": t["Name"],
                 "flags": t["Flags"]}
        if show_methods:
            first = t["MethodList"]
            last = typedefs[i + 1]["MethodList"] if i + 1 < len(typedefs) else len(methods) + 1
            entry["methods"] = [methods[m - 1]["Name"] for m in range(first, last) if 1 <= m <= len(methods)]
        out.append(entry)
    if pattern:
        rx = re.compile(pattern)
        out = [e for e in out if rx.search(e["full_name"]) or (show_methods and any(rx.search(m) for m in e.get("methods", [])))]
    if as_json:
        print(json.dumps(out, indent=2))
    else:
        print("typedefs: %d (filtered: %d)" % (len(typedefs), len(out)))
        for e in out:
            line = e["full_name"]
            if show_methods:
                line += "  ::  " + ", ".join(e["methods"])
            print(line)


if __name__ == "__main__":
    main()
