#!/usr/bin/env python3
"""KREN 이 올리는 institution.xml 과 이 저장소의 inst.d/ 를 견줘 차이를 보여준다.

  bin/check-kren.py                 # 원본을 받아서 비교
  bin/check-kren.py --file a.xml    # 받아 둔 파일로 비교

값을 자동으로 가져오지 않는다. 저쪽 XML 은 대학 RO 가 맡는 기관만 담아서
NRO 가 직접 realm 을 잡는 기관이 구조적으로 빠지고, 실제로 인증이 오가지
않는 realm 이 올라와 있는 경우도 있다. 그대로 덮어쓰면 고쳐 둔 값이
되돌아간다. 그래서 사람이 보고 판단하도록 차이만 적는다.

되풀이되는 차이는 etc/kren-ignore.yml 에 적어 두면 보고에서 빠진다.

차이가 있으면 1, 없으면 0 으로 끝난다.
"""

import argparse
import pathlib
import sys
import urllib.request
import xml.etree.ElementTree as ET

try:
    import yaml
except ImportError:
    sys.exit("PyYAML 이 필요하다:  pip install pyyaml")

URL = "http://www.eduroam.kr/general/institution.xml"
ROOT = pathlib.Path(__file__).resolve().parent.parent
IGNORE = ROOT / "etc" / "kren-ignore.yml"


def load_ours():
    """realm -> {instid, name_ko, name_en} (realm 하나가 기관 하나를 가리킨다)"""
    out = {}
    for p in sorted((ROOT / "inst.d").glob("*.yml")):
        if p.name.startswith("_"):
            continue
        d = yaml.safe_load(p.read_text(encoding="utf-8"))
        for r in d.get("realms") or []:
            out[r.lower()] = {
                "instid": d["instid"],
                "name_ko": (d.get("name") or {}).get("ko", ""),
                "name_en": (d.get("name") or {}).get("en", ""),
            }
    return out


def load_theirs(xml_bytes):
    out = {}
    for inst in ET.fromstring(xml_bytes):
        names = {n.get("lang"): (n.text or "").strip() for n in inst.findall("inst_name")}
        for r in inst.findall("inst_realm"):
            if r.text and r.text.strip():
                out[r.text.strip().lower()] = {
                    "instid": (inst.findtext("instid") or "").strip(),
                    "name_ko": names.get("ko", ""),
                    "name_en": names.get("en", ""),
                }
    return out


def load_ignore():
    if not IGNORE.exists():
        return {"realms": set(), "names": set()}
    d = yaml.safe_load(IGNORE.read_text(encoding="utf-8")) or {}
    return {"realms": set(d.get("realms") or []), "names": set(d.get("names") or [])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", help="받아 둔 institution.xml")
    ap.add_argument("--url", default=URL)
    args = ap.parse_args()

    if args.file:
        raw = pathlib.Path(args.file).read_bytes()
        src = args.file
    else:
        with urllib.request.urlopen(args.url, timeout=30) as r:
            raw = r.read()
        src = args.url

    ours, theirs = load_ours(), load_theirs(raw)
    ign = load_ignore()

    only_theirs = sorted(set(theirs) - set(ours) - ign["realms"])
    only_ours = sorted(set(ours) - set(theirs) - ign["realms"])
    renamed = sorted(
        r for r in set(ours) & set(theirs)
        if r not in ign["names"] and ours[r]["name_ko"] != theirs[r]["name_ko"]
    )

    print(f"원본   {src}")
    print(f"realm  저쪽 {len(theirs)} / 우리 {len(ours)}\n")

    if only_theirs:
        print(f"## 저쪽에만 있는 realm {len(only_theirs)}개 — 우리가 빠뜨렸는지 본다")
        for r in only_theirs:
            print(f"  + {r:<24} {theirs[r]['name_ko']}")
        print()
    if only_ours:
        print(f"## 우리에만 있는 realm {len(only_ours)}개 — 저쪽에 알려줄 것")
        for r in only_ours:
            print(f"  - {r:<24} {ours[r]['name_ko']}")
        print()
    if renamed:
        print(f"## 기관명이 다른 realm {len(renamed)}개")
        for r in renamed:
            print(f"  ~ {r:<24} 우리={ours[r]['name_ko']}  저쪽={theirs[r]['name_ko']}")
        print()

    n = len(only_theirs) + len(only_ours) + len(renamed)
    if n == 0:
        print("새로운 차이 없음.")
        return 0
    print(f"차이 {n}건. 확인한 뒤 되풀이해도 되는 것은 etc/kren-ignore.yml 에 적는다.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
