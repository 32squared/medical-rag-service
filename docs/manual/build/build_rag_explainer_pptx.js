/*
 * 마이헬스케어 RAG 쉬운 설명 — 비전공자용 슬라이드 (10장)
 * 브랜드: Warm Light (배경 #F6F4EF · 딥틸 #0E8A6B · 앰버 #E0A23E · 위험 레드)
 * 빌드: NODE_PATH=<global node_modules> node build_rag_explainer_pptx.js
 */
const path = require("path");
const pptxgen = require("pptxgenjs");

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
pres.author = "마이헬스케어";
pres.title = "마이헬스케어 RAG, 쉽게 이해하기";

const W = 13.33, H = 7.5, ML = 0.7, UW = W - ML * 2;
const FONT = "Malgun Gothic";
const P = {
  TEAL: "0E8A6B", TEALDK: "0B5E48", AMBER: "E0A23E", RED: "D64545",
  BG: "F6F4EF", CARD: "FFFFFF", INK: "23302C", BODY: "44524D", MUTE: "8A938F",
  CREAM: "F3EFE7", LIGHTTEAL: "CFE6DD", TEALTINT: "E7F2EE", REDTINT: "F7ECEA",
  AMBERTINT: "FBF1DF", DARKRED: "B5483B",
};
const shadow = () => ({ type: "outer", color: "000000", blur: 8, offset: 3, angle: 90, opacity: 0.10 });

function card(slide, x, y, w, h, fill) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x, y, w, h, rectRadius: 0.10, fill: { color: fill || P.CARD },
    line: { type: "none" }, shadow: shadow(),
  });
}
function circNum(slide, x, y, d, color, label) {
  slide.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color }, line: { type: "none" } });
  slide.addText(label, {
    x, y, w: d, h: d, align: "center", valign: "middle",
    fontSize: Math.round(d * 23), bold: true, color: "FFFFFF", fontFace: FONT, margin: 0,
  });
}
function dot(slide, x, y, color) {
  slide.addShape(pres.shapes.OVAL, { x, y, w: 0.16, h: 0.16, fill: { color }, line: { type: "none" } });
}
function arrowR(slide, x, y, w) {
  slide.addShape(pres.shapes.LINE, { x, y, w, h: 0, line: { color: "AEBAB4", width: 2.25, endArrowType: "triangle" } });
}
function titleText(slide, txt, color) {
  slide.addText(txt, { x: ML, y: 0.48, w: UW, h: 0.8, fontSize: 29, bold: true, color: color || P.INK, fontFace: FONT, align: "left", margin: 0 });
}
function pageNum(slide, n) {
  slide.addText(n + " / 10", { x: W - 1.6, y: H - 0.5, w: 1.2, h: 0.3, fontSize: 10, color: P.MUTE, fontFace: FONT, align: "right", margin: 0 });
}

/* ───────── Slide 1 — Title (dark) ───────── */
let s = pres.addSlide();
s.background = { color: P.TEALDK };
s.addText("비전공자용 안내 자료", { x: 0.9, y: 1.45, w: 8, h: 0.4, fontSize: 15, color: P.LIGHTTEAL, fontFace: FONT, charSpacing: 2, margin: 0 });
s.addText([
  { text: "마이헬스케어 RAG,", options: { breakLine: true } },
  { text: "쉽게 이해하기" },
], { x: 0.88, y: 2.0, w: 11.5, h: 1.9, fontSize: 46, bold: true, color: P.CREAM, fontFace: FONT, lineSpacingMultiple: 1.05, margin: 0 });
s.addText("‘아는 척’으로 지어내지 않고 — 믿을 자료를 찾아 답하는 AI", { x: 0.9, y: 4.05, w: 11, h: 0.6, fontSize: 19, color: P.LIGHTTEAL, fontFace: FONT, margin: 0 });
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.9, y: 5.35, w: 8.1, h: 0.72, rectRadius: 0.36, fill: { color: P.TEAL }, line: { type: "none" } });
s.addText("찾아보고(Retrieval)   →   근거로만 답한다(Generation)", { x: 0.9, y: 5.35, w: 8.1, h: 0.72, fontSize: 15, bold: true, color: P.CREAM, fontFace: FONT, align: "center", valign: "middle", margin: 0 });

/* ───────── Slide 2 — 비유 ───────── */
s = pres.addSlide(); s.background = { color: P.BG };
titleText(s, "RAG가 뭔가요?");
s.addText("한마디로, ‘도서관 사서’ 같은 AI입니다.", { x: ML, y: 1.18, w: UW, h: 0.4, fontSize: 15, color: P.BODY, fontFace: FONT, margin: 0 });
{
  const cy = 1.95, ch = 3.35, cw = (UW - 0.6) / 2, xL = ML, xR = ML + cw + 0.6;
  card(s, xL, cy, cw, ch, P.REDTINT);
  s.addText("그냥 답하는 AI", { x: xL + 0.35, y: cy + 0.32, w: cw - 0.7, h: 0.5, fontSize: 18, bold: true, color: P.DARKRED, fontFace: FONT, margin: 0 });
  s.addText([
    { text: "모르면 그럴듯하게 지어냅니다.", options: { breakLine: true } },
    { text: "( = 환각 )", options: { breakLine: true } },
    { text: "출처가 없어 믿기 어렵습니다." },
  ], { x: xL + 0.35, y: cy + 1.05, w: cw - 0.7, h: 2.0, fontSize: 15, color: P.BODY, fontFace: FONT, lineSpacingMultiple: 1.25, margin: 0, valign: "top" });

  card(s, xR, cy, cw, ch, P.TEALTINT);
  s.addText("RAG — 우리 방식", { x: xR + 0.35, y: cy + 0.32, w: cw - 0.7, h: 0.5, fontSize: 18, bold: true, color: P.TEAL, fontFace: FONT, margin: 0 });
  s.addText([
    { text: "① 믿을 자료를 먼저 찾고", options: { breakLine: true } },
    { text: "② 그 근거로만 답하고", options: { breakLine: true } },
    { text: "③ 출처까지 보여줍니다." },
  ], { x: xR + 0.35, y: cy + 1.05, w: cw - 0.7, h: 2.0, fontSize: 15, color: P.BODY, fontFace: FONT, lineSpacingMultiple: 1.25, margin: 0, valign: "top" });
}
s.addText("사서가 책을 펼쳐 확인하고, 몇 페이지에서 봤는지까지 알려주는 것과 같아요.", { x: ML, y: 5.6, w: UW, h: 0.5, fontSize: 13, italic: true, color: P.MUTE, fontFace: FONT, margin: 0 });
pageNum(s, 2);

/* ───────── Slide 3 — 왜 필수 ───────── */
s = pres.addSlide(); s.background = { color: P.BG };
titleText(s, "왜 의료 서비스엔 RAG가 ‘필수’인가");
{
  const cy = 2.0, ch = 3.5, cw = (UW - 1.0) / 3, gap = 0.5;
  const items = [
    [P.TEAL, "1", "의료법 준수", "AI는 진단·처방을 할 수 없습니다. 정보 안내만 가능합니다."],
    [P.RED, "2", "안전", "틀린 의학 정보는 사람을 다치게 합니다. 추측은 금물입니다."],
    [P.TEAL, "3", "신뢰", "모든 답에 근거와 출처를 답니다. 못 믿을 답은 내지 않습니다."],
  ];
  items.forEach((it, i) => {
    const x = ML + i * (cw + gap);
    card(s, x, cy, cw, ch);
    circNum(s, x + 0.35, cy + 0.4, 0.62, it[0], it[1]);
    s.addText(it[2], { x: x + 0.35, y: cy + 1.25, w: cw - 0.7, h: 0.5, fontSize: 17, bold: true, color: P.INK, fontFace: FONT, margin: 0 });
    s.addText(it[3], { x: x + 0.35, y: cy + 1.85, w: cw - 0.7, h: 1.4, fontSize: 13.5, color: P.BODY, fontFace: FONT, lineSpacingMultiple: 1.2, margin: 0, valign: "top" });
  });
}
pageNum(s, 3);

/* ───────── Slide 4 — 2단계 개요 ───────── */
s = pres.addSlide(); s.background = { color: P.BG };
titleText(s, "전체 흐름은 딱 2단계");
{
  const cy = 1.95, ch = 2.9, cw = (UW - 1.1) / 2, xL = ML, xR = ML + cw + 1.1;
  card(s, xL, cy, cw, ch, P.TEALTINT);
  s.addText("1단계 · 준비 (평소)", { x: xL + 0.4, y: cy + 0.45, w: cw - 0.8, h: 0.5, fontSize: 19, bold: true, color: P.TEAL, fontFace: FONT, margin: 0 });
  s.addText("신뢰할 수 있는 자료로 ‘지식창고’를 미리 만들어 둡니다.", { x: xL + 0.4, y: cy + 1.2, w: cw - 0.8, h: 1.3, fontSize: 15, color: P.BODY, fontFace: FONT, lineSpacingMultiple: 1.25, margin: 0, valign: "top" });
  card(s, xR, cy, cw, ch, P.CARD);
  s.addText("2단계 · 응답 (실시간)", { x: xR + 0.4, y: cy + 0.45, w: cw - 0.8, h: 0.5, fontSize: 19, bold: true, color: P.INK, fontFace: FONT, margin: 0 });
  s.addText("질문이 오면 창고에서 근거를 찾아 안전하게 답합니다.", { x: xR + 0.4, y: cy + 1.2, w: cw - 0.8, h: 1.3, fontSize: 15, color: P.BODY, fontFace: FONT, lineSpacingMultiple: 1.25, margin: 0, valign: "top" });
  arrowR(s, xL + cw + 0.18, cy + ch / 2, 1.1 - 0.36);
  // 핵심 pill
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: (W - 7.6) / 2, y: 5.45, w: 7.6, h: 0.78, rectRadius: 0.39, fill: { color: P.TEALTINT }, line: { type: "none" } });
  s.addText("핵심 — 답하기 전에 반드시 ‘찾아본다’.", { x: (W - 7.6) / 2, y: 5.45, w: 7.6, h: 0.78, fontSize: 15.5, bold: true, color: P.TEAL, fontFace: FONT, align: "center", valign: "middle", margin: 0 });
}
pageNum(s, 4);

/* ───────── Slide 5 — 1단계 지식창고 ───────── */
s = pres.addSlide(); s.background = { color: P.BG };
titleText(s, "1단계 · ‘지식창고(KB)’ 만들기");
{
  const cy = 2.35, ch = 3.0, gap = 0.4, cw = (UW - 3 * gap) / 4, step = cw + gap;
  const items = [
    ["신뢰 출처 수집", "식약처·질병청 등 공식 자료"],
    ["잘게 자르기", "문단·표 단위로 나눔 (청킹)"],
    ["의미를 숫자로", "비슷한 글을 찾게 변환 (임베딩)"],
    ["지식창고에 색인", "검색 가능한 형태로 저장 (KB)"],
  ];
  items.forEach((it, i) => {
    const x = ML + i * step;
    card(s, x, cy, cw, ch);
    circNum(s, x + 0.28, cy + 0.32, 0.56, P.TEAL, String(i + 1));
    s.addText(it[0], { x: x + 0.26, y: cy + 1.05, w: cw - 0.5, h: 0.5, fontSize: 14.5, bold: true, color: P.INK, fontFace: FONT, margin: 0 });
    s.addText(it[1], { x: x + 0.26, y: cy + 1.6, w: cw - 0.5, h: 1.2, fontSize: 11.5, color: P.BODY, fontFace: FONT, lineSpacingMultiple: 1.18, margin: 0, valign: "top" });
    if (i < 3) arrowR(s, x + cw + 0.06, cy + ch / 2, gap - 0.12);
  });
}
pageNum(s, 5);

/* ───────── Slide 6 — 2단계 (1/2) ───────── */
s = pres.addSlide(); s.background = { color: P.BG };
titleText(s, "2단계 · 질문이 오면 (1/2) : 찾기까지");
{
  const cy = 1.9, ch = 1.95, cw = (UW - 0.6) / 2, xL = ML, xR = ML + cw + 0.6;
  card(s, xL, cy, cw, ch);
  s.addText("① 질문 이해·분류", { x: xL + 0.35, y: cy + 0.35, w: cw - 0.7, h: 0.5, fontSize: 16.5, bold: true, color: P.INK, fontFace: FONT, margin: 0 });
  s.addText("응급인가? 약 질문인가? 위험도는 어느 정도인가?", { x: xL + 0.35, y: cy + 1.0, w: cw - 0.7, h: 0.8, fontSize: 13.5, color: P.BODY, fontFace: FONT, margin: 0, valign: "top" });
  card(s, xR, cy, cw, ch);
  s.addText("② 지식창고 검색", { x: xR + 0.35, y: cy + 0.35, w: cw - 0.7, h: 0.5, fontSize: 16.5, bold: true, color: P.INK, fontFace: FONT, margin: 0 });
  s.addText("뜻이 비슷한 글 + 같은 단어가 있는 글을 동시에 (하이브리드)", { x: xR + 0.35, y: cy + 1.0, w: cw - 0.7, h: 0.8, fontSize: 13.5, color: P.BODY, fontFace: FONT, lineSpacingMultiple: 1.15, margin: 0, valign: "top" });

  const gy = 4.15, gh = 2.35;
  card(s, ML, gy, UW, gh, P.TEALTINT);
  s.addText("③ 근거가 충분한가? — 안전 게이트", { x: ML + 0.45, y: gy + 0.32, w: UW - 0.9, h: 0.5, fontSize: 18, bold: true, color: P.TEAL, fontFace: FONT, margin: 0 });
  dot(s, ML + 0.5, gy + 1.18, P.TEAL);
  s.addText("충분하면  →  답변 단계로 진행", { x: ML + 0.8, y: gy + 1.02, w: UW - 1.3, h: 0.45, fontSize: 14.5, color: P.BODY, fontFace: FONT, margin: 0, valign: "middle" });
  dot(s, ML + 0.5, gy + 1.78, P.AMBER);
  s.addText("부족하면  →  ‘근거 부족’을 솔직히 알리고, 진료과·병원을 안내 (지어내지 않음)", { x: ML + 0.8, y: gy + 1.62, w: UW - 1.3, h: 0.45, fontSize: 14.5, color: P.BODY, fontFace: FONT, margin: 0, valign: "middle" });
}
pageNum(s, 6);

/* ───────── Slide 7 — 2단계 (2/2) ───────── */
s = pres.addSlide(); s.background = { color: P.BG };
titleText(s, "2단계 · 질문이 오면 (2/2) : 답하기까지");
{
  const cw = (UW - 0.6) / 2, ch = 2.25, gapx = 0.6, gapy = 0.4;
  const y1 = 1.9, y2 = y1 + ch + gapy, xL = ML, xR = ML + cw + gapx;
  const cells = [
    [xL, y1, P.CARD, "④ 검토 자료 묶기", "찾은 근거만 모읍니다 (8개 이내로 정리)."],
    [xR, y1, P.CARD, "⑤ AI가 답 작성", "이 근거만 사용하고, 문장마다 [출처]를 답니다."],
    [xL, y2, P.REDTINT, "⑥ 안전 검사 (가드레일)", "진단·처방·응급 오판이 있으면 → 다시 생성."],
    [xR, y2, P.TEALTINT, "⑦ 최종 답변 전달", "면책 문구 + (동의 시) 개인 맞춤 안내를 붙여 전달."],
  ];
  cells.forEach((c) => {
    card(s, c[0], c[1], cw, ch, c[2]);
    s.addText(c[3], { x: c[0] + 0.35, y: c[1] + 0.35, w: cw - 0.7, h: 0.5, fontSize: 16.5, bold: true, color: P.INK, fontFace: FONT, margin: 0 });
    s.addText(c[4], { x: c[0] + 0.35, y: c[1] + 1.0, w: cw - 0.7, h: 0.9, fontSize: 13.5, color: P.BODY, fontFace: FONT, lineSpacingMultiple: 1.15, margin: 0, valign: "top" });
  });
}
pageNum(s, 7);

/* ───────── Slide 8 — 핵심 안전장치 3가지 ───────── */
s = pres.addSlide(); s.background = { color: P.BG };
titleText(s, "안전을 위해 특별히 더한 3가지");
{
  const cy = 2.0, ch = 3.5, cw = (UW - 1.0) / 3, gap = 0.5;
  const items = [
    [P.TEAL, "1", "근거 게이트", "근거가 약하면 멈추고 안내로 전환합니다. → 환각 차단"],
    [P.RED, "2", "가드레일", "완성된 답도 위험하면 폐기하고 다시 생성합니다."],
    [P.AMBER, "3", "개인정보 경계", "혈압 같은 원시 수치는 AI에 직접 넣지 않고 ‘주의·경고’ 라벨로만 다룹니다."],
  ];
  items.forEach((it, i) => {
    const x = ML + i * (cw + gap);
    card(s, x, cy, cw, ch);
    circNum(s, x + 0.35, cy + 0.4, 0.62, it[0], it[1]);
    s.addText(it[2], { x: x + 0.35, y: cy + 1.25, w: cw - 0.7, h: 0.5, fontSize: 17, bold: true, color: P.INK, fontFace: FONT, margin: 0 });
    s.addText(it[3], { x: x + 0.35, y: cy + 1.85, w: cw - 0.7, h: 1.5, fontSize: 13.5, color: P.BODY, fontFace: FONT, lineSpacingMultiple: 1.2, margin: 0, valign: "top" });
  });
}
pageNum(s, 8);

/* ───────── Slide 9 — 용어 풀이 ───────── */
s = pres.addSlide(); s.background = { color: P.BG };
titleText(s, "함께 보면 좋은 용어");
{
  const terms = [
    ["RAG", "찾아본 뒤(검색) 답을 만드는(생성) 방식"],
    ["청킹", "긴 문서를 검색하기 좋게 잘게 자르기"],
    ["임베딩·벡터", "글의 ‘의미’를 숫자로 바꿔 비슷한 글을 찾는 기술"],
    ["하이브리드 검색", "의미 검색 + 단어 검색을 함께 사용"],
    ["게이트", "근거가 충분한지 판정하는 관문"],
    ["가드레일", "완성된 답을 안전 기준으로 다시 검사"],
    ["환각", "AI가 근거 없이 그럴듯하게 지어내는 현상"],
    ["KB (지식창고)", "신뢰 자료를 모아둔 검색용 저장소"],
  ];
  const colW = (UW - 0.7) / 2, rowH = 1.18, y0 = 1.95;
  terms.forEach((t, i) => {
    const col = i < 4 ? 0 : 1, row = i % 4;
    const x = ML + col * (colW + 0.7), y = y0 + row * rowH;
    s.addText(t[0], { x, y, w: colW, h: 0.4, fontSize: 15, bold: true, color: P.TEAL, fontFace: FONT, margin: 0 });
    s.addText(t[1], { x, y: y + 0.42, w: colW, h: 0.6, fontSize: 12.5, color: P.BODY, fontFace: FONT, lineSpacingMultiple: 1.1, margin: 0, valign: "top" });
  });
}
pageNum(s, 9);

/* ───────── Slide 10 — Closing (dark) ───────── */
s = pres.addSlide(); s.background = { color: P.TEALDK };
s.addText([
  { text: "근거가 없으면,", options: { breakLine: true } },
  { text: "답하지 않습니다." },
], { x: 0.9, y: 2.1, w: 11.5, h: 2.0, fontSize: 44, bold: true, color: P.CREAM, fontFace: FONT, lineSpacingMultiple: 1.08, margin: 0 });
s.addText("RAG = 찾아보고 · 근거 있을 때만 · 출처를 달아 답하고 · 없으면 솔직히 물러서는 AI", { x: 0.92, y: 4.5, w: 11.2, h: 0.7, fontSize: 17, color: P.LIGHTTEAL, fontFace: FONT, margin: 0 });
s.addText("마이헬스케어", { x: 0.92, y: 6.35, w: 6, h: 0.4, fontSize: 14, bold: true, color: "9FC9BC", fontFace: FONT, charSpacing: 1, margin: 0 });

const out = path.join(__dirname, "..", "마이헬스케어-RAG-쉬운설명.pptx");
pres.writeFile({ fileName: out }).then((f) => console.log("WROTE:", out)).catch((e) => { console.error(e); process.exit(1); });
