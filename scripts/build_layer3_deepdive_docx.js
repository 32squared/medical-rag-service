// 3층 결합형 상담 — 화면 흐름 + 대화 시나리오 상세 → Word(.docx).
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
  styles:{default:{document:{run:{font:FONT,size:20}}},
    paragraphStyles:[{id:"Heading1",name:"Heading 1",basedOn:"Normal",next:"Normal",quickFormat:true,run:{size:27,bold:true,font:FONT,color:"1F4E79"},paragraph:{spacing:{before:260,after:130},outlineLevel:0}}]},
  sections:[{
    properties:{page:{size:{width:12240,height:15840},margin:{top:1440,right:1440,bottom:1440,left:1440}}},
    footers:{default:new Footer({children:[new Paragraph({alignment:AlignmentType.CENTER,children:[t("3층 결합형 상담 상세 · ",{size:16,color:"888888"}),new TextRun({children:[PageNumber.CURRENT],font:FONT,size:16,color:"888888"})]})]})},
    children:[
      new Paragraph({spacing:{before:1000,after:0},alignment:AlignmentType.CENTER,children:[t("증상 상담 + 내 데이터 결합",{bold:true,size:40,color:"1F4E79"})]}),
      new Paragraph({spacing:{after:400},alignment:AlignmentType.CENTER,children:[t("3층 결합형 상담 — 화면 흐름 · 대화 시나리오",{size:24,color:"2E5496"})]}),
      new Paragraph({spacing:{after:500},alignment:AlignmentType.CENTER,children:[t("나만의 주치의 · 2026-06-21",{size:20,color:"555555"})]}),
      p("3층은 사용자가 증상을 물으면, 연결된 측정·검진·복약 데이터를 그 답변에 ‘진단 없이’ 결합하는 서비스다. 범용 AI가 못 하는 핵심 차별 영역.",{r:{italics:true,bold:true}}),
      new Paragraph({children:[new PageBreak()]}),

      h1("1. 화면 흐름"),
      flow([
        "① 챗 입력\n사용자 증상 질문",
        "② 분류\n증상/응급 판정",
        "③ 검색 + 내 데이터\n공인근거 + 결정적 해석(findings)",
        "④ 답변\n증상 카드 + 📋 내 기록 참고",
        "⑤ 후속\n추가 질문 / 병원 준비",
      ]),
      p("핵심: ③에서 내 측정·검진은 로컬에서 ‘구간 라벨’로 해석되고, 질의와 관련될 때만 ④의 ‘📋 내 기록 참고’ 블록으로 붙는다. 원시값·질환명은 외부로 안 나간다.",{r:{size:18},sp:{before:120}}),

      h1("2. 답변 구조"),
      p("증상 답변(가능한 원인·지금 할 수 있는 것·진료 안내) 끝에, 관련 있을 때만 아래 블록이 결합된다:",{}),
      new Paragraph({shading:{type:ShadingType.CLEAR,fill:"F8FAFC"},border:{left:{style:BorderStyle.SINGLE,size:18,color:"1F4E79",space:6}},spacing:{before:60,after:0},children:[t("📋 내 기록 참고",{bold:true})]}),
      new Paragraph({shading:{type:ShadingType.CLEAR,fill:"F8FAFC"},spacing:{after:0},children:[t("- 최근 측정된 혈압이 관리 권장 구간으로 확인돼요.",{size:19})]}),
      new Paragraph({shading:{type:ShadingType.CLEAR,fill:"F8FAFC"},spacing:{after:120},children:[t("  측정값의 해석과 진단은 의료진과 상담하세요.",{size:19,color:"555555"})]}),

      h1("3. 대화 시나리오"),
      sc("3.1 증상 + 최근 측정 (혈압)"),
      situ("집 혈압기 측정(145/92)이 앱에 연동됨"),
      qL("머리가 지끈거리는데 혹시 혈압 때문일까요?"),
      ...aL("두통은 수면·스트레스·긴장 등 여러 원인과 관련될 수 있어요. 갑작스러운 심한 두통이나 시야·언어 변화가 동반되면 진료를 권해드려요. 〔📋 내 기록 참고〕 최근 측정된 혈압이 관리 권장 구간으로 확인돼, 함께 살펴보시면 좋아요. 한 번 측정으로 단정하진 않으니 반복 측정·의료진 상담을 권합니다.","측정 맥락을 결합하되 ‘혈압 때문’ 단정 X(D3). 원시값 145/92·‘고혈압’ 미노출."),
      qL("그럼 혈압은 어떻게 관리해요?"),
      ...aL("규칙적인 유산소 운동·저염식·충분한 수면이 일반적으로 도움이 되는 것으로 알려져 있어요. 가정에서 같은 시간대에 반복 측정해 흐름을 보시고, 구간이 계속되면 의료진과 상의해보세요.","생활 일반 안내(천장 내)·약물/용량 단정 X."),

      sc("3.2 증상 + 검진 이력 (피로·빈혈)"),
      situ("작년 검진 혈색소가 빈혈 경계로 기록됨(비민감)"),
      qL("요즘 너무 피곤하고 어지러워요."),
      ...aL("피로·어지럼은 수면 부족·스트레스·빈혈 등 여러 원인과 관련될 수 있어요. 〔📋 내 기록 참고〕 작년 검진의 혈색소가 관리 권장 구간으로 기록돼 있어, 이번 증상도 같은 맥락에서 함께 살펴보시면 좋겠어요. 증상이 지속되면 내과 상담을 권해드립니다.","검진 이력을 indirect 브리징(과거시제)·진단 단정 X(A1·D3)."),

      sc("3.4 증상 + 복약 이력 (어지럼)"),
      situ("과거 혈압약 계열 처방 이력(약물명 미노출)"),
      qL("일어설 때 핑 돌고 어지러워요."),
      ...aL("기립 시 어지럼은 탈수·기립성 저혈압 등과 관련될 수 있어요. 〔📋 내 기록 참고〕 과거 혈압 관련 약물 계열 처방 이력이 확인되어, 현재 복용 중이시면 어지럼과 함께 약사·의료진께 한번 말씀해보시면 좋겠어요.","약물 계열만·현재복용 조건부·인과 단정 X(A7)."),

      sc("3.5 병원 갈 때 준비"),
      qL("내일 병원 가는데 뭘 말해야 할지 모르겠어요."),
      ...aL("진료 때 이런 것들을 말씀하시면 도움이 돼요: ① 최근 증상(언제부터·정도·동반 증상), ② 과거 관련 이력, ③ 복용 중인 약(있다면 계열·이름), ④ 최근 측정값 흐름. 원하시면 지금까지 말씀하신 증상으로 메모를 만들어 드릴게요.","PHR+대화 결합 정리·라벨/계열만·민감은 사용자 선택."),

      h1("4. 안전 처리 (이 층에 적용되는 공리)"),
      p("• D1 사용자가 ‘내 혈압 150’처럼 말로 댄 수치는 개인화(밴드)를 켜지 않음 — 증상 맥락으로만. 실제 활성화는 연동 측정값만.",{}),
      p("• D3 수집 맥락(증상·이력)은 답변 shaping 입력일 뿐 — 진단 단정 아님(인구집단 수준).",{}),
      p("• A1 민감 이력(정신·암·감염)은 ‘📋 내 기록 참고’에 표시하지 않음 — 내부 톤만.",{}),
      p("• 관련성 게이트 질의와 무관하면 ‘📋 내 기록 참고’ 미표시(과노출 차단). 원시값·질환명 외부 미전송.",{}),
      p("결과: 내 데이터로 답이 풍부해지되, 진단·과노출·원시값 유출은 구조적으로 0.",{r:{bold:true},sp:{before:100}}),
    ]}]});
Packer.toBuffer(doc).then((b)=>{fs.writeFileSync("docs/3층_결합형상담_상세_2026-06-21.docx",b);console.log("written:",b.length);});
