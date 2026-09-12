# CS2 饰品 T+7 异动雷达 V0.2

今天按 BUFF 最低卖价买入，至少 7 天后按 BUFF 最高求购价退出，风险收益是否仍值得承担？这是项目唯一交易决策目标。

默认覆盖 SteamDT 全部 CS2 商品目录，包括枪皮、印花、胶囊、挂件、喷漆等。显示名称直接使用 SteamDT 的中文名称；缺少官方中文名时保留 marketHashName。BUFF.MARKET 与 BUFF163 严格区分。其他平台仅提供库存/资金行为的辅助证据。

## 当前可用功能

- 六状态重放：平静 → 吸筹 → 点火 → 主升 → 派发 → 崩盘；正常转移需要持续确认，派发/崩盘即时防御。
- 库存持续性：净减少 / 总绝对变动，结合采样覆盖、有效更新数、下降次数、单次下降占比；撤单不当成交量。
- 市场与同类残差：SteamDT 大盘、同类 BUFF 价格/库存，排除商品自身。基准为对数收益差，beta 固定为 1，尚未拟合。
- 安静收缩区报价带：BUFF 在售量持续下降、求购支撑、价格未加速的连续区段。这只是隐含吸筹报价区，不能证明实际庄家成本。
- 独立的集中资金评分、事件/基本面风险、市场状态，再由统一决策层决定是否有候选。社交热度只能加风险，未验证的“拉盘”说法不能产生高权重正标签。
- 严格单件 BUFF 顶价回测：T+7、14、30 净收益，解锁时收益，锁定期/解锁后回撤，解锁后最高可观察求购收益。最高收益只作诊断，不作成功标签。
- 时间切分、30 日标签成熟期、embargo、walk-forward、同期匹配对照、缺失/右删失覆盖率。
- SQLite 增量迁移、元数据版本、时间边界、采集来源时间去重、只读 API 接入、离线评分与回测。

当前仍是启发式研究模型和经验分位数统计，不是已证明有效的交易策略。真实历史 BUFF 求购数据尚未积累，当前不提供校准概率或历史盈利承诺。

## 快速运行

Python 3.10+，仅标准库，无需安装第三方依赖。从本目录运行：

```text
python -m unittest discover -s tests -v
python src/radar.py status
python src/radar.py score --top 20
```

联网采集前，在运行进程的环境变量中配置 `STEAMDT_API_KEY`。不要写入源码或报告。`.env.example` 仅作环境变量模板；程序不会自动加载 `.env`。

```text
python src/radar.py refresh-universe
python src/radar.py collect-once
python src/radar.py collect-market
python src/radar.py collect-hot
python src/radar.py run
```

`run` 是前台持续采集，Ctrl+C 停止；本次开发没有安装常驻服务或自动任务。全目录批量轮询每 61 秒最多 100 项；基础目录每日最多请求一次。热点单查询至多每秒一次，一轮最多 30 项，并给新发现预留名额。44,387 项粗扫一轮约 7.52 小时，粗扫覆盖不足的商品不能直接通过细采门槛。目录刷新不会删除历史商品或重启已手动禁用的商品。

`score`、`status`、`backtest`、`import-data` 均可离线运行。`--db` 和 `--config` 是子命令之前的全局参数。

## 交易输出

顶层 `decision` 在没有候选时明确输出“今天没有值得买的”，同时注明采样范围与数据不足原因，不能把未覆盖全市场表述为完整市场判断。

每个商品包括官方名称、BUFF 实际卖价/求购价与更新时间、阶段、三项评分、持续性、市场/同类残差、报价带、原因和拒绝门槛。只有通过数据、新鲜度、价差、流动性、早期阶段和历史 T+7 样本要求，才可输出 `BUY_CANDIDATE`。

没有 BUFF、没有完整历史、缺少市场/同类基准、缺少合格历史经验分布或费率未配置时，`buy_price_max` 和推荐价格不会由其他平台补造。价格上限由以下三者取最小值，并向下取到分：

1. 历史同阶段/市场状态的 T+7 求购价中位数，扣费滑点后满足目标收益的最高买价。
2. 下侧 10% 经验求购价分位数，满足最大可接受亏损的最高买价。
3. 安静收缩报价带上沿加允许的溢价。

`no_chase_above` 使用同一风险上限。分位数来自过去已经成熟的标签，按事件组限权，要求足够独立样本及亏损样本；它不是成交保证或校准概率。流动性数据没有顶档深度，本版仅支持单件报价模拟。

## 回测与费率

正式配置 `fee_rate` 默认为 null。请按你的 BUFF 实际费率配置。以下 `0.025` 仅演示 **2.5% 费率情景**，不代表已核实你的当前费率；默认另加 0.5% 卖出滑点。

```text
python src/radar.py --fee 0.025 backtest --start 2025-09-12T00:00:00Z --end 2026-09-12T00:00:00Z --as-of 2026-09-12T12:00:00Z --output reports/walk_forward.json --calibration-output reports/calibration.json
python src/radar.py --fee 0.025 score --calibration reports/calibration.json --output reports/decisions.json
python src/radar.py --fee 0.025 run --calibration reports/calibration.json
```

所有时间使用 UTC 秒或带时区 ISO 格式。T0 只使用当时可获得且足够新鲜的 BUFF 最低卖价；解锁后在默认 6 小时容忍窗内取首个有效、新更新的最高求购价，记录实际延迟，不挑选最高价。没有报价则记缺失；时间还未到则记右删失。函数支持晚于 7 天的实际解锁时间，T+7 仍未解锁时返回 LOCKED。

默认训练窗 180 天，测试窗 30 天，测试前留 1 天 embargo。只有 T+30 加退出容忍窗已结束的标签能进入训练。测试期配置冻结；训练不从未来峰值或社区声称的成功案例取标签。全样本、亏损样本、同期匹配对照、不可执行入场、退出缺失都保留。缺少足够历史时返回 INSUFFICIENT_HISTORY，不输出伪造胜率。

重新修改参数后，旧校准文件因配置指纹不同失效。报告中的经验分位数和回撤要结合覆盖率阅读；稀疏报价可能低估盘中风险。没有逐笔成交、委托深度或资金规模模拟，所以结果不是可以叠加的组合收益。

## 导入已有历史

`python src/radar.py import-data PATH.json` 接受以下结构；数字仅为格式示例：

```json
{
  "batches": [{
    "sampled_at": 1780000000,
    "data": [{
      "marketHashName": "Sticker | Mastermind (Holo)",
      "dataList": [{
        "platform": "BUFF", "sellPrice": 10, "sellCount": 100,
        "biddingPrice": 9.5, "biddingCount": 30, "updateTime": 1779999900
      }]
    }]
  }],
  "market": [{"observed_at": 1780000000, "available_at": 1780000010, "value": 800}],
  "items": [{"available_at": 1780000010, "data": [{
    "marketHashName": "Sticker | Mastermind (Holo)",
    "name": "印花 | 幕后主谋（全息）", "category": "sticker"
  }]}],
  "evidence": []
}
```

`sampled_at` 必须是可审计的原始接收时间，不能用今日回溯抓取的时间伪装过去可用。元数据可选 `collection`、`supply`、`liquidity`，不可用今天信息回填过去。论文/帖子证据使用 `id, url, published_at, available_at, kind`，可带 `verified, independence_group, metrics`；未核实默认没有高权重训练标签。导入同一文件不会为价格特征增加来源更新次数，但原始快照可能保留重复采样记录用于审计。

`archive-kline` 只保存研究用原始响应，绝不把 K 线高价当成历史最高求购价：

```text
python src/radar.py archive-kline
python src/radar.py archive-kline --name "Sticker | Mastermind (Holo)"
```

## 研究与验收

- [架构审查、已修复问题、真实数据边界](research/architecture_audit_v2.md)
- [历史案例、失败入场线索与事件反例](research/historical_cases_v2.md)
- [SteamDT 接口文档](https://doc.steamdt.com/)
- [Steam 官方交易保护规则](https://help.steampowered.com/en/faqs/view/365F-4BEE-2AE2-7BDD)

默认 Git 忽略数据库、凭证文件、生成报告和本地数据。使用 `scripts/live_check.py` 可运行有限次数的联网检查；`scripts/report_readiness.py --fee 0.025` 输出明确标注费率情景的真实数据就绪报告。测试中的合成样本只验证实现，不代表真实市场回测结果。
