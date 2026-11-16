/* 수첩 디자인 - 랭킹 페이지 입장 색종이 */
(function () {
    'use strict';

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
        document.addEventListener('DOMContentLoaded', initConfetti);
    } else {
        initConfetti();
    }
})();
