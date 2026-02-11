/**
 * 메인 JavaScript
 */

// TRANSLATIONS 안전 접근 헬퍼
function t(key) {
    return (typeof TRANSLATIONS !== 'undefined' && TRANSLATIONS[key]) || key;
}

// ============================================
// 테마 선택 (계절/날씨)
// ============================================

// 테마 선택기 토글
function toggleThemeSelector() {
    const selector = document.querySelector('.theme-selector');
    selector.classList.toggle('open');
}

// 테마 선택기 닫기
function closeThemeSelector() {
    const selector = document.querySelector('.theme-selector');
    if (selector) selector.classList.remove('open');
}

// 수동 테마 설정
function setTheme(season, weather) {
    document.body.setAttribute('data-season', season);
    document.body.setAttribute('data-weather', weather);

    // localStorage에 저장 (페이지 이동해도 유지)
    localStorage.setItem('manualTheme', JSON.stringify({ season, weather }));
    localStorage.removeItem('autoTheme'); // 자동 모드 해제

    // 드롭다운 닫기
    closeThemeSelector();

    // 토스트 메시지
    var seasonNames = { spring: '🌸 ' + t('spring'), summer: '🌻 ' + t('summer'), fall: '🍂 ' + t('fall'), winter: '❄️ ' + t('winter') };
    var weatherNames = { clear: '☀️ ' + t('clear'), rain: '🌧️ ' + t('rain'), snow: '🌨️ ' + t('snow'), storm: '⛈️ ' + t('storm'), cloudy: '☁️ ' + t('cloudy'), wind: '💨 ' + t('wind') };

    showToast(seasonNames[season] + ' - ' + weatherNames[weather] + ' ' + t('themeApplied'));
}

// 자동 테마 (위치 기반)
function setAutoTheme() {
    localStorage.removeItem('manualTheme');
    localStorage.removeItem('manualTime');  // 시간대도 자동으로
    localStorage.setItem('autoTheme', 'true');

    closeThemeSelector();

    // 페이지 새로고침으로 자동 테마 적용
    showToast('🔄 ' + t('autoThemeSwitch'), 'success');
    setTimeout(() => location.reload(), 1000);
}

// 페이지 로드 시 저장된 테마 적용 & 이벤트 설정
document.addEventListener('DOMContentLoaded', () => {
    // 저장된 테마 적용
    const manualTheme = localStorage.getItem('manualTheme');
    if (manualTheme) {
        const { season, weather } = JSON.parse(manualTheme);
        document.body.setAttribute('data-season', season);
        document.body.setAttribute('data-weather', weather);
    }

    // 낮/밤 시간대 설정
    setDayNightTime();

    // 테마 버튼 클릭 이벤트 (모든 버튼에 적용)
    const themeBtns = document.querySelectorAll('.theme-btn');
    themeBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const selector = btn.closest('.theme-selector');
            if (selector) {
                document.querySelectorAll('.theme-selector').forEach(s => {
                    if (s !== selector) {
                        s.classList.remove('open');
                        s.querySelector('.theme-btn')?.setAttribute('aria-expanded', 'false');
                    }
                });
                // 언어 선택기 닫기
                document.querySelectorAll('.language-selector').forEach(s => s.classList.remove('open'));
                const isOpen = selector.classList.toggle('open');
                btn.setAttribute('aria-expanded', isOpen);
            }
        });
    });

    // 언어 선택 버튼 클릭 이벤트
    const langBtns = document.querySelectorAll('.lang-btn');
    langBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const selector = btn.closest('.language-selector');
            if (selector) {
                document.querySelectorAll('.language-selector').forEach(s => {
                    if (s !== selector) s.classList.remove('open');
                });
                // 테마 선택기 닫기
                document.querySelectorAll('.theme-selector').forEach(s => {
                    s.classList.remove('open');
                    s.querySelector('.theme-btn')?.setAttribute('aria-expanded', 'false');
                });
                const isOpen = selector.classList.toggle('open');
                btn.setAttribute('aria-expanded', isOpen);
            }
        });
    });

    // 외부 클릭 시 닫기
    document.addEventListener('click', (e) => {
        document.querySelectorAll('.theme-selector').forEach(selector => {
            if (!selector.contains(e.target)) {
                selector.classList.remove('open');
                selector.querySelector('.theme-btn')?.setAttribute('aria-expanded', 'false');
            }
        });
        document.querySelectorAll('.language-selector').forEach(selector => {
            if (!selector.contains(e.target)) {
                selector.classList.remove('open');
            }
        });
    });

    // 위치 기반 언어 자동 감지 (첫 방문 시)
});

// 낮/밤 시간대 설정 (6시~18시 낮, 나머지 밤) - 자동 모드일 때만
function setDayNightTime() {
    // 수동 설정이 있으면 사용
    const manualTime = localStorage.getItem('manualTime');
    if (manualTime) {
        document.body.setAttribute('data-time', manualTime);
        return;
    }

    // 자동 설정
    const hour = new Date().getHours();
    const isDay = hour >= 6 && hour < 18;
    document.body.setAttribute('data-time', isDay ? 'day' : 'night');
}

// 수동 낮/밤 선택
function setTimeMode(mode) {
    document.body.setAttribute('data-time', mode);
    localStorage.setItem('manualTime', mode);
    closeThemeSelector();

    showToast(mode === 'day' ? t('dayMode') : t('nightMode'));
}


// ============================================
// CSRF 토큰 가져오기
// ============================================
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

const csrftoken = getCookie('csrftoken');

// Fetch 기본 설정
function fetchWithCSRF(url, options = {}) {
    return fetch(url, {
        ...options,
        headers: {
            'X-CSRFToken': csrftoken,
            'Content-Type': 'application/x-www-form-urlencoded',
            ...options.headers,
        },
    });
}

// 좋아요 토글
async function toggleLike(coordinateId, button) {
    try {
        const res = await fetchWithCSRF(`/interactions/like/${coordinateId}/`, {
            method: 'POST',
        });
        const data = await res.json();

        // UI 업데이트
        const icon = button.querySelector('.like-icon');
        const count = button.querySelector('.like-count');

        if (data.liked) {
            button.classList.add('active');
            icon.textContent = '❤️';
        } else {
            button.classList.remove('active');
            icon.textContent = '🤍';
        }
        count.textContent = data.like_count;
    } catch (error) {
        console.error('Like toggle failed:', error);
    }
}

// 북마크 토글
async function toggleBookmark(coordinateId, button) {
    try {
        const res = await fetchWithCSRF(`/interactions/bookmark/${coordinateId}/`, {
            method: 'POST',
        });
        const data = await res.json();

        // UI 업데이트
        const icon = button.querySelector('.bookmark-icon');

        if (data.bookmarked) {
            button.classList.add('active');
            icon.textContent = '⭐';
        } else {
            button.classList.remove('active');
            icon.textContent = '☆';
        }
    } catch (error) {
        console.error('Bookmark toggle failed:', error);
    }
}

// 좌표 복사 (iOS/Safari 호환)
function copyCoords(coordinateId) {
    // 버튼 찾기
    var copyBtn = document.querySelector('.coords-box .btn-primary');

    // API 호출하여 좌표 가져오기
    fetch('/coordinates/' + coordinateId + '/copy-coords/')
        .then(function (res) { return res.json(); })
        .then(function (data) {
            var text = data.coords;

            function showSuccess() {
                if (copyBtn) {
                    copyBtn.innerHTML = '✅ ' + t('copied');
                    setTimeout(function () {
                        copyBtn.innerHTML = '📋 ' + t('copy');
                    }, 1500);
                }
                showToast(t('coordsCopied'));
            }

            // iOS/Safari 감지
            var isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) ||
                (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
            var isSafari = /^((?!chrome|android).)*safari/i.test(navigator.userAgent);

            // 클립보드 복사 시도
            if (isIOS || isSafari) {
                copyTextForiOS(text, showSuccess);
            } else if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(text).then(showSuccess).catch(function () {
                    copyTextFallback(text, showSuccess);
                });
            } else {
                copyTextFallback(text, showSuccess);
            }
        })
        .catch(function (error) {
            console.error('Copy failed:', error);
            showToast(t('copyFailed'), 'error');
        });
}

// iOS/Safari용 복사 함수
function copyTextForiOS(text, callback) {
    var input = document.createElement('input');
    input.setAttribute('readonly', 'readonly');
    input.setAttribute('contenteditable', 'true');
    input.style.position = 'fixed';
    input.style.top = '0';
    input.style.left = '0';
    input.style.padding = '0';
    input.style.border = 'none';
    input.style.outline = 'none';
    input.style.background = 'transparent';
    input.style.fontSize = '16px';
    input.value = text;
    document.body.appendChild(input);

    input.focus();
    input.select();

    var range = document.createRange();
    range.selectNodeContents(input);
    var selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    input.setSelectionRange(0, text.length);

    try {
        var success = document.execCommand('copy');
        if (success) {
            callback();
        } else {
            alert(t('copied') + ': ' + text);
        }
    } catch (err) {
        alert(t('copied') + ': ' + text);
    }

    document.body.removeChild(input);
}

// 일반 fallback 복사 함수
function copyTextFallback(text, callback) {
    var textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.left = '-9999px';
    textarea.style.top = '0';
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();

    try {
        document.execCommand('copy');
        callback();
    } catch (err) {
        alert(t('copied') + ': ' + text);
    }

    document.body.removeChild(textarea);
}

// 토스트 메시지
function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;

    document.body.appendChild(toast);

    // 애니메이션
    setTimeout(() => toast.classList.add('show'), 10);
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// 모바일 메뉴
document.addEventListener('DOMContentLoaded', () => {
    const mobileMenuBtn = document.querySelector('.mobile-menu-btn');
    const mobileMenu = document.querySelector('.mobile-menu');

    if (mobileMenuBtn && mobileMenu) {
        mobileMenuBtn.addEventListener('click', () => {
            const isOpen = mobileMenu.classList.toggle('show');
            mobileMenuBtn.classList.toggle('active');
            mobileMenuBtn.setAttribute('aria-expanded', isOpen);
        });
    }

    // 모바일 알림 버튼
    const notificationBtnMobile = document.getElementById('notificationBtnMobile');
    const notificationDropdownMobile = document.getElementById('notificationDropdownMobile');
    const markAllReadBtnMobile = document.getElementById('markAllReadBtnMobile');

    if (notificationBtnMobile) {
        notificationBtnMobile.addEventListener('click', (e) => {
            e.stopPropagation();
            notificationDropdownMobile?.classList.toggle('show');
            if (notificationDropdownMobile?.classList.contains('show')) {
                loadNotificationsMobile();
            }
        });
    }

    if (markAllReadBtnMobile) {
        markAllReadBtnMobile.addEventListener('click', (e) => {
            e.stopPropagation();
            markAllNotificationsRead();
            loadNotificationsMobile();
        });
    }

    const deleteAllBtnMobile = document.getElementById('deleteAllBtnMobile');
    if (deleteAllBtnMobile) {
        deleteAllBtnMobile.addEventListener('click', (e) => {
            e.stopPropagation();
            deleteAllNotifications();
            loadNotificationsMobile();
        });
    }

});

// 이미지 미리보기
function previewImages(input) {
    const preview = document.getElementById('image-preview');
    if (!preview) return;

    preview.innerHTML = '';

    const files = Array.from(input.files).slice(0, 5); // 최대 5장

    files.forEach((file, index) => {
        const reader = new FileReader();
        reader.onload = (e) => {
            const div = document.createElement('div');
            div.className = 'preview-image';
            div.innerHTML = `
                <img src="${e.target.result}" alt="Preview ${index + 1}">
                <button type="button" class="preview-remove" onclick="removePreviewImage(${index})">×</button>
            `;
            preview.appendChild(div);
        };
        reader.readAsDataURL(file);
    });
}

// 이미지 제거 (미리보기에서)
function removePreviewImage(index) {
    const input = document.getElementById('images');
    const preview = document.getElementById('image-preview');

    // DataTransfer를 사용해 파일 목록 수정
    const dt = new DataTransfer();
    const files = Array.from(input.files);

    files.forEach((file, i) => {
        if (i !== index) dt.items.add(file);
    });

    input.files = dt.files;

    // 미리보기 갱신
    previewImages(input);
}

// ============================================
// 알림 시스템
// ============================================

// 알림 드롭다운 토글
function toggleNotificationDropdown() {
    const dropdown = document.getElementById('notificationDropdown');
    const btn = document.getElementById('notificationBtn');
    if (dropdown) {
        const isOpen = dropdown.classList.toggle('show');
        if (btn) btn.setAttribute('aria-expanded', isOpen);
        if (isOpen) {
            loadNotifications();
        }
    }
}

// 알림 목록 로드
async function loadNotifications() {
    const list = document.getElementById('notificationList');
    if (!list) return;

    try {
        const response = await fetch('/interactions/notifications/');
        const data = await response.json();

        if (data.notifications && data.notifications.length > 0) {
            list.innerHTML = data.notifications.map(notif => {
                // 건의사항 알림은 내 건의사항 페이지로, 그 외에는 좌표 상세 페이지로
                const url = notif.type === 'SUGGESTION_REPLY'
                    ? '/accounts/my/suggestions/'
                    : `/coordinates/${notif.coordinate_id}/`;
                return `
                <a href="${url}"
                   class="notification-item ${notif.is_read ? '' : 'unread'}"
                   data-id="${notif.id}"
                   onclick="markNotificationRead(${notif.id})">
                    <div class="notification-message">${notif.message}</div>
                    <div class="notification-time">${notif.created_at}</div>
                </a>
            `;
            }).join('');
        } else {
            list.innerHTML = '<div class="notification-empty">' + t('noNotifications') + '</div>';
        }
    } catch (error) {
        console.error('Failed to load notifications:', error);
        list.innerHTML = '<div class="notification-empty">' + t('loadNotifFailed') + '</div>';
    }
}

// 모바일용 알림 목록 로드
async function loadNotificationsMobile() {
    const list = document.getElementById('notificationListMobile');
    if (!list) return;

    try {
        const response = await fetch('/interactions/notifications/');
        const data = await response.json();

        if (data.notifications && data.notifications.length > 0) {
            list.innerHTML = data.notifications.map(notif => {
                const url = notif.type === 'SUGGESTION_REPLY'
                    ? '/accounts/my/suggestions/'
                    : `/coordinates/${notif.coordinate_id}/`;
                return `
                <a href="${url}"
                   class="notification-item ${notif.is_read ? '' : 'unread'}"
                   data-id="${notif.id}"
                   onclick="markNotificationRead(${notif.id})">
                    <div class="notification-message">${notif.message}</div>
                    <div class="notification-time">${notif.created_at}</div>
                </a>
            `;
            }).join('');
        } else {
            list.innerHTML = '<div class="notification-empty">' + t('noNotifications') + '</div>';
        }
    } catch (error) {
        console.error('Failed to load mobile notifications:', error);
        list.innerHTML = '<div class="notification-empty">' + t('loadNotifFailed') + '</div>';
    }
}

// 읽지 않은 알림 개수 업데이트
async function updateUnreadCount() {
    const badge = document.getElementById('notificationBadge');
    if (!badge) return;

    try {
        const response = await fetch('/interactions/notifications/unread-count/');
        const data = await response.json();

        // 데스크톱 뱃지
        if (data.unread_count > 0) {
            badge.textContent = data.unread_count > 99 ? '99+' : data.unread_count;
            badge.style.display = 'flex';
        } else {
            badge.style.display = 'none';
        }

        // 모바일 뱃지
        const badgeMobile = document.getElementById('notificationBadgeMobile');
        if (badgeMobile) {
            if (data.unread_count > 0) {
                badgeMobile.textContent = data.unread_count > 99 ? '99+' : data.unread_count;
                badgeMobile.style.display = 'flex';
            } else {
                badgeMobile.style.display = 'none';
            }
        }
    } catch (error) {
        console.error('Failed to get unread count:', error);
    }
}

// 알림 읽음 처리
async function markNotificationRead(notificationId) {
    try {
        await fetchWithCSRF(`/interactions/notifications/${notificationId}/read/`, {
            method: 'POST'
        });
        updateUnreadCount();
    } catch (error) {
        console.error('Failed to mark notification as read:', error);
    }
}

// 모든 알림 읽음 처리
async function markAllNotificationsRead() {
    try {
        await fetchWithCSRF('/interactions/notifications/read-all/', {
            method: 'POST'
        });
        updateUnreadCount();
        loadNotifications();
    } catch (error) {
        console.error('Failed to mark all notifications as read:', error);
    }
}

// 모든 알림 삭제
async function deleteAllNotifications() {
    if (!confirm(t('deleteAllConfirm'))) return;

    try {
        await fetchWithCSRF('/interactions/notifications/delete-all/', {
            method: 'POST'
        });
        updateUnreadCount();
        loadNotifications();
    } catch (error) {
        console.error('Failed to delete all notifications:', error);
    }
}

// 알림 시스템 초기화
document.addEventListener('DOMContentLoaded', () => {
    const notificationBtn = document.getElementById('notificationBtn');
    const markAllReadBtn = document.getElementById('markAllReadBtn');

    if (notificationBtn) {
        notificationBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleNotificationDropdown();
        });

        // 초기 읽지 않은 알림 개수 로드
        updateUnreadCount();

        // 30초마다 새 알림 체크
        setInterval(updateUnreadCount, 30000);
    }

    if (markAllReadBtn) {
        markAllReadBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            markAllNotificationsRead();
        });
    }

    const deleteAllBtn = document.getElementById('deleteAllBtn');
    if (deleteAllBtn) {
        deleteAllBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            deleteAllNotifications();
        });
    }

    // 드롭다운 외부 클릭 시 닫기
    document.addEventListener('click', (e) => {
        const dropdown = document.getElementById('notificationDropdown');
        const wrapper = document.querySelector('.notification-wrapper');
        if (dropdown && wrapper && !wrapper.contains(e.target)) {
            dropdown.classList.remove('show');
        }
    });
});
