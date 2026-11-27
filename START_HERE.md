# Start here

The default source is MBARI 16 kHz PCM. Launch observations use 2 kHz PCM. This repository contains software, configuration, numeric reference descriptors and research documentation. Live measurements come from the host database. See the [initial measured baseline](benchmarks/pilot.md) and [operating procedures](docs/operations.md).

| Component | Entry point |
|---|---|
| Source discovery, validated ranges, PCM archive adapter | ingestion/provider.py and ingestion/mbari.py |
| Scheduling, budgets, coverage ledger and atomic publication | worker.py |
| FFT detection, waveform, lossless and listening excerpts | processing/dsp.py |
| Exemplar correlations and tentative cross-date groups | classification/ |
| Development references, high-resolution acquisition, reviews and evaluation | research/ |
| Browser dashboard and audio comparison | web/ |
| Owner-run installation, rollback and public health probe | deploy/ |

## Work on the project

1. Run the tests in [README.md](README.md). Use a separate state directory when changing an algorithm. Preserve existing results and evidence before migration. The launch schema runs one detector configuration per database.
2. Run one monitoring or backfill pass. Inspect `public/data/observatory.json`, the source ranges and SHA-256 evidence. Reproduce a clip from the published byte offset, byte length and S3 object validator.
3. Inspect the actual timer and public snapshot before reporting deployment status. The production service was activated on 2026-11-27 UTC. Its first run extended the six-minute pilot to eight minutes. Public HTTPS and ranged audio delivery passed. Use the live snapshot for current counts.
4. Handle human review offline. The [source audit](docs/sources.md) documents the reference excerpts and evaluation split. Held-out performance, deployment-aware calibration, broader coverage and long-term operational validation are open work.

The service checkout is under `/srv/oceanacoustics/releases/<commit>`. Research state is under `/srv/oceanacoustics/state`. The development checkout and pilot live under the operator's home. Never expose SQLite, logs, raw cache, research reference files, credentials or the home directory through Nginx.
