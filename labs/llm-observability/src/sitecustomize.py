"""Enable the version-scoped bridge only for explicitly launched model processes."""

import os

if os.environ.get("LLM_OBSERVE_INSTRUMENT") == "1":
    from llm_observe.instrumentation import install

    install()
