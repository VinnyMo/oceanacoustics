# Ocean Acoustics

An open research observatory for public hydrophone recordings. Explore the measured spectrum of offshore Monterey Bay, play original-speed candidate excerpts, and trace each observation back to its archive bytes. The first detector measures transient spectral excess. Source identification requires independent evidence.

[Get started](START_HERE.md) · [Research protocol](RESEARCH.md) · [Source audit](docs/sources.md) · [Pilot results](benchmarks/pilot.md)

A CPU worker discovers MBARI Pacific Sound objects, acquires version-checked native 16 kHz PCM ranges, and writes SQLite WAL records plus static website data. Nginx serves the dashboard, audio and images. Monitoring and historical backfill run independently under one resource-limited timer. The public application accepts no writes.

## Closing notes · November 2026

The hosted observatory has been retired. This repository preserves the software, methods and a compact [research ledger](results/observations.jsonl.gz). Each compressed JSON line describes an analyzed window, candidate, archive excerpt, listening review, review context, or provisional group. Source identifiers, checksums and byte ranges where available let researchers return to the public archives.

At the November 27, 19:05 UTC snapshot, the primary pipeline had processed 361 one-minute MBARI windows, representing 5 hours 54 minutes of distinct recording time. It flagged 288 candidates and grouped some into 14 provisional recurring patterns. Across the project we sampled 49 sites or deployments. Pip completed the initial review of all 35 anomalies in his startup queue. The ledger recorded zero human-reviewed candidates at that snapshot.

The most informative lesson came from listening back. Steady machinery and broadband hiss could earn a high review priority while offering a visitor little to distinguish on replay. We gave listening interest its own score and asked Pip to describe audible structure before suggesting an animal source. The recordings and notes are starting points for comparison. Confirming a biological source would take independent annotations and repeated observations under comparable conditions.

## Local run

Python 3.12, NumPy, SciPy, Pillow and FFmpeg with libopus are required. Use an existing environment or the Ubuntu packages listed in the installer. From the checkout:

```bash
export OPENBLAS_NUM_THREADS=1
python3 -m unittest discover -s tests -v
python3 worker.py monitor --state "$HOME/oceanacoustics-pilot"
python3 -m research.coverage "$HOME/oceanacoustics-pilot"
```

The worker contacts anonymous public S3 endpoints. Its state directory contains the database, cache, log, temporary area, and generated public files. Serve only `web/` at the site root and `STATE/public/data/` at `/data/`.

## Licensing and attribution

Software is GPL-3.0-only. Original project research figures, descriptors and written findings are offered under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Cite Ocean Acoustics and the algorithm revision. Source recordings retain their own licenses. Credit Monterey Bay Aquarium Research Institute for Pacific Sound audio, link the [dataset](https://registry.opendata.aws/pacific-sound/), specify access date and identify excerpts, visualizations and Opus encoding as transformations. NOAA reference excerpts stay outside the repository and public site. See the [source and license audit](docs/sources.md).
