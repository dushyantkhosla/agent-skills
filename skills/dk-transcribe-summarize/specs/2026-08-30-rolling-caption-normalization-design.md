# Rolling YouTube Caption Normalization

## Problem

YouTube auto-generated VTT files contain short, overlapping rolling-caption cues. The current repeated-phrase check counts those intermediary cues as real repetition, labels valid captions `garbled`, and unnecessarily falls back to audio download and cloud transcription.

## Goal

Use valid YouTube captions as the preferred transcription source while preserving detection of genuinely garbled/stuttering captions.

## Design

Add a small normalization helper in `scripts/audio.py` that:

- ignores cues shorter than 50 milliseconds, which are YouTube's rolling-caption intermediaries;
- strips/normalizes cue text and removes consecutive duplicate cues;
- returns normalized caption text for downstream consumers.

Make both `parse_vtt()` and `has_repeated_phrases()` consume the normalized representation. Keep the existing WPM, language, duration, and repeated-phrase thresholds unchanged.

No changes are needed to the audio downloader, model fallback chain, or output formats.

## Testing

Add a standard-library `unittest` suite and a small VTT fixture covering:

1. rolling captions normalize to one readable transcript;
2. rolling-caption duplicates do not trigger `has_repeated_phrases()`;
3. genuinely repeated five-word phrases still trigger the detector.

Run the focused tests and the full available test suite.

## Documentation

Update `SKILL.md` to explain that rolling YouTube cues are normalized before quality checks and that captions remain preferred over audio when the normalized result passes validation.

## Success Criteria

- The rolling-caption fixture is accepted as non-garbled.
- The genuine-stutter fixture remains rejected.
- Existing callers continue using `parse_vtt()` and `has_repeated_phrases()` without API changes.
- The skill documentation matches the implemented behavior.
