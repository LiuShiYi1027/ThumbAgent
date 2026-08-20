# ITER-0056 Acceptance

> 文档状态：Completed
> 迭代状态：Completed
> 更新日期：2026-08-20

## 验收条件

1. 全部既有 class 覆盖，组件 TSX 零改动。
2. 视觉符合方向稿 3c：奶油纸底、墨框卡片带硬阴影、黑底主按钮按压位移、印章徽章、
   方形时间线节点、语义色可区分（成功/警告/错误/占用一眼可分）。
3. 可访问性不回退：focus-visible 焦点环、prefers-reduced-motion、aria-label 等
   ITER-0055 hotfix 成果保留。
4. `make check-desktop` 通过；截图目检无裸元素、无布局破碎、正文对比度合格。

## 验收记录

验收日期：2026-08-20。

1. ✅ 组件 TSX 零改动；ITER-0055 的全部 class 在新主题中保留。
2. ✅ Chrome headless 截图目检（`/tmp/thumb-mono-main.png`）：奶油纸底、墨框硬阴影卡片、
   黑底按压按钮、旋转印章徽章、方形时间线节点（失败红方块）、logo 圆章红点均呈现；
   语义色绿/黄/红/紫在 mono 语言下仍可一眼区分。
3. ✅ 可访问性无回退：focus-visible 环、prefers-reduced-motion、aria-label、
   touch-action 均保留在新样式中。
4. ✅ `make check-desktop` 通过：oxlint 0 警告、tsc、cargo fmt/clippy、21 Rust 测试。
