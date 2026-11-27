# Multi-site NOAA historical sampling

The launch audit enumerated 30 public SanctSound station prefixes and 12 NRS station prefixes. FLAC excerpts passed validation at all 30 SanctSound stations and 10 NRS stations. The 40 successful representative prefixes transferred 33,606,880 audio bytes and produced 240 seconds of decoded mono audio. That byte count excludes metadata, retries and development probes. These checks establish access, timing evidence and decoding. They do not measure detector performance or archive-wide coverage. See the [per-station receipts](noaa-pilot.json).

NRS02 (Gulf of Alaska) and NRS07 (southeastern United States) had public recordings. The available starting filenames could not be independently aligned with a sufficiently precise UTC deployment-clock anchor in the scanned objects. Both are recorded as skipped. NRS04 and NRS12 passed on the second sequence position. CI01 deployment 02 is excluded from research ingestion to preserve the held-out evaluation set.

## Reproduce the inventory audit

Run in the source tree on a system with Python, NumPy and FFmpeg. Use a scratch directory inside the project's bounded storage volume. The CLI outputs one JSON record per station; temporary FLAC prefixes are removed after decoding. Supply an individual station and sequence to repeat a receipt.

```sh
nice -n 15 python3 -m research.noaa_sources "$STATE/tmp" --sequence 0
nice -n 15 python3 -m research.noaa_sources "$STATE/tmp" --station nrs/audio/04/ --sequence 1
nice -n 15 python3 -m research.noaa_sources "$STATE/tmp" --station nrs/audio/12/ --sequence 1
```

The adapter rotates over a station's eligible deployments, then through up to 96 initial objects per deployment. Pre/post-deployment-labelled objects are excluded. Station and directory limits make this a bounded historical sample. Archive objects can be replaced; the stored GCS generation identifies the exact source version sampled. Publicly listed stations can outnumber verified samples. MB03_01 restricts selection to the published [usable interval](https://storage.googleapis.com/noaa-passive-bioacoustic/sanctsound/audio/mb03/01/metadata/SanctSound_MB03_01.json).

Each download checks FLAC STREAMINFO, sample count and native format, HTTP 206 byte bounds and FLAC frame integrity. The request limit for a single compressed prefix is 4 MiB. Evidence includes SHA-256 of the received prefix and the six-second mono PCM output; the archive MD5 refers to the whole GCS object and is checked when the full object fits within the prefix. FFmpeg resamples to 16 kHz and mixes to mono. A 5 kHz original still has a 2.5 kHz Nyquist limit. Timing uses explicit UTC suffixes, known SoundTrap conventions, verified HARP XWAV timestamps, or independent NOAA/Tethys metadata. Source version time reflects GCS maintenance and can differ from first availability. [NCEI archive conventions](https://www.ncei.noaa.gov/products/passive-acoustic-data) · [Tethys timestamp standard](https://tethys.sdsu.edu/distribution/current-docs/Tethys.pdf) · [Recorder conventions](https://doi.org/10.5061/dryad.x0k6djj2d)

For historical NRS deployments with incomplete GCS listings, the [clock receipt](noaa-clock-evidence.json) preserves the first workbook filename whose encoded date and time match the independent FILE_NAME, START_DATE and START_TIME columns, grouped by DEPLOYMENT_NAME. The adapter checks these against deployment XML, or matches the exact indexed filename inside the recorded effort. The input workbook SHA-256 identifies the snapshot. [NOAA file index](https://storage.googleapis.com/noaa-passive-bioacoustic/big_query_metadata/NCEI_NRS_PAD_metadata.xlsx)

The NOAA raw-series catalog records declare CC0-1.0 for both series. Each sample carries its project citation, DOI, station and original source link. Credit NOAA Office of National Marine Sanctuaries and U.S. Navy for SanctSound. Credit NOAA OAR PMEL, National Marine Fisheries Service, NOS ONMS and DOI National Park Service for NRS. [SanctSound rights](https://www.fisheries.noaa.gov/inport/item/80342) · [NRS rights](https://catalog.data.gov/dataset/noaa-ocean-noise-reference-station-network-nrs-raw-passive-acoustic-data) · [NRS station directory](https://www.pmel.noaa.gov/acoustics/noaanps-ocean-noise-reference-station-network/)
