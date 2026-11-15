#!/usr/bin/env python3
"""static/maintenance.html -> cf-worker-maintenance.js 재생성

안내 페이지를 고친 뒤 이 스크립트를 돌리면 워커 파일이 갱신된다.
    python3 deploy/cloudflare/build-worker.py
그 다음 Cloudflare 대시보드에서 워커 코드를 다시 붙여넣어야 반영된다.
"""
import io
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(ROOT, 'static', 'maintenance.html')
OUT = os.path.join(HERE, 'cf-worker-maintenance.js')

TEMPLATE = '''// 피크민 다이어리 - 서버가 꺼졌을 때 보여줄 안내 화면
// Cloudflare Workers (무료 플랜 가능)
// 라우트: pikmindiary.com/*, www.pikmindiary.com/*
// 원본: /home/tori/pikmin-diary/static/maintenance.html (build-worker.py로 생성)

const DOWN_STATUS = [502, 504, 520, 521, 522, 523, 524, 525, 526];

const MAINTENANCE_HTML = `__HTML__`;

function maintenance() {
  return new Response(MAINTENANCE_HTML, {
    status: 503,
    headers: {
      'content-type': 'text/html; charset=UTF-8',
      'cache-control': 'no-store',
      'retry-after': '120',
    },
  });
}

export default {
  async fetch(request) {
    try {
      const response = await fetch(request);
      if (DOWN_STATUS.includes(response.status)) return maintenance();
      return response;
    } catch (err) {
      // 원본 서버에 아예 닿지 않는 경우
      return maintenance();
    }
  },
};
'''


def compact(html):
    """줄바꿈은 남기고 들여쓰기와 주석만 걷어낸다 (JS 안전)."""
    html = re.sub(r'<!--.*?-->', '', html, flags=re.S)
    lines = [line.strip() for line in html.split('\n')]
    return '\n'.join(line for line in lines if line)


def main():
    html = compact(io.open(SRC, encoding='utf-8').read())
    if '`' in html or '${' in html:
        raise SystemExit('HTML에 백틱이나 ${ 가 있어 템플릿 리터럴이 깨집니다')
    io.open(OUT, 'w', encoding='utf-8').write(TEMPLATE.replace('__HTML__', html))
    print('%s (%d bytes)' % (OUT, os.path.getsize(OUT)))


if __name__ == '__main__':
    main()
