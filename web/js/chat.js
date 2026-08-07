// chat.js — '상담' 탭. 순환 ⑥→① 재진입 지점. 정본 §A-2 · §B-6.
//
// 루틴형 전환의 핵심: 상담을 단발 Q&A 로 끝내지 않는다. 답변 말미에
// "이걸 이번 주 행동으로 넣을까요?" 를 붙여 ①→④ 로 되돌린다.

import { useState, useEffect, useRef } from 'preact/hooks';
import { GET, POST, errText } from './api.js';
import { html, Header, Loading, useLatest, arr, str } from './ui.js';

// 답변의 [n] 마커 → 클릭형 출처 링크
function renderAnswer(text, cites) {
  const list = arr(cites);
  return String(text || '').split(/(\[\d+\])/g).map((part, i) => {
    const m = part.match(/^\[(\d+)\]$/);
    if (!m) return part;
    const c = list[Number(m[1]) - 1];
    return (c && c.url)
      ? html`<a key=${'c' + i} class="citelink" href=${c.url} target="_blank"
          rel="noopener" title=${str(c.source)}>${part}</a>`
      : html`<span key=${'c' + i} class="citelink">${part}</span>`;
  });
}

export function ChatTab({ prefill, onConsumePrefill }) {
  const [msgs, setMsgs] = useState([]);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [iv, setIv] = useState(null);        // 문진: {base, questions, idx, answers, intro}
  const [loaded, setLoaded] = useState(false);
  const endRef = useRef(null);
  const sending = useRef(false);
  const race = useLatest();

  // 히스토리 복원(실패해도 대화는 가능)
  useEffect(() => {
    let alive = true;
    GET('/chat/history').then((r) => {
      if (!alive) return;
      const list = (r.ok && arr(r.data && r.data.messages)) || [];
      if (list.length) {
        setMsgs(list.map((m, i) => (m && m.role === 'user'
          ? { me: true, text: str(m.text), id: 'h' + i }
          : { ai: true, text: str(m && m.text), citations: arr(m && m.citations),
              personalize: !!(m && m.personalize), id: 'h' + i })));
      }
      setLoaded(true);
    }).catch(() => setLoaded(true));
    return () => { alive = false; };
  }, []);

  useEffect(() => {
    try { if (endRef.current) endRef.current.scrollIntoView({ behavior: 'smooth' }); } catch { /* noop */ }
  }, [msgs, iv, busy]);

  async function send(q) {
    const query = String(q == null ? text : q).trim();
    if (!query || sending.current) return;
    sending.current = true;
    setText(''); setIv(null); setBusy(true);
    setMsgs((m) => [...m, { me: true, text: query, id: 'u' + Date.now() }]);
    const id = race.begin();
    try {
      const r = await POST('/chat', { message: query });
      if (!race.accept(id)) return;
      if (!r.ok) {
        setMsgs((m) => [...m, { ai: true, text: errText(r), id: 'e' + Date.now() }]);
        return;
      }
      const body = r.data || {};
      const rag = body.rag && typeof body.rag === 'object' ? body.rag : {};
      const answer = str(rag.answer) || str(rag.echo)
        || (rag.error ? '답변을 불러오지 못했어요.' : '답변을 준비하지 못했어요.');
      setMsgs((m) => [...m, {
        ai: true, text: answer, citations: arr(rag.citations),
        personalize: !!body.personalization, id: 'a' + Date.now(),
      }]);
      const c = body.clarifiers;
      if (c && arr(c.questions).length) {
        setIv({ base: query, questions: arr(c.questions), idx: 0, answers: [], intro: str(c.intro) });
      }
    } catch {
      if (race.accept(id)) {
        setMsgs((m) => [...m, { ai: true, text: '일시적인 오류가 발생했어요.', id: 'x' + Date.now() }]);
      }
    } finally {
      sending.current = false;
      if (race.alive()) setBusy(false);
    }
  }

  // 탭 밖(오늘/리포트)에서 넘어온 질문 자동 전송
  useEffect(() => {
    if (loaded && prefill) {
      const q = prefill;
      if (onConsumePrefill) onConsumePrefill();
      send(q);
    }
  }, [loaded, prefill]);

  function answerIv(opt) {
    setIv((cur) => {
      if (!cur) return null;
      const answers = cur.answers.concat(opt);
      if (cur.idx + 1 < cur.questions.length) return { ...cur, idx: cur.idx + 1, answers };
      setTimeout(() => send(cur.base + ' / 문진: ' + answers.join(', ')), 0);
      return null;
    });
  }

  if (!loaded) return html`<div key="cl"><${Header} title="상담" /><${Loading} /></div>`;

  const ivQ = iv && iv.questions[iv.idx];

  return html`<div key="chat" class="chatwrap">
    <${Header} title="상담" />
    <div class="chat">
      ${msgs.length === 0 ? html`<div class="msg ai" key="greet">
        안녕하세요. 건강에 대해 궁금한 점을 물어보세요. 루틴을 하다 생긴 질문도 좋아요.
      </div>` : null}
      ${msgs.map((m) => html`<div class=${'msg ' + (m.me ? 'me' : 'ai')} key=${m.id}>
        ${m.personalize ? html`<div class="badge" key="b">맞춤 안내</div>` : null}
        ${m.me ? m.text : renderAnswer(m.text, m.citations)}
        ${(!m.me && arr(m.citations).length) ? html`<div class="sources" key="s">
          <div class="srctitle">출처 ${arr(m.citations).length}</div>
          ${arr(m.citations).map((c, i) => html`<a class="srcrow" key=${'s' + i}
              href=${str(c.url) || '#'} target=${c.url ? '_blank' : undefined} rel="noopener">
            <b>[${i + 1}]</b> ${str(c.source)}${c.title ? ' — ' + str(c.title) : ''}</a>`)}
        </div>` : null}
      </div>`)}

      ${ivQ ? html`<div class="msg ai iv" key="iv">
        <div class="ivintro">🩺 ${iv.intro || '조금 더 좁혀 드릴까요?'}</div>
        <div class="ivq"><b>(${iv.idx + 1}/${iv.questions.length})</b> ${str(ivQ.q)}</div>
        <div class="chips">
          ${arr(ivQ.options).map((o) => html`<button class="chip" key=${o}
            onClick=${() => answerIv(o)}>${o}</button>`)}
          <button class="chip ghost" key="skip" onClick=${() => setIv(null)}>괜찮아요</button>
        </div>
      </div>` : null}

      ${busy ? html`<div class="msg ai typing" key="typing">
        <span class="dots"><i></i><i></i><i></i></span><span>답변을 준비하고 있어요…</span>
      </div>` : null}
      <div ref=${endRef}></div>
    </div>
    <div class="composer">
      <input value=${text} placeholder="증상이나 건강 질문을 입력하세요"
        aria-label="질문 입력"
        onInput=${(e) => setText(e.target.value)}
        onKeyDown=${(e) => { if (e.key === 'Enter') send(); }} />
      <button class="btn sendbtn" disabled=${busy} onClick=${() => send()}>전송</button>
    </div>
  </div>`;
}
