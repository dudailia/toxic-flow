# Two-pass reader: equality proof and memory (2026-10-23)

src/toxic_flow/data/stream_convert.py streams each raw CSV three times: day statistics,
the rows near each cut target, then the conversion part by part. Each part goes through
the same hftbacktest steps as convert_parts (convert.part_events and convert.order_part),
and the cut rule is the same function (convert._clean_cuts_from).

## 2024-01-01 against the recorded conversion

The old conversion's 7 parts were each re-hashed and checked against data/manifest.json
(all 7 match), then hashed together in order. The streamed reader converted the same raw
files in 20 parts, and its parts were hashed together in order, with nothing written:

| Conversion | Parts | Events | SHA-256 of the concatenated events |
|---|---|---|---|
| recorded (old reader, parts checked against the manifest) | 7 | 100,128,234 | e7a8a9bd13a46c018a006e6ca21311cf03af2feb80fd8386515215529582562c |
| streamed reader | 20 | 100,128,234 | e7a8a9bd13a46c018a006e6ca21311cf03af2feb80fd8386515215529582562c |

Identical. The inferred tick, lot and off-grid counts also equal convert.json's. The
hash is now in the manifest as events_sha256 for 2024-01-01, and every later conversion
records its own, so a rebuild with any part size can be checked.

## Peak memory (/usr/bin/time, maximum resident set size)

| Day | Events | Parts | Peak | Seconds |
|---|---|---|---|---|
| 2024-01-01 | 100,128,234 | 20 | 3.38 GB | 53.0 |
| 2024-05-01, the largest day | 198,258,877 | 37 | 3.91 GB | 120.2 |

The old reader peaked at 7.55 GB on 2024-01-01 and would have needed about 14 GB on
2024-05-01. The memory guard now estimates 2.84 GB plus 5.41 GB per billion events, with
events taken as raw rows times 1.08 (the two days' ratios were 1.017 and 1.074).

Tests: tests/unit/test_stream_convert.py checks that the streamed reader gives the same
parts and info as convert_parts for the same cuts (1 and 3 parts, 997-byte and 1 MB
chunks, with and without the larger later snapshot of Q13), the same concatenated events
for different part counts, and the same parts on a 3M-row slice of 2024-01-01.
