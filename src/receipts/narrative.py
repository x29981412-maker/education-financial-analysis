"""报告与结果表使用同一次实验数据。"""

from __future__ import annotations

import csv
from pathlib import Path

from .data import money


def pct(number):
    return f"{number * 100:.2f}%" if isinstance(number, (int, float)) else "未计算"


def report_pages(root: Path, manifest: dict) -> list[dict]:
    rows = manifest["policies"]
    chosen = next(r for r in rows if r["policy"] == "cautious")
    with (root / "results" / "cautious" / "matches.csv").open(encoding="utf-8-sig", newline="") as f:
        matches = list(csv.DictReader(f))
    examples = []
    for method in ("reference", "group", "identity"):
        found = next(r for r in matches if r["method"] == method)
        examples.append([found["ledger_ids"], found["bank_ids"], found["ledger_amount"], method])
    after = next(r for r in matches if r["cutoff_status"] == "期后到账证据")
    examples.append([after["ledger_ids"], after["bank_ids"], after["ledger_amount"], "期后到账"])
    with (root / "results" / "cautious" / "control.csv").open(encoding="utf-8-sig", newline="") as f:
        control = next(csv.DictReader(f))
    return [
        {"title": "问题与数据", "paragraphs": [
            "分期收费项目中的业务台账与银行流水未必逐笔对应。付款可以合并，银行入账可以拆分，"
            "月末收款也可能在下一期间才出现银行记录。本项目研究这些差异如何影响自动核对，"
            "以及在资料不充分时应保留多少人工复核工作。",
            f"本次实验采用固定种子{manifest['seed']}生成的模拟样例，包含台账{manifest['ledger']['raw_rows']}行、"
            f"银行流水{manifest['bank']['raw_rows']}行。{manifest['excluded_rows']}行输入因编号重复、日期、金额精度或币种问题被隔离。"
            "数据不来自实习单位，也不含真实个人、银行账户或企业交易信息。",
            f"在五日窗口下，分层核对策略自动确认{chosen['matched_groups']}组，"
            f"已知标签上的组级精确率为{pct(chosen['precision'])}，台账覆盖率为{pct(chosen['ledger_coverage'])}。"
            "这些数值只用于比较本样例中的策略表现，不代表真实业务效果。"],
         "headers": ["场景", "业务差异", "核对重点"], "table": [
             ["单笔与退款", "正向收款和负向退款", "编号、币种、方向和金额"],
             ["合并与拆分", "一笔对应多笔", "同业务范围内的组金额"],
             ["月末与期后", "到账跨过截止日", "余额与后续证据分开"],
             ["信息不足", "同日同额或关键字段缺失", "候选唯一性与待查记录"]]},
        {"title": "核对规则与约束", "paragraphs": [
            "输入保留来源文件、原始行号和记录编号。字段统一后，金额以整数分计算，超过两位小数的金额不自动取整。"
            "重复编号的全部相关行进入隔离表，避免任意保留其中一条。每个币种单独核对，不在本实验中换算汇率。",
            "先寻找编号相同、金额相等、币种一致、方向一致、日期差在窗口内且无身份冲突的记录。"
            "只有当一对记录在候选关系两侧均唯一时才确认。编号相同但付款方或项目冲突的记录留待复核。",
            "合并与拆分仅在共同业务编号、项目和付款方内部搜索，组内金额必须精确相等。"
            "每侧组合最多四条，同一业务桶超过十二条时停止组合搜索。多个组合共享记录时全部保留待查。",
            "对于缺少银行业务编号的记录，分层策略补充使用项目和付款方。仅当金额、币种、方向及日期满足条件，"
            "且候选仍然双向唯一时才确认。金额日期优先策略则按日期距离选取剩余同额候选，作为比较基线。",
            "设 x 表示一组候选是否确认，则每条台账、每条银行记录的 x 之和均不超过1。"
            "每组台账金额之和等于对应银行金额之和。组合上限控制搜索规模，但不保证复杂批次中能找到所有合理关系。"],
         "headers": ["策略", "可用依据", "歧义处理"], "table": [
             ["编号唯一核对", "业务编号与金额", "保留"],
             ["编号与身份分层核对", "编号、组金额、项目与付款方", "保留"],
             ["金额日期优先", "先沿用编号与组匹配，再优先选近日期", "按固定顺序选取"]]},
        {"title": "策略比较与月末差异", "paragraphs": [
            "标签保存完整的真实对应组，供评价使用，匹配程序不读取标签。组内任一成员或对应关系错误，"
            "整组即记为误配。精确率为正确组数除以自动匹配组数；台账覆盖率为参与自动匹配的台账条数除以范围内有效台账条数。",
            "同日同额样例特意保留了业务资料无法区分的情况。金额日期优先可以提高覆盖率，但其确定性排序不能补足缺失证据。"
            "本样例将这类信息不足的取舍显式展示出来，未按真实企业的场景占比抽样。",
            f"分层策略在截止日后的五日内找到{chosen['subsequent_groups']}组到账证据。"
            "这些银行记录可以说明时间差，仍不计入截止日银行发生额。",
            f"CNY有效台账发生额为{control['ledger_current']}元，截止日银行发生额为{control['bank_current']}元，"
            f"原始差额为{control['raw_difference']}元。期后匹配对应的截止差额为{control['subsequent_settlement']}元，"
            f"未匹配台账为{control['ledger_unmatched']}元，未匹配银行为{control['bank_unmatched']}元。",
            "分解采用：台账发生额－当期银行发生额＝已匹配组的截止差额＋未匹配台账－未匹配银行。"
            "剩余校验差为零，只说明有效输入范围内分解守恒，不说明所有交易已经核清；输入隔离行仍需补正。"],
         "headers": ["策略", "自动组数", "误配组数", "精确率", "台账覆盖"],
         "table": [[r["strategy"], r["matched_groups"], r["wrong_groups"], pct(r["precision"]), pct(r["ledger_coverage"])] for r in rows]},
        {"title": "记录追溯与复核", "paragraphs": [
            "下表摘取本次分层策略的实际输出。记录编号可以回到data目录原始CSV，"
            "原始行号及匹配组编号见row_trace.csv。输入文件SHA-256与实验参数保存于manifest.json。",
            "同一匹配组中的金额严格相等。摘要表的数值不替代原始证据；对编号和日期口径的解释需要回查源记录。",
            "待查队列区分编号对应但金额或身份不一致、同金额候选不能唯一确认、未找到入账三种情况。"
            "仅在银行端出现的当期记录另行列示。下一步人工复核应补充收据、付款凭据或业务解释，"
            "本程序没有自动生成会计调整分录。",
            "退款使用负数表达，候选须同方向。完整业务分析还需要确认退款授权与业务依据；"
            "本项目只检验两份记录间的对应关系。"],
         "headers": ["台账编号", "银行编号", "金额（元）", "确认依据"], "table": examples},
        {"title": "窗口检验与复现", "paragraphs": [
            "在不改变样例与其他规则的条件下，将日期窗口设为1、3、5和7日。"
            "窗口扩大可以获得更多期后信息，也会扩大候选范围；其效果取决于交易日期分布及身份资料。",
            "实验结果可用python scripts/run_experiment.py重新生成。核心计算仅使用Python标准库。"
            "python -m unittest discover -s tests -v用于检查输入质量、匹配约束、期间边界及重复使用等问题。"
            "PDF由scripts/build_report.py从同一份实验结果生成，ReportLab仅用于排版。",
            "当前研究限定为单一币种内的对应核验，未处理汇兑、支付平台手续费净额、复杂多对多结算和完整复式记账。"
            "当前自动匹配只接受等额组，对小额差异不设置静默容差。模拟样例中的精确率不能直接外推到其他数据。",
            "方法参考：DataComPy的表间差异说明、Pandera的字段校验与错误清单，以及毕马威公开审计质量报告中的"
            "交易匹配和数据追溯场景。核对逻辑、样例和实验代码均在本仓库实现，引用入口见docs/references.md。"],
         "headers": ["窗口（日）", "自动组数", "误配组数", "期后组数", "待核对条数"],
         "table": [[r["window_days"], r["matched_groups"], r["wrong_groups"], r["subsequent_groups"], r["unresolved_ledger"]]
                   for r in manifest["sensitivity"]]}
    ]


def write_report(root: Path, manifest: dict):
    pages = report_pages(root, manifest)
    lines = ["# 项目收款多场景核对与月末差异分析", "", "模拟样例复现实验", ""]
    for i, page in enumerate(pages, 1):
        lines += [f"## {i}. {page['title']}", ""]
        for paragraph in page["paragraphs"]:
            lines += [paragraph, ""]
        lines += ["| " + " | ".join(page["headers"]) + " |",
                  "| " + " | ".join("---" for _ in page["headers"]) + " |"]
        for row in page["table"]:
            lines.append("| " + " | ".join(map(str, row)) + " |")
        lines.append("")
    (root / "paper").mkdir(exist_ok=True)
    (root / "paper" / "report.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
