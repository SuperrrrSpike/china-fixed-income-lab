from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

import pandas as pd


CATEGORY_KEYWORDS = {
    "资金面": ("公开市场", "逆回购", "资金面", "流动性", "DR007", "Shibor"),
    "宏观": ("GDP", "CPI", "PPI", "PMI", "社融", "信贷", "通胀"),
    "信用": ("评级", "违约", "信用债", "信用利差", "展期"),
    "一级发行": ("发行", "招标", "中标", "簿记", "承销"),
}


def keyword_classify(title: str) -> tuple[str, str]:
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword.lower() in title.lower() for keyword in keywords):
            impact = "偏空" if any(word in title for word in ("违约", "上行", "收紧")) else "中性"
            return category, impact
    return "其他", "待评估"


@dataclass(frozen=True)
class OpenAICompatibleClassifier:
    base_url: str
    api_key: str
    model: str
    timeout: int = 30

    @classmethod
    def from_env(cls) -> "OpenAICompatibleClassifier":
        values = {
            "base_url": os.environ.get("LLM_BASE_URL", ""),
            "api_key": os.environ.get("LLM_API_KEY", ""),
            "model": os.environ.get("LLM_MODEL", ""),
        }
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise ValueError(f"LLM configuration missing: {', '.join(missing)}")
        return cls(**values)

    def classify(self, titles: list[str]) -> list[dict[str, str]]:
        endpoint = self.base_url.rstrip("/")
        if not endpoint.endswith("/chat/completions"):
            endpoint += "/chat/completions"
        prompt = (
            "请将以下债券市场标题分类。只返回JSON数组，每项必须包含title、category、impact。"
            "category只能是资金面、宏观、信用、一级发行、其他；impact只能是偏多、中性、偏空、待评估。\n"
            + "\n".join(f"- {title}" for title in titles)
        )
        payload = json.dumps(
            {
                "model": self.model,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": "你是固定收益市场信息分类助手。"},
                    {"role": "user", "content": prompt},
                ],
            },
            ensure_ascii=False,
        ).encode("utf-8")
        request = urllib.request.Request(
            endpoint,
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"LLM classification request failed: {exc}") from exc
        content = body["choices"][0]["message"]["content"].strip()
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content)
        items = json.loads(content)
        if not isinstance(items, list) or len(items) != len(titles):
            raise ValueError("LLM classification response has an unexpected shape")
        return items


def classify_news_frame(
    frame: pd.DataFrame,
    classifier: OpenAICompatibleClassifier | None = None,
) -> pd.DataFrame:
    if "title" not in frame.columns:
        raise ValueError("News input requires a title column")
    result = frame.copy()
    titles = result["title"].astype(str).tolist()
    if classifier is None:
        labels = [keyword_classify(title) for title in titles]
        result["category"] = [label[0] for label in labels]
        result["impact"] = [label[1] for label in labels]
        result["classification_method"] = "keyword_rules"
        return result
    labels = classifier.classify(titles)
    result["category"] = [item["category"] for item in labels]
    result["impact"] = [item["impact"] for item in labels]
    result["classification_method"] = "llm_with_manual_review_required"
    return result

