# Ocean Acoustics

An open research observatory for public hydrophone recordings. Explore the measured spectrum of offshore Monterey Bay, play original-speed candidate excerpts, and trace each observation back to its archive bytes. The first detector measures transient spectral excess. Source identification requires independent evidence.

[Observatory](https://oceanacoustics.vincentmossman.com) · [Get started](START_HERE.md) · [Research protocol](RESEARCH.md) · [Source audit](docs/sources.md) · [Pilot results](benchmarks/pilot.md)

A CPU worker discovers MBARI Pacific Sound objects, acquires version-checked native 16 kHz PCM ranges, and writes SQLite WAL records plus static website data. Nginx serves the dashboard, audio and images. Monitoring and historical backfill run independently under one resource-limited timer. The public application accepts no writes.

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
