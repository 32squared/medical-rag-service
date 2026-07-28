"""Living Canvas — 생성형/앰비언트 인터랙션 시퀀스(3프레임). 정적 화면이 못 담는
'UI가 그 순간 생성·소멸' 패러다임을 흐름으로. 색은 잠정(추후 팔레트 재제안)."""
import os
HERE = os.path.dirname(os.path.abspath(__file__))

CSS = """
*{margin:0;padding:0;box-sizing:border-box;-webkit-font-smoothing:antialiased}
.ti{font-family:'tabler-icons'!important;font-style:normal}
body{background:#06090A;font-family:'Pretendard',sans-serif;padding:46px 40px}
.flow{display:flex;align-items:center;gap:8px;width:max-content}
.col{display:flex;flex-direction:column;align-items:center}
.cap{margin-top:18px;text-align:center;max-width:330px}
.cap .n{font-size:13px;font-weight:700;color:#3FE6B4;letter-spacing:1px}
.cap .t{font-size:15px;font-weight:600;color:rgba(255,255,255,.82);margin-top:5px;letter-spacing:-.2px}
.cap .s{font-size:12.5px;color:rgba(255,255,255,.42);margin-top:4px;line-height:1.45}
.arr{font-size:30px;color:rgba(255,255,255,.22);padding:0 4px;margin-bottom:60px}
.phone{width:330px;height:716px;background:#0A0F0D;border-radius:42px;position:relative;
 overflow:hidden;color:#F1F5F3;border:1px solid rgba(255,255,255,.06)}
.amb{position:absolute;inset:0}
.amb.dim{background:radial-gradient(360px 320px at 50% 36%, rgba(43,212,166,.08), transparent 70%)}
.amb.act{background:radial-gradient(420px 380px at 50% 34%, rgba(43,212,166,.22), transparent 70%),
 radial-gradient(260px 260px at 78% 20%, rgba(56,189,248,.12), transparent 70%)}
.amb.set{background:radial-gradient(380px 340px at 50% 30%, rgba(43,212,166,.15), transparent 70%)}
.w{position:relative;z-index:2;height:100%;display:flex;flex-direction:column;padding:0 24px}
.top{height:54px;flex:none;display:flex;align-items:center;justify-content:space-between;
 padding-top:16px;font-size:12px;color:rgba(241,245,243,.4)}
.stage{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center}
.orbwrap{position:relative;width:230px;height:230px;display:flex;align-items:center;justify-content:center}
.ring{position:absolute;border-radius:50%;border:1px solid rgba(43,212,166,.12)}
.glow{position:absolute;border-radius:50%;filter:blur(44px);
 background:radial-gradient(circle, rgba(43,212,166,.55), transparent 65%)}
.orb{position:relative;border-radius:50%;
 background:radial-gradient(circle at 38% 32%, #7CF0D8 0%, #34E0AE 26%, #18B892 52%, #0C7C63 78%, #075745 100%);
 box-shadow:0 0 60px rgba(43,212,166,.45), inset -12px -16px 34px rgba(4,40,32,.55),
  inset 9px 11px 26px rgba(180,255,238,.32)}
.orb .sh{position:absolute;top:16px;left:24px;width:48px;height:32px;border-radius:50%;
 background:radial-gradient(circle, rgba(255,255,255,.5), transparent 70%);filter:blur(4px)}
.lab{text-align:center;margin-top:24px}
.lab .t{font-size:19px;font-weight:600;letter-spacing:-.4px}
.lab .s{font-size:12.5px;color:rgba(241,245,243,.45);margin-top:5px}
.compose{display:flex;gap:5px;margin-top:20px;align-items:center;justify-content:center}
.compose i{width:7px;height:7px;border-radius:50%;background:#38E0AE;opacity:.9}
.compose i:nth-child(2){opacity:.55}.compose i:nth-child(3){opacity:.3}
.said{margin:0 auto;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.12);
 border-radius:18px;border-bottom-right-radius:6px;padding:11px 15px;font-size:14px;
 color:rgba(241,245,243,.92);letter-spacing:-.2px;max-width:230px;margin-bottom:16px}
.gen{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);border-radius:20px;
 padding:16px 17px;margin-bottom:18px;animation:none}
.gen .tag{display:flex;align-items:center;gap:6px;font-size:10px;font-weight:600;letter-spacing:1.2px;
 color:#38E0AE;text-transform:uppercase;margin-bottom:11px}
.gen .nar{font-size:14px;line-height:1.55;color:rgba(241,245,243,.9);letter-spacing:-.2px}
.ribbon{display:flex;align-items:flex-end;gap:5px;height:46px;margin:13px 0 4px}
.ribbon span{flex:1;background:linear-gradient(180deg,#38E0AE,rgba(56,224,174,.25));border-radius:4px}
.rday{font-size:9.5px;color:rgba(241,245,243,.32);text-align:center;letter-spacing:.5px}
.dock{flex:none;margin-bottom:22px;display:flex;align-items:center;gap:11px;
 background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);border-radius:22px;
 padding:13px 13px 13px 17px}
.dock.act{box-shadow:0 8px 44px rgba(43,212,166,.22);border-color:rgba(43,212,166,.3)}
.dock .sp{font-size:19px;color:#38E0AE}
.dock .ph{flex:1;font-size:14px;color:rgba(241,245,243,.5);letter-spacing:-.2px}
.dock .mic{width:38px;height:38px;border-radius:50%;background:#2BD4A6;color:#06241C;flex:none;
 display:flex;align-items:center;justify-content:center;font-size:18px}
.dock .mic.on{box-shadow:0 0 0 6px rgba(43,212,166,.18)}
"""

def orb(size, glow, rings):
    rs = "".join(f'<div class="ring" style="width:{size+40+i*44}px;height:{size+40+i*44}px"></div>'
                 for i in range(rings))
    return (f'<div class="orbwrap">{rs}'
            f'<div class="glow" style="width:{size+70}px;height:{size+70}px;opacity:{glow}"></div>'
            f'<div class="orb" style="width:{size}px;height:{size}px"><div class="sh"></div></div></div>')

F1 = (f'<div class="top"><span>수요일 저녁</span><span>9:41</span></div>'
      f'<div class="stage">{orb(120,.3,1)}'
      f'<div class="lab"><div class="t" style="font-size:17px;color:rgba(241,245,243,.7)">잔잔히 쉬고 있어요</div>'
      f'<div class="s">필요할 때 깨워주세요</div></div></div>'
      f'<div class="dock"><i class="ti ti-sparkles sp"></i><span class="ph">말하거나 물어보세요</span>'
      f'<span class="mic"><i class="ti ti-microphone"></i></span></div>')

F2 = (f'<div class="top"><span>수요일 저녁</span><span>9:41</span></div>'
      f'<div class="stage">{orb(150,.6,2)}'
      f'<div class="compose"><i></i><i></i><i></i></div></div>'
      f'<div class="said">이번 주 내 흐름, 어땠어?</div>'
      f'<div class="dock act"><i class="ti ti-sparkles sp"></i><span class="ph" style="color:#38E0AE">듣고 있어요…</span>'
      f'<span class="mic on"><i class="ti ti-microphone"></i></span></div>')

F3 = (f'<div class="top"><span>수요일 저녁</span><span>9:41</span></div>'
      f'<div class="stage" style="flex:none;padding-top:30px">{orb(108,.35,1)}'
      f'<div class="lab"><div class="t" style="font-size:16px;color:rgba(241,245,243,.7)">안정적인 한 주였어요</div></div></div>'
      f'<div style="flex:1"></div>'
      f'<div class="gen"><div class="tag"><i class="ti ti-sparkles" style="font-size:12px"></i>이 질문에 맞춰 생성됨</div>'
      f'<div class="ribbon"><span style="height:55%"></span><span style="height:48%"></span><span style="height:40%"></span>'
      f'<span style="height:62%"></span><span style="height:45%"></span><span style="height:38%"></span><span style="height:35%"></span></div>'
      f'<div class="rday">월 화 수 목 금 토 일</div>'
      f'<div class="nar" style="margin-top:12px">이번 주는 <b style="color:#fff">잔잔했어요</b>. 저염을 이어간 5일과 흐름이 겹쳐요. 며칠 더 가볼까요?</div></div>'
      f'<div class="dock"><i class="ti ti-sparkles sp"></i><span class="ph">이어서 물어보세요</span>'
      f'<span class="mic"><i class="ti ti-microphone"></i></span></div>')

FRAMES = [("01 · 앰비언트", "인터페이스가 거의 없다", "평소엔 유기체와 입력만. 앱이 물러나 있음.", "dim", F1),
          ("02 · 인텐트", "말을 건네면 깨어난다", "음성·자연어가 유일한 컨트롤. 화면을 찾지 않음.", "act", F2),
          ("03 · 제너러티브", "그 순간 UI가 생성된다", "질문에 맞춰 AI가 컴포넌트를 조립 → 답하면 사라짐.", "set", F3)]


def main():
    parts = []
    for i, (n, t, s, amb, inner) in enumerate(FRAMES):
        if i: parts.append('<div class="arr"><i class="ti ti-chevron-right"></i></div>')
        parts.append(f'<div class="col"><div class="phone"><div class="amb {amb}"></div>'
                     f'<div class="w">{inner}</div></div>'
                     f'<div class="cap"><div class="n">{n}</div><div class="t">{t}</div><div class="s">{s}</div></div></div>')
    head = ('<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">'
            '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont/dist/tabler-icons.min.css">'
            f'<style>{CSS}</style>')
    html = f"<!DOCTYPE html><html lang='ko'><head><meta charset='utf-8'>{head}</head><body><div class='flow'>{''.join(parts)}</div></body></html>"
    out = os.path.join(HERE, "living-sequence.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print("WROTE", out, len(html))


if __name__ == "__main__":
    main()
