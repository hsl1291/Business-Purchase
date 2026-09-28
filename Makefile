.PHONY: install test demo

install:
	pip install -r requirements.txt

test:
	python -m pytest tests -q

# Full pipeline on the bundled sample data
demo:
	python run.py data/sample_raw_licenses.csv --out-dir data
	python tools/make_call_sheet.py data/ranked_with_estimate.csv -n 5 -o data/call_sheet.csv
	python -m src.valuation data/sample_pnl.yaml
	python -m src.deal_tracker data/deals -o data/deal_comparison.csv
