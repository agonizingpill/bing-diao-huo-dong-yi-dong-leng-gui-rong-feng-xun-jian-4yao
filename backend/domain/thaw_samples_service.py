from sqlalchemy import select

from core.queueing import submit, result
from core.records import get, insert, need, scan, update
from domain.cold_cells_model import cold_cells
from domain.thaw_samples_model import thaw_samples
from domain.seam_maps_model import seam_maps
from domain.cell_swaps_model import cell_swaps
from domain.cell_swaps_service import cell_score_codes, expire_scores, lock_cells


def observe_seam(conn, user, data):
    cell = get(conn, cold_cells, data.cell, lock=True)
    need(cell['authorized'] and not cell['closed'], '柜格当前不开放测量')
    need(0 <= data.mass_kg <= 350 and 0 <= data.melt <= 30 and -30 <= data.drift <= 30, '柜格观测值越界')
    need((data.mass_kg == 0) == data.empty_test, '空载凭单要求零质量')
    output = insert(conn, thaw_samples, **data.model_dump())
    if not data.empty_test:
        # 晚到的带载记录入账：本格旧评分失效，涉及的已预留换格单停办，已占余位留给原单。
        expire_scores(conn, cell_score_codes(conn, data.cell),
                      f'补录带载记录 {data.code}，涉及评分失效，待重算')
    return output
