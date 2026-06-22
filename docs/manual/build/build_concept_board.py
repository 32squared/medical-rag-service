"""마이헬스케어 'Calm Intelligence' 디자인 컨셉 보드 — 핵심 6화면 다크 프리미엄.
HTML 조립 → headless screenshot. Pretendard + 오로라 글로우 + 생성형 AI 표현."""
import os
HERE = os.path.dirname(os.path.abspath(__file__))

AUR = ('<div class="aur a1"></div><div class="aur a2"></div><div class="aur a3"></div>')
ST = ('<div class="st"><span>9:41</span><span class="str"><i class="ti ti-wifi"></i>'
      '<i class="ti ti-battery-3"></i></span></div>')

CSS = """
*{margin:0;padding:0;box-sizing:border-box;-webkit-font-smoothing:antialiased}
.ti{font-family:'tabler-icons'!important;font-style:normal}
body{background:#080C0B;font-family:'Pretendard','Pretendard Variable',sans-serif;padding:40px}
.board{display:grid;grid-template-columns:repeat(3,390px);gap:32px 30px;width:max-content}
.col{display:flex;flex-direction:column;align-items:center}
.lbl{margin-top:16px;color:rgba(255,255,255,.5);font-size:15px;font-weight:600;letter-spacing:-.2px}
.lbl span{color:rgba(255,255,255,.32);font-weight:400}
.phone{width:390px;height:844px;background:#0E1512;border-radius:46px;position:relative;
 overflow:hidden;color:#F3F6F4;border:1px solid rgba(255,255,255,.06)}
.aur{position:absolute;border-radius:50%;filter:blur(58px);pointer-events:none}
.a1{width:320px;height:320px;top:-90px;left:-70px;opacity:.5;
 background:radial-gradient(circle,#2BD4A6 0%,rgba(43,212,166,0) 70%)}
.a2{width:300px;height:300px;top:-50px;right:-110px;opacity:.4;
 background:radial-gradient(circle,#38BDF8 0%,rgba(56,189,248,0) 70%)}
.a3{width:280px;height:280px;bottom:30px;left:-90px;opacity:.18;
 background:radial-gradient(circle,#34D399 0%,rgba(52,211,153,0) 70%)}
.w{position:relative;z-index:2;height:100%;display:flex;flex-direction:column;padding:0 26px}
.st{height:54px;flex:none;display:flex;align-items:center;justify-content:space-between;
 font-size:15px;font-weight:600;letter-spacing:.3px;padding-top:8px}
.str{display:flex;gap:7px;font-size:15px}
.hd{display:flex;align-items:center;gap:12px;padding:2px 0 8px}
.hd .bk{font-size:21px;color:rgba(243,246,244,.6)}
.hd .ti2{font-size:17px;font-weight:600;letter-spacing:-.3px;flex:1}
.mark{font-size:12px;font-weight:600;letter-spacing:2.5px;color:rgba(243,246,244,.45)}
.av{width:38px;height:38px;border-radius:50%;background:rgba(255,255,255,.07);
 border:1px solid rgba(255,255,255,.1);display:flex;align-items:center;justify-content:center;
 font-size:19px;color:rgba(243,246,244,.7)}
.gs{font-size:15px;color:rgba(243,246,244,.55)}
.gn{font-size:29px;font-weight:600;letter-spacing:-.6px;margin-top:5px}
.card{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.09);
 border-radius:24px;padding:20px}
.lab{display:flex;align-items:center;gap:6px;font-size:11px;font-weight:600;letter-spacing:1.4px;
 color:#38E0AE;text-transform:uppercase}
.lab i{font-size:15px}
.ctxt{font-size:15.5px;line-height:1.62;color:rgba(243,246,244,.92);margin-top:11px;letter-spacing:-.2px}
.cmeta{font-size:11.5px;color:rgba(243,246,244,.4);margin-top:12px;display:flex;align-items:center;gap:5px}
.ask{display:flex;align-items:center;gap:12px;background:rgba(255,255,255,.07);
 border:1px solid rgba(255,255,255,.11);border-radius:20px;padding:15px 15px 15px 18px;
 box-shadow:0 8px 40px rgba(43,212,166,.16)}
.ask .sp{font-size:20px;color:#38E0AE}
.ask .ph{flex:1;font-size:14.5px;color:rgba(243,246,244,.5);letter-spacing:-.2px}
.go{width:34px;height:34px;border-radius:50%;background:#2BD4A6;color:#06241C;display:flex;
 align-items:center;justify-content:center;font-size:18px;flex:none}
.chips{display:flex;gap:8px;flex-wrap:wrap}
.chip{font-size:12.5px;color:rgba(243,246,244,.78);background:rgba(255,255,255,.055);
 border:1px solid rgba(255,255,255,.08);border-radius:30px;padding:8px 14px;letter-spacing:-.2px}
.chip i{color:#38E0AE;font-size:13px;margin-right:4px;vertical-align:-1px}
.sp1{flex:1}
.stat{display:flex;align-items:center;gap:9px;font-size:13px;color:rgba(243,246,244,.62);letter-spacing:-.2px}
.dot{width:7px;height:7px;border-radius:50%;background:#38E0AE;box-shadow:0 0 9px #38E0AE}
.tab{display:flex;justify-content:space-between;align-items:center;background:rgba(255,255,255,.06);
 border:1px solid rgba(255,255,255,.09);border-radius:26px;padding:13px 26px;margin-bottom:20px}
.tab i{font-size:22px;color:rgba(243,246,244,.4)}
.tab .on{color:#2BD4A6}
.bubL{display:flex;gap:10px;margin-bottom:14px}
.bubL .a{width:30px;height:30px;border-radius:50%;flex:none;display:flex;align-items:center;
 justify-content:center;font-size:16px;color:#06241C;
 background:linear-gradient(135deg,#38E0AE,#2BD4A6)}
.bubL .t{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.08);border-radius:18px;
 border-top-left-radius:6px;padding:13px 15px;font-size:14.5px;line-height:1.6;
 color:rgba(243,246,244,.92);letter-spacing:-.2px}
.bubR{display:flex;justify-content:flex-end;margin-bottom:14px}
.bubR .t{background:#1C9C7B;color:#fff;border-radius:18px;border-top-right-radius:6px;
 padding:11px 15px;font-size:14.5px;letter-spacing:-.2px}
.cite{font-size:11px;background:rgba(56,224,174,.16);color:#38E0AE;border-radius:5px;
 padding:1px 5px;margin-left:3px;font-weight:600}
.btnP{background:#2BD4A6;color:#06241C;border-radius:14px;height:52px;display:flex;align-items:center;
 justify-content:center;gap:8px;font-size:15px;font-weight:600;letter-spacing:-.3px}
.btnG{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);color:#F3F6F4;
 border-radius:14px;height:48px;display:flex;align-items:center;justify-content:center;
 font-size:14px;font-weight:500}
.row{display:flex;gap:9px}
.prog{height:7px;background:rgba(255,255,255,.1);border-radius:4px;overflow:hidden}
.prog>div{height:100%;background:#2BD4A6;border-radius:4px}
.streak{display:flex;align-items:center;gap:18px;background:rgba(43,212,166,.1);
 border:1px solid rgba(43,212,166,.18);border-radius:22px;padding:20px 22px}
.streak .num{font-size:44px;font-weight:600;color:#38E0AE;line-height:1;letter-spacing:-1px}
.rwd{display:flex;gap:8px}
.rwd .c{display:flex;align-items:center;gap:5px;font-size:12.5px;font-weight:600;
 background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.09);border-radius:11px;
 padding:8px 11px;color:#F3F6F4}
.rwd .c i{color:#38E0AE;font-size:15px}
.tog{display:flex;align-items:center;gap:12px;padding:13px 0;border-bottom:1px solid rgba(255,255,255,.07)}
.tog .sw{width:40px;height:24px;border-radius:14px;background:#2BD4A6;position:relative;flex:none}
.tog .sw::after{content:'';position:absolute;right:3px;top:3px;width:18px;height:18px;border-radius:50%;background:#06241C}
.tog .off{background:rgba(255,255,255,.13)}
.tog .off::after{left:3px;right:auto;background:#0E1512}
.bn{background:rgba(56,224,174,.08);border:1px solid rgba(56,224,174,.16);border-radius:16px;
 padding:14px;font-size:12px;line-height:1.55;color:rgba(243,246,244,.82);display:flex;gap:9px}
.bn i{color:#38E0AE;font-size:16px;flex:none}
.glow{position:absolute;width:200px;height:200px;border-radius:50%;filter:blur(50px);
 background:radial-gradient(circle,#2BD4A6 0%,rgba(43,212,166,0) 70%);opacity:.4;
 top:120px;left:50%;transform:translateX(-50%)}
.trophy{width:84px;height:84px;border-radius:50%;background:rgba(43,212,166,.14);
 border:1px solid rgba(43,212,166,.25);display:flex;align-items:center;justify-content:center;
 font-size:40px;color:#38E0AE;margin:0 auto}
"""

HOME = (f'{ST}<div class="hd"><span class="mark">MY HEALTHCARE</span><div style="flex:1"></div>'
        f'<div class="av"><i class="ti ti-user"></i></div></div>'
        f'<div style="margin-top:30px"><div class="gs">좋은 저녁이에요</div><div class="gn">김건강님</div></div>'
        f'<div class="card" style="margin-top:24px"><div class="lab"><i class="ti ti-sparkles"></i>AI 인사이트</div>'
        f'<div class="ctxt">오늘 혈압이 <b style="color:#fff">안정 구간</b>으로 확인됐어요. 어제 저염 실천이 이어진 '
        f'영향일 수 있어요. 이 흐름을 며칠 더 이어가 볼까요?</div>'
        f'<div class="cmeta"><i class="ti ti-clock" style="font-size:13px"></i>방금 생성됨 · 비식별 밴드 기준</div></div>'
        f'<div class="ask" style="margin-top:18px"><i class="ti ti-sparkles sp"></i>'
        f'<span class="ph">건강에 대해 무엇이든 물어보세요</span><span class="go"><i class="ti ti-arrow-up"></i></span></div>'
        f'<div class="chips" style="margin-top:14px"><span class="chip"><i class="ti ti-bolt"></i>혈압 관리 방법</span>'
        f'<span class="chip"><i class="ti ti-salad"></i>오늘 저녁 식단</span>'
        f'<span class="chip"><i class="ti ti-flame"></i>코칭 이어가기</span></div>'
        f'<div class="sp1"></div>'
        f'<div class="stat" style="margin-bottom:14px"><span class="dot"></span>혈압 안정 · 식단 챌린지 5일째 실천 중</div>'
        f'<div class="tab"><i class="ti ti-home on"></i><i class="ti ti-message-2"></i>'
        f'<i class="ti ti-chart-line"></i><i class="ti ti-user"></i></div>')

CHAT = (f'{ST}<div class="hd"><i class="ti ti-chevron-left bk"></i><span class="ti2">AI 건강 상담</span>'
        f'<span class="dot"></span></div>'
        f'<div style="margin-top:14px"></div>'
        f'<div class="bubR"><div class="t">혈압이 높게 나왔어요</div></div>'
        f'<div class="bubL"><div class="a"><i class="ti ti-sparkles"></i></div>'
        f'<div class="t">일시적으로 높을 수 있어요. 잠시 쉬었다 <b style="color:#fff">다시 측정</b>해 확인해 주세요'
        f'<span class="cite">1</span>. 두통·가슴통증이 함께라면 바로 진료가 필요해요<span class="cite">2</span>.</div></div>'
        f'<div style="margin:2px 0 14px 40px"><span class="chip" style="display:inline-flex"><i class="ti ti-lock"></i>내 혈압 밴드 반영됨</span></div>'
        f'<div class="card" style="margin-left:40px;padding:15px 17px;background:rgba(43,212,166,.08);border-color:rgba(43,212,166,.18)">'
        f'<div style="font-size:13.5px;color:rgba(243,246,244,.85);line-height:1.5">생활 속 실천으로 이어가 볼까요?</div>'
        f'<div style="display:flex;align-items:center;gap:6px;color:#38E0AE;font-size:13.5px;font-weight:600;margin-top:8px">'
        f'<i class="ti ti-flame"></i>저염 식단 코칭 시작 <i class="ti ti-arrow-right" style="font-size:14px"></i></div></div>'
        f'<div class="sp1"></div>'
        f'<div class="ask" style="margin-bottom:22px"><i class="ti ti-sparkles sp"></i>'
        f'<span class="ph">메시지 입력</span><span class="go"><i class="ti ti-arrow-up"></i></span></div>')

CHOME = (f'{ST}<div class="hd"><span class="ti2" style="font-size:19px;font-weight:600">코칭</span><div style="flex:1"></div>'
         f'<div class="av" style="background:rgba(43,212,166,.12);color:#38E0AE;font-size:13px;font-weight:600;width:auto;padding:0 12px;border-radius:16px"><i class="ti ti-star" style="font-size:14px;margin-right:3px"></i>Lv.2</div></div>'
         f'<div class="streak" style="margin-top:18px"><div style="text-align:center"><div class="num">5</div>'
         f'<div style="font-size:11px;color:#38E0AE;font-weight:600;margin-top:3px">일째</div></div>'
         f'<div style="flex:1"><div style="font-size:16px;font-weight:600;letter-spacing:-.3px">연속 실천 중이에요</div>'
         f'<div style="font-size:13px;color:rgba(243,246,244,.55);margin-top:4px">이번 주 4번 · 좋은 흐름이에요</div></div>'
         f'<i class="ti ti-flame" style="font-size:26px;color:#38E0AE"></i></div>'
         f'<div style="font-size:11px;font-weight:600;letter-spacing:1.2px;color:rgba(243,246,244,.4);text-transform:uppercase;margin:24px 0 10px">오늘의 목표</div>'
         f'<div class="card"><div style="font-size:17px;font-weight:600;letter-spacing:-.3px">국물 반 남기기</div>'
         f'<div style="font-size:13px;color:rgba(243,246,244,.5);margin-top:3px">저염 실천 · 2주 챌린지</div>'
         f'<div class="btnP" style="margin-top:16px"><i class="ti ti-check" style="font-size:19px"></i>오늘 체크인하기</div></div>'
         f'<div style="display:flex;justify-content:space-between;font-size:13px;margin:20px 2px 9px">'
         f'<span style="color:rgba(243,246,244,.7);font-weight:500">2주 식단 챌린지</span>'
         f'<span style="color:rgba(243,246,244,.55)"><b style="color:#38E0AE">9</b> / 14일</span></div>'
         f'<div class="prog"><div style="width:64%"></div></div>'
         f'<div class="sp1"></div>'
         f'<div class="tab"><i class="ti ti-home on"></i><i class="ti ti-message-2"></i>'
         f'<i class="ti ti-chart-line"></i><i class="ti ti-user"></i></div>')

CHECK = (f'{ST}<div class="hd"><i class="ti ti-chevron-left bk"></i><span class="ti2">오늘의 체크인</span></div>'
         f'<div style="font-size:23px;font-weight:600;letter-spacing:-.5px;margin:18px 0 4px">국물 반,<br>남기셨어요?</div>'
         f'<div style="font-size:13.5px;color:rgba(243,246,244,.5);margin-bottom:20px">2주 저염 챌린지 · 6일차</div>'
         f'<div class="row" style="margin-bottom:22px"><div class="btnP" style="flex:1"><i class="ti ti-check"></i>네</div>'
         f'<div class="btnG" style="flex:1;height:52px">아니오</div>'
         f'<div class="btnG" style="flex:1;height:52px">외식</div></div>'
         f'<div class="rwd" style="margin-bottom:16px"><span class="c"><i class="ti ti-flame"></i>5일 연속</span>'
         f'<span class="c"><i class="ti ti-coin"></i>+10P</span><span class="c"><i class="ti ti-award"></i>새 배지</span></div>'
         f'<div class="bubL"><div class="a"><i class="ti ti-sparkles"></i></div>'
         f'<div class="t">좋아요, 5일 연속이에요! 이 페이스면 충분해요. 외식이 잦은 날엔 \'국물만\' 줄여도 괜찮아요.</div></div>'
         f'<div class="sp1"></div>'
         f'<div class="row" style="margin-bottom:22px"><div class="btnP" style="flex:1">계속</div>'
         f'<div class="btnG" style="flex:1;height:52px">코치와 더 얘기</div></div>')

DONE = (f'{ST}<div class="glow"></div>'
        f'<div class="sp1"></div>'
        f'<div style="text-align:center"><div class="trophy"><i class="ti ti-trophy"></i></div>'
        f'<div style="font-size:25px;font-weight:600;letter-spacing:-.5px;margin-top:20px">2주 챌린지 완주!</div>'
        f'<div style="font-size:14px;color:rgba(243,246,244,.55);margin-top:7px">꾸준함이 멋져요, 김건강님</div></div>'
        f'<div class="row" style="margin-top:26px"><div class="card" style="flex:1;text-align:center;padding:18px 0">'
        f'<div style="font-size:26px;font-weight:600;color:#38E0AE;letter-spacing:-1px">71%</div>'
        f'<div style="font-size:12px;color:rgba(243,246,244,.5);margin-top:3px">실천율</div></div>'
        f'<div class="card" style="flex:1;text-align:center;padding:18px 0">'
        f'<div style="font-size:26px;font-weight:600;color:#38E0AE;letter-spacing:-1px">6일</div>'
        f'<div style="font-size:12px;color:rgba(243,246,244,.5);margin-top:3px">최장 스트릭</div></div></div>'
        f'<div class="bn" style="margin-top:16px"><i class="ti ti-sparkles"></i>'
        f'<div>저염 실천을 꾸준히 이어간 2주였어요. 혈압 안정 흐름을 유지하는 데 도움이 됐을 수 있어요.</div></div>'
        f'<div class="sp1"></div>'
        f'<div class="btnP" style="margin-top:10px">다음 목표 정하기</div>'
        f'<div style="text-align:center;font-size:13px;color:rgba(243,246,244,.45);margin:14px 0 22px">졸업·유지 모드로 전환</div>')

PHR = (f'{ST}<div class="hd"><i class="ti ti-chevron-left bk"></i><span class="ti2">건강 데이터 연결</span></div>'
       f'<div style="font-size:22px;font-weight:600;letter-spacing:-.5px;margin:16px 0 6px">더 정확한 안내를<br>받아보세요</div>'
       f'<div style="font-size:14px;color:rgba(243,246,244,.55);line-height:1.55;margin-bottom:22px">'
       f'검진·진료 기록을 연결하면 AI가 내 상황에 맞춰 안내해요.</div>'
       f'<div class="tog"><i class="ti ti-square-rounded-check" style="font-size:22px;color:#38E0AE"></i>'
       f'<span style="flex:1;font-size:14.5px">건강검진 결과 <span style="color:rgba(243,246,244,.45);font-size:12.5px">혈압·혈당·BMI</span></span>'
       f'<div class="sw"></div></div>'
       f'<div class="tog"><i class="ti ti-square-rounded-check" style="font-size:22px;color:#38E0AE"></i>'
       f'<span style="flex:1;font-size:14.5px">진료·투약 내역</span><div class="sw"></div></div>'
       f'<div class="bn" style="margin-top:18px"><i class="ti ti-shield-lock"></i>'
       f'<div>민감정보는 <b style="color:#fff">암호화 보관</b>되고, AI 분석엔 <b style="color:#fff">비식별 밴드 라벨만</b> '
       f'쓰여요(원시수치·진단명 미전송). 일부 처리는 국외 AI를 경유할 수 있어요 — 동의 시.</div></div>'
       f'<div class="sp1"></div>'
       f'<div class="btnP">간편인증으로 연결</div>'
       f'<div style="text-align:center;font-size:13px;color:rgba(243,246,244,.45);margin:14px 0 22px">나중에 · 연결 없이도 일반 안내 가능</div>')

SCREENS = [("AI 홈", "생성형 인사이트 · 자연어 중심", HOME),
           ("AI 건강 상담", "근거 인용 · 개인맥락 · 핸드오프", CHAT),
           ("코칭 홈", "스트릭 히어로 · 오늘의 한 가지", CHOME),
           ("체크인", "1탭 + AI 코치 반응", CHECK),
           ("완주", "마일스톤 · 재참여", DONE),
           ("PHR 연결", "민감정보 동의 · 신뢰", PHR)]


def main():
    cols = "".join(
        f'<div class="col"><div class="phone">{AUR}<div class="w">{inner}</div></div>'
        f'<div class="lbl">{t} <span>· {s}</span></div></div>'
        for t, s, inner in SCREENS)
    head = ('<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">'
            '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont/dist/tabler-icons.min.css">'
            f'<style>{CSS}</style>')
    html = f"<!DOCTYPE html><html lang='ko'><head><meta charset='utf-8'>{head}</head><body><div class='board'>{cols}</div></body></html>"
    out = os.path.join(HERE, "concept-board.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print("WROTE", out, len(html))


if __name__ == "__main__":
    main()
