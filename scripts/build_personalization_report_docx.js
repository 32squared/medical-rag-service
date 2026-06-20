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
const STAR_FILL = "FCE8D5"; // 핵심 역량 강조

function t(text, opts = {}) { return new TextRun({ text, font: FONT, ...opts }); }
function p(text, opts = {}) {
  return new Paragraph({ children: [t(text, opts.run || {})], spacing: { after: 120, ...(opts.spacing || {}) }, ...(opts.p || {}) });
}
function h1(text) { return new Paragraph({ heading: HeadingLevel.HEADING_1, children: [t(text, { bold: true })] }); }
function h2(text) { return new Paragraph({ heading: HeadingLevel.HEADING_2, children: [t(text, { bold: true })] }); }
function bullet(text, opts = {}) {
  return new Paragraph({ numbering: { reference: "b", level: 0 }, spacing: { after: 60 }, children: [t(text, opts)] });
}

function table(colW, header, rows, opts = {}) {
  const rowFill = (r) => (r.__star ? STAR_FILL : (rows.indexOf(r) % 2 ? ALT_FILL : "FFFFFF"));
  const mk = (cells, isHead) => new TableRow({
    tableHeader: !!isHead,
    children: cells.map((c, i) => new TableCell({
      borders, width: { size: colW[i], type: WidthType.DXA },
      shading: { fill: isHead ? HEAD_FILL : rowFill(cells), type: ShadingType.CLEAR },
      margins: { top: 70, bottom: 70, left: 110, right: 110 },
      children: String(c).split("\n").map((line) =>
        new Paragraph({ spacing: { after: 0 }, children: [t(line, isHead ? { bold: true, color: "FFFFFF", size: 18 } : { size: 18, bold: !!cells.__bold0 && i === 0 })] })),
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
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [t("나만의 주치의 · 개인화 고객가치 보고서 · ", { size: 16, color: "888888" }), new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 16, color: "888888" })] })] }) },
    children: [
      // 표지
      new Paragraph({ spacing: { before: 1300, after: 0 }, alignment: AlignmentType.CENTER, children: [t("개인 건강데이터 기반 AI 안내", { bold: true, size: 44, color: "1F4E79" })] }),
      new Paragraph({ spacing: { after: 500 }, alignment: AlignmentType.CENTER, children: [t("고객 가치 보고서", { bold: true, size: 34, color: "2E5496" })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 }, children: [t("무엇을 제공하는가 · 어떤 가치를 주는가", { size: 24, color: "333333" })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 600 }, children: [t("나만의 주치의 (medical-rag-service) · 2026-06-20", { size: 20, color: "555555" })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, border: { top: { style: BorderStyle.SINGLE, size: 6, color: "1F4E79", space: 8 }, bottom: { style: BorderStyle.SINGLE, size: 6, color: "1F4E79", space: 8 } }, spacing: { before: 200, after: 200 }, children: [
        t("디바이스·검진 데이터를 ", { size: 21, italics: true }),
        t("안전하게(의료법 위반 0) ", { size: 21, italics: true, bold: true }),
        t("연계해, 범용 AI(GPT·Gemini)가 못 하는 ", { size: 21, italics: true }),
        t("“내 데이터 기반 건강 안내”", { size: 21, italics: true, bold: true }),
        t("를 제공한다. 파트너의 규제 리스크를 제거하면서 차별화·체류를 만든다.", { size: 21, italics: true }),
      ] }),
      new Paragraph({ children: [new PageBreak()] }),
      new Paragraph({ heading: HeadingLevel.HEADING_1, children: [t("목차", { bold: true })] }),
      new TableOfContents("목차", { hyperlink: true, headingStyleRange: "1-2" }),
      new Paragraph({ children: [new PageBreak()] }),

      // 1. 고객은 누구인가
      h1("1. 고객은 누구인가"),
      table([2600, 6760], ["고객", "설명"], [
        ["파트너 (1차 고객)", "건강관리앱 운영사 — 혈압기·체중계·워치·검진 데이터를 보유. 우리 AI를 앱에 탑재한다."],
        ["최종 사용자", "앱으로 건강을 관리하는 일반인 — 증상이 궁금하거나, 측정값의 의미를 알고 싶거나, 병원에 가야 할지 판단하고 싶은 사람."],
      ]),
      p("두 고객 모두에게 가치를 줘야 한다: 사용자에겐 ‘쓸모 있는 건강 도우미’, 파트너에겐 ‘차별화 + 규제 안전’.", { run: { bold: true } }),

      // 2. 무엇을 할 수 있는가 (역량 × 가치)
      h1("2. 고객에게 제공하는 것 — 역량 × 가치"),
      p("서비스가 제공하는 6대 역량을, 사용자 경험과 가치(사용자/사업) 기준으로 정리한다."),
      table([1900, 2700, 2380, 2380],
        ["역량", "사용자 경험", "사용자 가치", "사업(파트너) 가치"],
        [
          ["① 신뢰 건강 답변", "“두통은 왜 생겨?” → 공인 출처(질병청·식약처·학회) 인용 답변", "검색·블로그의 부정확 정보 대신 출처 있는 안내", "앱 내 신뢰 채널 확보"],
          ["② 증상 상담·진료 안내", "증상 설명 → 가능한 원인·진료과·언제 가면 좋은지", "막연한 불안 해소, 병원행 판단 도움", "사용자 체류·재방문 증가"],
          ["③ 응급 즉시 안내", "위험 증상 감지 → 즉시 119/응급실 안내", "안전사고 방지", "사고·책임 리스크 감소"],
          (() => { const r = ["④ ★ 내 측정데이터 맞춤안내", "혈압 측정 → “관리 권장 구간입니다, 의료진 상담 권유”", "내 데이터 기반 ‘주치의’ 경험", "GPT·Gemini엔 없는 데이터 연계 차별점"]; r.__star = true; return r; })(),
          ["⑤ 검진·진료 챙김", "“위암검진 권장주기가 지났어요” 등 시기 안내", "놓치기 쉬운 건강 관리 챙김", "건강관리 가치 제고·신뢰"],
          ["⑥ 컨디션 추세(웰니스)", "수면·활동·안정시심박의 본인 기준 추세 참고", "일상 건강 인식", "일일 사용·락인(lock-in)"],
        ]),
      p("★ ④번이 이번 작업의 핵심이자 차별점 — 디바이스/검진 데이터를 ‘진단하지 않고’ 안전하게 답변에 반영한다.", { run: { bold: true } }),

      // 3. 핵심 차별점
      h1("3. 핵심 차별점 — 왜 범용 AI는 못 하는가"),
      p("같은 “내 혈압 150”을 받았을 때:"),
      table([3000, 6360], ["", "응답"], [
        ["범용 AI(GPT·Gemini)", "거절(“진단은 의사와 상담하세요”)하거나, 위험하게 단정(“고혈압 2기입니다”). 둘 다 가치가 없거나 위험."],
        (() => { const r = ["나만의 주치의", "진단하지 않고 “관리 권장 구간 — 의료진 상담 권유”로 안내. 원시 수치·질환명은 외부 AI에 전송조차 안 함. 안전하게 개인 데이터를 활용."]; r.__star = true; return r; })(),
      ]),
      p("= 디바이스·검진 데이터를 가진 헬스앱이 범용 AI 대비 가질 수 있는 ‘유일하게 합법적인 무기’. 데이터가 자산이 되려면, 그 데이터를 안전하게 쓸 수 있는 우리 같은 엔진이 필요하다.", { run: { bold: true } }),

      // 4. 안전 = 사업 가치
      h1("4. ‘안전’이 곧 사업 가치 — 규제 리스크 제거"),
      p("파트너(헬스앱 운영사)가 의료 AI 도입에서 가장 두려워하는 것은 규제·책임 리스크다. 우리는 이를 설계로 제거한다."),
      table([3300, 6060], ["파트너의 우려", "우리 설계가 제거하는 방식"], [
        ["무면허 의료행위(의료법)", "진단·처방 단정 0 — 측정값은 ‘구간 안내 + 의료진 상담’으로만. 질환명(“고혈압 2기”)을 사용자에게 절대 출력 안 함."],
        ["개인정보·국외이전", "원시 건강데이터를 외부 AI(국외)로 전송하지 않음 — 비식별 ‘구간 라벨’만, 그조차 미전송 구조. 동의 부담 최소화."],
        ["민감정보 노출", "정신건강·암·감염병 이력은 화면에 표시하지 않음(내부 참고만). 가족 공유 기기에서도 안전."],
        ["거짓 안심 사고", "위험 수치를 ‘괜찮다’고 오안내하지 않도록 설계·검증. ‘경고는 민감하게, 안심은 보수적으로.’"],
      ]),
      p("→ 규제 리스크가 헬스앱의 의료 AI 도입 장벽인데, 그 장벽을 우리가 설계로 낮춘다 = 도입 설득력 그 자체.", { run: { bold: true } }),

      // 5. 현재 vs 곧
      h1("5. 지금 제공 가능 / 곧 가능 (정직한 현황)"),
      table([2400, 5260, 1700], ["역량", "내용", "상태"], [
        ["① ② ③", "비개인화 건강 답변·증상 상담·응급 안내", "제공 중"],
        (() => { const r = ["④ 측정데이터 맞춤", "혈압 등 측정값을 안전하게 답변에 반영하는 엔진 — 구현·검증 완료. 디바이스 데이터가 연결되면 즉시 동작.", "엔진 완료\n(연동 시 가동)"]; r.__star = true; return r; })(),
        ["⑥ 컨디션 추세", "수면·활동·심박 추세 해석 엔진 — 구현 완료. 측정 이력 저장 연동 후 표시.", "엔진 완료\n(이력 연동 후)"],
        ["⑤ 검진·진료 챙김", "암검진 시기·진료 이력 안내 — 설계 완료.", "설계 완료\n(로드맵)"],
      ]),
      p("핵심: ④번 ‘개인 데이터 맞춤 안내’의 두뇌(안전 해석 엔진)는 이미 완성·검증됐다. 남은 것은 데이터를 ‘어디서 어떻게 받을지’의 연동 결정이다.", { run: { bold: true } }),

      // 6. 다음 결정
      h1("6. 가치 실현을 막는 다음 결정 (사업 의사결정)"),
      table([700, 3100, 5560], ["#", "결정", "이 결정이 여는 가치"], [
        ["1", "디바이스 연동 방식 — 파트너앱이 데이터를 넘겨줄지(유력) / 헬스플랫폼 경유 / 직접 연동", "역량 ④⑥(측정 맞춤·추세)의 실가동 시점을 결정"],
        ["2", "검진(PHR) 데이터 출처 — 공단·심평원 직접 / 파트너앱 보유분", "역량 ⑤(검진 챙김)와 민감정보 처리 범위를 결정"],
      ]),
      p("이 두 결정 후, 개인화 가치(④⑤⑥)가 사용자에게 실제로 도달한다. 해석 엔진은 그대로 재사용 — 데이터 연결만 남았다.", { run: { bold: true } }),

      // 한 장 요약
      h1("7. 한 장 요약"),
      bullet("우리는 ‘건강 데이터를 안전하게 쓰는 AI’다 — 범용 AI가 못 하는 영역.", { bold: true }),
      bullet("사용자에겐: 내 측정값·증상에 맞춘 신뢰 안내 + 병원 가야 할 때 판단 → ‘내 주치의’ 경험."),
      bullet("파트너에겐: GPT 대비 차별화(데이터 연계) + 규제 리스크 제거 → 도입·차별화 명분."),
      bullet("지금: 신뢰 답변·증상·응급 제공 중. 개인 데이터 맞춤 엔진 완성·검증 완료."),
      bullet("다음: 디바이스 연동·검진 출처 2개 결정 → 개인화 가치 본격 가동."),
    ],
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync("docs/개인화_고객가치_보고서_2026-06-20.docx", buf);
  console.log("written:", buf.length, "bytes");
});
