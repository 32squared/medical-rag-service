"""컬러 팔레트 옵션 3종 — 같은 AI 홈 화면에 팔레트만 교체해 비교.
A Emerald(차분 웰니스·현재) / B Indigo(AI 미래) / C Warm Light(따뜻·접근성).
CSS 변수만 스왑. headless 렌더용 단일 화면 3개."""
import os
HERE = os.path.dirname(os.path.abspath(__file__))

PALETTES = {
 "a": dict(name="A · Emerald", desc="차분한 웰니스 (현재)",
   bg="#0E1512", amb1="rgba(43,212,166,.18)", amb2="rgba(56,189,248,.10)",
   txt="#F1F5F3", txt2="rgba(241,245,243,.55)", txt3="rgba(241,245,243,.4)",
   surf="rgba(255,255,255,.05)", bd="rgba(255,255,255,.09)",
   accent="#2BD4A6", accentTxt="#06241C", tint="rgba(43,212,166,.12)", tintTxt="#7BF0D4",
   tag="#38E0AE", glow="rgba(43,212,166,.18)", cardsh="none", strong="#FFFFFF"),
 "b": dict(name="B · Indigo", desc="AI·미래적",
   bg="#0B0D16", amb1="rgba(124,124,240,.22)", amb2="rgba(56,189,248,.12)",
   txt="#EDEEF7", txt2="rgba(237,238,247,.55)", txt3="rgba(237,238,247,.4)",
   surf="rgba(255,255,255,.05)", bd="rgba(255,255,255,.10)",
   accent="#8B8CF7", accentTxt="#0E0F26", tint="rgba(124,124,240,.16)", tintTxt="#BDB9FF",
   tag="#A99CFF", glow="rgba(124,124,240,.22)", cardsh="none", strong="#FFFFFF"),
 "c": dict(name="C · Warm Light", desc="따뜻·접근성·의료 신뢰",
   bg="#F6F4EF", amb1="rgba(14,138,107,.10)", amb2="rgba(224,162,62,.10)",
   txt="#232220", txt2="rgba(35,34,32,.62)", txt3="rgba(35,34,32,.42)",
   surf="#FFFFFF", bd="rgba(0,0,0,.08)",
   accent="#0E8A6B", accentTxt="#FFFFFF", tint="rgba(14,138,107,.10)", tintTxt="#0B5F4A",
   tag="#0E8A6B", glow="rgba(14,138,107,.16)", cardsh="0 6px 22px rgba(0,0,0,.06)", strong="#111110"),
}


def html(p):
    return f"""<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont/dist/tabler-icons.min.css">
<style>
 *{{margin:0;padding:0;box-sizing:border-box;-webkit-font-smoothing:antialiased}}
 .ti{{font-family:'tabler-icons'!important;font-style:normal}}
 :root{{--bg:{p['bg']};--txt:{p['txt']};--txt2:{p['txt2']};--txt3:{p['txt3']};
  --surf:{p['surf']};--bd:{p['bd']};--accent:{p['accent']};--accentTxt:{p['accentTxt']};
  --tint:{p['tint']};--tintTxt:{p['tintTxt']};--tag:{p['tag']};--glow:{p['glow']};
  --cardsh:{p['cardsh']};--strong:{p['strong']}}}
 html,body{{width:390px;height:844px}}
 body{{font-family:'Pretendard',sans-serif;background:var(--bg);color:var(--txt);
  position:relative;overflow:hidden;display:flex;flex-direction:column}}
 .amb{{position:absolute;inset:0;background:
  radial-gradient(420px 360px at 50% 30%, {p['amb1']}, transparent 70%),
  radial-gradient(300px 300px at 80% 16%, {p['amb2']}, transparent 70%)}}
 .w{{position:relative;z-index:2;height:100%;display:flex;flex-direction:column;padding:0 26px}}
 .st{{height:54px;flex:none;display:flex;align-items:center;justify-content:space-between;
  font-size:15px;font-weight:600;letter-spacing:.3px;padding-top:8px}}
 .top{{display:flex;align-items:center;justify-content:space-between;margin-top:2px}}
 .mark{{font-size:12px;font-weight:600;letter-spacing:2.5px;color:var(--txt3)}}
 .av{{width:38px;height:38px;border-radius:50%;background:var(--surf);border:1px solid var(--bd);
  display:flex;align-items:center;justify-content:center;font-size:19px;color:var(--txt2)}}
 .greet{{margin-top:32px}}
 .greet .s{{font-size:15px;color:var(--txt2)}}
 .greet .n{{font-size:29px;font-weight:600;letter-spacing:-.6px;margin-top:5px}}
 .card{{margin-top:24px;background:var(--surf);border:1px solid var(--bd);border-radius:24px;
  padding:20px;box-shadow:var(--cardsh)}}
 .lab{{display:flex;align-items:center;gap:6px;font-size:11px;font-weight:600;letter-spacing:1.4px;
  color:var(--tag);text-transform:uppercase}}
 .lab i{{font-size:15px}}
 .ctxt{{font-size:15.5px;line-height:1.62;color:var(--txt);margin-top:11px;letter-spacing:-.2px}}
 .ctxt b{{color:var(--strong);font-weight:600}}
 .cmeta{{font-size:11.5px;color:var(--txt3);margin-top:12px;display:flex;align-items:center;gap:5px}}
 .ask{{margin-top:18px;display:flex;align-items:center;gap:12px;background:var(--surf);
  border:1px solid var(--bd);border-radius:20px;padding:15px 15px 15px 18px;
  box-shadow:0 8px 40px var(--glow)}}
 .ask .sp{{font-size:20px;color:var(--tag)}}
 .ask .ph{{flex:1;font-size:14.5px;color:var(--txt3);letter-spacing:-.2px}}
 .go{{width:34px;height:34px;border-radius:50%;background:var(--accent);color:var(--accentTxt);
  display:flex;align-items:center;justify-content:center;font-size:18px;flex:none}}
 .chips{{display:flex;gap:8px;margin-top:14px;flex-wrap:wrap}}
 .chip{{font-size:12.5px;color:var(--txt2);background:var(--surf);border:1px solid var(--bd);
  border-radius:30px;padding:8px 14px;letter-spacing:-.2px}}
 .chip i{{color:var(--tag);font-size:13px;margin-right:4px;vertical-align:-1px}}
 .sp1{{flex:1}}
 .stat{{display:flex;align-items:center;gap:9px;margin-bottom:14px;font-size:13px;color:var(--txt2)}}
 .dot{{width:7px;height:7px;border-radius:50%;background:var(--tag)}}
 .tab{{display:flex;justify-content:space-between;align-items:center;background:var(--surf);
  border:1px solid var(--bd);border-radius:26px;padding:13px 26px;margin-bottom:20px}}
 .tab i{{font-size:22px;color:var(--txt3)}}
 .tab .on{{color:var(--accent)}}
</style></head><body>
 <div class="amb"></div>
 <div class="w">
  <div class="st"><span>9:41</span><span style="display:inline-flex;gap:7px"><i class="ti ti-wifi"></i><i class="ti ti-battery-3"></i></span></div>
  <div class="top"><span class="mark">MY HEALTHCARE</span><div class="av"><i class="ti ti-user"></i></div></div>
  <div class="greet"><div class="s">좋은 저녁이에요</div><div class="n">김건강님</div></div>
  <div class="card"><div class="lab"><i class="ti ti-sparkles"></i>AI 인사이트</div>
   <div class="ctxt">오늘 혈압이 <b>안정 구간</b>으로 확인됐어요. 어제 저염 실천이 이어진 영향일 수 있어요. 이 흐름을 며칠 더 이어가 볼까요?</div>
   <div class="cmeta"><i class="ti ti-clock" style="font-size:13px"></i>방금 생성됨 · 비식별 밴드 기준</div></div>
  <div class="ask"><i class="ti ti-sparkles sp"></i><span class="ph">건강에 대해 무엇이든 물어보세요</span><span class="go"><i class="ti ti-arrow-up"></i></span></div>
  <div class="chips"><span class="chip"><i class="ti ti-bolt"></i>혈압 관리 방법</span><span class="chip"><i class="ti ti-salad"></i>오늘 저녁 식단</span><span class="chip"><i class="ti ti-flame"></i>코칭 이어가기</span></div>
  <div class="sp1"></div>
  <div class="stat"><span class="dot"></span>혈압 안정 · 식단 챌린지 5일째 실천 중</div>
  <div class="tab"><i class="ti ti-home on"></i><i class="ti ti-message-2"></i><i class="ti ti-chart-line"></i><i class="ti ti-user"></i></div>
 </div>
</body></html>"""


def main():
    for k, p in PALETTES.items():
        out = os.path.join(HERE, f"palette-{k}.html")
        with open(out, "w", encoding="utf-8") as f:
            f.write(html(p))
        print("WROTE", out)


if __name__ == "__main__":
    main()
