# CS2 T+7 Radar

面向 Steam/CS2 **7 天交易保护**约束的饰品异动雷达。目标不是追已经暴涨的品，而是持续记录低位盘口，发现“库存收缩 + 求购增加 + 跨平台同步 + 价格尚未失控”的早期建仓结构。

## 为什么是 T+7

CS2 物品通过交易获得后会进入 7 天交易保护。这个项目因此把“买入后至少 7 天无法自由退出”视为硬约束：评分会对已经大涨、流动性极差、单平台孤立异动的品种施加追高/锁仓风险惩罚。

## SteamDT 数据

使用：
- `/open/cs2/v1/base`：全量 marketHashName，日更缓存。
- `/open/cs2/v1/price/batch`：一次最多 100 个，用于全市场轮询。
- `/open/cs2/v1/price/single`：后续用于高分候选的分钟级盯盘。
- `/open/cs2/item/v1/kline`：历史价格辅助；官方 K 线不含成交量。

本项目自己把每次 `sellPrice/sellCount/biddingPrice/biddingCount` 快照写入 SQLite，从而生成 SteamDT 没直接提供的库存变化、求购变化、跨平台一致性等时序特征。注意：库存减少不等于真实成交量，撤单也会造成库存下降，所以必须结合求购、价格和多个平台交叉确认。

## 当前 V0.1 评分

`T7 Score 0-100` 由以下部分组成：24h 在售库存收缩、24h 求购数量增长、跨平台确认、买卖价差、流动性代理、低位价格稳定性、早期动量；同时对 24h/7d 已明显暴涨和极低流动性品种施加惩罚。

阶段：`ACCUMULATION`（吸筹候选）、`EARLY_MARKUP`（早期拉升）、`WATCH`、`CHASE_RISK`（T+7 不宜追）。这不是“5 倍概率”；要把它训练成概率，需要先持续采样，再用未来第 7/14/30 天收益做标签回测。

## 快速开始

```bash
cd cs2-t7-radar
cp .env.example .env
# 把 key 写到环境变量，不要提交真实 key
export STEAMDT_API_KEY='...'
python src/radar.py refresh-universe
python src/radar.py collect-once
python src/radar.py score --top 20
python src/radar.py run
```

默认先扫描 Sticker / Graffiti。批量接口的官方频率限制是每分钟 1 次、每批最多 100 个，因此程序每 61 秒轮换一批；T+7 策略不需要每个品都秒级采样。下一阶段会加入高分候选的 `price/single` 高频通道。

## 安全

不要把真实 `STEAMDT_API_KEY` 写进源码、网页前端或公共 GitHub。推荐在本机/服务器使用环境变量或 `.env`（并确保 `.gitignore` 忽略）。如果 Key 曾经公开发送或提交，正式部署前应重新生成。