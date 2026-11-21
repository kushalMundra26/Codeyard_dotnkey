PY=.venv/bin/python
setup:
	uv venv --python 3.12 .venv && uv pip install --python $(PY) -r requirements.txt
collect:
	$(PY) scripts/collect.py --rounds 1
demo:
	$(PY) scripts/run_pipeline.py --category sunscreen --campaign
app:
	$(PY) -m streamlit run app/streamlit_app.py
api:
	$(PY) -m uvicorn api.main:app --port 8000 --reload
mcp:
	$(PY) mcp_server.py
test:
	$(PY) -m pytest -q
eval:
	$(PY) scripts/eval_accuracy.py --category sunscreen
