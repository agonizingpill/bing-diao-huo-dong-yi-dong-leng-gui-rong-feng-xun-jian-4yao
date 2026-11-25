from sqlalchemy import select

from core.queueing import submit, result
from core.records import get, insert, need, scan, update
from domain.cold_cells_model import cold_cells
from domain.thaw_samples_model import thaw_samples
from domain.seam_maps_model import seam_maps
from domain.cell_swaps_model import cell_swaps

# 行锁顺序约定：先按编号升序锁 cold_cells，再读写 seam_maps，最后动 cell_swaps，
# 保证补录、回执、重算并发时由先办成的事务生效，且不会互相等待成死锁。

def lock_cells(conn, codes):
    return {code: get(conn, cold_cells, code, lock=True) for code in sorted(set(codes))}


def swap_cells(conn, order):
    seam = get(conn, seam_maps, order['seam'])
    origin = get(conn, thaw_samples, seam['sample'])['cell']
    return origin, order['target']


def suspend_swaps(conn, seam_codes, reason):
    # 评分失效波及已预留单：停办但保留已锁余位，等重算后结算。已交换单不受影响。
    for order in scan(conn, cell_swaps):
        if order['state'] == '已预留' and (order['seam'] in seam_codes or order['target_seam'] in seam_codes):
            conn.execute(cell_swaps.update().where(cell_swaps.c.code == order['code'])
                         .where(cell_swaps.c.state == '已预留').values(hold=reason))


def expire_scores(conn, seam_codes, reason):
    if not seam_codes:
        return
    conn.execute(seam_maps.update().where(seam_maps.c.code.in_(seam_codes)).values(valid=False))
    suspend_swaps(conn, set(seam_codes), reason)


def cell_score_codes(conn, cell):
    rows = conn.execute(select(seam_maps.c.code).join(thaw_samples, seam_maps.c.sample == thaw_samples.c.code)
                        .where(thaw_samples.c.cell == cell).where(seam_maps.c.valid == True)).scalars()
    return list(rows)


def fresh_score(conn, sample):
    rows = [r for r in scan(conn, seam_maps) if r['sample'] == sample and r['valid']]
    return rows[0] if rows else None


def settle_swaps(conn, cell):
    # 重算入账后结算涉及该格的停办单：双格评分齐备才定夺，齐备前继续停办。
    for order in scan(conn, cell_swaps):
        if order['state'] != '已预留' or not order['hold']:
            continue
        origin, target = swap_cells(conn, order)
        if cell not in (origin, target):
            continue
        origin_score = fresh_score(conn, get(conn, seam_maps, order['seam'])['sample'])
        target_score = fresh_score(conn, get(conn, seam_maps, order['target_seam'])['sample']) \
            if order['target_seam'] else None
        if origin_score is None or target_score is None:
            continue
        if origin_score['decision'] == '建议换格' and target_score['decision'] == '同档可留':
            update(conn, cell_swaps, order['code'], seam=origin_score['code'],
                   target_seam=target_score['code'], hold=None)
        else:
            # 仅已预留单会走到这里，退位后状态翻转，重试不会重复退位。
            conn.execute(cold_cells.update().where(cold_cells.c.code == target)
                         .values(free_slots=cold_cells.c.free_slots + 1))
            update(conn, cell_swaps, order['code'], state='已退位',
                   hold='重算后换格条件不再满足，已退还目标位')


def reserve_swap(conn, user, data):
    assessment = get(conn, seam_maps, data.seam)
    row = get(conn, thaw_samples, assessment['sample'])
    need(row['cell'] != data.target, '没有异格换位依据')
    target_assessment = get(conn, seam_maps, data.target_seam)
    target_row = get(conn, thaw_samples, target_assessment['sample'])
    need(target_row['cell'] == data.target, '目标柜格评分须来自本格带载历史')
    cells = lock_cells(conn, (row['cell'], data.target))
    original, destination = cells[row['cell']], cells[data.target]
    assessment = get(conn, seam_maps, data.seam)
    target_assessment = get(conn, seam_maps, data.target_seam)
    need(assessment['valid'], '原柜格评分已失效，待重算')
    need(assessment['decision'] == '建议换格', '原柜格融缝未见异常')
    need(target_assessment['valid'], '目标柜格评分已失效，待重算')
    need(target_assessment['decision'] == '同档可留', '目标柜格带载评分不合格')
    need(original['duty'] == destination['duty'], '旧模脱模区不得占用成品转运格')
    agents = [p.strip() for p in data.handover.split('/')]
    need(len(agents) == 2 and all(agents) and len(set(agents)) == 2, '需要两名不同搬移人签认')
    need(destination['authorized'] and not destination['closed'] and destination['free_slots'] > 0, '目标柜格不可用')
    output = insert(conn, cell_swaps, **data.model_dump(), state='已预留', hold=None)
    update(conn, cold_cells, data.target, free_slots=destination['free_slots'] - 1)
    return output


def confirm_swap(conn, user, data):
    order = get(conn, cell_swaps, data.swap)
    origin, target = swap_cells(conn, order)
    lock = lock_cells(conn, (origin, target))
    order = get(conn, cell_swaps, data.swap, lock=True)
    need(order['state'] == '已预留' and data.stamp.startswith(order['target'] + '/'), '状态或格签不匹配')
    need(not order['hold'], '换格单停办中：' + (order['hold'] or ''))
    need(not lock[order['target']]['closed'], '目标柜格已经暂停，须复核')
    update(conn, cold_cells, origin, free_slots=lock[origin]['free_slots'] + 1)
    return update(conn, cell_swaps, data.swap, state='已交换 ' + data.stamp)


def score_label(score):
    label = f"{score['density']} / {score['threshold']} · {score['decision']}"
    return label if score['valid'] else label + '（已失效）'


def list_swaps(conn):
    rows = scan(conn, cell_swaps)
    for order in rows:
        order['origin_score'] = score_label(get(conn, seam_maps, order['seam']))
        order['target_score'] = score_label(get(conn, seam_maps, order['target_seam'])) \
            if order['target_seam'] else None
    return rows
