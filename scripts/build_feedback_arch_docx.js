// 개선 루프 아키텍처 + 비식별 이벤트 스키마 → Word.
const fs=require("fs");
const {Document,Packer,Paragraph,TextRun,Table,TableRow,TableCell,AlignmentType,HeadingLevel,BorderStyle,WidthType,ShadingType,Footer,PageNumber,PageBreak,ImageRun}=require("docx");
const FONT="Malgun Gothic",CW=9360;
const LOOP=fs.readFileSync("docs/ontology/feedback-loop.png");
const bd={style:BorderStyle.SINGLE,size:1,color:"CCCCCC"};const bds={top:bd,bottom:bd,left:bd,right:bd};
const HEAD="1F4E79",ALT="EDF2F7";
const t=(x,o={})=>new TextRun({text:x,font:FONT,...o});
const h1=(x)=>new Paragraph({heading:HeadingLevel.HEADING_1,children:[t(x,{bold:true})]});
const p=(x,o={})=>new Paragraph({spacing:{after:100,...(o.sp||{})},children:[t(x,o.r||{})]});
function table(colW,header,rows){const mk=(c,h)=>new TableRow({tableHeader:!!h,children:c.map((x,i)=>new TableCell({borders:bds,width:{size:colW[i],type:WidthType.DXA},shading:{fill:h?HEAD:(rows.indexOf(c)%2?ALT:"FFFFFF"),type:ShadingType.CLEAR},margins:{top:40,bottom:40,left:80,right:80},children:String(x).split("\n").map(l=>new Paragraph({spacing:{after:0},children:[t(l,h?{bold:true,color:"FFFFFF",size:15}:{size:15})]}))}))});
 return new Table({width:{size:CW,type:WidthType.DXA},columnWidths:colW,rows:[mk(header,true),...rows.map(r=>mk(r))]});}
const doc=new Document({styles:{default:{document:{run:{font:FONT,size:20}}},paragraphStyles:[{id:"Heading1",name:"Heading 1",basedOn:"Normal",next:"Normal",quickFormat:true,run:{size:27,bold:true,font:FONT,color:"1F4E79"},paragraph:{spacing:{before:260,after:130},outlineLevel:0}}]},
 sections:[{properties:{page:{size:{width:12240,height:15840},margin:{top:1440,right:1440,bottom:1440,left:1440}}},
  footers:{default:new Footer({children:[new Paragraph({alignment:AlignmentType.CENTER,children:[t("개선 루프 아키텍처 · ",{size:16,color:"888888"}),new TextRun({children:[PageNumber.CURRENT],font:FONT,size:16,color:"888888"})]})]})},
  children:[
   new Paragraph({spacing:{before:900,after:0},alignment:AlignmentType.CENTER,children:[t("대화 기반 성능 개선 루프",{bold:true,size:40,color:"1F4E79"})]}),
   new Paragraph({spacing:{after:400},alignment:AlignmentType.CENTER,children:[t("아키텍처 · 도구 분담 · 비식별 이벤트 스키마",{size:23,color:"2E5496"})]}),
   new Paragraph({spacing:{after:500},alignment:AlignmentType.CENTER,children:[t("나만의 주치의 · 2026-06-21",{size:20,color:"555555"})]}),
   p("대화·반응을 메모리화하고, 피드백을 추출해 성능을 점점 개선하는 폐루프. 단, 의료 데이터라 ‘비식별·동의·국내저장·골든셋 게이트’가 전제. 정본: docs/ontology/feedback-ontology.ttl",{r:{italics:true,color:"555555"}}),
   new Paragraph({alignment:AlignmentType.CENTER,spacing:{before:120,after:60},children:[new ImageRun({type:"png",data:LOOP,transformation:{width:620,height:392},altText:{title:"개선 폐루프",description:"대화→3채널→백로그→골든셋게이트→배포",name:"loop"}})]}),
   new Paragraph({children:[new PageBreak()]}),

   h1("1. 개선 루프 = 3개의 다른 일 (도구 분담)"),
   p("한 도구로 안 됩니다. 행동·피드백·품질은 서로 다른 데이터·방법입니다.",{}),
   table([1700,3260,2600,1800],["일","무엇","도구","비고"],[
     ["A. 행동 분석","이벤트·퍼널·리텐션·코호트·A/B·기능플래그·세션리플레이","PostHog (self-hosted)","✅ 핵심 적합"],
     ["B. 피드백 추출","대화에서 만족·거절수요·정정·재질문·👍/👎 추출","우리 LLM 파이프라인 + Feedback 온톨로지","우리가 직접"],
     ["C. LLM 품질·관측","골든셋·judge·인용 정확도·지연·안전판정·프롬프트 버전","ANANTA / wraith (내부·국내)","Phoenix 대체"],
   ]),
   p("PostHog 하나로 B·C를 대신할 수 없음. PostHog는 행동(A)용.",{r:{bold:true},sp:{before:80}}),

   h1("2. PostHog 도입 단서 (의료라서)"),
   p("• 반드시 self-hosted(오픈소스) — Cloud는 미국 호스팅이라 ‘국외이전+이벤트에 건강정보’ 시 경계선 설계와 충돌. 자체 호스팅으로 국내 저장.",{}),
   p("• 비식별 이벤트만 — 라벨·카운트·불리언만. 질의 텍스트·원시 수치·진단명·PII는 절대 미전송(아래 §3).",{}),

   h1("3. 비식별 이벤트 스키마 (PostHog로 보낼 안전 이벤트)"),
   table([3200,6160],["이벤트(eventName)","의미"],[
     ["query_received","질의 수신(분류 결과 포함)"],
     ["answer_shown","답변 노출(경로·인용 수)"],
     ["followup_asked","후속 질문 제시"],
     ["referral_given","진료과/내원 안내 제공"],
     ["personal_block_shown","‘📋 내 기록 참고’ 결합 노출(여부만)"],
     ["insufficient_evidence","근거부족→길안내 전환(거절수요 신호)"],
     ["emergency_redirect","응급 안내 발생"],
     ["thumbs_up / thumbs_down","명시 피드백"],
     ["reask / abandoned","재질문 / 이탈"],
   ]),
   p("허용 속성(비식별):",{r:{bold:true},sp:{before:100,after:40}}),
   table([4680,4680],["허용 (보내도 됨)","금지 (절대 미전송)"],[
     ["intent(응급/증상/정보/바이탈)\npath\nprimary_domain\ncitations_count\nlatency_ms\nguardrail_action\ngate_decision\nevidence_quality\nis_followup\nhad_personal_block(bool)\ngave_referral(bool)\nrefusal(bool)","질의 원문 텍스트\n원시 측정값(예 165/92)\n진단명·질환명·약물명\n검진 라벨(개인 건강상태)\n이름·생년·주소 등 PII\n대화 자유텍스트"],
   ]),
   p("원칙: 분석은 ‘무슨 일이 얼마나’만 — ‘누가 무슨 병/수치’는 안 보냄. 개인 건강상태 라벨(밴드)도 이벤트엔 미포함(집계 불리언만).",{r:{bold:true},sp:{before:80}}),

   h1("4. 피드백 신호 유형 (B — 대화에서 추출)"),
   table([2400,6960],["신호","활용"],[
     ["거절 수요(RefusalDemand)","‘원했으나 합법적으로 못 준’ → KB 확장·표현 개선 1급 입력(E4)"],
     ["정정(Correction)","‘아니 그게 아니라’ → 답 오류 신호"],
     ["재질문(Reask)","같은 의도 반복 → 답 부족 신호"],
     ["만족도/명시(👍/👎)","유용성 KPI·랭킹 학습 입력"],
     ["이탈/체류","답변 효과·UX 신호(행동분석과 결합)"],
   ]),

   h1("5. 안전 공리 (개선 루프 E1~E7)"),
   table([700,8660],["#","규칙"],[
     ["E1","피드백은 민감(건강 텍스트) → 동의·마스킹·국내저장"],
     ["E2","PostHog엔 비식별 이벤트만 · 질의텍스트·원시수치·진단명·PII 금지 · self-hosted(국외이전 0)"],
     ["E3","개선 항목은 골든셋 게이트 통과 시에만 배포(안전 회귀 0)"],
     ["E4","거절수요 = ‘원했으나 합법적으로 못 준’ = KB확장·표현개선 1급 입력"],
     ["E5","자동 추출 피드백은 사람 검수 경유 — 자동 프롬프트/규칙 변경 금지"],
     ["E6","매 턴 응급 재평가·안전 불변식은 실험·개선과 무관하게 항상 유지"],
     ["E7","A/B는 안전 동등성 전제 — 어느 변이도 진단단정·거짓안심·민감노출 0이어야 분배"],
   ]),
   p("핵심: 성능은 ‘대화에서 배워’ 좋아지되, 안전은 ‘골든셋 게이트’가 지킨다 — 개선이 안전을 무너뜨릴 수 없는 구조.",{r:{bold:true},sp:{before:120}}),

   h1("부록. 이미 있는 것 / 신규"),
   p("• 이미: rag_gap_analysis(거절수요)·review_queue·감사 필드·골든셋. • 신규: feedback-ontology.ttl·비식별 이벤트 파이프라인·PostHog(self-hosted)·ANANTA/wraith 연동.",{r:{size:18}}),
  ]}]});
Packer.toBuffer(doc).then(b=>{fs.writeFileSync("docs/개선루프_아키텍처_2026-06-21.docx",b);console.log("written:",b.length);});
