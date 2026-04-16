from __future__ import annotations


def speaker_for_index(index: int) -> str:
    return "agent" if index % 2 == 0 else "customer"


def normalize_speaker(value: str) -> str:
    lowered = value.lower()
    if any(token in lowered for token in ("agent", "rep", "advisor", "support", "assistant", "operator")):
        return "agent"
    if any(token in lowered for token in ("customer", "caller", "client", "user", "consumer")):
        return "customer"
    return lowered.replace(" ", "_")[:32] or "agent"


def split_speaker_prefix(line: str, index: int) -> tuple[str, str]:
    for delimiter in (":", "-", "—"):
        if delimiter not in line:
            continue
        prefix, remainder = line.split(delimiter, 1)
        if 1 <= len(prefix.strip()) <= 24:
            return normalize_speaker(prefix.strip()), remainder.strip()
    return speaker_for_index(index), line.strip()


def turns_from_text(transcript_text: str) -> list[dict[str, object]]:
    parts = [line.strip() for line in transcript_text.splitlines() if line.strip()]
    if not parts:
        parts = [segment.strip() for segment in transcript_text.split(".") if segment.strip()]

    turns: list[dict[str, object]] = []
    for index, part in enumerate(parts[:200]):
        speaker, text = split_speaker_prefix(part, index)
        turns.append(
            {
                "speaker": speaker,
                "text": text,
                "timestamp_seconds": float(index * 8),
            }
        )
    return turns
