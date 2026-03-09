VENV     := /home/lism/env/venv
PYTHON   := $(VENV)/bin/python
PIP      := $(VENV)/bin/pip
PYTEST   := $(VENV)/bin/pytest
RUFF     := $(VENV)/bin/ruff
MKDOCS   := $(VENV)/bin/mkdocs
UVICORN  := $(VENV)/bin/uvicorn

PRODUCT  ?= OpenAI GPT-4o
DEPTH    ?= deep

.PHONY: install lint test build serve refresh learn

install:
	$(PIP) install -e ".[dev]"

lint:
	$(RUFF) check src/ tests/
	$(VENV)/bin/mypy src/

test:
	$(PYTEST) tests/ --cov=src --cov-report=term-missing

build:
	$(MKDOCS) build --clean

serve:
	$(UVICORN) src.server:app --reload --port 8080

learn:
	$(PYTHON) -m src.prompt_learner

refresh:
	$(PYTHON) -m src.__main__ --product "$(PRODUCT)" --depth $(DEPTH)
	$(MKDOCS) build --clean
