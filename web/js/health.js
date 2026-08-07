// health.js — '내 건강' 탭(상태 진단 ③) + 병원·약국 찾기 + 설정. 정본 §D-3 · §F-5.

import { useState } from 'preact/hooks';
import { GET, POST, PUT, DEL, errText, setTok } from './api.js';
import {
  html, Header, Loading, ErrorView, Empty, useLoader, useLatest, arr, num, str,
} from './ui.js';

const ITEM_DESC = {
  personal_info: '서비스 이용을 위한 기본 개인정보',
  sensitive_info: '맞춤 안내를 위한 건강·검진 정보(민감)',
  cross_border: '국외 LLM 이용 시 개인정보 국외이전',
  location: '가까운 병원·약국 찾기(위치)',
  push: '루틴 리마인더 등 알림',
  phr_link: '공단 건강검진 연동',
};

const HOURS = ['08:00', '09:00', '12:00', '18:00', '19:00', '20:00'];

// ── 내 건강(진단) ────────────────────────────────────────────────
export function HealthTab({ go }) {
  const L = useLoader(() => GET('/diagnosis'), []);
  const N = useLoader(() => GET('/routine/today'), []);
  const [saving, setSaving] = useState('');
  const [notifyMsg, setNotifyMsg] = useState('');

  if (L.state === 'loading') return html`<${Loading} />`;
  if (L.state === 'error') {
    return html`<div key="he"><${Header} title="내 건강" />
      <${ErrorView} err=${L.err} text=${errText(L.err)} onRetry=${L.reload} /></div>`;
  }

  const d = L.data || {};
  const items = arr(d.items);
  const rec = d.recommended && typeof d.recommended === 'object' ? d.recommended : {};
  const cur = (N.state === 'data' && N.data && N.data.notify && N.data.notify.hhmm) || null;

  async function saveNotify(hh) {
    setSaving(hh); setNotifyMsg('');
    const r = await PUT('/routine/notify', { hhmm: hh, channel: 'inapp' });
    setSaving('');
    if (!r.ok) { setNotifyMsg(errText(r)); return; }
    N.reload();
  }

  return html`<div key="health">
    <${Header} title="내 건강"
      right=${html`<button class="icobtn" key="set" onClick=${() => go('settings')}>설정</button>`} />
    <div class="scroll">
      ${d.safety ? html`<div class="safetybox" key="sf">
        <div class="safetytitle">🚨 ${str(d.safety.text)}</div></div>` : null}

      <div class="dgcard" key="dg">
        <div class="dgtop">
          <div class="dgband">${d.band ? `${str(d.band)} 구간` : '측정 정보 없음'}</div>
          ${d.personalization ? null : html`<span class="dgoff" key="off">개인화 꺼짐</span>`}
        </div>
        ${items.length ? html`<div class="dgitems" key="items">
          ${items.map((it) => html`<div class="dgrow" key=${str(it.key) || str(it.label)}>
            <span>${str(it.label)}</span>
            <span class=${'dgstate s-' + (str(it.state) || 'none')}>${str(it.state) || '—'}</span>
          </div>`)}
        </div>` : html`<div class="muted" key="noitem" style="font-size:13px;margin-top:8px">
          체험 프로필을 고르면 상태 구간을 볼 수 있어요.</div>`}
        <div class="dgnotice">${str(d.notice)}</div>
      </div>

      ${rec.track ? html`<div class="reccard" key="rec">
        <div class="sectitle">추천 루틴</div>
        <div class="rectext">${rec.evidence_phrase ? str(rec.evidence_phrase) + ' · ' : ''}
          ${rec.track === 'diet' ? '식이 기록' : rec.track === 'exercise' ? '활동 기록' : '생활 리듬 기록'} 트랙</div>
      </div>` : null}

      ${arr(d.practice_profile).length ? html`<div class="reccard" key="pp">
        <div class="sectitle">내 실천 기록</div>
        ${arr(d.practice_profile).map((p) => html`<div class="rectext" key=${str(p.label)}>
          ${str(p.label)} · ${num(p.days)}일 (${num(p.weeks)}주차)</div>`)}
        <div class="muted" style="font-size:11.5px;margin-top:6px">같은 기간의 기록이에요.</div>
      </div>` : null}

      <div class="reccard" key="notify">
        <div class="sectitle">알림 시각</div>
        <div class="muted" style="font-size:12.5px;margin-bottom:8px">
          매일 이 시각에 오늘의 행동을 떠올려 드려요. ${cur ? `(현재 ${cur})` : ''}</div>
        <div class="chips">
          ${HOURS.map((hh) => html`<button class=${'chip' + (cur === hh ? ' sel' : '')}
            key=${hh} disabled=${saving === hh} onClick=${() => saveNotify(hh)}>${hh}</button>`)}
        </div>
        ${notifyMsg ? html`<div class="err" key="nm">${notifyMsg}</div>` : null}
      </div>

      <button class="btn ghost" key="finder" onClick=${() => go('finder')}>📍 병원·약국 찾기</button>
      <div class="bottompad"></div>
    </div>
  </div>`;
}

// ── 설정(동의·로그아웃·탈퇴) ─────────────────────────────────────
export function SettingsView({ go, onLoggedOut }) {
  const L = useLoader(() => GET('/me'), []);
  const [busy, setBusy] = useState('');

  async function toggle(it) {
    if (it.required) return;
    setBusy(str(it.item_key));
    await POST('/consent', {
      item_key: it.item_key, action: it.granted ? 'revoke' : 'grant', source: 'settings',
    });
    setBusy('');
    L.reload();
  }
  async function logout() {
    await POST('/auth/logout', {});
    setTok(null);
    onLoggedOut();
  }
  async function withdraw() {
    let ok = false;
    try { ok = window.confirm('회원 탈퇴하시겠어요? 루틴 기록과 동의가 모두 해제됩니다.'); } catch { ok = false; }
    if (!ok) return;
    await DEL('/me');
    setTok(null);
    onLoggedOut();
  }

  const back = () => go('health');
  if (L.state === 'loading') {
    return html`<div key="sl"><${Header} title="설정" onBack=${back} /><${Loading} /></div>`;
  }
  if (L.state === 'error') {
    return html`<div key="se"><${Header} title="설정" onBack=${back} />
      <${ErrorView} err=${L.err} text=${errText(L.err)} onRetry=${L.reload} /></div>`;
  }

  const consent = arr((L.data || {}).consent);
  return html`<div key="settings">
    <${Header} title="설정 · 동의 관리" onBack=${back} />
    <div class="scroll">
      <div class="card" key="cs">
        ${consent.map((it) => html`<div class="row" key=${str(it.item_key)}>
          <div style="flex:1">
            <div style="font-weight:600">${str(it.title)}${it.required ? html`<span class="req">필수</span>` : null}</div>
            <div class="muted" style="font-size:12.5px">${ITEM_DESC[it.item_key] || ''}</div>
          </div>
          <div class=${'sw' + (it.granted ? ' on' : '') + (it.required || busy === it.item_key ? ' lock' : '')}
            role="switch" aria-checked=${!!it.granted}
            onClick=${() => toggle(it)}><i></i></div>
        </div>`)}
      </div>
      <p class="note">동의 철회는 즉시 반영됩니다. 맞춤 안내는 민감정보 동의가 있을 때만 제공됩니다.</p>
      <button class="btn ghost" key="lo" onClick=${logout}>로그아웃</button>
      <div style="height:10px"></div>
      <button class="btn warn" key="wd" onClick=${withdraw}>회원 탈퇴</button>
      <div class="bottompad"></div>
    </div>
  </div>`;
}

// ── 병원·약국 찾기 ───────────────────────────────────────────────
const REGIONS = [
  { name: '서울 강남', lat: 37.4979, lon: 127.0276 }, { name: '서울 시청', lat: 37.5663, lon: 126.9779 },
  { name: '경기 수원', lat: 37.2636, lon: 127.0286 }, { name: '경기 성남', lat: 37.4200, lon: 127.1267 },
  { name: '인천', lat: 37.4563, lon: 126.7052 }, { name: '부산', lat: 35.1577, lon: 129.0594 },
  { name: '대구', lat: 35.8693, lon: 128.6062 }, { name: '대전', lat: 36.3504, lon: 127.3845 },
  { name: '광주', lat: 35.1525, lon: 126.8513 }, { name: '울산', lat: 35.5384, lon: 129.3114 },
  { name: '강원 춘천', lat: 37.8813, lon: 127.7300 }, { name: '충북 청주', lat: 36.6424, lon: 127.4890 },
  { name: '충남 천안', lat: 36.8151, lon: 127.1139 }, { name: '전북 전주', lat: 35.8242, lon: 127.1480 },
  { name: '경북 포항', lat: 36.0190, lon: 129.3435 }, { name: '경남 창원', lat: 35.2280, lon: 128.6811 },
  { name: '제주', lat: 33.4996, lon: 126.5312 },
];

export function FinderView({ go }) {
  const [kind, setKind] = useState('pharmacy');
  const [res, setRes] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [where, setWhere] = useState('');
  const [pick, setPick] = useState(false);
  const race = useLatest();

  async function search(lat, lon, label) {
    setErr(''); setBusy(true); setRes(null); setWhere(label || '');
    const id = race.begin();
    const r = await POST('/facilities', { lat, lon, kind });
    if (!race.accept(id)) return;
    setBusy(false);
    if (!r.ok) { setErr(errText(r)); return; }
    setRes(r.data || {});
  }

  function locate() {
    setErr(''); setRes(null);
    let geo = null;
    try { geo = navigator.geolocation; } catch { geo = null; }
    if (!geo) { setErr('이 기기에서 위치를 쓸 수 없어요. 아래에서 지역을 선택하세요.'); setPick(true); return; }
    setBusy(true);
    try {
      geo.getCurrentPosition(
        (pos) => search(pos.coords.latitude, pos.coords.longitude, '현재 위치(GPS)'),
        (e) => {
          setBusy(false); setPick(true);
          setErr('위치를 가져오지 못했어요' + (e && e.code === 1 ? '(권한 거부)' : '')
            + '. 아래에서 지역을 선택해보세요.');
        },
        { timeout: 15000, enableHighAccuracy: true, maximumAge: 0 });
    } catch {
      setBusy(false); setPick(true); setErr('위치를 가져오지 못했어요. 지역을 선택해주세요.');
    }
  }

  const items = arr(res && res.items);
  const isDemoHospital = res && kind === 'hospital' && !res.real;

  return html`<div key="finder">
    <${Header} title="병원·약국 찾기" onBack=${() => go('health')} />
    <div class="scroll">
      <div class="seg" key="seg">
        <button class=${'segb' + (kind === 'pharmacy' ? ' on' : '')}
          onClick=${() => { setKind('pharmacy'); setRes(null); }}>약국</button>
        <button class=${'segb' + (kind === 'hospital' ? ' on' : '')}
          onClick=${() => { setKind('hospital'); setRes(null); }}>병원</button>
      </div>
      <button class="btn" key="loc" disabled=${busy} onClick=${locate}>
        ${busy ? '찾는 중…' : '📍 내 위치(GPS)로 찾기'}</button>
      <button class="btn ghost" key="pickbtn" style="margin-top:8px"
        onClick=${() => setPick((v) => !v)}>지역 직접 선택</button>
      ${pick ? html`<div class="chips" key="regions" style="margin-top:10px">
        ${REGIONS.map((rg) => html`<button class="chip" key=${rg.name} disabled=${busy}
          onClick=${() => search(rg.lat, rg.lon, rg.name)}>${rg.name}</button>`)}
      </div>` : null}
      ${err ? html`<div class="err" key="ferr">${err}</div>` : null}
      <p class="note">위치는 검색에만 쓰이고 저장하지 않아요 · 거리순 중립 안내(특정 업체 추천 아님).</p>

      ${isDemoHospital ? html`<div class="infobox" key="hosp">
        🏥 <b>병원 실시간 검색은 준비 중이에요.</b> 공공데이터포털 '병원정보서비스' 승인 후 제공됩니다.
        지금은 <b>약국</b> 탭이 실데이터로 동작해요.</div>` : null}

      ${(res && !isDemoHospital) ? html`<div key="results">
        <div class="muted" style="font-size:12px;margin:8px 0 6px">
          ${res.real ? '실데이터' : '예시(데모)'}${where ? ` · 📍 ${where} 기준` : ''}</div>
        ${items.length ? items.map((f, i) => html`<div class="card faccard" key=${str(f.name) + '|' + str(f.addr) + i}>
          <div style="display:flex;justify-content:space-between;align-items:start;gap:8px">
            <div style="font-weight:700">${str(f.name)}</div>
            ${f.open_now === true ? html`<span class="badge open" key="o">영업중</span>`
              : f.open_now === false ? html`<span class="badge closed" key="c">영업종료</span>` : null}
          </div>
          <div class="muted" style="font-size:12.5px">${str(f.dist_label)}${f.hours ? ' · ' + str(f.hours) : ''}${f.addr ? ' · ' + str(f.addr) : ''}</div>
          <div style="display:flex;gap:8px;margin-top:8px">
            ${f.map_url ? html`<a class="btn ghost small" key="map" href=${str(f.map_url)}
              target="_blank" rel="noopener">지도</a>` : null}
            ${f.tel_url ? html`<a class="btn ghost small" key="tel" href=${str(f.tel_url)}>전화</a>` : null}
          </div>
        </div>`) : html`<p class="muted" key="none">주변에서 찾지 못했어요.</p>`}
      </div>` : null}
      <div class="bottompad"></div>
    </div>
  </div>`;
}
