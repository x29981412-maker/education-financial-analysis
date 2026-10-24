# 数据与运行说明

## 统一输入字段

| 字段 | 含义 | 约束 |
| --- | --- | --- |
| record_id | 来源内记录编号 | 非空且唯一 |
| date | 台账记载日或银行入账日 | YYYY-MM-DD |
| amount | 带符号金额 | 非零，最多两位小数 |
| currency | 币种 | 三个英文字母，分别核对 |
| reference | 业务编号 | 可以为空，编号相同不覆盖身份冲突 |
| project_id | 项目编号 | 可为空，缺失时不能进入身份补充层 |
| counterparty | 付款方或交易对方 | 可以为空，不做名称模糊归并 |

文件编码为UTF-8，可带BOM。每行表示一条来源记录。一次核对的两份文件须使用一致的金额方向：收款为正，退款或支出为负。

## 用自己的数据运行

```bash
python -m pip install -e .
receipts check --ledger ledger.csv --bank bank.csv --output local-results --start 2026-06-01 --cutoff 2026-06-30 --policy cautious --window 5
```

也可以在安装后使用`python -m receipts check`。输出目录由调用者指定，不会覆盖输入文件。

- matches.csv：每组对应的台账和银行编号、方法、金额及截止日状态。
- row_trace.csv：全部有效输入的原始行号、规范化字段、匹配组和状态。
- review_queue.csv：剩余台账及候选银行记录，供补充资料后检查。
- bank_unmatched.csv：当期仅出现在银行一侧的记录。
- control.csv：按币种的发生额与差异分解，金额单位为元。
- input_issues.csv：隔离输入和原因。修正这些输入后应重新运行。

CSV是运行结果快照，手动修改结果文件不会改变核对程序中的关系。当前版本没有自动应用人工调整的接口。

## 模拟样例

data/ledger.csv和data/bank.csv由src/receipts/simulation.py生成，种子为47，业务期间为2026年6月。项目和付款方均为人工编号。

data/truth.csv只供实验评价使用。每行描述一组完整对应关系，缺失入账、银行费用及金额差异等不强行建立真实匹配标签。data/scenario_counts.csv列出有真实对应标签的场景组数。

本样例强调边界情况，没有以真实行业分布为目标；不能据此估计真实企业的自动核对比例。若更换样例种子，结果以新运行文件为准。

## PDF排版

报告默认在Windows上使用系统宋体。其他环境可以通过RECEIPTS_CJK_FONT指定有授权的TrueType中文字体路径；没有本地字体时使用ReportLab内置中文字体引用。字体文件不随仓库分发。
