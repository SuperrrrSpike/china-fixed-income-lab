from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .bond import BondAnalytics, BondSpec
from .data import fetch_china_yield_curve, sample_dataset
from .news import OpenAICompatibleClassifier, classify_news_frame
from .report import write_report_bundle


def _price_command(args: argparse.Namespace) -> int:
    analytics = BondAnalytics(
        BondSpec(
            settlement_date=args.settlement,
            maturity_date=args.maturity,
            coupon_rate=args.coupon,
            frequency=args.frequency,
            face_value=args.face,
        )
    )
    metrics = analytics.risk_metrics(args.yield_rate)
    for name, value in metrics.items():
        print(f"{name}: {value:.8f}")
    print("\nscenario_table")
    print(analytics.scenario_table(args.yield_rate, [-25, -10, 0, 10, 25]).to_string(index=False))
    return 0


def _demo_command(args: argparse.Namespace) -> int:
    dataset = sample_dataset()
    markdown, workbook = write_report_bundle(
        dataset.curve,
        dataset.issuance,
        dataset.news,
        destination=Path(args.output).expanduser() if args.output else None,
    )
    print(markdown)
    print(workbook)
    return 0


def _fetch_command(args: argparse.Namespace) -> int:
    dataset = sample_dataset()
    curve = fetch_china_yield_curve(args.start, args.end, args.curve_keyword)
    markdown, workbook = write_report_bundle(
        curve,
        dataset.issuance,
        dataset.news,
        destination=Path(args.output).expanduser() if args.output else None,
    )
    print(markdown)
    print(workbook)
    return 0


def _classify_command(args: argparse.Namespace) -> int:
    source = pd.read_csv(args.input)
    classifier = OpenAICompatibleClassifier.from_env() if args.use_llm else None
    result = classify_news_frame(source, classifier)
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(destination, index=False)
    print(destination)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="China fixed-income analytics lab")
    subparsers = parser.add_subparsers(dest="command", required=True)

    demo = subparsers.add_parser("demo", help="Generate an offline sample report bundle")
    demo.add_argument("--output", help="Optional report directory")
    demo.set_defaults(func=_demo_command)

    fetch = subparsers.add_parser("fetch", help="Fetch ChinaBond curve data through AKShare")
    fetch.add_argument("--start", required=True, help="YYYYMMDD")
    fetch.add_argument("--end", required=True, help="YYYYMMDD")
    fetch.add_argument("--curve-keyword", default="国债收益率曲线")
    fetch.add_argument("--output", help="Optional report directory")
    fetch.set_defaults(func=_fetch_command)

    price = subparsers.add_parser("price", help="Price a fixed-rate bond")
    price.add_argument("--settlement", required=True, help="YYYY-MM-DD")
    price.add_argument("--maturity", required=True, help="YYYY-MM-DD")
    price.add_argument("--coupon", required=True, type=float, help="Annual decimal rate")
    price.add_argument("--yield-rate", required=True, type=float, help="Annual decimal rate")
    price.add_argument("--frequency", type=int, default=2)
    price.add_argument("--face", type=float, default=100.0)
    price.set_defaults(func=_price_command)

    classify = subparsers.add_parser("classify-news", help="Classify market-news headlines")
    classify.add_argument("--input", required=True, help="CSV with a title column")
    classify.add_argument("--output", required=True, help="Output CSV")
    classify.add_argument("--use-llm", action="store_true")
    classify.set_defaults(func=_classify_command)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
