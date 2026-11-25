from sqlalchemy import select

from core.queueing import submit, result
from core.records import get, insert, need, scan, update
from domain.cold_cells_model import cold_cells
from domain.thaw_samples_model import thaw_samples
from domain.seam_maps_model import seam_maps
from domain.cell_swaps_model import cell_swaps
from domain.cell_swaps_service import expire_scores, lock_cells, settle_swaps, swap_cells


def score_seam(conn, user, data):
    source = get(conn, thaw_samples, data.sample)
    need(not source['empty_test'], '空载测试不评估冰雕融缝')
    pool = [r for r in scan(conn, thaw_samples) if r['cell'] == source['cell'] and
            not r['empty_test'] and r['code'] != data.sample]
    need(len(pool) >= 20, '此柜格带载基线不足二十条')
    return submit(user, {'source': source, 'pool': pool})


def record_seam(conn, user, data):
    run = result(user, data.token); metrics = run['result']
    source = run['input']['source']
    # 先收齐涉及柜格再按序加锁：与补录、预留、回执并发时由先办成者生效。
    involved = {source['cell']}
    for order in scan(conn, cell_swaps):
        if order['state'] == '已预留' and source['cell'] in swap_cells(conn, order):
            involved.update(swap_cells(conn, order))
    lock_cells(conn, involved)
    output = insert(conn, seam_maps, code=data.code, sample=source['code'],
                    density=metrics['density'], threshold=metrics['threshold'], token=data.token,
                    valid=True,
                    decision='建议换格' if metrics['density'] < metrics['threshold'] else '同档可留')
    # 同一样本的旧评分让位，波及单停办后立刻按新评分结算：通过则恢复交接，否则退还目标位。
    stale = [r['code'] for r in scan(conn, seam_maps)
             if r['sample'] == source['code'] and r['valid'] and r['code'] != data.code]
    expire_scores(conn, stale, '评分重算让位，待双格评分齐备')
    settle_swaps(conn, source['cell'])
    return output
