<!-- graph analysis_id=graph-2026-06-12-Wilson-fe7df818 dry_run=True -->
# Graph 管线附录 · Wilson

- **analysis_id**: `graph-2026-06-12-Wilson-fe7df818`
- **预算**: $0.06 / $5.00 （LLM 调用 15 次，degraded=False）

## Quality Gate
通过 3 只；缺口 0 项


## Portfolio Manager
<!-- stub role=portfolio_manager -->
**[portfolio_manager]** 占位输出（dry-run）。

- 输入约 1030 字符
- 请设置 `GRAPH_PIPELINE_ENABLED=1` 且提供 `CURSOR_API_KEY` 以启用 Cloud Agent。


## Hard Gate
```json
{
  "index": {
    "ok": true,
    "structure": "下跌趋势",
    "buy_point": "观望/空",
    "action": "wait",
    "score": -1.2,
    "protect_price": 4042.18,
    "ZD": 4042.18,
    "ZG": 4167.075,
    "buy_reason": "价格低于中枢下沿 ZD≈4042.18"
  },
  "index_blocks_new_buy": false,
  "stocks": {
    "600021": {
      "name": "上海电力",
      "buy_point": "观望/空",
      "protect_price": 17.275,
      "allows_new_buy": false,
      "reason": "指数缠论偏空（观望/空），标的无强买点",
      "can_open_verdict": true,
      "open_block_reason": null
    },
    "000010": {
      "name": "ST美丽",
      "buy_point": "二买候选",
      "protect_price": 2.198,
      "allows_new_buy": true,
      "reason": "二买候选",
      "can_open_verdict": true,
      "open_block_reason": null
    },
    "002730": {
      "name": "电光科技",
      "buy_point": "无明确买卖点",
      "protect_price": 27.733,
      "allows_new_buy": false,
      "reason": "指数缠论偏空（观望/空），标的无强买点",
      "can_open_verdict": true,
      "open_block_reason": null
    }
  },
  "note": "缠论 hard_gate 优先于 PM/LLM 结论"
}
```


---

（dry-run / 预算不足：未调用最终 sug Reporter；启用 `GRAPH_PIPELINE_ENABLED=1` 后由 Cloud Agent 生成完整 trade_template。）
