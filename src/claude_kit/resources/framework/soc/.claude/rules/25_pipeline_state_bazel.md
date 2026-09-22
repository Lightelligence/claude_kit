---
paths:
  - "**/pipeline_state.json"
---

# Pipeline State 机制 (Bazel)

每个独立开发的模块拥有 `pipeline_state.json`。它是经过验证的协调信号，不是叙事日志。

## 阶段

只有 4 个阶段: `doc`, `rtl`, `verif`, `syn`。依赖关系: `doc -> rtl -> {verif, syn}`。

架构、审查、PD、发布和 signoff 是外部 handoff，不是额外阶段。

## 状态机

```
blocked -> pending -> in_progress -> done
                                \-> fail -> in_progress
pending -> skipped              # 仅批准的 doc 例外
done/in_progress/fail -> pending # 显式失效并附注
done -> in_progress             # RTL 重开；使消费者失效
```

## 更新 Pipeline State

```bash
# 开始 RTL 工作
python3 .claude/scripts/update_state.py \
  hw/rtl/<module> \
  rtl in_progress

# 完成 RTL (需要真实证据)
python3 .claude/scripts/update_state.py \
  hw/rtl/<module> \
  rtl done \
  --artifacts "hw/rtl/eic/eic.sv" \
  --check "soc_lint:passed" \
  --check "soc_comp:passed" \
  --check "rtl_quality:passed"

# 完成验证 (附加 MCP run_id)
python3 .claude/scripts/update_state.py \
  hw/rtl/<module> \
  verif done \
  --artifacts "<absolute_immutable_artifact_path_from_selected_MCP_run>" \
  --check "soc_sim:passed" \
  --run-id "<run_id_from_selected_MCP_run>" \
  --source-fingerprint "<source_fingerprint_from_selected_MCP_run>"
```

## 检查命令

上述命令是参数模板，不是运行或关闭阶段的授权。替换所有占位符，并仅在真实
检查通过后填写 `passed`。RTL fingerprint 由状态工具计算，不接受 `--fingerprint`。
`verif`/`syn` 的 run ID、fingerprint 和不可变 artifact 必须来自已选择的 MCP 运行。
如果当前项目布局或 MCP evidence 不满足状态校验器要求，保持阶段未完成并报告
`needs-validation`；不要用伪造 hash、目录或日志文本绕过校验。

```bash
# 查看当前状态 (紧凑)
python3 .claude/scripts/query_state.py \
  hw/rtl/<module> --compact

# 完整状态
python3 .claude/scripts/query_state.py \
  hw/rtl/<module>
```

## 规则

- 使用 `init_state.py` 仅当状态不存在时；每次转换使用 `update_state.py`。
- 在工作前标记阶段为 `in_progress`。
- `done` 需要存在的非空规范 artifact、所有必需检查通过、当前 RTL fingerprint。
- `verif` 和 `syn` 额外需要 `run_id`, `source_fingerprint` 和其注册 MCP 运行发出的不可变 artifact 路径。
- 失败记录失败的检查和修复说明。
- 在 `dev` 中，定向检查是任务证据但不关闭阶段。
- 在 `merge/signoff` 中，仅关闭 packet 标记为 stale 的阶段。
- 如果验证修复了 RTL，完成其最终仿真并使综合失效一次；反之亦然。
