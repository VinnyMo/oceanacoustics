# Archive provenance and access

## Pacific Sound

MBARI's MARS site is offshore in Monterey Bay. Decimated 2 kHz mono WAV covers frequencies below 1 kHz. Source UTC comes from the object key; preserve the RIFF INFO comments when investigating calibration or instrument changes. MBARI documents two successive hydrophones and separate sensitivities. Dashboard levels are relative digital measurements. Compare calibrated levels only after resolving the deployment, frequency response and gain. The registry lists daily updates. Object modification times can include archive migration, so a recording-to-object lag estimates the age of that archived version; original first-publication time can be unknown. Cite MBARI, date of access and the project paper when sharing a derivative. Audio is CC BY 4.0. [Archive and license](https://registry.opendata.aws/pacific-sound/) · [2 kHz format and calibration](https://docs.mbari.org/pacific-sound/notebooks/data/PacificSound2kHz/) · [Project paper](https://doi.org/10.1109/OCEANS.2016.7761363)

For a reviewed event, retrieve up to 60 seconds of native 16 kHz mono WAV. The tool locks the worker, checks storage, validates the S3 version and range, and writes a private excerpt and SHA-256 manifest under STATE/research. An exact UTC second and duration are required. Multi-day intervals must be split at midnight. The launch check read one second of the 2020-01-01 daily file. The higher-resolution archive may have different coverage. [16 kHz archive format](https://docs.mbari.org/pacific-sound/notebooks/data/PacificSound16kHz/)

```sh
python3 -m research.highres "$STATE" 2020-01-01T00:00:00Z 1
```

## Kim et al. and SanctSound

Dryad version 376573 contains UTC chorus start/end logs and effort metadata by site and deployment. The dataset API declares CC0-1.0 for those annotations. The acoustic recordings have separate terms and citation. During the launch audit the API served workbook names and SHA-256 digests. Anonymous downloads returned HTTP 401 through the API and 403 through the website. To verify retrieved workbooks, compare the SHA-256 against the Dryad version manifest. Use the Detection sheet's UTC boundaries and comments together with the MetaData sheet's effort intervals. Record unknown or masked effort separately. [Dryad](https://doi.org/10.5061/dryad.q2bvq83sw) · [Version manifest](https://datadryad.org/api/v2/versions/376573/files?per_page=100)

The original study also labelled two sustained example intervals in figure 2. Each local development excerpt starts inside a figure box chosen by site and UTC. Time boundaries read from the plot are approximate. A sample taken inside a chorus interval can include other animals, machinery or recording noise. Digital levels and the strongest bin inside a preselected band are descriptive; neither constitutes an identification. [Kim et al. 2025, figure 2](https://www.int-res.com/articles/meps_oa/m764p135.pdf) · [Kim et al. 2026, peak bands and study design](https://doi.org/10.1093/icesjms/fsag096)

| Reference | Published interval | Local excerpt (UTC, 30 s) | Native format and metadata |
|---|---|---|---|
| UF310 | Fig. 2C, MB02 off Point Pinos, green box | 2018-12-20 01:52:18 | 96 kHz, 16-bit mono. SoundTrap 500 at 66.5 m. The archive flags compromised low-frequency amplitude from 20–1000 Hz. [Deployment](https://storage.googleapis.com/noaa-passive-bioacoustic/sanctsound/audio/mb02/sanctsound_mb02_01/metadata/SanctSound_MB02_01.json) |
| UF440 | Fig. 2B, CI05 east of Anacapa, magenta box | 2021-08-07 10:55:02 | 48 kHz, 16-bit mono. SoundTrap 500 at 141.5 m. Bocaccio also appears in the plotted time range. The deployment metadata lists publication on 2022-03-31. [Deployment](https://storage.googleapis.com/noaa-passive-bioacoustic/sanctsound/audio/ci05/sanctsound_ci05_08/metadata/SanctSound_CI05_08.json) |

The development clips are lossless prefixes of the pinned GCS generations. Each reconstruction reads 4 MiB and verifies the byte hash, decoded sample count and signed 16-bit little-endian PCM hash. The repository contains provenance only. NOAA Office of National Marine Sanctuaries and U.S. Navy, 2020, *SanctSound Raw Passive Acoustic Data*, accessed for this implementation. NCEI identifies its citation and use conditions and publishes updates as needed. The private reference set has no project-assigned redistribution license. [NCEI record and terms](https://doi.org/10.25921/saca-sp25) · [Manifest](../research/references.json)

```sh
python3 -m research.references "$STATE/research"
python3 -m research.describe "$STATE/research"
```

Native-rate Welch estimates with one-second Hann windows and 50% overlap put the highest bin **inside each target's published peak band** at 304 Hz (MB02, search range 304–320 Hz) and 437 Hz (CI05, range 417–469 Hz). These two positive development examples provide neither negative controls nor an estimate of generalization. Their labels do not transfer to MBARI MARS.

## Evaluation protocol

1. Hypothesize that sustained energy in a reference band can help distinguish independently reviewed chorus intervals from absence at SanctSound sites. Define a second, independent question for offshore transfer. Pre-register a detector version, threshold, bin width, exclusion criteria and split manifest before computing held-out results.
2. Use MB02_01 and CI05_08 for development. Reserve CI01_02 for held-out UF440. Figure 2A provides a weak label near 2019-04-30 03:00 UTC there. Check recorder clock drift and discontinuities before matching. Reserve a different Monterey deployment with independently confirmed UF310 and negatives before testing that target. Never use neighbouring clips from one deployment across both splits.
3. Stratify disjoint 30-second windows by site, season and background. Have two reviewers inspect audio, spectrogram and surrounding long-term context blind to predictions. Record reviewer IDs, disagreements, source hashes, actual observed effort, noise stratum and exclusions in the experiment record. Label absent only after reviewing valid effort. Use quiet/moderate/loud noise bins with cut points fit on development recordings and frozen for the evaluation.
4. Freeze algorithm and parameters. For each target and window, export a binary prediction. Retain a separate audit record for uncertain, mixed-source and masked windows. Report coverage, excluded counts, performance by noise and deployment, and sample denominators. Document non-detections as well as positive examples. Estimate uncertainty by bootstrapping deployments once enough independent sites are available.
5. Use the evaluation command on a blinded CSV with columns `deployment,split,window_start_utc,target,noise,review,prediction`. Allowed reviews are `present`, `absent` and `unknown`; predictions are `present` or `absent`. Undefined denominators yield JSON null. The reports concern window-level performance. Event-boundary or alerts-per-hour evaluation needs a separate matching rule.

```sh
python3 -m research.evaluate reviewed-windows.csv
```

## Ocean Networks Canada

The ONC live page offers public listening from NEPTUNE and VENUS hydrophones. Oceans 3.0 programmatic archive access requires a personal profile token. Deployment-specific records identify device, coordinates, formats and version history. An example Chatham Sound icListen HF archive lists FLAC and WAV. ONC-owned portal datasets use CC BY 4.0; partner-owned and multimedia assets can have different conditions. Before activating an adapter, resolve deployment DOI, UTC clock, actual object coverage, recording format, license and permitted excerpts. Measure first-seen delay per feed. API access and archive delay remain untested pending an account token. [Live audio](https://www.oceannetworks.ca/multimedia/live-audio/) · [API setup](https://oceannetworkscanada.github.io/Oceans3.0-API/Home.html) · [Data policy](https://www.oceannetworks.ca/data/data-policy/) · [Example deployment](https://doi.org/10.34943/28ece634-7d7d-4a51-9d90-77eb2390c0a8)

## Reference spectrum comparison

The worker can compare each MBARI candidate against both historical development examples. The descriptor records 16 mean log spectral powers in disjoint 50 Hz bands from 100 to 900 Hz. The native coastal clips are polyphase-resampled to 2 kHz. A one-second Hann Welch estimate with 50% overlap provides one-Hz frequency bins. The comparison centers each log spectrum and reports the Pearson coefficient on a signed scale from −1 to +1. A flat spectrum has undefined correlation. The committed numerical summaries include the source PCM checksums, deployment and references. No waveform can be reconstructed from these coarse averages.

Similar background noise or instrument response may produce a high coefficient. The launch baseline assigns no taxon, chorus label or probability using this number. In particular the UF310 recorder's low-frequency amplitude quality flag applies to the reference curve. The algorithm has no validated threshold for offshore observations. To reproduce the reference file from retrieved audio, run the following in the repository root.

```sh
python3 -m research.build_descriptors "$STATE/research" | diff - classification/reference_bands.json
```


## Research feed archives

- Orcasound offers Salish Sea hydrophone streams, archived audio and annotated bouts. The registry lists typical latency of 10–120 seconds and CC BY-NC-SA 4.0. Preserve that license and distinguish lossy stream audio from lossless sources. [AWS registry](https://registry.opendata.aws/orcasound/)
- AWI PALAOA's early-2022 Antarctic deployment recorded at 96 kHz and 155 m depth. Daily tar files contain ten-minute WAV members under CC BY 4.0. The sampler resolves tar member offsets and retrieves six seconds by HTTP range. [PANGAEA dataset](https://doi.pangaea.de/10.1594/PANGAEA.962533)
- NOAA/NPS Noise Reference Stations offer multiyear regional comparisons in the 10–2,000 Hz band. Retain the original station bandwidth and check deployment metadata and use constraints. [NOAA network](https://www.pmel.noaa.gov/acoustics/noaanps-ocean-noise-reference-station-network/) · [Archive](https://www.ncei.noaa.gov/access/metadata/landing-page/bin/iso?id=gov.noaa.ngdc.mgg.pad%3ANRS_Raw_Data)
