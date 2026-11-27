# Initial CPU pilot

On 2026-11-27 UTC a single worker on a 14-vCPU AMD EPYC VPS ran three two-window passes. Each processed one minute of delayed monitoring and one minute of historical audio. Hardware had 70 GiB RAM. Runtime used Python 3.12, NumPy 1.26.4, SciPy 1.15.3, Pillow 12.1.1, FFmpeg 6.1.1 and one OpenBLAS thread. Production uses Ubuntu packages and a CPU quota; production throughput remains to be measured.

| Pass | Wall seconds, including startup and discovery | Audio / wall time | Peak RSS (KiB) |
|---|---:|---:|---:|
| First acquisition | 9.59 | 12.5× | 125376 |
| Second acquisition | 5.31 | 22.6× | 126612 |
| Integrated detector, descriptors and grouping | 5.42 | 22.1× | 126984 |

A total of 360 seconds and 2,160,000 PCM bytes were analyzed. Listing, header and protocol bytes are additional. The dashboard's per-window speed (43.28× in this pilot) excludes discovery, interpreter startup and publication overhead. The final pass used 1.99 user CPU seconds and 0.43 system CPU seconds. The measured pilot state occupied 6,037,504 filesystem bytes including the manual references.

Monitoring sampled 23:57–24:00 UTC on 2026-11-25 off Monterey Bay. The strongest qualifying detector bins in successive windows were 23.4375, 78.125 and 39.0625 Hz. Three six-second candidates were preserved. No recurrence group or human identification was established. The 2015-07-28 00:00 and 00:01 windows contained only zeros. The 2015-07-29 12:00 window contained signal and produced no qualifying candidate. These six minutes describe sampled effort and provide no archive-wide prevalence estimate.

Reproduce the window selection from the dates and sample offsets in the ledger or fetch the same 24-bit PCM ranges from MBARI Pacific Sound, accessed 2026-11-27. The timing command was `OPENBLAS_NUM_THREADS=1 /usr/bin/time -v /usr/bin/python3 worker.py both --state STATE`. Network time and archive head change between runs. [Archive citation and terms](https://registry.opendata.aws/pacific-sound/)
