#!/usr/bin/env python3
"""YAML 원본을 eduroam database v2 제출용 XML 로 빌드한다.

  inst.d/<realm>.yml  →  dist/general/institution.xml   (<institutions> 안에 기관 전부)
  ro.yml              →  dist/general/ro.xml            (<ROs> 안에 NRO 자신)

general/ 아래에 두는 것은 eduroam database 를 올리는 곳들이 따르는 관례다.
KREN 도 www.eduroam.kr/general/institution.xml 로 올린다. GÉANT 에 한 번
등록한 주소는 바꾸기 번거로우므로 처음부터 맞춘다.

엘리먼트 순서는 schema/*.xsd 의 xs:sequence 가 강제한다. 아래 ORDER 상수가
그 순서를 그대로 옮긴 것이고, 손으로 바꾸지 않는다 — 바꾸려면 XSD 를 먼저 본다.

usage: build.py [--out dist] [--validate]
"""

import argparse
import datetime
import json
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

# 스펙 문서는 lang 이 붙는 항목에 영문을 요구하지만 XSD 는 강제하지 않는다.
# 기관명은 GÉANT monitor 에 국제적으로 노출되므로 없으면 오류로 막고,
# 안내 URL 은 한국어 페이지밖에 없는 기관이 많아 경고만 낸다.
REQUIRED_LANG = "en"

# inst_type 은 IEEE Std 802.11-2012 의 표 8-52(group) · 8-53(type) 에서 고른
# "group,type" 코드다. eduroam 스펙은 이 표를 싣지 않고 clause 8.4.1.34 를
# 참조만 하므로, 코드를 기억으로 적지 말고 표를 보고 여기에 뜻과 함께 늘린다.
VENUE_TYPES = {
    "0,0": "Unspecified / Unspecified",
    "1,7": "Assembly / Convention Center",
    "1,8": "Assembly / Library",
    "1,9": "Assembly / Museum",
    "2,0": "Business / Unspecified",
    "2,7": "Business / Professional Office",
    "2,8": "Business / Research and Development Facility",
    "3,1": "Educational / School, Primary",
    "3,2": "Educational / School, Secondary",
    "3,3": "Educational / University or College",
    "5,1": "Institutional / Hospital",
}

# 대한민국 참여기관은 거의 다 대학 아니면 연구기관이다. 숫자만 봐서는 무엇인지
# 알 수 없으므로 이 둘은 이름으로 적는다. 나머지는 위 표의 코드를 그대로 쓴다.
# 고를 코드가 없으면 기타 — 표가 그 경우로 0,0 Unspecified 를 두고 있다.
INST_TYPES = {
    "대학": "3,3",
    "연구": "2,8",
    "기타": "0,0",
}

# kr: 아래는 eduroam 대한민국 고유 항목이다. 제출 XML 에는 들어가지 않고
# NRO 사이트가 쓴다. 스펙 항목과 섞이지 않도록 이 블록 안에만 둔다.
#   type        eduroamKR 위키의 '구분'
#   parent_ro   인증 요청이 어디를 거치는지. NRO 서버의 conf.d 에 realm 이
#               직접 잡혀 있으면 nro, 아니면 대학 RO(KREN)를 거친다.
#   univ_type   설립 형태. 대학에만 적는다.
#   year_joined 위키의 '가입년도'. 연도까지만 안다.
#   campus      캠퍼스가 여럿일 때만 적는다. 본교 하나뿐이면 적지 않는다.
KR_TYPES = ("대학", "출연", "기타")
KR_PARENT_RO = ("nro", "kren_ro")
KR_UNIV_TYPES = ("국립", "국립대법인", "공립", "사립", "특별법법인", "기타")
KR_KEYS = ("type", "parent_ro", "univ_type", "year_joined", "campus")

WARNINGS = []


class BuildError(Exception):
    pass


# ── XML 조립 도우미 ────────────────────────────────────────────────

def el(parent, tag, text=None, **attrs):
    e = ET.SubElement(parent, tag, {k: str(v) for k, v in attrs.items() if v is not None})
    if text is not None:
        e.text = str(text)
    return e


def lang_fields(parent, tag, value, where, require_en=True, warn=True):
    """{en: ..., ko: ...} → <tag lang="en">…</tag> 를 언어 수만큼."""
    if value is None:
        return
    if not isinstance(value, dict):
        raise BuildError(f"{where}: {tag} 는 언어별 매핑이어야 한다 (예: {{en: ..., ko: ...}})")
    if REQUIRED_LANG not in value:
        msg = f"{where}: {tag} 에 '{REQUIRED_LANG}' 가 없다"
        if require_en:
            raise BuildError(msg + ". 스펙상 영문은 필수다")
        if warn:
            WARNINGS.append(msg)
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
        raise BuildError(f"{where}: contacts 가 최소 하나 있어야 한다. "
                         f"기관 연락처가 없으면 ro.yml 의 default_contact 가 대신 들어간다")
    for c in value:
        e = ET.SubElement(parent, "contact")
        # XSD 는 셋 다 요구하지만 빈 문자열을 허용한다. 전화만 있고 메일이 없는
        # 기관이 많아서, 없는 것은 빈 값으로 두고 있는 것만 채운다.
        el(e, "name", c["name"])
        el(e, "email", c.get("email", ""))
        el(e, "phone", c.get("phone", ""))
        # 기관 연락처는 부서 수준에서 공개 가능한 것만 적는 것이 이 저장소의 방침이라
        # type=1(부서) · privacy=1(공개) 이 기본이다. 필요하면 파일에서 덮어쓴다.
        el(e, "type", c.get("type", 1))
        el(e, "privacy", c.get("privacy", 1))


# 전송 방식이다. 기관 종류(IdP/SP)가 아니다 — 그건 institution 의 type 이다.
SERVER_TYPES = {0: "UDP", 1: "TLS", 2: "F-ticks"}


def coord(value, where, field="coordinates"):
    """{latitude: .., longitude: ..} → "경도,위도". XSD 가 요구하는 순서가 경도 먼저다."""
    if value is None:
        return None
    if isinstance(value, str):
        raise BuildError(f"{where}: {field} 는 latitude/longitude 로 나눠 쓴다. "
                         f'문자열 "{value}" 은 경도·위도 순서를 헷갈리기 쉬워 받지 않는다')
    missing = [k for k in ("latitude", "longitude") if value.get(k) is None]
    if missing:
        raise BuildError(f"{where}: {field} 에 {', '.join(missing)} 가 없다")
    return f'{value["longitude"]},{value["latitude"]}'


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

def build_institution(root, data, src, default_contact=None, fallback_log=None):
    where = src.name
    inst = ET.SubElement(root, "institution")

    el(inst, "instid", data["instid"])
    el(inst, "ROid", ROID)
    el(inst, "type", data["type"])
    el(inst, "stage", data.get("stage", 1))

    # XSD 는 realm 을 0..N 으로만 정의한다. "SP 에는 realm 을 적지 않는다" 는
    # 스펙 본문에만 있는 규칙이라 (표의 inst_realm 설명이 "only for IdP or IdP+SP")
    # 검증기로는 안 걸린다. 여기서 막는다.
    realms = data.get("realms") or []
    inst_type_ = data["type"]
    if inst_type_ == "SP" and realms:
        raise BuildError(f"{where}: type 이 SP 인데 realms 가 있다. "
                         f"SP 에는 realm 을 적지 않는다 — {', '.join(realms)}")
    if inst_type_ != "SP" and not realms:
        WARNINGS.append(f"{where}: type 이 {inst_type_} 인데 realms 가 없다. "
                        f"IdP 는 realm 이 있어야 인증 요청이 도달한다")
    for r in realms:
        el(inst, "inst_realm", r)

    servers(inst, data.get("servers"), where)
    lang_fields(inst, "inst_name", data.get("name"), where)
    addresses(inst, data.get("address"), where)

    c = coord(data.get("coordinate") or data.get("coordinates"), where, "coordinate")
    if c:
        el(inst, "coordinates", c)
    if data.get("inst_type"):
        name = data["inst_type"]
        if name in INST_TYPES:
            code = INST_TYPES[name]
        elif name in VENUE_TYPES:
            code = name
        else:
            raise BuildError(f"{where}: inst_type 은 이름({' / '.join(INST_TYPES)}) "
                             f"이나 Venue Info 코드({' / '.join(VENUE_TYPES)}) 중 "
                             f"하나다 — 받은 값 {name!r}. 표에 없는 코드를 써야 하면 "
                             f"build.py 의 VENUE_TYPES 에 뜻과 함께 먼저 적는다")
        el(inst, "inst_type", code)

    # kr: 는 제출 XML 에 안 들어간다. 그래서 오타가 나도 빌드가 조용히 지나가
    # 버린다. 여기서 한 번 본다.
    kr = data.get("kr")
    if kr is not None:
        if not isinstance(kr, dict):
            raise BuildError(f"{where}: kr 은 매핑이어야 한다 (예: kr: {{type: 사립}})")
        unknown = set(kr) - set(KR_KEYS)
        if unknown:
            raise BuildError(f"{where}: kr 에 모르는 항목이 있다 — "
                             f"{', '.join(sorted(unknown))}. 새 항목을 늘리려면 "
                             f"build.py 의 KR_KEYS 부터 고친다")
        if kr.get("type") and kr["type"] not in KR_TYPES:
            raise BuildError(f"{where}: kr.type 은 {' / '.join(KR_TYPES)} 중 하나다 "
                             f"— 받은 값 {kr['type']!r}")
        for key, allowed in (("parent_ro", KR_PARENT_RO), ("univ_type", KR_UNIV_TYPES)):
            if kr.get(key) and kr[key] not in allowed:
                raise BuildError(f"{where}: kr.{key} 는 {' / '.join(allowed)} 중 "
                                 f"하나다 — 받은 값 {kr[key]!r}")
        if kr.get("univ_type") and kr.get("type") != "대학":
            raise BuildError(f"{where}: kr.univ_type 은 대학에만 적는다 "
                             f"— kr.type 이 {kr.get('type')!r} 이다")
        cam = kr.get("campus")
        if cam is not None:
            if not isinstance(cam, list) or not all(isinstance(c, str) and c.strip() for c in cam):
                raise BuildError(f"{where}: kr.campus 는 캠퍼스 이름 목록이다 — 받은 값 {cam!r}")
            if len(cam) < 2:
                raise BuildError(f"{where}: kr.campus 는 캠퍼스가 둘 이상일 때만 적는다. "
                                 f"하나뿐이면 항목을 지운다 — 받은 값 {cam!r}")
        yj = kr.get("year_joined")
        if yj is not None and not (isinstance(yj, int) and 2000 <= yj <= 2100):
            raise BuildError(f"{where}: kr.year_joined 는 네 자리 연도다 — 받은 값 {yj!r}")

    cs = data.get("contacts")
    if not cs and default_contact:
        cs = [default_contact]
        if fallback_log is not None:
            fallback_log.append(data["instid"])
    contacts(inst, cs, where)
    lang_fields(inst, "info_URL", data.get("info_url"), where, require_en=False)
    lang_fields(inst, "policy_URL", data.get("policy_url"), where, require_en=False)

    el(inst, "ts", data.get("ts") or git_ts(src))

    for loc in data.get("locations", []):
        build_location(inst, loc, where, data.get("info_url"))


def build_location(inst, loc, where, inherit_info_url=None):
    e = ET.SubElement(inst, "location")
    el(e, "locationid", loc["id"])
    el(e, "coordinates", coord(loc.get("coordinates") or loc.get("coordinate"), where))
    el(e, "stage", loc.get("stage", 1))
    # 0=단일 지점, 1=영역, 2=이동체. 캠퍼스 단위로 잡으므로 영역이 기본이다.
    el(e, "type", loc.get("type", 1))
    lang_fields(e, "loc_name", loc.get("name"), where, require_en=False)
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
    # location 의 안내 URL 은 대개 기관 것과 같다. 없으면 기관 값을 물려받는다.
    # 물려받은 값은 기관 쪽에서 이미 검사했으므로 여기서 또 경고하지 않는다.
    own = loc.get("info_url")
    lang_fields(e, "info_URL", own or inherit_info_url, where,
                require_en=False, warn=bool(own))


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
    c = coord(data.get("coordinate") or data.get("coordinates"), where, "coordinate")
    if c:
        el(ro, "coordinates", c)
    servers(ro, data.get("servers"), where)
    contacts(ro, data.get("contacts"), where)
    lang_fields(ro, "info_URL", data.get("info_url"), where, require_en=False)
    lang_fields(ro, "policy_URL", data.get("policy_url"), where, require_en=False)

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


# ── NRO 사이트용 JSON ──────────────────────────────────────────────
#
# 제출 XML 과 따로 낸다. general/ 은 GÉANT 에 등록한 주소라 모양을 바꿀 수 없고,
# 사이트가 쓰기에는 XML 이 무겁다. 여기서 필요한 것만 추려 둔다.

def write_site_json(here, files, out):
    logos = {p.stem: p.name for p in (here / "logo").iterdir() if p.suffix != ".md"}
    insts, feats = [], []
    for f in files:
        d = yaml.safe_load(f.read_text())
        realm = d["instid"]
        kr = d.get("kr") or {}
        locs = d.get("locations") or []
        insts.append({
            "realm": realm,
            "realms": d.get("realms") or [],
            "name": d.get("name") or {},
            "type": kr.get("type"),
            "parent_ro": kr.get("parent_ro"),
            "univ_type": kr.get("univ_type"),
            "year_joined": kr.get("year_joined"),
            "campus": kr.get("campus") or [],
            "info_url": (d.get("info_url") or {}).get("ko") or (d.get("info_url") or {}).get("en"),
            "logo": logos.get(realm),
            "locations": len(locs),
        })
        for loc in locs:
            c = loc.get("coordinates") or {}
            if not c: continue
            feats.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [c["longitude"], c["latitude"]]},
                "properties": {
                    "realm": realm,
                    "name": (d.get("name") or {}).get("ko", realm),
                    "name_en": (d.get("name") or {}).get("en", ""),
                    "loc": (loc.get("name") or {}).get("ko") or (loc.get("name") or {}).get("en", ""),
                    "logo": logos.get(realm),
                    "info_url": (d.get("info_url") or {}).get("ko"),
                },
            })
    insts.sort(key=lambda x: x["name"].get("ko", ""))
    built = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    d = out / "site"
    d.mkdir(parents=True, exist_ok=True)
    (d / "institutions.json").write_text(json.dumps(
        {"built": built, "count": len(insts), "institutions": insts},
        ensure_ascii=False, indent=1), encoding="utf-8")
    (d / "locations.geojson").write_text(json.dumps(
        {"type": "FeatureCollection", "built": built, "features": feats},
        ensure_ascii=False, indent=1), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dist", type=pathlib.Path)
    ap.add_argument("--validate", action="store_true", help="xmllint 로 XSD 검증까지 한다")
    args = ap.parse_args()

    here = pathlib.Path(__file__).parent
    errors = []

    ro_src = here / "ro.yml"
    ro_data = yaml.safe_load(ro_src.read_text())

    # 기관이 자기 연락처를 주지 않았을 때 대신 들어가는 값. ro.yml 에서 정한다.
    default_contact = ro_data.get("default_contact")
    fallback = []

    # institution.xml — 앞에 _ 나 . 이 붙은 파일은 예시/초안으로 보고 건너뛴다
    root = ET.Element("institutions")
    files = sorted(f for f in (here / "inst.d").glob("*.y*ml")
                   if not f.name.startswith(("_", ".")))
    for f in files:
        try:
            build_institution(root, yaml.safe_load(f.read_text()), f, default_contact, fallback)
        except BuildError as e:
            errors.append(str(e))
        except KeyError as e:
            errors.append(f"{f.name}: 필수 항목 {e} 가 없다")

    ro_root = None
    try:
        ro_root = build_ro(ro_data, ro_src)
    except (BuildError, KeyError) as e:
        errors.append(f"ro.yml: {e}")

    if errors:
        for e in errors:
            print(f"  ✗ {e}", file=sys.stderr)
        sys.exit(f"\n{len(errors)}건의 오류. 아무것도 쓰지 않았다.")

    ok = True
    if ro_root is not None:
        write(ro_root, args.out / "general" / "ro.xml")
        print(f"ro.xml            → {args.out / 'general' / 'ro.xml'}")
        if args.validate:
            ok &= validate(args.out / "general" / "ro.xml", here / "schema/ro.xsd")

    if files:
        write(root, args.out / "general" / "institution.xml")
        print(f"institution.xml   → {args.out / 'general' / 'institution.xml'}  ({len(files)}개 기관)")
        if args.validate:
            ok &= validate(args.out / "general" / "institution.xml", here / "schema/institution.xsd")
    else:
        # XSD 가 institution 최소 1개를 요구하므로 빈 문서는 만들지 않는다
        print("inst.d 에 기관 파일이 없다 — institution.xml 은 만들지 않았다", file=sys.stderr)

    if files:
        write_site_json(here, files, args.out)
        print(f"site json         → {args.out / 'site'}/  (지도·목록용)")

    if WARNINGS:
        print(f"\n경고 {len(WARNINGS)}건 — 빌드는 되지만 스펙 문서의 권고를 벗어난다")
        for w in WARNINGS[:10]:
            print(f"  ! {w}")
        if len(WARNINGS) > 10:
            print(f"  … 외 {len(WARNINGS) - 10}건")

    if fallback:
        print(f"\n기관 연락처가 없어 ro.yml 의 default_contact 를 쓴 곳: {len(fallback)}곳")
        print("  " + ", ".join(fallback))
        print("  해당 기관이 자기 연락처를 PR 로 넣으면 그 값이 이긴다.")

    if not ok:
        sys.exit("XSD 검증 실패")
    if args.validate:
        print("XSD 검증 통과")


if __name__ == "__main__":
    main()
