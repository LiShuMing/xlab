.PHONY: all test bench report clean

PYTHON ?= python3

all: test bench report

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -v

bench:
	PYTHONPATH=src $(PYTHON) tools/bench_suite.py

report:
	PYTHONPATH=src $(PYTHON) tools/build_report.py

clean:
	rm -rf .local/runs .local/report.html
