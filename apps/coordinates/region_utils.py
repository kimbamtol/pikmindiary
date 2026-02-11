"""Region detection utilities using Nominatim API"""
import requests
import logging
import threading
from functools import lru_cache

logger = logging.getLogger(__name__)

# 국가 코드 → 지역 매핑
COUNTRY_TO_REGION = {
    # 한국
    'kr': 'KOREA',
    
    # 일본
    'jp': 'JAPAN',
    
    # 북미
    'us': 'NORTH_AMERICA',
    'ca': 'NORTH_AMERICA',
    'mx': 'NORTH_AMERICA',
    
    # 유럽
    'de': 'EUROPE', 'fr': 'EUROPE', 'gb': 'EUROPE', 'it': 'EUROPE',
    'es': 'EUROPE', 'pt': 'EUROPE', 'nl': 'EUROPE', 'be': 'EUROPE',
    'ch': 'EUROPE', 'at': 'EUROPE', 'pl': 'EUROPE', 'cz': 'EUROPE',
    'se': 'EUROPE', 'no': 'EUROPE', 'dk': 'EUROPE', 'fi': 'EUROPE',
    'ie': 'EUROPE', 'gr': 'EUROPE', 'hu': 'EUROPE', 'ro': 'EUROPE',
    'bg': 'EUROPE', 'hr': 'EUROPE', 'sk': 'EUROPE', 'si': 'EUROPE',
    'ee': 'EUROPE', 'lv': 'EUROPE', 'lt': 'EUROPE', 'lu': 'EUROPE',
    'mt': 'EUROPE', 'cy': 'EUROPE', 'is': 'EUROPE', 'ua': 'EUROPE',
    'ru': 'EUROPE',  # 러시아는 유럽으로 분류
    
    # 아시아 기타
    'cn': 'ASIA_OTHER', 'tw': 'ASIA_OTHER', 'hk': 'ASIA_OTHER',
    'sg': 'ASIA_OTHER', 'my': 'ASIA_OTHER', 'th': 'ASIA_OTHER',
    'vn': 'ASIA_OTHER', 'ph': 'ASIA_OTHER', 'id': 'ASIA_OTHER',
    'in': 'ASIA_OTHER', 'pk': 'ASIA_OTHER', 'bd': 'ASIA_OTHER',
    'np': 'ASIA_OTHER', 'lk': 'ASIA_OTHER', 'mm': 'ASIA_OTHER',
    'kh': 'ASIA_OTHER', 'la': 'ASIA_OTHER', 'bn': 'ASIA_OTHER',
    'mn': 'ASIA_OTHER', 'kz': 'ASIA_OTHER', 'uz': 'ASIA_OTHER',
    'ae': 'ASIA_OTHER', 'sa': 'ASIA_OTHER', 'il': 'ASIA_OTHER',
    'tr': 'ASIA_OTHER',  # 터키는 아시아로 분류
}

# Nominatim API 설정
NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "PikminDiary/1.0 (pikmindiary.com)"
REQUEST_TIMEOUT = 10


def detect_region_from_nominatim(latitude, longitude):
    """
    Nominatim API를 사용해 좌표에서 지역(Region) 감지
    
    Returns:
        str: Region 값 (KOREA, JAPAN, etc.) 또는 None (실패 시)
    """
    try:
        params = {
            'format': 'json',
            'lat': str(latitude),
            'lon': str(longitude),
            'zoom': 3,  # country level
            'addressdetails': 1,
        }
        
        headers = {
            'User-Agent': USER_AGENT,
        }
        
        response = requests.get(
            NOMINATIM_URL,
            params=params,
            headers=headers,
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        
        data = response.json()
        
        # address에서 country_code 추출
        address = data.get('address', {})
        country_code = address.get('country_code', '').lower()
        
        if country_code:
            region = COUNTRY_TO_REGION.get(country_code, 'OTHER')
            logger.info(f"Nominatim: ({latitude}, {longitude}) → {country_code} → {region}")
            return region
        
        logger.warning(f"Nominatim: No country_code for ({latitude}, {longitude})")
        return None
        
    except requests.exceptions.Timeout:
        logger.warning(f"Nominatim timeout for ({latitude}, {longitude})")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Nominatim error for ({latitude}, {longitude}): {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in detect_region_from_nominatim: {e}")
        return None


def update_coordinate_region_async(coordinate_id):
    """
    백그라운드 스레드에서 좌표의 지역 업데이트
    """
    def _update():
        try:
            # 지연 import로 순환 참조 방지
            from .models import Coordinate
            
            coord = Coordinate.objects.get(pk=coordinate_id)
            region = detect_region_from_nominatim(coord.latitude, coord.longitude)
            
            if region and region != coord.region:
                coord.region = region
                coord.save(update_fields=['region'])
                logger.info(f"Updated Coordinate {coordinate_id} region to {region}")
                
        except Exception as e:
            logger.error(f"Failed to update region for Coordinate {coordinate_id}: {e}")
    
    # 백그라운드 스레드로 실행 (2초 딜레이로 Nominatim rate limit 준수)
    thread = threading.Timer(2.0, _update)
    thread.daemon = True
    thread.start()
