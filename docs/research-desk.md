# Research desk

Pip is the observatory's AI-assisted listening researcher. The public page combines published clips, ranked model notes and measured quality statistics. The existing detector and human review ledger remain the scientific records. Positive identification and validated performance require independent review.

## Geographic coverage

The worker monitors MBARI and rotates across 30 SanctSound station prefixes, 12 NOAA/NPS Noise Reference Station prefixes, six public Orcasound feeds and five Antarctic AWI deployments on PANGAEA. Each visit tries to retrieve six seconds. Initial cycles visit up to three feeds; subsequent cycles visit one. Source availability, clocks, licenses and native rates are checked per adapter. A failed visit is recorded and another archive gets its turn. Inventory size counts configured feeds/deployments. Verified clips and measured time count only actual samples. Historical sampling is deliberately sparse, and environmental prevalence cannot be estimated from the review queue.

Time-stamped samples include their source object, checksum information, source-native rate and the analysis copy's sampling rate. Native source bandwidth can be lower than the common 16 kHz analysis format. Public archive samples are distinct from detector-selected MBARI candidates. The human review and provisional recurrence counts currently cover MBARI. Supplemental sources have a separate 400 MB publication budget, within the shared 3 GB protected evidence allocation. Disable additional source acquisition with `ENABLE_SOURCE_SAMPLING=0` in the service environment. Ocean Networks Canada remains pending an authorized token and deployment-specific validation.

MBARI excerpts retain CC BY 4.0. NOAA collection rights and clock receipts are documented in the NOAA adapter. AWI data links preserve the dataset DOI and CC BY 4.0 terms. Orcasound playback and transformed excerpts retain CC BY-NC-SA 4.0. Use each recording's credit and license. A linked source URL may reference a much larger recording or daily archive.

## What the listener hears

Original retains archive level. For supplemental sources the PCM working excerpt is downmixed/resampled to 16 kHz. Boosted listening applies a 12 Hz high-pass and a constant gain targeting approximately −21 dBFS RMS with a 0.70 peak limit and 72 dB maximum gain. For low-frequency peaks the additional listening option translates a low-pass filtered band upward by 220 Hz while preserving time. Both are separate playback derivatives. Boosting raises recording noise along with signals. Spectrograms, source checksums, native MBARI WAVs and detector thresholds use the underlying evidence.

## OpenAI review

The worker sends a level-adjusted, unshifted six-second WAV and measured context to `gpt-audio-1.5` via Chat Completions. It requests text only, `store:false`, no tools and at most 450 completion tokens. Inputs include location, bandwidth, available quality measures, prior research questions and the current coverage. Selection favors unreviewed clips from locations with fewer AI attempts, provisional recurrence and strong detector responses. Each note contains an observation, tentative hypothesis, competing explanation, suggested human check and a 1–5 listening priority. Publication associates the note with the exact clip, model and time. SQLite stores the request ID, input audio digest, prompt version and returned usage. Research statistics distinguish AI reviews from human decisions.

Provide a dedicated OpenAI project key with Chat Completions write permission in `/etc/oceanacoustics/openai.key`, readable by root and the dedicated service group (0640). A terminal prompt keeps the key out of chat, shell history, source control and browser code:

```bash
sudo bash -c 'set -eu; d=/etc/oceanacoustics; install -d -o root -g oceanacoustics -m 0750 "$d"; umask 077; t=$(mktemp "$d/.key.XXXXXXXX"); systemd-ask-password "OpenAI project API key:" > "$t"; test -s "$t"; chgrp oceanacoustics "$t"; chmod 0640 "$t"; mv -T "$t" "$d/openai.key"'
```

Initial allowance is **three requests total**, with at most one attempt per worker cycle. Set `OCEAN_AI_LIMIT` in `/etc/default/oceanacoustics` to a cumulative request ceiling; zero disables further requests. It is an attempt cap, not a currency amount. The worker reserves an attempt durably before making the call. Timeouts, process interruption and invalid output consume the reservation to avoid duplicate billing. An authorization rejection pauses requests for that key. After fixing permissions, rotating the credential resumes attempts within the remaining allowance. API credits, key permissions and billing are managed by the operator. The public site cannot trigger paid calls. The current asset and ingestion release uses the existing root-owned installer.

[OpenAI project keys](https://platform.openai.com/api-keys) · [Audio input documentation](https://developers.openai.com/api/docs/guides/audio-chat-completions) · [Model and pricing](https://developers.openai.com/api/docs/models/gpt-audio-1.5)

## Artwork

The built-in image generator produced the researcher illustration. Generation prompt:

> A small sea otter acoustic scientist in a slightly oversized white lab coat, wearing studio headphones and listening intently with a pencil and pocket notebook. Waist-up, clear friendly silhouette, vintage marine field-guide ink illustration with subtle watercolor, warm ochre fur, teal accents, transparent background, no text.

### Monthly listening budget and catalog

Set `OCEAN_AI_MONTHLY_USD=25` in the service environment to replace the lifetime trial with a $25 calendar-month allowance (UTC). Zero pauses paid listening. The worker lock serializes reservations. Each six-second audio-in, text-out review reserves $0.05 before transmission. Completed requests use reported token counts at standard gpt-audio-1.5 rates ($2.50/M text input, $32/M audio input and $10/M text output). Failed, interrupted and unmetered requests retain their reservation for that month. Review these rates before changing models or request sizes. This ledger covers Pip’s requests only. The OpenAI billing dashboard is authoritative for account charges.

Every playable clip has a permanent recording page and a catalog description. Pip’s listening notes add an observation, possible source, alternative explanation and listening check. Pending clips use measured features. Possible-source filters represent hypotheses. Listening impressions such as Spooky describe how a clip sounds. The catalog publishes only categories with recordings.
