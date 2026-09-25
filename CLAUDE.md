# eduroam-kr-db — 작업 규약

대한민국 eduroam 참여기관 정보를 YAML 로 두고, eduroam database v2 제출용 XML 로 빌드하는 저장소. 사이트가 아니라 **데이터**다. 무엇을 하는지는 [README.md](README.md) 에 있고, 이 파일은 어떻게 작업할지만 다룬다.

## 이 저장소가 지켜야 하는 것

**GÉANT harvester 가 보는 URL 이 여기서 나온다.** 그래서 두 가지가 다른 무엇보다 우선한다.

1. **깨진 XML 을 게시하지 않는다.** 검증 없이 `main` 에 들어가는 경로를 만들지 않는다. harvester 는 조용히 실패하고, 실패했다는 사실을 아무도 모른다.
2. **URL 을 바꾸지 않는다.** `/institution.xml` 과 `/ro.xml` 의 주소는 GÉANT 에 한 번 등록하면 바꾸기 번거롭다. 파일명·경로를 옮기는 변경은 등록 갱신까지 한 묶음으로 처리한다.

이 저장소를 사이트(`site-template-2` 등)와 합치지 않는 이유도 이것이다. 사이트 개편 중에 데이터 URL 이 404 가 되면 안 된다.

## 스키마는 손대지 않는다

`schema/institution.xsd`, `schema/ro.xsd` 는 GÉANT 공식 파일을 그대로 받아둔 것이다. 고치지 않는다. 검증이 실패하면 스키마가 아니라 우리 쪽이 틀린 것이다.

갱신이 필요하면 통째로 다시 받는다.

```sh
curl -sSO https://monitor.eduroam.org/eduroam-database/v2/docs/eduroam-database-xsd-ver30112021.zip
```

스펙 버전이 올라가면 XSD 교체가 아니라 ADR 을 먼저 쓴다 — 기존 YAML 전부가 영향을 받는다.

## 엘리먼트 순서

XSD 가 `xs:sequence` 라서 **순서가 강제된다.** `build.py` 의 함수들이 그 순서를 코드 순서로 표현하고 있다. 항목을 추가할 때 함수 안에서 아무 데나 끼워 넣으면 검증에서 떨어진다.

institution:

```
instid → ROid → type → stage → inst_realm* → server* → inst_name+ → address*
→ coordinates? → inst_type? → contact+ → info_URL* → policy_URL* → ts → location*
```

location:

```
locationid → coordinates → stage → type → loc_name* → address* → location_type?
→ contact* → SSID → operator_name? → enc_level? → AP_no? → wired_no? → tag?
→ availability? → operation_hours? → info_URL*
```

RO:

```
ROid → country → stage → org_name+ → address+ → coordinates? → server*
→ contact+ → info_URL+ → policy_URL+ → ts
```

## 값을 짐작하지 않는다

열거형은 전부 XSD 에 정의되어 있다. 기억으로 적으면 틀린다 — 실제로 두 번 틀렸다.

- **`server_type` 은 전송 방식이다**: `0`=UDP, `1`=TLS, `2`=F-ticks. IdP/SP 구분이 아니다. 기관 종류는 최상위 `type` (`IdP` / `SP` / `IdP+SP`) 이다.
- **location 의 `contact` 에도 `type` 이 있다.** institution 의 contact 과 필드가 같다.

새 필드를 다루기 전에 XSD 를 열어 `simpleType` 의 `enumeration` 을 읽는다.

## XSD 가 못 잡는 규칙은 빌드가 잡는다

스펙 본문에는 있는데 스키마로 표현할 수 없는 규칙이 있다. 검증기를 통과해도 틀린 것이므로 `build.py` 가 막는다.

- **`type: SP` 에는 realm 을 적지 않는다.** 스펙 표의 `inst_realm` 설명이 `(only for IdP or IdP+SP)` 이고 각주가 "for type SP no realms should be specified" 다. XSD 는 `minOccurs="0" maxOccurs="unbounded"` 라서 SP 에 realm 이 있어도 통과시킨다. → 오류로 막음.
- **IdP 인데 realm 이 없으면** 인증 요청이 도달하지 않는다. 스펙이 명시적으로 금지하진 않아 → 경고.
- **영문(`en`)** 은 이름에만 필수다. 스펙 각주가 `name in English is required` 라고 이름에 대해서만 말하고, URL 은 `language info` 만 요구한다. → 이름은 오류, URL 은 경고.

같은 성격의 규칙을 새로 발견하면 여기에 적고 `build.py` 에 넣는다. XML 에서 realm 은 `<inst_realm>` 엘리먼트를 반복해서 표현한다 — 구분자도 속성도 없다.

## `ts` 는 사람이 관리하지 않는다

`build.py` 가 각 파일의 **마지막 커밋 시각**(`git log -1 --format=%cI -- <file>`)을 `ts` 로 넣는다. 기관이 내용을 고치면 커밋 시각이 자동으로 따라오므로 "ts 갱신을 잊었다" 는 실패 유형이 아예 없어진다.

그래서 **CI 의 checkout 은 반드시 `fetch-depth: 0`** 이다. 얕은 클론이면 모든 파일의 마지막 커밋이 같은 하나로 보여서 `ts` 가 전부 같아진다. 워크플로에서 이 옵션을 빼지 않는다.

YAML 에 `ts:` 를 직접 쓰면 그 값이 이긴다. 과거 시점을 보존해야 하는 특수한 경우에만 쓴다.

커밋 이력이 없는 파일(로컬에서 아직 커밋 안 한 새 파일)은 파일 수정 시각으로 대신하고 경고를 낸다. CI 에서는 이 경로를 타지 않는다.

## 입력 스키마는 사람이 틀리기 어렵게 만든다

YAML 은 XML 을 그대로 옮긴 것이 아니다. 같은 값을 두 번 쓰게 하거나 순서를 헷갈리게 하는 자리는 스키마 쪽에서 없앤다.

- **좌표는 `latitude` / `longitude` 로 나눠 받는다.** XML 은 `경도,위도` 한 문자열인데 지도 앱은 대개 반대 순서로 보여준다. 문자열로 받으면 뒤집힌 걸 아무도 눈치채지 못하므로 `build.py` 가 문자열을 **거부**한다.
- **연락처의 `type`·`privacy` 는 적지 않는다.** 이 저장소는 부서 수준에서 공개 가능한 연락처만 받으므로 `type=1`(부서) · `privacy=1`(공개) 가 기본이다. 다른 값이 필요할 때만 쓴다.
- **`location` 의 `type` 은 적지 않는다.** 캠퍼스 단위로 잡으므로 `1`(영역)이 기본이다.
- **`location` 의 `info_url` 은 적지 않는다.** 기관 값을 물려받는다. 그 위치만 다른 안내 페이지를 쓸 때만 적는다.
- **`ROid` 는 적지 않는다.** 빌드가 `kr01` 을 넣는다.
- **`ts` 는 적지 않는다.** 커밋 시각에서 들어온다.

새 필드를 열 때도 같은 기준으로 본다 — 기관이 매번 같은 값을 적게 되는 항목이면 기본값이나 상속으로 없앤다.

## Venue Info 코드

`inst_type` 은 IEEE Std 802.11-2012 의 표 8-52(group) · 8-53(type) 에서 고른다. eduroam 스펙은 이 표를 싣지 않고 clause 8.4.1.34 를 참조만 하므로, 값을 기억으로 적지 말고 표를 본다.

확인된 값: `3,3` University or College · `2,8` Research and Development Facility · `2,7` Professional Office · `1,7` Convention Center · `1,8` Library · `1,9` Museum · `5,1` Hospital · `3,1` School Primary · `3,2` School Secondary.

선택 항목이라 확실하지 않으면 비운다. 틀린 값을 넣는 것보다 낫다.

## 등록 기관과 RADIUS 서버의 관계

대한민국 eduroam 은 두 층으로 나뉜다.

- **KREN RO** — 대부분의 `.ac.kr` 대학이 여기 붙는다. NRO 서버에는 realm conf 가 없는 것이 정상이다.
- **NRO** — 연구소(`.re.kr`)는 전부 여기 직접 붙고, `.ac.kr` 중에도 KAIST·GIST·POSTECH·DGIST 처럼 직결인 곳이 있다. 서버는 `134.75.30.51` (`ssh -J ns root@...`), realm conf 는 `/opt/kr-nro/freeradius/conf.d/<realm>.conf` 다.

따라서 **"NRO 서버에 realm 이 없다" 는 사실만으로 기관을 뺄 수 없다.** KREN RO 산하면 없는 게 맞다. 뺄 수 있는 것은 **KREN RO 산하도 아니고 NRO 서버에도 없는** 경우뿐이다 — 인증이 실제로 동작하지 않는 상태다.

## `inst.disabled/`

제출 XML 에서 빼되 기록은 남길 기관을 둔다. `build.py` 는 `inst.d/` 만 읽으므로 여기 있는 파일은 빌드에 들어가지 않는다.

파일 머리에 **왜 껐는지와 언제 다시 켤 수 있는지**를 적는다. 조건이 충족되면 `inst.d/` 로 옮기고 머리말을 지운다. 지우지 말고 옮기는 이유는, 기관이 빠진 사실 자체가 나중에 설명이 필요한 정보이기 때문이다.

## 기관 파일

- 파일명은 `inst.d/<realm>.yml`. realm 과 파일명을 일치시켜야 무엇이 있는지 목록만 보고 안다.
- `_` 나 `.` 으로 시작하는 파일은 빌드에서 제외된다. 예시와 작업 중인 초안을 두는 자리다.
- **PR 하나는 기관 하나.** 여러 기관을 한 PR 에 담으면 리뷰도 되돌리기도 어려워진다.
- `ROid` 를 YAML 에 쓰지 않는다. 빌드가 `kr01` 을 넣는다. 파일마다 적으면 언젠가 하나가 틀린다.

## 빌드 실패는 메시지로 갚는다

이 저장소의 주 사용자는 git 에 익숙하지 않은 기관 전산 담당자다. 빌드가 실패하면 **어느 파일의 무엇이 왜 틀렸는지** 한 줄로 나와야 한다. `KeyError: 'instid'` 같은 스택 트레이스를 그대로 노출하지 않는다.

`build.py` 는 오류를 모아서 한 번에 보여주고, 하나라도 있으면 아무것도 쓰지 않는다. 첫 오류에서 멈추면 담당자가 PR 을 여러 번 왕복해야 한다.

## 로컬

```sh
pip install pyyaml
python3 build.py --validate
```

`dist/` 는 산출물이라 커밋하지 않는다 (`.gitignore`). 게시본은 Actions 가 만든다.

## 프로젝트 운영

`prj/` 5파일 시스템. 규칙 전문은 [prj/PROCESS.md](prj/PROCESS.md).

커밋은 한 줄, 주제별로 쪼갠다. `Co-Authored-By: Claude <noreply@anthropic.com>` 는 붙이고 `Claude-Session` 은 붙이지 않는다 (public 저장소).

## 주석은 줄 끝에 달지 않는다

YAML 이든 Python 이든, 주석은 **자기 줄에** 쓴다.

```yaml
# 도메인 형식의 기관 고유 ID
instid: example.ac.kr
```

```yaml
instid: example.ac.kr          # 이렇게 쓰지 않는다
```

`cat x.yml | grep -v '#'` 로 값만 훑는 사용 방식 때문이다. 줄 끝 주석이 있으면 그 줄이 통째로 사라져서 데이터까지 안 보인다.

같은 이유로 **플로우 매핑(`{ a: 1, b: 2 }`)을 쓰지 않는다.** 한 줄에 여러 값이 들어가면 그 줄 하나가 사라질 때 잃는 게 많고, diff 에서도 무엇이 바뀌었는지 안 보인다. 블록 스타일로 편다.

```yaml
contacts:
  - name: IT Helpdesk
    email: helpdesk@example.ac.kr
    type: 1
```

`inst.d/` 파일을 생성하는 도구를 쓸 때도 이 두 규칙을 지킨다.

## 문서

하드 랩 금지 — 문단·목록 항목을 각각 한 줄로 쓰고 줄바꿈은 렌더러에 맡긴다. 하드 랩이 있으면 단어 하나 고쳤을 때 이후 모든 줄이 리플로우되어 diff 가 못 쓰게 된다.
