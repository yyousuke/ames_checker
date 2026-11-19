#!/usr/bin/env python3
"""Validate NASA Ames ASCII exchange files (spec v2.0 baseline checks).

This validator focuses on structural conformance:
- Printable ASCII and line-length constraints
- Header structure by FFI
- Count consistency for variable-length sections
- Basic data-record structure by FFI
- Optional checks for Version 2 metadata declarations

It intentionally does not attempt full semantic validation of every metadata field.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

NUM_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?$")
INT_RE = re.compile(r"^[+-]?\d+$")
PRINTABLE_MIN = 32
PRINTABLE_MAX = 126
MAX_LINE_LEN = 132
SUPPORTED_FFIS = {1001, 1010, 1020, 2010, 2110, 2160, 2310, 3010, 4010}


@dataclass
class ValidationIssue:
    level: str
    message: str
    line: Optional[int] = None


@dataclass
class ValidationResult:
    errors: List[ValidationIssue] = field(default_factory=list)
    warnings: List[ValidationIssue] = field(default_factory=list)

    def add_error(self, message: str, line: Optional[int] = None) -> None:
        self.errors.append(ValidationIssue("ERROR", message, line))

    def add_warning(self, message: str, line: Optional[int] = None) -> None:
        self.warnings.append(ValidationIssue("WARN", message, line))

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass
class HeaderInfo:
    nlhead: int
    ffi: int
    nv: int
    nauxv: int
    nauxc: int
    nscoml: int
    nncoml: int
    nx: List[int]
    nxdef: List[int]
    lenx2: Optional[int]
    lena_string_aux: List[int]
    vmiss: List[float]
    amiss: List[float | str]
    dx: List[float]
    nvpm1: Optional[int]
    normal_comments: List[str]


class ParseError(RuntimeError):
    pass


class Cursor:
    def __init__(self, lines: List[str], result: ValidationResult) -> None:
        self.lines = lines
        self.i = 0
        self.result = result

    def at_end(self) -> bool:
        return self.i >= len(self.lines)

    def current_line_no(self) -> int:
        return self.i + 1

    def read_string_line(self) -> str:
        if self.at_end():
            raise ParseError("Unexpected EOF while reading string record")
        s = self.lines[self.i]
        self.i += 1
        return s

    @staticmethod
    def _parse_numeric_prefix(line: str) -> tuple[List[float], str]:
        tokens = line.strip().split()
        out: List[float] = []
        for idx, tok in enumerate(tokens):
            if NUM_RE.match(tok):
                out.append(float(tok))
            else:
                # Non-numeric token starts annotation (allowed by spec).
                rest = " ".join(tokens[idx:])
                return out, rest
        return out, ""

    def read_numeric_record(self, count: int) -> List[float]:
        if count < 0:
            raise ParseError(f"Invalid numeric count requested: {count}")
        if count == 0:
            return []

        if self.at_end():
            raise ParseError("Unexpected EOF while reading numeric record")

        start_line_no = self.current_line_no()
        values: List[float] = []

        while len(values) < count:
            if self.at_end():
                raise ParseError(
                    f"Unexpected EOF while reading numeric record starting at line {start_line_no}"
                )
            line = self.read_string_line()
            nums, _annotation = self._parse_numeric_prefix(line)
            values.extend(nums)

            if not nums:
                self.result.add_warning(
                    "Numeric record line has no parseable numeric tokens",
                    line=self.i,
                )

        if len(values) > count:
            self.result.add_error(
                f"Numeric record has too many values: expected {count}, got {len(values)}",
                line=start_line_no,
            )
            values = values[:count]

        return values


# ---------- Scalar parsing helpers ----------


def as_int(v: float, what: str, result: ValidationResult, line: Optional[int] = None) -> int:
    if abs(v - int(v)) > 1e-9:
        result.add_error(f"{what} must be an integer, got {v}", line=line)
    return int(v)


def parse_date_parts(parts: List[float], label: str, result: ValidationResult, line: int) -> None:
    if len(parts) != 3:
        result.add_error(f"{label} must have 3 integers (YYYY MM DD)", line=line)
        return
    y, m, d = [as_int(x, label, result, line=line) for x in parts]
    try:
        _dt.date(y, m, d)
    except ValueError:
        result.add_error(f"{label} is not a valid calendar date: {y:04d}-{m:02d}-{d:02d}", line=line)


# ---------- Validation stages ----------


def validate_ascii_constraints(raw: bytes, lines: List[str], result: ValidationResult) -> None:
    for idx, b in enumerate(raw):
        if b in (10, 13):
            continue
        if not (PRINTABLE_MIN <= b <= PRINTABLE_MAX):
            result.add_error(f"Non-printable ASCII byte {b} at byte offset {idx}")
            break

    for ln, line in enumerate(lines, start=1):
        if "\t" in line:
            result.add_error("TAB character is not allowed", line=ln)
        if len(line) > MAX_LINE_LEN:
            result.add_error(
                f"Line exceeds {MAX_LINE_LEN} printable characters ({len(line)})",
                line=ln,
            )



def parse_header(cur: Cursor, result: ValidationResult) -> HeaderInfo:
    if cur.at_end():
        raise ParseError("File is empty")

    first_line_no = cur.current_line_no()
    first = cur.read_numeric_record(2)
    nlhead = as_int(first[0], "NLHEAD", result, line=first_line_no)
    ffi = as_int(first[1], "FFI", result, line=first_line_no)

    if ffi not in SUPPORTED_FFIS:
        result.add_error(f"Unsupported/unknown FFI: {ffi}", line=first_line_no)

    # Always read the 4 required string lines.
    _oname = cur.read_string_line()
    _org = cur.read_string_line()
    _sname = cur.read_string_line()
    _mname = cur.read_string_line()

    line_6 = cur.current_line_no()
    ivol_nvol = cur.read_numeric_record(2)
    ivol = as_int(ivol_nvol[0], "IVOL", result, line=line_6)
    nvol = as_int(ivol_nvol[1], "NVOL", result, line=line_6)
    if ivol <= 0 or nvol <= 0:
        result.add_error("IVOL and NVOL must be positive integers", line=line_6)
    if ivol > nvol:
        result.add_error("IVOL must be <= NVOL", line=line_6)

    line_7 = cur.current_line_no()
    date_vals = cur.read_numeric_record(6)
    parse_date_parts(date_vals[:3], "DATE", result, line=line_7)
    parse_date_parts(date_vals[3:], "RDATE", result, line=line_7)

    nauxv = 0
    nauxc = 0
    nx: List[int] = []
    nxdef: List[int] = []
    lenx2: Optional[int] = None
    lena_string_aux: List[int] = []
    nvpm1: Optional[int] = None

    # FFI-specific pre-variable blocks.
    if ffi == 1001:
        dx = cur.read_numeric_record(1)
        _xname = cur.read_string_line()
    elif ffi == 1010:
        dx = cur.read_numeric_record(1)
        _xname = cur.read_string_line()
    elif ffi == 1020:
        dx = cur.read_numeric_record(1)
        if abs(dx[0]) < 1e-20:
            result.add_error("For FFI=1020, DX(1) must be non-zero", line=cur.current_line_no() - 1)
        line_nvpm = cur.current_line_no()
        nvpm1 = as_int(cur.read_numeric_record(1)[0], "NVPM(1)", result, line=line_nvpm)
        if nvpm1 <= 0:
            result.add_error("NVPM(1) must be > 0", line=line_nvpm)
        _xname = cur.read_string_line()
    elif ffi == 2010:
        dx = cur.read_numeric_record(2)
        line_nx = cur.current_line_no()
        nx1 = as_int(cur.read_numeric_record(1)[0], "NX(1)", result, line=line_nx)
        line_nxdef = cur.current_line_no()
        nxdef1 = as_int(cur.read_numeric_record(1)[0], "NXDEF(1)", result, line=line_nxdef)
        if nx1 <= 0:
            result.add_error("NX(1) must be > 0", line=line_nx)
        if nxdef1 <= 0 or nxdef1 > nx1:
            result.add_error("NXDEF(1) must satisfy 1 <= NXDEF(1) <= NX(1)", line=line_nxdef)
        _xvals = cur.read_numeric_record(max(nxdef1, 0))
        _xname1 = cur.read_string_line()
        _xname2 = cur.read_string_line()
        nx = [nx1]
        nxdef = [nxdef1]
    elif ffi == 2110:
        dx = cur.read_numeric_record(2)
        _xname1 = cur.read_string_line()
        _xname2 = cur.read_string_line()
    elif ffi == 2160:
        dx = cur.read_numeric_record(1)
        line_lenx2 = cur.current_line_no()
        lenx2 = as_int(cur.read_numeric_record(1)[0], "LENX(2)", result, line=line_lenx2)
        if lenx2 <= 0 or lenx2 >= 133:
            result.add_error("LENX(2) must satisfy 0 < LENX(2) < 133", line=line_lenx2)
        _xname1 = cur.read_string_line()
        _xname2 = cur.read_string_line()
    elif ffi == 2310:
        dx = cur.read_numeric_record(1)
        _xname1 = cur.read_string_line()
        _xname2 = cur.read_string_line()
    elif ffi == 3010:
        dx = cur.read_numeric_record(3)
        line_nx = cur.current_line_no()
        nx12 = cur.read_numeric_record(2)
        nx1 = as_int(nx12[0], "NX(1)", result, line=line_nx)
        nx2 = as_int(nx12[1], "NX(2)", result, line=line_nx)
        line_nxdef = cur.current_line_no()
        nxdef12 = cur.read_numeric_record(2)
        nxdef1 = as_int(nxdef12[0], "NXDEF(1)", result, line=line_nxdef)
        nxdef2 = as_int(nxdef12[1], "NXDEF(2)", result, line=line_nxdef)
        if nx1 <= 0 or nx2 <= 0:
            result.add_error("NX(1), NX(2) must be > 0", line=line_nx)
        if nxdef1 <= 0 or nxdef1 > nx1 or nxdef2 <= 0 or nxdef2 > nx2:
            result.add_error("NXDEF bounds invalid for FFI=3010", line=line_nxdef)
        _x1 = cur.read_numeric_record(max(nxdef1, 0))
        _x2 = cur.read_numeric_record(max(nxdef2, 0))
        _xname1 = cur.read_string_line()
        _xname2 = cur.read_string_line()
        _xname3 = cur.read_string_line()
        nx = [nx1, nx2]
        nxdef = [nxdef1, nxdef2]
    elif ffi == 4010:
        dx = cur.read_numeric_record(4)
        line_nx = cur.current_line_no()
        nx123 = cur.read_numeric_record(3)
        nx1 = as_int(nx123[0], "NX(1)", result, line=line_nx)
        nx2 = as_int(nx123[1], "NX(2)", result, line=line_nx)
        nx3 = as_int(nx123[2], "NX(3)", result, line=line_nx)
        line_nxdef = cur.current_line_no()
        nxdef123 = cur.read_numeric_record(3)
        nxdef1 = as_int(nxdef123[0], "NXDEF(1)", result, line=line_nxdef)
        nxdef2 = as_int(nxdef123[1], "NXDEF(2)", result, line=line_nxdef)
        nxdef3 = as_int(nxdef123[2], "NXDEF(3)", result, line=line_nxdef)
        if nx1 <= 0 or nx2 <= 0 or nx3 <= 0:
            result.add_error("NX(1), NX(2), NX(3) must be > 0", line=line_nx)
        if (
            nxdef1 <= 0
            or nxdef1 > nx1
            or nxdef2 <= 0
            or nxdef2 > nx2
            or nxdef3 <= 0
            or nxdef3 > nx3
        ):
            result.add_error("NXDEF bounds invalid for FFI=4010", line=line_nxdef)
        _x1 = cur.read_numeric_record(max(nxdef1, 0))
        _x2 = cur.read_numeric_record(max(nxdef2, 0))
        _x3 = cur.read_numeric_record(max(nxdef3, 0))
        _xname1 = cur.read_string_line()
        _xname2 = cur.read_string_line()
        _xname3 = cur.read_string_line()
        _xname4 = cur.read_string_line()
        nx = [nx1, nx2, nx3]
        nxdef = [nxdef1, nxdef2, nxdef3]
    else:
        dx = []

    line_nv = cur.current_line_no()
    nv = as_int(cur.read_numeric_record(1)[0], "NV", result, line=line_nv)
    if nv <= 0:
        result.add_error("NV must be > 0", line=line_nv)

    _vscal = cur.read_numeric_record(max(nv, 0))
    vmiss = cur.read_numeric_record(max(nv, 0))
    for _ in range(max(nv, 0)):
        cur.read_string_line()  # VNAME(n)

    amiss: List[float | str] = []

    if ffi != 1001:
        line_nauxv = cur.current_line_no()
        nauxv = as_int(cur.read_numeric_record(1)[0], "NAUXV", result, line=line_nauxv)
        if nauxv < 0:
            result.add_error("NAUXV must be >= 0", line=line_nauxv)

        if ffi in (2110, 2160, 2310) and nauxv < 1:
            result.add_error(f"FFI={ffi} requires NAUXV >= 1", line=line_nauxv)
        if ffi == 2310 and nauxv < 3:
            result.add_error("FFI=2310 requires first 3 auxiliary values: NX, X(1), DX", line=line_nauxv)

        if ffi == 2160:
            line_nauxc = cur.current_line_no()
            nauxc = as_int(cur.read_numeric_record(1)[0], "NAUXC", result, line=line_nauxc)
            if nauxc < 0 or nauxc > nauxv:
                result.add_error("NAUXC must satisfy 0 <= NAUXC <= NAUXV", line=line_nauxc)

            numeric_aux_count = max(nauxv - nauxc, 0)
            _ascal = cur.read_numeric_record(numeric_aux_count)
            amiss_numeric = cur.read_numeric_record(numeric_aux_count)

            # String auxiliary variable lengths and AMISS values.
            lena_string_aux = []
            for _ in range(nauxc):
                line_lena = cur.current_line_no()
                lena = as_int(cur.read_numeric_record(1)[0], "LENA(a)", result, line=line_lena)
                if lena <= 0 or lena >= 133:
                    result.add_error("LENA(a) must satisfy 0 < LENA(a) < 133", line=line_lena)
                lena_string_aux.append(lena)

            amiss_string = []
            for _ in range(nauxc):
                amiss_string.append(cur.read_string_line())

            amiss = list(amiss_numeric) + amiss_string
        else:
            _ascal = cur.read_numeric_record(max(nauxv, 0))
            amiss = cur.read_numeric_record(max(nauxv, 0))

        for _ in range(max(nauxv, 0)):
            cur.read_string_line()  # ANAME(a)

    line_nscoml = cur.current_line_no()
    nscoml = as_int(cur.read_numeric_record(1)[0], "NSCOML", result, line=line_nscoml)
    if nscoml < 0:
        result.add_error("NSCOML must be >= 0", line=line_nscoml)
    for _ in range(max(nscoml, 0)):
        cur.read_string_line()

    line_nncoml = cur.current_line_no()
    nncoml = as_int(cur.read_numeric_record(1)[0], "NNCOML", result, line=line_nncoml)
    if nncoml < 0:
        result.add_error("NNCOML must be >= 0", line=line_nncoml)

    normal_comments = [cur.read_string_line() for _ in range(max(nncoml, 0))]

    # Validate NLHEAD now that the header parse reached data start.
    if cur.i != nlhead:
        result.add_error(
            f"NLHEAD mismatch: declared {nlhead}, parsed {cur.i} header lines",
            line=1,
        )

    return HeaderInfo(
        nlhead=nlhead,
        ffi=ffi,
        nv=nv,
        nauxv=nauxv,
        nauxc=nauxc,
        nscoml=nscoml,
        nncoml=nncoml,
        nx=nx,
        nxdef=nxdef,
        lenx2=lenx2,
        lena_string_aux=lena_string_aux,
        vmiss=vmiss,
        amiss=amiss,
        dx=dx,
        nvpm1=nvpm1,
        normal_comments=normal_comments,
    )


def _is_missing(nx_value: int, amiss0: float | str) -> bool:
    if isinstance(amiss0, str):
        return False
    return abs(nx_value - amiss0) < 1e-9


def validate_v2_metadata_first_lines(h: HeaderInfo, result: ValidationResult) -> None:
    if h.nncoml < 2:
        return

    def split_fields(s: str) -> List[str]:
        return [f.strip() for f in s.split("|")]

    f1 = split_fields(h.normal_comments[0])
    f2 = split_fields(h.normal_comments[1])

    looks_v2 = (
        len(f1) >= 5
        and f1[0] == "#MD"
        and f1[1] == "NA"
        and f1[2].lower() == "format version"
    )

    if not looks_v2:
        return

    if not (len(f2) >= 5 and f2[0] == "#MD" and f2[1] == "NA" and f2[2] == "NIVM"):
        result.add_error(
            "Version 2 extension indicated, but second normal comment is not '#MD | NA | NIVM | 1 | ...'"
        )
        return

    try:
        n1 = int(float(f1[3]))
        v1 = float(f1[4].split()[0])
        n2 = int(float(f2[3]))
        v2 = int(float(f2[4].split()[0]))
    except Exception:
        result.add_error("Failed to parse Version 2 metadata numeric fields")
        return

    if n1 != 1 or abs(v1 - 2.0) > 1e-9:
        result.add_error("Version 2 first metadata must be '#MD | NA | format version | 1 | 2'")
    if n2 != 1 or v2 <= 0:
        result.add_error("NIVM metadata must have one positive value")


def validate_data_section(cur: Cursor, h: HeaderInfo, result: ValidationResult) -> None:
    ivm_values: List[float] = []

    def read_ivm_real_with_aux(aux_count: int) -> tuple[float, List[float]]:
        rec = cur.read_numeric_record(1 + aux_count)
        return rec[0], rec[1:]

    while not cur.at_end():
        try:
            if h.ffi == 1001:
                rec = cur.read_numeric_record(1 + h.nv)
                ivm_values.append(rec[0])

            elif h.ffi == 1010:
                ivm, _aux = read_ivm_real_with_aux(h.nauxv)
                ivm_values.append(ivm)
                cur.read_numeric_record(h.nv)

            elif h.ffi == 1020:
                ivm, _aux = read_ivm_real_with_aux(h.nauxv)
                ivm_values.append(ivm)
                block = h.nvpm1 or 0
                for _ in range(h.nv):
                    cur.read_numeric_record(block)

            elif h.ffi == 2010:
                ivm, _aux = read_ivm_real_with_aux(h.nauxv)
                ivm_values.append(ivm)
                nx1 = h.nx[0]
                for _ in range(h.nv):
                    cur.read_numeric_record(nx1)

            elif h.ffi == 2110:
                rec = cur.read_numeric_record(1 + h.nauxv)
                ivm_values.append(rec[0])
                nxm1 = as_int(rec[1], "NX(m,1)", result, line=cur.current_line_no() - 1)
                skip = (nxm1 == 0) or (h.amiss and _is_missing(nxm1, h.amiss[0]))
                if not skip:
                    if nxm1 < 0:
                        result.add_error("NX(m,1) must be >= 0", line=cur.current_line_no() - 1)
                    for _ in range(max(nxm1, 0)):
                        cur.read_numeric_record(1 + h.nv)

            elif h.ffi == 2160:
                ivm = cur.read_string_line()
                if h.lenx2 is not None and len(ivm) != h.lenx2:
                    result.add_warning(
                        f"IVM string length is {len(ivm)} but LENX(2)={h.lenx2}",
                        line=cur.current_line_no() - 1,
                    )

                numeric_aux_count = h.nauxv - h.nauxc
                rec2 = cur.read_numeric_record(1 + numeric_aux_count)
                nxm1 = as_int(rec2[0], "NX(m,1)", result, line=cur.current_line_no() - 1)

                for j in range(h.nauxc):
                    s = cur.read_string_line()
                    expected = h.lena_string_aux[j]
                    if len(s) != expected:
                        result.add_warning(
                            f"String auxiliary length is {len(s)} but LENA={expected}",
                            line=cur.current_line_no() - 1,
                        )

                skip = (nxm1 == 0) or (h.amiss and _is_missing(nxm1, h.amiss[0]))
                if not skip:
                    if nxm1 < 0:
                        result.add_error("NX(m,1) must be >= 0", line=cur.current_line_no() - 1)
                    for _ in range(max(nxm1, 0)):
                        cur.read_numeric_record(1 + h.nv)

            elif h.ffi == 2310:
                rec = cur.read_numeric_record(1 + h.nauxv)
                ivm_values.append(rec[0])
                nxm1 = as_int(rec[1], "NX(m,1)", result, line=cur.current_line_no() - 1)
                skip = (nxm1 == 0) or (h.amiss and _is_missing(nxm1, h.amiss[0]))
                if not skip:
                    if nxm1 < 0:
                        result.add_error("NX(m,1) must be >= 0", line=cur.current_line_no() - 1)
                    for _ in range(h.nv):
                        cur.read_numeric_record(max(nxm1, 0))

            elif h.ffi == 3010:
                ivm, _aux = read_ivm_real_with_aux(h.nauxv)
                ivm_values.append(ivm)
                nx1, nx2 = h.nx
                for _n in range(h.nv):
                    for _j in range(nx2):
                        cur.read_numeric_record(nx1)

            elif h.ffi == 4010:
                ivm, _aux = read_ivm_real_with_aux(h.nauxv)
                ivm_values.append(ivm)
                nx1, nx2, nx3 = h.nx
                for _n in range(h.nv):
                    for _k in range(nx3):
                        for _j in range(nx2):
                            cur.read_numeric_record(nx1)

            else:
                result.add_error(f"Data parsing not implemented for FFI={h.ffi}")
                break

        except ParseError as e:
            result.add_error(str(e), line=cur.current_line_no())
            break

    # Monotonicity check for real-valued IVMs.
    if len(ivm_values) >= 2:
        first_diff = ivm_values[1] - ivm_values[0]
        if abs(first_diff) < 1e-15:
            result.add_error("Independent Variable Marks are not monotonic (repeated value)")
            return
        increasing = first_diff > 0
        for a, b in zip(ivm_values, ivm_values[1:]):
            if increasing and not (b > a):
                result.add_error("Independent Variable Marks must be strictly increasing or decreasing")
                break
            if (not increasing) and not (b < a):
                result.add_error("Independent Variable Marks must be strictly increasing or decreasing")
                break



def validate_file(path: Path) -> ValidationResult:
    result = ValidationResult()

    raw = path.read_bytes()
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as e:
        result.add_error(f"File is not pure ASCII: {e}")
        return result

    # Keep exact logical lines, no trailing newline chars.
    lines = text.splitlines()
    validate_ascii_constraints(raw, lines, result)

    cur = Cursor(lines, result)

    try:
        header = parse_header(cur, result)
        validate_v2_metadata_first_lines(header, result)
        validate_data_section(cur, header, result)
    except ParseError as e:
        result.add_error(str(e), line=cur.current_line_no())

    return result


def format_issue(issue: ValidationIssue) -> str:
    where = f"line {issue.line}: " if issue.line is not None else ""
    return f"[{issue.level}] {where}{issue.message}"


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="Validate NASA Ames ASCII exchange file structure (v2.0 baseline)."
    )
    p.add_argument("file", type=Path, help="Path to NASA Ames file")
    args = p.parse_args(argv)

    if not args.file.exists():
        print(f"[ERROR] File not found: {args.file}")
        return 2

    res = validate_file(args.file)

    for w in res.warnings:
        print(format_issue(w))
    for e in res.errors:
        print(format_issue(e))

    if res.ok:
        print("OK: no structural format errors found.")
        return 0

    print(f"FAILED: {len(res.errors)} error(s), {len(res.warnings)} warning(s).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
