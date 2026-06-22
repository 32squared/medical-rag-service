"""임원용 쉬운 안내서 → 깔끔한 PDF (친근한 신호등·안전장치 그림 포함)."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))

CSS = """
@page { size: A4; margin: 20mm 18mm; }
* { box-sizing: border-box; }
body { font-family:'Malgun Gothic','Noto Sans KR','Segoe UI',sans-serif; font-size:11.5pt;
  line-height:1.75; color:#2b2b27; margin:0; }
h1 { font-size:26pt; font-weight:700; color:#0f3d2e; margin:0 0 4px; }
h2 { font-size:16pt; font-weight:700; color:#0f6e56; margin:26px 0 8px;
  border-bottom:2px solid #cde7dd; padding-bottom:5px; page-break-after:avoid; }
p { margin:8px 0; }
ul { margin:8px 0; padding-left:20px; } li { margin:6px 0; }
b { color:#13402f; }
.lead { font-size:13pt; color:#0f6e56; line-height:1.7; }
.cover { height:230mm; display:flex; flex-direction:column; justify-content:center;
  align-items:center; text-align:center; page-break-after:always; }
.cover .sub { font-size:14pt; color:#0f6e56; margin-top:10px; }
.cover .meta { font-size:11pt; color:#6b6a64; margin-top:30px; }
.fig { text-align:center; margin:16px 0; page-break-inside:avoid; }
.cap { font-size:10pt; color:#6b6a64; margin-top:6px; }
.quote { background:#f2f7f4; border-left:4px solid #1D9E75; padding:12px 16px; margin:14px 0;
  border-radius:0 8px 8px 0; font-size:11.5pt; }
.warn { background:#fff7e8; border-left:4px solid #EF9F27; padding:12px 16px; margin:14px 0;
  border-radius:0 8px 8px 0; }
.url { font-size:13pt; color:#185FA5; font-weight:700; word-break:break-all; }
table { border-collapse:collapse; width:100%; font-size:11pt; margin:12px 0; }
td,th { border:1px solid #d7e3dd; padding:9px 12px; text-align:left; vertical-align:top; }
th { background:#eef6f2; color:#0f3d2e; width:24%; }
.num { display:inline-block; width:22px; height:22px; line-height:22px; text-align:center;
  background:#1D9E75; color:#fff; border-radius:50%; font-size:10pt; font-weight:700; margin-right:6px; }
"""

LIGHT = """
<svg width="460" viewBox="0 0 460 150" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="건강수치를 안정·주의·경고 신호등으로 해석">
<circle cx="90" cy="60" r="38" fill="#E7F3E8" stroke="#2E7D32" stroke-width="2"/>
<circle cx="90" cy="60" r="20" fill="#2E7D32"/>
<text x="90" y="124" text-anchor="middle" font-family="Malgun Gothic,sans-serif" font-size="15" fill="#2E7D32" font-weight="bold">안정</text>
<circle cx="230" cy="60" r="38" fill="#FDF1DF" stroke="#B06A00" stroke-width="2"/>
<circle cx="230" cy="60" r="20" fill="#EF9F27"/>
<text x="230" y="124" text-anchor="middle" font-family="Malgun Gothic,sans-serif" font-size="15" fill="#B06A00" font-weight="bold">주의</text>
<circle cx="370" cy="60" r="38" fill="#FBE9E9" stroke="#C62828" stroke-width="2"/>
<circle cx="370" cy="60" r="20" fill="#C62828"/>
<text x="370" y="124" text-anchor="middle" font-family="Malgun Gothic,sans-serif" font-size="15" fill="#C62828" font-weight="bold">경고</text>
</svg>
"""

SAFE = """
<svg width="560" viewBox="0 0 560 130" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="내 실제 수치는 AI에 넘기지 않고 신호등 표시만 전달">
<rect x="10" y="40" width="170" height="56" rx="10" fill="#F1EFE8" stroke="#888780" stroke-width="1.5"/>
<text x="95" y="64" text-anchor="middle" font-family="Malgun Gothic,sans-serif" font-size="13" fill="#2C2C2A" font-weight="bold">내 실제 수치</text>
<text x="95" y="84" text-anchor="middle" font-family="Malgun Gothic,sans-serif" font-size="12" fill="#5F5E5A">152 / 96</text>
<rect x="215" y="40" width="130" height="56" rx="10" fill="#FAEEDA" stroke="#BA7517" stroke-width="1.5"/>
<text x="280" y="64" text-anchor="middle" font-family="Malgun Gothic,sans-serif" font-size="13" fill="#412402" font-weight="bold">안전 잠금</text>
<text x="280" y="84" text-anchor="middle" font-family="Malgun Gothic,sans-serif" font-size="11" fill="#854F0B">동의·응급 확인 등</text>
<rect x="380" y="40" width="170" height="56" rx="10" fill="#E1F5EE" stroke="#1D9E75" stroke-width="1.5"/>
<text x="465" y="64" text-anchor="middle" font-family="Malgun Gothic,sans-serif" font-size="13" fill="#04342C" font-weight="bold">AI에게는</text>
<text x="465" y="84" text-anchor="middle" font-family="Malgun Gothic,sans-serif" font-size="12" fill="#0F6E56">‘경고’ 신호만</text>
<line x1="180" y1="68" x2="213" y2="68" stroke="#888780" stroke-width="2"/>
<polygon points="213,68 205,64 205,72" fill="#888780"/>
<line x1="345" y1="68" x2="378" y2="68" stroke="#888780" stroke-width="2"/>
<polygon points="378,68 370,64 370,72" fill="#888780"/>
<text x="280" y="118" text-anchor="middle" font-family="Malgun Gothic,sans-serif" font-size="11" fill="#A32D2D">원본 숫자(152/96)는 넘어가지 않습니다</text>
</svg>
"""

BODY = f"""
<div class="cover">
  <h1>나만의 주치의</h1>
  <div class="sub">쉽게 보는 안내서</div>
  <div class="meta">기술 용어 없이 정리한 설명 · 2026-06-22<br>출시 전 시제품</div>
</div>

<h2>한마디로</h2>
<p class="lead"><b>건강이 궁금할 때, 믿을 수 있는 의학 정보를 ‘사람 말’로 안내해 주는 AI 건강비서입니다.</b></p>
<p>단, 의사를 대신해 병명을 단정하거나 약을 처방하지는 않습니다. 그건 법(의료법)으로 금지돼 있고, 우리는 그 선을 기술로 철저히 지킵니다.</p>

<h2>왜 필요한가</h2>
<p>사람들은 몸이 궁금하면 인터넷이나 일반 챗봇(ChatGPT 등)에 묻습니다. 그런데 거기엔 세 가지 문제가 있습니다.</p>
<ul>
<li><b>틀릴 수 있다</b> — 출처가 불분명하거나 과장된 정보가 섞입니다.</li>
<li><b>위험할 수 있다</b> — “당신은 ○○병입니다” 식으로 함부로 단정하면 사람을 잘못 안심시키거나 겁줍니다.</li>
<li><b>불법일 수 있다</b> — 의사 면허 없이 진단·처방하는 건 의료법 위반입니다.</li>
</ul>
<p>우리 서비스는 <b>질병관리청·식약처 같은 공식 의학 자료</b>를 바탕으로, <b>법이 허용하는 범위 안에서</b> 친절하게 안내합니다. 건강관리 앱에 넣어 일반 AI(GPT·제미나이)와 차별화하는 것이 목표입니다.</p>

<h2>무엇을 해주나</h2>
<p><span class="num">1</span><b>믿을 수 있는 답 + 출처를 함께</b> — 공식 자료에 근거해 답하고, 그 내용이 어디서 나왔는지 출처를 같이 보여줍니다.</p>
<p><span class="num">2</span><b>위험하면 “병원으로” 안내</b> — 병명을 단정하는 대신, 어느 진료과로·언제 응급실로 가야 하는지 길을 안내합니다.</p>
<p><span class="num">3</span><b>내 건강수치를 ‘신호등’으로</b> — 혈압·혈당 같은 수치를 아래 신호등으로 해석해 내 상황에 맞춰 답합니다.</p>
<div class="fig">{LIGHT}<div class="cap">예: 혈압이 ‘경고’면 “재측정하고, 지속되면 진료받으세요”처럼 더 적극적으로 안내합니다.</div></div>
<p><span class="num">4</span><b>애매하면 몇 가지 더 여쭤본 뒤 정확히</b> — 처음엔 간단히 답하고, 더 정확히 하려고 “증상이 언제부터였나요?”처럼 선택형 질문을 몇 개 던진 뒤 맞춤 답을 줍니다. (병원 문진표를 작성하듯)</p>

<h2>어떻게 안전하게·합법적으로 지키나 (가장 중요)</h2>
<p>이 서비스의 진짜 경쟁력은 ‘똑똑함’보다 <b>‘안전하게 선을 지키는 것’</b>입니다.</p>
<ul>
<li><b>의사 흉내를 내지 않습니다.</b> 병명 단정·약 처방을 하지 않고, ‘정보 제공’과 ‘병원 안내’까지만 합니다.</li>
<li><b>내 실제 수치는 AI에 넘기지 않습니다.</b> 원본 숫자 대신 신호등 표시만, 그것도 여러 겹의 잠금장치를 모두 통과해야 전달됩니다.</li>
<li><b>응급은 무조건 119가 먼저</b>입니다. 위급 신호면 다 멈추고 응급실 안내부터.</li>
<li><b>섣부른 안심을 차단</b>합니다. 병원을 안 가게 만들 수 있는 “괜찮습니다” 같은 표현을 자동으로 걸러냅니다.</li>
</ul>
<div class="fig">{SAFE}</div>
<div class="quote"><b>비유하자면</b> — 자동차로 치면, 빠른 엔진보다 <b>안전벨트·에어백·브레이크</b>를 먼저 갖춘 셈입니다. 이 ‘안전장치’가 우리 제품의 핵심입니다.</div>

<h2>지금 직접 보기</h2>
<p>인터넷 주소만 열면 누구나 바로 체험할 수 있는 시험용 화면을 띄워 두었습니다. (실제 환자가 아니라 <b>가짜 예시 인물</b>로 안전하게 테스트합니다.)</p>
<p class="url">https://medical-rag-viewer-716262961556.asia-northeast3.run.app</p>
<ul>
<li><b>왼쪽</b> — 가상의 환자를 고르고</li>
<li><b>가운데</b> — 그 사람의 건강수치(신호등)와 기록을 보고</li>
<li><b>오른쪽</b> — 질문하고 답을 받는 대화창</li>
</ul>
<div class="warn">※ 시험용 시제품이며, 실제 의료 자문이 아닙니다. 모든 데이터는 가짜입니다.</div>

<h2>지금 어디까지 왔나 (있는 그대로)</h2>
<p>지금은 <b>‘출시 전 시제품’</b>입니다. 핵심 기능과 안전장치는 만들어져 작동하지만, 진짜 서비스로 내보내려면 아직 할 일이 남았습니다.</p>
<p><b>출시 전 꼭 끝내야 할 3가지</b></p>
<ul>
<li><b>변호사 법률 검토</b> — 이 방식이 의료법상 문제없는지 최종 확인</li>
<li><b>실제 동의 절차</b> — 개인정보·해외 전송 동의를 제대로 받는 시스템</li>
<li><b>의료진 감수</b> — 답변에 쓰는 의학 자료를 의사가 검수</li>
</ul>
<div class="warn"><b>분명히 해 둘 점</b> — “시험을 통과했다”는 것은 ‘우리가 만든 대로 작동한다’는 뜻이지, ‘의학적으로 정확하고 법적으로 다 끝났다’는 뜻이 <b>아닙니다.</b></div>

<h2>한 장 요약</h2>
<table>
<tr><th>무엇</th><td>믿을 수 있고, 법을 지키고, 내게 맞춘 건강 안내 AI</td></tr>
<tr><th>차별점</th><td>안전·합법의 경계를 ‘기술로 강제’ — 일반 챗봇이 못 하는 부분</td></tr>
<tr><th>현재</th><td>시제품 작동 중 · 출시 전 법률·동의·의료진 감수 남음</td></tr>
<tr><th>체험</th><td>공개 시험 주소에서 누구나 바로</td></tr>
</table>
"""


def main():
    html = f"<!DOCTYPE html><html lang='ko'><head><meta charset='utf-8'><style>{CSS}</style></head><body>{BODY}</body></html>"
    out = os.path.join(HERE, "manual_exec.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print("WROTE", out, len(html))


if __name__ == "__main__":
    main()
