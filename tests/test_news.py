import json

import pandas as pd
import pytest

from fixed_income_lab.news import (
    OpenAICompatibleClassifier,
    classify_news_frame,
    keyword_classify,
)


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")


def _classifier():
    return OpenAICompatibleClassifier(
        base_url="https://example.test/v1",
        api_key="fixture-key",
        model="fixture-model",
    )


def _mock_response(monkeypatch, content):
    payload = {"choices": [{"message": {"content": content}}]}
    monkeypatch.setattr(
        "fixed_income_lab.news.urllib.request.urlopen",
        lambda *args, **kwargs: _Response(payload),
    )


def test_keyword_classifier_recognizes_liquidity():
    category, impact = keyword_classify("央行开展公开市场逆回购操作")
    assert category == "资金面"
    assert impact == "中性"


def test_keyword_classifier_marks_default_negative():
    category, impact = keyword_classify("某信用债发生违约")
    assert category == "信用"
    assert impact == "偏空"


def test_classify_news_frame_adds_audit_method():
    result = classify_news_frame(pd.DataFrame({"title": ["国债发行招标结果公布"]}))
    assert result.iloc[0]["category"] == "一级发行"
    assert result.iloc[0]["classification_method"] == "keyword_rules"


def test_classify_news_frame_requires_title():
    with pytest.raises(ValueError):
        classify_news_frame(pd.DataFrame({"headline": ["x"]}))


def test_llm_classifier_accepts_exact_audited_labels(monkeypatch):
    title = "央行开展公开市场操作"
    _mock_response(
        monkeypatch,
        "```json\n"
        + json.dumps(
            [{"title": title, "category": "资金面", "impact": "中性"}],
            ensure_ascii=False,
        )
        + "\n```",
    )

    result = _classifier().classify([title])

    assert result == [{"title": title, "category": "资金面", "impact": "中性"}]


@pytest.mark.parametrize(
    ("item", "message"),
    [
        (
            {"title": "另一条标题", "category": "资金面", "impact": "中性"},
            "title",
        ),
        (
            {"title": "测试标题", "category": "股票", "impact": "中性"},
            "category",
        ),
        (
            {"title": "测试标题", "category": "宏观", "impact": "强烈看多"},
            "impact",
        ),
        ("not-an-object", "object"),
    ],
)
def test_llm_classifier_rejects_untrusted_labels(monkeypatch, item, message):
    _mock_response(monkeypatch, json.dumps([item], ensure_ascii=False))

    with pytest.raises(ValueError, match=message):
        _classifier().classify(["测试标题"])


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"choices": []},
        {"choices": [{"message": {"content": 123}}]},
    ],
)
def test_llm_classifier_rejects_malformed_provider_shape(monkeypatch, payload):
    monkeypatch.setattr(
        "fixed_income_lab.news.urllib.request.urlopen",
        lambda *args, **kwargs: _Response(payload),
    )

    with pytest.raises(ValueError, match="response shape"):
        _classifier().classify(["测试标题"])
