// 4층 교차신호 + 5층 환경×건강 — 화면 흐름·시나리오 → Word.
const fs = require("fs");
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  AlignmentType, HeadingLevel, BorderStyle, WidthType, ShadingType, PageBreak, Footer, PageNumber } = require("docx");
const FONT="Malgun Gothic", CW=9360, Q="DCE6F2", A="F1F1F1";
const bd={style:BorderStyle.SINGLE,size:1,color:"CCCCCC"}; const bds={top:bd,bottom:bd,left:bd,right:bd};
const t=(x,o={})=>new TextRun({text:x,font:FONT,...o});
const h1=(x)=>new Paragraph({heading:HeadingLevel.HEADING_1,children:[t(x,{bold:true})]});
const p=(x,o={})=>new Paragraph({spacing:{after:100,...(o.sp||{})},children:[t(x,o.r||{})]});
const sc=(x)=>new Paragraph({spacing:{before:220,after:40},children:[t(x,{bold:true,size:23,color:"1F4E79"})]});
const situ=(x)=>new Paragraph({spacing:{before:120,after:20},children:[t("상황  ",{bold:true,size:18,color:"B06A00"}),t(x,{size:18,italics:true,color:"8a6d3b"})]});
const qL=(x)=>new Paragraph({shading:{type:ShadingType.CLEAR,fill:Q},spacing:{before:60,after:0},border:{left:{style:BorderStyle.SINGLE,size:22,color:"2E5496",space:8}},children:[t("사용자   ",{bold:true,color:"1F4E79",size:19}),t(x,{size:20})]});
const aL=(x,note)=>{const o=[new Paragraph({shading:{type:ShadingType.CLEAR,fill:A},spacing:{before:0,after:note?0:30},border:{left:{style:BorderStyle.SINGLE,size:22,color:"548235",space:8}},children:[t("주치의   ",{bold:true,color:"2E5d27",size:19}),t(x,{size:20})]})];if(note)o.push(new Paragraph({spacing:{before:18,after:30},indent:{left:240},children:[t("→ "+note,{italics:true,size:16,color:"8a8a8a"})]}));return o;};
function flow(steps){return new Table({width:{size:CW,type:WidthType.DXA},columnWidths:steps.map(()=>Math.floor(CW/steps.length)),rows:[new TableRow({children:steps.map((s)=>new TableCell({borders:bds,shading:{fill:"EAF1E6",type:ShadingType.CLEAR},margins:{top:60,bottom:60,left:70,right:70},children:s.split("\n").map((l,i)=>new Paragraph({alignment:AlignmentType.CENTER,spacing:{after:0},children:[t(l,i===0?{bold:true,size:16}:{size:14,color:"5a6b7b"})]}))}))})]})}

const doc=new Document({
  styles:{default:{document:{run:{font:FONT,size:20}}},paragraphStyles:[{id:"Heading1",name:"Heading 1",basedOn:"Normal",next:"Normal",quickFormat:true,run:{size:27,bold:true,font:FONT,color:"1F4E79"},paragraph:{spacing:{before:260,after:130},outlineLevel:0}}]},
  sections:[{
    properties:{page:{size:{width:12240,height:15840},margin:{top:1440,right:1440,bottom:1440,left:1440}}},
    footers:{default:new Footer({children:[new Paragraph({alignment:AlignmentType.CENTER,children:[t("4·5층 상세 · ",{size:16,color:"888888"}),new TextRun({children:[PageNumber.CURRENT],font:FONT,size:16,color:"888888"})]})]})},
    children:[
      new Paragraph({spacing:{before:900,after:0},alignment:AlignmentType.CENTER,children:[t("교차신호 · 환경×건강",{bold:true,size:40,color:"1F4E79"})]}),
      new Paragraph({spacing:{after:400},alignment:AlignmentType.CENTER,children:[t("4층 교차신호 조기신호 · 5층 환경×건강 — 화면 흐름·시나리오",{size:22,color:"2E5496"})]}),
      new Paragraph({spacing:{after:500},alignment:AlignmentType.CENTER,children:[t("마이헬스케어 · 2026-06-21",{size:20,color:"555555"})]}),
      p("4층은 여러 측정을 ‘공인 근거 있는 조합’으로만 엮어 조기신호를 보여주고, 5층은 실내 공기질을 증상·이력과 결합해 환경 안내를 한다. 둘 다 진단이 아니라 ‘함께 살펴볼 패턴/환기 권유’ 천장.",{r:{italics:true,bold:true}}),
      new Paragraph({children:[new PageBreak()]}),

      h1("1. 4층 — 교차신호 조기신호"),
      p("화면 흐름: 여러 디바이스 신호가 모이면, 화이트리스트 등재 조합만 ‘함께 살펴볼 패턴’으로 발화한다(미등재·유사과학 조합은 구조적으로 차단).",{}),
      flow(["① 신호 집계\n워치·혈압·검진","② 조합 평가\n화이트리스트만","③ 출처 확인\n공인 근거 필수","④ 안내\n‘함께 볼 패턴’(진단 아님)"]),

      sc("4.1 컨디션 저하 조기신호 (워치)"),
      situ("워치 데이터: 안정시 심박이 평소보다 높고, 수면 짧고, 야간 호흡수 상승(연동)"),
      qL("요즘 몸이 좀 무거운데 워치에 뭔가 보이나요?"),
      ...aL("최근 안정시 심박이 평소보다 높고 수면이 짧으며 호흡수도 다소 올라간 흐름이에요. 이런 패턴은 인구집단 연구에서 컨디션 저하·감염 초기와 함께 관찰되곤 합니다. 무리하지 마시고 충분한 휴식·수분을 권하며, 발열·호흡곤란 등이 동반되면 진료를 권해드려요.","공인 근거 조합(W1·W2)만·진단 아님. 단일 신호 수치는 비노출, 본인 기저선 대비 ‘흐름’만."),

      sc("4.2 대사 관리 묶음"),
      situ("가정혈압 주의 + 체중/BMI 관리권장 + 작년 검진 공복혈당 경계(연동)"),
      qL("건강검진에서 이것저것 걸렸는데 뭘 같이 봐야 해요?"),
      ...aL("최근 가정혈압이 관리 권장 구간이고, 체중·BMI와 작년 공복혈당도 함께 관리하면 좋은 항목으로 보여요. 이들은 함께 살펴볼 때 도움이 되는 위험요인으로 알려져 있어, 식습관·운동·체중 관리와 함께 의료진 상담을 권해드립니다.","여러 소스 결합(B4 대사 조합)·운명론 아님·진단 아님."),

      h1("2. 5층 — 환경 × 건강"),
      p("실내 공기질을 증상·질병이력과 결합한다. 단, ‘환경이 영향 줄 수 있는 수준 + 환기 권유’가 천장 — 진단·실외 혼동 금지.",{}),
      flow(["① 증상/이력","② 실내 공기질\n(공기청정기 연동)","③ 결합 판단\n관련성 게이트","④ 안내\n환기 + 진료(필요시)"]),

      sc("5.1 호흡기·알레르기 케어"),
      situ("질병이력에 천식/COPD, 실내 PM2.5 ‘나쁨’(연동)"),
      qL("며칠째 기침이 안 멎고 답답해요."),
      ...aL("지속되는 기침은 여러 원인과 관련될 수 있어요. 〔🌬️ 실내 공기질 참고〕 현재 실내 미세먼지가 증상에 영향을 줄 수 있는 수준으로, 환기를 권해드립니다. 과거 호흡기 관련 이력도 있어, 증상이 계속되면 호흡기내과 상담을 권합니다.","공기질×이력 결합·환기 권유 천장(B5)·진단 아님·이력은 과거시제."),

      sc("5.2 수면·집중 환경 (CO2)"),
      situ("실내 CO2 ‘매우 나쁨’(연동)"),
      qL("요즘 잠도 잘 안 오고 낮에 멍해요."),
      ...aL("수면·집중 저하는 여러 원인과 관련될 수 있어요. 〔🌬️ 실내 공기질 참고〕 실내 이산화탄소가 높은 수준으로 환기를 권해드립니다. 규칙적 수면·활동이 일반적으로 도움이 되며, 지속되면 의료진 상담을 권합니다.","CO2 환기 권유·일반 생활 안내·진단 아님."),

      h1("3. 두 층의 안전 천장"),
      p("• 4층: 교차는 출처 첨부 화이트리스트만(B4). 유사과학 조합(HRV+수면=‘번아웃’)은 미등재 = 발화 불가. 워치 신호 수치는 비노출(기저선 흐름만).",{}),
      p("• 5층: 환경은 ‘진단 아님 + 환기 권유’ 천장(B5). 실내 한정(실외 혼동 금지). 공기질을 증상의 확정 원인으로 단정하지 않음.",{}),
      p("• 공통: 관련성 게이트로 무관 시 미표시. 원시값·질환명 외부 미전송.",{r:{bold:true},sp:{before:80}}),
    ]}]});
Packer.toBuffer(doc).then((b)=>{fs.writeFileSync("docs/4-5층_교차환경_상세_2026-06-21.docx",b);console.log("written:",b.length);});
