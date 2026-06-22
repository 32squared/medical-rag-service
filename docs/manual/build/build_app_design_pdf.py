"""마이헬스케어 전체 앱 UX/UI 시안서 — 화면 카탈로그 + 디자인 시스템 + 개발 핸드오프.
HTML 조립 → Chrome/Edge headless --print-to-pdf 로 PDF화. (build_manual_pdf.py 와 동일 방식)
화면은 고정 라이트 테마 폰 목업(인쇄용). 스펙은 실제 백엔드(RAG·코칭 18 §7·방향2 17) 바인딩."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# ── 브랜드 토큰 ────────────────────────────────────────────────
TEAL, TEAL50, TEAL800 = "#0F6E56", "#E1F5EE", "#085041"
INK, SUB, MUTE = "#2C2C2A", "#5F5E5A", "#9A9A93"
LINE, TRACK, SURF = "#E6E4DC", "#EFEDE6", "#F7F6F1"
AMB_F, AMB_T, AMB_I = "#FAEEDA", "#633806", "#BA7517"
DNG_F, DNG_T = "#FCEBEB", "#A32D2D"

ST = ('<div class="st"><div class="notch"></div><span>9:41</span>'
      '<span class="sti"><i class="ti ti-wifi"></i><i class="ti ti-battery-3"></i></span></div>')

CSS = f"""
@page {{ size:A4; margin:13mm 11mm 14mm 11mm; }}
* {{ box-sizing:border-box; }}
body {{ font-family:'Malgun Gothic','Noto Sans KR','Segoe UI',sans-serif; font-size:10pt;
  line-height:1.5; color:{INK}; margin:0; }}
h1 {{ font-size:25pt; font-weight:600; color:{TEAL800}; margin:0 0 6px; }}
h2 {{ font-size:15pt; font-weight:600; color:{TEAL}; border-bottom:2px solid #1D9E75;
  padding-bottom:4px; margin:22px 0 10px; page-break-after:avoid; }}
h3 {{ font-size:11.5pt; font-weight:600; color:{INK}; margin:13px 0 5px; page-break-after:avoid; }}
p {{ margin:5px 0; }} ul {{ margin:5px 0; padding-left:17px; }} li {{ margin:2px 0; }}
code {{ font-family:Consolas,monospace; background:{SURF}; padding:0 3px; border-radius:3px;
  font-size:8.6pt; color:#4a1b0c; }}
table {{ border-collapse:collapse; width:100%; font-size:9pt; margin:8px 0; page-break-inside:avoid; }}
th,td {{ border:1px solid #cfcdc4; padding:4px 6px; text-align:left; vertical-align:top; }}
th {{ background:#eef4f1; color:{TEAL800}; font-weight:600; }}
.cover {{ height:250mm; display:flex; flex-direction:column; justify-content:center;
  align-items:center; text-align:center; page-break-after:always; }}
.cover .logo {{ width:96px; height:96px; border-radius:28px; background:{TEAL50}; color:{TEAL};
  font-size:50px; display:flex; align-items:center; justify-content:center; margin-bottom:22px; }}
.cover .sub {{ font-size:13pt; color:{TEAL}; margin-top:10px; }}
.cover .meta {{ font-size:10pt; color:{SUB}; margin-top:30px; line-height:1.7; }}
section {{ page-break-before:always; }} .sec0 {{ page-break-before:avoid; }}
.toc {{ font-size:10.5pt; }} .toc li {{ margin:4px 0; }}
.note {{ background:{SURF}; border-left:3px solid #1D9E75; padding:8px 12px; margin:9px 0;
  border-radius:0 6px 6px 0; font-size:9.4pt; }}
.danger {{ background:{DNG_F}; border-left:3px solid {DNG_T}; padding:8px 12px; margin:9px 0;
  border-radius:0 6px 6px 0; font-size:9.4pt; color:#501313; }}
.tok {{ display:flex; flex-wrap:wrap; gap:10px; margin:8px 0; }}
.sw {{ width:96px; font-size:8pt; color:{SUB}; }}
.sw .chip {{ height:34px; border-radius:7px; border:1px solid {LINE}; margin-bottom:3px; }}
/* 화면 카탈로그 행 */
.scr {{ display:flex; gap:15px; align-items:flex-start; margin:12px 0 16px; page-break-inside:avoid; }}
.spec {{ flex:1; font-size:8.7pt; }}
.spec h3 {{ margin:0 0 5px; font-size:11pt; }}
.spec table {{ font-size:8.4pt; margin:4px 0; }}
.spec th {{ width:62px; white-space:nowrap; }}
.gal {{ display:flex; flex-wrap:wrap; gap:13px; justify-content:flex-start; }}
.gal .cap {{ font-size:8.3pt; color:{SUB}; text-align:center; margin-top:5px; font-weight:600; }}
/* 폰 목업 */
.ph {{ width:218px; background:#fff; border:1px solid #DDDBD3; border-radius:24px; overflow:hidden;
  display:flex; flex-direction:column; }}
.ph.sm {{ width:206px; }}
.st {{ position:relative; display:flex; align-items:center; justify-content:space-between;
  padding:7px 14px 3px; font-size:8pt; color:{INK}; font-weight:600; }}
.notch {{ position:absolute; left:50%; transform:translateX(-50%); top:5px; width:58px; height:12px;
  background:#1a1a1a; border-radius:7px; }}
.sti i {{ margin-left:3px; }}
.b {{ padding:7px 11px 12px; display:flex; flex-direction:column; flex:1; }}
.hd {{ display:flex; align-items:center; justify-content:space-between; padding-bottom:7px;
  border-bottom:1px solid #EEECE5; margin-bottom:8px; }}
.hl {{ display:flex; align-items:center; gap:6px; font-size:10pt; font-weight:600; }}
.logo {{ width:21px; height:21px; border-radius:50%; background:{TEAL50}; color:{TEAL};
  display:flex; align-items:center; justify-content:center; font-size:12px; }}
.lv {{ font-size:8.5pt; font-weight:600; background:{TEAL50}; color:{TEAL800}; border-radius:14px;
  padding:2px 8px; }}
.t {{ font-size:13pt; font-weight:600; color:{INK}; margin:1px 0 2px; }}
.s {{ font-size:8.6pt; color:{SUB}; line-height:1.45; margin-bottom:8px; }}
.inp {{ border:1px solid #DDDBD3; border-radius:8px; padding:8px 9px; font-size:8.8pt; color:{MUTE};
  margin:4px 0; }}
.cta {{ font-size:9.6pt; font-weight:600; background:{TEAL}; color:#fff; border-radius:9px;
  padding:9px; text-align:center; margin-top:auto; }}
.btn {{ font-size:8.8pt; font-weight:600; border:1px solid #DDDBD3; background:#fff; border-radius:7px;
  padding:7px 3px; text-align:center; flex:1; color:{INK}; }}
.btnP {{ background:{TEAL}; color:#fff; border-color:{TEAL}; }}
.row {{ display:flex; gap:5px; margin:5px 0; }}
.card {{ background:{SURF}; border-radius:9px; padding:8px 9px; margin:5px 0; }}
.ocard {{ border:1px solid {LINE}; border-radius:9px; padding:8px; margin:5px 0; display:flex;
  align-items:center; gap:8px; }}
.oico {{ width:30px; height:30px; border-radius:8px; background:{TEAL50}; color:{TEAL};
  display:flex; align-items:center; justify-content:center; font-size:16px; flex:none; }}
.chip {{ display:inline-flex; align-items:center; gap:3px; font-size:8.3pt; font-weight:600;
  border-radius:7px; padding:3px 7px; background:{AMB_F}; color:{AMB_T}; }}
.chipT {{ background:{TEAL50}; color:{TEAL800}; }}
.li {{ display:flex; align-items:center; gap:8px; font-size:9pt; color:{INK}; padding:6px 0; }}
.li i {{ font-size:15px; color:{TEAL}; }}
.bord {{ border-bottom:1px solid #F2F0E9; }}
.track {{ height:6px; background:{TRACK}; border-radius:4px; overflow:hidden; margin:4px 0; }}
.fill {{ height:100%; background:{TEAL}; border-radius:4px; }}
.tab {{ display:flex; justify-content:space-around; border-top:1px solid #EEECE5; padding-top:6px;
  margin-top:8px; font-size:8pt; color:{MUTE}; }}
.tab .on {{ color:{TEAL}; }} .tab i {{ font-size:15px; display:block; margin-bottom:1px; }}
.tab span {{ text-align:center; }}
.bnW {{ display:flex; gap:7px; align-items:flex-start; background:{AMB_F}; color:{AMB_T};
  border-radius:9px; padding:8px 10px; font-size:8.3pt; line-height:1.45; }}
.bnI {{ background:{TEAL50}; color:{TEAL800}; }}
.bub {{ display:flex; gap:7px; background:{TEAL50}; border-radius:10px; padding:8px 9px; }}
.bavt {{ width:22px; height:22px; border-radius:50%; background:{TEAL}; color:#fff; flex:none;
  display:flex; align-items:center; justify-content:center; font-size:12px; }}
.cite {{ font-size:7.6pt; background:#E6F1FB; color:#185FA5; border-radius:3px; padding:0 3px; }}
.modal {{ background:rgba(0,0,0,0.35); padding:40px 14px; display:flex; align-items:center; }}
"""


def ph(inner, cls=""):
    return f'<div class="ph {cls}">{ST}<div class="b">{inner}</div></div>'


def card_screen(sid, title, inner, spec_rows, cls=""):
    rows = "".join(f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in spec_rows)
    return (f'<div class="scr">{ph(inner, cls)}'
            f'<div class="spec"><h3>{sid} · {title}</h3>'
            f'<table>{rows}</table></div></div>')


def wifi():
    return ''


# ── 화면 inner HTML ───────────────────────────────────────────
S1 = (f'<div style="flex:1;display:flex;flex-direction:column;align-items:center;'
      f'justify-content:center;text-align:center">'
      f'<div style="width:56px;height:56px;border-radius:17px;background:{TEAL50};color:{TEAL};'
      f'font-size:30px;display:flex;align-items:center;justify-content:center;margin-bottom:12px">'
      f'<i class="ti ti-heart"></i></div>'
      f'<div style="font-size:16pt;font-weight:600">마이헬스케어</div>'
      f'<div style="font-size:8.6pt;color:{SUB};margin-top:5px">내 건강정보, 똑똑한 안내와 코칭</div>'
      f'<div class="cta" style="width:100%;margin-top:24px">시작하기</div>'
      f'<div style="font-size:8.3pt;color:{MUTE};margin-top:8px">이미 계정이 있어요 · 로그인</div></div>')

S2 = (f'<div class="t">로그인</div><div class="s">간편하게 시작하세요</div>'
      f'<div style="font-size:9pt;font-weight:600;background:#FEE500;color:#3C2E00;border-radius:8px;'
      f'padding:9px;text-align:center;margin:4px 0">카카오로 시작하기</div>'
      f'<div style="font-size:9pt;font-weight:600;background:#03C75A;color:#fff;border-radius:8px;'
      f'padding:9px;text-align:center;margin:4px 0">네이버로 시작하기</div>'
      f'<div style="font-size:9pt;font-weight:600;background:#1a1a1a;color:#fff;border-radius:8px;'
      f'padding:9px;text-align:center;margin:4px 0">Apple로 시작하기</div>'
      f'<div style="display:flex;align-items:center;gap:7px;margin:8px 0"><div style="flex:1;height:1px;'
      f'background:#EEECE5"></div><span style="font-size:8pt;color:{MUTE}">또는 이메일</span>'
      f'<div style="flex:1;height:1px;background:#EEECE5"></div></div>'
      f'<div class="inp">이메일 주소</div><div class="inp">비밀번호</div>'
      f'<div class="cta">로그인</div>')

S3 = (f'<div style="font-size:9pt;color:{SUB};margin-bottom:6px"><i class="ti ti-chevron-left"></i> 본인인증</div>'
      f'<div class="t">본인확인이 필요해요</div>'
      f'<div class="s">안전한 건강 서비스를 위해 휴대폰 본인인증을 진행합니다.</div>'
      f'<div class="inp">이름</div><div class="inp">생년월일 8자리</div><div class="inp">휴대폰 번호</div>'
      f'<div style="font-size:8.4pt;color:{SUB};margin:7px 0 4px">인증수단</div>'
      f'<div class="row" style="margin:0">'
      f'<span class="btn btnP">PASS</span><span class="btn">카카오</span><span class="btn">통신사</span></div>'
      f'<div class="cta">인증 요청</div>')

S4 = (f'<div class="t">약관 동의</div><div class="s">서비스 이용을 위해 동의가 필요해요.</div>'
      f'<div style="display:flex;align-items:center;gap:8px;font-size:9.5pt;font-weight:600;'
      f'background:{SURF};border-radius:8px;padding:9px 10px;margin-bottom:4px">'
      f'<i class="ti ti-square-check" style="font-size:17px;color:{TEAL}"></i>전체 동의</div>'
      f'<div class="li bord"><i class="ti ti-square-check"></i><span style="flex:1">(필수) 서비스 이용약관</span></div>'
      f'<div class="li bord"><i class="ti ti-square-check"></i><span style="flex:1">(필수) 개인정보 수집·이용</span></div>'
      f'<div class="li bord"><i class="ti ti-square-check"></i><span style="flex:1">(필수) 민감정보(건강) 처리</span></div>'
      f'<div class="li bord"><i class="ti ti-square" style="color:#C4C2B8"></i>'
      f'<span style="flex:1;color:{SUB}">(선택) 위치정보 이용</span></div>'
      f'<div class="li"><i class="ti ti-square" style="color:#C4C2B8"></i>'
      f'<span style="flex:1;color:{SUB}">(선택) 마케팅·푸시 수신</span></div>'
      f'<div class="cta">동의하고 계속</div>')

S5 = (f'<div class="t">건강 데이터 연결</div>'
      f'<div class="s">검진·진료 기록을 연결하면 내 상황에 맞는 안내를 받아요. <b style="color:{SUB}">(선택)</b></div>'
      f'<div class="ocard"><div class="oico"><i class="ti ti-building-hospital"></i></div>'
      f'<div style="flex:1"><div style="font-size:9pt;font-weight:600">국민건강보험공단</div>'
      f'<div style="font-size:8pt;color:{MUTE}">검진·진료·투약</div></div><span class="chip chipT">연결</span></div>'
      f'<div class="ocard"><div class="oico"><i class="ti ti-device-watch"></i></div>'
      f'<div style="flex:1"><div style="font-size:9pt;font-weight:600">측정기기·웨어러블</div>'
      f'<div style="font-size:8pt;color:{MUTE}">혈압계·체중계·워치</div></div><span class="chip chipT">연결</span></div>'
      f'<div class="ocard"><div class="oico"><i class="ti ti-file-text"></i></div>'
      f'<div style="flex:1"><div style="font-size:9pt;font-weight:600">검진결과지 사진</div>'
      f'<div style="font-size:8pt;color:{MUTE}">촬영 불러오기(OCR)</div></div><span class="chip chipT">연결</span></div>'
      f'<div style="font-size:8.3pt;color:{MUTE};text-align:center;margin-top:auto">나중에 하기 · 연결 없이도 일반 안내 가능</div>')

S6 = (f'<div style="font-size:9pt;color:{SUB};margin-bottom:6px"><i class="ti ti-chevron-left"></i> 공단 간편인증</div>'
      f'<div class="t">인증수단 선택</div><div class="s">건강정보를 안전하게 불러올 방법을 골라주세요.</div>'
      f'<div class="li bord"><i class="ti ti-message-circle" style="color:#FBC02D"></i>'
      f'<span style="flex:1">카카오 인증</span><i class="ti ti-chevron-right" style="font-size:13px;color:{MUTE}"></i></div>'
      f'<div class="li bord"><i class="ti ti-circle" style="color:#03C75A"></i>'
      f'<span style="flex:1">네이버 인증</span><i class="ti ti-chevron-right" style="font-size:13px;color:{MUTE}"></i></div>'
      f'<div class="li bord"><i class="ti ti-shield-lock"></i>'
      f'<span style="flex:1">PASS(통신사)</span><i class="ti ti-chevron-right" style="font-size:13px;color:{MUTE}"></i></div>'
      f'<div class="li"><i class="ti ti-certificate" style="color:{SUB}"></i>'
      f'<span style="flex:1">공동·금융 인증서</span><i class="ti ti-chevron-right" style="font-size:13px;color:{MUTE}"></i></div>'
      f'<div class="cta">선택한 방법으로 인증</div>')

S7 = (f'<div class="t">가져올 정보 동의</div><div class="s">다음 건강정보를 안전하게 불러옵니다.</div>'
      f'<div class="li bord"><i class="ti ti-square-check"></i>'
      f'<span style="flex:1">건강검진 결과 (혈압·혈당·BMI)</span></div>'
      f'<div class="li"><i class="ti ti-square-check"></i><span style="flex:1">진료·투약 내역</span></div>'
      f'<div class="bnI" style="margin-top:8px"><i class="ti ti-lock" style="font-size:14px"></i>'
      f'<div>민감정보는 <b>암호화 보관</b>, AI 분석엔 <b>비식별 밴드 라벨만</b> 사용'
      f'(원시수치·진단명 미전송). 일부 처리는 <b>국외 AI 경유 가능</b> — 동의 시.</div></div>'
      f'<div class="cta">동의하고 가져오기</div>')

S8 = (f'<div style="text-align:center;flex:1;display:flex;flex-direction:column">'
      f'<div style="width:54px;height:54px;border-radius:50%;background:{TEAL50};display:flex;'
      f'align-items:center;justify-content:center;margin:14px auto 10px">'
      f'<i class="ti ti-circle-check" style="font-size:30px;color:{TEAL}"></i></div>'
      f'<div style="font-size:13pt;font-weight:600">연결 완료!</div>'
      f'<div class="s" style="margin:5px 0 10px">이 정보로 더 정확한 안내를 드릴게요.</div>'
      f'<div style="border:1px solid {LINE};border-radius:10px;padding:10px;text-align:left">'
      f'<div style="display:flex;justify-content:space-between;font-size:9pt;padding:4px 0">'
      f'<span style="color:{SUB}">건강검진</span><span style="font-weight:600">3건</span></div>'
      f'<div style="display:flex;justify-content:space-between;font-size:9pt;padding:4px 0;border-top:1px solid #F2F0E9">'
      f'<span style="color:{SUB}">진료·투약</span><span style="font-weight:600">12건</span></div>'
      f'<div style="display:flex;justify-content:space-between;font-size:9pt;padding:4px 0;border-top:1px solid #F2F0E9">'
      f'<span style="color:{SUB}">최근 혈압</span><span style="font-weight:600;color:{AMB_I}">주의</span></div></div>'
      f'<div class="cta">시작하기</div></div>')

S9 = (f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:9px">'
      f'<div><div style="font-size:8.3pt;color:{MUTE}">안녕하세요</div>'
      f'<div style="font-size:11pt;font-weight:600">김건강 님</div></div>'
      f'<div class="logo" style="width:28px;height:28px;font-size:15px"><i class="ti ti-user"></i></div></div>'
      f'<div style="display:flex;align-items:center;gap:7px;border:1px solid #DDDBD3;border-radius:10px;'
      f'padding:9px;color:{MUTE};font-size:8.8pt"><i class="ti ti-search" style="font-size:15px"></i>건강에 대해 물어보세요</div>'
      f'<div class="bnW" style="margin:8px 0"><i class="ti ti-activity" style="font-size:16px;color:{AMB_I}"></i>'
      f'<div><div style="font-weight:600">내 혈압 · 주의 구간</div>재측정과 생활관리가 권장돼요</div></div>'
      f'<div class="row" style="margin:2px 0 0">'
      f'<div style="flex:1;border:1px solid {LINE};border-radius:10px;padding:11px 6px;text-align:center">'
      f'<i class="ti ti-stethoscope" style="font-size:19px;color:{TEAL}"></i>'
      f'<div style="font-size:8.8pt;font-weight:600;margin-top:4px">건강 질문</div></div>'
      f'<div style="flex:1;border:1px solid {LINE};border-radius:10px;padding:11px 6px;text-align:center">'
      f'<i class="ti ti-flame" style="font-size:19px;color:{TEAL}"></i>'
      f'<div style="font-size:8.8pt;font-weight:600;margin-top:4px">실천 코칭</div></div></div>'
      f'<div class="tab"><span class="on"><i class="ti ti-home"></i>홈</span>'
      f'<span><i class="ti ti-message"></i>코치</span><span><i class="ti ti-chart-bar"></i>진척</span>'
      f'<span><i class="ti ti-settings"></i>설정</span></div>')

# 의료 RAG
M1 = (f'<div class="hd"><div class="hl"><div class="logo"><i class="ti ti-heart"></i></div>건강 질문</div></div>'
      f'<div style="text-align:right;margin-bottom:6px"><span style="background:{TEAL};color:#fff;'
      f'border-radius:10px;padding:6px 9px;font-size:8.7pt;display:inline-block">혈압이 높게 나왔어요</span></div>'
      f'<div class="card" style="font-size:8.7pt;line-height:1.5">일시적으로 높을 수 있어 다시 측정해 확인하세요 '
      f'<span class="cite">1</span>. 두통·가슴통증이 함께면 바로 진료가 필요합니다 <span class="cite">2</span>.</div>'
      f'<div style="margin:5px 0"><span class="chip chipT"><i class="ti ti-lock"></i>개인맥락 반영됨 — 혈압=경고</span></div>'
      f'<div class="bnW"><i class="ti ti-bulb" style="font-size:15px;color:{AMB_I}"></i>'
      f'<div style="flex:1">생활 속 실천이 궁금하세요?</div></div>'
      f'<div class="cta" style="margin-top:7px"><i class="ti ti-flame"></i> 실천 코칭 받기</div>')

M2 = (f'<div style="font-size:9pt;color:{SUB};margin-bottom:6px"><i class="ti ti-chevron-left"></i> 가까운 곳 찾기</div>'
      f'<div class="t" style="font-size:12pt">병원·약국 안내</div>'
      f'<div class="bnW" style="background:{DNG_F};color:{DNG_T};margin-bottom:6px">'
      f'<i class="ti ti-urgent" style="font-size:15px"></i><div>응급 증상이면 119 · 응급실로 바로 연락하세요</div></div>'
      f'<div class="inp" style="color:{INK}"><i class="ti ti-map-pin" style="color:{TEAL}"></i> 동네 입력 (예: 역삼동)</div>'
      f'<div class="ocard"><div class="oico"><i class="ti ti-building-hospital"></i></div>'
      f'<div style="flex:1"><div style="font-size:9pt;font-weight:600">병원 찾기</div>'
      f'<div style="font-size:8pt;color:{MUTE}">심평원·공공데이터</div></div>'
      f'<i class="ti ti-external-link" style="color:{MUTE}"></i></div>'
      f'<div class="ocard"><div class="oico"><i class="ti ti-pill"></i></div>'
      f'<div style="flex:1"><div style="font-size:9pt;font-weight:600">약국 찾기</div>'
      f'<div style="font-size:8pt;color:{MUTE}">약학정보원·휴일지킴이</div></div>'
      f'<i class="ti ti-external-link" style="color:{MUTE}"></i></div>'
      f'<div style="font-size:7.8pt;color:{MUTE};text-align:center;margin-top:auto">중립 공공정보 · 특정 병원 추천 아님</div>')

# 코칭 온보딩
C1 = (f'<div style="font-size:9pt;color:{SUB};margin-bottom:6px"><i class="ti ti-chevron-left"></i> 실천 코칭</div>'
      f'<div class="t">어느 쪽을 도와드릴까요?</div><div class="s">원하는 코칭 방향을 골라주세요.</div>'
      f'<div class="ocard" style="border-color:{TEAL}"><div class="oico"><i class="ti ti-salad"></i></div>'
      f'<div style="flex:1"><div style="font-size:9.5pt;font-weight:600">식단</div>'
      f'<div style="font-size:8pt;color:{MUTE}">저염·균형 잡힌 식생활</div></div>'
      f'<i class="ti ti-check" style="color:{TEAL}"></i></div>'
      f'<div class="ocard" style="opacity:.55"><div class="oico"><i class="ti ti-run"></i></div>'
      f'<div style="flex:1"><div style="font-size:9.5pt;font-weight:600">운동</div>'
      f'<div style="font-size:8pt;color:{MUTE}">준비 중</div></div></div>'
      f'<div class="ocard" style="opacity:.55"><div class="oico"><i class="ti ti-bed"></i></div>'
      f'<div style="flex:1"><div style="font-size:9.5pt;font-weight:600">생활습관</div>'
      f'<div style="font-size:8pt;color:{MUTE}">준비 중</div></div></div>'
      f'<div class="cta">식단 코칭 시작</div>')

C2 = (f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:9px">'
      f'<i class="ti ti-chevron-left" style="color:{SUB}"></i>'
      f'<div style="flex:1"><div class="track" style="margin:0"><div class="fill" style="width:33%"></div></div></div>'
      f'<span style="font-size:8.3pt;color:{MUTE}">1/3</span></div>'
      f'<div class="t" style="font-size:13.5pt">평소 외식·배달 빈도는?</div>'
      f'<div style="margin-top:14px">'
      f'<div class="inp" style="color:{INK};text-align:center;border-color:{TEAL};color:{TEAL800};font-weight:600">거의 매일</div>'
      f'<div class="inp" style="color:{INK};text-align:center">주 2~3회</div>'
      f'<div class="inp" style="color:{INK};text-align:center">드뭄</div></div>'
      f'<div style="font-size:8.2pt;color:{MUTE};text-align:center;margin-top:auto">한 번에 한 질문씩 · 이전으로 수정 가능</div>')

C3 = (f'<div class="t">코칭 개인화 동의</div>'
      f'<div class="s">내 건강 신호를 반영하면 더 맞춤한 코칭을 받아요. (선택)</div>'
      f'<div class="li bord"><i class="ti ti-square-check"></i>'
      f'<span style="flex:1">밴드·추세·웨어러블 신호 반영</span></div>'
      f'<div class="li bord"><i class="ti ti-square-check"></i>'
      f'<span style="flex:1">매일 체크인 푸시 알림 받기</span></div>'
      f'<div class="bnI" style="margin-top:8px"><i class="ti ti-shield-check" style="font-size:14px"></i>'
      f'<div>코칭에도 <b>비식별 라벨만</b> 사용 · 경고밴드면 진료 우선 · 동의는 언제든 철회 가능</div></div>'
      f'<div style="font-size:8pt;color:{MUTE};margin-top:7px">동의 안 해도 일반 식단 코칭은 가능해요</div>'
      f'<div class="cta">동의하고 플랜 받기</div>')

C4 = (f'<div class="hd"><div class="hl"><div class="logo"><i class="ti ti-heart"></i></div>마이헬스케어 코치</div>'
      f'<span class="lv"><i class="ti ti-star"></i>Lv.1</span></div>'
      f'<div style="font-size:12pt;font-weight:600">2주 저염 식단 플랜</div>'
      f'<div style="font-size:8.4pt;color:{SUB};margin:2px 0 7px">혈압=주의 · 외식 잦음 기준</div>'
      f'<div class="li bord"><i class="ti ti-square"></i>국물 반 남기기</div>'
      f'<div class="li bord"><i class="ti ti-square"></i>라면 주 1회로 줄이기</div>'
      f'<div class="li"><i class="ti ti-square"></i>채소 한 접시 추가</div>'
      f'<div style="font-size:7.8pt;color:{MUTE};margin:5px 0 7px">근거 [1] 식약처 [2] 보건소</div>'
      f'<div class="bnW"><i class="ti ti-alert-triangle" style="font-size:14px"></i>'
      f'<div>혈압 주의 — 식이 조절은 진료와 병행하세요</div></div>'
      f'<div class="cta" style="margin-top:8px">2주 챌린지 시작</div>')

C5 = (f'<div class="hd"><div class="hl"><div class="logo"><i class="ti ti-heart"></i></div>마이헬스케어 코치</div>'
      f'<span class="lv"><i class="ti ti-star"></i>Lv.2</span></div>'
      f'<div style="display:flex;align-items:center;gap:9px;background:{AMB_F};border-radius:10px;padding:9px 11px">'
      f'<i class="ti ti-flame" style="font-size:25px;color:{AMB_I}"></i>'
      f'<div><div style="font-size:13pt;font-weight:600;color:{AMB_T}">5일 연속</div>'
      f'<div style="font-size:8.3pt;color:#854F0B">이번 주 4/7 실천</div></div></div>'
      f'<div class="card"><div style="font-size:8.7pt;font-weight:600;margin-bottom:5px">오늘의 체크인 · 국물 반 남기기</div>'
      f'<div class="row" style="margin:0"><span class="btn btnP">네</span><span class="btn">아니오</span>'
      f'<span class="btn">외식 안 함</span></div></div>'
      f'<div style="font-size:8.4pt;color:{SUB};margin:6px 0 0">2주 챌린지 · 9/14일</div>'
      f'<div class="track"><div class="fill" style="width:64%"></div></div>'
      f'<div style="display:flex;justify-content:space-between;align-items:center;background:{TEAL50};'
      f'border-radius:9px;padding:8px 10px;margin-top:7px;color:{TEAL800};font-size:8.8pt;font-weight:600">'
      f'<span><i class="ti ti-message"></i> 코치와 대화하기</span><i class="ti ti-chevron-right"></i></div>'
      f'<div class="tab"><span class="on"><i class="ti ti-home"></i>홈</span><span><i class="ti ti-message"></i>코치</span>'
      f'<span><i class="ti ti-chart-bar"></i>진척</span><span><i class="ti ti-settings"></i>설정</span></div>')

C6 = (f'<div style="font-size:9pt;color:{SUB};margin-bottom:7px"><i class="ti ti-chevron-left"></i> 오늘의 체크인</div>'
      f'<div class="t" style="font-size:13pt">국물 반 남기셨어요?</div>'
      f'<div class="row" style="margin:8px 0 10px"><span class="btn btnP"><i class="ti ti-check"></i> 네</span>'
      f'<span class="btn">아니오</span><span class="btn">외식 안 함</span></div>'
      f'<div class="row" style="margin:0 0 8px"><span class="chip"><i class="ti ti-flame"></i>5일</span>'
      f'<span class="chip"><i class="ti ti-coin"></i>+10P</span><span class="chip"><i class="ti ti-award"></i>배지</span></div>'
      f'<div class="bub"><div class="bavt"><i class="ti ti-heart"></i></div>'
      f'<div style="font-size:8.7pt;line-height:1.5;color:{TEAL800}">좋아요! 이번 주 4번째 실천이에요. 이 페이스면 충분해요.</div></div>'
      f'<div class="row" style="margin-top:auto"><span class="btn btnP">계속</span>'
      f'<span class="btn">코치와 더 얘기</span></div>')

C7 = (f'<div class="hd"><div class="hl"><div class="logo"><i class="ti ti-heart"></i></div>코치</div></div>'
      f'<div class="bub" style="margin-bottom:6px"><div class="bavt"><i class="ti ti-heart"></i></div>'
      f'<div style="font-size:8.6pt;line-height:1.5;color:{TEAL800}">요즘 어떤 점이 어려우세요?</div></div>'
      f'<div style="text-align:right;margin-bottom:6px"><span style="background:{TEAL};color:#fff;'
      f'border-radius:10px;padding:6px 9px;font-size:8.5pt;display:inline-block">외식이 너무 잦아요</span></div>'
      f'<div class="bub"><div class="bavt"><i class="ti ti-heart"></i></div>'
      f'<div style="font-size:8.6pt;line-height:1.5;color:{TEAL800}">그럼 이번 주는 \'국물만 줄이기\' 하나로 단순화해볼까요?</div></div>'
      f'<div style="margin:7px 0"><span class="chip" style="background:#fff;border:1px solid {LINE};color:{SUB}">플랜 너무 어려워요</span>'
      f'<span class="chip" style="background:#fff;border:1px solid {LINE};color:{SUB}">외식 잦아요</span></div>'
      f'<div class="inp" style="margin-top:auto">메시지 입력…</div>')

C8 = (f'<div class="hd"><div class="hl">진척</div><span class="lv">이번 주</span></div>'
      f'<div class="row"><div class="card" style="flex:1;text-align:center;margin:0">'
      f'<div style="font-size:15pt;font-weight:600;color:{TEAL}">71%</div>'
      f'<div style="font-size:8pt;color:{MUTE}">실천율</div></div>'
      f'<div class="card" style="flex:1;text-align:center;margin:0">'
      f'<div style="font-size:15pt;font-weight:600;color:{TEAL}">6일</div>'
      f'<div style="font-size:8pt;color:{MUTE}">최장 스트릭</div></div></div>'
      f'<div style="font-size:8.4pt;color:{SUB};margin:8px 0 3px">최근 7일</div>'
      f'<div style="display:flex;gap:4px;align-items:flex-end;height:46px">'
      + "".join(f'<div style="flex:1;background:{TEAL if h>20 else TRACK};height:{h}px;border-radius:3px"></div>'
                for h in [30, 38, 20, 42, 36, 44, 28]) +
      f'</div><div style="font-size:8.3pt;color:{SUB};margin-top:8px"><i class="ti ti-award" style="color:{AMB_I}"></i> '
      f'배지 2개 · 다음: 일주일 연속</div>'
      f'<div class="cta" style="background:{SURF};color:{TEAL800}">보상·배지 보기</div>')

C9 = (f'<div class="hd"><div class="hl">배지 · 레벨</div><span class="lv"><i class="ti ti-star"></i>Lv.2</span></div>'
      f'<div style="font-size:8.3pt;color:{SUB}">Lv.2 · 다음까지 40P</div>'
      f'<div class="track"><div class="fill" style="width:60%"></div></div>'
      f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin:8px 0">'
      f'<div class="card" style="text-align:center;margin:0;padding:8px 4px"><i class="ti ti-award" style="font-size:16px;color:{AMB_I}"></i>'
      f'<div style="font-size:7.8pt;margin-top:2px">입문 ✓</div></div>'
      f'<div class="card" style="text-align:center;margin:0;padding:8px 4px"><i class="ti ti-flame" style="font-size:16px;color:{AMB_I}"></i>'
      f'<div style="font-size:7.8pt;margin-top:2px">작심삼일 ✓</div></div>'
      f'<div class="card" style="text-align:center;margin:0;padding:8px 4px;opacity:.4"><i class="ti ti-calendar" style="font-size:16px"></i>'
      f'<div style="font-size:7.8pt;margin-top:2px">일주일</div></div>'
      f'<div class="card" style="text-align:center;margin:0;padding:8px 4px;opacity:.4"><i class="ti ti-trophy" style="font-size:16px"></i>'
      f'<div style="font-size:7.8pt;margin-top:2px">완주</div></div></div>'
      f'<div style="text-align:center;font-size:8.4pt;color:{SUB};background:{SURF};border-radius:8px;padding:7px;margin-top:auto">'
      f'<i class="ti ti-users"></i> 이번 주 상위 18% · 익명</div>')

C10 = (f'<div style="text-align:center;flex:1;display:flex;flex-direction:column">'
       f'<div style="width:52px;height:52px;border-radius:50%;background:{TEAL50};display:flex;'
       f'align-items:center;justify-content:center;margin:10px auto 8px">'
       f'<i class="ti ti-trophy" style="font-size:28px;color:{TEAL}"></i></div>'
       f'<div style="font-size:13pt;font-weight:600">2주 챌린지 완주!</div>'
       f'<div class="s" style="margin:4px 0 8px">꾸준함이 멋져요</div>'
       f'<div class="row" style="justify-content:center"><span class="chip chipT"><i class="ti ti-medal"></i>완주 배지</span>'
       f'<span class="chip chipT"><i class="ti ti-star"></i>Lv.2 달성</span></div>'
       f'<div class="row" style="margin:8px 0"><div class="card" style="flex:1;text-align:center;margin:0">'
       f'<div style="font-size:14pt;font-weight:600;color:{TEAL}">71%</div><div style="font-size:7.8pt;color:{MUTE}">실천율</div></div>'
       f'<div class="card" style="flex:1;text-align:center;margin:0"><div style="font-size:14pt;font-weight:600;color:{TEAL}">6일</div>'
       f'<div style="font-size:7.8pt;color:{MUTE}">최장 스트릭</div></div></div>'
       f'<div style="font-size:8.5pt;font-weight:600;color:{SUB};margin-bottom:5px">다음 목표를 정해볼까요?</div>'
       f'<div class="row" style="margin:0"><span class="btn btnP">4주 챌린지</span><span class="btn">새 트랙</span></div></div>')

# 안전·시스템·알림
C11 = (f'<div class="modal" style="flex:1">'
       f'<div style="background:#fff;border-radius:16px;padding:16px;width:100%">'
       f'<div style="width:42px;height:42px;border-radius:50%;background:{DNG_F};display:flex;'
       f'align-items:center;justify-content:center;margin:0 auto 9px">'
       f'<i class="ti ti-alert-triangle" style="font-size:22px;color:{DNG_T}"></i></div>'
       f'<div style="text-align:center;font-size:11.5pt;font-weight:600">진료가 우선이에요</div>'
       f'<div style="text-align:center;font-size:8.6pt;color:{SUB};line-height:1.5;margin:6px 0 11px">'
       f'최근 혈압이 경고 구간으로 확인됐어요. 코칭은 잠시 멈추고 의료진 상담을 권합니다.</div>'
       f'<div class="cta" style="margin:0"><i class="ti ti-map-pin"></i> 가까운 병원 찾기</div>'
       f'<div style="text-align:center;font-size:8.4pt;color:{MUTE};margin-top:8px">나중에 · 코칭 계속</div></div></div>')

C13 = (f'<div class="hd"><div class="hl">설정</div></div>'
       f'<div class="li bord"><i class="ti ti-bell"></i><span style="flex:1">푸시 알림 시간</span>'
       f'<span style="font-size:8.3pt;color:{MUTE}">저녁 8시</span></div>'
       f'<div class="li bord"><i class="ti ti-shield-check"></i><span style="flex:1">개인정보 동의 관리</span>'
       f'<i class="ti ti-chevron-right" style="font-size:13px;color:{MUTE}"></i></div>'
       f'<div class="li bord"><i class="ti ti-database"></i><span style="flex:1">건강 데이터 연결</span>'
       f'<span style="font-size:8.3pt;color:{TEAL}">연결됨</span></div>'
       f'<div class="li bord"><i class="ti ti-school"></i><span style="flex:1">졸업·유지 모드</span>'
       f'<i class="ti ti-chevron-right" style="font-size:13px;color:{MUTE}"></i></div>'
       f'<div class="li"><i class="ti ti-trash" style="color:{DNG_T}"></i>'
       f'<span style="flex:1;color:{DNG_T}">동의 철회·데이터 삭제</span></div>'
       f'<div style="font-size:7.8pt;color:{MUTE};text-align:center;margin-top:auto">마이헬스케어 Phase 2 프로토타입</div>')

NPUSH = (f'<div style="flex:1;display:flex;flex-direction:column;justify-content:center;gap:9px">'
         f'<div style="background:#fff;border:1px solid {LINE};border-radius:13px;padding:10px 11px;'
         f'box-shadow:none"><div style="display:flex;align-items:center;gap:6px;font-size:8pt;color:{MUTE};margin-bottom:4px">'
         f'<div class="logo" style="width:15px;height:15px;font-size:9px"><i class="ti ti-heart"></i></div>마이헬스케어 · 지금</div>'
         f'<div style="font-size:9pt;font-weight:600">오늘 국물 반 남기셨어요?</div>'
         f'<div style="font-size:8.3pt;color:{SUB}">1초면 체크 완료 · 5일 연속 도전 중</div></div>'
         f'<div style="background:#fff;border:1px solid {LINE};border-radius:13px;padding:10px 11px">'
         f'<div style="display:flex;align-items:center;gap:6px;font-size:8pt;color:{MUTE};margin-bottom:4px">'
         f'<div class="logo" style="width:15px;height:15px;font-size:9px"><i class="ti ti-flame"></i></div>마이헬스케어 · 저녁 8:50</div>'
         f'<div style="font-size:9pt;font-weight:600">5일 연속이 곧 끊겨요</div>'
         f'<div style="font-size:8.3pt;color:{SUB}">오늘 체크인하면 이어집니다 (무비난 리마인드)</div></div>'
         f'<div style="font-size:7.8pt;color:{MUTE};text-align:center;margin-top:6px">21시 전 발송 · 정보통신망법 동의 기반</div></div>')


def scr_row(sid_title, inner, spec_rows, cls=""):
    rows = "".join(f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in spec_rows)
    return (f'<div class="scr">{ph(inner, cls)}'
            f'<div class="spec"><h3>{sid_title}</h3><table>{rows}</table></div></div>')


def sw(label, hexv, txt=INK):
    return (f'<div class="sw"><div class="chip" style="background:{hexv}"></div>'
            f'{label}<br><code style="font-size:7.6pt">{hexv}</code></div>')


SCREENS = [
    ("온보딩 · 로그인~PHR 인증", [
        ("1 스플래시", S1, [("목적", "브랜드 진입·시작/로그인 분기"), ("컴포넌트", "로고·CTA·텍스트링크"),
                          ("데이터·API", "없음 (정적)"), ("전이", "시작하기→2 · 로그인→2")]),
        ("2 로그인", S2, [("목적", "소셜·이메일 로그인 / 회원가입"), ("컴포넌트", "소셜버튼3·입력2·CTA"),
                       ("데이터·API", "OAuth(카카오·네이버·Apple) · 파트너 SSO"), ("상태", "오류=문구·재시도"), ("전이", "→3 본인인증")]),
        ("3 본인인증", S3, [("목적", "휴대폰 본인확인(건강서비스 신뢰)"), ("컴포넌트", "입력3·인증수단탭·CTA"),
                        ("데이터·API", "본인확인기관(PASS/통신사) — 외부"), ("전이", "→4 약관")]),
        ("4 약관 동의", S4, [("목적", "필수·선택 약관 동의 취득"), ("컴포넌트", "전체동의·체크리스트"),
                         ("데이터·API", "consent_ledger 저장(필수3·선택2)"), ("상태", "필수 미동의=CTA 비활성"), ("전이", "→5 PHR")]),
        ("5 PHR 연동 허브", S5, [("목적", "건강데이터 연결 경로 선택(선택)"), ("컴포넌트", "연동 카드3·건너뛰기"),
                            ("데이터·API", "공단·웨어러블(12)·OCR(13)"), ("상태", "미연동=L0 일반안내"), ("전이", "공단→6 · 건너뛰기→9")]),
        ("6 PHR 간편인증", S6, [("목적", "공단/마이데이터 간편인증 수단 선택"), ("컴포넌트", "인증수단 리스트"),
                           ("데이터·API", "공단 간편인증(카카오·네이버·PASS·인증서)"), ("전이", "→7 동의")]),
        ("7 건강정보 동의(민감)", S7, [("목적", "가져올 민감정보 범위·국외이전 동의"), ("컴포넌트", "체크리스트·고지박스"),
                              ("데이터·API", "민감정보 동의→personal_record(암호화)·bands 산출"),
                              ("컴플라이언스", "방향2/17 · LAUNCH B · 원시값 미전송"), ("전이", "→8 완료")]),
        ("8 연동 완료", S8, [("목적", "인입 결과·밴드 요약 확인"), ("컴포넌트", "체크아이콘·요약카드"),
                         ("데이터·API", "vital_rules.run → 밴드 라벨(혈압=주의)"), ("전이", "→9 홈")]),
        ("9 홈 진입", S9, [("목적", "앱 허브 — 의료/코칭 분기"), ("컴포넌트", "검색바·건강요약·바로가기2·탭바"),
                       ("데이터·API", "GET 건강요약(밴드) · 검색 진입"), ("전이", "건강질문→M1 · 실천코칭→C1")]),
    ]),
    ("의료 정보 (RAG)", [
        ("M1 의료 대화", M1, [("목적", "질문→근거기반 답변·진단 단정 0"), ("컴포넌트", "말풍선·인용[n]·개인맥락 배지·핸드오프 버튼"),
                          ("데이터·API", "POST /api/service/conversations (generate_response SSE)"),
                          ("안전", "가드레일·인용검증·I7 응급 / 핸드오프 detect §3-A"), ("전이", "코칭→C1 · 시설→M2")]),
        ("M2 시설 안내", M2, [("목적", "병원·약국 중립 안내(유인·알선 0)"), ("컴포넌트", "응급배너·지역입력·디렉터리 링크"),
                          ("데이터·API", "E-Gen·심평원·공공데이터(§5.8) · 위치=자가입력"),
                          ("컴플라이언스", "의료법 27조3항 · 특정병원 추천 금지"), ("전이", "외부 디렉터리")]),
    ]),
    ("웰니스 코칭", [
        ("C1 트랙 선택", C1, [("목적", "코칭 방향 선택(고정 아님)"), ("컴포넌트", "트랙 카드3(MVP=식단만 활성)"),
                          ("데이터·API", "wellness_router · coaching_session(track)"), ("전이", "→C2 문진")]),
        ("C2 문진", C2, [("목적", "맞춤 입력(한 번에 한 문항)"), ("컴포넌트", "진행바·질문·선택지·뒤로"),
                       ("데이터·API", "coaching intake(3문항) → 플랜 입력"), ("전이", "3문항 완료→C3")]),
        ("C3 코칭 동의", C3, [("목적", "개인신호·푸시 동의(코칭 프로파일)"), ("컴포넌트", "토글2·고지"),
                          ("데이터·API", "coaching_consent(§6-A G2) · 미동의=L0"), ("전이", "→C4 플랜")]),
        ("C4 첫 플랜·챌린지", C4, [("목적", "맞춤 플랜 제시 + 게임 진입"), ("컴포넌트", "헤더·체크리스트·근거·안전배너·CTA·Lv"),
                            ("데이터·API", "coaching_plan 생성(§4-A) · WC-C1~6 통과"), ("상태", "경고밴드=soft+진료배너(§5.4)"), ("전이", "→C5 홈")]),
        ("C5 코칭 홈(허브)", C5, [("목적", "매일 돌아오는 대시보드"), ("컴포넌트", "스트릭 히어로·체크인카드·진행바·탭바"),
                            ("데이터·API", "GET session/plan + 오늘 체크인 상태"), ("전이", "체크인→C6·코치→C7·진척→C8")]),
        ("C6 체크인", C6, [("목적", "1탭 기록 + 즉시 보상"), ("컴포넌트", "질문·버튼3·보상칩·코치말풍선"),
                        ("데이터·API", "POST coaching_checkin(done) → 스트릭·포인트·배지 + 코치 LLM(WC-C)"),
                        ("상태", "안됨=무비난 격려·단순화(§4-B.3)"), ("전이", "계속→C5·더얘기→C7")]),
        ("C7 코치 대화", C7, [("목적", "적응·문의(LLM 코치)"), ("컴포넌트", "채팅·빠른질문칩·입력"),
                          ("데이터·API", "코치 LLM (WC-C 통과) → plan 조정"), ("안전", "경고밴드 시 진료 우선·매 메시지 가드레일"), ("전이", "조정→C4 갱신")]),
        ("C8 진척·주간 요약", C8, [("목적", "동기 가시화"), ("컴포넌트", "통계카드2·주간 막대·배지요약"),
                            ("데이터·API", "GET checkin 집계(adherence·streak)"), ("전이", "→C9 보상")]),
        ("C9 배지·레벨·랭킹", C9, [("목적", "수집·등급 동기"), ("컴포넌트", "레벨게이지·배지그리드·익명랭킹"),
                            ("데이터·API", "포인트·배지·레벨(coaching_plan adherence_state)"),
                            ("안전", "보상=행동연동·경고밴드 톤완화(§4-B.4)"), ("전이", "—")]),
        ("C10 완주·다음 목표", C10, [("목적", "마일스톤 + 재참여 플라이휠"), ("컴포넌트", "트로피·배지·통계·다음목표 버튼"),
                              ("데이터·API", "완주 판정(실천율 70%+) · 다음 챌린지"), ("상태", "미완주=무비난 재도전"), ("전이", "다음목표→C4·졸업→C13")]),
    ]),
    ("안전 · 시스템 · 알림", [
        ("C11 진료 에스컬레이션", C11, [("목적", "코칭 중 경고/응급 밴드 → 진료 우선"), ("컴포넌트", "모달·병원찾기 CTA"),
                                ("데이터·API", "밴드 동적 재평가(§4-B.7) WC-C3/C4"), ("상태", "응급=119·코칭 차단(I7)"), ("전이", "→M2 시설안내")]),
        ("C13 설정", C13, [("목적", "동의·푸시·졸업·삭제권"), ("컴포넌트", "알림시간·동의관리·연결·졸업·삭제"),
                        ("데이터·API", "consent 철회 → 즉시 L0 · conversation_id 캐스케이드 삭제"), ("전이", "각 상세")]),
        ("N1·N2 푸시", NPUSH, [("목적", "저녁 체크인 큐 + 스트릭-세이버"), ("컴포넌트", "알림 카드2"),
                            ("데이터·API", "FCM/APNs · ML 발송시간(§4-B.10)"),
                            ("컴플라이언스", "정보통신망법 동의·21~08 제한·문구 WC-C1"), ("전이", "탭→C6 체크인")]),
    ]),
]


DS = (f'<section class="sec0"><h2>1. 디자인 시스템</h2>'
      f'<h3>컬러 토큰</h3><div class="tok">'
      + sw("Primary(틸)", TEAL) + sw("Primary 50", TEAL50) + sw("Primary 800", TEAL800)
      + sw("주의(앰버)", AMB_I) + sw("앰버 배경", AMB_F) + sw("위험(레드)", DNG_T)
      + sw("본문 잉크", INK) + sw("보조", SUB) + sw("힌트", MUTE) + sw("라인", LINE) + sw("서피스", SURF)
      + f'</div><p style="font-size:8.6pt;color:{SUB}">브랜드 = 헬스 틸. 상태색: 주의=앰버, 경고·위험=레드, 정보=틸 50. '
      f'밴드(안정/주의/경고)와 게이미피케이션 보상(앰버)을 색으로 분리.</p>'
      f'<h3>타이포 · 간격 · 라운드</h3>'
      f'<table><tr><th>토큰</th><th>값</th><th>용도</th></tr>'
      f'<tr><td>화면 타이틀</td><td>16px / 600</td><td>각 화면 제목</td></tr>'
      f'<tr><td>본문</td><td>13px / 400</td><td>카드·리스트</td></tr>'
      f'<tr><td>보조·캡션</td><td>11~12px</td><td>설명·메타</td></tr>'
      f'<tr><td>라운드</td><td>8 · 12 · 16 · 24px</td><td>버튼·카드·모달·기기</td></tr>'
      f'<tr><td>간격</td><td>4 · 8 · 12px</td><td>컴포넌트 내부·사이</td></tr></table>'
      f'<h3>컴포넌트 라이브러리</h3><p style="font-size:9pt">버튼(primary 틸 / secondary 아웃라인) · 입력 필드 · '
      f'카드(서피스/아웃라인) · 칩(보상 앰버 / 틸) · 리스트 항목 · 체크·토글 · 진행바 · 배지·레벨 게이지 · '
      f'하단 탭바 · 배너(정보 틸 / 주의 앰버 / 위험 레드) · 코치 말풍선 · 인용 [n] · 모달.</p></section>')

IA = ('<section><h2>2. 정보구조 · 내비게이션</h2>'
      '<p>온보딩 후 <b>홈(9)</b>이 허브. 홈에서 <b>의료 질문(M1)</b>과 <b>실천 코칭(C1~)</b>으로 분기. '
      '코칭 진입 후엔 <b>코칭 홈(C5)</b>이 일일 허브이며 하단 탭(홈·코치·진척·설정)으로 이동. '
      '경고/응급 안전 레이어(C11·M2)는 어느 화면에서든 최상위로 끼어든다.</p>'
      '<table><tr><th>레벨</th><th>구성</th></tr>'
      '<tr><td>진입</td><td>스플래시 → 로그인 → 본인인증 → 약관 → PHR 연동 → 홈</td></tr>'
      '<tr><td>홈 허브</td><td>건강 질문(RAG) · 실천 코칭 · 내 건강요약(밴드)</td></tr>'
      '<tr><td>코칭 탭</td><td>홈(C5) · 코치(C7) · 진척(C8·C9) · 설정(C13)</td></tr>'
      '<tr><td>전역 안전</td><td>진료 에스컬레이션(C11) · 시설 안내(M2) — 밴드 트리거</td></tr></table></section>')

FLOW = (f'<section><h2>3. 화면 플로우</h2>'
        f'<div style="font-family:Consolas,monospace;font-size:8.6pt;line-height:1.9;background:{SURF};'
        f'border-radius:8px;padding:12px;white-space:pre-wrap">'
        f'<b>온보딩</b>  1 스플래시 → 2 로그인 → 3 본인인증 → 4 약관 → 5 PHR허브 → 6 간편인증 → 7 민감정보동의 → 8 완료 → 9 홈\n'
        f'<b>허브</b>    9 홈 ┬ 건강질문 → M1 의료대화 ─(핸드오프)→ C1 코칭   └ 시설 → M2\n'
        f'<b>온보딩</b>  C1 트랙 → C2 문진 → C3 동의 → C4 플랜·챌린지 → C5 홈\n'
        f'<b>일일</b>    N1/N2 푸시 → C6 체크인(1탭) → 보상 → 코치 적응 → C5 갱신\n'
        f'<b>완결</b>    C8 진척 → C10 완주(실천율 70%+) → 다음목표 → C4 (새 챌린지)\n'
        f'<b>안전</b>    (전역) 경고/응급 밴드 → C11 진료 에스컬레이션 → M2 / 응급 119</div></section>')

HANDOFF = ('<section><h2>5. 개발 핸드오프</h2>'
           '<h3>데이터 모델</h3>'
           '<table><tr><th>테이블</th><th>핵심 컬럼</th><th>비고</th></tr>'
           '<tr><td>coaching_session</td><td>session_id·conversation_id·track·band_at_start·consent_personal</td><td>mig 018(신규)</td></tr>'
           '<tr><td>coaching_plan</td><td>plan_id·items_json·target_period·compliance_action·original_items_json·adherence_state·streak_count</td><td>mig 018</td></tr>'
           '<tr><td>coaching_checkin</td><td>checkin_id·plan_id·item_key·done·ts</td><td>실천 bool만</td></tr>'
           '<tr><td>analytics_events</td><td>event_name + props_json(track·topic·reason)</td><td>015 재사용·스키마변경 0</td></tr>'
           '<tr><td>personal_record / consent</td><td>암호화 건강데이터 · 동의원장</td><td>017+ · 방향2</td></tr></table>'
           '<h3>엔드포인트</h3>'
           '<table><tr><th>API</th><th>용도</th></tr>'
           '<tr><td>POST /api/service/conversations</td><td>의료 RAG 답변(SSE) · 핸드오프 메타 동봉</td></tr>'
           '<tr><td>POST /api/rag/feedback</td><td>👍/👎 명시 피드백</td></tr>'
           '<tr><td>GET /api/rag/admin/*</td><td>운영 어드민 집계(기존)</td></tr>'
           '<tr><td>(신규) wellness_router</td><td>룰 분기 medical/wellness</td></tr>'
           '<tr><td>(신규) coaching plan/checkin CRUD</td><td>P2~ 플랜·체크인·보상</td></tr></table>'
           '<h3>환경 플래그</h3><p style="font-size:9pt"><code>WELLNESS_ROUTER_ENABLED</code>(P1) · '
           '<code>COACHING_PERSONAL_PROFILE</code>(P2) · <code>PERSONAL_SIGNAL_TO_LLM</code> · '
           '<code>ALLOW_CROSS_BORDER_PERSONAL</code> — 전부 기본 off(fail-closed), 재배포 시 재적용 주의.</p>'
           '<h3>빌드 순서</h3>'
           '<table><tr><th>단계</th><th>산출</th><th>DB</th></tr>'
           '<tr><td>P1</td><td>룰 라우터 + 핸드오프 버튼(M1) + 감사 이벤트</td><td>변경 0</td></tr>'
           '<tr><td>P2</td><td>식단 1트랙(C1~C6) + 코칭 KB + WC-C 백스톱</td><td>mig 018</td></tr>'
           '<tr><td>P3</td><td>멀티 트랙(운동·습관) + 트랙 메뉴</td><td>—</td></tr>'
           '<tr><td>P4</td><td>지속 루프(체크인·게이미피케이션·푸시 N1/N2·재참여)</td><td>adherence_state·streak</td></tr></table>'
           '<div class="note">백스톱 <b>WC-C1~6</b>(효능표방·처방성·밴드캡·응급차단·출처·referral 중립성)은 코칭 출력의 STOP 전 필수 통과. '
           '라우터가 우회 불가.</div></section>')

COMPLY = ('<section><h2>6. 화면별 안전·컴플라이언스 게이트</h2>'
          '<table><tr><th>화면</th><th>걸리는 안전장치</th><th>근거</th></tr>'
          '<tr><td>7 민감정보 동의</td><td>비식별 라벨만 AI 투입·원시값 미전송·국외이전 동의</td><td>방향2 / 17 · LAUNCH B</td></tr>'
          '<tr><td>M1 의료 대화</td><td>진단·처방 단정 0 · 가드레일 · 인용검증 · 응급 I7</td><td>의료법 27조</td></tr>'
          '<tr><td>M2 시설 안내</td><td>중립 공공출처만 · 특정병원 추천·영리알선 금지</td><td>27조 3항 · §5.8</td></tr>'
          '<tr><td>C4 플랜 / C6·C7 코치</td><td>효능표방·처방성 차단 · 경고밴드=soft·진료 우선</td><td>WC-C1·C2·C3 · §5.4</td></tr>'
          '<tr><td>C9 보상</td><td>보상=행동연동(건강결과 비연동) · 경고밴드 톤완화</td><td>§4-B.4</td></tr>'
          '<tr><td>C11 에스컬레이션</td><td>코칭 중 밴드 악화→진료 / 응급→119·코칭 차단</td><td>WC-C3·C4 · I7</td></tr>'
          '<tr><td>N1·N2 푸시</td><td>사전동의·야간 21~08 제한·문구 효능표방 금지</td><td>정보통신망법 · WC-C1</td></tr>'
          '<tr><td>C13 설정</td><td>동의 철회 즉시 L0 · 데이터 삭제권(캐스케이드)</td><td>개인정보보호법</td></tr></table>'
          '<div class="danger"><b>출시 전 선결(LAUNCH-READINESS)</b> — A 의료법·식광법·정보통신망법 변호사 검토 · '
          'B 민감정보·국외이전·푸시 동의 시스템 · D 코칭 KB 의료검수. <b>본 시안 ≠ 출시 가능.</b></div></section>')


def render_catalog():
    out = ['<section><h2>4. 화면 카탈로그 (전체 앱)</h2>'
           '<p style="font-size:9pt;color:#5F5E5A">각 화면 = 목업 + 개발 스펙(목적·컴포넌트·데이터/API·상태·전이·안전). '
           '폰 목업은 인쇄용 라이트 테마.</p></section>']
    for group, screens in SCREENS:
        out.append(f'<section><h2 style="font-size:13pt;border-bottom-width:1px">{group}</h2>')
        cls = "sm" if "푸시" in group or "안전" in group else ""
        for sid, inner, spec in screens:
            out.append(scr_row(sid, inner, spec))
        out.append('</section>')
    return "".join(out)


def main():
    cover = (f'<div class="cover"><div class="logo"><i class="ti ti-heart"></i></div>'
             f'<h1>마이헬스케어</h1><div class="sub">전체 앱 UX/UI 시안서 · 로그인 ~ PHR 인증 ~ 코칭</div>'
             f'<div class="meta">Phase 2 프로토타입 · medical-rag-service · 2026-06-22<br>'
             f'화면 25 · 디자인 시스템 · 개발 핸드오프 · 안전 게이트<br>'
             f'<b style="color:{DNG_T}">설계 시안 — 출시 전 LAUNCH-READINESS 선결</b></div></div>')
    toc = ('<div class="toc"><h2 class="sec0">목차</h2><ol>'
           '<li>디자인 시스템</li><li>정보구조 · 내비게이션</li><li>화면 플로우</li>'
           '<li>화면 카탈로그 (온보딩 · 의료 RAG · 코칭 · 안전/시스템/알림)</li>'
           '<li>개발 핸드오프 (데이터·API·플래그·빌드순서)</li>'
           '<li>화면별 안전·컴플라이언스 게이트</li></ol></div>')
    body = cover + toc + DS + IA + FLOW + render_catalog() + HANDOFF + COMPLY
    head = ('<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont/dist/tabler-icons.min.css">'
            f"<style>.ti{{font-family:'tabler-icons'!important;font-style:normal;line-height:1}}{CSS}</style>")
    html = f"<!DOCTYPE html><html lang='ko'><head><meta charset='utf-8'>{head}</head><body>{body}</body></html>"
    out = os.path.join(HERE, "app-design.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print("WROTE", out, len(html), "bytes")


if __name__ == "__main__":
    main()
