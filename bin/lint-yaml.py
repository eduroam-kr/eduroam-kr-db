#!/usr/bin/env python3
"""inst.d/ 의 기관 파일을 저장소 서식으로 맞춘다.

  bin/lint-yaml.py          # 어긋난 곳을 보여준다 (CI 용, 어긋나면 1)
  bin/lint-yaml.py --fix    # 파일을 고쳐 쓴다

PR 로 들어오는 YAML 은 들여쓰기도 항목 순서도 따옴표도 제각각이다. 사람이
리뷰에서 지적하면 왕복이 길어지므로, 기계가 맞출 수 있는 것은 기계가 맞춘다.

맞추는 것
  - 항목 순서 (kr → instid → type → realms → name → ... → locations)
  - 블록 스타일, 두 칸 들여쓰기, 줄 끝 주석 없음
  - 전화번호·URL 은 따옴표, 좌표는 숫자
  - 파일명과 instid 가 같은지

`_` 로 시작하는 파일은 건너뛴다 — 예시 파일은 주석이 본문이라 다시 쓰면 날아간다.
"""

import argparse
import pathlib
import re
import sys

try:
    import yaml
except ImportError:
    sys.exit("PyYAML 이 필요하다:  pip install pyyaml")

ROOT = pathlib.Path(__file__).resolve().parent.parent
INST = ROOT / "inst.d"

# 파일에 쓰는 순서. XML 순서와 별개다 — 사람이 읽는 순서다.
ORDER = ["kr", "instid", "type", "stage", "realms", "servers", "name", "address",
         "coordinate", "inst_type", "contacts", "info_url", "policy_url", "locations"]
KR_ORDER = ["type", "parent_ro", "univ_type", "year_joined", "campus"]
LOC_ORDER = ["id", "coordinates", "stage", "type", "name", "address", "location_type",
             "contacts", "ssid", "operator_name", "enc_level", "ap_no", "wired_no",
             "tag", "availability", "operation_hours", "info_url"]
CONTACT_ORDER = ["name", "email", "phone", "type", "privacy"]
ADDR_ORDER = ["street", "city"]
# 빈 줄을 앞에 두는 최상위 항목
BLANK_BEFORE = {"instid", "contacts", "info_url", "policy_url", "locations"}
# 언제나 따옴표로 감싸는 항목
QUOTED = {"phone"}
# YAML 이 문자열로 안 읽을 값들. 따옴표가 없으면 뜻이 바뀐다 —
# 04763 은 8진수, 2026-09-30 은 날짜, yes 는 참이 된다.
AMBIGUOUS = re.compile(r"""(?x)
    ^$ | ^\s | \s$                        # 빈 값·앞뒤 공백
  | ^[-+]?[\d_]+$ | ^[-+]?\d*\.\d+([eE][-+]?\d+)?$   # 숫자
  | ^0[bxo]? | ^[-+]?\d+:\d+              # 8진수·16진수·시각
  | ^\d{4}-\d{2}(-\d{2})?$               # 날짜
  | ^\d+,\d+$                            # Venue Info 코드 "1,7"
  | ^(y|Y|yes|Yes|YES|n|N|no|No|NO|true|True|TRUE|false|False|FALSE|on|On|ON|off|Off|OFF|null|Null|NULL|~)$
  | ^https?:// | ^[&*?|<>=!%@`{}\[\],#"'] | :\s | \s\#
""")


def order(d, keys):
    known = [k for k in keys if k in d]
    rest = [k for k in d if k not in keys]
    return known + rest, rest


def scalar(v, key=None):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v) if isinstance(v, float) else str(v)
    s = str(v)
    if key in QUOTED or AMBIGUOUS.search(s) or s.startswith("-"):
        return '"' + s.replace('"', '\\"') + '"'
    return s


def emit_map(d, keys, indent, out, quoted_parent=None):
    ks, unknown = order(d, keys)
    for k in ks:
        v = d[k]
        pad = " " * indent
        if isinstance(v, dict):
            out.append(f"{pad}{k}:")
            sub = ADDR_ORDER if k in ("en", "ko") else keys
            emit_map(v, sub, indent + 2, out)
        elif isinstance(v, list):
            out.append(f"{pad}{k}:")
            for item in v:
                if isinstance(item, dict):
                    sub = CONTACT_ORDER if k == "contacts" else LOC_ORDER
                    lines = []
                    emit_map(item, sub, indent + 4, lines)
                    lines[0] = f"{pad}  - " + lines[0].lstrip()
                    out.extend(lines)
                else:
                    out.append(f"{pad}  - {scalar(item, k)}")
        else:
            out.append(f"{pad}{k}: {scalar(v, k)}")
    return unknown


def render(data):
    out, unknown = [], []
    ks, rest = order(data, ORDER)
    unknown += rest
    for k in ks:
        if k in BLANK_BEFORE and out:
            out.append("")
        v = data[k]
        if k == "kr":
            out.append("kr:")
            unknown += emit_map(v, KR_ORDER, 2, out)
        elif isinstance(v, dict):
            out.append(f"{k}:")
            unknown += emit_map(v, ADDR_ORDER if k == "address" else ["en", "ko"], 2, out)
        elif isinstance(v, list):
            emit_map({k: v}, [k], 0, out)
        else:
            out.append(f"{k}: {scalar(v, k)}")
    return "\n".join(out) + "\n", unknown


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", action="store_true", help="파일을 고쳐 쓴다")
    args = ap.parse_args()

    bad = []
    for p in sorted(INST.glob("*.yml")):
        if p.name.startswith("_"):
            continue
        raw = p.read_text(encoding="utf-8")
        data = yaml.safe_load(raw)
        want, unknown = render(data)

        if unknown:
            bad.append((p, f"모르는 항목: {', '.join(sorted(set(unknown)))}"))
        if data.get("instid") != p.stem:
            bad.append((p, f"파일명과 instid 가 다르다 — instid={data.get('instid')}"))
        if want != raw:
            if args.fix:
                p.write_text(want, encoding="utf-8")
            else:
                bad.append((p, "서식이 저장소 규칙과 다르다"))

    if not bad:
        print("inst.d/ 서식 이상 없음." if not args.fix else "맞춤 완료.")
        return 0
    if args.fix:
        for p, why in bad:
            print(f"  {p.name}: {why}")
        return 1 if any("모르는" in w or "instid" in w for _, w in bad) else 0
    for p, why in bad:
        print(f"  {p.name}: {why}")
    print(f"\n{len(bad)}건. `python3 bin/lint-yaml.py --fix` 로 맞춘다.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
