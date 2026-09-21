import pandas as pd
import pytest

from fixed_income_lab.news import classify_news_frame, keyword_classify


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

