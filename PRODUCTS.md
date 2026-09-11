# Life K-Line Final · Three Product Masters

从本版本开始，人生 K 线正式拆分为三个相互独立的产品母版。以后不要再从旧 `lifekline` 或旧 `2002-12-12/` 页面直接开始。

## 1. Mobile HTML
路径：`products/mobile-html/`

手机优先的单文件离线 HTML。核心是触摸手势、捏合缩放、横屏 K 线工作台。

## 2. Desktop HTML
路径：`products/desktop-html/`

电脑优先的单文件离线 HTML。核心是宽屏、高信息密度、鼠标拖动与滚轮缩放。

## 3. PDF
路径：`products/pdf/`

正式档案交付版本，可直接发送、保存和打印。

## 共同原则

- 三个版本共享同一命盘与年度数据口径，但 UI / 交互 / 排版分别维护。
- HTML 最终产物必须是单文件、自包含、无 CDN、无网络请求。
- HTML 的运行不依赖 GitHub，因此中国大陆网络、VPN 与否不影响本地打开。
- GitHub 只保存母版源码和版本历史，不再承担客户页面运行时托管。
- 用户没有明确要求时不调用 AskLingxi；真太阳时默认自行计算。
