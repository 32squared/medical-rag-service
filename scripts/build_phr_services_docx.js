// PHR 기반 서비스 기획 (4갈래 12기능) → Word(.docx). 한글: 맑은 고딕.
// 실행: NODE_PATH="$(npm root -g)" node scripts/build_phr_services_docx.js
const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  AlignmentType, LevelFormat, HeadingLevel, BorderStyle, WidthType, ShadingType,
  TableOfContents, PageBreak, Footer, PageNumber,
} = require("docx");

const FONT = "Malgun Gothic";
const CONTENT_W = 9360;
const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };
const HEAD_FILL = "1F4E79", ALT_FILL = "EDF2F7", STAR_FILL = "FCE8D5";
const Q_FILL = "DCE6F2", A_FILL = "F1F1F1";

function t(text, o = {}) { return new TextRun({ text, font: FONT, ...o }); }
function p(text, o = {}) { return new Paragraph({ children: [t(text, o.run || {})], spacing: { after: 120, ...(o.spacing || {}) }, ...(o.p || {}) }); }
function h1(text) { return new Paragraph({ heading: HeadingLevel.HEADING_1, children: [t(text, { bold: true })] }); }
function bullet(text, o = {}) { return new Paragraph({ numbering: { reference: "b", level: 0 }, spacing: { after: 60 }, children: [t(text, o)] }); }
function qLine(text) { return new Paragraph({ shading: { type: ShadingType.CLEAR, fill: Q_FILL }, spacing: { before: 80, after: 0 }, border: { left: { style: BorderStyle.SINGLE, size: 22, color: "2E5496", space: 8 } }, children: [t("사용자   ", { bold: true, color: "1F4E79", size: 19 }), t(text, { size: 20 })] }); }
function aLine(text) { return new Paragraph({ shading: { type: ShadingType.CLEAR, fill: A_FILL }, spacing: { before: 0, after: 80 }, border: { left: { style: BorderStyle.SINGLE, size: 22, color: "548235", space: 8 } }, children: [t("주치의   ", { bold: true, color: "2E5d27", size: 19 }), t(text, { size: 20 })] }); }

function table(colW, header, rows) {
  const rowFill = (r) => (r.__star ? STAR_FILL : (rows.indexOf(r) % 2 ? ALT_FILL : "FFFFFF"));
  const mk = (cells, head) => new TableRow({ tableHeader: !!head, children: cells.map((c, i) => new TableCell({
    borders, width: { size: colW[i], type: WidthType.DXA }, shading: { fill: head ? HEAD_FILL : rowFill(cells), type: ShadingType.CLEAR },
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: String(c).split("\n").map((line, li) => new Paragraph({ spacing: { after: 0 }, children: [
      li === 0 ? t(line, head ? { bold: true, color: "FFFFFF", size: 17 } : { size: 17, bold: i === 0 }) : t(line, { size: 15, italics: true, color: "777777" }),
    ] })),
  })) });
  return new Table({ width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: colW, rows: [mk(header, true), ...rows.map((r) => mk(r))] });
}

// 갈래별 기능 표: 기능 / 무엇을 해주나(+안전) / 필요 PHR 데이터 / 우선순위
function funcTable(rows) { return table([1450, 4060, 2050, 1800], ["기능", "무엇을 해주나  (둘째 줄: 안전 처리)", "필요 PHR 데이터", "우선순위"], rows); }
function star(arr) { arr.__star = true; return arr; }

const doc = new Document({
  styles: { default: { document: { run: { font: FONT, size: 21 } } },
    paragraphStyles: [{ id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 28, bold: true, font: FONT, color: "1F4E79" }, paragraph: { spacing: { before: 300, after: 140 }, outlineLevel: 0 } }] },
  numbering: { config: [{ reference: "b", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 460, hanging: 260 } } } }] }] },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [t("마이헬스케어 · PHR 서비스 기획 · ", { size: 16, color: "888888" }), new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 16, color: "888888" })] })] }) },
    children: [
      new Paragraph({ spacing: { before: 1400, after: 0 }, alignment: AlignmentType.CENTER, children: [t("PHR로 가능한 서비스 기획", { bold: true, size: 44, color: "1F4E79" })] }),
      new Paragraph({ spacing: { after: 500 }, alignment: AlignmentType.CENTER, children: [t("건강검진·진료·처방 데이터로 무엇을 해줄 수 있나 — 4갈래 12기능", { size: 24, color: "2E5496" })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 700 }, children: [t("마이헬스케어 · 2026-06-21", { size: 20, color: "555555" })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, border: { top: { style: BorderStyle.SINGLE, size: 6, color: "1F4E79", space: 8 }, bottom: { style: BorderStyle.SINGLE, size: 6, color: "1F4E79", space: 8 } }, spacing: { before: 200, after: 200 }, children: [t("PHR(건강검진·진료·처방 기록)은 ‘챙겨주기 · 결과 풀이 · 맞춤 상담 · 건강 요약’ 4갈래로 가치를 낸다. 모두 ", { size: 21, italics: true }), t("진단 없이, 민감정보는 표시하지 않고", { size: 21, italics: true, bold: true }), t(" 안전하게 제공한다.", { size: 21, italics: true })] }),
      new Paragraph({ children: [new PageBreak()] }),

      h1("한눈에 — 4갈래 12기능"),
      table([1900, 5560, 1900], ["갈래", "기능", "성격"], [
        star(["1. 챙겨주기", "1.1 검진 알리미 · 1.2 처방약 리필 · 1.3 진료 추적", "즉시·저리스크"]),
        ["2. 결과 풀이", "2.1 검진 결과 풀이 · 2.2 연도별 추세 · 2.3 용어 설명", "★ 킬러"],
        ["3. 맞춤 상담", "3.1 이력 맞춤 증상상담 · 3.2 진료과 추적 · 3.3 복약 정보", "핵심 개인화"],
        ["4. 건강 요약", "4.1 건강 요약 카드 · 4.2 병원 갈 때 준비 · 4.3 위험요인 묶음", "제품 허브"],
      ]),

      // 갈래 1
      h1("갈래 1. 챙겨주기 — 놓치지 않게 (시간산술, 가장 안전)"),
      funcTable([
        star(["1.1 검진 알리미", "국가검진·6대 암검진의 대상·권장주기 대비 경과를 계산해 받을 시기 알림\n안전: 결과 판정 X(시기만), ‘기록상’ 단서·조건부 환기, 국가검진 출처", "암/일반검진 수검 이력, 생년·성별", "★ 즉시\n낮음"]),
        ["1.2 처방약 리필 알림", "처방일수 기반 약 소진 예상 시점 알림\n안전: 현재 복용 단정 X(조건부), 약물명 X(계열만)", "처방이력(일수·계열)", "중~높\n낮음"],
        ["1.3 진료 추적 알림", "최근 진료 후 경과로 추적 진료 시기 환기\n안전: 진료 사유 추론 X, 빈도 과해석 X", "진료이력(과·날짜)", "중\n낮음"],
      ]),

      // 갈래 2
      h1("갈래 2. 검진 결과 풀이 — 검진지 받아도 모르는 사람들 (킬러)"),
      funcTable([
        star(["2.1 검진 결과 풀이", "검진 수치를 중립 구간 라벨로 쉽게 + 함께 볼 항목 안내\n안전: 진단 X(질환명 X), deny항목은 ‘수치는 의료진과’, 측정시점 결합", "검진 수치", "★★ 최고\n중"]),
        ["2.2 연도별 추세", "같은 항목 연도별 변화를 중립 데이터 패턴으로\n안전: 개선/악화(판단) X — 지속상승 등 패턴만, N년 이상만", "다년 검진 수치", "★ 높음\n중"],
        ["2.3 검진 용어 설명", "검진 항목·용어 일반 정보\n안전: 일반 정보, 개인 귀속 X", "(불필요·KB)", "중\n낮음"],
      ]),
      p("예시 — 검진 결과 풀이:", { run: { bold: true, size: 19 }, spacing: { before: 120, after: 40 } }),
      qLine("이번 검진 결과 어때요?"),
      aLine("총콜레스테롤과 중성지방이 관리가 권장되는 구간으로 확인돼요. 작년보다 조금 오른 흐름이라 식습관·운동과 함께 살펴보시면 좋고, 정확한 해석은 의료진과 상담해보세요."),

      // 갈래 3
      h1("갈래 3. 내 이력 맞춤 상담 — 증상 답변에 내 기록 반영"),
      funcTable([
        star(["3.1 이력 맞춤 증상상담", "증상 질의에 관련 과거 이력·검진을 함께 살펴보자 연결(indirect)\n안전: 민감군(정신·암·감염) 표면화 0, 인과 단정 X, 과거시제", "질병이력(비민감)·검진·처방계열", "★ 높음\n중"]),
        ["3.2 진료과 추적 안내", "과거 진료 이력 있는 과로 추적 권유\n안전: 진료과는 조건부 안내로만", "진료이력(과)", "중\n낮음"],
        ["3.3 복약 일반 정보", "과거 처방 계열 관련 일반 주의·상호작용 정보\n안전: 약물명 X·현재복용 단정 X, 정신과·항감염 계열 표면화 0", "처방계열", "중\n중"],
      ]),
      p("예시 — 이력 맞춤 증상상담:", { run: { bold: true, size: 19 }, spacing: { before: 120, after: 40 } }),
      qLine("머리가 아픈데 혹시 혈압 때문일까요?"),
      aLine("두통은 여러 원인과 관련될 수 있어요. 최근 혈압이 관리 권장 구간으로 기록돼 있어 함께 살펴보시면 좋고, 반복되면 의료진 상담을 권해드려요."),

      // 갈래 4
      h1("갈래 4. 내 건강 요약 / 병원 준비 — PHR 통합의 본질 가치"),
      funcTable([
        star(["4.1 내 건강 요약 카드", "흩어진 검진·진료·복약 이력을 사용자 친화적으로 한눈에 요약\n안전: 라벨만(원시값·질환명 X), 민감 이력 제외", "PHR 전반", "높음\n중~높"]),
        ["4.2 병원 갈 때 준비", "진료 전 말하면 좋은 이력·약·증상 정리\n안전: 라벨·계열만, 민감은 사용자 선택", "PHR + 대화", "높음\n중"],
        ["4.3 위험요인 묶음", "검진수치+가족력+생활습관을 ‘함께 관리하면 좋은 항목’으로\n안전: 운명론 X(통제 가능 프레임), 암 가족력 민감", "검진·가족력·생활습관", "중\n중"],
      ]),
      p("예시 — 병원 갈 때 준비:", { run: { bold: true, size: 19 }, spacing: { before: 120, after: 40 } }),
      qLine("내일 병원 가요."),
      aLine("진료 때 이런 것들 말씀하시면 도움이 돼요: 과거 ○○ 이력, 복용 중인 약 계열, 최근 증상(언제부터·정도)."),

      new Paragraph({ children: [new PageBreak()] }),

      // 우선순위
      h1("우선순위 매트릭스 (가치 × 난이도·리스크)"),
      table([2100, 3630, 3630], ["", "저난이도·저리스크", "중난이도"], [
        ["高가치", "1.1 검진 알리미 · 2.3 용어설명", "2.1 결과풀이 · 2.2 추세 · 3.1 맞춤상담 · 4.1 요약카드 · 4.2 병원준비"],
        ["中가치", "1.2 리필 · 1.3 진료추적", "3.2 진료과추적 · 3.3 복약정보 · 4.3 위험요인"],
      ]),
      p("Quick win(즉시): 1.1 · 1.2 · 2.3   /   Killer(차별·고가치): 2.1 · 2.2 · 4.1 · 4.2 · 3.1", { run: { bold: true } }),

      // 로드맵
      h1("단계별 로드맵"),
      table([1600, 4400, 3360], ["단계", "기능", "이유"], [
        star(["A. 챙김(즉시)", "1.1 검진알리미 · 1.2 리필 · 1.3 진료추적", "시간산술, 리스크 최저, 즉시 가치"]),
        ["B. 결과 이해(킬러)", "2.1 결과풀이 · 2.2 추세 · 2.3 용어", "PHR만의 차별점, 밴드/추세 엔진 일부 완성"],
        ["C. 개인화·허브", "3.1 맞춤상담 · 4.1 요약카드 · 4.2 병원준비", "관련성 게이트·민감 분류 성숙 후"],
        ["D. 확장", "3.2 · 3.3 · 4.3", "진료과·복약·예방"],
      ]),

      h1("공통 선결 / 결정사항"),
      bullet("데이터 출처: 공단·심평원 직접 연동(인증·국외이전 난이도↑) vs 파트너앱 보유분 — 범위·일정을 가름."),
      bullet("검진 수치 밴드 시드 확장: 결과풀이(2.1)의 선결 — 7종 시드 + eGFR 등 deny 분류는 이미 설계 완료."),
      bullet("민감정보(정신·암·감염병): 전 기능 공통 — 표면화 0, 내부 톤만."),
      bullet("추세(2.2)·요약(4.1): 다년·통합 데이터 = 영속화(저장) 필요."),
    ],
  }],
});

Packer.toBuffer(doc).then((buf) => { fs.writeFileSync("docs/PHR_서비스기획_2026-06-21.docx", buf); console.log("written:", buf.length, "bytes"); });
