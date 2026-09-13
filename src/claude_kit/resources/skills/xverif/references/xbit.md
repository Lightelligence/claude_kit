# xbit bit 计算

xbit 是确定性 bit/value/expression calculator。遇到 SV literal、slice、signed、mask、表达式或 expected value 比较时必须使用，不要心算。

## 何时使用

- 进制转换：hex/bin/decimal/SV literal。
- signed/unsigned：如 `8'shff`。
- bit slice/index、concat/repeat、trunc/zext/sext。
- popcount、onehot、mask、gray code。
- 常量表达式、valid-ready 条件、opcode/field 比较。
- xdebug 返回 `xbit_hints.commands[]` 或 `slice_hint`。

## 入口

在 Claude Code 中优先使用注册的 MCP 工具。以下是输入给 Claude 的提示词，
不是终端命令：

```text
Call xverif_bit_convert with value="8'shff" and output_format="json".
Report unsigned and signed_value from the actual result.

Call xverif_bit_slice with value="32'hdeadbeef", msb=15, lsb=8,
and output_format="json". Report the actual extracted value.
```

这两个例子的预期结果分别是 unsigned=255/signed_value=-1 和 unsigned=190。
表达式计算使用 `xverif_bit_eval`；不要假设它支持所有 C/Python literal 语法。
当前 ETX 验证发现工具说明中的 `0x10 + 0x1` 示例返回 PARSE_ERROR。
以下 MCP 参数已经实测通过：

```text
Call xverif_bit_eval with expr="8'h10 + 8'h01" and output_format="json".
Report the actual result; the expected unsigned value is 17.

Call xverif_bit_check with expr="actual == expected",
vars={"actual":"8'h11","expected":"8'h11"}, and output_format="json".
Report matched from the actual response.
```

`xverif_bit_check.values` 是变量绑定 JSON 文件路径，不是预期数值；也不能与 `vars` 同时传入。
比较表达式应明确写出相等或其它条件；工具返回 `matched` 表示表达式真假。
遇到错误应报告失败，不能把错误响应当成结果或改用心算冒充工具输出。

## 读取规则

- 先看 `ok`。
- 结果读 `result.width/result.unsigned/result.signed_value/result.hex/result.bin/result.sv`。
- 条件读 `result.bool` 或 `matched`。
- `known:false` 不能当确定值。
- 错误时读 `error.code`，修输入宽度、literal 或表达式。

## 边界

xbit 不读 RTL、不做 elaboration、不查波形。需要事实先用 xdebug，拿到值后再用 xbit 算。
