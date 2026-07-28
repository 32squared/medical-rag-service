// 임원 보고용 1장 요약 (가로 1페이지) → Word.
const fs = require("fs");
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, AlignmentType, BorderStyle,
  WidthType, ShadingType, PageOrientation, ImageRun, VerticalAlign } = require("docx");
const FONT = "Malgun Gothic";
const ONTO = fs.readFileSync("docs/ontology/phr-ontology-unified.png");
const nb = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" }; const noB = { top: nb, bottom: nb, left: nb, right: nb };
const bd = { style: BorderStyle.SINGLE, size: 1, color: "D4DDE7" }; const bds = { top: bd, bottom: bd, left: bd, right: bd };
const t = (x, o = {}) => new TextRun({ text: x, font: FONT, ...o });
const P = (runs, o = {}) => new Paragraph({ spacing: { after: o.after ?? 30, before: o.before ?? 0 }, alignment: o.al, children: Array.isArray(runs) ? runs : [runs] });
const cell = (children, o = {}) => new TableCell({ borders: o.b ? bds : noB, width: { size: o.w, type: WidthType.DXA },
  shading: o.fill ? { fill: o.fill, type: ShadingType.CLEAR } : undefined, verticalAlign: o.va,
  margins: { top: o.m ?? 60, bottom: o.m ?? 60, left: 110, right: 110 }, children });
const CW = 14112; // landscape letter, 0.6" margins

// 6층 서비스 칩 표
function svcTable() {
  const rows = [
    ["1 측정", "혈압·체중·워치 추세·공기질 — 측정값 즉시 해석", "단일"],
    ["2 기록이해", "검진 결과 풀이★·추세·알리미·요약카드·OCR", "단일"],
    ["3 증상결합", "증상+측정/검진/복약·병원 갈 때 준비", "결합★"],
    ["4 교차신호", "컨디션 저하 조기신호·대사 관리 묶음", "결합"],
    ["5 환경×건강", "호흡기·알레르기 케어·수면/집중 환경", "결합"],
    ["6 예방", "위험요인 묶음·암검진 갭(위험군)", "결합"],
  ];
  return new Table({ width: { size: CW, type: WidthType.DXA }, columnWidths: [1900, 10212, 2000],
    rows: [new TableRow({ tableHeader: true, children: ["층", "대표 서비스 (총 22개)", "유형"].map((h, i) =>
        cell([P(t(h, { bold: true, color: "FFFFFF", size: 17 }))], { w: [1900, 10212, 2000][i], b: true, fill: "1F4E79", m: 40 })) }),
      ...rows.map((r, ri) => new TableRow({ children: r.map((c, i) =>
        cell([P(t(c, { size: 17, bold: i === 0 }))], { w: [1900, 10212, 2000][i], b: true, m: 36, fill: r[2].startsWith("결합") ? "EAF1E6" : (ri % 2 ? "F4F7FA" : "FFFFFF") })) })) ] });
}
function roadmap() {
  const q = [["Q1", "혈압·검진풀이·알리미·환기 (저리스크·고가치)"], ["Q2", "추세·요약 + 결합상담 시작"],
    ["Q3", "워치·대사 묶음·호흡기 환경 (개인화 심화)"], ["Q4", "교차신호·환경·예방·OCR"]];
  const fills = { Q1: "DCEAF5", Q2: "E3F0E0", Q3: "FBEFD9", Q4: "F2E5F0" };
  return new Table({ width: { size: CW, type: WidthType.DXA }, columnWidths: [3528, 3528, 3528, 3528],
    rows: [new TableRow({ children: q.map(([k, v]) => cell([
      P(t(k, { bold: true, size: 20, color: "1F4E79" })), P(t(v, { size: 15, color: "41505f" })) ], { w: 3528, b: true, fill: fills[k], m: 60 })) })] });
}

const doc = new Document({
  styles: { default: { document: { run: { font: FONT, size: 18 } } } },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840, orientation: PageOrientation.LANDSCAPE }, margin: { top: 864, right: 864, bottom: 720, left: 864 } } },
    children: [
      P([t("마이헬스케어", { bold: true, size: 32, color: "1F4E79" }), t("   임원 요약 (1-pager)", { size: 22, color: "2E5496" }), t("    ·  2026-06-21", { size: 16, color: "888888" })], { after: 40 }),
      // 한 줄 결론
      new Table({ width: { size: CW, type: WidthType.DXA }, columnWidths: [CW], rows: [new TableRow({ children: [cell([
        P([t("디바이스·검진 데이터를 ", { size: 19 }), t("의료법 위반 0", { size: 19, bold: true }), t("으로 활용 — 범용 AI가 못 하는 ‘내 데이터 기반 건강 안내’. ", { size: 19 }),
           t("P1a(혈압) 종단 구현·556 테스트 검증 완료", { size: 19, bold: true }), t(". 다음은 연동 결정 2건.", { size: 19 })])
      ], { w: CW, b: true, fill: "EAF1F8", m: 90 })] })] }),
      P(t(""), { after: 40 }),
      // 본문 2열: 좌(가치) / 우(그림)
      new Table({ width: { size: CW, type: WidthType.DXA }, columnWidths: [8400, 5712], rows: [new TableRow({ children: [
        cell([
          P([t("무엇  ", { bold: true, color: "1F4E79", size: 18 }), t("건강관리 앱에 탑재되는 챗봇. 건강 질문에 공인 출처로 답하고, 연결된 측정·검진 데이터를 진단 없이 답변에 반영.", { size: 17 })]),
          P([t("차별점  ", { bold: true, color: "1F4E79", size: 18 }), t("“내 혈압 150” → GPT는 거절/위험단정, 우리는 “관리 권장 구간 + 상담 권유”. 원시값·질환명은 외부 AI 미전송.", { size: 17 })]),
          P([t("안전=가치  ", { bold: true, color: "1F4E79", size: 18 }), t("진단 0·민감정보 비표시·국외 미전송 → 파트너의 규제 리스크 제거 = 도입 명분.", { size: 17 })]),
          P([t("기반  ", { bold: true, color: "1F4E79", size: 18 }), t("통합 데이터 온톨로지(PHR·디바이스·환경·OCR·대화) — 소스는 여럿이어도 해석·안전 코어는 하나(우측 그림).", { size: 17 })]),
        ], { w: 8400, va: VerticalAlign.CENTER }),
        cell([ new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 0 }, children: [
          new ImageRun({ type: "png", data: ONTO, transformation: { width: 360, height: 228 }, altText: { title: "통합 온톨로지", description: "여러 소스가 하나의 안전 코어로", name: "o" } })] }) ], { w: 5712, va: VerticalAlign.CENTER }),
      ] })] }),
      P([t("서비스 — 22개 / 6층", { bold: true, size: 19, color: "1F4E79" })], { before: 80, after: 30 }),
      svcTable(),
      P([t("출시 로드맵 (가치×준비도×결정 의존)", { bold: true, size: 19, color: "1F4E79" })], { before: 80, after: 30 }),
      roadmap(),
      P([t("다음 결정 2건  ", { bold: true, color: "B06A00", size: 18 }),
         t("① 디바이스 연동 방식(파트너앱 push 유력)  ② PHR 출처(공단 vs 파트너) — 이 둘이 정해지면 결합형 가치가 본격 가동.", { size: 17 })], { before: 80 }),
    ],
  }],
});
Packer.toBuffer(doc).then((b) => { fs.writeFileSync("docs/임원요약_1pager_2026-06-21.docx", b); console.log("written:", b.length); });
