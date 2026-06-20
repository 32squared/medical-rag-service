// PHR 온톨로지 → Word(.docx). 한글: 맑은 고딕.
// 실행: NODE_PATH="$(npm root -g)" node scripts/build_phr_ontology_docx.js
const fs = require("fs");
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  AlignmentType, HeadingLevel, BorderStyle, WidthType, ShadingType, PageBreak, Footer, PageNumber } = require("docx");

const FONT = "Malgun Gothic", MONO = "Consolas", CW = 9360;
const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };
const HEAD = "1F4E79", ALT = "EDF2F7", SENS = "F7E2D2";
const t = (x, o = {}) => new TextRun({ text: x, font: FONT, ...o });
const h1 = (x) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [t(x, { bold: true })] });
const p = (x, o = {}) => new Paragraph({ spacing: { after: 100, ...(o.sp || {}) }, children: [t(x, o.r || {})] });
const code = (x) => new Paragraph({ spacing: { after: 0 }, children: [new TextRun({ text: x, font: MONO, size: 17 })] });
function table(colW, header, rows) {
  const mk = (cells, head) => new TableRow({ tableHeader: !!head, children: cells.map((c, i) => new TableCell({
    borders, width: { size: colW[i], type: WidthType.DXA },
    shading: { fill: head ? HEAD : (cells.__sens ? SENS : (rows.indexOf(cells) % 2 ? ALT : "FFFFFF")), type: ShadingType.CLEAR },
    margins: { top: 50, bottom: 50, left: 90, right: 90 },
    children: String(c).split("\n").map((l) => new Paragraph({ spacing: { after: 0 }, children: [t(l, head ? { bold: true, color: "FFFFFF", size: 16 } : { size: 16 })] })) })) });
  return new Table({ width: { size: CW, type: WidthType.DXA }, columnWidths: colW, rows: [mk(header, true), ...rows.map((r) => mk(r))] });
}
const sens = (a) => { a.__sens = true; return a; };

const doc = new Document({
  styles: { default: { document: { run: { font: FONT, size: 20 } } },
    paragraphStyles: [{ id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 28, bold: true, font: FONT, color: "1F4E79" }, paragraph: { spacing: { before: 280, after: 140 }, outlineLevel: 0 } }] },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [t("PHR 온톨로지 · ", { size: 16, color: "888888" }), new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 16, color: "888888" })] })] }) },
    children: [
      new Paragraph({ spacing: { before: 1200, after: 0 }, alignment: AlignmentType.CENTER, children: [t("PHR 데이터 온톨로지", { bold: true, size: 44, color: "1F4E79" })] }),
      new Paragraph({ spacing: { after: 500 }, alignment: AlignmentType.CENTER, children: [t("개념 · 관계 · 통제어휘 · 안전 공리", { size: 24, color: "2E5496" })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 600 }, children: [t("나만의 주치의 · 2026-06-21", { size: 20, color: "555555" })] }),
      p("공단·심평원 건강검진/진료/처방 데이터를 진단 없이 안전하게 활용하기 위한 개념 모델. 정본 파일: phr-ontology.ttl(OWL), PHR_온톨로지.xlsx.", { r: { italics: true, color: "555555" } }),
      new Paragraph({ children: [new PageBreak()] }),

      h1("1. 클래스 계층 (Taxonomy)"),
      code("phr:Person  /  phr:PHR"),
      code("phr:HealthRecord (추상)"),
      code("  ├ HealthCheckup(건강검진) · DiseaseHistory(질병이력) · FamilyHistory(가족력)"),
      code("  ├ Lifestyle(생활습관) · CancerScreening(암검진) · HealthReport(건강리포트)"),
      code("  └ Prescription(처방) · TreatmentVisit(진료이력)"),
      code("phr:Observation (관찰값, 추상)"),
      code("  ├ Anthropometric(계측): 신장·체중·허리·BMI"),
      code("  ├ VitalMeasure(활력): 수축기·이완기 혈압"),
      code("  ├ BloodTest(혈액): 혈색소·혈당·TC·HDL·LDL·TG·크레아티닌·eGFR"),
      code("  ├ LiverFunctionTest(간): AST·ALT·GGT"),
      code("  ├ UrineTest(요): 요단백 · ImagingResult(영상): 흉부X선"),
      code("  └ BoneDensity: T-score · OverallJudgment: 종합판정"),
      code("(보조) Condition·DrugClass·Institution·MedicalDepartment·"),
      code("       RecommendedCycle·ReferenceRange·Band·BandLabel·Trend"),

      h1("2. 객체 속성 (관계)"),
      table([2000, 1900, 2100, 3360], ["속성", "Domain", "Range", "설명"], [
        ["hasObservation", "HealthCheckup", "Observation", "검진→관찰값"],
        ["interpretedAs", "Observation", "BandLabel", "관찰값→밴드 라벨 (★핵심, A3·A5)"],
        ["comparedTo", "Observation", "ReferenceRange", "관찰값→참조범위(해석 입력)"],
        ["partOfTrend", "Observation", "Trend", "관찰값→추세"],
        ["hasDrugClass", "Prescription", "DrugClass", "처방→약물계열(약물명 X)"],
        ["records / diagnosis", "이력·진료", "Condition", "질환/상병 참조"],
        ["screensFor / recommendedCycle", "CancerScreening", "Condition·Cycle", "암검진→대상·권장주기"],
        ["hasSensitivity / hasProvenance", "(횡단)", "Sensitivity·Provenance", "민감도·출처 분류"],
      ]),

      h1("3. 데이터 속성 (Attributes)"),
      table([2200, 2600, 1300, 3260], ["속성", "Domain", "타입", "설명"], [
        ["value", "Observation", "decimal", "원시 측정값 — 내부전용·외부 미전송(A5)"],
        ["clinicalLabel", "Observation", "string", "임상/질환명 — 내부전용(A3)"],
        ["labelUser", "Observation", "enum", "노출 라벨(안정/주의/경고)"],
        ["qualitativeValue", "UrineTest 등", "string", "정성 결과"],
        ["daysSupplied", "Prescription", "integer", "처방일수(리필 산술)"],
        ["isPresent / ageAtOnset", "이력·가족력", "bool·int", "이력 유무·발병연령"],
      ]),

      h1("4. 통제 어휘 (Value Sets)"),
      table([2400, 6960], ["개념", "허용값"], [
        ["BandLabel(노출)", "안정 · 주의 · 경고"],
        ["Trend", "안정유지 · 지속상승 · 지속저하 · 불안정반복  (개선/악화 제외)"],
        ["Sensitivity", "일반 · 민감(정신·암·감염병)"],
        ["Utilization", "밴드 · deny · 시간산술 · 이력ack · 내부"],
        ["VisitType / ScreeningResult", "외래·입원·응급 / 정상·이상소견·판정유보"],
        ["Provenance", "공단 · 심평원 · 파트너앱 · OCR"],
      ]),

      h1("5. 안전 공리 (A1~A8) — 데이터 모델에 박힌 규칙"),
      table([700, 8660], ["#", "규칙"], [
        ["A1", "민감 질환(정신·암·감염병)은 표면화 금지 — 내부 신호만"],
        ["A2", "deny 목록(eGFR·골밀도·요단백·LDL)은 밴드 라벨 금지 → '수치는 의료진과'"],
        ["A3", "노출 라벨 ⊆ {안정,주의,경고}; 임상/질환명 라벨은 내부 전용"],
        ["A4", "추세는 데이터 패턴만 — '개선/악화'(건강 판단) 금지"],
        ["A5", "원시 측정값은 내부 전용 — 외부(LLM/국외) 미전송"],
        ["A6", "암검진 갭 = 오늘 − 마지막수검일 − 권장주기 (시간산술)"],
        ["A7", "처방 노출 = 약물계열 ∧ 과거시제 ∧ (정신과·항감염 계열은 내부)"],
        ["A8", "표면화 = 민감도 일반 ∧ 질의 관련 ∧ 신선일 때만"],
      ]),
      p("이 온톨로지의 핵심: 개념·관계뿐 아니라 우리 안전설계(진단 금지·민감 비표시·deny·원시값 비노출)를 공리로 박아, 데이터 모델 자체가 의료법·프라이버시 규칙을 강제한다.", { r: { bold: true }, sp: { before: 120 } }),

      h1("부록. 직렬화"),
      p("· phr-ontology.ttl — OWL/Turtle(Protégé 열람)  · PHR_온톨로지.xlsx — 시트별 카탈로그(필드분류 43행 포함)", { r: { size: 18 } }),
      code("phr:eGFR rdfs:subClassOf phr:BloodTest ; phr:utilization phr:Deny .   # A2"),
      code("phr:interpretedAs rdfs:domain phr:Observation ; rdfs:range phr:BandLabel ."),
      code("phr:Depression rdfs:subClassOf phr:Condition ; phr:sensitivity phr:Sensitive .  # A1"),
    ],
  }],
});
Packer.toBuffer(doc).then((b) => { fs.writeFileSync("docs/ontology/PHR_온톨로지_2026-06-21.docx", b); console.log("written:", b.length); });
