/* 피크민 — 이름 옆 표식과 복사 효과
 *
 * SVG 를 여기 한 곳에서만 만든다. 장고는 <span class="pk-mark" data-*> 만 내보내고
 * 생김새는 전부 이 파일이 정한다. 두 군데서 같은 그림을 그리면 반드시 어긋난다.
 *
 * data 속성
 *   data-pk-c  피크민 색   red yellow blue white pink rock purple ice
 *   data-pk-f  꽃 색       pink white yellow red blue
 *   data-pk-l  잎 모양     0~4
 *   data-pk-t  머리        leaf bud flower
 *   data-pk-h  마릿수      1~12
 *   data-pk-s  보조색      무리에 섞이는 색
 *   data-pk-m  탈것        turtle (전용) 또는 빈 값
 */
(function () {
'use strict';

const PK = {
  red   :{label:'빨강', feat:'nose'},
  yellow:{label:'노랑', feat:'ears'},
  blue  :{label:'파랑', feat:'gills'},
  white :{label:'흰색', feat:'none'},
  pink  :{label:'분홍', feat:'wings', fly:true},
  rock  :{label:'바위', feat:'rock'},
  purple:{label:'보라', feat:'fat'},
  ice   :{label:'얼음', feat:'none'}
};

/* ── 머리: 등급이 정한다. 색과 무관하게 자란다 ── */
function headSvg(tier, dy){
  const y = n => (n + dy).toFixed(1);
  if (tier === 'flower')
    return `<g class="stem"><line x1="12" y1="${y(12)}" x2="12" y2="${y(7.5)}" stroke="var(--pk-dark)" stroke-width="1.4" stroke-linecap="round"/>
      <ellipse cx="12" cy="${y(3.4)}" rx="2.3" ry="3.1" fill="var(--fl)" stroke="var(--fl-d)" stroke-width=".4"/>
      <ellipse cx="9.2" cy="${y(5.4)}" rx="2.3" ry="3.1" transform="rotate(-55 9.2 ${y(5.4)})" fill="var(--fl)" stroke="var(--fl-d)" stroke-width=".4"/>
      <ellipse cx="14.8" cy="${y(5.4)}" rx="2.3" ry="3.1" transform="rotate(55 14.8 ${y(5.4)})" fill="var(--fl)" stroke="var(--fl-d)" stroke-width=".4"/>
      <circle cx="12" cy="${y(5.2)}" r="1.5" fill="var(--fl-c)"/></g>`;
  if (tier === 'bud')
    return `<g class="stem"><line x1="12" y1="${y(12)}" x2="12" y2="${y(7)}" stroke="var(--pk-dark)" stroke-width="1.4" stroke-linecap="round"/>
      <ellipse cx="12" cy="${y(4.6)}" rx="2.9" ry="3.9" fill="var(--fl-d)"/>
      <ellipse cx="12" cy="${y(3.5)}" rx="1.8" ry="2.5" fill="var(--fl)" opacity=".85"/></g>`;
  // 잎은 셋 다 그려두고 CSS 로 고른다 — 클래스만 바꾸면 되니 간단하다
  return `<g class="stem"><line x1="12" y1="${y(12)}" x2="12" y2="${y(6)}" stroke="var(--pk-dark)" stroke-width="1.4" stroke-linecap="round"/>
      <ellipse class="leaf lf1" cx="12" cy="${y(4)}" rx="4.2" ry="2.7"/>
      <ellipse class="leaf lf2a" cx="9.1" cy="${y(4.3)}" rx="3.2" ry="2.0" transform="rotate(-26 9.1 ${y(4.3)})"/>
      <ellipse class="leaf lf2b" cx="14.9" cy="${y(4.3)}" rx="3.2" ry="2.0" transform="rotate(26 14.9 ${y(4.3)})"/>
      <ellipse class="leaf lf3" cx="12" cy="${y(2.8)}" rx="2.0" ry="3.0"/></g>`;
}

/* ── 몸: 색이 정한다 ── */
function bodySvg(color, dy){
  const y = n => (n + dy).toFixed(1);
  const f = PK[color] ? PK[color].feat : 'none';
  let extra = '', body;

  if (f === 'rock')     body = `<path class="body" d="M12 ${y(11.6)} L18.3 ${y(15.4)} L18.9 ${y(22.6)} L12 ${y(26.8)} L5.1 ${y(22.6)} L5.7 ${y(15.4)} Z"/>`;
  else if (f === 'fat') body = `<ellipse class="body" cx="12" cy="${y(19)}" rx="7.4" ry="7.6"/>`;
  else                  body = `<ellipse class="body" cx="12" cy="${y(19)}" rx="6.6" ry="7.6"/>`;

  if (f === 'nose')  extra += `<path d="M12 ${y(19.6)} L12 ${y(22.4)} L14.1 ${y(21.2)} Z" fill="var(--pk-dark)"/>`;
  if (f === 'ears')  extra += `<ellipse cx="4.3" cy="${y(16.2)}" rx="2.5" ry="3.6" transform="rotate(-24 4.3 ${y(16.2)})" fill="var(--pk)" stroke="var(--pk-dark)" stroke-width=".5"/>
                               <ellipse cx="19.7" cy="${y(16.2)}" rx="2.5" ry="3.6" transform="rotate(24 19.7 ${y(16.2)})" fill="var(--pk)" stroke="var(--pk-dark)" stroke-width=".5"/>`;
  if (f === 'gills') extra += `<path d="M9 ${y(22.6)} Q12 ${y(25.2)} 15 ${y(22.6)}" stroke="var(--pk-dark)" stroke-width="1.1" fill="none" stroke-linecap="round"/>`;
  if (f === 'wings') extra += `<ellipse class="wing wingL" cx="4.6" cy="${y(17.4)}" rx="4.4" ry="2.5" transform="rotate(-22 4.6 ${y(17.4)})"/>
                               <ellipse class="wing wingR" cx="19.4" cy="${y(17.4)}" rx="4.4" ry="2.5" transform="rotate(22 19.4 ${y(17.4)})"/>`;

  return `${f === 'wings' ? extra : ''}
    <g class="face">${body}
      <ellipse cx="9.6" cy="${y(17.4)}" rx="1.5" ry="2.1" fill="#fff" stroke="var(--pk-dark)" stroke-width=".35"/>
      <ellipse cx="14.4" cy="${y(17.4)}" rx="1.5" ry="2.1" fill="#fff" stroke="var(--pk-dark)" stroke-width=".35"/>
      <circle class="pupil" cx="9.8" cy="${y(17.7)}" r=".9"/><circle class="pupil" cx="14.2" cy="${y(17.7)}" r=".9"/>
      ${f === 'wings' ? '' : extra}
    </g>`;
}

/* ── 다리: 발이 있어야 땅에 닿는다. 선 끝만 둥글면 매달린 것처럼 보인다 ── */
function legsSvg(dy){
  const y = n => (n + dy).toFixed(1);
  return `<g class="legL"><line class="leg" x1="10.4" y1="${y(21.6)}" x2="9.9" y2="${y(29.7)}"/>
      <ellipse class="foot" cx="9.7" cy="${y(30.4)}" rx="2.0" ry="1.15"/></g>
    <g class="legR"><line class="leg" x1="13.6" y1="${y(21.6)}" x2="14.1" y2="${y(29.7)}"/>
      <ellipse class="foot" cx="14.3" cy="${y(30.4)}" rx="2.0" ry="1.15"/></g>`;
}

/* ── 팔: 다리와 반대로 흔든다. 걷는다는 신호 중 제일 읽기 쉽다 ── */
function armsSvg(dy){
  const y = n => (n + dy).toFixed(1);
  return `<line class="arm armL" x1="9.6" y1="${y(19.4)}" x2="4.6" y2="${y(24.4)}"/>
    <line class="arm armR" x1="14.4" y1="${y(19.4)}" x2="19.4" y2="${y(24.4)}"/>`;
}

/* ── 한 마리 전체. 쌓는 순서가 걸음의 전부다.
     그림자는 기울기 밖에 둔다(땅은 안 기운다).
     다리는 bod 밖에 둔다(몸이 내려앉아도 발은 땅에 남는다). ── */
function figure(color, tier, dy){
  const y = n => (n + dy).toFixed(1);
  return `
    <ellipse class="shadow" cx="12" cy="${y(31.2)}" rx="5.6" ry="1.35"/>
    <g class="lean">
      ${legsSvg(dy)}
      <g class="bod"><g class="tilt">
        ${headSvg(tier, dy)}
        ${armsSvg(dy)}
        ${bodySvg(color, dy)}
      </g></g>
    </g>`;
}

function pikmin(color, tier, opts){
  opts = opts || {};
  const cls = ['pk', 'c-' + (color || 'red'), 'f-' + (opts.fl || 'pink'),
               'lv-' + (opts.lv == null ? 0 : opts.lv)];
  if (opts.walk) cls.push('walk');
  if (PK[color] && PK[color].fly) cls.push('fly');
  const size = opts.size || 'width:1.45em;height:2em;vertical-align:-.6em';
  // 걸음 위상을 어긋나게 한다. --d 없이 animation-delay만 주면
  // 자식 애니메이션엔 상속되지 않아 무리 전체가 발을 맞춰 걷는다.
  const d = opts.delay ? ';--d:' + (-opts.delay).toFixed(2) + 's' : '';
  return `<svg class="${cls.join(' ')}" viewBox="0 0 24 33" aria-hidden="true"
      style="${size}${d}">${figure(color, tier, 0, false)}</svg>`;
}

function runnerSvg(color, tier){
  return figure(color, tier, 1);
}

/* ── 🐢 정면에서 걸어오는 거북이 + 등에 탄 피크민 (달리는거북이님 전용) ──
   viewBox 0 0 44 42. 옆모습이 아니라 이쪽으로 온다.
   쌓는 순서: 뒷다리 → 등껍질 → 머리 → 앞다리 → 올라탄 피크민 */
function turtleSvg(color, tier){
  return `
    <ellipse class="shadow" cx="22" cy="39.2" rx="13.6" ry="1.6"/>
    <g class="tlegs">
      <ellipse class="skin dim" cx="8.4" cy="32.6" rx="3.1" ry="2.5"/>
      <ellipse class="skin dim" cx="35.6" cy="32.6" rx="3.1" ry="2.5"/>
    </g>
    <g class="tbod">
      <path class="shell" d="M5 31.6 A17.5 13 0 0 1 39 31.6 Z"/>
      <ellipse class="rim" cx="22" cy="31.6" rx="17" ry="2.6"/>
      <path class="plate" d="M22 20.6 L28.2 25 L25.9 31 L18.1 31 L15.8 25 Z"/>
      <ellipse class="plate" cx="10.6" cy="29.2" rx="3.6" ry="2.1"/>
      <ellipse class="plate" cx="33.4" cy="29.2" rx="3.6" ry="2.1"/>
      <ellipse class="plate" cx="22" cy="23.4" rx="3.1" ry="1.7" opacity=".55"/>
    </g>
    <g class="tleg tlegL"><rect class="skin" x="9.2" y="31.0" width="5.4" height="7.6" rx="2.7"/></g>
    <g class="tleg tlegR"><rect class="skin" x="29.4" y="31.0" width="5.4" height="7.6" rx="2.7"/></g>
    <g class="thead">
      <ellipse class="skin" cx="22" cy="35.4" rx="4.2" ry="3.2"/>
      <circle cx="20.5" cy="34.7" r=".8" fill="#1B5E20"/>
      <circle cx="23.5" cy="34.7" r=".8" fill="#1B5E20"/>
      <path d="M20.8 36.8 Q22 37.7 23.2 36.8" stroke="#33691E" stroke-width=".7"
            fill="none" stroke-linecap="round"/>
    </g>
    <g class="rider" transform="translate(15.3,0.9) scale(.56)">
      <g class="legL"><line class="leg" x1="10.3" y1="26.2" x2="9.2" y2="32.4"/>
        <ellipse class="foot" cx="9.0" cy="33.1" rx="2.0" ry="1.15"/></g>
      <g class="legR"><line class="leg" x1="13.7" y1="26.2" x2="14.8" y2="32.4"/>
        <ellipse class="foot" cx="15.0" cy="33.1" rx="2.0" ry="1.15"/></g>
      <g class="bod"><g class="tilt">
        ${headSvg(tier, 2)}
        ${armsSvg(2)}
        ${bodySvg(color, 2)}
      </g></g>
    </g>`;
}


/* ── 이름 옆 표식 그리기 ─────────────────────────────── */
function look(el){
  const d = el.dataset;
  return {
    c: d.pkC || 'red', f: d.pkF || 'pink', l: +(d.pkL || 0),
    t: d.pkT || 'leaf', h: +(d.pkH || 1), s: d.pkS || d.pkC || 'red',
    m: d.pkM || ''
  };
}

function markSvg(k, walking){
  if (k.m === 'turtle')
    return `<svg class="pk tt${walking ? ' go' : ''} c-${k.c} f-${k.f} lv-${k.l}"
      viewBox="0 0 44 42" aria-hidden="true" focusable="false"
      style="width:100%;height:100%">${turtleSvg(k.c, k.t)}</svg>`;
  return pikmin(k.c, k.t, {walk: walking, fl: k.f, lv: k.l,
    size: 'width:100%;height:100%'});
}

/* 화면 안에 있을 때만 걷는다.
   목록 20장이면 영구 애니메이션이 120개다 — 안 보이는 것까지 돌 이유가 없다. */
let io = null;
function watch(el){
  if (!('IntersectionObserver' in window)) { el.classList.add('pk-on'); return; }
  if (!io) io = new IntersectionObserver(entries => {
    entries.forEach(e => e.target.classList.toggle('pk-on', e.isIntersecting));
  }, {rootMargin: '120px'});
  io.observe(el);
}

function drawMarks(root){
  const q = (root || document).querySelectorAll('.pk-mark:not([data-pk-done])');
  q.forEach(el => {
    el.setAttribute('data-pk-done', '1');
    if (el.dataset.pkShow === '0') return;   // 안 켠 사람은 안 그린다
    const k = look(el);
    if (k.m) el.classList.add('has-mount');
    el.innerHTML = markSvg(k, true);
    watch(el);
  });
}

/* ── 복사하면 무리가 지나간다 ─────────────────────────── */
function parade(card, k, mark){
  let box = card.querySelector('.pk-runners');
  if (!box) {
    box = document.createElement('div');
    box.className = 'pk-runners';
    box.setAttribute('aria-hidden', 'true');
    card.appendChild(box);
  }
  // 어디를 땅으로 삼을지 정한다.
  // 사진 아래끝이 제일 자연스럽다 — 작성자 줄과 통계 사이엔 16px 밖에 없어서
  // 거기 두면 좋아요·조회수 숫자를 가린다.
  const b = card.getBoundingClientRect();
  const ground = card.querySelector('.coord-card-image, .coord-card-placeholder');
  const stats = card.querySelector('.coord-card-stats');
  let top;
  if (ground) top = ground.getBoundingClientRect().bottom - b.top - 36;
  else if (stats) top = stats.getBoundingClientRect().top - b.top - 38;
  else if (mark) top = mark.getBoundingClientRect().bottom - b.top + 2;
  else top = b.height - 40;
  box.style.top = Math.max(0, Math.min(top, b.height - 36)).toFixed(0) + 'px';
  let html = '';
  for (let i = 0; i < k.h; i++) {
    const delay = (i * 0.085).toFixed(3);
    if (i === 0 && k.m === 'turtle') {
      html += `<svg class="pk tt go runner rider c-${k.c} f-${k.f} lv-${k.l}"
        viewBox="0 0 44 42" aria-hidden="true" focusable="false"
        style="animation-delay:${delay}s">${turtleSvg(k.c, k.t)}</svg>`;
    } else {
      // 주색 둘에 보조색 하나꼴로 섞인다. 실제 블룸 분대도 섞여 다닌다
      const c = (i % 3 === 2) ? k.s : k.c;
      html += `<svg class="pk runner c-${c} f-${k.f} lv-${k.l}${PK[c] && PK[c].fly ? ' fly' : ''}"
        viewBox="0 0 24 34" aria-hidden="true" focusable="false"
        style="animation-delay:${delay}s;--d:${(-delay * 0.41).toFixed(2)}s">${runnerSvg(c, k.t)}</svg>`;
    }
  }
  box.innerHTML = '';
  void box.offsetWidth;          // 리플로우 강제 — 연달아 눌러도 처음부터 다시 간다
  // left 를 움직이면 매 프레임 레이아웃을 다시 잰다. transform 은 GPU 가 한다.
  // 얼마나 가야 하는지는 여기서만 알 수 있어서 변수로 넘긴다.
  box.style.setProperty('--span', (box.clientWidth + 130) + 'px');
  box.innerHTML = html;
  clearTimeout(box._t);
  box._t = setTimeout(() => { box.innerHTML = ''; }, 1900);
}

/* 복사 버튼에서 부른다.
   기존 핸들러가 stopPropagation 을 하므로 버블로는 못 듣는다 —
   handleCopy 가 직접 부르고, 못 부르는 경로는 캡처 단계로 받는다. */
function paradeFrom(btn){
  if (!btn) return;
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const card = btn.closest('[data-pk-stage]') || btn.closest('.coord-card') ||
               btn.closest('.coord-detail-card') || btn.closest('.card');
  if (!card) return;
  const mark = card.querySelector('.pk-mark');
  if (!mark) return;
  if (getComputedStyle(card).position === 'static') card.style.position = 'relative';
  parade(card, look(mark), mark);
}
window.pikminParade = paradeFrom;

document.addEventListener('click', e => {
  const btn = e.target.closest('.copy-btn, .copy-coords-btn, [data-pk-copy]');
  if (btn) paradeFrom(btn);
}, true);   // 캡처 — stopPropagation 보다 먼저 지나간다

/* ── 설정 화면: 고르면 미리보기가 바로 바뀐다 ────────── */
function syncSettings(){
  const prev = document.getElementById('pk-preview');
  if (!prev) return;
  const c = document.querySelector('#pk-colors input[name="pikmin_color"]:checked');
  const f = document.querySelector('#pk-flowers input[name="pikmin_flower"]:checked');
  const m = document.querySelector('#pk-colors input[name="pikmin_mount"]');
  const color  = c ? c.value : prev.dataset.pkC;
  const flower = f ? f.value : prev.dataset.pkF;
  const leaf   = f ? [...document.querySelectorAll('#pk-flowers input')].indexOf(f) : +prev.dataset.pkL;
  const mount  = (m && m.checked) ? m.value : '';

  prev.dataset.pkC = color; prev.dataset.pkF = flower;
  prev.dataset.pkL = leaf;  prev.dataset.pkM = mount;
  prev.dataset.pkS = color;
  prev.classList.toggle('has-mount', !!mount);
  prev.innerHTML = markSvg(look(prev), true);

  // 칩 그림도 지금 고른 값에 맞춘다 — 빨강을 고르면 꽃 칩도 빨강이 된다
  document.querySelectorAll('#pk-flowers .pk-chip-art').forEach(el => {
    el.dataset.pkC = color; el.dataset.pkS = color;
    el.innerHTML = markSvg(look(el), true);
  });
  document.querySelectorAll('#pk-colors .pk-chip:not(.pk-chip-mount) .pk-chip-art').forEach(el => {
    el.dataset.pkF = flower; el.dataset.pkL = leaf;
    el.innerHTML = markSvg(look(el), true);
  });
  document.querySelectorAll('#pk-colors .pk-chip-mount .pk-chip-art').forEach(el => {
    el.dataset.pkC = color; el.dataset.pkF = flower; el.dataset.pkL = leaf; el.dataset.pkS = color;
    el.innerHTML = markSvg(look(el), true);
  });
}
document.addEventListener('change', e => {
  if (e.target.closest('#pk-colors, #pk-flowers')) syncSettings();
});

/* HTMX 로 목록이 갈아끼워져도 다시 그린다 */
document.addEventListener('DOMContentLoaded', () => drawMarks());
document.body && drawMarks();
document.addEventListener('htmx:afterSettle', e => drawMarks(e.target));
document.addEventListener('htmx:afterSwap', e => drawMarks(e.target));
window.pikminDraw = drawMarks;

})();
