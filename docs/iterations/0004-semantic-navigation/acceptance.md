# ITER-0004 Acceptance

> 状态：Draft  
> 更新日期：2026-07-04

## 必选验收

- [ ] UI Node、Selector 和 Match Result 具有版本化 Contract。
- [ ] XML 解析不执行外部实体，并对节点数、深度和文本长度设限。
- [ ] 支持 resource ID、text、content description、clickable 和祖先路径匹配。
- [ ] exact 与 contains 语义明确，默认区分大小写。
- [ ] 不存在返回 `TARGET_NOT_FOUND`，多个结果返回 `TARGET_AMBIGUOUS`。
- [ ] 不可点击目标不会被静默转换为坐标点击。
- [ ] bounds 必须有效、位于屏幕内，点击点位于目标 bounds 内。
- [ ] `input.tap_element` 固定为 Medium 风险且需要确认。
- [ ] Tool 使用最新 Observation 的 UI tree，不接受调用方伪造 bounds。
- [ ] 等待具有超时和轮询上限，不形成无限循环。
- [ ] 导航 Skill 通过目标 UI 证据验证成功。
- [ ] 默认测试集不依赖真实设备。
- [ ] 质量门禁和全部自动化测试通过。

## 真机安全验收

- [ ] 从系统设置主页按语义进入一个设置子页面。
- [ ] 目标元素唯一、可点击且 bounds 有效。
- [ ] 页面标题或目标 UI 证据验证成功。
- [ ] 未修改任何设置，未执行文本输入或裸坐标真机调用。

## 验证记录

迭代完成后填写。
