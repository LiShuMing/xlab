You are acting as my senior engineering partner.

I want to build a production-oriented prototype for a system that:
- reads my Gmail newsletter/subscription emails daily(eg: iceberg-dev/spark-dev email)
- summarizes them with an LLM(eg: qwen code)
- generates a daily digest to find the topic of email and the recent iceberg/spark discuss topic
- stores structured results for later retrieval and extension

Your task is to help me design and implement this system step by step.

## Important working mode

Do not just brainstorm.
Work in an implementation-oriented way.

Please do the following in order:

1. Refine the requirements into a precise engineering spec
2. Propose a minimal but solid architecture
3. Recommend a concrete tech stack
4. Design the database schema
5. Design the Gmail sync strategy
6. Design the LLM summarization workflow
7. Generate the initial project structure
8. Generate starter code for the key modules
9. Explain how to run the MVP locally
10. Suggest the next implementation steps

## Core requirements

The system should:
- connect to Gmail via Gmail API and OAuth
- support incremental sync
- focus on newsletter/subscription/update emails
- clean HTML-heavy email bodies into useful text
- summarize each email into structured JSON
- aggregate the daily summaries into one digest
- store raw messages and structured results
- avoid duplicate processing
- support future extension to:
  - local LLMs (e.g. Ollama)
  - web UI
  - user preferences
  - multi-user support

## Preferred stack

- Python
- FastAPI or CLI-first backend
- Gmail API
- SQLite for MVP, easy upgrade to Postgres
- modular package structure
- structured logging
- environment-based config
- clean separation of ingestion / parsing / summarization / digest / storage

## Expected output format

Please structure your answer as:

1. Engineering spec
2. Architecture
3. Tech stack decision
4. Database schema
5. Gmail sync design
6. LLM prompt and JSON schema design
7. File tree
8. Starter code
9. Local run guide
10. Next-step roadmap

Please include:
- concrete tradeoffs
- SQL schema examples
- Python code skeletons
- example prompts
- example output JSON
- practical implementation details

Avoid:
- generic AI product talk
- over-complicated distributed systems design
- vague "you could also..." suggestions without prioritization

Assume this is a serious personal productivity / knowledge-digest system that may later evolve into a product.