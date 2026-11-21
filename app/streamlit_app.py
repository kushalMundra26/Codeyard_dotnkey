"""SignalStudio — Streamlit entry point (multipage via st.navigation)."""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Hosted (Streamlit Community Cloud): keys live in the app's Secrets, never in git. Copy them into the
# environment before core/ is imported, so the same env-based config works locally (.env) and hosted.
import os  # noqa: E402

try:
    for _k, _v in st.secrets.items():
        if isinstance(_v, (str, int, float)):
            os.environ.setdefault(_k, str(_v))
except Exception:
    pass  # no secrets.toml locally — .env is used instead

st.set_page_config(page_title="Dot & Key · SignalStudio", page_icon=":material/light_mode:", layout="wide",
                   initial_sidebar_state="auto")

P = Path(__file__).parent / "pages"
pages = {
    "1 · Research": [
        st.Page(P / "1_Overview.py", title="Market overview", url_path="overview", default=True),
        st.Page(P / "6_Radar.py", title="Launch radar", url_path="radar"),
    ],
    "2 · Insight": [
        st.Page(P / "2_Product.py", title="Product deep-dive", url_path="product"),
        st.Page(P / "3_Strategy.py", title="SWOT & gaps", url_path="swot"),
        st.Page(P / "4_Audit.py", title="Listing audit", url_path="audit"),
    ],
    "3 · Create & approve": [
        st.Page(P / "5_Studio.py", title="Creative studio", url_path="studio"),
        st.Page(P / "7_Packs.py", title="Campaign packs", url_path="packs"),
    ],
    "Trust": [
        st.Page(P / "8_Trust.py", title="Accuracy & method", url_path="trust"),
        st.Page(P / "9_Label.py", title="Label reviews (gold set)", url_path="label"),
        st.Page(P / "10_Settings.py", title="Settings & data", url_path="settings"),
    ],
}
st.navigation(pages).run()
