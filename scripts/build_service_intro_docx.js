// "무엇을 해주는 서비스인가" — 실제 대화 예시 중심 보고서 → Word(.docx). 한글: 맑은 고딕.
// 실행: NODE_PATH="$(npm root -g)" node scripts/build_service_intro_docx.js
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

// 대화 블록
function situation(text) {
  return new Paragraph({ spacing: { before: 150, after: 30 }, children: [t("상황  ", { bold: true, size: 18, color: "B06A00" }), t(text, { size: 18, italics: true, color: "8a6d3b" })] });
}
function qLine(text) {
  return new Paragraph({ shading: { type: ShadingType.CLEAR, fill: Q_FILL }, spacing: { before: 60, after: 0 },
    border: { left: { style: BorderStyle.SINGLE, size: 22, color: "2E5496", space: 8 } },
    children: [t("사용자   ", { bold: true, color: "1F4E79", size: 20 }), t(text, { size: 21 })] });
}
function aLine(text, note) {
  const out = [new Paragraph({ shading: { type: ShadingType.CLEAR, fill: A_FILL }, spacing: { before: 0, after: note ? 0 : 30 },
    border: { left: { style: BorderStyle.SINGLE, size: 22, color: "548235", space: 8 } },
    children: [t("주치의   ", { bold: true, color: "2E5d27", size: 20 }), t(text, { size: 21 })] })];
  if (note) out.push(new Paragraph({ spacing: { before: 20, after: 30 }, indent: { left: 240 }, children: [t("→ " + note, { italics: true, size: 17, color: "8a8a8a" })] }));
  return out;
}
function scTitle(text) { return new Paragraph({ spacing: { before: 240, after: 40 }, children: [t(text, { bold: true, size: 23, color: "1F4E79" })] }); }

function table(colW, header, rows) {
  const rowFill = (r) => (r.__star ? STAR_FILL : (rows.indexOf(r) % 2 ? ALT_FILL : "FFFFFF"));
  const mk = (cells, head) => new TableRow({ tableHeader: !!head, children: cells.map((c, i) => new TableCell({
    borders, width: { size: colW[i], type: WidthType.DXA },
    shading: { fill: head ? HEAD_FILL : rowFill(cells), type: ShadingType.CLEAR },
    margins: { top: 70, bottom: 70, left: 110, right: 110 },
    children: String(c).split("\n").map((line) => new Paragraph({ spacing: { after: 0 }, children: [t(line, head ? { bold: true, color: "FFFFFF", size: 18 } : { size: 18, bold: i === 0 && !!cells.__b0 })] })),
  })) });
  return new Table({ width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: colW, rows: [mk(header, true), ...rows.map((r) => mk(r))] });
}

const doc = new Document({
  styles: {
    default: { document: { run: { font: FONT, size: 21 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 30, bold: true, font: FONT, color: "1F4E79" }, paragraph: { spacing: { before: 300, after: 160 }, outlineLevel: 0 } },
    ],
  },
  numbering: { config: [{ reference: "b", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 460, hanging: 260 } } } }] }] },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [t("나만의 주치의 · 서비스 소개 · ", { size: 16, color: "888888" }), new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 16, color: "888888" })] })] }) },
    children: [
      // 표지
      new Paragraph({ spacing: { before: 1500, after: 0 }, alignment: AlignmentType.CENTER, children: [t("나만의 주치의", { bold: true, size: 50, color: "1F4E79" })] }),
      new Paragraph({ spacing: { after: 500 }, alignment: AlignmentType.CENTER, children: [t("무엇을 해주는 서비스인가", { bold: true, size: 32, color: "2E5496" })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 700 }, children: [t("실제 대화로 보는 서비스 소개 · 2026-06-20", { size: 21, color: "555555" })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, border: { top: { style: BorderStyle.SINGLE, size: 6, color: "1F4E79", space: 8 }, bottom: { style: BorderStyle.SINGLE, size: 6, color: "1F4E79", space: 8 } }, spacing: { before: 200, after: 200 }, children: [
        t("건강관리 앱 안에 들어가는 챗봇입니다. 사용자가 건강을 물으면 ", { size: 22 }),
        t("안전하게 답하고, 연결된 기기·검진 데이터를 그 답변에 반영", { size: 22, bold: true }),
        t("해줍니다.", { size: 22 }),
      ] }),
      new Paragraph({ children: [new PageBreak()] }),

      // 1. 한 줄 정의
      h1("1. 한 줄로 말하면"),
      p("“챗GPT 건강 버전”이 아닙니다. 사용자의 진짜 측정값·검진 기록을 — 진단은 하지 않으면서 — 답변에 안전하게 반영해주는 챗봇입니다. 이것이 일반 AI는 못 하는 부분이고, 디바이스·검진 데이터를 가진 헬스앱이 우리를 탑재하는 이유입니다.", { run: { bold: true } }),

      // 2. 실제 대화 예시 (핵심)
      h1("2. 실제로 이런 대화를 합니다"),

      scTitle("① 그냥 건강이 궁금할 때"),
      qLine("두통이 자주 나는데 왜 그럴까요?"),
      ...aLine("두통은 수면 부족·스트레스·근육 긴장 등 여러 원인과 관련될 수 있어요. 공인 자료를 바탕으로 가능한 원인을 알려드리고, 갑작스러운 심한 두통이나 말이 어눌해지는 증상이 함께 있으면 진료를 권해드려요.", "검색·블로그와 달리 공인 출처(질병청·학회) 기반. 특정 병으로 단정하지 않음."),

      scTitle("② 병원 가야 하나 고민될 때"),
      qLine("3일째 기침이 안 멎어요."),
      ...aLine("지속되는 기침의 일반적 원인과 생활 관리법을 알려드리고, 안정 시에도 숨이 차거나 가래에 피가 섞이면 호흡기내과 상담을 권해드려요. 증상이 계속되면 가까운 시일 내 진료를 고려해보세요.", "어느 진료과로, 언제 가면 좋은지까지 안내."),

      scTitle("③ 위험한 증상일 때"),
      qLine("갑자기 가슴이 쥐어짜듯 아프고 식은땀이 나요."),
      ...aLine("즉시 119에 연락하거나 가까운 응급실을 이용하세요.", "위험 신호를 감지하면 다른 안내보다 응급 안내를 최우선으로 함."),

      scTitle("④ ★ 기기를 연결했을 때 — 핵심 차별점"),
      situation("집 혈압기로 측정한 값(145/92)이 앱에 올라옴"),
      qLine("내 혈압 괜찮은 거예요?"),
      ...aLine("최근 측정된 혈압이 관리가 권장되는 구간으로 확인돼요. 한 번의 측정만으로 판단하지 않으니, 며칠간 반복 측정해보시고 의료진과 상담해보시길 권해드려요.", "GPT·Gemini는 이 답을 못 함 — 거절하거나 “고혈압입니다” 위험 단정. 우리는 진단 없이 데이터를 안전하게 반영."),

      scTitle("⑤ 증상과 기기 데이터를 함께"),
      situation("혈압 데이터가 연결되어 있음"),
      qLine("머리가 아픈데 혹시 혈압 때문일까요?"),
      ...aLine("두통은 여러 원인과 관련될 수 있어요. 최근 혈압이 관리 권장 구간으로 기록돼 있어 함께 살펴보시면 좋고, 증상이 반복되면 의료진 상담을 권해드려요.", "내 측정 데이터를 증상 답변과 자연스럽게 연결."),

      scTitle("⑥ 검진 기록을 연결했을 때 — 먼저 챙겨줌"),
      ...aLine("건강검진 기록을 보니 위암검진 권장주기(2년)가 지난 것으로 보여요. 검진 시기를 의료진과 상의해보시면 좋겠어요.", "놓치기 쉬운 검진 시기를 먼저 알려줌(결과 판정은 하지 않음)."),

      scTitle("⑦ 약이 궁금할 때"),
      qLine("타이레놀 하루에 얼마나 먹어도 돼요?"),
      ...aLine("해당 성분(아세트아미노펜) 계열의 일반적인 주의사항을 안내드리되, 정확한 용량·복용법은 약사나 의료진과 상담이 필요해요.", "구체적 용량은 단정하지 않음(의료법 안전)."),

      new Paragraph({ children: [new PageBreak()] }),

      // 3. 무엇을 연결하면 무엇을 해주나
      h1("3. 무엇을 연결하면, 무엇을 해주나"),
      table([2200, 3760, 3400], ["연결하는 기기·기록", "올라오는 데이터", "해주는 것"], [
        (() => { const r = ["가정용 혈압기", "수축기·이완기·맥박", "내 혈압이 어느 구간인지 안내 + 추세"]; r.__star = true; r.__b0 = true; return r; })(),
        (() => { const r = ["스마트 체중계", "체중·BMI·체지방·근육·내장지방", "체중·BMI 추세, 혈압과 함께 보기"]; r.__b0 = true; return r; })(),
        (() => { const r = ["스마트워치 / 밴드", "심박·수면·활동·산소포화도 등", "수면·활동·안정시심박 추세(웰니스)"]; r.__b0 = true; return r; })(),
        (() => { const r = ["통합 측정기(Vital)", "맥박·산소포화도·혈압·체온·스트레스", "한 번에 여러 항목 측정값 안내"]; r.__b0 = true; return r; })(),
        (() => { const r = ["건강검진 기록(PHR)", "검진 수치·질병/가족력·처방·암검진", "검진 시기 챙김, 내 이력을 답변에 반영"]; r.__b0 = true; return r; })(),
        (() => { const r = ["종이기록 사진(OCR)", "처방전·검사지·진단서·약봉투", "종이 기록을 찍으면 데이터로 전환해 활용"]; r.__b0 = true; return r; })(),
      ]),
      p("기기를 연결하지 않은 사용자도 ①②③⑦(일반 답변·증상·응급·약 정보)은 그대로 이용합니다. 연동은 ‘내 데이터 맞춤’이라는 추가 가치를 더하는 것.", { run: { size: 19 } }),

      // 4. 차별점
      h1("4. 왜 일반 AI(GPT·Gemini)로는 안 되나"),
      p("같은 “내 혈압 145/92”를 받았을 때:"),
      table([3000, 6360], ["", "응답"], [
        ["일반 AI(GPT·Gemini)", "거절(“의사와 상담하세요”) 또는 위험한 단정(“고혈압입니다”). 둘 다 쓸모없거나 위험."],
        (() => { const r = ["나만의 주치의", "“관리 권장 구간 — 반복 측정·의료진 상담 권유”로 안전하게 안내. 원시 수치·질환명은 외부 AI에 전송조차 안 함."]; r.__star = true; return r; })(),
      ]),
      p("= 기기·검진 데이터를 가진 헬스앱이 일반 AI 대비 가질 수 있는 ‘유일하게 합법적인 무기’.", { run: { bold: true } }),

      // 5. 안심하고 쓸 수 있는 이유
      h1("5. 안심하고 쓸 수 있는 이유 (안전)"),
      bullet("진단을 하지 않는다 — 측정값은 ‘구간 안내 + 의료진 상담’으로만. “고혈압입니다” 같은 단정을 사용자에게 하지 않음(의료법 안전)."),
      bullet("내 원시 데이터가 외부로 안 나간다 — 수치 해석은 국내 시스템에서만, 외부 AI엔 비식별 라벨만(그조차 미전송 구조)."),
      bullet("민감한 이력은 화면에 안 띄운다 — 정신건강·암·감염병 이력은 내부 참고만. 가족과 기기를 같이 써도 안전."),
      bullet("위험을 놓치지 않는다 — 위험한 수치를 ‘괜찮다’고 안심시키지 않도록 설계·검증(‘경고는 민감하게, 안심은 보수적으로’)."),

      // 6. 현황 / 다음
      h1("6. 지금 가능 / 곧 가능, 그리고 남은 결정"),
      bullet("지금 제공: ①②③⑦ 일반 건강 답변·증상 상담·응급 안내·약 정보."),
      bullet("엔진 완성(연동되면 즉시): ④⑤ 기기 측정값 맞춤 안내·검진 챙김 — 혈압 등 측정값을 안전하게 답변에 녹이는 핵심 엔진은 이미 구현·검증 완료."),
      bullet("남은 결정 2가지(사업): ① 기기 연동 방식(파트너앱 전달이 유력 / 애플 건강·삼성 헬스 경유) ② 검진(PHR) 데이터 출처. 이 둘이 정해지면 ‘내 데이터 맞춤’ 가치가 사용자에게 실제로 도달.", { bold: true }),

      // 7. 한 줄 요약
      h1("7. 한 줄 요약"),
      p("건강을 물으면 안전하게 답하고, 내가 연결한 혈압기·워치·검진 데이터를 그 답에 ‘진단 없이’ 반영해주는 챗봇. 일반 AI가 못 하는 ‘내 건강 데이터를 안전하게 쓰는 AI’입니다.", { run: { bold: true, size: 22 } }),
    ],
  }],
});

Packer.toBuffer(doc).then((buf) => { fs.writeFileSync("docs/나만의주치의_서비스소개_2026-06-20.docx", buf); console.log("written:", buf.length, "bytes"); });
