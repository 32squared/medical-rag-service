"""인쇄용 매뉴얼 HTML 조립 — assets/*.svg 인라인 + 전 기능 상세. Chrome headless로 PDF화."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(os.path.dirname(HERE), "assets")


def svg(name):
    with open(os.path.join(ASSETS, name), encoding="utf-8") as f:
        s = f.read()
    return f'<div class="fig">{s}</div>'


CSS = """
@page { size: A4; margin: 15mm 13mm 16mm 13mm; }
* { box-sizing: border-box; }
body { font-family:'Malgun Gothic','Noto Sans KR','Segoe UI',sans-serif; font-size:10.5pt;
  line-height:1.55; color:#26261f; margin:0; }
h1 { font-size:24pt; font-weight:600; color:#0f3d2e; margin:0 0 6px; }
h2 { font-size:15pt; font-weight:600; color:#0f6e56; border-bottom:2px solid #1D9E75;
  padding-bottom:4px; margin:24px 0 10px; page-break-after:avoid; }
h3 { font-size:12pt; font-weight:600; color:#26215c; margin:14px 0 6px; page-break-after:avoid; }
p { margin:6px 0; }
ul { margin:6px 0; padding-left:18px; } li { margin:3px 0; }
code { font-family:Consolas,'Courier New',monospace; background:#f1efe8; padding:0 3px;
  border-radius:3px; font-size:9pt; color:#4a1b0c; }
table { border-collapse:collapse; width:100%; font-size:9.3pt; margin:10px 0; page-break-inside:avoid; }
th,td { border:1px solid #cfcdc4; padding:5px 7px; text-align:left; vertical-align:top; }
th { background:#eef4f1; color:#0f3d2e; font-weight:600; }
.fig { text-align:center; margin:14px 0; page-break-inside:avoid; }
.fig svg { max-width:100%; height:auto; border:1px solid #e6e4da; border-radius:8px; padding:6px; background:#fff; }
.cap { font-size:9pt; color:#5F5E5A; margin-top:4px; }
.cover { height:247mm; display:flex; flex-direction:column; justify-content:center;
  align-items:center; text-align:center; page-break-after:always; }
.cover .sub { font-size:13pt; color:#0f6e56; margin-top:8px; }
.cover .meta { font-size:10.5pt; color:#5F5E5A; margin-top:28px; }
.note { background:#f1efe8; border-left:3px solid #1D9E75; padding:8px 12px; margin:10px 0;
  border-radius:0 6px 6px 0; font-size:9.8pt; }
.danger { background:#FCEBEB; border-left:3px solid #A32D2D; padding:8px 12px; margin:10px 0;
  border-radius:0 6px 6px 0; font-size:9.8pt; color:#501313; }
.toc { font-size:10.5pt; page-break-after:always; }
.toc li { margin:4px 0; }
section { page-break-before:always; }
.sec0 { page-break-before:avoid; }
/* viewer mockup */
.vw { display:grid; grid-template-columns:128px 1fr 1fr; gap:8px; margin:10px 0; page-break-inside:avoid;
  font-size:9pt; }
.vw .pane { border:1px solid #D3D1C7; border-radius:10px; padding:8px; background:#fff; }
.vw .ph { font-size:8.5pt; color:#888780; margin-bottom:6px; }
.vw .card { border:1px solid #D3D1C7; border-radius:7px; padding:6px; margin-bottom:6px; }
.vw .chip { display:inline-block; font-size:8.5pt; border-radius:6px; padding:1px 6px; margin:1px 2px 1px 0; }
.vw .gray { background:#F1EFE8; }
.vw .red { background:#FCEBEB; color:#A32D2D; }
.vw .grn { background:#EAF3DE; color:#27500A; }
.vw .amb { background:#FAEEDA; color:#854F0B; }
.vw .info { background:#E6F1FB; color:#185FA5; border:1px solid #B5D4F4; }
.vw .bubble { background:#F1EFE8; border-radius:9px; padding:5px 8px; display:inline-block; }
.vw .cite { font-size:8pt; background:#E6F1FB; color:#185FA5; border-radius:3px; padding:0 3px; }
.vw .btn { display:inline-block; font-size:8.5pt; border:1px solid #B4B2A9; border-radius:7px;
  padding:3px 8px; margin:2px 3px 0 0; }
"""

VIEWER = """
<div class="vw">
  <div class="pane">
    <div class="ph">① 페르소나</div>
    <div class="card"><b>고혈압 어르신</b><div style="color:#888780;font-size:8.5pt;margin-top:2px">65세 · 고혈압</div>
      <div style="margin-top:5px"><span class="chip red">혈압 경고</span></div></div>
    <div style="color:#888780;margin-bottom:4px">다른 페르소나</div>
    <div><span class="chip gray">당뇨 직장인</span><span class="chip gray">임신부</span><span class="chip gray">천식 아동</span></div>
  </div>
  <div class="pane">
    <div class="ph">② 개인화 정보</div>
    <div style="margin-bottom:6px"><span class="chip red">혈압 경고</span><span class="chip grn">심박 안정</span><span class="chip amb">추세 상승</span></div>
    <div class="card"><b>결합 블록</b><div style="margin-top:2px">최근 혈압이 ‘경고’ 구간이에요. 재측정하고 지속되면 진료를 권합니다.</div></div>
    <div class="card info"><b>LLM 비식별 맥락 (방향2)</b><div style="margin-top:2px">혈압=경고 <span style="opacity:.7">(밴드 라벨만)</span></div></div>
    <div class="card"><b>혈압 추이 (14일)</b>
      <svg width="100%" viewBox="0 0 210 50"><rect x="22" y="5" width="184" height="12" rx="2" fill="#FCEBEB"/><rect x="22" y="17" width="184" height="10" rx="2" fill="#FAEEDA"/><polyline points="26,36 56,34 86,30 116,27 146,20 176,15 202,11" fill="none" stroke="#185FA5" stroke-width="1.4"/><circle cx="202" cy="11" r="2.6" fill="#A32D2D"/></svg></div>
  </div>
  <div class="pane">
    <div class="ph">③ 대화</div>
    <div style="text-align:right;margin-bottom:6px"><span class="bubble">혈압이 높게 나왔어요</span></div>
    <div class="card">일시적으로 높을 수 있어 다시 측정해 확인하세요 <span class="cite">1</span>. 두통·가슴통증이 함께면 바로 진료가 필요합니다 <span class="cite">2</span>.</div>
    <div style="margin-bottom:6px"><span class="chip info">🔒 개인맥락 반영됨 — 혈압=경고</span></div>
    <div style="border-top:1px solid #D3D1C7;padding-top:6px">
      <div style="margin-bottom:4px"><span style="color:#888780">(1/3)</span> 증상이 시작된 지 얼마나 됐나요?</div>
      <span class="btn">오늘</span><span class="btn">2~3일</span><span class="btn">일주일+</span><span class="btn" style="color:#888780">괜찮아요</span>
    </div>
  </div>
</div>
"""

BODY = """
<div class="cover">
  <h1>나만의 주치의 — 전체 기능·개발 매뉴얼</h1>
  <div class="sub">medical-rag-service · 의료법 경계 안의 한국어 의료정보 RAG</div>
  <div class="meta">기준일 2026-06-22 · 출시 전 검토용 프로토타입<br>웰니스 코칭 에이전트(기획 단계)는 범위 밖</div>
</div>

<div class="toc">
  <h2 class="sec0">목차</h2>
  <ol>
    <li>개요</li><li>시스템 아키텍처</li><li>경계선 설계 (안전의 핵심)</li>
    <li>안전 불변식</li><li>RAG 생성 파이프라인</li><li>개인화 — 해석 엔진 · 2경로 · 방향2 6게이트</li>
    <li>방향2 관찰성 (배지)</li><li>멀티턴 문진</li><li>뷰어 화면 (페르소나 테스트)</li>
    <li>개선 루프 (이벤트 스토어)</li><li>성능</li><li>데이터 · 마이그레이션</li>
    <li>운영 (배포 · 환경 변수)</li><li>테스트</li><li>출시 전 블로커</li>
  </ol>
</div>

<section class="sec0"><h2>1. 개요</h2>
<p><b>의료법(무면허 의료행위 27조) 경계 안에서</b> 개인 건강 데이터를 활용하는 <b>한국어 의료정보 RAG</b>. 진단·처방 단정 0, 거절 대신 내비게이션(어디로 가야 하나)으로 욕구를 충족. B2B2C(건강관리 앱 임베드, GPT/Gemini와 경쟁). 파트너 대화 플랫폼(<code>wraith</code>)에 SSE로 연결.</p>
<div class="note">핵심 설계 = <b>경계선 설계</b>: 원시 측정값은 결정적 로컬 엔진이 해석해 <b>중립 밴드 라벨</b>로만 LLM·국외에 넘긴다.</div></section>

<section><h2>2. 시스템 아키텍처</h2>
__SVG_PIPELINE__
<p class="cap">그림 1. 입력 → 개인화 해석(원시값 0) → 분류·검색·근거게이트 → 방향2 주입(옵트인) → LLM 생성 → 가드레일 후처리 → wraith SSE → 개선 루프.</p>
<p><b>개인화 결합은 2경로</b>(둘 다 원시값 미투입): ① (기본) 결정적 중립 블록을 생성 <i>후</i> 답변에 후append, ② (방향2·옵트인) 비식별 밴드 라벨만 LLM system_prompt에 주입(6게이트 fail-closed, 기본 off).</p></section>

<section><h2>3. 경계선 설계 (안전의 핵심)</h2>
__SVG_BOUNDARY__
<p class="cap">그림 2. 원시 측정값은 결정적 해석 엔진에서 멈추고, 경계선 오른쪽으로는 밴드 라벨만 넘어간다.</p>
<p>위험의 축은 <b>개인 귀속 진단</b>이지 원시 수치 자체가 아니다. 따라서 ① 원시값(152/96)은 LLM 프롬프트에 절대 미투입(불변식 I1), ② 사용자에게도 중립 3단 라벨(안정/주의/경고)만 노출(I12), ③ 질환명 단정 0(I2).</p></section>

<section><h2>4. 안전 불변식 (전 기능 공통)</h2>
<table><tr><th>ID</th><th>규칙</th><th>강제 위치</th></tr>
<tr><td>I1</td><td>원시 측정값을 표면화·LLM투입 안 함. 밴드 라벨·노트만.</td><td>vital_rules · 후append</td></tr>
<tr><td>I2</td><td>개인 귀속 진단 단정 0 (질환명 게이트)</td><td>personalization_safety C21</td></tr>
<tr><td>I7</td><td>응급 감지 시 개인화 결합 억제 (응급 안내 우선)</td><td>rag_engine · 방향2 G3</td></tr>
<tr><td>I8</td><td>임상 판독 금지 신호(ECG·웰니스 합성점수)는 밴드 조회 자체 안 함</td><td>vital_rules denied</td></tr>
<tr><td>I12</td><td>사용자 라벨은 중립 3단(안정/주의/경고)만. 질환 라벨은 내부 감사용.</td><td>vital_rules</td></tr>
<tr><td>게이트</td><td>질의 scope와 무관한 finding 미표면화 (과노출 차단)</td><td>relevance_gate</td></tr>
<tr><td>C20</td><td>주입 블록의 원시값·질환명 백스톱 스캔</td><td>scan_personal_block</td></tr>
<tr><td>C22</td><td>거짓안심("정상입니다") 백스톱 + 골든셋</td><td>find_false_reassurance</td></tr>
<tr><td>E2</td><td>분석 이벤트는 비식별(라벨·카운트·불리언)만</td><td>analytics_events.sanitize</td></tr>
</table></section>

<section><h2>5. RAG 생성 파이프라인</h2>
<p>라이브 경로는 <code>rag_engine.generate_response</code>(스트리밍 제너레이터).</p>
<h3>종료 4경로</h3>
<table><tr><th>경로</th><th>조건</th><th>동작</th></tr>
<tr><td>answer_shown</td><td>정상</td><td>생성 + 개인화 후append + 인용</td></tr>
<tr><td>insufficient_evidence</td><td>근거 부족</td><td>거절 → 내비게이션(어디로)</td></tr>
<tr><td>emergency_redirect</td><td>응급 분류</td><td>119·응급실, 개인화 억제(I7)</td></tr>
<tr><td>triage_clarify</td><td>트리아지</td><td>되묻기</td></tr></table>
<h3>단계</h3>
<ul>
<li><b>분류·재작성</b>: medical_classifier(intent·도메인) + 멀티턴 후속 재작성(followup_rewriter, 응급이면 미재작성).</li>
<li><b>검색·근거 게이트</b>: hybrid_search(BM25+벡터, top_k=5) → retrieval_router가 top1점수·관련청크·토픽으로 SUFFICIENT/WEAK/INSUFFICIENT 판정.</li>
<li><b>가드레일 후처리</b>: ComplianceAnalyzer 재분석 → CRITICAL 차단 / HIGH 1회 재생성 / 오탐 필터. 면책 상·하단 자동 부착.</li>
<li><b>인용</b>: 본문 [n]→청크 매핑. citation_verifier·grounding은 shadow(로그·검수 신호, 답변 무변경).</li>
</ul></section>

<section><h2>6. 개인화 — 해석 엔진 · 2경로 · 방향2 6게이트</h2>
<h3>해석 엔진 4축 (원시값 노출 0)</h3>
<table><tr><th>축</th><th>모듈</th><th>산출</th></tr>
<tr><td>밴드</td><td>vital_rules.run / lookup_band</td><td>혈압·산소·체온·심박·BMI → 안정/주의/경고</td></tr>
<tr><td>추세</td><td>run_trends / label_trend</td><td>지속상승/저하/불안정 (건강판단 금지)</td></tr>
<tr><td>환경</td><td>env_rules.air_quality_finding</td><td>나쁨→주의/매우나쁨→경고, 환기 권유</td></tr>
<tr><td>교차</td><td>match_cross_signals</td><td>I9 화이트리스트(혈압+BMI 대사묶음)</td></tr></table>
<h3>방향2 — 비식별 밴드 라벨 LLM 주입 (6게이트 fail-closed)</h3>
__SVG_GATES__
<p class="cap">그림 3. G1~G6 모두 통과해야 주입. 하나라도 미충족이면 미주입(fail-closed). 들어가는 것은 중립 밴드 라벨뿐 — 원시값·진단명 0.</p></section>

<section><h2>7. 방향2 관찰성 (배지)</h2>
<p>주입이 실제 일어났는지 답변만으론 알기 어렵다 → 주입된 밴드를 <code>STOP.personal_injected</code>로 내려보내 뷰어가 <b>🔒 배지</b>로 표시. 미주입이면 빈 리스트(음성 확인). A/B 실측: ON이면 경고 밴드를 반영해 "⚠️ 서둘러 진료" 섹션이 추가되고, OFF엔 없음.</p></section>

<section><h2>8. 멀티턴 문진</h2>
<p>간단히 물으면 <b>답변을 먼저</b> 주고, 그 답변을 바탕으로 <b>한 번에 한 질문</b>씩 선택지를 제시(Claude Code 인풋 방식). 모든 선택이 모이면 "원질의 / 문진: …"로 정밀 재안내. followups.clarify가 토픽별 질문+선택지를 생성, 뷰어가 버튼으로 렌더.</p></section>

<section><h2>9. 뷰어 화면 (페르소나 테스트)</h2>
<p>localhost:8770 · 3분할 반응형. ① 페르소나 선택 ② 개인화 정보(밴드·결합블록·LLM 맥락·차트·처방) ③ 대화(답변·인용·개인맥락 배지·문진 버튼).</p>
__VIEWER__
<p class="cap">그림 4. 페르소나 테스트 뷰어 3분할 화면 구성(고혈압 어르신 · 혈압 경고 예시).</p></section>

<section><h2>10. 개선 루프 (이벤트 스토어)</h2>
__SVG_LOOP__
<p class="cap">그림 5. 진입·종료 4종·피드백 이벤트가 비식별 이벤트 스토어로 모여 BI·품질·개선으로 흐른다.</p>
<p>허브 = 이벤트 스토어(Postgres, analytics_events). emit()은 화이트리스트 sanitize(라벨·카운트·불리언만, 금지키 구조적 제거). BI=Metabase/Grafana, 품질=골든셋·judge. PostHog는 선택. rag_queries는 원문 보관(내부 감사용, BI 미사용).</p></section>

<section><h2>11. 성능 (2026-06-22)</h2>
<p>체감 응답 ~40초 → ~8초(warm). 진범은 LLM/검색이 아니라 <b>SSE 연결을 30초 늦게 닫던 keep-alive</b>였다.</p>
<table><tr><th>측정</th><th>이전</th><th>지금(warm)</th></tr>
<tr><td>Cloud Run 요청 레이턴시</td><td>~40초</td><td>~7.7초</td></tr>
<tr><td>첫 토큰 전 추론(프리필)</td><td>12.75초</td><td>~1초</td></tr>
<tr><td>꼬리(마지막 토큰→STOP)</td><td>~30초</td><td>~0초</td></tr></table>
<ul>
<li><b>SSE 연결 즉시 종료</b>: <code>Connection: close</code> + close_connection (keep-alive+settimeout(30) 유휴 대기 제거).</li>
<li><b>reasoning_effort=minimal</b>: gpt-5.4-mini 지원값 minimal/low/medium/high (none은 400, fail-safe).</li>
<li><b>DB 후처리 비차단화</b>: 감사·검수·analytics 데몬 스레드.</li>
<li><b>INSUFFICIENT 인용-0건 재생성 생략</b>.</li>
</ul></section>

<section><h2>12. 데이터 · 마이그레이션 (PG + _sqlite)</h2>
<table><tr><th>#</th><th>테이블·변경</th></tr>
<tr><td>001</td><td>kb_sources·kb_documents·kb_chunks·llm_providers·rag_queries</td></tr>
<tr><td>005</td><td>evidence_grounding(근거 게이트 컬럼)</td></tr>
<tr><td>010</td><td>vital_reference_ranges</td></tr>
<tr><td>011</td><td>conversations 호환 컬럼</td></tr>
<tr><td>013</td><td>rag_queries 멀티턴 감사 컬럼</td></tr>
<tr><td>014</td><td>rag_projects</td></tr>
<tr><td>015</td><td>analytics_events(비식별 이벤트)</td></tr>
<tr><td>016</td><td>response_feedback(명시 피드백)</td></tr></table>
<div class="note">012 미사용(예약). SQLite 러너는 ; split → 주석에 세미콜론 금지. 영속 개인화(personal_record 등)는 017+ 예약. 방향2는 마이그레이션 없음(env 플래그).</div></section>

<section><h2>13. 운영 (배포 · 환경 변수)</h2>
<p><b>배포</b>: deploy-rag.ps1 → Cloud Run <code>medical-rag-dev</code>(asia-northeast3). RUN_MODE=rag, gpt-5.4-mini, LLM_REASONING_EFFORT=minimal(영속).</p>
<div class="danger"><b>개인화 플래그 리셋 주의</b>: PERSONAL_SIGNAL_TO_LLM·ALLOW_CROSS_BORDER_PERSONAL는 컴플라이언스상 deploy 스크립트에 미포함(기본 off=fail-closed). --set-env-vars 전체교체 재배포마다 off로 리셋 → 시연 시 매 배포 후 <code>gcloud run services update ... --update-env-vars</code>로 재적용.</div></section>

<section><h2>14. 테스트 · 출시 전 블로커</h2>
<p><code>python -m pytest tests/ -q</code> — 664개 수집. 순수 함수·결정적 위주. 골든셋: 멀티턴 게이트(≥80%), 거짓안심 0(C22), 페르소나 E2E.</p>
<div class="danger"><b>🔴 출시 차단</b> — A 의료법 27조 변호사 검토(밴드 라벨=개인 의학 평가가 의료행위로 해석될 리스크) · B 민감정보+국외이전 실제 동의 시스템(현재 게이트만) · D KB 의료진 검수.<br><b>🟠</b> C 국내 LLM 경로 · E 영속·암호화 · G 운영등급 배포.</div>
<div class="note"><b>정직 포인트</b>: 개인화를 하는 순간(방향2 off여도 후append 포함) 의료법 질문은 존재. "원시값 미투입"은 LLM 한정이고 원문은 rag_queries에 저장. "기본 off=안전"이 아니라 "그 기능 미사용"일 뿐. 페르소나=합성 데이터, KB=dev. <b>테스트 그린 ≠ 출시 가능.</b></div></section>
"""


def main():
    body = (BODY
            .replace("__SVG_PIPELINE__", svg("rag-pipeline.svg"))
            .replace("__SVG_BOUNDARY__", svg("boundary.svg"))
            .replace("__SVG_GATES__", svg("gates.svg"))
            .replace("__SVG_LOOP__", svg("improvement-loop.svg"))
            .replace("__VIEWER__", VIEWER))
    html = f"<!DOCTYPE html><html lang='ko'><head><meta charset='utf-8'><style>{CSS}</style></head><body>{body}</body></html>"
    out = os.path.join(HERE, "manual.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print("WROTE", out, len(html), "bytes")


if __name__ == "__main__":
    main()
