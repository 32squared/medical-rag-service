// 통합 온톨로지(PHR+장치·환경+OCR·대화) → Word(.docx).
// 실행: NODE_PATH="$(npm root -g)" node scripts/build_unified_ontology_docx.js
const fs = require("fs");
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  AlignmentType, HeadingLevel, BorderStyle, WidthType, ShadingType, PageBreak, Footer, PageNumber, ImageRun } = require("docx");
const ONTO_PNG = fs.readFileSync("docs/ontology/phr-ontology-unified.png");
const ontoImg = () => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 120 },
  children: [new ImageRun({ type: "png", data: ONTO_PNG, transformation: { width: 600, height: 380 },
    altText: { title: "통합 데이터 온톨로지", description: "여러 소스가 하나의 안전 코어로", name: "ontology" } })] });
const FONT = "Malgun Gothic", MONO = "Consolas", CW = 9360;
const bd = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" }; const bds = { top: bd, bottom: bd, left: bd, right: bd };
const HEAD = "1F4E79", ALT = "EDF2F7";
const t = (x, o = {}) => new TextRun({ text: x, font: FONT, ...o });
const h1 = (x) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [t(x, { bold: true })] });
const p = (x, o = {}) => new Paragraph({ spacing: { after: 100, ...(o.sp || {}) }, children: [t(x, o.r || {})] });
const code = (x) => new Paragraph({ spacing: { after: 0 }, children: [new TextRun({ text: x, font: MONO, size: 16 })] });
function table(colW, header, rows) {
  const mk = (cells, head) => new TableRow({ tableHeader: !!head, children: cells.map((c, i) => new TableCell({
    borders: bds, width: { size: colW[i], type: WidthType.DXA },
    shading: { fill: head ? HEAD : (rows.indexOf(cells) % 2 ? ALT : "FFFFFF"), type: ShadingType.CLEAR },
    margins: { top: 40, bottom: 40, left: 80, right: 80 },
    children: String(c).split("\n").map((l) => new Paragraph({ spacing: { after: 0 }, children: [t(l, head ? { bold: true, color: "FFFFFF", size: 15 } : { size: 15 })] })) })) });
  return new Table({ width: { size: CW, type: WidthType.DXA }, columnWidths: colW, rows: [mk(header, true), ...rows.map((r) => mk(r))] });
}
const doc = new Document({
  styles: { default: { document: { run: { font: FONT, size: 20 } } },
    paragraphStyles: [{ id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 27, bold: true, font: FONT, color: "1F4E79" }, paragraph: { spacing: { before: 260, after: 130 }, outlineLevel: 0 } }] },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [t("통합 온톨로지 · ", { size: 16, color: "888888" }), new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 16, color: "888888" })] })] }) },
    children: [
      new Paragraph({ spacing: { before: 1100, after: 0 }, alignment: AlignmentType.CENTER, children: [t("통합 데이터 온톨로지", { bold: true, size: 42, color: "1F4E79" })] }),
      new Paragraph({ spacing: { after: 400 }, alignment: AlignmentType.CENTER, children: [t("PHR · 장치 · 환경 · OCR · LLM 대화", { size: 24, color: "2E5496" })] }),
      new Paragraph({ spacing: { after: 500 }, alignment: AlignmentType.CENTER, children: [t("나만의 주치의 · 2026-06-21", { size: 20, color: "555555" })] }),
      p("정본: docs/ontology/*.ttl (phr·device·context) — 통합 741 트리플·120 노드. 핵심: 모든 소스가 signalKey로 같은 참조범위를 조인 → 해석·안전 코어는 하나.", { r: { italics: true, color: "555555" } }),
      ontoImg(),
      p("[그림] 여러 입력 소스(PHR·디바이스·환경·OCR·대화) → 정규화 → 하나의 해석·안전 코어.", { r: { size: 16, color: "777777" }, p: { alignment: AlignmentType.CENTER } }),
      new Paragraph({ children: [new PageBreak()] }),

      h1("1. 클래스 계층 (입력 소스 통합)"),
      code("phr:Person / phr:PHR"),
      code("phr:HealthRecord ⊃ 검진·질병·가족·생활·암검진·리포트·처방·진료   [PHR]"),
      code("phr:Observation ⊃ 계측·활력·혈액·간·요·영상·골·종합            [검진 측정값]"),
      code("phr:Device ⊃ 혈압기·체중계·통합측정기(A1)·스마트워치·공기질센서"),
      code("phr:DeviceMeasurement ⊑ Observation  (해석 코어 재사용)"),
      code("   ⊃ WatchSignal(웰니스): 안정시심박·HRV·수면·활동·SpO2·ECG …"),
      code("phr:EnvironmentReading ⊃ PM10·PM2.5·NOx·VOC·HCHO·CO2·온습도  [실내 공기질]"),
      code("phr:OCRDocument ⊃ 처방전·검사지·진단서·약봉투  → 확인 후 PHR 합류"),
      code("phr:Conversation ⊃ 사용자발화·응답 ; DerivedContext(증상·환자맥락) ; UserStatedValue"),
      code("(공유 코어) ReferenceRange·BandLabel·Trend·WellnessLabel·Sensitivity·CrossSignalCombo"),

      h1("2. 객체 속성 (관계) — 신규 포함"),
      table([2400, 2300, 2300, 2360], ["속성", "Domain", "Range", "설명"], [
        ["interpretedAs", "Observation", "BandLabel", "관찰값→밴드(★)"],
        ["measuredBy / hasDeviceGrade", "DeviceMeasurement", "Device·DeviceGrade", "측정 장치·등급"],
        ["interpretedAsWellness / comparedToBaseline", "WatchSignal", "WellnessLabel·Baseline", "웰니스 해석(B1)"],
        ["hasEnvGrade", "EnvironmentReading", "EnvGrade", "공기질 등급"],
        ["partOfCombo", "DeviceMeasurement", "CrossSignalCombo", "교차 조합(I9)"],
        ["extractedFrom / feedsInto", "OCR", "OCRDocument·PHR레코드", "OCR→PHR 합류"],
        ["hasIntent / collectedAxis", "대화", "Intent·DerivedContext", "의도·수집맥락"],
      ]),

      h1("3. 통제 어휘 (Value Sets)"),
      table([2500, 6860], ["개념", "허용값"], [
        ["BandLabel(노출)", "안정 · 주의 · 경고"],
        ["WellnessLabel", "평소대비높음 · 평소대비낮음 · 평소수준 · 참고 (본인 기저선)"],
        ["Trend", "안정유지 · 지속상승 · 지속저하 · 불안정반복 (개선/악화 제외)"],
        ["Sensitivity / Utilization", "일반·민감 / 밴드·deny·시간산술·이력ack·내부·웰니스"],
        ["DeviceGrade / EnvGrade", "의료근접·소비자·웰니스·환경 / 좋음·보통·나쁨·매우나쁨"],
        ["Intent(대화) / ConfirmState(OCR)", "응급·증상·정보·바이탈·비핵심 / 추출됨·확인필요·차단·사용자확인"],
      ]),

      h1("4. 안전 공리 (A·B·C·D — 데이터 모델에 박힌 규칙)"),
      p("A · PHR", { r: { bold: true, color: "1F4E79" }, sp: { before: 80, after: 40 } }),
      table([700, 8660], ["#", "규칙"], [
        ["A1", "민감 질환(정신·암·감염병) 표면화 금지 — 내부 신호만"],
        ["A2", "deny(eGFR·골밀도·요단백·LDL) 밴드 금지 → '수치는 의료진과'"],
        ["A3", "노출 라벨 ⊆ {안정,주의,경고}; 임상/질환명 라벨 내부 전용"],
        ["A4·A5", "추세는 데이터 패턴만(개선/악화 금지) · 원시값 외부 미전송"],
        ["A6·A7·A8", "암검진 갭 시간산술 · 처방=계열·과거시제 · 표면화=일반∧관련∧신선"],
      ]),
      p("B · 장치 / 환경", { r: { bold: true, color: "1F4E79" }, sp: { before: 100, after: 40 } }),
      table([700, 8660], ["#", "규칙"], [
        ["B1", "deviceGrade=웰니스 ⇒ 임상밴드 금지, 본인 기저선 WellnessLabel만"],
        ["B2", "ECG·불규칙맥·워치SpO2(저산소)·낙상·합성점수 deny (기기 알림 패스스루만)"],
        ["B3·B4", "워치 웰니스 신호 교차 입력 제외 · 교차=화이트리스트+출처 필수(미등재 금지)"],
        ["B5", "환경: 진단 아님 — '환경 교차 참고+환기 권유' 천장, 실내 한정"],
        ["B6·B7", "타이핑 수치 미활성 · 원시값·고해상 파형(ECG·RR·hypnogram) 전송 금지(집계만)"],
        ["B8·B9", "출처충돌→재측정 권유 · 체지방·근육·내장지방 추세 위주·천장 낮음"],
      ]),
      p("C · OCR    /    D · 대화", { r: { bold: true, color: "1F4E79" }, sp: { before: 100, after: 40 } }),
      table([700, 8660], ["#", "규칙"], [
        ["C1·C2", "확인 전 활용 차단 · 진단서→질병이력 자동생성 금지(사람 확인분만)"],
        ["C3·C4·C5", "민감·단위·용량 강제 재확인 · 단위 실패=차단 · 확인 후 디바이스급 승격"],
        ["D1·D2", "진술수치=밴드 미활성(증상 맥락만) · 매 턴 응급 재평가 불변"],
        ["D3·D4·D5", "맥락=shaping(진단 아님) · 멀티턴 재질문 금지 · 자유텍스트 동의·마스킹"],
      ]),
      p("핵심: 소스는 여럿이어도 해석·안전은 한 코어. 새 장치가 추가돼도 signalKey로 같은 참조범위·안전 규칙을 재사용한다.", { r: { bold: true }, sp: { before: 120 } }),

      h1("부록. 파일"),
      p("· phr-ontology.ttl · device-ontology.ttl · context-ontology.ttl (OWL/Turtle) · 통합_온톨로지.xlsx · phr-ontology-unified.svg(구조도)", { r: { size: 18 } }),
    ],
  }],
});
Packer.toBuffer(doc).then((b) => { fs.writeFileSync("docs/ontology/통합_온톨로지_2026-06-21.docx", b); console.log("written:", b.length); });
