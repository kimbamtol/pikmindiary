/**
 * 날씨/계절 테마 관리
 */
class WeatherTheme {
    constructor() {
        // 서버 기본 위치 (한국 서울)
        this.serverLocation = { lat: 37.5665, lng: 126.9780 };
    }

    /**
     * 랜딩 페이지용: 서버 위치 기준 테마 적용
     */
    async initLanding() {
        const weather = await this.fetchWeather(
            this.serverLocation.lat,
            this.serverLocation.lng
        );
        if (weather) {
            this.applyTheme(weather);
        } else {
            // API 실패 시 기본값 적용
            this.applyDefaultTheme();
        }
    }

    /**
     * 입장 버튼 클릭 시: 위치 권한 요청 후 이동
     */
    async handleEnterClick() {
        try {
            const position = await this.requestLocation();
            // 위치 허용됨 - localStorage에 저장
            localStorage.setItem('userLocation', JSON.stringify({
                lat: position.lat,
                lng: position.lng,
                granted: true
            }));
        } catch (error) {
            // 위치 거부됨
            localStorage.setItem('userLocation', JSON.stringify({
                lat: this.serverLocation.lat,
                lng: this.serverLocation.lng,
                granted: false
            }));
        }
        // 좌표 목록 페이지로 이동
        window.location.href = '/coordinates/';
    }

    /**
     * 메인 페이지용: 저장된 위치 기준 테마 적용
     */
    async initMain() {
        const stored = localStorage.getItem('userLocation');
        let location = this.serverLocation;

        if (stored) {
            try {
                const parsed = JSON.parse(stored);
                location = { lat: parsed.lat, lng: parsed.lng };
            } catch (e) {
                console.error('Failed to parse stored location:', e);
            }
        }

        const weather = await this.fetchWeather(location.lat, location.lng);
        if (weather) {
            this.applyTheme(weather);
        } else {
            this.applyDefaultTheme();
        }
    }

    /**
     * 위치 권한 요청
     */
    requestLocation() {
        return new Promise((resolve, reject) => {
            if (!navigator.geolocation) {
                reject(new Error('Geolocation not supported'));
                return;
            }

            navigator.geolocation.getCurrentPosition(
                (pos) => resolve({
                    lat: pos.coords.latitude,
                    lng: pos.coords.longitude
                }),
                (err) => reject(err),
                { timeout: 10000, enableHighAccuracy: false }
            );
        });
    }

    /**
     * Open-Meteo API로 날씨 조회
     */
    async fetchWeather(lat, lng) {
        try {
            const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lng}&current_weather=true`;
            const res = await fetch(url);
            if (!res.ok) throw new Error('Weather API failed');
            return await res.json();
        } catch (error) {
            console.error('Weather fetch error:', error);
            return null;
        }
    }

    /**
     * 테마 적용
     */
    applyTheme(weather) {
        const latitude = weather.latitude || this.serverLocation.lat;
        const season = this.getSeason(latitude);
        const weatherEffect = this.getWeatherEffect(weather.current_weather?.weathercode || 0);

        document.body.dataset.season = season;
        document.body.dataset.weather = weatherEffect;

        console.log(`Theme applied: season=${season}, weather=${weatherEffect}`);
    }

    /**
     * 기본 테마 적용 (API 실패 시)
     */
    applyDefaultTheme() {
        const season = this.getSeason(this.serverLocation.lat);
        document.body.dataset.season = season;
        document.body.dataset.weather = 'clear';
    }

    /**
     * 위도와 월로 계절 판단
     */
    getSeason(latitude) {
        const month = new Date().getMonth() + 1; // 1-12
        const isNorthern = latitude >= 0;

        if ([3, 4, 5].includes(month)) {
            return isNorthern ? 'spring' : 'fall';
        }
        if ([6, 7, 8].includes(month)) {
            return isNorthern ? 'summer' : 'winter';
        }
        if ([9, 10, 11].includes(month)) {
            return isNorthern ? 'fall' : 'spring';
        }
        // 12, 1, 2
        return isNorthern ? 'winter' : 'summer';
    }

    /**
     * WMO 날씨 코드로 효과 판단
     * https://open-meteo.com/en/docs
     */
    getWeatherEffect(code) {
        // 51-67: 이슬비, 비
        if (code >= 51 && code <= 67) return 'rain';
        // 71-77: 눈
        if (code >= 71 && code <= 77) return 'snow';
        // 80-82: 소나기
        if (code >= 80 && code <= 82) return 'rain';
        // 85-86: 눈 소나기
        if (code >= 85 && code <= 86) return 'snow';
        // 95-99: 뇌우
        if (code >= 95 && code <= 99) return 'rain';

        return 'clear';
    }
}

// 글로벌 인스턴스
const weatherTheme = new WeatherTheme();

// 페이지 로드 시 자동 초기화
document.addEventListener('DOMContentLoaded', () => {
    // 랜딩 페이지인지 확인
    const isLanding = document.body.classList.contains('landing-page');

    if (isLanding) {
        weatherTheme.initLanding();
    } else {
        weatherTheme.initMain();
    }
});
