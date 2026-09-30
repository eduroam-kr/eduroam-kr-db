# 기관 로고

`db.eduroam.kreonet.net` 이 그대로 서빙한다. NRO 사이트와 안내 페이지가 가져다 쓴다.

## 파일 이름

```
<realm>.<확장자>
```

`<realm>` 은 `inst.d/<realm>.yml` 의 파일명과 같다. 기관당 한 장이다.

확장자는 웹에서 그대로 뜨는 형식이면 된다 — `svg` `png` `jpg` `gif` `webp`. 벡터가 있으면 `svg` 를 쓴다.

가로세로비는 기관마다 다르다. 가져다 쓰는 쪽이 `object-fit` 으로 맞춘다.

**심볼판을 고른다.** 기관명을 붙인 시그니처는 가로로 길어서 목록에서 작아 보인다.

넣기 전에 `python3 bin/lint-logo.py` 를 돌린다. 흰 바탕에서 안 보이는 것, 애니메이션, 너무 큰 파일, 가로로 너무 긴 것을 잡아 준다. 기준과 이유는 [AGENTS.md](../AGENTS.md) 의 '기관 로고' 에 있다.

CMYK JPEG 은 브라우저가 색을 틀리게 그리므로 RGB 로 바꾼다.

## 권리

각 로고의 권리는 해당 기관에 있다. 이 저장소는 eduroam 참여기관을 **알아보게 하는 식별 표시**로만 담아 두며, 기관을 보증하거나 후원 관계를 나타내지 않는다. 기관이 내려달라고 하면 내린다.

eduroam 로고와 `eduroam®` 은 [GÉANT Association 의 등록상표](https://eduroam.org/eduroam-trademark-information/)이고 여기 두지 않는다.

## 출처

[eduroam.kr 이용 가능 대학](https://www.eduroam.kr/service-status/universities) 에 올라와 있는 것을 받았다. 기관이 더 나은 파일을 주면 교체한다.
