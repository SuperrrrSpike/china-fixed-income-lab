from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_dashboard_renders_without_exceptions():
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(str(app_path)).run(timeout=20)
    assert not app.exception
    assert app.title[0].value == "中国固定收益分析实验室"
    assert [tab.label for tab in app.tabs] == ["市场看板", "债券风险", "晨报导出"]

