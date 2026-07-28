// 개인화 "고객 가치" 보고서 → Word(.docx). 한글: 맑은 고딕.
// 실행: NODE_PATH="$(npm root -g)" node scripts/build_personalization_report_docx.js
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
const HEAD_FILL = "1F4E79";
const ALT_FILL = "EDF2F7";
const STAR_FILL = "FCE8D5";

function t(text, opts = {}) { return new TextRun({ text, font: FONT, ...opts }); }
function p(text, opts = {}) {
  return new Paragraph({ children: [t(text, opts.run || {})], spacing: { after: 120, ...(opts.spacing || {}) }, ...(opts.p || {}) });
}
function h1(text) { return new Paragraph({ heading: HeadingLevel.HEADING_1, children: [t(text, { bold: true })] }); }
function h2(text) { return new Paragraph({ heading: HeadingLevel.HEADING_2, children: [t(text, { bold: true })] }); }
function bullet(text, opts = {}) {
  return new Paragraph({ numbering: { reference: "b", level: 0 }, spacing: { after: 60 }, children: [t(text, opts)] });
}
function table(colW, header, rows) {
  const rowFill = (r) => (r.__star ? STAR_FILL : (rows.indexOf(r) % 2 ? ALT_FILL : "FFFFFF"));
  const mk = (cells, isHead) => new TableRow({
    tableHeader: !!isHead,
    children: cells.map((c, i) => new TableCell({
      borders, width: { size: colW[i], type: WidthType.DXA },
      shading: { fill: isHead ? HEAD_FILL : rowFill(cells), type: ShadingType.CLEAR },
      margins: { top: 70, bottom: 70, left: 110, right: 110 },
      children: String(c).split("\n").map((line) =>
        new Paragraph({ spacing: { after: 0 }, children: [t(line, isHead ? { bold: true, color: "FFFFFF", size: 18 } : { size: 18, bold: i === 0 && !!cells.__b0 })] })),
    })),
  });
  return new Table({ width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: colW, rows: [mk(header, true), ...rows.map((r) => mk(r, false))] });
}

const doc = new Document({
  styles: {
    default: { document: { run: { font: FONT, size: 21 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 30, bold: true, font: FONT, color: "1F4E79" }, paragraph: { spacing: { before: 280, after: 160 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: FONT, color: "2E5496" }, paragraph: { spacing: { before: 200, after: 120 }, outlineLevel: 1 } },
    ],
  },
  numbering: { config: [{ reference: "b", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 460, hanging: 260 } } } }] }] },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [t("마이헬스케어 · 개인화 고객가치 보고서 · ", { size: 16, color: "888888" }), new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 16, color: "888888" })] })] }) },
    children: [
      // 표지
      new Paragraph({ spacing: { before: 1300, after: 0 }, alignment: AlignmentType.CENTER, children: [t("개인 건강데이터·기기 연동 AI 안내", { bold: true, size: 40, color: "1F4E79" })] }),
      new Paragraph({ spacing: { after: 500 }, alignment: AlignmentType.CENTER, children: [t("고객 가치 보고서", { bold: true, size: 34, color: "2E5496" })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 }, children: [t("무엇을 연결하나 · 무엇을 제공하나 · 어떤 가치를 주나", { size: 23, color: "333333" })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 600 }, children: [t("마이헬스케어 (medical-rag-service) · 2026-06-20", { size: 20, color: "555555" })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, border: { top: { style: BorderStyle.SINGLE, size: 6, color: "1F4E79", space: 8 }, bottom: { style: BorderStyle.SINGLE, size: 6, color: "1F4E79", space: 8 } }, spacing: { before: 200, after: 200 }, children: [
        t("혈압기·체중계·워치·검진기록 등의 데이터를 ", { size: 21, italics: true }),
        t("안전하게(의료법 위반 0) ", { size: 21, italics: true, bold: true }),
        t("연동해, 범용 AI(GPT·Gemini)가 못 하는 ", { size: 21, italics: true }),
        t("“내 데이터 기반 건강 안내”", { size: 21, italics: true, bold: true }),
        t("를 제공한다.", { size: 21, italics: true }),
      ] }),
      new Paragraph({ children: [new PageBreak()] }),
      new Paragraph({ heading: HeadingLevel.HEADING_1, children: [t("목차", { bold: true })] }),
      new TableOfContents("목차", { hyperlink: true, headingStyleRange: "1-2" }),
      new Paragraph({ children: [new PageBreak()] }),

      // 1. 고객
      h1("1. 고객은 누구인가"),
      table([2600, 6760], ["고객", "설명"], [
        ["파트너 (1차 고객)", "건강관리앱 운영사 — 혈압기·체중계·워치·검진 데이터를 보유. 우리 AI를 앱에 탑재한다."],
        ["최종 사용자", "앱으로 건강을 관리하는 일반인 — 증상이 궁금하거나, 측정값의 의미를 알고 싶거나, 병원에 가야 할지 판단하고 싶은 사람."],
      ]),

      // 2. 연동 데이터 소스 (핵심) ─────────────────────
      h1("2. 무엇을 연결하나 — 연동 데이터 소스 (핵심)"),
      p("이 서비스의 심장은 ‘기기·기록 연동’이다. 아래 6종 데이터 소스를 연결하면, 각 데이터가 빠짐없이 답변에 활용된다.", { run: { bold: true } }),
      table([2100, 3760, 3500],
        ["기기 / 데이터 소스", "올라오는 데이터", "연결 시 사용자가 얻는 것"],
        [
          (() => { const r = ["가정용 혈압기", "수축기·이완기·맥박", "내 혈압이 어느 구간인지 안내 + 측정 추세, 체중과 함께 보기"]; r.__star = true; r.__b0 = true; return r; })(),
          (() => { const r = ["스마트 체중계", "체중·BMI·체지방률·근육량·내장지방", "체중·BMI 추세, 대사 관련 항목을 함께 안내"]; r.__b0 = true; return r; })(),
          (() => { const r = ["스마트워치 / 밴드", "심박·HRV·수면·활동·산소포화도·심전도", "수면·활동·안정시심박 추세(웰니스), 컨디션 변화 인식"]; r.__b0 = true; return r; })(),
          (() => { const r = ["통합 측정기 (Vital)", "맥박·산소포화도·혈압·체온·스트레스", "한 번에 여러 항목의 측정값 안내"]; r.__b0 = true; return r; })(),
          (() => { const r = ["건강검진 기록 (PHR)", "검진 수치·질병/가족력·처방·암검진 이력", "검진 시기 챙김, 내 이력 맥락을 안내에 반영"]; r.__b0 = true; return r; })(),
          (() => { const r = ["종이기록 사진 (OCR)", "처방전·검사지·진단서·약봉투", "종이 기록을 찍으면 데이터로 전환해 활용"]; r.__b0 = true; return r; })(),
        ]),
      p("설계 원칙: 위 모든 소스의 데이터가 ‘수집만 하고 안 쓰는 것 없이’ 하나하나 활용되도록 정리했다. 단, 정확도·위험에 따라 ‘구간 안내’할 것과 ‘참고만’ 할 것, ‘표시 안 하고 내부 참고만’ 할 것(예: 정신건강 이력)을 구분한다.", { run: { size: 19 } }),

      // 3. 어떻게 연결되나
      h1("3. 어떻게 연결되나 — 연동 구조"),
      table([3120, 3120, 3120],
        ["① 기기/앱", "② 우리 AI (국내)", "③ 사용자 답변"],
        [["혈압기·워치·검진 등\n데이터 전송", "원시값을 ‘구간 라벨’로\n안전 해석(진단 아님)", "“관리 권장 구간,\n의료진 상담 권유”"]]),
      bullet("연결 경로: 파트너 헬스앱이 보유한 기기·검진 데이터를 우리 AI로 전달(앱 연동) → 헬스플랫폼(애플 건강·삼성 헬스) 경유 방식도 가능.", { }),
      bullet("안전 핵심: 원시 수치(예: 165/105)는 우리 시스템(국내)에서만 해석하고, 외부 AI(국외)에는 비식별 ‘구간 라벨’만 — 그조차 전송하지 않는 구조. 규제·프라이버시 안전.", { bold: true }),
      bullet("연결 안 해도 동작: 기기를 연결하지 않은 사용자에게도 일반 건강 답변·증상 상담·응급 안내는 그대로 제공(연동은 ‘추가 가치’).", { }),

      // 4. 역량 × 가치
      h1("4. 고객에게 제공하는 것 — 역량 × 가치"),
      table([1900, 2700, 2380, 2380],
        ["역량", "사용자 경험", "사용자 가치", "사업(파트너) 가치"],
        [
          ["① 신뢰 건강 답변", "“두통은 왜 생겨?” → 공인 출처(질병청·식약처·학회) 인용", "출처 있는 안내(검색·블로그 대비)", "앱 내 신뢰 채널"],
          ["② 증상 상담·진료 안내", "증상 → 가능한 원인·진료과·내원 시점", "불안 해소, 병원행 판단", "체류·재방문 증가"],
          ["③ 응급 즉시 안내", "위험 증상 → 즉시 119/응급실", "안전사고 방지", "사고·책임 리스크↓"],
          (() => { const r = ["④ ★ 기기데이터 맞춤안내", "혈압 측정 → “관리 권장 구간, 상담 권유”", "내 데이터 기반 ‘주치의’ 경험", "GPT엔 없는 데이터 연계 차별점"]; r.__star = true; return r; })(),
          ["⑤ 검진·진료 챙김", "“암검진 권장주기가 지났어요”", "놓치는 관리 챙김", "건강관리 가치 제고"],
          ["⑥ 컨디션 추세(웰니스)", "수면·활동·심박의 본인 기준 추세", "일상 건강 인식", "일일 사용·락인"],
        ]),

      // 5. 차별점
      h1("5. 핵심 차별점 — 왜 범용 AI는 못 하는가"),
      p("같은 “내 혈압 150”을 받았을 때:"),
      table([3000, 6360], ["", "응답"], [
        ["범용 AI(GPT·Gemini)", "거절(“의사와 상담하세요”) 또는 위험한 단정(“고혈압 2기입니다”). 둘 다 가치 없거나 위험."],
        (() => { const r = ["마이헬스케어", "진단하지 않고 “관리 권장 구간 — 의료진 상담 권유”로 안내. 원시 수치·질환명은 외부 AI에 전송조차 안 함."]; r.__star = true; return r; })(),
      ]),
      p("= 기기·검진 데이터를 가진 헬스앱이 범용 AI 대비 가질 수 있는 ‘유일하게 합법적인 무기’. 데이터를 자산으로 만들려면 그 데이터를 안전하게 쓰는 엔진이 필요하다.", { run: { bold: true } }),

      // 6. 안전 = 가치
      h1("6. ‘안전’이 곧 사업 가치 — 규제 리스크 제거"),
      table([3300, 6060], ["파트너의 우려", "우리 설계가 제거하는 방식"], [
        ["무면허 의료행위(의료법)", "진단·처방 단정 0 — 측정값은 ‘구간 안내 + 의료진 상담’으로만. 질환명을 사용자에게 출력 안 함."],
        ["개인정보·국외이전", "원시 건강데이터를 외부 AI(국외)로 전송 안 함 — 비식별 라벨만, 그조차 미전송 구조."],
        ["민감정보 노출", "정신건강·암·감염병 이력은 화면 표시 안 함(내부 참고만). 가족 공유 기기에서도 안전."],
        ["거짓 안심 사고", "위험 수치를 ‘괜찮다’고 오안내하지 않도록 설계·검증(‘경고는 민감, 안심은 보수’)."],
      ]),

      // 7. 현황
      h1("7. 지금 가능 / 곧 가능 (정직한 현황)"),
      table([2400, 5260, 1700], ["역량", "내용", "상태"], [
        ["① ② ③", "비개인화 건강 답변·증상 상담·응급 안내", "제공 중"],
        (() => { const r = ["④ 기기데이터 맞춤", "혈압 등 측정값을 안전하게 답변에 반영하는 엔진 — 구현·검증 완료. 기기 데이터가 연결되면 즉시 동작.", "엔진 완료\n(연동 시 가동)"]; r.__star = true; return r; })(),
        ["⑥ 컨디션 추세", "수면·활동·심박 추세 해석 엔진 — 구현 완료. 측정 이력 저장 연동 후 표시.", "엔진 완료\n(이력 연동 후)"],
        ["⑤ 검진·진료 챙김", "암검진 시기·진료 이력 안내 — 설계 완료.", "설계 완료\n(로드맵)"],
      ]),
      p("핵심: ‘기기 데이터 맞춤 안내’의 두뇌(안전 해석 엔진)는 이미 완성·검증됐다. 남은 것은 데이터를 ‘어디서 어떻게 받을지’의 연동 결정이다.", { run: { bold: true } }),

      // 8. 다음 결정
      h1("8. 가치 실현을 막는 다음 결정 (사업 의사결정)"),
      table([700, 3100, 5560], ["#", "결정", "이 결정이 여는 가치"], [
        ["1", "기기 연동 방식 — 파트너앱이 데이터를 넘겨줄지(유력) / 헬스플랫폼(애플 건강·삼성 헬스) 경유 / 직접 연동", "역량 ④⑥(측정 맞춤·추세) 실가동 시점 결정"],
        ["2", "검진(PHR) 데이터 출처 — 공단·심평원 직접 / 파트너앱 보유분", "역량 ⑤(검진 챙김)·민감정보 처리 범위 결정"],
      ]),
      p("이 두 결정 후, 개인화 가치(④⑤⑥)가 사용자에게 실제로 도달한다. 해석 엔진은 그대로 재사용 — 데이터 연결만 남았다.", { run: { bold: true } }),

      // 9. 한 장 요약
      h1("9. 한 장 요약"),
      bullet("연결: 혈압기·체중계·워치·통합측정기·검진기록(PHR)·종이기록(OCR) 6종 — 올라오는 데이터를 하나도 버리지 않고 활용.", { bold: true }),
      bullet("제공: 신뢰 건강 답변·증상/진료 안내·응급 안내(지금) + 기기데이터 맞춤·검진 챙김·컨디션 추세(연동 후)."),
      bullet("차별: 범용 AI가 못 하는 ‘건강 데이터를 안전하게 쓰는 AI’ — 헬스앱의 합법적 무기."),
      bullet("안전: 의료법·국외이전·민감정보·거짓안심 리스크를 설계로 제거 → 파트너 도입 명분."),
      bullet("다음: 기기 연동 방식·검진 출처 2개 결정 → 개인화 가치 본격 가동."),
    ],
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync("docs/개인화_고객가치_보고서_v2_2026-06-20.docx", buf);
  console.log("written:", buf.length, "bytes");
});
