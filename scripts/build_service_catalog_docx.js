// 서비스 카탈로그 → Word(.docx).
const fs = require("fs");
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  AlignmentType, HeadingLevel, BorderStyle, WidthType, ShadingType, PageBreak, Footer, PageNumber, ImageRun } = require("docx");
const ONTO_PNG = fs.readFileSync("docs/ontology/phr-ontology-unified.png");
const FONT="Malgun Gothic", CW=9360;
const bd={style:BorderStyle.SINGLE,size:1,color:"CCCCCC"}; const bds={top:bd,bottom:bd,left:bd,right:bd};
const HEAD="1F4E79", ALT="EDF2F7", COMBO="EAF1E6", STAR="FCE8D5";
const t=(x,o={})=>new TextRun({text:x,font:FONT,...o});
const h1=(x)=>new Paragraph({heading:HeadingLevel.HEADING_1,children:[t(x,{bold:true})]});
const p=(x,o={})=>new Paragraph({spacing:{after:100,...(o.sp||{})},children:[t(x,o.r||{})]});
function table(colW,header,rows){
  const mk=(cells,head)=>new TableRow({tableHeader:!!head,children:cells.map((c,i)=>new TableCell({
    borders:bds,width:{size:colW[i],type:WidthType.DXA},
    shading:{fill:head?HEAD:(cells.__star?STAR:(cells.__combo?COMBO:(rows.indexOf(cells)%2?ALT:"FFFFFF"))),type:ShadingType.CLEAR},
    margins:{top:40,bottom:40,left:80,right:80},
    children:String(c).split("\n").map((l)=>new Paragraph({spacing:{after:0},children:[t(l,head?{bold:true,color:"FFFFFF",size:15}:{size:15})]}))}))});
  return new Table({width:{size:CW,type:WidthType.DXA},columnWidths:colW,rows:[mk(header,true),...rows.map((r)=>mk(r))]});
}
const data=[
 ["1 측정값","1.1 혈압 안내","단일","혈압기·A1","내 혈압 구간+상담","높음"],
 ["1 측정값","1.2 체중·체성분 추세","단일","체중계","체중·BMI 흐름","높음"],
 ["1 측정값","1.3 컨디션 추세","단일","워치","수면·활동·심박 본인기준","중"],
 ["1 측정값","1.4 공기질·환기","단일","공기질·청정기","환기 안내","중"],
 ["2 기록이해","2.1 검진 결과 풀이","단일","PHR 검진","검진지 쉬운 해석 ★","★"],
 ["2 기록이해","2.2 연도별 추세","단일","PHR 검진(다년)","변화 인식","높음"],
 ["2 기록이해","2.3 검진·복약·진료 알리미","단일","PHR 시간산술","챙김","★"],
 ["2 기록이해","2.4 종이기록 디지털화","입력","OCR","처방전·검사지→기록","중"],
 ["2 기록이해","2.5 내 건강 요약 카드","단일","PHR 전반","흩어진 기록 한눈에","높음"],
 ["3 결합상담","3.1 증상+최근 측정","결합","대화×혈압기","측정 맥락 결합 ★","★"],
 ["3 결합상담","3.2 증상+검진 이력","결합","대화×PHR","과거 이력 맥락","높음"],
 ["3 결합상담","3.3 증상+환경","결합","대화×공기질","환기+진료","중"],
 ["3 결합상담","3.4 증상+복약 이력","결합","대화×처방","약사 상담 연결","중"],
 ["3 결합상담","3.5 병원 갈 때 준비","결합","대화×PHR","진료 효율","높음"],
 ["4 교차신호","4.1 컨디션 저하 조기신호","결합","워치(심박+수면+호흡)","감염 초기 패턴","중"],
 ["4 교차신호","4.2 대사 관리 묶음","결합","혈압+체중+검진혈당","함께 볼 위험요인","높음"],
 ["4 교차신호","4.3 활동·수면 코칭","결합","워치(활동+수면)","생활 안내","중"],
 ["5 환경×건강","5.1 호흡기·알레르기 케어","결합","공기질×질병이력","환기·외출","중"],
 ["5 환경×건강","5.2 수면·집중 환경","결합","CO2×대화","환기 권유","낮~중"],
 ["6 예방","6.1 위험요인 묶음","결합","검진+가족력+생활+측정","통합 관리","중"],
 ["6 예방","6.2 암검진 갭(위험군)","결합","C형간염×간암검진","위험군 검진","중"],
].map(r=>{ if(r[5]==="★")r.__star=true; else if(r[2]==="결합")r.__combo=true; return r; });

const doc=new Document({
  styles:{default:{document:{run:{font:FONT,size:20}}},
    paragraphStyles:[{id:"Heading1",name:"Heading 1",basedOn:"Normal",next:"Normal",quickFormat:true,run:{size:27,bold:true,font:FONT,color:"1F4E79"},paragraph:{spacing:{before:240,after:130},outlineLevel:0}}]},
  sections:[{
    properties:{page:{size:{width:12240,height:15840},margin:{top:1440,right:1440,bottom:1440,left:1440}}},
    footers:{default:new Footer({children:[new Paragraph({alignment:AlignmentType.CENTER,children:[t("서비스 카탈로그 · ",{size:16,color:"888888"}),new TextRun({children:[PageNumber.CURRENT],font:FONT,size:16,color:"888888"})]})]})},
    children:[
      new Paragraph({spacing:{before:900,after:0},alignment:AlignmentType.CENTER,children:[t("서비스 카탈로그",{bold:true,size:44,color:"1F4E79"})]}),
      new Paragraph({spacing:{after:400},alignment:AlignmentType.CENTER,children:[t("통합 데이터 온톨로지 기반 · 22개 서비스",{size:24,color:"2E5496"})]}),
      new Paragraph({spacing:{after:500},alignment:AlignmentType.CENTER,children:[t("마이헬스케어 · 2026-06-21",{size:20,color:"555555"})]}),
      p("PHR·디바이스·환경·OCR·대화를 진단 없이 안전하게 활용하는 22개 서비스. 단일 소스(1·2층)는 각 기기/기록 해석, 결합형(3·4·5·6층)은 소스를 엮은 차별 서비스.",{r:{italics:true,color:"555555"}}),
      new Paragraph({alignment:AlignmentType.CENTER,spacing:{before:120,after:60},children:[new ImageRun({type:"png",data:ONTO_PNG,transformation:{width:600,height:380},altText:{title:"통합 데이터 온톨로지",description:"여러 소스가 하나의 안전 코어로",name:"onto"}})]}),
      p("[그림] 이 22개 서비스가 딛고 선 통합 온톨로지 — 여러 소스가 하나의 안전 코어로.",{r:{size:16,color:"777777"},sp:{after:40}}),
      new Paragraph({children:[new PageBreak()]}),
      h1("전체 서비스 (22)"),
      table([1400,2700,1100,2360,1800],["층","서비스","유형","사용 데이터","사용자 가치"],
        data.map(r=>{const o=[r[0],r[1],r[2],r[3],r[4]];o.__star=r.__star;o.__combo=r.__combo;return o;})),
      p("주황=킬러(★) · 연두=결합형. 우선순위·안전공리는 Excel 카탈로그 참조.",{r:{size:16,color:"777777"},sp:{before:80}}),
      h1("두 층으로 보는 차별점"),
      table([2600,6760],["",""],[
        ["단일 소스 (1·2층)","각 기기/기록을 안전하게 해석 — 경쟁사도 일부 가능"],
        (()=>{const o=["★ 결합형 (3·4·5·6층)","증상×측정×검진×환경을 진단 없이 엮음 — 통합 온톨로지(공유 코어·signalKey·교차 화이트리스트)가 있어야 안전 가능, 범용 AI 불가"];o.__star=true;return o;})(),
      ]),
      p("모든 서비스가 온톨로지 안전 공리(A~D)를 상속 — 진단 0·민감정보 비표시·원시값 비전송. 서비스가 늘어도 리스크는 안 늘어난다.",{r:{bold:true},sp:{before:120}}),
    ]}]});
Packer.toBuffer(doc).then((b)=>{fs.writeFileSync("docs/서비스카탈로그_2026-06-21.docx",b);console.log("written:",b.length);});
