        import {workspace} from '../workspace.js';
        import {el} from '../dom.js';

        const page = {
  "title": "成品转运格互换",
  "module": "冰雕跨格互换单",
  "caption": "冰雕跨格互换单",
  "detail": "预留需原格融缝异常且目标格本格带载评分合格；补录带载记录会使旧评分失效并停办交接，重算通过后恢复，条件不再满足则退还目标位。",
  "path": "/cell_swaps",
  "columns": [
    {
      "name": "code",
      "label": "编号"
    },
    {
      "name": "seam",
      "label": "融缝复核"
    },
    {
      "name": "origin_score",
      "label": "原格评分"
    },
    {
      "name": "target",
      "label": "目标柜格"
    },
    {
      "name": "target_seam",
      "label": "目标格评分单"
    },
    {
      "name": "target_score",
      "label": "目标格评分"
    },
    {
      "name": "handover",
      "label": "现场双签"
    },
    {
      "name": "state",
      "label": "状态"
    },
    {
      "name": "hold",
      "label": "停办原因"
    }
  ],
  "layout": "flip",
  "view": "stack",
  "actions": [
    {
      "name": "reserve_swap",
      "label": "锁定替换柜格",
      "path": "/cell_swaps/reserve-swap",
      "fields": [
        {
          "name": "code",
          "label": "互换单号",
          "kind": "text",
          "initial": "SWP-24"
        },
        {
          "name": "seam",
          "label": "融缝单号",
          "kind": "text",
          "initial": "DENS-24"
        },
        {
          "name": "target",
          "label": "目标柜格",
          "kind": "text",
          "initial": "CELL-B"
        },
        {
          "name": "target_seam",
          "label": "目标格评分单",
          "kind": "text",
          "initial": "DENS-B1"
        },
        {
          "name": "handover",
          "label": "两位搬移人",
          "kind": "text",
          "initial": "江峰/罗岚"
        }
      ],
      "help": "目标柜格余位需先锁定，且目标格本格带载评分须合格。",
      "roles": [
        "reviewer"
      ],
      "success": "已写入"
    },
    {
      "name": "confirm_swap",
      "label": "收回换格凭条",
      "path": "/cell_swaps/confirm-swap",
      "fields": [
        {
          "name": "swap",
          "label": "互换单号",
          "kind": "text",
          "initial": "SWP-24"
        },
        {
          "name": "stamp",
          "label": "格签回执",
          "kind": "text",
          "initial": "CELL-B/2416"
        }
      ],
      "help": "交换到位后归还原柜格余位；停办中的单须等重算结算。",
      "roles": [
        "operator",
        "reviewer"
      ],
      "success": "已写入"
    }
  ]
};

        export const {title} = page;
        export const key = "cell_swaps";
        export async function render(root, role) {
          await workspace(root, role, page);

        }
