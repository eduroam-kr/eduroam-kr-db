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

NRO 서버는 `134.75.30.51` (`ssh -J ns root@...`), 설정은 `/opt/kr-nro/freeradius/` 다. 기관이 실제로 인증되는지 보려면 이 구조를 알아야 한다.

- **`.ac.kr` 은 전부 KREN RO 로 넘어간다.** `kren_ro.conf` 에 catch-all 정규식 realm `~^(.*\.)*ac\.kr$` 이 있어서 개별 conf 없이 모두 프록시된다. 즉 **`.ac.kr` 은 conf.d 에 없는 게 정상이다** — 없다고 빼면 100여 곳을 잘못 지운다.
- **그 밖의 `.kr` 은 기본이 거부다.** `~^(.*\.)*kr$` 이 `auth-reject` 로 잡혀 있다. 그래서 비(非) `.ac.kr` 기관은 `conf.d/` 에 자기 realm 이나 client 가 있어야만 동작한다.
- **`conf.disabled/` 는 읽히지 않는다.** `$INCLUDE conf.d/` 범위 밖이다. 여기 있으면 꺼진 것이다.

### 서버에 있는지 확인할 때 파일명만 보지 않는다

**SP-only 기관은 realm 이 없고 `client` 블록만 있다. 그 블록이 다른 기관 파일 안에 들어 있을 수 있다.** 대전컨벤션센터(`dcckorea.or.kr`)가 실제로 `conf.d/dime.or.kr.conf` 안에 `client 2015_dcckorea_or_kr_13` 으로 들어 있다 — 파일명으로 찾으면 "없음"으로 잘못 판단한다. 한 번 그렇게 틀렸다.

확인은 내용까지 본다.

```sh
ssh -J ns root@134.75.30.51 \
  'cd /opt/kr-nro/freeradius && grep -ohE "^realm[[:space:]]+[^ {]+" conf.d/*.conf;
   grep -rhoE "^client[[:space:]]+[0-9]{4}_[A-Za-z0-9_]+" conf.d/*.conf'
```

`conf.d/*.conf` 에는 RADIUS 공유 비밀키가 평문으로 있다. 필요한 필드만 뽑아 쓰고 키는 어디에도 남기지 않는다.

## 연락처를 넣는 기준

**스펙은 `contact_name` / `contact_email` / `contact_phone` / `contact_type` / `contact_privacy` 를 전부 필수로 표시한다** (스펙 PDF 3쪽, 굵은 글씨가 필수 표기). XSD 는 엘리먼트 존재만 강제하고 내용이 비어도 통과시키지만, 빈 값은 스펙을 벗어난 상태다. 채울 수 있으면 채운다.

**기관이 자기 홈페이지에 공개한 업무용 연락처는 그대로 쓴다.** eduroam 문의처로 공개해 둔 것을 eduroam 데이터베이스의 eduroam 연락처로 옮기는 것이므로 공개 목적 범위 안이다.

- **부서 대표 주소**(`infra@`, `staff@`, `netadm@`)는 `privacy: 1`(공개, 기본값). 담당자가 바뀌어도 살아 있다.
- **개인 업무 계정**(`parkj2@korea.ac.kr` 같은)은 `privacy: 0`(비공개)으로 넣는다. GÉANT·NRO 는 볼 수 있고 공개는 안 된다. 스펙이 이 용도로 만든 필드다. 나중에 부서 대표 주소를 확보하면 교체한다.
- **로그인 ID 예시는 연락처가 아니다.** eduroam 안내 페이지에는 `ID@기관.ac.kr`, `12345@...`, `3D121401@...` 같은 예시가 반드시 있다. 자동 수집하면 이게 가장 많이 걸린다.
- **다른 업무의 연락처를 끌어오지 않는다.** 계정 분실 문의, 학적팀 팩스 같은 것이 근처에 있어도 eduroam 담당이 아니면 쓰지 않는다.
- **내선번호에 국번을 붙였으면 주석에 적는다.** 추정이 섞인 값이라 나중에 확인해야 한다.

`name` 은 `<부서> eduroam 담당` → `<부서> wifi 담당` → `<부서> 담당` 순으로 구체적인 것을 쓴다.

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
