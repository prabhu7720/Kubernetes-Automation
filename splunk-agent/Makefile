.PHONY: test demo lint
test:
	python -m pytest -q || python -m unittest discover -s tests -t .
demo:
	python scripts/build_sample_catalog.py
	SPLUNK_AGENT_CATALOG=catalog/demo.db python agent.py catalog import catalog/sample_catalog.json
	SPLUNK_AGENT_CATALOG=catalog/demo.db python agent.py ask "Generate dashboard for Kubernetes health" --out out/k8s
lint:
	ruff check . && mypy .
