# 中国固定收益分析实验室

这是一个面向证券销售交易实习场景的 Python 项目，覆盖两个可独立展示的模块：

1. 债券市场晨报与一级发行跟踪系统
2. 中国国债收益率曲线与利率风险分析平台

项目同时支持 AKShare 在线数据和仓库内置的离线示例数据。离线数据只用于演示和测试，不代表真实市场行情。

## 功能

- 获取并标准化中国国债及政策性金融债收益率曲线。
- 计算关键期限日度 BP 变化、2Y-10Y 和 5Y-10Y 期限利差。
- 跟踪国债、政策性金融债和信用债发行信息。
- 生成结构化 Markdown 晨报和多工作表 Excel 数据包。
- 计算固定利率债净价、全价、应计利息和到期收益率。
- 计算麦考利久期、修正久期、凸性和 DV01。
- 模拟平行移位、陡峭化和扁平化情景下的债券价格损益。
- 提供 Streamlit 交互式看板及 pytest 自动测试。
- 支持规则分类与可选的 OpenAI 兼容接口进行新闻分类，LLM 结果必须人工复核。

## 项目结构

```text
china-fixed-income-lab/
├── app.py                         # Streamlit 入口
├── data/                          # 离线示例数据
├── src/fixed_income_lab/
│   ├── bond.py                    # 债券定价与风险指标
│   ├── cli.py                     # 命令行入口
│   ├── dashboard.py               # 交互式看板
│   ├── data.py                    # AKShare 和离线数据
│   ├── issuance.py                # 一级发行跟踪
│   ├── paths.py                   # Lexar 优先的输出路径
│   ├── report.py                  # 晨报与 Excel 导出
│   └── yield_curve.py             # 曲线、利差与情景冲击
└── tests/                         # 计算与数据校验
```

## 安装

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e '.[dev]'
```

中国大陆网络环境可以使用镜像：

```bash
python -m pip install -e '.[dev]' -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 快速演示

生成离线示例晨报和 Excel：

```bash
fixed-income-lab demo
```

使用 AKShare 获取在线曲线并生成报告：

```bash
fixed-income-lab fetch --start 20260901 --end 20260922
```

计算债券价格与风险：

```bash
fixed-income-lab price --settlement 2026-09-22 --maturity 2031-09-22 \
  --coupon 0.022 --yield-rate 0.019 --frequency 2
```

对新闻标题进行本地规则分类：

```bash
fixed-income-lab classify-news --input news.csv --output classified_news.csv
```

如需使用 OpenAI 兼容的聚合平台，先配置 `.env.example` 中对应的三个环境变量，再增加 `--use-llm`。密钥不得提交到 Git。

启动看板：

```bash
streamlit run app.py
```

运行测试：

```bash
pytest
```

## 输出路径

按以下优先级选择输出目录：

1. 环境变量 `FIXED_INCOME_OUTPUT_DIR`
2. `/Volumes/Lexar_Spike/项目归档/china-fixed-income-lab/reports`，仅在 Lexar 已挂载且可写时使用
3. 仓库本地 `reports/`

## 面试讲解主线

项目先把不同来源的数据转换为统一的长表结构，再由分析层计算 BP 变化、期限利差和债券风险指标。报告层只消费经过校验的结构化结果，避免让大模型直接生成或修改数值。大模型适合做新闻分类和文字初稿，最终数值、来源和结论必须人工复核。

在债券定价部分，价格等于未来现金流按到期收益率折现后的现值；净价等于全价减应计利息。久期衡量价格对收益率的一阶敏感度，凸性补充二阶影响，DV01 表示收益率变化 1BP 时价格的近似变化金额。

## 数据与免责声明

- AKShare 接口来源及字段可能随上游网站调整，代码对字段变化提供明确错误信息。
- `data/` 中的示例数据是合成数据，只用于离线演示。
- 本项目用于学习和工程展示，不构成投资建议。
