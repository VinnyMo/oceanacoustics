# Research protocol

## Questions

Can a local-background spectral detector recover short tonal or broadband changes under different noise conditions? Do spectrally similar unidentified events recur on separate offshore recording dates? Can coastal fish-chorus descriptors discriminate reviewed coastal windows, and how much specificity is lost when comparing offshore candidates?

## Launch experiment

Use UTC-aligned, nonoverlapping 60-second windows at 2 kHz. Check the WAV encoding, object identity and byte range. Store object key, ETag, offsets and SHA-256 of the analyzed bytes. Use a Hann STFT with 256 samples, 64-sample hop, and a per-bin temporal median in decibels. Average excess over 11 frames. Search bins above 15.625 Hz and below Nyquist, with a floor on spectral magnitude. Preserve a six-second excerpt around the strongest qualifying response at or above 12 dB. Peak frequency describes a detector bin. The six seconds describe the excerpt duration. The detector does not estimate call boundaries. In a minute with multiple events only one is retained.

Store non-detections and zero-filled intervals. Zero samples can indicate padding, dropout or missing effort. A nonzero recording alone cannot establish valid calibrated effort. The coverage exporter reports half-open sample ranges; a null upper bound means the object data length has yet to be inspected. Unlisted archive days and a site's physical uptime need independent effort metadata. Published timestamps distinguish recording, object modification, acquisition and processing. Original publication delay is unknown unless the provider supplies it.

## Native 16 kHz experiment

Use 2,048 samples per transform and a 512-sample hop. This preserves 7.8125 Hz bin spacing and 32 ms frame spacing while extending the analysis to 8 kHz. Store native PCM and the recording rate on every new excerpt. Clustering compares full-band profiles within the same sample rate. The coastal reference comparator receives an anti-aliased 2 kHz copy of the candidate because its descriptor frequency range ends below 1 kHz. Higher-frequency detector performance remains unmeasured on held-out recordings. Hours analyzed counts each processed window. Distinct recording time collapses repeated UTC minutes from the same site across rates and archive versions.

## Evidence and review

Preserve the native PCM excerpt in a lossless WAV, its PCM checksum, a listening copy encoded as Opus at original speed, a waveform and a relative-level spectrogram. Brightness scales per image. Pressure calibration and cross-instrument loudness comparisons require deployment metadata. Correlation against the two numeric coastal reference profiles measures broad spectral shape. These scores have no validated species interpretation.

Tentative families use unit-length square-root pooled spectral magnitudes (32 bands), cosine similarity at least 0.97 and peak frequency within 8 Hz of a fixed exemplar. Distinct source days are required for publication of a group. Matching depends on acquisition order and thresholds. Reviewers should check correlated noise, recording artifacts, harmonics and repeated machinery. The initial group counter measures provisional clusters. Human classifications include known sound, probable match, unidentified recurring pattern, isolated anomaly, recording artifact and uncertain. Record rationale and conflicting evidence in the offline review ledger.

Run an experiment on a separate state directory pinned to a Git commit. Retain the source key/ETag, byte range, PCM hash, algorithm version, package versions, selection policy, thresholds and reviewer decisions. A changed archive version is a distinct observation. Compare unique chronological coverage separately from effort spent reprocessing versions.

## Evaluation and limitations

Freeze development decisions before scoring held-out deployments. Follow the [site, noise-stratum, positive and negative sampling protocol](docs/sources.md). The evaluation command reports precision, recall, false-positive rate, exclusions and denominators. Catalog candidates are deliberately selected and cannot estimate recall. Independently sample detector-negative windows. Published [pilot results](benchmarks/pilot.md) include the negative observations. No identified species, novel sound source or held-out accuracy claim follows from this pilot.
