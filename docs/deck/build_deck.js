// 투자용 피치덱 — 근거 기반 개인화 의료정보 AI
// pptxgenjs (전역). 아이콘은 도형으로 직접 렌더(외부 의존 최소화).
const pptxgen = require("pptxgenjs");

const P = {
  ink:   "0B2E36",   // 딥 틸-네이비 (다크 배경)
  ink2:  "123E48",
  teal:  "0E7C86",   // 메인 틸
  teal2: "12A4A4",
  mint:  "27D3B5",   // 액센트 민트
  coral: "F25C54",   // 안전/응급 강조
  amber: "F2A65A",
  paper: "F4F7F6",   // 라이트 배경
  card:  "FFFFFF",
  line:  "D9E5E3",
  gray:  "5C6B6A",
  dark:  "0B2E36",
  white: "FFFFFF",
};
const HF = "Malgun Gothic";  // 헤더
const BF = "Malgun Gothic";  // 본문

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
pres.author = "medical-rag-service";
pres.title = "근거 기반 개인화 의료정보 AI — 투자 제안";
const W = 13.33, H = 7.5, M = 0.6;

const sh = () => ({ type: "outer", color: "0B2E36", blur: 9, offset: 3, angle: 135, opacity: 0.16 });
const shUp = () => ({ type: "outer", color: "000000", blur: 6, offset: 2, angle: 270, opacity: 0.12 });

function pageNum(slide, n) {
  slide.addText(String(n).padStart(2, "0"), {
    x: W - 1.0, y: H - 0.5, w: 0.6, h: 0.3, align: "right",
    fontFace: BF, fontSize: 9, color: P.gray,
  });
}
function kicker(slide, text, color) {
  slide.addShape(pres.shapes.RECTANGLE, { x: M, y: 0.62, w: 0.16, h: 0.34, fill: { color: color || P.teal }, line: { type: "none" } });
  slide.addText(text, { x: M + 0.28, y: 0.6, w: 9, h: 0.4, fontFace: HF, fontSize: 13, bold: true, color: color || P.teal, charSpacing: 2, margin: 0, valign: "middle" });
}
function title(slide, text, color) {
  slide.addText(text, { x: M, y: 1.02, w: W - 2 * M, h: 0.9, fontFace: HF, fontSize: 30, bold: true, color: color || P.ink, margin: 0 });
}
function chip(slide, x, y, w, txt, fill, tcolor) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h: 0.42, rectRadius: 0.21, fill: { color: fill }, line: { type: "none" } });
  slide.addText(txt, { x, y, w, h: 0.42, align: "center", valign: "middle", fontFace: BF, fontSize: 11.5, bold: true, color: tcolor, margin: 0 });
}

// ───────────────────────── 1. TITLE (dark) ─────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: P.ink };
  // 모티프: 우측 큰 동심원
  s.addShape(pres.shapes.OVAL, { x: 9.4, y: -1.6, w: 6.2, h: 6.2, fill: { color: P.ink2 }, line: { type: "none" } });
  s.addShape(pres.shapes.OVAL, { x: 10.7, y: 0.0, w: 3.8, h: 3.8, fill: { color: P.teal }, line: { type: "none" } });
  s.addShape(pres.shapes.OVAL, { x: 11.7, y: 1.1, w: 1.8, h: 1.8, fill: { color: P.mint }, line: { type: "none" } });
  // 작은 의료 십자
  s.addShape(pres.shapes.RECTANGLE, { x: 12.42, y: 1.62, w: 0.38, h: 0.12, fill: { color: P.ink }, line: { type: "none" } });
  s.addShape(pres.shapes.RECTANGLE, { x: 12.55, y: 1.49, w: 0.12, h: 0.38, fill: { color: P.ink }, line: { type: "none" } });

  s.addText("MEDICAL RAG · 투자 제안", { x: M, y: 1.4, w: 8, h: 0.4, fontFace: HF, fontSize: 13, bold: true, color: P.mint, charSpacing: 3, margin: 0 });
  s.addText("근거 기반 개인화\n의료정보 AI", { x: M, y: 1.95, w: 9, h: 2.0, fontFace: HF, fontSize: 46, bold: true, color: P.white, lineSpacingMultiple: 1.0, margin: 0 });
  s.addText("“출처 없는 의학적 주장은 한 문장도 내보내지 않는다.”", { x: M, y: 4.15, w: 9.5, h: 0.5, fontFace: BF, fontSize: 17, italic: true, color: P.teal2, margin: 0 });
  s.addText("한국어 의료 질의응답 RAG · 의료법 준수 아키텍처 · 인용 검증 · 안전 게이트 · 개인화 컨텍스트 확장", { x: M, y: 4.85, w: 10.5, h: 0.5, fontFace: BF, fontSize: 13, color: P.line, margin: 0 });
  // 하단 지표 스트립
  const stats = [["56", "증상 커버"], ["15", "진료과"], ["19", "KB 출처"], ["100%", "안전 게이트"]];
  let sx = M;
  stats.forEach(([n, l]) => {
    s.addText(n, { x: sx, y: 5.7, w: 1.9, h: 0.6, fontFace: HF, fontSize: 30, bold: true, color: P.mint, margin: 0 });
    s.addText(l, { x: sx, y: 6.32, w: 1.9, h: 0.35, fontFace: BF, fontSize: 11, color: P.line, margin: 0 });
    sx += 2.25;
  });
}

// ───────────────────────── 2. PROBLEM ─────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: P.paper };
  kicker(s, "PROBLEM", P.coral);
  title(s, "범용 LLM은 의료 답변에 그대로 쓸 수 없다");
  const probs = [
    ["환각(hallucination)", "그럴듯하지만 틀린 의학 정보를 자신 있게 생성. 환자 위해로 직결.", P.coral],
    ["출처 불명", "근거를 “언급”할 뿐 검증되지 않음. 확률적 생성이라 추적 불가.", P.amber],
    ["의료법 리스크", "무면허 의료행위(진단·처방) 경계를 모델이 스스로 통제하지 못함.", P.teal],
    ["개인 맥락 부재", "사용자의 복용약·기저질환·환경을 모르는 일반론만 제공.", P.teal2],
  ];
  const cw = (W - 2 * M - 0.5) / 2, chh = 1.9;
  probs.forEach((p, i) => {
    const x = M + (i % 2) * (cw + 0.5), y = 2.15 + Math.floor(i / 2) * (chh + 0.35);
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: cw, h: chh, fill: { color: P.card }, line: { type: "none" }, shadow: sh() });
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: 0.12, h: chh, fill: { color: p[2] }, line: { type: "none" } });
    s.addText(p[0], { x: x + 0.4, y: y + 0.28, w: cw - 0.7, h: 0.5, fontFace: HF, fontSize: 19, bold: true, color: P.ink, margin: 0 });
    s.addText(p[1], { x: x + 0.4, y: y + 0.92, w: cw - 0.7, h: 0.85, fontFace: BF, fontSize: 14, color: P.gray, margin: 0, lineSpacingMultiple: 1.05 });
  });
  pageNum(s, 2);
}

// ───────────────────────── 3. SOLUTION ─────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: P.paper };
  kicker(s, "SOLUTION", P.teal);
  title(s, "정확성을 모델이 아니라 ‘맥락·근거·안전’로 만든다");
  s.addText("범용 LLM과 같은 모델을 쓰더라도, 검증된 지식베이스 인용을 강제하고 안전을 코드로 통제하면 결과 카테고리가 달라진다.", { x: M, y: 1.95, w: W - 2 * M, h: 0.5, fontFace: BF, fontSize: 14.5, color: P.gray, margin: 0 });
  const pillars = [
    ["인용 강제", "Evidence Pack 외 근거 사용 금지. 모든 의학적 주장에 [출처] 부착 후 문장 단위 인용 커버리지를 결정적으로 검증.", P.teal],
    ["안전 아키텍처", "진단·처방 금지, 응급 119 / 위기 109 게이트를 LLM이 아닌 규칙으로 강제. 안심 단정 금지, 보수 방향만 허용.", P.coral],
    ["개인화 컨텍스트", "증상·복용약·환경을 검색 필터와 규칙 판정으로 반영. 범용 LLM이 가질 수 없는 ‘내 상황’의 근거.", P.teal2],
  ];
  const cw = (W - 2 * M - 0.7) / 3;
  pillars.forEach((p, i) => {
    const x = M + i * (cw + 0.35), y = 2.7, hh = 3.4;
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: cw, h: hh, fill: { color: P.card }, line: { type: "none" }, shadow: sh() });
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: cw, h: 0.14, fill: { color: p[2] }, line: { type: "none" } });
    s.addShape(pres.shapes.OVAL, { x: x + 0.4, y: y + 0.45, w: 0.7, h: 0.7, fill: { color: p[2] }, line: { type: "none" } });
    s.addText(String(i + 1), { x: x + 0.4, y: y + 0.45, w: 0.7, h: 0.7, align: "center", valign: "middle", fontFace: HF, fontSize: 24, bold: true, color: P.white, margin: 0 });
    s.addText(p[0], { x: x + 0.4, y: y + 1.35, w: cw - 0.8, h: 0.5, fontFace: HF, fontSize: 19, bold: true, color: P.ink, margin: 0 });
    s.addText(p[1], { x: x + 0.4, y: y + 1.95, w: cw - 0.8, h: 1.3, fontFace: BF, fontSize: 13, color: P.gray, margin: 0, lineSpacingMultiple: 1.08 });
  });
  pageNum(s, 3);
}

// ───────────────────────── 4. TECH 1: 검색·생성 파이프라인 ─────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: P.paper };
  kicker(s, "기술 특징 1 / 2", P.teal);
  title(s, "검증된 검색·생성 파이프라인");
  // 좌: 설명
  const feats = [
    ["Hybrid Search + RRF", "pgvector 코사인(dense) + tsvector BM25(sparse)를 Reciprocal Rank Fusion으로 융합."],
    ["의료 안전 부스팅", "red-flag ×1.3, 한국 출처 ×1.15, evidence_topic 정렬로 무관 청크 차단."],
    ["Evidence Pack", "출처 우선순위(KDCA·DUR·지침 > 논문) 적용, 근거 0건이면 insufficient 모드."],
    ["인용 검증", "생성 후 문장 단위 claim 인용 커버리지를 검증, 미달 시 재생성."],
  ];
  let y = 2.15;
  feats.forEach((f) => {
    s.addShape(pres.shapes.OVAL, { x: M, y: y + 0.06, w: 0.26, h: 0.26, fill: { color: P.mint }, line: { type: "none" } });
    s.addText(f[0], { x: M + 0.45, y, w: 5.7, h: 0.4, fontFace: HF, fontSize: 16, bold: true, color: P.ink, margin: 0 });
    s.addText(f[1], { x: M + 0.45, y: y + 0.4, w: 5.9, h: 0.7, fontFace: BF, fontSize: 12.5, color: P.gray, margin: 0, lineSpacingMultiple: 1.04 });
    y += 1.18;
  });
  // 우: 파이프라인 흐름 카드
  const px = 7.4, pw = W - px - M;
  s.addShape(pres.shapes.RECTANGLE, { x: px, y: 2.05, w: pw, h: 4.55, fill: { color: P.ink }, line: { type: "none" }, shadow: sh() });
  s.addText("END-TO-END 파이프라인", { x: px + 0.4, y: 2.3, w: pw - 0.8, h: 0.4, fontFace: HF, fontSize: 13, bold: true, color: P.mint, charSpacing: 1, margin: 0 });
  const steps = ["PII 마스킹", "질문 분류", "안전 사전점검 (위기·응급 분기)", "출처 라우팅", "Hybrid 검색 + 부스팅", "Evidence Pack", "근거기반 생성", "인용 검증 · 가드레일", "리뷰 큐 · 감사 로그"];
  let sy = 2.85;
  steps.forEach((t, i) => {
    const hot = i === 2;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: px + 0.4, y: sy, w: pw - 0.8, h: 0.36, rectRadius: 0.06, fill: { color: hot ? P.coral : P.ink2 }, line: { color: hot ? P.coral : P.teal, width: 0.75 } });
    s.addText((i + 1) + ".  " + t, { x: px + 0.6, y: sy, w: pw - 1.0, h: 0.36, valign: "middle", fontFace: BF, fontSize: 11.5, bold: hot, color: P.white, margin: 0 });
    sy += 0.40;
  });
  pageNum(s, 4);
}

// ───────────────────────── 5. TECH 2: 안전·도달·측정 ─────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: P.paper };
  kicker(s, "기술 특징 2 / 2", P.coral);
  title(s, "안전 · 한국어 도달 · 측정 인프라");
  const rows = [
    ["결정적 안전 게이트", "응급 119 / 자살위기 109를 LLM을 거치지 않고 고정 템플릿으로 즉시 응답. 뇌졸중 구음장애·자살 완곡표현까지 분류.", P.coral],
    ["한국어 구어체 도달", "‘머리아파’→두통 처럼 증상 표현을 증상명·동의어(99그룹)·형태소로 매칭. 진료과(15개)까지 안내.", P.teal],
    ["측정 인프라 (골든셋)", "67케이스 오프라인 회귀 게이트. 안전 100% 필수로 CI 고정 — ‘측정 없는 개선 금지’.", P.teal2],
    ["데이터 플라이휠", "근거부족·미도달 질의를 수집 우선순위 큐로 환류. 사용자가 늘수록 KB가 수요에 맞게 두꺼워짐.", P.mint],
    ["감사 가능성", "모든 질의를 분류·근거품질·인용과 함께 기록. ‘왜 그렇게 답했는가’ 재현 가능 = B2B 진입권.", P.teal],
  ];
  let y = 2.05;
  const rw = W - 2 * M, rhh = 0.82;
  rows.forEach((r) => {
    s.addShape(pres.shapes.RECTANGLE, { x: M, y, w: rw, h: rhh, fill: { color: P.card }, line: { type: "none" }, shadow: sh() });
    s.addShape(pres.shapes.OVAL, { x: M + 0.22, y: y + 0.2, w: 0.42, h: 0.42, fill: { color: r[2] }, line: { type: "none" } });
    s.addText(r[0], { x: M + 0.95, y: y + 0.1, w: 3.5, h: rhh - 0.2, valign: "middle", fontFace: HF, fontSize: 15, bold: true, color: P.ink, margin: 0 });
    s.addText(r[1], { x: M + 4.55, y: y + 0.08, w: rw - 4.8, h: rhh - 0.14, valign: "middle", fontFace: BF, fontSize: 12.5, color: P.gray, margin: 0, lineSpacingMultiple: 1.02 });
    y += rhh + 0.15;
  });
  pageNum(s, 5);
}

// ───────────────────────── 6. 의학 커버리지 ─────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: P.paper };
  kicker(s, "의학 커버리지", P.teal);
  title(s, "지금 다루는 의학 범위");
  // 상단 stat callouts
  const stats = [["56", "증상", P.teal], ["15", "진료과", P.teal2], ["19", "KB 출처", P.mint], ["99", "동의어 그룹", P.amber]];
  const sw = (W - 2 * M - 1.05) / 4;
  stats.forEach((st, i) => {
    const x = M + i * (sw + 0.35);
    s.addShape(pres.shapes.RECTANGLE, { x, y: 1.95, w: sw, h: 1.2, fill: { color: P.card }, line: { type: "none" }, shadow: sh() });
    s.addShape(pres.shapes.RECTANGLE, { x, y: 1.95, w: sw, h: 0.1, fill: { color: st[2] }, line: { type: "none" } });
    s.addText(st[0], { x, y: 2.12, w: sw, h: 0.7, align: "center", fontFace: HF, fontSize: 38, bold: true, color: st[2], margin: 0 });
    s.addText(st[1], { x, y: 2.82, w: sw, h: 0.3, align: "center", fontFace: BF, fontSize: 12, color: P.gray, margin: 0 });
  });
  // 진료과 칩
  s.addText("진료과 (15)", { x: M, y: 3.45, w: 6, h: 0.35, fontFace: HF, fontSize: 13, bold: true, color: P.ink, margin: 0 });
  const depts = ["내과", "신경과", "정형외과", "피부과", "이비인후과", "비뇨의학과", "안과", "산부인과", "정신건강의학과", "가정의학과", "재활의학과", "소아청소년과", "치과", "외과", "응급의학과"];
  let cx = M, cy = 3.85;
  depts.forEach((d) => {
    const w = 0.45 + d.length * 0.21;
    if (cx + w > W - M) { cx = M; cy += 0.55; }
    chip(s, cx, cy, w, d, P.ink, P.white);
    cx += w + 0.2;
  });
  // KB 출처 영역 박스
  const bx = M, by = 5.5, bw = W - 2 * M;
  s.addShape(pres.shapes.RECTANGLE, { x: bx, y: by, w: bw, h: 1.4, fill: { color: P.ink }, line: { type: "none" }, shadow: sh() });
  s.addText("지식베이스 출처 (공공누리·퍼블릭도메인)", { x: bx + 0.4, y: by + 0.22, w: bw - 0.8, h: 0.35, fontFace: HF, fontSize: 13, bold: true, color: P.mint, margin: 0 });
  const kb = "질병관리청 국가건강정보포털 · 감염병 · 예방접종(NIP)  |  식약처 의약품안전(DUR·e약은요)  |  심평원(HIRA)  |  응급의료포털(NEMC)  |  공인 참조범위(혈압·혈당·SpO2·공기질)  |  생애주기(암·정신·임신·노인·만성질환)  |  의료이용 안내(진료과·검진·건강보험)  |  중독·소아 응급  |  법령";
  s.addText(kb, { x: bx + 0.4, y: by + 0.58, w: bw - 0.8, h: 0.78, fontFace: BF, fontSize: 11.5, color: P.line, margin: 0, lineSpacingMultiple: 1.1 });
  pageNum(s, 6);
}

// ───────────────────────── 7. 측정 성과 ─────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: P.paper };
  kicker(s, "측정 성과", P.teal);
  title(s, "골든셋 오프라인 평가 — 전 차원 100%");
  s.addChart(pres.charts.BAR, [{
    name: "통과율", labels: ["증상 도달", "진료과 일치", "구어체 도달", "안전 게이트", "intent 분류"], values: [100, 100, 100, 100, 100],
  }], {
    x: M, y: 2.1, w: 6.6, h: 4.4, barDir: "col",
    chartColors: [P.teal, P.teal2, P.mint, P.coral, P.amber],
    chartArea: { fill: { color: P.paper } }, plotArea: { fill: { color: P.paper } },
    valAxisMinVal: 0, valAxisMaxVal: 100, valAxisMajorUnit: 25,
    catAxisLabelColor: P.ink, catAxisLabelFontSize: 11, catAxisLabelFontBold: true,
    valAxisLabelColor: P.gray, valAxisLabelFontSize: 9,
    valGridLine: { color: P.line, size: 0.5 }, catGridLine: { style: "none" },
    showValue: true, dataLabelPosition: "outEnd", dataLabelColor: P.ink, dataLabelFontBold: true, dataLabelFontSize: 12, dataLabelFormatCode: '0"%"',
    showLegend: false, showTitle: false,
  });
  // 우: before/after 케이스
  const bx = 7.5, bw = W - bx - M;
  s.addText("케이스: “나 머리아파”", { x: bx, y: 2.05, w: bw, h: 0.4, fontFace: HF, fontSize: 16, bold: true, color: P.ink, margin: 0 });
  // before
  s.addShape(pres.shapes.RECTANGLE, { x: bx, y: 2.6, w: bw, h: 1.55, fill: { color: P.card }, line: { type: "none" }, shadow: sh() });
  s.addShape(pres.shapes.RECTANGLE, { x: bx, y: 2.6, w: 0.12, h: 1.55, fill: { color: P.coral }, line: { type: "none" } });
  s.addText("BEFORE", { x: bx + 0.35, y: 2.75, w: bw - 0.6, h: 0.3, fontFace: HF, fontSize: 11, bold: true, color: P.coral, charSpacing: 2, margin: 0 });
  s.addText([
    { text: "증상 매칭 실패 → 두통 미도달", options: { breakLine: true, bullet: true } },
    { text: "red-flag 부스트·진료과 안내 미발동", options: { breakLine: true, bullet: true } },
    { text: "근거 부족 응답으로 종료", options: { bullet: true } },
  ], { x: bx + 0.4, y: 3.1, w: bw - 0.7, h: 1.0, fontFace: BF, fontSize: 12, color: P.gray, margin: 0, paraSpaceAfter: 3 });
  // after
  s.addShape(pres.shapes.RECTANGLE, { x: bx, y: 4.35, w: bw, h: 1.75, fill: { color: P.card }, line: { type: "none" }, shadow: sh() });
  s.addShape(pres.shapes.RECTANGLE, { x: bx, y: 4.35, w: 0.12, h: 1.75, fill: { color: P.mint }, line: { type: "none" } });
  s.addText("AFTER", { x: bx + 0.35, y: 4.5, w: bw - 0.6, h: 0.3, fontFace: HF, fontSize: 11, bold: true, color: P.teal, charSpacing: 2, margin: 0 });
  s.addText([
    { text: "두통 도달 → 신경과 진료과 안내", options: { breakLine: true, bullet: true } },
    { text: "red-flag·문진 체크리스트 발동", options: { breakLine: true, bullet: true } },
    { text: "구어체·띄어쓰기 변형까지 도달", options: { bullet: true } },
  ], { x: bx + 0.4, y: 4.85, w: bw - 0.7, h: 1.15, fontFace: BF, fontSize: 12, color: P.ink, margin: 0, paraSpaceAfter: 3 });
  pageNum(s, 7);
}

// ───────────────────────── 8. 해자 ─────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: P.paper };
  kicker(s, "MOAT", P.teal);
  title(s, "범용 LLM이 구조적으로 따라올 수 없는 것");
  const moats = [
    ["규제 레일", "한국 의료 마이데이터·DUR·공공 KB는 국내 법인·심사를 요구. 글로벌 단일 제품 논리와 충돌."],
    ["인용 ‘보장’", "확률적 언급이 아니라 인용 없는 의학 claim은 출고 차단. 범용 챗봇 UX와 상충해 채택 어려움."],
    ["컴플라이언스 아키텍처", "의료법 경계를 프롬프트가 아닌 코드 게이트로 통제. 시장별 법적 책임 인수를 빅테크는 회피."],
    ["감사 가능성", "답변 재현·추적 가능 = 보험사·검진기관·지자체 조달의 전제. 폐쇄형 API로는 불가."],
    ["프라이버시 설계", "원시 의료데이터를 외부 모델에 그대로 넘기지 않는 신뢰 포지션. 빅테크의 데이터 흡수 모델과 반대."],
    ["데이터 플라이휠", "한국 사용자의 실제 질문에 최적화되는 운영 해자. 모델 세대교체로 무력화되지 않음."],
  ];
  const cw = (W - 2 * M - 0.7) / 3, chh = 1.95;
  moats.forEach((m, i) => {
    const x = M + (i % 3) * (cw + 0.35), y = 2.15 + Math.floor(i / 3) * (chh + 0.3);
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: cw, h: chh, fill: { color: P.card }, line: { type: "none" }, shadow: sh() });
    s.addText(String(i + 1).padStart(2, "0"), { x: x + 0.35, y: y + 0.25, w: 1.2, h: 0.5, fontFace: HF, fontSize: 22, bold: true, color: P.mint, margin: 0 });
    s.addText(m[0], { x: x + 0.35, y: y + 0.78, w: cw - 0.7, h: 0.45, fontFace: HF, fontSize: 15.5, bold: true, color: P.ink, margin: 0 });
    s.addText(m[1], { x: x + 0.35, y: y + 1.22, w: cw - 0.65, h: 0.65, fontFace: BF, fontSize: 11.5, color: P.gray, margin: 0, lineSpacingMultiple: 1.04 });
  });
  pageNum(s, 8);
}

// ───────────────────────── 9. 데이터 플라이휠 ─────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: P.paper };
  kicker(s, "FLYWHEEL", P.teal);
  title(s, "평가가 수집을 견인하는 데이터 플라이휠");
  s.addText("사용자 질문이 늘수록 ‘무엇이 부족한지’가 데이터로 쌓이고, 그 신호가 다음 커버리지 확장을 자동으로 정한다.", { x: M, y: 1.95, w: W - 2 * M, h: 0.5, fontFace: BF, fontSize: 14.5, color: P.gray, margin: 0 });
  const nodes = [
    ["질의 · 응답", "rag_queries 감사 로그", P.teal],
    ["갭 분석", "근거부족·미도달 질의 집계", P.coral],
    ["수요 큐", "커버리지 확장 우선순위 산출", P.amber],
    ["KB · 증상 확장", "수요 기반 큐레이션 수집", P.mint],
    ["골든셋 회귀", "개선을 수치로 검증", P.teal2],
  ];
  const n = nodes.length, gap = 0.5;
  const cw = (W - 2 * M - gap * (n - 1)) / n, y = 2.95, hh = 2.4;
  nodes.forEach((nd, i) => {
    const x = M + i * (cw + gap);
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: cw, h: hh, fill: { color: P.card }, line: { type: "none" }, shadow: sh() });
    s.addShape(pres.shapes.OVAL, { x: x + cw / 2 - 0.4, y: y + 0.35, w: 0.8, h: 0.8, fill: { color: nd[2] }, line: { type: "none" } });
    s.addText(String(i + 1), { x: x + cw / 2 - 0.4, y: y + 0.35, w: 0.8, h: 0.8, align: "center", valign: "middle", fontFace: HF, fontSize: 26, bold: true, color: P.white, margin: 0 });
    s.addText(nd[0], { x: x + 0.1, y: y + 1.32, w: cw - 0.2, h: 0.4, align: "center", fontFace: HF, fontSize: 14, bold: true, color: P.ink, margin: 0 });
    s.addText(nd[1], { x: x + 0.1, y: y + 1.74, w: cw - 0.2, h: 0.6, align: "center", fontFace: BF, fontSize: 10.5, color: P.gray, margin: 0, lineSpacingMultiple: 1.0 });
    if (i < n - 1) s.addText("→", { x: x + cw + 0.04, y: y + hh / 2 - 0.35, w: gap - 0.08, h: 0.7, align: "center", valign: "middle", fontFace: HF, fontSize: 22, bold: true, color: P.teal2, margin: 0 });
  });
  // 순환 화살표 라벨
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: M, y: 5.7, w: W - 2 * M, h: 0.7, rectRadius: 0.1, fill: { color: P.ink }, line: { type: "none" } });
  s.addText("↻  순환: 5 → 1  골든셋 통과로 개선이 확인되면 다시 운영 데이터로 — 모델 교체와 무관하게 누적되는 운영 해자", { x: M + 0.4, y: 5.7, w: W - 2 * M - 0.8, h: 0.7, valign: "middle", fontFace: BF, fontSize: 13, bold: true, color: P.mint, margin: 0 });
  pageNum(s, 9);
}

// ───────────────────────── 10. 로드맵 / 해결할 문제 ─────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: P.paper };
  kicker(s, "ROADMAP", P.teal);
  title(s, "어떻게 발전해 어떤 문제를 풀 것인가");
  const phases = [
    ["단기 (0–6개월)", "답변 품질 본격화", ["Kiwi 형태소로 도달률 추가 상향", "멀티턴 대화 문맥화", "학습형 리랭커 + 골든셋 250 확장", "임상 검수 리뷰보드"], P.teal],
    ["중기 (6–12개월)", "개인화 — 진짜 차별화", ["생체신호·PHR·집안 공기질 융합", "복용약 × DUR 교차 안내", "규칙 엔진이 해석, LLM은 서술([R#])", "동의·프라이버시 아키텍처"], P.coral],
    ["장기 (12개월+)", "확장 — 시장·규모", ["SaMD(의료기기) 경계 설계·인증 대비", "글로벌: 한국 → 일본 → 영어권", "B2B(검진·보험·지자체) — 감사 기반", "다국어 임베딩·교차언어 검색"], P.teal2],
  ];
  const cw = (W - 2 * M - 0.7) / 3;
  phases.forEach((p, i) => {
    const x = M + i * (cw + 0.35), y = 2.15, hh = 4.45;
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: cw, h: hh, fill: { color: P.card }, line: { type: "none" }, shadow: sh() });
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: cw, h: 0.95, fill: { color: p[3] }, line: { type: "none" } });
    s.addText(p[0], { x: x + 0.35, y: y + 0.16, w: cw - 0.7, h: 0.35, fontFace: HF, fontSize: 14, bold: true, color: P.white, margin: 0 });
    s.addText(p[1], { x: x + 0.35, y: y + 0.5, w: cw - 0.7, h: 0.4, fontFace: HF, fontSize: 16.5, bold: true, color: P.white, margin: 0 });
    s.addText(p[2].map((t) => ({ text: t, options: { bullet: { code: "2022" }, breakLine: true, paraSpaceAfter: 8 } })), { x: x + 0.4, y: y + 1.2, w: cw - 0.75, h: hh - 1.4, fontFace: BF, fontSize: 13, color: P.ink, margin: 0, lineSpacingMultiple: 1.05 });
  });
  pageNum(s, 10);
}

// ───────────────────────── 11. 시장·규제 포지셔닝 ─────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: P.paper };
  kicker(s, "POSITIONING", P.teal);
  title(s, "웰니스(비의료기기) 포지션 + 규제 전략");
  // 좌: 허용/금지
  const okx = M, okw = 5.9;
  s.addShape(pres.shapes.RECTANGLE, { x: okx, y: 2.1, w: okw, h: 4.4, fill: { color: P.card }, line: { type: "none" }, shadow: sh() });
  s.addShape(pres.shapes.RECTANGLE, { x: okx, y: 2.1, w: okw, h: 0.6, fill: { color: P.teal }, line: { type: "none" } });
  s.addText("허용 — 정보 제공", { x: okx + 0.35, y: 2.1, w: okw - 0.7, h: 0.6, valign: "middle", fontFace: HF, fontSize: 15, bold: true, color: P.white, margin: 0 });
  s.addText([
    "공인 출처 인용 건강정보",
    "측정값의 공인 기준 범위 ‘대조 표시’",
    "DUR 등재 ‘사실’ + 상담 권유",
    "응급 의심 시 119 안내",
    "진료과 · 의료 이용 내비게이션",
  ].map((t) => ({ text: t, options: { bullet: { code: "2713" }, breakLine: true, paraSpaceAfter: 7, color: P.ink } })), { x: okx + 0.4, y: 2.9, w: okw - 0.8, h: 3.4, fontFace: BF, fontSize: 13.5, margin: 0 });
  // 우: 금지
  const ngx = okx + okw + 0.4, ngw = 5.9;
  s.addShape(pres.shapes.RECTANGLE, { x: ngx, y: 2.1, w: ngw, h: 4.4, fill: { color: P.card }, line: { type: "none" }, shadow: sh() });
  s.addShape(pres.shapes.RECTANGLE, { x: ngx, y: 2.1, w: ngw, h: 0.6, fill: { color: P.coral }, line: { type: "none" } });
  s.addText("금지 — 의료행위", { x: ngx + 0.35, y: 2.1, w: ngw - 0.7, h: 0.6, valign: "middle", fontFace: HF, fontSize: 15, bold: true, color: P.white, margin: 0 });
  s.addText([
    "특정 질병 진단 · 병명 단정",
    "약 복용 · 용량 지시/변경",
    "자체 알고리즘 위험도 점수/트리아지",
    "‘응급 아님’ 안심 단정",
    "치료효과 보장",
  ].map((t) => ({ text: t, options: { bullet: { code: "2715" }, breakLine: true, paraSpaceAfter: 7, color: P.ink } })), { x: ngx + 0.4, y: 2.9, w: ngw - 0.8, h: 3.4, fontFace: BF, fontSize: 13.5, margin: 0 });
  // 하단 진출 순서
  s.addText([
    { text: "글로벌 진출 순서:  ", options: { bold: true, color: P.teal } },
    { text: "한국(레일·KB 보유) → 일본(비해당 기준 명문화) → 영어권(PD 콘텐츠 파일럿) → EU(규제 정비 후)", options: { color: P.gray } },
  ], { x: M, y: 6.7, w: W - 2 * M, h: 0.5, fontFace: BF, fontSize: 12.5, margin: 0 });
  pageNum(s, 11);
}

// ───────────────────────── 12. CLOSING (dark) ─────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: P.ink };
  s.addShape(pres.shapes.OVAL, { x: -1.8, y: 3.4, w: 6.2, h: 6.2, fill: { color: P.ink2 }, line: { type: "none" } });
  s.addShape(pres.shapes.OVAL, { x: -0.5, y: 4.6, w: 3.2, h: 3.2, fill: { color: P.teal }, line: { type: "none" } });
  s.addText("우리가 푸는 문제", { x: M, y: 1.3, w: 9, h: 0.4, fontFace: HF, fontSize: 14, bold: true, color: P.mint, charSpacing: 3, margin: 0 });
  s.addText("의료 정보의 비대칭을\n안전하게 좁힌다", { x: M, y: 1.85, w: 11, h: 1.7, fontFace: HF, fontSize: 38, bold: true, color: P.white, lineSpacingMultiple: 1.0, margin: 0 });
  s.addText("“진단 대신 길 안내” — 환자가 가장 먼저 만나는, 출처가 보장되고 의료법을 지키는 1차 건강 안내. 그리고 개인 데이터가 더해질수록 범용 LLM이 줄 수 없는 ‘내 상황의 근거’로 진화한다.", { x: M, y: 3.7, w: 10.6, h: 1.2, fontFace: BF, fontSize: 16, color: P.line, margin: 0, lineSpacingMultiple: 1.12 });
  // Ask 칩
  const asks = [["측정된 기반", "56증상·100% 안전게이트·감사 가능"], ["분명한 해자", "규제 레일 + 운영 데이터 플라이휠"], ["확장 경로", "개인화 → SaMD → 글로벌"]];
  let ax = M;
  asks.forEach((a) => {
    const w = 3.7;
    s.addShape(pres.shapes.RECTANGLE, { x: ax, y: 5.35, w, h: 1.25, fill: { color: P.ink2 }, line: { color: P.teal, width: 1 } });
    s.addText(a[0], { x: ax + 0.3, y: 5.5, w: w - 0.5, h: 0.4, fontFace: HF, fontSize: 15, bold: true, color: P.mint, margin: 0 });
    s.addText(a[1], { x: ax + 0.3, y: 5.92, w: w - 0.5, h: 0.6, fontFace: BF, fontSize: 11.5, color: P.line, margin: 0, lineSpacingMultiple: 1.04 });
    ax += w + 0.35;
  });
}

pres.writeFile({ fileName: "docs/deck/medical-rag-investor-deck.pptx" }).then((f) => console.log("WROTE", f));
