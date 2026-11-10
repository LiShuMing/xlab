# Sources and licensing

This lab is an independent implementation informed by these public projects:

- [kevinyvv/qwen-3-1.7b-finetune-proj](https://github.com/kevinyvv/qwen-3-1.7b-finetune-proj),
  MIT, Copyright (c) 2026 Kevin Wu. Reference topics: Qwen3 forward pass, LoRA,
  answer-only SFT, group-normalized rewards, reference adapters, and policy scoring.
- [M4cr0Chen/mini-vllm](https://github.com/M4cr0Chen/mini-vllm),
  MIT, Copyright (c) 2026 Zhenghong Chen. Reference topics: explicit prefill/decode
  boundaries, cache correctness experiments and fixed-work performance measurement.

The corresponding MIT notices are retained under `licenses/`. No runtime import,
symlink, data copy or model weight from these repositories is required.
Their published accuracy and throughput are not validation results of this lab.

Qwen model weights are downloaded separately from
[Qwen/Qwen3-0.6B](https://huggingface.co/Qwen/Qwen3-0.6B).
Model identity is recorded by resolved revision and file hashes; model licenses and
dependency licenses remain those of the respective upstream publishers.
