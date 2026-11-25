"""「없어졌다는 제보」 상태를 글에 붙인다.

목록 카드 오른쪽 위의 「?」가 이걸 보고 붙는다. 카드마다 제보를 세면
한 쪽에 30번을 묻게 되므로(N+1), 쪽에 실린 글 전부를 **한 번에** 센다.
`tests/test_gone.py` 가 쿼리 수를 지킨다.

붙는 값은 세 가지다.

    coord.gone_n     없어졌다는 표 (아직 운영자가 확인 안 한 것만)
    coord.alive_n    아직 있다는 반대표
    coord.gone_last  마지막으로 없어졌다는 말이 들어온 때

**운영자가 확인한 뒤에 들어온 제보만 센다.** 안 그러면 한 번 처리한 글에
「?」가 영영 붙어 있는다. 기준은 관리자 대기줄과 같다(`change_checked_at`).
"""
from .models import NerfReport


def attach_gone_state(coords):
    """글 목록(또는 하나)에 gone_n / alive_n / gone_last 를 달아준다. 쿼리 1개."""
    coords = [c for c in coords if c is not None]
    if not coords:
        return coords

    ids = [c.pk for c in coords]
    rows = NerfReport.objects.filter(
        coordinate_id__in=ids,
        change_kind__in=(NerfReport.ChangeKind.GONE, NerfReport.ChangeKind.ALIVE),
    ).values_list('coordinate_id', 'change_kind', 'created_at')

    bucket = {}
    for cid, kind, made in rows:
        bucket.setdefault(cid, []).append((kind, made))

    for c in coords:
        gone_n = alive_n = 0
        last = None
        checked = c.change_checked_at
        for kind, made in bucket.get(c.pk, ()):
            if checked is not None and made <= checked:
                continue                      # 운영자가 이미 보고 넘긴 제보다
            if kind == NerfReport.ChangeKind.GONE:
                gone_n += 1
                if last is None or made > last:
                    last = made
            else:
                alive_n += 1
        c.gone_n = gone_n
        c.alive_n = alive_n
        c.gone_last = last
    return coords
