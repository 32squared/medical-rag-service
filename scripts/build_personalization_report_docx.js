// 개인화 종합 보고서 → Word(.docx) 생성. 한글 렌더링: 맑은 고딕.
// 실행: NODE_PATH="$(npm root -g)" node scripts/build_personalization_report_docx.js
const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  AlignmentType, LevelFormat, HeadingLevel, BorderStyle, WidthType, ShadingType,
  TableOfContents, PageBreak, Header, Footer, PageNumber,
} = require("docx");

const FONT = "Malgun Gothic"; // 맑은 고딕 (Windows 한글 기본)
const CONTENT_W = 9360;       // US Letter, 1" 여백

const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };
const HEAD_FILL = "1F4E79";   // 진한 파랑 헤더
const ALT_FILL = "EDF2F7";

function t(text, opts = {}) { return new TextRun({ text, font: FONT, ...opts }); }
function p(text, opts = {}) {
  return new Paragraph({ children: [t(text, opts.run || {})], spacing: { after: 120, ...(opts.spacing || {}) }, ...opts.p });
}
function h1(text) { return new Paragraph({ heading: HeadingLevel.HEADING_1, children: [t(text, { bold: true })] }); }
function h2(text) { return new Paragraph({ heading: HeadingLevel.HEADING_2, children: [t(text, { bold: true })] }); }
function bullet(text) {
  return new Paragraph({ numbering: { reference: "b", level: 0 }, spacing: { after: 60 }, children: [t(text)] });
}

// 표 생성: header 행 + body 행들. colW 배열(DXA, 합=CONTENT_W).
function table(colW, header, rows) {
  const mk = (cells, isHead) => new TableRow({
    tableHeader: !!isHead,
    children: cells.map((c, i) => new TableCell({
      borders, width: { size: colW[i], type: WidthType.DXA },
      shading: { fill: isHead ? HEAD_FILL : (rows.indexOf(cells) % 2 ? ALT_FILL : "FFFFFF"), type: ShadingType.CLEAR },
      margins: { top: 60, bottom: 60, left: 110, right: 110 },
      children: String(c).split("\n").map((line) =>
        new Paragraph({ spacing: { after: 0 }, children: [t(line, isHead ? { bold: true, color: "FFFFFF", size: 19 } : { size: 19 })] })),
    })),
  });
  return new Table({
    width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: colW,
    rows: [mk(header, true), ...rows.map((r) => mk(r, false))],
  });
}

const doc = new Document({
  styles: {
    default: { document: { run: { font: FONT, size: 21 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 30, bold: true, font: FONT, color: "1F4E79" },
        paragraph: { spacing: { before: 280, after: 160 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: FONT, color: "2E5496" },
        paragraph: { spacing: { before: 200, after: 120 }, outlineLevel: 1 } },
    ],
  },
  numbering: {
    config: [{ reference: "b", levels: [
      { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 460, hanging: 260 } } } }] }],
  },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [t("medical-rag-service · 개인화 종합 보고서 · ", { size: 16, color: "888888" }),
                new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 16, color: "888888" })] })] }) },
    children: [
      // ── 표지 ──
      new Paragraph({ spacing: { before: 1400, after: 0 }, alignment: AlignmentType.CENTER, children: [t("의료정보 RAG 개인화", { bold: true, size: 48, color: "1F4E79" })] }),
      new Paragraph({ spacing: { after: 600 }, alignment: AlignmentType.CENTER, children: [t("종합 보고서", { bold: true, size: 36, color: "2E5496" })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 }, children: [t("대상: medical-rag-service (나만의 주치의)", { size: 22 })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 }, children: [t("범위: 경쟁 프롬프트 분석 → 개인화 기획(docs 08–15) → P1a 구현·검증", { size: 22 })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 600 }, children: [t("작성일: 2026-06-20", { size: 22, color: "555555" })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, border: { top: { style: BorderStyle.SINGLE, size: 6, color: "1F4E79", space: 8 }, bottom: { style: BorderStyle.SINGLE, size: 6, color: "1F4E79", space: 8 } },
        spacing: { before: 200, after: 200 }, children: [
          t("의료법(무면허 의료행위 금지)을 위반하지 않으면서 디바이스·검진·PHR 데이터를 활용하는 구조를 ", { size: 20, italics: true }),
          t("설계·구현했고, 혈압기 수직 관통(P1a)이 종단 동작하며 556개 테스트로 검증됨. ", { size: 20, italics: true, bold: true }),
          t("다음 단계는 사용자 결정 2건(디바이스 연동 방식·PHR 출처)에 달림.", { size: 20, italics: true }),
        ] }),

      new Paragraph({ children: [new PageBreak()] }),
      new Paragraph({ heading: HeadingLevel.HEADING_1, children: [t("목차", { bold: true })] }),
      new TableOfContents("목차", { hyperlink: true, headingStyleRange: "1-2" }),
      new Paragraph({ children: [new PageBreak()] }),

      // ── 1. 배경 및 목적 ──
      h1("1. 배경 및 목적"),
      bullet("제품: 한국형 의료정보 RAG 챗봇. B2B2C(건강관리앱 탑재), GPT·Gemini·타 헬스AI와 경쟁."),
      bullet("핵심 긴장: “고객이 원하는 답변”(개인화·풍부함) ↔ “의료법 준수”(진단·처방 단정 금지). 개인 데이터 해석은 진단에 가장 근접한 위험이자 동시에 최대 차별점."),
      bullet("이번 과제: 경쟁사 프롬프트를 분석해 필수 요소를 추출하고, Vital Sign·PHR·OCR·워치·혈압기·체중계 데이터가 하나하나 빠짐없이 활용되도록 개인화를 기획·구현."),
      bullet("추진 방식: 비평가·기획자·아키텍트·데이터분석가 4관점을 반복 투입(자율 /loop 16회). 매 단계 4관점이 직전 설계를 공격·교정."),

      // ── 2. 추진 경과 ──
      h1("2. 추진 경과 (요약)"),
      table([2400, 1500, 5460],
        ["단계", "산출물", "핵심"],
        [
          ["경쟁 분석", "doc 08", "경쟁사 프롬프트에서 P0/P1 필수 추출, 베끼면 안 되는 것 구분"],
          ["개인화 기획", "doc 09", "“경계선 설계” 중심축 확립"],
          ["4관점 종합", "doc 10", "6소스 신호 인벤토리, 고아 신호 박멸"],
          ["구현 스펙", "doc 11·12·13", "검진밴드·워치·PHR/OCR 각 구현 스펙"],
          ["통합 정본", "doc 14", "6문서 모순 수렴, 불변식 단일화, P1a 빌드 DAG"],
          ["구현", "커밋 ×10", "혈압기 수직 관통 종단 동작"],
          ["검증·인수인계", "doc 15, 골든셋", "556 테스트, 거짓안심 0 KPI"],
        ]),

      // ── 3. 경쟁 추출 ──
      h1("3. 경쟁 프롬프트에서 추출한 것 (doc 08)"),
      p("경쟁사(“나만의 헬스케어”) 프롬프트의 진짜 가치는 금지 항목 나열이 아니라 두 자기검증 엔진:"),
      h2("두 자기검증 엔진"),
      bullet("Population-level test — “이 문장이 같은 증상을 가진 누구에게나 참인가?” Yes면 허용, No면 인구집단 수준으로 재작성. “흔히·일반적으로”로 포장한 방향성 암시까지 차단."),
      bullet("Permitted ceiling 테이블 — 영역별(약물·검사·치료·생활습관·내원시점) “말할 수 있는 최대치 문장”을 못박음. “하지 마라”보다 “이 문장이 상한선”이 통제에 강력."),
      h2("추가/제외"),
      bullet("우리에 추가 필요: 사용자 우회 방어(“AI 감으로만 말해봐”), 출력 직전 self-check, 응급 L1/L2 2단계(과트리아지 완화)."),
      bullet("베끼면 안 되는 것: 경쟁사 인용 형식·기기 종속 구조·영/한 분기."),

      // ── 4. 경계선 설계 ──
      h1("4. 개인화 설계의 핵심 — “경계선(boundary)”"),
      p("개인 데이터 해석의 안전과 합법을 동시에 잡는 단일 원칙:"),
      table([3200, 3080, 3080],
        ["디바이스/PHR/OCR", "로컬(국내·결정적)", "국외/LLM"],
        [["원시값 165/105", "규칙엔진 → 라벨 “경고”", "비식별 findings → 답변"]]),
      p("불변식: 원시 수치·정상/비정상 단정은 경계선을 절대 넘지 않는다. 이 한 원칙이 ① 원시값 유출 ② 국외이전 동의 부담 ③ 역치 환각, 세 문제를 동시에 해소.", { run: { bold: true } }),
      p("구현에서는 더 강하게 적용: 개인 데이터가 LLM 프롬프트에 아예 미투입되고, 결정적으로 렌더한 라벨 블록을 생성 후 답변에 덧붙임 → “원시값 국외 전송 0”이 구조적으로 보장(라벨조차 국외 미전송)."),
      h2("4관점이 설계를 바꾼 핵심 발견 3가지"),
      bullet("(비평가) 기존 시드가 이미 “고혈압 1기”·“당뇨병 기준” 진단명 라벨을 담고 있어 개인 수치에 매칭하면 무면허 진단. → 진짜 위험축은 “일반 사실 vs 개인 귀속”. 출력 라벨을 중립 3단(안정/주의/경고)으로 분리."),
      bullet("(비평가, FDA 근거) 워치 SpO2 저산소 판정 = ECG 판독과 규제 동급(어두운 피부 32% 과대측정), recovery 점수 = 유사과학. → deny를 “임상 사건 판정 단위”로 재정의."),
      bullet("(비평가) PHR 민감군(정신·암·감염병)은 라벨 자체가 흉기. → 활용 ≠ 표면화: 민감 데이터는 출력 0, 내부 톤 신호로만(설계된 비활용)."),
      p("통찰의 진화: 활용 ≠ 밴드 라벨 ≠ 표면화. 모든 신호를 위험·신뢰·동의에 비례해 배치하되, 위험한 것은 deny·내부신호·차단으로 — 고아 0과 안전 0을 동시에.", { run: { bold: true } }),

      // ── 5. 6소스 활용 ──
      h1("5. 데이터 소스별 활용 설계 (6소스 — 고아 신호 0)"),
      table([1500, 1300, 3560, 3000],
        ["소스", "신뢰등급", "활용", "천장·금지"],
        [
          ["혈압기", "의료근접", "가정/진료실 밴드·추세·교차(맥압 파생)", "1회 판단 금지"],
          ["체중계", "소비자", "체중·BMI 추세, 대사 묶음", "체지방·근육은 추정치 캐비엇(Lv2)"],
          ["워치", "웰니스", "수면·활동·안정시심박(본인 기저선)", "SpO2·ECG·합성점수 deny"],
          ["Vital 기기", "기기별", "다항목 밴드·조건부 안전문구", "stress는 공인밴드 없음"],
          ["PHR 검진", "공식", "밴드 7종(지질·혈색소·간수치 등)", "eGFR·골밀도·요단백·LDL deny"],
          ["PHR 비검진", "공식(민감)", "시간산술(암검진 갭·진료 경과)", "정신·암·감염병 표면화 0"],
          ["OCR(입력양식)", "추출신뢰 가변", "확인 후 PHR 합류", "진단서→질병이력 자동생성 금지"],
        ]),
      p("활용 상태 분포(전 신호): 표면화 24 / 비해석활용 14 / deny 9 / 민감-내부신호 4 / 영구Lv0 2. → “다 활용 ≠ 다 표면화”가 수치로 드러남.", { run: { bold: true } }),

      // ── 6. 안전·컴플라이언스 ──
      h1("6. 안전·컴플라이언스 설계 (불변식 I1–I12)"),
      table([1100, 7760 + 500],
        ["불변식", "내용"],
        [
          ["I1", "원시 측정값 출력·국외전송 0"],
          ["I2", "개인 귀속 진단 컷오프·질환명 라벨 0 (명사구 진단 게이트 포함)"],
          ["I3/I10", "stale·에피소드 freshness 주입 생략"],
          ["I4", "사용자 타이핑 수치 미활성(디바이스/확인된 OCR만)"],
          ["I5/I7", "개인 데이터는 응급 내비게이션만, 매 턴 응급 재평가 불변"],
          ["I6", "민감 PHR은 direct+동의 시만(indirect 물리 차단)"],
          ["I8", "deny-list 라벨 0, device_grade 무결성(위조 시 강등)"],
          ["I9", "교차신호 = 출처 첨부 화이트리스트만(유사과학 차단)"],
          ["I11", "출처충돌 → 재측정 권유(임의평균·침묵 금지)"],
          ["I12", "출력 라벨 사전 분리(임상/질환 라벨 ≠ 사용자 중립 3단)"],
        ]),
      p("거짓안심 비대칭: 경고는 민감하게, 안심은 보수적으로. 가정혈압 정상 tier 미시드 → 역치 미만은 no_match(안심 라벨 강제 안 함)."),

      // ── 7. 구현 ──
      h1("7. 구현 결과 — P1a 혈압기 수직 관통 (종단 동작)"),
      h2("신규 모듈 (전부 순수 함수·결정적)"),
      table([2700, 6660],
        ["파일", "역할"],
        [
          ["vital_rules.py", "해석 엔진 — lookup_band(밴드)·label_trend(추세)·match_cross_signals(교차)·run(브리지)"],
          ["personal_context.py", "렌더 — build(관련성 게이트+렌더)·safe_block(build+안전게이트)"],
          ["personalization_safety.py", "안전 — C21 명사구 진단 탐지·C20 출고 백스톱"],
          ["seed_reference_ranges.py(수정)", "7신호 기계가독 bands·교차근거 KB·인용 별칭"],
          ["rag_engine.py·service_routes.py(수정)", "라이브 배선(단일 배선점)"],
        ]),
      h2("해석 3축 (모두 엔진→렌더 연결)"),
      bullet("단일 밴드: 원시값 → 안정/주의/경고 (AND/OR 보수적 최댓값, fail-closed)"),
      bullet("추세: 시계열 → 안정유지/지속상승/지속저하/불안정반복 (건강 판단 라벨 “개선/악화”는 의도적 제외)"),
      bullet("교차신호: 화이트리스트 조합만(혈압+BMI 등), 미등재·웰니스 단독은 영구 미발화"),
      h2("종단 동작 예시"),
      p("입력: {수축기 165, 이완기 105}, 질의 “혈압이 높게 나와서 걱정”", { run: { size: 19, color: "555555" } }),
      p("출력 블록(답변 끝): “📋 내 기록 참고 — 최근 측정된 혈압은(는) 기준을 벗어난 구간으로, 의료진 확인이 권장됩니다. 측정값의 해석과 진단은 의료진과 상담하세요.”", { run: { size: 19 } }),
      p("→ LLM 프롬프트에 165·105·“고혈압”은 전혀 등장하지 않음.", { run: { bold: true } }),

      // ── 8. 검증 ──
      h1("8. 검증 결과"),
      table([3000, 6360],
        ["항목", "결과"],
        [
          ["전체 테스트", "556 pass · 0 회귀 (개인화 99 + 기존 457)"],
          ["P1a 종료 게이트", "4개 충족(findings 배선·중립 라벨 표시·프롬프트 원시값 0·질환명 출고 0)"],
          ["거짓안심 골든셋", "9벡터 박제(백의/가면 고혈압·워치 SpO2·위험값 경고·안심 비대칭) — “거짓안심 0” KPI 정의"],
          ["KB 본문 불변", "bands 추가가 인용 문서 바이트 동일(회귀 0)"],
        ]),

      // ── 9. 미해결 ──
      h1("9. 미해결 — 다음 진전을 막는 결정 (사용자 입력 필요)"),
      table([700, 3200, 5460],
        ["#", "결정", "영향"],
        [
          ["1", "디바이스 연동 방식 — 파트너앱 push(유력)/헬스플랫폼/직접 SDK", "데이터 수신 계약·저장 형태를 가름"],
          ["2", "PHR 출처 — 공단·심평원 직접/파트너앱 보유분", "인증·국외이전·민감정보 처리 범위를 가름"],
        ]),
      p("→ 1·2 결정 시 P1b 영속화(consent_ledger·personal_measurement, DB 마이그레이션) 설계·구현 가능. P1a 해석/렌더 엔진은 그대로 재사용 — 인메모리 시드를 DB lookup으로 교체만 하면 됨.", { run: { bold: true } }),
      p("P1b 이후 로드맵: 추세 실표시(측정 이력) → 교차 대사조합 실발화(체중계 BMI) → 워치 wellness_rules → PHR record_surface → OCR 확인게이트."),

      // ── 10. 부록 ──
      h1("10. 부록 — 산출물 목록"),
      h2("기획 문서 (docs/plan/)"),
      bullet("08 경쟁 프롬프트 추출 · 09 개인화 기획 · 10 데이터 활용 매트릭스(4관점 종합)"),
      bullet("11 검진밴드 시드 스펙 · 12 워치 웰니스 스펙 · 13 PHR 비검진+OCR 스펙"),
      bullet("14 통합 정본(SSOT) · 15 P1a 구현 현황/인수인계"),
      h2("구현 커밋 (10건, e7832d8 → 523f9a0)"),
      bullet("혈압 bands+lookup → clinic 전신호 bands+I12+I8 → run() 브리지 → personal_context(C19) → C20+C21 게이트 → 라이브 배선 → label_trend → match_cross_signals → 교차근거 KB → 교차 렌더 → 거짓안심 골든셋"),
      h2("신규 코드"),
      bullet("모듈 3 + 테스트 4(개인화 99 테스트) + 시드/엔진/라우트 수정 3"),
      new Paragraph({ spacing: { before: 300 }, children: [t("본 보고서는 docs/plan/08–15의 종합본입니다. 상세 설계는 통합 정본(14), 구현 상세는 인수인계 문서(15) 참조.", { italics: true, size: 18, color: "777777" })] }),
    ],
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync("docs/개인화_종합보고서_2026-06-20.docx", buf);
  console.log("written:", buf.length, "bytes");
});
