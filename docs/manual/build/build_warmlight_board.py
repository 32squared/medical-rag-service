"""확정 디자인(Warm Light + Anticipatory) 전체 화면 보드 — 핵심 9화면.
홈(선제)·AI상담·PHR동의·코칭홈·체크인·플랜·완주·진료에스컬레이션·시설안내. headless 렌더."""
import os
HERE = os.path.dirname(os.path.abspath(__file__))

# Warm Light 토큰
BG, SURF, LINE = "#F6F4EF", "#FFFFFF", "rgba(0,0,0,.08)"
SH = "0 5px 18px rgba(0,0,0,.05)"
INK, SUB, HINT = "#232220", "rgba(35,34,32,.62)", "rgba(35,34,32,.42)"
TEAL, TEALD, TINT, TINTX = "#0E8A6B", "#0B5F4A", "rgba(14,138,107,.10)", "#0B5F4A"
AMB, AMBX, AMBBG = "#E0A23E", "#B5721A", "rgba(224,162,62,.10)"
RED, REDBG = "#C0392B", "rgba(192,57,43,.08)"

ST = ('<div class="st"><span>9:41</span><span class="r"><i class="ti ti-wifi"></i>'
      '<i class="ti ti-battery-3"></i></span></div>')

CSS = f"""
*{{margin:0;padding:0;box-sizing:border-box;-webkit-font-smoothing:antialiased}}
.ti{{font-family:'tabler-icons'!important;font-style:normal}}
body{{background:#E7E4DC;font-family:'Pretendard',sans-serif;padding:42px 36px}}
.board{{display:grid;grid-template-columns:repeat(3,372px);gap:30px 28px;width:max-content}}
.col{{display:flex;flex-direction:column;align-items:center}}
.lbl{{margin-top:14px;font-size:14px;font-weight:600;color:#3a3833;letter-spacing:-.2px}}
.lbl em{{color:#9a988f;font-weight:400;font-style:normal}}
.phone{{width:372px;height:806px;background:{BG};border-radius:44px;overflow:hidden;position:relative;
 border:1px solid rgba(0,0,0,.06);box-shadow:0 18px 50px rgba(60,50,30,.14)}}
.amb{{position:absolute;inset:0;background:
 radial-gradient(320px 280px at 80% 8%, {AMBBG}, transparent 70%),
 radial-gradient(340px 300px at 16% 40%, rgba(14,138,107,.06), transparent 70%)}}
.w{{position:relative;z-index:2;height:100%;display:flex;flex-direction:column;padding:0 24px}}
.st{{height:50px;flex:none;display:flex;align-items:center;justify-content:space-between;
 font-size:13px;font-weight:600;color:{INK};padding-top:12px;letter-spacing:.2px}}
.st .r{{display:flex;gap:6px}}
.hd{{display:flex;align-items:center;gap:11px;padding:6px 0 12px}}
.hd .bk{{font-size:20px;color:{SUB}}}
.hd .t{{font-size:16px;font-weight:600;letter-spacing:-.3px;flex:1}}
.av{{width:36px;height:36px;border-radius:50%;background:{SURF};border:1px solid {LINE};
 display:flex;align-items:center;justify-content:center;color:{SUB};font-size:18px;box-shadow:{SH}}}
.lv{{font-size:12px;font-weight:600;background:{TINT};color:{TEALD};border-radius:16px;padding:4px 11px;
 display:inline-flex;align-items:center;gap:3px}}
.t1{{font-size:20px;font-weight:600;letter-spacing:-.4px;line-height:1.3}}
.t2{{font-size:14px;color:{SUB};margin-top:4px;letter-spacing:-.2px;line-height:1.5}}
.card{{background:{SURF};border:1px solid {LINE};border-radius:20px;padding:17px;box-shadow:{SH}}}
.tag{{display:flex;align-items:center;gap:6px;font-size:11px;font-weight:600;letter-spacing:1px;
 text-transform:uppercase;color:{TEAL}}}
.tag.amb{{color:{AMBX}}}
.lead{{font-size:11.5px;font-weight:600;letter-spacing:1px;text-transform:uppercase;color:{HINT};
 display:flex;align-items:center;gap:7px;margin:6px 0 10px}}
.lead .p{{width:7px;height:7px;border-radius:50%;background:{AMB}}}
.body{{font-size:14px;line-height:1.55;color:{SUB};margin-top:8px;letter-spacing:-.2px}}
.body b{{color:{INK};font-weight:600}}
.cta{{background:{TEAL};color:#fff;border-radius:13px;height:50px;display:flex;align-items:center;
 justify-content:center;gap:7px;font-size:14.5px;font-weight:600;letter-spacing:-.3px}}
.cta.amb{{background:{AMB};color:#3A2606}}
.btn{{flex:1;border:1px solid {LINE};background:{SURF};border-radius:12px;height:46px;display:flex;
 align-items:center;justify-content:center;gap:6px;font-size:13.5px;font-weight:600;color:{INK}}}
.btn.p{{background:{TEAL};color:#fff;border-color:{TEAL}}}
.row{{display:flex;gap:8px}}
.li{{display:flex;align-items:center;gap:10px;font-size:14px;color:{INK};padding:9px 0}}
.li i{{font-size:18px;color:{TEAL}}}
.bord{{border-bottom:1px solid rgba(0,0,0,.06)}}
.prog{{height:7px;background:rgba(0,0,0,.07);border-radius:4px;overflow:hidden}}
.prog>div{{height:100%;background:{TEAL};border-radius:4px}}
.chip{{display:inline-flex;align-items:center;gap:4px;font-size:12px;font-weight:600;border-radius:9px;
 padding:6px 10px}}
.chip.a{{background:{AMBBG};color:{AMBX}}}
.chip.t{{background:{TINT};color:{TEALD}}}
.bub{{display:flex;gap:9px;margin-bottom:11px}}
.bub .a{{width:28px;height:28px;border-radius:50%;flex:none;background:{TEAL};color:#fff;display:flex;
 align-items:center;justify-content:center;font-size:15px}}
.bub .x{{background:{SURF};border:1px solid {LINE};border-radius:15px;border-top-left-radius:5px;
 padding:11px 13px;font-size:13.5px;line-height:1.55;color:{INK};box-shadow:{SH}}}
.ur{{display:flex;justify-content:flex-end;margin-bottom:11px}}
.ur .x{{background:{TEAL};color:#fff;border-radius:15px;border-top-right-radius:5px;padding:10px 13px;
 font-size:13.5px;letter-spacing:-.2px}}
.cite{{font-size:10.5px;background:{TINT};color:{TEALD};border-radius:4px;padding:1px 4px;margin-left:2px;font-weight:600}}
.sp1{{flex:1}}
.tab{{display:flex;justify-content:space-between;align-items:center;border-top:1px solid rgba(0,0,0,.06);
 padding-top:9px;margin-bottom:16px;color:{HINT};font-size:11px}}
.tab i{{font-size:21px;display:block;margin-bottom:1px}}
.tab .on{{color:{TEAL}}}.tab span{{text-align:center}}
.ask{{display:flex;align-items:center;gap:10px;background:{SURF};border:1px solid {LINE};
 border-radius:17px;padding:11px 11px 11px 15px;box-shadow:{SH}}}
.ask .ph{{flex:1;font-size:13px;color:{HINT}}}
.ask .m{{width:30px;height:30px;border-radius:50%;background:#F1EFE9;color:{SUB};display:flex;
 align-items:center;justify-content:center;font-size:15px}}
.orb{{width:50px;height:50px;border-radius:50%;flex:none;
 background:radial-gradient(circle at 38% 32%, #F2D9A0, #E0A23E 42%, #B97A1E 78%, #7A4E12);
 box-shadow:0 6px 18px rgba(224,162,62,.4)}}
.bn{{display:flex;gap:8px;align-items:flex-start;border-radius:13px;padding:11px 13px;font-size:12px;
 line-height:1.5}}
.bn.a{{background:{AMBBG};color:{AMBX}}}.bn.t{{background:{TINT};color:{TEALD}}}.bn.r{{background:{REDBG};color:{RED}}}
.bn i{{font-size:16px;flex:none}}
.modal{{position:absolute;inset:0;background:rgba(40,34,24,.28);display:flex;align-items:center;
 padding:0 22px;z-index:3}}
.mc{{background:#fff;border-radius:22px;padding:22px;width:100%;box-shadow:0 20px 50px rgba(0,0,0,.2)}}
.trophy{{width:74px;height:74px;border-radius:50%;background:{TINT};display:flex;align-items:center;
 justify-content:center;font-size:34px;color:{TEAL};margin:0 auto}}
.oico{{width:42px;height:42px;border-radius:11px;background:{TINT};color:{TEAL};display:flex;
 align-items:center;justify-content:center;font-size:21px;flex:none}}
"""

HOME = (f'{ST}<div class="hd" style="padding-bottom:8px"><div class="orb"></div>'
        f'<div style="flex:1"><div class="t2" style="margin:0">김건강님, 안 물어보셔도</div>'
        f'<div class="t1" style="font-size:19px">오늘 챙길 게 하나 있어요</div></div></div>'
        f'<div class="lead"><span class="p"></span>지금 꼭 챙기세요</div>'
        f'<div class="card" style="background:{AMBBG};border-color:rgba(224,162,62,.3)">'
        f'<div class="oico" style="background:rgba(224,162,62,.18);color:{AMBX};margin-bottom:12px"><i class="ti ti-heart-rate-monitor"></i></div>'
        f'<div class="t1" style="font-size:17px">혈압이 3일째 주의 구간이에요</div>'
        f'<div class="body">어제까지 이어졌어요. 이번 주 안에 진료를 한 번 고려해보시면 좋겠어요.</div>'
        f'<div class="body" style="font-size:11.5px;color:{HINT};margin-top:9px"><i class="ti ti-info-circle"></i> 측정 구간 기준 · 진단은 아니에요</div>'
        f'<div class="row" style="margin-top:14px"><div class="cta amb" style="flex:1;height:46px"><i class="ti ti-map-pin"></i>병원 찾기</div>'
        f'<div class="btn">내일 알려줘</div></div></div>'
        f'<div class="body" style="margin:20px 0 10px;color:{SUB};font-size:13px">이런 것도 궁금하실 수 있어요</div>'
        f'<div class="card bord" style="display:flex;align-items:center;gap:11px;padding:13px 15px;margin-bottom:8px;border-bottom:1px solid {LINE}">'
        f'<i class="ti ti-sparkles" style="color:{TEAL};font-size:17px"></i><span style="flex:1;font-size:13.5px">어제는 왜 더 높았을까요?</span><i class="ti ti-chevron-right" style="color:{HINT}"></i></div>'
        f'<div class="sp1"></div>'
        f'<div class="ask" style="margin-bottom:18px"><i class="ti ti-microphone" style="color:{HINT};font-size:16px"></i>'
        f'<span class="ph">다른 게 궁금하면 물어보세요</span><span class="m"><i class="ti ti-arrow-up"></i></span></div>')

CHAT = (f'{ST}<div class="hd"><i class="ti ti-chevron-left bk"></i><span class="t">AI 건강 상담</span></div>'
        f'<div class="ur"><div class="x">혈압이 높게 나왔어요</div></div>'
        f'<div class="bub"><div class="a"><i class="ti ti-sparkles"></i></div>'
        f'<div class="x">일시적으로 높을 수 있어요. 잠시 쉬었다 <b>다시 측정</b>해 확인해 주세요<span class="cite">1</span>. 두통·가슴통증이 함께면 바로 진료가 필요해요<span class="cite">2</span>.</div></div>'
        f'<div style="margin:0 0 12px 37px"><span class="chip t"><i class="ti ti-lock"></i>내 혈압 밴드 반영됨</span></div>'
        f'<div class="bn t" style="margin-left:37px;border:1px solid rgba(14,138,107,.2)"><i class="ti ti-flame"></i>'
        f'<div>생활 속 실천으로 이어가 볼까요? <b style="color:{TEAL}">저염 식단 코칭 →</b></div></div>'
        f'<div class="sp1"></div>'
        f'<div class="ask" style="margin-bottom:18px"><i class="ti ti-sparkles" style="color:{TEAL};font-size:17px"></i>'
        f'<span class="ph">메시지 입력</span><span class="m" style="background:{TEAL};color:#fff"><i class="ti ti-arrow-up"></i></span></div>')

PHR = (f'{ST}<div class="hd"><i class="ti ti-chevron-left bk"></i><span class="t">건강 데이터 연결</span></div>'
       f'<div class="t1" style="margin-top:8px">가져올 정보 동의</div>'
       f'<div class="t2">다음 건강정보를 안전하게 불러옵니다.</div>'
       f'<div style="margin-top:16px"><div class="li bord"><i class="ti ti-square-rounded-check"></i><span style="flex:1">건강검진 결과 <span style="color:{HINT};font-size:12px">혈압·혈당·BMI</span></span></div>'
       f'<div class="li"><i class="ti ti-square-rounded-check"></i><span style="flex:1">진료·투약 내역</span></div></div>'
       f'<div class="bn t" style="margin-top:14px"><i class="ti ti-shield-lock"></i>'
       f'<div>민감정보는 <b style="color:{TEALD}">암호화 보관</b>, AI 분석엔 <b style="color:{TEALD}">비식별 밴드 라벨만</b> 쓰여요(원시수치·진단명 미전송). 일부 처리는 국외 AI 경유 가능 — 동의 시.</div></div>'
       f'<div class="sp1"></div>'
       f'<div class="cta" style="margin-bottom:11px">간편인증으로 연결</div>'
       f'<div style="text-align:center;font-size:12.5px;color:{HINT};margin-bottom:18px">나중에 · 연결 없이도 일반 안내 가능</div>')

CHOME = (f'{ST}<div class="hd"><span class="t" style="font-size:18px;flex:1">코칭</span>'
         f'<span class="lv"><i class="ti ti-star" style="font-size:13px"></i>Lv.2</span></div>'
         f'<div class="card" style="background:{TINT};border-color:rgba(14,138,107,.18);display:flex;align-items:center;gap:16px">'
         f'<div style="text-align:center"><div style="font-size:40px;font-weight:600;color:{TEAL};line-height:1;letter-spacing:-1px">5</div>'
         f'<div style="font-size:11px;color:{TEAL};font-weight:600;margin-top:2px">일째</div></div>'
         f'<div style="flex:1"><div style="font-size:15px;font-weight:600;color:{TEALD}">연속 실천 중이에요</div>'
         f'<div style="font-size:12.5px;color:{TEAL}">이번 주 4번 · 좋은 흐름이에요</div></div>'
         f'<i class="ti ti-flame" style="font-size:24px;color:{TEAL}"></i></div>'
         f'<div style="font-size:11px;font-weight:600;letter-spacing:1px;color:{HINT};text-transform:uppercase;margin:22px 0 10px">오늘의 목표</div>'
         f'<div class="card"><div style="font-size:16.5px;font-weight:600;letter-spacing:-.3px">국물 반 남기기</div>'
         f'<div style="font-size:12.5px;color:{SUB};margin-top:2px">저염 실천 · 2주 챌린지</div>'
         f'<div class="cta" style="margin-top:14px;height:48px"><i class="ti ti-check"></i>오늘 체크인하기</div></div>'
         f'<div style="display:flex;justify-content:space-between;font-size:13px;margin:18px 2px 8px"><span style="color:{SUB};font-weight:500">2주 챌린지</span><span style="color:{SUB}"><b style="color:{TEAL}">9</b> / 14일</span></div>'
         f'<div class="prog"><div style="width:64%"></div></div>'
         f'<div class="sp1"></div>'
         f'<div class="tab"><span class="on"><i class="ti ti-home"></i>홈</span><span><i class="ti ti-message"></i>코치</span>'
         f'<span><i class="ti ti-chart-bar"></i>진척</span><span><i class="ti ti-settings"></i>설정</span></div>')

CHECK = (f'{ST}<div class="hd"><i class="ti ti-chevron-left bk"></i><span class="t">오늘의 체크인</span></div>'
         f'<div class="t1" style="font-size:22px;margin:14px 0 4px">국물 반,<br>남기셨어요?</div>'
         f'<div class="t2" style="margin-bottom:18px">2주 저염 챌린지 · 6일차</div>'
         f'<div class="row" style="margin-bottom:20px"><div class="btn p" style="height:50px"><i class="ti ti-check"></i>네</div>'
         f'<div class="btn" style="height:50px">아니오</div><div class="btn" style="height:50px">외식</div></div>'
         f'<div class="row" style="margin-bottom:16px"><span class="chip a"><i class="ti ti-flame"></i>5일 연속</span>'
         f'<span class="chip a"><i class="ti ti-coin"></i>+10P</span><span class="chip a"><i class="ti ti-award"></i>새 배지</span></div>'
         f'<div class="bub"><div class="a"><i class="ti ti-sparkles"></i></div>'
         f'<div class="x">좋아요, 5일 연속이에요! 이 페이스면 충분해요. 외식 잦은 날엔 \'국물만\' 줄여도 괜찮아요.</div></div>'
         f'<div class="sp1"></div>'
         f'<div class="row" style="margin-bottom:18px"><div class="btn p" style="height:48px">계속</div>'
         f'<div class="btn" style="height:48px">코치와 더 얘기</div></div>')

PLAN = (f'{ST}<div class="hd"><div class="oico" style="width:34px;height:34px;font-size:17px"><i class="ti ti-heart"></i></div>'
        f'<span class="t" style="font-size:14px">마이헬스케어 코치</span><span class="lv"><i class="ti ti-star" style="font-size:13px"></i>Lv.1</span></div>'
        f'<div class="t1" style="font-size:18px;margin-top:4px">2주 저염 식단 플랜</div>'
        f'<div class="t2" style="margin-bottom:6px">혈압=주의 · 외식 잦음 기준</div>'
        f'<div class="li bord"><i class="ti ti-square" style="color:{HINT}"></i>국물 반 남기기</div>'
        f'<div class="li bord"><i class="ti ti-square" style="color:{HINT}"></i>라면 주 1회로 줄이기</div>'
        f'<div class="li"><i class="ti ti-square" style="color:{HINT}"></i>채소 한 접시 추가</div>'
        f'<div style="font-size:11px;color:{HINT};margin:6px 0 11px">근거 [1] 식약처 [2] 보건소</div>'
        f'<div class="bn a"><i class="ti ti-alert-triangle"></i><div>혈압 주의 구간 — 식이 조절은 진료와 병행하세요</div></div>'
        f'<div class="sp1"></div>'
        f'<div class="cta" style="margin-bottom:18px">2주 챌린지 시작하기</div>')

DONE = (f'{ST}<div class="sp1"></div>'
        f'<div style="text-align:center"><div class="trophy"><i class="ti ti-trophy"></i></div>'
        f'<div class="t1" style="font-size:23px;margin-top:18px">2주 챌린지 완주!</div>'
        f'<div class="t2">꾸준함이 멋져요, 김건강님</div></div>'
        f'<div class="row" style="margin-top:22px"><div class="card" style="flex:1;text-align:center;padding:16px 0">'
        f'<div style="font-size:25px;font-weight:600;color:{TEAL};letter-spacing:-1px">71%</div><div style="font-size:11.5px;color:{HINT};margin-top:2px">실천율</div></div>'
        f'<div class="card" style="flex:1;text-align:center;padding:16px 0"><div style="font-size:25px;font-weight:600;color:{TEAL};letter-spacing:-1px">6일</div>'
        f'<div style="font-size:11.5px;color:{HINT};margin-top:2px">최장 스트릭</div></div></div>'
        f'<div class="bn t" style="margin-top:14px"><i class="ti ti-sparkles"></i>'
        f'<div>저염을 꾸준히 이어간 2주였어요. 혈압 안정 흐름 유지에 도움이 됐을 수 있어요.</div></div>'
        f'<div class="sp1"></div>'
        f'<div class="cta" style="margin-bottom:11px">다음 목표 정하기</div>'
        f'<div style="text-align:center;font-size:12.5px;color:{HINT};margin-bottom:18px">졸업·유지 모드로 전환</div>')

ESC = (f'{ST}<div class="sp1"></div><div class="sp1"></div>'
       f'<div class="modal"><div class="mc">'
       f'<div style="width:46px;height:46px;border-radius:50%;background:{REDBG};display:flex;align-items:center;'
       f'justify-content:center;margin:0 auto 12px"><i class="ti ti-alert-triangle" style="font-size:24px;color:{RED}"></i></div>'
       f'<div class="t1" style="font-size:18px;text-align:center">진료가 우선이에요</div>'
       f'<div class="body" style="text-align:center;margin-top:8px;color:{SUB}">최근 혈압이 경고 구간으로 확인됐어요. 코칭은 잠시 멈추고 의료진 상담을 권합니다.</div>'
       f'<div class="cta" style="margin-top:16px"><i class="ti ti-map-pin"></i>가까운 병원 찾기</div>'
       f'<div style="text-align:center;font-size:13px;color:{HINT};margin-top:12px">나중에 · 코칭 계속</div></div></div>')

FAC = (f'{ST}<div class="hd"><i class="ti ti-chevron-left bk"></i><span class="t">병원·약국 안내</span></div>'
       f'<div class="bn r" style="margin-bottom:12px"><i class="ti ti-urgent"></i><div>응급 증상이면 119·응급실로 바로 연락하세요</div></div>'
       f'<div class="ask" style="margin-bottom:12px"><i class="ti ti-map-pin" style="color:{TEAL};font-size:17px"></i><span class="ph" style="color:{INK}">동네 입력 (예: 역삼동)</span></div>'
       f'<div class="card bord" style="display:flex;align-items:center;gap:12px;border-bottom:1px solid {LINE};border-radius:16px 16px 0 0;margin-bottom:0">'
       f'<div class="oico"><i class="ti ti-building-hospital"></i></div><div style="flex:1"><div style="font-size:14px;font-weight:600">병원 찾기</div>'
       f'<div style="font-size:11.5px;color:{HINT}">심평원·공공데이터</div></div><i class="ti ti-external-link" style="color:{HINT}"></i></div>'
       f'<div class="card" style="display:flex;align-items:center;gap:12px;border-radius:0 0 16px 16px;border-top:none">'
       f'<div class="oico"><i class="ti ti-pill"></i></div><div style="flex:1"><div style="font-size:14px;font-weight:600">약국 찾기</div>'
       f'<div style="font-size:11.5px;color:{HINT}">약학정보원·휴일지킴이</div></div><i class="ti ti-external-link" style="color:{HINT}"></i></div>'
       f'<div class="sp1"></div>'
       f'<div style="text-align:center;font-size:11.5px;color:{HINT};margin-bottom:18px">중립 공공정보 · 특정 병원 추천 아님</div>')

SCREENS = [("홈 (선제)", "묻기 전에 챙겨줌", HOME), ("AI 건강 상담", "근거·개인맥락·핸드오프", CHAT),
           ("PHR 동의", "민감정보·국외이전 투명성", PHR), ("코칭 홈", "스트릭·오늘의 한 가지", CHOME),
           ("체크인", "1탭 + AI 코치", CHECK), ("첫 플랜", "맞춤 플랜·안전배너", PLAN),
           ("완주", "마일스톤·재참여", DONE), ("진료 에스컬레이션", "경고밴드→진료 우선", ESC),
           ("시설 안내", "중립 공공출처", FAC)]


def main():
    cols = "".join(f'<div class="col"><div class="phone"><div class="amb"></div><div class="w">{inn}</div></div>'
                   f'<div class="lbl">{t} <em>· {s}</em></div></div>' for t, s, inn in SCREENS)
    head = ('<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">'
            '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont/dist/tabler-icons.min.css">'
            f'<style>{CSS}</style>')
    html = f"<!DOCTYPE html><html lang='ko'><head><meta charset='utf-8'>{head}</head><body><div class='board'>{cols}</div></body></html>"
    out = os.path.join(HERE, "warmlight-board.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print("WROTE", out, len(html))


if __name__ == "__main__":
    main()
