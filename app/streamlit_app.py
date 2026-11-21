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
                   initial_sidebar_state="collapsed")

P = Path(__file__).parent / "pages"
pages = {
    "Research": [
        st.Page(P / "r_start.py", title="1 · Start", url_path="start", default=True),
        st.Page(P / "r_market.py", title="2 · Market", url_path="market"),
    ],
    "Insight": [
        st.Page(P / "i_product.py", title="3 · Product deep-dive", url_path="product"),
        st.Page(P / "i_swot.py", title="4 · SWOT & gaps", url_path="swot"),
        st.Page(P / "i_audit.py", title="5 · Listing audit", url_path="audit"),
    ],
    "Create & approve": [
        st.Page(P / "c_brief.py", title="6 · Brief", url_path="brief"),
        st.Page(P / "c_ads.py", title="7 · Ad studio", url_path="ads"),
        st.Page(P / "c_copy.py", title="8 · Copy & video", url_path="copy"),
        st.Page(P / "c_approve.py", title="9 · Approve", url_path="approve"),
    ],
    "Trust & settings": [
        st.Page(P / "8_Trust.py", title="Accuracy & method", url_path="trust"),
        st.Page(P / "9_Label.py", title="Label reviews", url_path="label"),
        st.Page(P / "10_Settings.py", title="Settings & data", url_path="settings"),
    ],
}
st.navigation(pages, position="top").run()
