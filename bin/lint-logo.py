#!/usr/bin/env python3
"""logo/ 를 검사한다.

  bin/lint-logo.py     # 어긋나면 1, 경고만 있으면 0

로고는 db.eduroam.kreonet.net 이 그대로 서빙하고 NRO 사이트가 가져다 쓴다.
사람이 눈으로 보고 넘기면 흰 바탕에서 안 보이는 파일이나 3MB 짜리가 들어온다.
기계가 볼 수 있는 것은 기계가 본다.

막는 것(오류)
  - inst.d 에 없는 realm 의 파일
  - 한 기관에 파일이 둘 이상
  - 흰 바탕에서 안 보이는 것 — 머리글용 흰색 로고를 그대로 받으면 이렇게 된다
  - 애니메이션 — 목록에서 움직이면 읽는 데 방해가 된다
  - 파일 300KB 초과, 또는 긴 변 1200px 초과

알리는 것(경고)
  - 로고가 없는 기관
  - 가로세로비가 0.4:1 ~ 2.5:1 을 벗어난 것. 정사각 칸에 넣으면 2.5:1 부터
    로고 높이가 칸의 40% 아래로 떨어져 옆 기관보다 작아 보인다. 심볼만 있는
    판이 있으면 그것으로 바꾼다. 기관이 시그니처만 공개했으면 그대로 둔다.
"""

import pathlib
import re
import sys

try:
    import yaml
    from PIL import Image
except ImportError:
    sys.exit("PyYAML 과 Pillow 가 필요하다:  pip install pyyaml pillow")

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOGO, INST = ROOT / "logo", ROOT / "inst.d"
MAX_BYTES, MAX_PX = 300 * 1024, 1200
RATIO_LO, RATIO_HI = 0.4, 2.5


def size_of(p):
    """(가로, 세로). 읽을 수 없으면 None."""
    if p.suffix == ".svg":
        t = p.read_text(encoding="utf-8", errors="replace")[:4000]
        m = (re.search(r'viewBox="[\d.\-]+[, ]+[\d.\-]+[, ]+([\d.]+)[, ]+([\d.]+)"', t)
             or re.search(r'width="([\d.]+)[a-z]*"[^>]*height="([\d.]+)[a-z]*"', t, re.S))
        return (float(m.group(1)), float(m.group(2))) if m else None
    try:
        return Image.open(p).size
    except Exception:
        return None


def main():
    realms = {p.stem for p in INST.glob("*.yml") if not p.name.startswith("_")}
    files = [p for p in sorted(LOGO.iterdir()) if p.suffix != ".md"]
    errors, warns = [], []

    seen = {}
    for p in files:
        seen.setdefault(p.stem, []).append(p.name)
        if p.stem not in realms:
            errors.append(f"{p.name}: inst.d 에 {p.stem}.yml 이 없다")
        if p.stat().st_size > MAX_BYTES:
            errors.append(f"{p.name}: {p.stat().st_size // 1024}KB — {MAX_BYTES // 1024}KB 를 넘는다")

        wh = size_of(p)
        if wh is None:
            errors.append(f"{p.name}: 크기를 읽을 수 없다")
            continue
        w, h = wh
        if p.suffix != ".svg":
            im = Image.open(p)
            if getattr(im, "n_frames", 1) > 1:
                errors.append(f"{p.name}: 애니메이션이다 ({im.n_frames}프레임)")
            if max(w, h) > MAX_PX:
                errors.append(f"{p.name}: {int(w)}x{int(h)} — 긴 변이 {MAX_PX}px 를 넘는다")
            px = [q for q in im.convert("RGBA").get_flattened_data() if q[3] > 40]
            if not px or sum(1 for r, g, b, _ in px if r > 235 and g > 235 and b > 235) / len(px) > 0.95:
                errors.append(f"{p.name}: 흰 바탕에서 안 보인다 — 컬러판을 받는다")

        r = w / h
        if not (RATIO_LO <= r <= RATIO_HI):
            warns.append(f"{p.name}: {int(w)}x{int(h)} = {r:.1f}:1 — 정사각 칸에서 높이가 "
                         f"{100 / max(r, 1 / r):.0f}% 로 줄어든다")

    for realm, names in seen.items():
        if len(names) > 1:
            errors.append(f"{realm}: 파일이 둘 이상이다 — {', '.join(names)}. 기관당 한 장이다")
    for realm in sorted(realms - set(seen)):
        warns.append(f"{realm}: 로고가 없다")

    for w in warns:
        print(f"  ! {w}")
    for e in errors:
        print(f"  ✗ {e}")
    print(f"\n로고 {len(files)}개 / 기관 {len(realms)}곳 — 오류 {len(errors)}건, 경고 {len(warns)}건")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
