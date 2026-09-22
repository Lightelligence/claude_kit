---
paths:
  - "hw/rtl/**"
---

# RTL 变更门控

## 材料变更 (进入模块 pipeline)

材料变更包括:
- 可综合 RTL
- RTL/filelist 组合
- 接口
- 时钟/复位
- 寄存器可见行为
- 综合约束
- 生成的 top/wrapper/寄存器文件/CRG
- 芯片集成

## 风险升级

一个低风险模块可以在 `dev` 中以 `rtl in_progress` 迭代。以下影响升级到 `signoff`:
- 接口变更
- 寄存器变更
- 时钟/复位变更
- 约束变更
- 生成的 top
- chip-top RTL
- 多模块影响
- 低功耗
- PD 影响

## 轻量变更

以下变更不重新打开 RTL pipeline:
- 注释/格式化变更
- 非行为性文档
- 不改变 RTL 的测试清单

对轻量变更运行最近的 parser/checker。

## 规则

- 材料编辑前，使用 router packet，只读取其规则，启动拥有的阶段。
- 在交付模式中，仅用当前 artifact 和注册检查关闭 RTL。
- 仅当 packet 标记为 fresh 时重用下游证据。
