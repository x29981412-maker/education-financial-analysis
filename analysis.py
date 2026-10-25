"""整理公开年报的口径、勾稽关系及现金流变化。"""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent
YEARS = (2023, 2024, 2025)


def load_data(path=ROOT / "data" / "financials.csv"):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    data = {}
    for row in rows:
        key = row["metric"]
        if key in data:
            raise ValueError(f"指标重复：{key}")
        values = {year: Decimal(row[f"fy{year}"].strip()) if row[f"fy{year}"].strip() else None for year in YEARS}
        if any(v is not None and not v.is_finite() for v in values.values()):
            raise ValueError(f"指标存在非有限数：{key}")
        data[key] = values
    return data, rows


def divide(a, b):
    return None if a is None or b is None or b == 0 else a / b


def change(a, b):
    value = divide(a, b)
    return value - 1 if value is not None else None


def calculate(data):
    indicators, checks = [], []
    for year in YEARS:
        def value(metric):
            return data[metric][year]

        revenue, profit, cash = value("revenue"), value("net_income"), value("operating_cf")
        previous = year - 1
        indicators.append({
            "year": year, "revenue_usd_million": revenue / 1000,
            "net_income_usd_million": profit / 1000, "operating_cf_usd_million": cash / 1000,
            "revenue_growth": change(revenue, data["revenue"].get(previous)),
            "net_income_growth": change(profit, data["net_income"].get(previous)),
            "operating_cf_growth": change(cash, data["operating_cf"].get(previous)),
            "cf_to_group_net_income": divide(cash, profit),
            "gross_margin": divide(revenue + value("cost_of_revenue"), revenue),
            "operating_margin": divide(value("operating_income"), revenue),
            "net_margin": divide(profit, revenue),
            "overseas_revenue_usd_million": value("overseas_segment") / 1000,
            "overseas_share": divide(value("overseas_segment"), revenue),
            "current_ratio": divide(value("current_assets"), value("current_liabilities"))})

        def check(name, left, right, pages):
            difference = left - right
            checks.append({"year": year, "check": name, "difference_usd_thousands": difference,
                           "status": "一致" if abs(difference) <= 1 else "待核实", "source_pdf_pages": pages})

        check("服务与产品收入合计", value("service_revenue") + value("product_revenue"), revenue, "190")
        check("收入与经营费用勾稽", revenue + value("operating_expenses"), value("operating_income"), "190")
        check("跨报表净利润一致性", profit, value("cf_net_income"), "190;195")
        check("分部收入加总", sum(value(m) for m in ("education_segment", "commerce_segment", "overseas_segment", "other_segment")), revenue, "128;190")
        check("现金流组成与汇率影响", sum(value(m) for m in ("operating_cf", "investing_cf", "financing_cf", "fx_effect")), value("cash_change"), "195-197")
        check("年初至年末现金滚动", value("cash_begin") + value("cash_change"), value("cash_end"), "197")
        if year in (2024, 2025):
            check("资产负债权益平衡", value("liabilities") + value("equity"), value("assets"), "187-189")
            check("受限现金口径衔接", value("cash_equivalents") + value("restricted_current") + value("restricted_noncurrent"), value("cash_end"), "187;197")
    profit_change = data["net_income"][2025] - data["net_income"][2024]
    deferred_change = data["deferred_cf"][2025] - data["deferred_cf"][2024]
    total_change = data["operating_cf"][2025] - data["operating_cf"][2024]
    bridge = [
        {"item": "合并净利润变动", "usd_thousands": profit_change},
        {"item": "递延收入现金流调整变动", "usd_thousands": deferred_change},
        {"item": "其他调整合计变动（差额计算）", "usd_thousands": total_change - profit_change - deferred_change},
        {"item": "经营现金流总变动", "usd_thousands": total_change}]
    return indicators, checks, bridge


def save_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: "" if v is None else format(v, ".6f").rstrip("0").rstrip(".")
                             if isinstance(v, Decimal) and v != v.to_integral_value() else str(v)
                             for k, v in row.items()})


def percent(value):
    return f"{value * 100:.2f}%"


def research_sections(data, indicators, checks, bridge):
    last = indicators[-1]
    observed = sum(v is not None for values in data.values() for v in values.values())
    zero = sum(row["difference_usd_thousands"] == 0 for row in checks)
    return [
        {"title": "研究问题与个人工作", "paragraphs": [
            "本研究以新东方教育科技集团2023—2025财年为例，核对公开财务数据的基本关系，并比较利润增长与经营现金流变化。"
            "研究采用三人小组形式，我负责数据整理与分析。",
            f"我的工作包括从原年报整理{len(data)}个指标、{observed}个已披露观测值，记录原始科目和页码，统一币种、"
            "财年与合并口径；在此基础上复算财务指标和勾稽关系，并整理现金流变化的分析依据。",
            "数据来源为港交所披露的新东方2025年报。原始金额单位为千美元，财年截至每年5月31日。"
            "所选资产负债表只列2024、2025年，2023年相应数据留空。研究区间固定为2023—2025财年。"],
         "headers": ["主要指标（百万美元）", "2023财年", "2024财年", "2025财年"],
         "table": [[label, *(f"{data[key][y] / 1000:,.3f}" for y in YEARS)] for key, label in
                   (("revenue", "营业收入"), ("net_income", "合并净利润"), ("operating_cf", "经营活动现金流净额"),
                    ("overseas_segment", "留学咨询服务收入"))],
         "source": "来源：新东方2025年报，PDF第128、190、195页。"},
        {"title": "数据口径与勾稽核验", "paragraphs": [
            "录入时保留原表负数符号，费用和现金流出均按原表记录。利润采用合并净利润，"
            "与现金流量表起点一致；现金采用现金、现金等价物和受限现金合计，不能只取资产负债表中的现金等价物。",
            f"共进行{len(checks)}项基本勾稽检查，{zero}项差额为零。检查包括收入加总、营业利润关系、净利润跨表一致性、"
            "现金流组成、现金滚动、资产负债权益关系与受限现金衔接。结果支持所选数据在这些关系上的算术一致性。",
            "分部收入取自年报经营回顾表，与合并财务报表分开标识。集团业务还包括教育课程和直播电商，"
            "集团现金流不能直接当作留学咨询业务现金流。合计关系一致也不能代替交易层面的核实或审计意见。"],
         "headers": ["检查内容", "覆盖年度", "检查次数", "原表PDF页"],
         "table": [["收入、费用与利润关系", "2023—2025", "6", "190"],
                   ["净利润与分部收入跨表", "2023—2025", "6", "128、190、195"],
                   ["现金流构成与滚动", "2023—2025", "6", "195—197"],
                   ["资产权益及受限现金", "2024—2025", "4", "187—189、197"]],
         "source": "完整检查记录见results/checks.csv；原始值和页码见data/financials.csv。"},
        {"title": "经营现金流与利润的变化", "paragraphs": [
            f"2025财年营业收入同比增长{percent(last['revenue_growth'])}，合并净利润同比增长{percent(last['net_income_growth'])}，"
            f"经营活动现金流量净额则同比变化{percent(last['operating_cf_growth'])}。利润和经营现金流在该年度表现出不同方向。",
            "经营现金流与合并净利润之比分别为" + "、".join(f"{r['cf_to_group_net_income']:.2f}" for r in indicators) +
            "。这一比值描述两个已披露项目的关系，其变化需要结合预收学费、费用结算和非现金调整解释。",
            "将2024至2025年的经营现金流差额分解：合并净利润增加50,615千美元，递延收入对现金流调整的贡献减少304,373千美元，"
            "其余调整合计增加27,707千美元，三项相加对应经营现金流减少226,051千美元。其余调整是差额汇总项，"
            "不是一项单独披露的现金流科目。"],
         "headers": ["2024至2025财年变动", "千美元"],
         "table": [[r["item"], f"{r['usd_thousands']:+,}"] for r in bridge],
         "source": "来源：年报PDF第190、195页；变动分解由本研究计算。"},
        {"title": "留学业务与研究结论", "paragraphs": [
            "留学咨询服务收入由2023财年的354.764百万美元增至2025财年的516.367百万美元。"
            f"2025财年约占集团收入的{percent(last['overseas_share'])}。这可以用于了解留学服务板块规模，"
            "但不能据此分摊集团经营现金流或推断某家留学机构的收款情况。",
            "研究中最需要注意的是口径：财年与自然年不同，合并净利润与归母净利润不同，现金流量表期末现金也包含受限现金。"
            "这些差异会影响比率与勾稽结果，必须先统一口径再做解释。",
            "我的主要贡献是把年报中的分散数据整理成可追溯的数据表，复算勾稽与指标，并将现金流变动拆解到可回查的科目。"
            "研究结论限于公开年报中的所选数据和基本财务关系。未接触企业内部账簿、银行流水或审计底稿。"],
         "headers": ["留学咨询服务", "2023财年", "2024财年", "2025财年"],
         "table": [["收入（百万美元）", *(f"{r['overseas_revenue_usd_million']:.3f}" for r in indicators)],
                   ["占集团收入", *(percent(r['overseas_share']) for r in indicators)]],
         "source": "来源：年报经营回顾分部收入表，PDF第128页。"}
    ]


def run():
    data, rows = load_data()
    indicators, checks, bridge = calculate(data)
    save_csv(ROOT / "results" / "indicators.csv", indicators)
    save_csv(ROOT / "results" / "checks.csv", checks)
    save_csv(ROOT / "results" / "cashflow_bridge.csv", bridge)
    lines = ["# 教育企业财务数据核验与现金流分析", "", "以新东方2023—2025财年为例", ""]
    for i, section in enumerate(research_sections(data, indicators, checks, bridge), 1):
        lines += [f"## {i}. {section['title']}", ""]
        for paragraph in section["paragraphs"]:
            lines += [paragraph, ""]
        lines += ["| " + " | ".join(section["headers"]) + " |", "| " + " | ".join("---" for _ in section["headers"]) + " |"]
        lines += ["| " + " | ".join(map(str, row)) + " |" for row in section["table"]]
        lines += ["", section["source"], ""]
    (ROOT / "paper").mkdir(exist_ok=True)
    (ROOT / "paper" / "report.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    if any(row["status"] != "一致" for row in checks):
        raise ValueError("存在待核实勾稽关系，请查看results/checks.csv")
    print(f"整理{len(rows)}个指标，{sum(v is not None for row in data.values() for v in row.values())}个披露值；"
          f"{len(checks)}项勾稽检查完成。")
    return data, indicators, checks, bridge


if __name__ == "__main__":
    run()
