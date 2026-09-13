---
title: 'Treating Nvidia like a ''central bank'': a dev''s playbook'
description: 'Practical steps to reduce GPU vendor lock-in, benchmark performance, and design portable ML infrastructure in an Nvidia-dominated ecosystem.'
pubDate: 'Sep 13 2026'
heroImage: '../../assets/blog-placeholder-2.jpg'
---

A lot of teams now run on hardware and tooling where one vendor — Nvidia — provides the common rails: drivers, runtime images, performant libraries, and the majority of GPU capacity you'll encounter in cloud and on-prem. Call it what you want; as an engineer that reality changes how you build systems.

This post lists practical steps I use when designing ML infrastructure and apps so they perform well on Nvidia gear while remaining portable enough to migrate later or run on alternative accelerators.

## Why the "central bank" analogy matters for engineers

When a single vendor is the de facto standard, two things happen in practice:

- Upstream libraries and tools optimize first for that vendor. You'll get best throughput, tooling, and integrations there.
- Driver/runtime/version churn becomes a real operational surface: a driver mismatch can silently change numerical results or break start-up.

For a developer this means: optimize for the common case (Nvidia), but don't hard-code assumptions. Expect to rebuild or reconfigure when hardware changes.

Concrete, low-risk tradeoffs I make:

- Use vendor-optimized images for development and CI to get predictable performance (for example, base CUDA images for local profiling).
- Keep an abstraction layer around model runtime and IO so I can swap the backend (ONNX Runtime, Triton, custom CUDA kernel) with minimal changes to business logic.

## Short-term tactics: make your stack portable

These are quick wins you can apply today.

1) Use standard model exchange formats

Export models to ONNX or TorchScript as part of your CI. That provides a mechanical way to test alternatives later.

Example (PyTorch -> ONNX):

```python
import torch
# model: a trained PyTorch model
dummy = torch.randn(1, 3, 224, 224)
torch.onnx.export(model, dummy, "model.onnx", opset_version=17)
```

2) Containerize with vendor runtime in mind

Pick a CUDA base image for GPU builds, but keep your app code independent of CUDA APIs.

Dockerfile example:

```Dockerfile
FROM nvidia/cuda:12.1-runtime-ubuntu22.04
RUN apt-get update && apt-get install -y python3 python3-pip
COPY . /app
WORKDIR /app
RUN pip install -r requirements.txt
ENTRYPOINT ["python3", "serve.py"]
```

Run with the NVIDIA runtime:

```bash
docker run --gpus all --rm -it myimage:latest python3 serve.py
```

3) Probe hardware at startup

Add a small hardware-check step to fail fast and give clear errors. A single command often suffices:

```bash
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
```

Include that output in logs for postmortems.

4) CI: test multiple runtime labels, not multiple GPUs

Instead of trying to run GPU jobs on CI providers that don't support them, run smaller smoke tests on self-hosted GPU runners and replicate the same tests on CPU-hosted runners. Use a matrix to ensure code paths are exercised.

Example GitHub Actions matrix snippet:

```yaml
jobs:
  test:
    runs-on: ${{ matrix.runner }}
    strategy:
      matrix:
        runner: [ubuntu-latest, self-hosted-gpu]
    steps:
      - uses: actions/checkout@v4
      - name: Run tests
        run: |
          if [[ "${{ matrix.runner }}" == "self-hosted-gpu" ]]; then
            python -m pytest tests/gpu_only
          else
            python -m pytest tests/cpu
          fi
```

This keeps GPU work isolated while still validating the control paths.

## Long-term design: decouple, benchmark, and prepare for churn

Treat Nvidia-optimized code as the fast path. But structure your system so the fast path is a drop-in rather than baked into business logic.

- Abstractions: create a runtime interface in your app (load_model, run_inference, warmup). Implement an Nvidia-backed and a fallback implementation. Tests should assert both implementations deliver the same shape and types.

- Benchmarking: measure throughput and latency on representative inputs. Keep raw traces (latency percentiles, memory use) alongside model artifacts so you can compare across hardware or driver versions.

- Driver/version policy: pin runtime images and driver versions in deployment recipes. Have a rolling upgrade plan: test new driver images in a staging cluster before rolling to production.

- Progressive optimization: start with correctness and portability, then add vendor-specific optimizations behind feature flags. For example, enable cuDNN autotuner or fused kernels only after verifying numerical stability on your test set.

Conclusion

If Nvidia is the common rail you will likely run on, accept that and use it to your advantage for performance. At the same time, design for portability: model formats, a small runtime abstraction, targeted CI, and a clear benchmarking story give you options later. Those options are what make infrastructure resilient when the hardware and tooling landscape inevitably shifts.

If you want, I can sketch a small runtime interface for Python (load/run/warmup) and a minimal test harness you can drop into an existing repo.