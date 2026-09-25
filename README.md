# eduroamKR database 📇

대한민국(`kr01`) eduroam 참여기관 정보를 모아 [eduroam database specification v2.0.1](https://monitor.eduroam.org/fact_eduroam_db.php) 제출용 XML 로 빌드하는 저장소입니다.

기관은 **자기 YAML 파일 하나만 Pull Request** 하면 됩니다. 별도 제출 창구도, 기관이 XML 을 호스팅할 필요도 없습니다.

```
inst.d/<realm>.yml   ──┐
                       ├─► GitHub Actions ─► institution.xml   (참여기관 전체)
ro.yml               ──┘                     ro.xml            (NRO 정보)
```

---

## 기관 정보 등록·수정하기

1. 이 저장소를 fork 합니다.
2. [`inst.d/_example.ac.kr.yml`](inst.d/_example.ac.kr.yml) 을 복사해 `inst.d/<기관realm>.yml` 로 만듭니다.

    ```
    inst.d/kaist.ac.kr.yml
    ```

3. 내용을 기관 정보에 맞게 고칩니다. 각 항목의 의미는 예시 파일 주석에 있습니다.
4. Pull Request 를 보냅니다. **자기 기관 파일 하나만** 담아주세요.

PR 을 열면 GitHub Actions 가 XML 을 빌드하고 공식 XSD 로 검증합니다. 초록불이면 그대로 병합됩니다. 빨간불이면 어느 줄이 왜 틀렸는지 로그에 나옵니다.

병합되면 몇 분 안에 아래 URL 이 갱신되고, GÉANT eduroam monitor 가 이걸 harvest 합니다.

### 안 적어도 되는 것

| 항목 | 이유 |
|---|---|
| `ROid` | 대한민국 기관은 전부 `kr01` 이라 빌드가 넣습니다 |
| `ts` (마지막 수정 시각) | 파일의 **마지막 커밋 시각**에서 자동으로 들어갑니다. 고치는 걸 잊을 일이 없습니다 |
| XML 문법 | YAML 만 쓰면 됩니다. 닫는 태그도, 엘리먼트 순서도 신경 쓰지 않습니다 |

### 자주 틀리는 것

- **영문(`en`)은 필수입니다.** `name`, `address`, `info_url`, `policy_url`, `loc_name` 은 한국어만 있으면 검증에서 떨어집니다.
- **`server` 의 `type` 은 전송 방식입니다** — `0`=UDP, `1`=TLS, `2`=F-ticks. IdP/SP 구분이 아닙니다. 기관 종류는 최상위 `type` (`IdP` / `SP` / `IdP+SP`) 입니다.
- **SP 전용 기관은 `realms` 항목을 통째로 지웁니다.** 빈 목록으로 두지 않습니다.
- `coordinates` 는 **경도,위도** 순입니다. 지도 앱에서 복사하면 대개 반대라 뒤집어야 합니다.

---

## 산출물

| URL | 내용 |
|---|---|
| `/institution.xml` | `<institutions>` — 참여기관 전체 |
| `/ro.xml` | `<ROs>` — NRO(eduroamKR) 정보 |

두 파일 모두 `main` 에 push 될 때마다 다시 빌드되어 GitHub Pages 로 게시됩니다.

제출 전 스펙 준수 여부는 GÉANT 검증기로도 확인할 수 있습니다.

```
https://monitor.eduroam.org/eduroam-database/v2/scripts/xml_validation_test.php?url=<URL>
```

---

## 로컬에서 돌려보기

```sh
pip install pyyaml
python3 build.py --validate      # dist/ 에 빌드하고 XSD 검증까지
```

`xmllint` 가 있으면 `--validate` 가 공식 XSD([`schema/`](schema/))로 검증합니다. macOS 와 대부분의 리눅스에 기본으로 들어 있습니다.

파일명이 `_` 나 `.` 으로 시작하면 빌드에서 제외됩니다 — 예시 파일과 작업 중인 초안을 두는 자리입니다.

---

## 저장소 구조

```
inst.d/            기관별 YAML — 기관이 PR 로 고치는 유일한 곳
ro.yml             NRO 자신의 정보 — NRO 담당자만 고침
schema/            GÉANT 공식 XSD (그대로 vendor, 손대지 않음)
build.py           YAML → XML 빌드 + 검증
public/index.html  게시 페이지의 안내문
prj/               프로젝트 운영 문서 (PRD·PROCESS·TASKS·ADR·NOTES)
```
