const fs=require("fs");
const {Document,Packer,Paragraph,TextRun,Table,TableRow,TableCell,AlignmentType,HeadingLevel,BorderStyle,WidthType,ShadingType,Footer,PageNumber}=require("docx");
const FONT="Malgun Gothic",CW=9360;
const bd={style:BorderStyle.SINGLE,size:1,color:"CCCCCC"};const bds={top:bd,bottom:bd,left:bd,right:bd};
const QF={Q1:"DCEAF5",Q2:"E3F0E0",Q3:"FBEFD9",Q4:"F2E5F0"};
const t=(x,o={})=>new TextRun({text:x,font:FONT,...o});
const h1=(x)=>new Paragraph({heading:HeadingLevel.HEADING_1,children:[t(x,{bold:true})]});
const p=(x,o={})=>new Paragraph({spacing:{after:100,...(o.sp||{})},children:[t(x,o.r||{})]});
function qtable(q,rows){const mk=(c,h)=>new TableRow({tableHeader:!!h,children:c.map((x,i)=>new TableCell({borders:bds,width:{size:[1700,5160,2500][i],type:WidthType.DXA},shading:{fill:h?"1F4E79":QF[q],type:ShadingType.CLEAR},margins:{top:40,bottom:40,left:80,right:80},children:[new Paragraph({children:[t(String(x),h?{bold:true,color:"FFFFFF",size:15}:{size:15})]})]}))});
 return new Table({width:{size:CW,type:WidthType.DXA},columnWidths:[1700,5160,2500],rows:[mk(["층","서비스","근거"],true),...rows.map(r=>mk(r))]});}
const Q={
 Q1:[["1","1.1 혈압 안내","엔진 완성·고가치"],["2","2.1 검진 결과 풀이","킬러"],["2","2.3 검진·복약·진료 알리미","저리스크·시간산술"],["1","1.4 공기질·환기","환경 시드 보유"]],
 Q2:[["1","1.2 체중·체성분 추세","추세 엔진"],["2","2.2 연도별 추세","변화 인식"],["2","2.5 내 건강 요약 카드","제품 허브"],["3","3.1 증상+최근 측정","결합 상담 ★"],["3","3.5 병원 갈 때 준비","실용 차별"]],
 Q3:[["3","3.2 증상+검진 / 3.4 증상+복약","개인화 상담"],["1","1.3 컨디션 추세(워치)","웰니스(정확도 고지)"],["4","4.2 대사 관리 묶음","위험요인 통합"],["5","5.1 호흡기·알레르기 케어","환경×이력"]],
 Q4:[["4","4.1 조기신호 / 4.3 활동코칭","워치 교차(공인 조합)"],["3","3.3 증상+환경","환경 결합"],["5","5.2 수면·집중 환경","환기 안내"],["6","6.1 위험요인 / 6.2 암검진갭","예방"],["2","2.4 OCR 디지털화","입력 확장"]],
};
const theme={Q1:"저리스크·고가치 단일 (연동 결정 직후)",Q2:"추세·요약 + 결합상담 시작",Q3:"개인화 심화 + 워치",Q4:"교차신호·환경·예방·OCR"};
const doc=new Document({styles:{default:{document:{run:{font:FONT,size:20}}},paragraphStyles:[{id:"Heading1",name:"Heading 1",basedOn:"Normal",next:"Normal",quickFormat:true,run:{size:27,bold:true,font:FONT,color:"1F4E79"},paragraph:{spacing:{before:240,after:120},outlineLevel:0}}]},
 sections:[{properties:{page:{size:{width:12240,height:15840},margin:{top:1440,right:1440,bottom:1440,left:1440}}},
  footers:{default:new Footer({children:[new Paragraph({alignment:AlignmentType.CENTER,children:[t("출시 로드맵 · ",{size:16,color:"888888"}),new TextRun({children:[PageNumber.CURRENT],font:FONT,size:16,color:"888888"})]})]})},
  children:[
   new Paragraph({spacing:{before:900,after:0},alignment:AlignmentType.CENTER,children:[t("서비스 출시 로드맵",{bold:true,size:42,color:"1F4E79"})]}),
   new Paragraph({spacing:{after:400},alignment:AlignmentType.CENTER,children:[t("22개 서비스 · 분기별 (가치×준비도×결정 의존)",{size:23,color:"2E5496"})]}),
   p("순서 원칙: 저리스크·고가치·엔진 완성 먼저(Q1) → 추세·결합 시작(Q2) → 개인화·워치(Q3) → 교차·환경·예방·OCR(Q4). 모든 단계는 데이터 연동·PHR 출처 결정 위에서 진행.",{r:{italics:true,color:"555555"}}),
   ...["Q1","Q2","Q3","Q4"].flatMap(q=>[h1(q+" — "+theme[q]),qtable(q,Q[q])]),
   p("Q1은 디바이스 연동 방식·PHR 출처 2개 결정이 선행되면 즉시 가동. 결합형(3·4·5·6층)은 소스가 연동될수록 강해진다.",{r:{bold:true},sp:{before:140}}),
  ]}]});
Packer.toBuffer(doc).then(b=>{fs.writeFileSync("docs/서비스_출시로드맵_2026-06-21.docx",b);console.log("written:",b.length);});
