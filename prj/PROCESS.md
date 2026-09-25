# Project Process

이 프로젝트는 5파일 시스템을 기본 운영 구조로 한다.

* Ryan Carson 3파일 시스템
    - `PRD.md`: 무엇을 왜 만드는지, 성공 기준이 무엇인지 적는다.
    - `PROCESS.md`: 프로젝트를 어떻게 운영할지 적는다.
    - `TASKS.md`: 번호가 붙은 실행 작업을 관리한다.
* 보조 기억
    - `ADR.md`: 번호가 붙은 아키텍처 결정 기록.
    - `NOTES.md`: PRD, PROCESS, TASKS, ADR 중 어디에도 깔끔히 들어가지 않는 중요한 관찰.

## 번호 체계

작업은 `T-0001`, `T-0002`처럼 번호를 붙인다.

아키텍처 결정은 `ADR-0001`, `ADR-0002`처럼 번호를 붙인다.

탐색 관찰은 필요할 때 `OBS-YYYYMMDD-NN` 형식을 쓴다.

## 상태 표기

작업 상태:

- `TODO`: 아직 시작하지 않음.
- `DOING`: 현재 진행 중.
- `BLOCKED`: 사용자 입력이나 외부 상태 없이는 진행 불가.
- `DONE`: 현재 범위에서 충분히 완료 및 확인됨.
- `DROP`: 의도적으로 하지 않기로 함.

ADR 상태:

- `Proposed`: 유력하지만 아직 검증 중인 결정.
- `Accepted`: 현재 프로젝트 방향으로 채택한 결정.
- `Superseded`: 이후 ADR에 의해 대체된 결정.

## Git 로그 규칙

커밋 로그는 나중에 `git log --oneline`만 봐도 작업 흐름이 보이게 쓴다.

기본 형식:

```text
<type>(<scope>): <무엇을 왜 했는지>
```

`scope`는 필요할 때만 쓴다.

주요 type:

- `feat`: 새 기능.
- `fix`: 버그 수정.
- `docs`: 문서 수정.
- `refactor`: 동작 변화가 거의 없는 구조 변경.
- `test`: 테스트 추가 또는 수정.
- `chore`: 빌드, 설정, 정리 작업.
- `release`: 릴리스 준비.

작업 번호가 있으면 제목에 포함한다.

```text
Task T-0007: 팔레트 module navigation 계획 추가
Task T-0007 Stage 1: module definition 초안 작성
```

PR이나 외부 기여를 반영할 때는 출처가 보이게 쓴다.

```text
PR #12 반영: userscript host build 설정 정리
Merge local/devel: module definition 구조 조정
```

예:

```text
docs(process): git 로그 규칙 추가
feat(palette): module 선택 상태와 query 보존 분리
fix(userscript): overlay가 원본 검색 입력을 가로채지 않게 수정
refactor(adapter): portal route 실행 계약 분리
```

원칙:

- 커밋 하나는 하나의 의도를 가진다.
- 제목에는 "파일을 바꿈"보다 "왜 바꿨는지"를 쓴다.
- 큰 작업은 `Task T-0000 Stage N`처럼 쪼개서 남긴다.
- 문서화 커밋도 의미 있는 산출물이면 별도 커밋으로 남긴다.
- 자동 생성물, 빌드 결과, 임시 캡처는 필요할 때만 커밋한다.
- 커밋 로그에 Claude-Session 은 기재하지 않는다.
