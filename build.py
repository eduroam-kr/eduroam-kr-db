#!/usr/bin/env python3
"""YAML 원본을 eduroam database v2 제출용 XML 로 빌드한다.

  inst.d/<realm>.yml  →  dist/institution.xml   (<institutions> 안에 기관 전부)
  ro.yml              →  dist/ro.xml            (<ROs> 안에 NRO 자신)

엘리먼트 순서는 schema/*.xsd 의 xs:sequence 가 강제한다. 아래 ORDER 상수가
그 순서를 그대로 옮긴 것이고, 손으로 바꾸지 않는다 — 바꾸려면 XSD 를 먼저 본다.

usage: build.py [--out dist] [--validate]
"""

import argparse
import datetime
import pathlib
import subprocess
import sys
import xml.etree.ElementTree as ET

try:
    import yaml
except ImportError:
    sys.exit("PyYAML 이 필요하다:  pip install pyyaml")

# 대한민국 eduroam 참여기관은 ROid 가 전부 이 값이다 (스펙 고정)
ROID = "kr01"
COUNTRY = "kr"

# lang 속성이 있는 필드는 en 이 반드시 있어야 검증을 통과한다
REQUIRED_LANG = "en"


class BuildError(Exception):
    pass


# ── XML 조립 도우미 ────────────────────────────────────────────────

def el(parent, tag, text=None, **attrs):
    e = ET.SubElement(parent, tag, {k: str(v) for k, v in attrs.items() if v is not None})
    if text is not None:
        e.text = str(text)
    return e


def lang_fields(parent, tag, value, where):
    """{en: ..., ko: ...} → <tag lang="en">…</tag> 를 언어 수만큼."""
    if value is None:
        return
    if not isinstance(value, dict):
        raise BuildError(f"{where}: {tag} 는 언어별 매핑이어야 한다 (예: {{en: ..., ko: ...}})")
    if REQUIRED_LANG not in value:
        raise BuildError(f"{where}: {tag} 에 '{REQUIRED_LANG}' 가 없다. 스펙상 영문은 필수다")
    for lang, text in value.items():
        el(parent, tag, text, lang=lang)


def addresses(parent, value, where):
    """{en: {street, city}, ko: {...}} → <address> 를 언어 수만큼 (주소는 lang 이 하위에 붙는다)."""
    if not value:
        return
    if REQUIRED_LANG not in value:
        raise BuildError(f"{where}: address 에 '{REQUIRED_LANG}' 가 없다")
    for lang, parts in value.items():
        missing = [k for k in ("street", "city") if not parts.get(k)]
        if missing:
            raise BuildError(f"{where}: address.{lang} 에 {', '.join(missing)} 가 없다")
        a = ET.SubElement(parent, "address")
        el(a, "street", parts["street"], lang=lang)
        el(a, "city", parts["city"], lang=lang)
        # postcode 는 XSD 에 없는 항목이다. YAML 에는 남겨두되 XML 로는 내보내지 않는다.


def contacts(parent, value, where):
    if not value:
        raise BuildError(f"{where}: contacts 가 최소 하나 있어야 한다")
    for c in value:
        e = ET.SubElement(parent, "contact")
        el(e, "name", c["name"])
        el(e, "email", c["email"])
        el(e, "phone", c["phone"])
        el(e, "type", c.get("type", 0))
        el(e, "privacy", c.get("privacy", 0))


# 전송 방식이다. 기관 종류(IdP/SP)가 아니다 — 그건 institution 의 type 이다.
SERVER_TYPES = {0: "UDP", 1: "TLS", 2: "F-ticks"}


def servers(parent, value, where):
    for s in value or []:
        t = s["type"]
        if t not in SERVER_TYPES:
            raise BuildError(f"{where}: server type {t!r} 은 없는 값이다. "
                             f"허용: {', '.join(f'{k}={v}' for k, v in SERVER_TYPES.items())}")
        e = ET.SubElement(parent, "server")
        el(e, "server_name", s["name"])
        el(e, "server_type", t)


# ── ts: git 커밋 시각에서 뽑는다 ──────────────────────────────────

def git_ts(path):
    """해당 파일의 마지막 커밋 시각(ISO 8601). 기관이 ts 를 직접 관리하지 않게 한다.

    커밋 이력이 없으면(로컬에서 아직 커밋 안 한 새 파일) 파일 수정 시각으로 대신한다.
    CI 에서는 항상 커밋 이력이 있으므로 이 폴백이 쓰이지 않는다.
    """
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "--", str(path)],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        if out:
            return out
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    mtime = datetime.datetime.fromtimestamp(path.stat().st_mtime).astimezone()
    print(f"  ! {path.name}: 커밋 이력이 없어 파일 수정 시각을 ts 로 쓴다 ({mtime.isoformat(timespec='seconds')})",
          file=sys.stderr)
    return mtime.isoformat(timespec="seconds")


# ── institution ───────────────────────────────────────────────────

def build_institution(root, data, src):
    where = src.name
    inst = ET.SubElement(root, "institution")

    el(inst, "instid", data["instid"])
    el(inst, "ROid", ROID)
    el(inst, "type", data["type"])
    el(inst, "stage", data.get("stage", 1))

    for r in data.get("realms", []):
        el(inst, "inst_realm", r)

    servers(inst, data.get("servers"), where)
    lang_fields(inst, "inst_name", data.get("name"), where)
    addresses(inst, data.get("address"), where)

    if data.get("coordinates"):
        el(inst, "coordinates", data["coordinates"])
    if data.get("inst_type"):
        el(inst, "inst_type", data["inst_type"])

    contacts(inst, data.get("contacts"), where)
    lang_fields(inst, "info_URL", data.get("info_url"), where)
    lang_fields(inst, "policy_URL", data.get("policy_url"), where)

    el(inst, "ts", data.get("ts") or git_ts(src))

    for loc in data.get("locations", []):
        build_location(inst, loc, where)


def build_location(inst, loc, where):
    e = ET.SubElement(inst, "location")
    el(e, "locationid", loc["id"])
    el(e, "coordinates", loc["coordinates"])
    el(e, "stage", loc.get("stage", 1))
    el(e, "type", loc.get("type", 0))
    lang_fields(e, "loc_name", loc.get("name"), where)
    addresses(e, loc.get("address"), where)
    if loc.get("location_type"):
        el(e, "location_type", loc["location_type"])
    if loc.get("contacts"):
        contacts(e, loc["contacts"], where)
    el(e, "SSID", loc.get("ssid", "eduroam"))
    for key, tag in (("operator_name", "operator_name"), ("enc_level", "enc_level"),
                     ("ap_no", "AP_no"), ("wired_no", "wired_no"), ("tag", "tag"),
                     ("availability", "availability"), ("operation_hours", "operation_hours")):
        if loc.get(key) is not None:
            el(e, tag, loc[key])
    lang_fields(e, "info_URL", loc.get("info_url"), where)


# ── RO ────────────────────────────────────────────────────────────

def build_ro(data, src):
    where = src.name
    root = ET.Element("ROs")
    ro = ET.SubElement(root, "RO")

    el(ro, "ROid", ROID)
    el(ro, "country", COUNTRY)
    el(ro, "stage", data.get("stage", 1))
    lang_fields(ro, "org_name", data.get("name"), where)
    addresses(ro, data.get("address"), where)
    if data.get("coordinates"):
        el(ro, "coordinates", data["coordinates"])
    servers(ro, data.get("servers"), where)
    contacts(ro, data.get("contacts"), where)
    lang_fields(ro, "info_URL", data.get("info_url"), where)
    lang_fields(ro, "policy_URL", data.get("policy_url"), where)

    el(ro, "ts", data.get("ts") or git_ts(src))
    return root


# ── 출력 ──────────────────────────────────────────────────────────

def write(root, path):
    ET.indent(root, "  ")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('<?xml version="1.0" encoding="UTF-8"?>\n'
                    + ET.tostring(root, encoding="unicode") + "\n")


def validate(xml_path, xsd_path):
    try:
        r = subprocess.run(["xmllint", "--noout", "--schema", str(xsd_path), str(xml_path)],
                           capture_output=True, text=True)
    except FileNotFoundError:
        sys.exit("xmllint 이 없어 --validate 를 할 수 없다.\n"
                 "  macOS: 기본 포함  ·  Debian/Ubuntu: apt-get install -y libxml2-utils")
    sys.stderr.write(r.stderr)
    return r.returncode == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dist", type=pathlib.Path)
    ap.add_argument("--validate", action="store_true", help="xmllint 로 XSD 검증까지 한다")
    args = ap.parse_args()

    here = pathlib.Path(__file__).parent
    errors = []

    # institution.xml — 앞에 _ 나 . 이 붙은 파일은 예시/초안으로 보고 건너뛴다
    root = ET.Element("institutions")
    files = sorted(f for f in (here / "inst.d").glob("*.y*ml")
                   if not f.name.startswith(("_", ".")))
    for f in files:
        try:
            build_institution(root, yaml.safe_load(f.read_text()), f)
        except BuildError as e:
            errors.append(str(e))
        except KeyError as e:
            errors.append(f"{f.name}: 필수 항목 {e} 가 없다")

    # ro.xml
    ro_src = here / "ro.yml"
    ro_root = None
    try:
        ro_root = build_ro(yaml.safe_load(ro_src.read_text()), ro_src)
    except (BuildError, KeyError) as e:
        errors.append(f"ro.yml: {e}")

    if errors:
        for e in errors:
            print(f"  ✗ {e}", file=sys.stderr)
        sys.exit(f"\n{len(errors)}건의 오류. 아무것도 쓰지 않았다.")

    ok = True
    if ro_root is not None:
        write(ro_root, args.out / "ro.xml")
        print(f"ro.xml            → {args.out / 'ro.xml'}")
        if args.validate:
            ok &= validate(args.out / "ro.xml", here / "schema/ro.xsd")

    if files:
        write(root, args.out / "institution.xml")
        print(f"institution.xml   → {args.out / 'institution.xml'}  ({len(files)}개 기관)")
        if args.validate:
            ok &= validate(args.out / "institution.xml", here / "schema/institution.xsd")
    else:
        # XSD 가 institution 최소 1개를 요구하므로 빈 문서는 만들지 않는다
        print("inst.d 에 기관 파일이 없다 — institution.xml 은 만들지 않았다", file=sys.stderr)

    if not ok:
        sys.exit("XSD 검증 실패")
    if args.validate:
        print("XSD 검증 통과")


if __name__ == "__main__":
    main()
