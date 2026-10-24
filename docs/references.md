# 参考资料与实现范围

## 业务背景

1. [毕马威审计与鉴证实习项目](https://kpmg.com/cn/zh/careers/campus/basecamp/audit-and-assurance.html)。用于理解审计实习与人才培养方向。
2. [毕马威2023年度审计质量报告](https://assets.kpmg.com/content/dam/kpmgsites/cn/pdf/zh/2024/07/2023-kpmg-audit-quality-report.pdf.coredownload.inline.pdf)，第16—18页。用于理解交易匹配、异常信息处理、原始记录追溯与报告校验的应用场景。

## 方法参考

3. [DataComPy](https://github.com/capitalone/datacompy)及其[Pandas使用说明](https://capitalone.github.io/datacompy/pandas_usage.html)。参考其逐项差异和可读报告的思路。
4. [Pandera](https://github.com/unionai-oss/pandera)及其[错误报告说明](https://pandera.readthedocs.io/en/stable/error_report.html)。参考输入字段校验与错误清单的组织方式。
5. [auto-reconcile](https://github.com/rubansi/auto-reconcile)。参考其将输入、匹配和期间差异分别组织的业务流程。

本仓库没有复制上述项目的源代码、数据或结果。核心实现使用Python标准库，重点是业务范围约束、双向唯一候选、合并拆分搜索及截止日差异分解。数据由本仓库生成器独立构造。

PDF排版使用ReportLab，属于独立的报告可选依赖。引用资料不代表相关机构参与、认可或使用本项目。
