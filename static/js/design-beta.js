/* 새 디자인(수첩) 체험 - 안내 팝업 / 투표 띠 */
(function () {
    'use strict';

    function getCookie(name) {
        var m = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
        return m ? decodeURIComponent(m.pop()) : '';
    }

    function csrfToken() {
        var input = document.querySelector('input[name=csrfmiddlewaretoken]');
        return (input && input.value) || getCookie('csrftoken');
    }

    function post(url, data) {
        var body = new URLSearchParams(data || {});
        return fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': csrfToken(),
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: body.toString(),
            credentials: 'same-origin'
        });
    }

    /* ---------- 안내 팝업 ---------- */
    function initPopup() {
        var popup = document.getElementById('betaPopup');
        if (!popup) return;

        // 첫 화면을 가리지 않도록 잠깐 뒤에 보여준다
        setTimeout(function () { popup.classList.add('show'); }, 700);

        function close(days) {
            popup.classList.remove('show');
            setTimeout(function () { popup.remove(); }, 260);
            post('/design/popup/dismiss/', { days: days || '' }).catch(function () {});
        }

        popup.querySelectorAll('[data-dismiss]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                close(btn.getAttribute('data-dismiss') === '7' ? '7' : '');
            });
        });

        // 바깥 클릭 / ESC 는 이번 방문만 숨김
        popup.addEventListener('click', function (e) {
            if (e.target === popup) close('');
        });
        document.addEventListener('keydown', function onEsc(e) {
            if (e.key === 'Escape' && document.getElementById('betaPopup')) {
                close('');
                document.removeEventListener('keydown', onEsc);
            }
        });
    }

    /* ---------- 투표 띠 ---------- */
    function initVoteBar() {
        var bar = document.getElementById('betaVoteBar');
        if (!bar) return;

        var reopen = document.getElementById('betaVoteReopen');
        var result = document.getElementById('betaVoteResult');
        var ask = bar.querySelector('.bv-ask');
        var thanks = bar.querySelector('.bv-thanks');
        var buttons = bar.querySelectorAll('.bv-btn');

        function markVoted(choice) {
            buttons.forEach(function (b) {
                b.classList.toggle('chosen', b.getAttribute('data-choice') === choice);
            });
            if (ask) ask.hidden = true;
            if (thanks) thanks.hidden = false;
        }

        function showTally(t) {
            if (!result || !t) return;
            document.getElementById('bvrNew').textContent = t.new;
            document.getElementById('bvrOld').textContent = t.old;
            document.getElementById('bvrFill').style.width = t.new_pct + '%';
            result.hidden = false;
        }

        // 이미 투표한 상태로 들어온 경우
        var already = bar.getAttribute('data-voted');
        if (already) markVoted(already);

        buttons.forEach(function (btn) {
            btn.addEventListener('click', function () {
                var choice = btn.getAttribute('data-choice');
                buttons.forEach(function (b) { b.disabled = true; });
                post('/design/vote/', { choice: choice })
                    .then(function (r) { return r.json(); })
                    .then(function (data) {
                        buttons.forEach(function (b) { b.disabled = false; });
                        if (!data.ok) return;
                        markVoted(data.choice);
                        showTally(data.tally);
                    })
                    .catch(function () {
                        buttons.forEach(function (b) { b.disabled = false; });
                    });
            });
        });

        // 접기 / 다시 열기 (이번 방문 동안만 기억)
        var HIDDEN_KEY = 'pd_votebar_hidden';
        function setHidden(hidden) {
            bar.hidden = hidden;
            if (reopen) reopen.hidden = !hidden;
            try { sessionStorage.setItem(HIDDEN_KEY, hidden ? '1' : '0'); } catch (e) {}
        }
        try {
            if (sessionStorage.getItem(HIDDEN_KEY) === '1') setHidden(true);
        } catch (e) {}

        var closeBtn = document.getElementById('betaVoteClose');
        if (closeBtn) closeBtn.addEventListener('click', function () { setHidden(true); });
        if (reopen) reopen.addEventListener('click', function () { setHidden(false); });
    }


    /* ---------- 랭킹 페이지 입장 색종이 ---------- */
    function initConfetti() {
        if (document.body.dataset.ui !== 'notebook') return;
        if (!document.querySelector('.hall-of-fame')) return;   // 랭커가 있을 때만
        try {
            if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
        } catch (e) {}

        var layer = document.createElement('div');
        layer.className = 'nb-confetti';
        layer.setAttribute('aria-hidden', 'true');

        var colours = ['c1', 'c2', 'c3', 'c4', 'c5'];
        var shapes = ['', 'round', 'slim'];
        var count = window.innerWidth < 600 ? 28 : 46;

        for (var i = 0; i < count; i++) {
            var piece = document.createElement('i');
            piece.className = colours[i % colours.length] + ' ' + shapes[i % shapes.length];
            piece.style.left = Math.random() * 100 + '%';
            piece.style.animationDuration = (2.4 + Math.random() * 1.8).toFixed(2) + 's';
            piece.style.animationDelay = (Math.random() * 0.9).toFixed(2) + 's';
            piece.style.setProperty('--nb-drift', (Math.random() * 160 - 80).toFixed(0) + 'px');
            piece.style.setProperty('--nb-spin', (Math.random() * 900 - 300).toFixed(0) + 'deg');
            layer.appendChild(piece);
        }

        document.body.appendChild(layer);
        setTimeout(function () { layer.remove(); }, 6000);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () { initPopup(); initVoteBar(); initConfetti(); });
    } else {
        initPopup();
        initVoteBar();
        initConfetti();
    }
})();
