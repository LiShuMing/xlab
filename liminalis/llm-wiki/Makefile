BIN := bin/ctx
WEB_BIN := bin/ctx-web
DEMO_DATA ?= .demo-data
WEB_PROVIDER ?= llm

.PHONY: test build build-web web demo llm-demo psql-demo psql-llm-demo embed-demo eval-py clean

test:
	go test ./...

build:
	mkdir -p bin
	go build -o $(BIN) ./cmd/ctx

build-web:
	mkdir -p bin
	go build -o $(WEB_BIN) ./cmd/ctx-web

web: build-web
	$(WEB_BIN) --data $(DEMO_DATA) --provider $(WEB_PROVIDER)

demo: build
	rm -rf $(DEMO_DATA)
	$(BIN) --data $(DEMO_DATA) demo run

llm-demo: build
	rm -rf $(DEMO_DATA)
	$(BIN) --data $(DEMO_DATA) --provider llm demo run

psql-demo: build
	$(BIN) --repo postgres demo run

psql-llm-demo: build
	$(BIN) --repo postgres --provider llm demo run

embed-demo: build
	rm -rf $(DEMO_DATA)
	$(BIN) --data $(DEMO_DATA) demo seed
	$(BIN) --data $(DEMO_DATA) embed run --user kevin
	$(BIN) --data $(DEMO_DATA) embed run --user amy
	$(BIN) --data $(DEMO_DATA) query self --user kevin --text "AI infra 和周末城市生活" --semantic
	$(BIN) --data $(DEMO_DATA) match run --user kevin --semantic

eval-py:
	PYTHONPATH=.:$$PYTHONPATH python -c "from python.eval.report import main; main()"

clean:
	rm -rf bin $(DEMO_DATA)
