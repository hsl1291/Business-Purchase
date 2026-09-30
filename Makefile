.PHONY: install test demo

# Developer install (editable, with test deps). End users: see install.sh / install.ps1
install:
	pip install -e ".[dev]"

test:
	python -m pytest tests -q

# Full pipeline on the bundled sample data, in a throwaway workspace
demo:
	bizbuy init demo-workspace
	cd demo-workspace && bizbuy run samples/sample_raw_licenses.csv --out-dir data \
	  && bizbuy callsheet data/ranked_with_estimate.csv -n 5 -o data/call_sheet.csv \
	  && bizbuy value samples/sample_pnl.yaml \
	  && bizbuy deals samples/deals -o data/deal_comparison.csv
