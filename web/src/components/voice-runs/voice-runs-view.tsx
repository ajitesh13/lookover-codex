"use client";

import { Fragment, useMemo, useRef, useState, type MutableRefObject } from "react";
import { AlertCircle, Mic, Search, ShieldCheck, Waves } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type {
  ApiVoiceFinding,
  ApiVoiceRunFilters,
  ApiVoiceRunRecord,
  ApiVoiceRunsListResponse,
  ApiVoiceTranscriptTurn,
} from "@/lib/lookover-api";
import { formatCompactDate, formatRelativeTime } from "@/lib/lookover-format";

const initialDraftFilters: ApiVoiceRunFilters = {
  query: "",
  disposition: "",
  status: "",
  tenant: "",
  deployer: "",
  applicability: "",
  ai_disclosure_status: "",
  article: "",
  severity: "",
  from: "",
  to: "",
  high_risk_flag: "",
  emotion_or_biometric_features: "",
  human_handoff: "",
  page: 1,
  page_size: 25,
};

const badgeTone: Record<string, "neutral" | "success" | "warning" | "danger"> = {
  completed: "success",
  failed: "danger",
  pending: "warning",
  pass: "success",
  fail: "danger",
  needs_review: "warning",
  hard_fail: "danger",
  soft_fail: "danger",
  not_applicable: "neutral",
  not_evaluable_from_logs: "neutral",
};

const INITIAL_VISIBLE_TURNS = 8;
const VISIBLE_TURN_STEP = 12;

type TranscriptDensity = "comfortable" | "compact";

type TranscriptUIState = {
  visibleTurns: number;
  search: string;
  density: TranscriptDensity;
};

type GroupedTranscriptTurn = {
  index: number;
  turn: ApiVoiceTranscriptTurn;
};

function toneFor(value: string) {
  return badgeTone[value] ?? "neutral";
}

function findingsSummary(record: ApiVoiceRunRecord) {
  if (record.failing_finding_count > 0) {
    return `${record.failing_finding_count} failing article checks`;
  }
  if (record.needs_review_finding_count > 0) {
    return `${record.needs_review_finding_count} articles need review`;
  }
  return `${record.finding_count} article checks passed or were not applicable`;
}

function topArticleCounts(records: ApiVoiceRunRecord[]) {
  const counts = new Map<string, number>();
  for (const record of records) {
    for (const finding of record.findings) {
      const key = `${finding.article}:${finding.status}`;
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
  }
  return Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8);
}

function previewTurnsForRecord(record: ApiVoiceRunRecord) {
  if (record.transcript_preview.length > 0) return record.transcript_preview;
  if (record.transcript_turns.length > 0) return record.transcript_turns.slice(0, 4);
  return [];
}

function summarizeBoolean(value: boolean, positive: string, negative: string) {
  return value ? positive : negative;
}

function estimateReadTime(turns: ApiVoiceTranscriptTurn[]) {
  const words = turns
    .map((turn) => turn.text)
    .join(" ")
    .trim()
    .split(/\s+/)
    .filter(Boolean).length;
  const minutes = Math.max(1, Math.ceil(words / 180));
  return `${minutes} min read`;
}

function transcriptDurationLabel(turns: ApiVoiceTranscriptTurn[]) {
  if (turns.length === 0) return "No timing";
  const first = turns[0]?.timestamp_seconds ?? 0;
  const last = turns[turns.length - 1]?.timestamp_seconds ?? 0;
  const duration = Math.max(0, last - first);

  if (duration < 60) return `${duration.toFixed(0)}s span`;
  return `${(duration / 60).toFixed(1)}m span`;
}

function runMetadata(record: ApiVoiceRunRecord) {
  return [
    `${record.transcript_turns.length} turns`,
    transcriptDurationLabel(record.transcript_turns),
    estimateReadTime(record.transcript_turns),
    `${record.finding_count} findings`,
  ];
}

function escapeRegex(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function highlightSegments(text: string, query: string) {
  const normalizedQuery = query.trim();
  if (!normalizedQuery) {
    return [{ value: text, match: false }];
  }

  const matcher = new RegExp(`(${escapeRegex(normalizedQuery)})`, "ig");
  return text.split(matcher).filter(Boolean).map((value) => ({
    value,
    match: value.toLowerCase() === normalizedQuery.toLowerCase(),
  }));
}

function countTranscriptMatches(turns: ApiVoiceTranscriptTurn[], query: string) {
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) return 0;

  return turns.reduce((total, turn) => {
    const matches = turn.text.toLowerCase().match(new RegExp(escapeRegex(normalizedQuery), "g"));
    return total + (matches?.length ?? 0);
  }, 0);
}

function HighlightedText({ text, query }: { text: string; query: string }) {
  return (
    <>
      {highlightSegments(text, query).map((segment, index) =>
        segment.match ? (
          <mark key={`${segment.value}-${index}`} className="rounded bg-amber-100 px-0.5 text-inherit">
            {segment.value}
          </mark>
        ) : (
          <Fragment key={`${segment.value}-${index}`}>{segment.value}</Fragment>
        ),
      )}
    </>
  );
}

function groupTranscriptTurns(turns: GroupedTranscriptTurn[]) {
  const groups: Array<{ speaker: string; turns: GroupedTranscriptTurn[] }> = [];

  for (const entry of turns) {
    const previous = groups[groups.length - 1];
    if (previous && previous.speaker === entry.turn.speaker) {
      previous.turns.push(entry);
      continue;
    }
    groups.push({ speaker: entry.turn.speaker, turns: [entry] });
  }

  return groups;
}

function firstTurnIndexAtOrAfter(turns: ApiVoiceTranscriptTurn[], timestamp: number) {
  const foundIndex = turns.findIndex((turn) => turn.timestamp_seconds >= timestamp);
  return foundIndex >= 0 ? foundIndex : null;
}

function resolveFindingTurnIndex(record: ApiVoiceRunRecord, finding: ApiVoiceFinding) {
  const evidenceKey = finding.evidence_span.trim().toLowerCase();
  if (record.disclosure_timestamp !== null && finding.article === "50") {
    return firstTurnIndexAtOrAfter(record.transcript_turns, record.disclosure_timestamp);
  }

  if (evidenceKey) {
    const matchedTimeline = record.timeline.find((event) => {
      const normalizedEvent = event.event.trim().toLowerCase();
      return normalizedEvent.includes(evidenceKey) || evidenceKey.includes(normalizedEvent);
    });
    if (matchedTimeline) {
      return firstTurnIndexAtOrAfter(record.transcript_turns, matchedTimeline.timestamp_seconds);
    }
  }

  return null;
}

function TranscriptPanel({
  record,
  state,
  onStateChange,
  jumpToTurn,
  turnRefs,
}: {
  record: ApiVoiceRunRecord;
  state: TranscriptUIState;
  onStateChange: (updater: (state: TranscriptUIState) => TranscriptUIState) => void;
  jumpToTurn: (index: number | null) => void;
  turnRefs: MutableRefObject<Record<number, HTMLDivElement | null>>;
}) {
  const allTurns = record.transcript_turns;
  const search = state.search.trim();
  const totalMatches = countTranscriptMatches(allTurns, search);
  const visibleEntries = allTurns.slice(0, state.visibleTurns).map((turn, index) => ({ turn, index }));
  const groupedTurns = groupTranscriptTurns(visibleEntries);
  const firstMatchIndex = search
    ? allTurns.findIndex((turn) => turn.text.toLowerCase().includes(search.toLowerCase()))
    : -1;

  return (
    <div className="rounded-2xl border border-lookover-border bg-slate-50/70">
      <div className="sticky top-0 z-10 rounded-t-2xl border-b border-lookover-border bg-white/95 px-4 py-4 backdrop-blur">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="lookover-label">Transcript</div>
            <div className="mt-2 flex flex-wrap gap-2">
              {runMetadata(record).map((item) => (
                <span
                  key={`${record.voice_run_id}-${item}`}
                  className="rounded-full border border-lookover-border bg-slate-50 px-3 py-1 text-[12px] text-lookover-text-muted"
                >
                  {item}
                </span>
              ))}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              className={`rounded-full border px-3 py-1.5 text-[12px] font-medium transition ${
                state.density === "comfortable"
                  ? "border-slate-900 bg-slate-900 text-white"
                  : "border-lookover-border bg-white text-slate-700 hover:bg-slate-50"
              }`}
              onClick={() => onStateChange((value) => ({ ...value, density: "comfortable" }))}
            >
              Comfortable
            </button>
            <button
              type="button"
              className={`rounded-full border px-3 py-1.5 text-[12px] font-medium transition ${
                state.density === "compact"
                  ? "border-slate-900 bg-slate-900 text-white"
                  : "border-lookover-border bg-white text-slate-700 hover:bg-slate-50"
              }`}
              onClick={() => onStateChange((value) => ({ ...value, density: "compact" }))}
            >
              Compact
            </button>
          </div>
        </div>

        <div className="mt-4 flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <label className="flex min-w-0 flex-1 items-center gap-2 rounded-xl border border-lookover-border bg-white px-3 py-2">
            <Search className="h-4 w-4 text-slate-400" />
            <input
              className="min-w-0 flex-1 border-0 bg-transparent text-[14px] text-slate-900 outline-none"
              value={state.search}
              onChange={(event) => onStateChange((value) => ({ ...value, search: event.target.value }))}
              placeholder="Search transcript text"
            />
          </label>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[12px] text-lookover-text-muted">
              {search ? `${totalMatches} matches` : "Search all turns"}
            </span>
            <button
              type="button"
              className="rounded-lg border border-lookover-border px-3 py-2 text-[12px] font-medium text-slate-700 transition hover:bg-white disabled:opacity-50"
              onClick={() => jumpToTurn(firstMatchIndex >= 0 ? firstMatchIndex : null)}
              disabled={firstMatchIndex < 0}
            >
              Jump to first match
            </button>
            <button
              type="button"
              className="rounded-lg border border-lookover-border px-3 py-2 text-[12px] font-medium text-slate-700 transition hover:bg-white disabled:opacity-50"
              onClick={() => jumpToTurn(firstTurnIndexAtOrAfter(allTurns, record.disclosure_timestamp ?? -1))}
              disabled={record.disclosure_timestamp === null}
            >
              Disclosure moment
            </button>
          </div>
        </div>
      </div>

      <div className="space-y-4 px-4 py-4">
        {groupedTurns.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-lookover-border bg-white px-4 py-8 text-center text-[14px] text-lookover-text-muted">
            No structured transcript turns are available for this run.
          </div>
        ) : null}

        {groupedTurns.map((group, groupIndex) => {
          const groupStart = group.turns[0]?.turn.timestamp_seconds ?? 0;
          const groupEnd = group.turns[group.turns.length - 1]?.turn.timestamp_seconds ?? groupStart;

          return (
            <section key={`${group.speaker}-${groupStart}-${groupIndex}`} className="rounded-2xl border border-lookover-border bg-white">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-lookover-border px-4 py-3">
                <div className="flex items-center gap-3">
                  <span className="text-[12px] font-semibold uppercase tracking-[0.12em] text-slate-500">{group.speaker}</span>
                  <span className="text-[12px] text-lookover-text-muted">
                    {group.turns.length} turn{group.turns.length === 1 ? "" : "s"}
                  </span>
                </div>
                <span className="text-[12px] text-lookover-text-muted">
                  {groupStart.toFixed(1)}s to {groupEnd.toFixed(1)}s
                </span>
              </div>
              <div className={state.density === "compact" ? "divide-y divide-slate-100" : "space-y-3 p-3"}>
                {group.turns.map(({ turn, index }) => (
                  <div
                    key={`${index}-${turn.timestamp_seconds}-${turn.text.slice(0, 18)}`}
                    ref={(element) => {
                      turnRefs.current[index] = element;
                    }}
                    className={
                      state.density === "compact"
                        ? "grid gap-2 px-4 py-3 md:grid-cols-[84px,1fr]"
                        : "rounded-xl border border-slate-100 bg-slate-50/70 px-4 py-3"
                    }
                  >
                    <div className="text-[12px] font-medium text-lookover-text-muted">{turn.timestamp_seconds.toFixed(1)}s</div>
                    <p className={`text-slate-900 ${state.density === "compact" ? "text-[13px] leading-6" : "text-[14px] leading-6"}`}>
                      <HighlightedText text={turn.text} query={search} />
                    </p>
                  </div>
                ))}
              </div>
            </section>
          );
        })}

        {state.visibleTurns < allTurns.length ? (
          <div className="flex items-center justify-center">
            <button
              type="button"
              className="rounded-xl border border-lookover-border bg-white px-4 py-2.5 text-[13px] font-semibold text-slate-900 transition hover:bg-slate-50"
              onClick={() =>
                onStateChange((value) => ({
                  ...value,
                  visibleTurns: Math.min(allTurns.length, value.visibleTurns + VISIBLE_TURN_STEP),
                }))
              }
            >
              Show {Math.min(VISIBLE_TURN_STEP, allTurns.length - state.visibleTurns)} more turns
            </button>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function VoiceRunExpandedContent({
  record,
  state,
  onStateChange,
}: {
  record: ApiVoiceRunRecord;
  state: TranscriptUIState;
  onStateChange: (updater: (state: TranscriptUIState) => TranscriptUIState) => void;
}) {
  const turnRefs = useRef<Record<number, HTMLDivElement | null>>({});

  function jumpToTurn(index: number | null) {
    if (index === null) return;

    const nextVisibleTurns = Math.max(state.visibleTurns, index + 1);
    if (nextVisibleTurns !== state.visibleTurns) {
      onStateChange((value) => ({ ...value, visibleTurns: nextVisibleTurns }));
      setTimeout(() => {
        turnRefs.current[index]?.scrollIntoView({ behavior: "smooth", block: "center" });
      }, 40);
      return;
    }

    turnRefs.current[index]?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[1.15fr,0.85fr]">
      <TranscriptPanel
        record={record}
        state={state}
        onStateChange={onStateChange}
        jumpToTurn={jumpToTurn}
        turnRefs={turnRefs}
      />

      <div className="space-y-4">
        <div className="rounded-2xl border border-lookover-border bg-slate-50/70 px-4 py-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <div className="lookover-label">Created</div>
              <div className="mt-2 text-[14px] text-slate-900">{formatCompactDate(record.created_at)}</div>
            </div>
            <div>
              <div className="lookover-label">Applicability</div>
              <div className="mt-2 text-[14px] text-slate-900">{record.applicability.replaceAll("_", " ")}</div>
            </div>
            <div>
              <div className="lookover-label">Tenant / Deployer</div>
              <div className="mt-2 text-[14px] text-slate-900">
                {record.tenant || "—"} / {record.deployer || "—"}
              </div>
            </div>
            <div>
              <div className="lookover-label">Disclosure</div>
              <div className="mt-2 text-[14px] text-slate-900">{record.ai_disclosure_status.replaceAll("_", " ")}</div>
            </div>
            <div>
              <div className="lookover-label">Risk flag</div>
              <div className="mt-2 text-[14px] text-slate-900">
                {summarizeBoolean(record.high_risk_flag, "High risk", "Not high risk")}
              </div>
            </div>
            <div>
              <div className="lookover-label">Human handoff</div>
              <div className="mt-2 text-[14px] text-slate-900">
                {summarizeBoolean(record.human_handoff, "Path present", "No path")}
              </div>
            </div>
          </div>
        </div>

        {record.timeline.length > 0 ? (
          <div className="rounded-2xl border border-lookover-border bg-white px-4 py-4">
            <div className="lookover-label">Timeline</div>
            <div className="mt-3 space-y-2">
              {record.timeline.map((item, index) => (
                <button
                  key={`${record.voice_run_id}-timeline-${index}`}
                  type="button"
                  className="flex w-full items-center justify-between rounded-xl border border-lookover-border bg-slate-50/70 px-3 py-3 text-left transition hover:bg-slate-50"
                  onClick={() => jumpToTurn(firstTurnIndexAtOrAfter(record.transcript_turns, item.timestamp_seconds))}
                >
                  <span className="text-[13px] font-medium text-slate-900">{item.event}</span>
                  <span className="text-[12px] text-lookover-text-muted">{item.timestamp_seconds.toFixed(1)}s</span>
                </button>
              ))}
            </div>
          </div>
        ) : null}

        <div className="rounded-2xl border border-lookover-border bg-white">
          <div className="border-b border-lookover-border px-4 py-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="lookover-label">Findings</div>
                <div className="mt-2 text-[14px] text-lookover-text-muted">{findingsSummary(record)}</div>
              </div>
              <Badge tone={toneFor(record.disposition)}>{record.disposition.replaceAll("_", " ")}</Badge>
            </div>
          </div>
          <div className="space-y-3 px-4 py-4">
            {record.findings.map((finding, index) => {
              const targetIndex = resolveFindingTurnIndex(record, finding);
              return (
                <div key={`${finding.article}-${index}`} className="rounded-2xl border border-lookover-border bg-slate-50/70 px-4 py-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone={toneFor(finding.status)}>{finding.status.replaceAll("_", " ")}</Badge>
                      <span className="text-[13px] font-semibold text-slate-900">Article {finding.article}</span>
                      <span className="text-[12px] uppercase tracking-[0.12em] text-lookover-text-muted">{finding.severity}</span>
                    </div>
                    <button
                      type="button"
                      className="rounded-lg border border-lookover-border bg-white px-3 py-2 text-[12px] font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-default disabled:opacity-60"
                      onClick={() => jumpToTurn(targetIndex)}
                      disabled={targetIndex === null}
                      title={targetIndex === null ? "This finding does not expose a transcript timestamp." : undefined}
                    >
                      {targetIndex === null ? "Evidence not time-linked" : "Jump to transcript"}
                    </button>
                  </div>
                  <p className="mt-3 text-[14px] leading-6 text-slate-700">{finding.reason}</p>
                  <div className="mt-3 flex flex-wrap gap-2 text-[12px] text-lookover-text-muted">
                    <span className="rounded-full border border-white/80 bg-white px-3 py-1">
                      Confidence {Math.round(finding.confidence * 100)}%
                    </span>
                    <span className="rounded-full border border-white/80 bg-white px-3 py-1">
                      {finding.owner || "Owner unassigned"}
                    </span>
                    {finding.manual_review_required ? (
                      <span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-amber-700">Manual review</span>
                    ) : null}
                  </div>
                </div>
              );
            })}
            {record.findings.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-lookover-border bg-slate-50/70 px-4 py-8 text-center text-[14px] text-lookover-text-muted">
                No findings are stored for this run.
              </div>
            ) : null}
          </div>
        </div>

        {record.transcript_turns.length === 0 && record.transcript_text ? (
          <div className="rounded-2xl border border-lookover-border bg-white px-4 py-4">
            <div className="lookover-label">Raw transcript fallback</div>
            <p className="mt-3 whitespace-pre-wrap text-[14px] leading-6 text-slate-700">{record.transcript_text}</p>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function VoiceRunCard({
  record,
  open,
  onToggle,
  state,
  onStateChange,
}: {
  record: ApiVoiceRunRecord;
  open: boolean;
  onToggle: (open: boolean) => void;
  state: TranscriptUIState;
  onStateChange: (updater: (state: TranscriptUIState) => TranscriptUIState) => void;
}) {
  const previewTurns = previewTurnsForRecord(record);

  return (
    <details
      open={open}
      onToggle={(event) => onToggle((event.currentTarget as HTMLDetailsElement).open)}
      className="rounded-[20px] border border-lookover-border bg-white"
    >
      <summary className="cursor-pointer list-none px-5 py-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="lookover-label">Voice run</div>
            <div className="mt-2 flex flex-wrap items-center gap-3">
              <h3 className="text-[18px] font-semibold tracking-[-0.03em] text-slate-900">{record.call_id}</h3>
              <span className="text-[13px] text-lookover-text-muted">{formatRelativeTime(record.updated_at)}</span>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {runMetadata(record).map((item) => (
                <span
                  key={`${record.voice_run_id}-${item}`}
                  className="rounded-full border border-lookover-border bg-slate-50 px-3 py-1 text-[12px] text-lookover-text-muted"
                >
                  {item}
                </span>
              ))}
            </div>
            <div className="mt-4 grid gap-2">
              {previewTurns.length > 0 ? (
                previewTurns.slice(0, 3).map((turn, index) => (
                  <div
                    key={`${record.voice_run_id}-preview-${index}`}
                    className="rounded-xl border border-lookover-border bg-slate-50/70 px-3 py-3"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-[12px] font-semibold uppercase tracking-[0.12em] text-slate-500">{turn.speaker}</span>
                      <span className="text-[12px] text-lookover-text-muted">{turn.timestamp_seconds.toFixed(1)}s</span>
                    </div>
                    <p className="mt-1.5 max-h-[3.25rem] overflow-hidden text-[13px] leading-6 text-slate-800">{turn.text}</p>
                  </div>
                ))
              ) : (
                <p className="max-w-[64ch] text-[14px] leading-6 text-lookover-text-muted">
                  {record.transcript_text || "Stored voice-run transcript"}
                </p>
              )}
            </div>
            <div className="mt-3 flex flex-wrap gap-2 text-[12px] text-lookover-text-muted">
              <span>{summarizeBoolean(record.high_risk_flag, "High risk", "Standard risk")}</span>
              <span>{summarizeBoolean(record.human_handoff, "Human path present", "No handoff path")}</span>
              <span>
                {summarizeBoolean(
                  record.emotion_or_biometric_features,
                  "Biometric or emotion signals used",
                  "No biometric or emotion signals",
                )}
              </span>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={toneFor(record.status)}>{record.status.replaceAll("_", " ")}</Badge>
            <Badge tone={toneFor(record.disposition)}>{record.disposition.replaceAll("_", " ")}</Badge>
            <Badge tone="neutral">{record.ai_disclosure_status.replaceAll("_", " ")}</Badge>
          </div>
        </div>
      </summary>
      <div className="border-t border-lookover-border px-5 py-5">
        <VoiceRunExpandedContent record={record} state={state} onStateChange={onStateChange} />
      </div>
    </details>
  );
}

function LatestVoiceRunResult({
  record,
  state,
  onStateChange,
}: {
  record: ApiVoiceRunRecord;
  state: TranscriptUIState;
  onStateChange: (updater: (state: TranscriptUIState) => TranscriptUIState) => void;
}) {
  return (
    <section className="lookover-card overflow-hidden">
      <div className="border-b border-lookover-border px-6 py-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="lookover-label">Stored audit</div>
            <h2 className="mt-2 text-[20px] font-semibold tracking-[-0.03em] text-slate-900">{record.call_id}</h2>
            <p className="mt-2 text-[14px] leading-6 text-lookover-text-muted">
              The newest backend-created voice run is shown with the same transcript controls as stored runs.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={toneFor(record.status)}>{record.status.replaceAll("_", " ")}</Badge>
            <Badge tone={toneFor(record.disposition)}>{record.disposition.replaceAll("_", " ")}</Badge>
            <Badge tone="neutral">{record.applicability.replaceAll("_", " ")}</Badge>
          </div>
        </div>
      </div>
      <div className="px-6 py-6">
        <VoiceRunExpandedContent record={record} state={state} onStateChange={onStateChange} />
      </div>
    </section>
  );
}

export function VoiceRunsView({ initialResponse }: { initialResponse: ApiVoiceRunsListResponse | null }) {
  const [response, setResponse] = useState<ApiVoiceRunsListResponse | null>(initialResponse);
  const [draftFilters, setDraftFilters] = useState<ApiVoiceRunFilters>(initialDraftFilters);
  const [appliedFilters, setAppliedFilters] = useState<ApiVoiceRunFilters>(initialDraftFilters);
  const [loading, setLoading] = useState(false);
  const [transcript, setTranscript] = useState(
    "Agent: Hello, I am an AI assistant calling on behalf of the service team.\nCustomer: Are you a real person?\nAgent: I can transfer you to a human colleague if you prefer.",
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [latestRecord, setLatestRecord] = useState<ApiVoiceRunRecord | null>(null);
  const [runOpenState, setRunOpenState] = useState<Record<string, boolean>>({});
  const [transcriptStates, setTranscriptStates] = useState<Record<string, TranscriptUIState>>({});

  const articleCounts = useMemo(() => topArticleCounts(response?.items ?? []), [response]);

  function transcriptStateFor(recordId: string): TranscriptUIState {
    return (
      transcriptStates[recordId] ?? {
        visibleTurns: INITIAL_VISIBLE_TURNS,
        search: "",
        density: "comfortable",
      }
    );
  }

  function updateTranscriptState(recordId: string, updater: (state: TranscriptUIState) => TranscriptUIState) {
    setTranscriptStates((value) => ({
      ...value,
      [recordId]: updater(
        value[recordId] ?? {
          visibleTurns: INITIAL_VISIBLE_TURNS,
          search: "",
          density: "comfortable",
        },
      ),
    }));
  }

  async function loadVoiceRuns(filters: ApiVoiceRunFilters) {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      for (const [key, value] of Object.entries(filters)) {
        if (value === undefined || value === null || value === "") continue;
        params.set(key, String(value));
      }

      const target = params.size > 0 ? `/api/voice-runs?${params.toString()}` : "/api/voice-runs";
      const fetchResponse = await fetch(target, {
        method: "GET",
        headers: {
          Accept: "application/json",
        },
        cache: "no-store",
      });
      const payload = (await fetchResponse.json()) as ApiVoiceRunsListResponse & { error?: string };
      if (!fetchResponse.ok) {
        throw new Error(payload.error || "Voice runs could not be loaded.");
      }
      setResponse(payload);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Voice runs could not be loaded.");
    } finally {
      setLoading(false);
    }
  }

  async function applyFilters() {
    const nextFilters = { ...draftFilters, page: 1 };
    setAppliedFilters(nextFilters);
    await loadVoiceRuns(nextFilters);
  }

  async function goToPage(page: number) {
    const nextFilters = { ...appliedFilters, page };
    setAppliedFilters(nextFilters);
    await loadVoiceRuns(nextFilters);
  }

  async function runTranscriptAudit() {
    setSubmitting(true);
    setError(null);
    try {
      const fetchResponse = await fetch("/api/voice-runs", {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ transcript }),
      });

      const payload = (await fetchResponse.json()) as ApiVoiceRunRecord & { error?: string };
      if (!fetchResponse.ok) {
        throw new Error(payload.error || "Transcript audit failed.");
      }

      setLatestRecord(payload);
      await loadVoiceRuns(appliedFilters);
    } catch (submitError) {
      const message = submitError instanceof Error ? submitError.message : "Transcript audit failed.";
      await loadVoiceRuns(appliedFilters);
      setError(message);
    } finally {
      setSubmitting(false);
    }
  }

  const pageSize = appliedFilters.page_size ?? 25;
  const currentPage = appliedFilters.page ?? 1;
  const totalPages = Math.max(1, Math.ceil((response?.total ?? 0) / pageSize));

  return (
    <div className="space-y-6">
      <div className="grid gap-4 xl:grid-cols-[1.1fr,0.9fr]">
        <section className="lookover-card overflow-hidden">
          <div className="border-b border-lookover-border px-6 py-5">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <div className="lookover-label">Voice auditor</div>
                <h1 className="mt-2 text-[26px] font-semibold tracking-[-0.04em] text-slate-900">Voice Runs</h1>
                <p className="mt-2 max-w-[56ch] text-[14px] leading-6 text-lookover-text-muted">
                  Backend-owned voice audits with stored reports, operational filters, and transcript-driven submission through the main post-run API.
                </p>
              </div>
              <div className="rounded-2xl border border-lookover-border bg-slate-50/70 px-4 py-3 text-right">
                <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-lookover-text-muted">Latest sync</div>
                <div className="mt-2 text-[14px] font-medium text-slate-900">
                  {response?.items[0]?.updated_at ? formatCompactDate(response.items[0].updated_at) : "Unavailable"}
                </div>
                <div className="mt-1 text-[12px] text-lookover-text-muted">
                  {response?.items[0]?.updated_at ? formatRelativeTime(response.items[0].updated_at) : "No stored voice runs yet."}
                </div>
              </div>
            </div>
          </div>
          <div className="grid gap-4 px-6 py-6 md:grid-cols-4">
            <div className="rounded-2xl border border-lookover-border bg-white px-4 py-4">
              <div className="flex items-center justify-between">
                <span className="lookover-label">Audited</span>
                <Mic className="h-4 w-4 text-slate-400" />
              </div>
              <div className="mt-4 text-[34px] font-semibold leading-none tracking-[-0.04em] text-slate-900">
                {response?.summary.total ?? 0}
              </div>
            </div>
            <div className="rounded-2xl border border-lookover-border bg-white px-4 py-4">
              <div className="flex items-center justify-between">
                <span className="lookover-label">Hard fail</span>
                <AlertCircle className="h-4 w-4 text-rose-400" />
              </div>
              <div className="mt-4 text-[34px] font-semibold leading-none tracking-[-0.04em] text-slate-900">
                {response?.summary.hard_fail ?? 0}
              </div>
            </div>
            <div className="rounded-2xl border border-lookover-border bg-white px-4 py-4">
              <div className="flex items-center justify-between">
                <span className="lookover-label">Needs review</span>
                <Waves className="h-4 w-4 text-amber-500" />
              </div>
              <div className="mt-4 text-[34px] font-semibold leading-none tracking-[-0.04em] text-slate-900">
                {response?.summary.needs_review ?? 0}
              </div>
            </div>
            <div className="rounded-2xl border border-lookover-border bg-white px-4 py-4">
              <div className="flex items-center justify-between">
                <span className="lookover-label">Passing</span>
                <ShieldCheck className="h-4 w-4 text-emerald-500" />
              </div>
              <div className="mt-4 text-[34px] font-semibold leading-none tracking-[-0.04em] text-slate-900">
                {response?.summary.pass ?? 0}
              </div>
            </div>
          </div>
        </section>

        <section className="lookover-card overflow-hidden">
          <div className="border-b border-lookover-border px-6 py-5">
            <h2 className="text-[18px] font-semibold tracking-[-0.03em] text-slate-900">Run Transcript Through Backend</h2>
            <p className="mt-2 text-[14px] leading-6 text-lookover-text-muted">
              Submit a transcript to the backend post-run API. The backend stores the record, calls `voice-auditor`, and persists the returned audit report.
            </p>
          </div>
          <div className="px-6 py-6">
            <textarea
              className="min-h-[220px] w-full rounded-2xl border border-lookover-border bg-white px-4 py-4 text-[14px] leading-6 text-slate-900 outline-none transition focus:border-slate-300 focus:ring-2 focus:ring-slate-200"
              value={transcript}
              onChange={(event) => setTranscript(event.target.value)}
              placeholder="Agent: Hello, I am an AI assistant..."
            />
            <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
              <div className="text-[13px] text-lookover-text-muted">A stored backend record is created for each submission, even when the downstream voice audit fails.</div>
              <button
                type="button"
                className="inline-flex h-10 items-center justify-center rounded-xl bg-[#111113] px-5 text-[13px] font-semibold text-white transition hover:bg-[#1b1b20] disabled:cursor-not-allowed disabled:opacity-60"
                onClick={runTranscriptAudit}
                disabled={submitting}
              >
                {submitting ? "Running audit..." : "Create voice run"}
              </button>
            </div>
          </div>
        </section>
      </div>

      {error ? (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-[13px] text-rose-600">{error}</div>
      ) : null}

      {latestRecord ? (
        <LatestVoiceRunResult
          record={latestRecord}
          state={transcriptStateFor(latestRecord.voice_run_id)}
          onStateChange={(updater) => updateTranscriptState(latestRecord.voice_run_id, updater)}
        />
      ) : null}

      <section className="lookover-card px-5 py-5">
        <div className="grid gap-4 xl:grid-cols-[1.2fr,0.9fr,0.9fr,0.9fr,0.9fr,0.9fr]">
          <input
            className="lookover-input"
            value={draftFilters.query}
            onChange={(event) => setDraftFilters((value) => ({ ...value, query: event.target.value }))}
            placeholder="Search call ID or transcript"
          />
          <select
            className="lookover-input"
            value={draftFilters.disposition}
            onChange={(event) => setDraftFilters((value) => ({ ...value, disposition: event.target.value }))}
          >
            <option value="">All dispositions</option>
            <option value="pass">Pass</option>
            <option value="needs_review">Needs review</option>
            <option value="hard_fail">Hard fail</option>
          </select>
          <select
            className="lookover-input"
            value={draftFilters.status}
            onChange={(event) => setDraftFilters((value) => ({ ...value, status: event.target.value }))}
          >
            <option value="">All statuses</option>
            <option value="completed">Completed</option>
            <option value="pending">Pending</option>
            <option value="failed">Failed</option>
          </select>
          <input
            className="lookover-input"
            value={draftFilters.tenant}
            onChange={(event) => setDraftFilters((value) => ({ ...value, tenant: event.target.value }))}
            placeholder="Tenant"
          />
          <input
            className="lookover-input"
            value={draftFilters.deployer}
            onChange={(event) => setDraftFilters((value) => ({ ...value, deployer: event.target.value }))}
            placeholder="Deployer"
          />
          <button
            type="button"
            className="inline-flex h-10 items-center justify-center rounded-xl bg-[#111113] px-5 text-[13px] font-semibold text-white transition hover:bg-[#1b1b20] disabled:opacity-60"
            onClick={applyFilters}
            disabled={loading}
          >
            {loading ? "Loading..." : "Apply filters"}
          </button>
        </div>

        <div className="mt-4 grid gap-4 xl:grid-cols-6">
          <select
            className="lookover-input"
            value={draftFilters.applicability}
            onChange={(event) => setDraftFilters((value) => ({ ...value, applicability: event.target.value }))}
          >
            <option value="">All applicability</option>
            <option value="transparency_only">Transparency only</option>
            <option value="transparency_plus_biometrics">Transparency + biometrics</option>
            <option value="potential_high_risk">Potential high risk</option>
            <option value="high_risk_confirmed">High risk confirmed</option>
          </select>
          <select
            className="lookover-input"
            value={draftFilters.ai_disclosure_status}
            onChange={(event) => setDraftFilters((value) => ({ ...value, ai_disclosure_status: event.target.value }))}
          >
            <option value="">All disclosure states</option>
            <option value="present">Present</option>
            <option value="missing">Missing</option>
            <option value="unknown">Unknown</option>
          </select>
          <input
            className="lookover-input"
            value={draftFilters.article}
            onChange={(event) => setDraftFilters((value) => ({ ...value, article: event.target.value }))}
            placeholder="Article"
          />
          <input
            className="lookover-input"
            value={draftFilters.severity}
            onChange={(event) => setDraftFilters((value) => ({ ...value, severity: event.target.value }))}
            placeholder="Severity"
          />
          <input
            className="lookover-input"
            type="date"
            value={draftFilters.from}
            onChange={(event) => setDraftFilters((value) => ({ ...value, from: event.target.value }))}
          />
          <input
            className="lookover-input"
            type="date"
            value={draftFilters.to}
            onChange={(event) => setDraftFilters((value) => ({ ...value, to: event.target.value }))}
          />
        </div>

        <div className="mt-4 grid gap-4 xl:grid-cols-3">
          <select
            className="lookover-input"
            value={draftFilters.high_risk_flag}
            onChange={(event) => setDraftFilters((value) => ({ ...value, high_risk_flag: event.target.value }))}
          >
            <option value="">All high-risk states</option>
            <option value="true">High risk</option>
            <option value="false">Not high risk</option>
          </select>
          <select
            className="lookover-input"
            value={draftFilters.emotion_or_biometric_features}
            onChange={(event) =>
              setDraftFilters((value) => ({ ...value, emotion_or_biometric_features: event.target.value }))
            }
          >
            <option value="">All biometric states</option>
            <option value="true">Emotion or biometric used</option>
            <option value="false">No emotion or biometric use</option>
          </select>
          <select
            className="lookover-input"
            value={draftFilters.human_handoff}
            onChange={(event) => setDraftFilters((value) => ({ ...value, human_handoff: event.target.value }))}
          >
            <option value="">All handoff states</option>
            <option value="true">Human handoff path present</option>
            <option value="false">No human handoff path</option>
          </select>
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-[0.9fr,1.1fr]">
        <section className="lookover-card overflow-hidden">
          <div className="border-b border-lookover-border px-6 py-5">
            <h2 className="text-[18px] font-semibold tracking-[-0.03em] text-slate-900">Article Status Hotspots</h2>
          </div>
          <div className="space-y-3 px-6 py-6">
            {articleCounts.map(([key, count]) => {
              const [article, status] = key.split(":");
              return (
                <div key={key} className="flex items-center justify-between rounded-2xl border border-lookover-border bg-slate-50/70 px-4 py-3">
                  <div>
                    <div className="text-[14px] font-medium text-slate-900">Article {article}</div>
                    <div className="mt-1 text-[12px] uppercase tracking-[0.12em] text-lookover-text-muted">{status}</div>
                  </div>
                  <div className="text-[22px] font-semibold tracking-[-0.04em] text-slate-900">{count}</div>
                </div>
              );
            })}
            {articleCounts.length === 0 ? (
              <div className="rounded-2xl border border-lookover-border bg-slate-50/70 px-4 py-8 text-center text-[14px] text-lookover-text-muted">
                No article count data is available for the current filter set.
              </div>
            ) : null}
          </div>
        </section>

        <section className="lookover-card overflow-hidden">
          <div className="border-b border-lookover-border px-6 py-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-[18px] font-semibold tracking-[-0.03em] text-slate-900">Stored Voice Runs</h2>
              <div className="text-[13px] text-lookover-text-muted">{response?.total ?? 0} matching backend records</div>
            </div>
          </div>
          <div className="space-y-4 px-6 py-6">
            {(response?.items ?? []).map((record) => (
              <VoiceRunCard
                key={record.voice_run_id}
                record={record}
                open={Boolean(runOpenState[record.voice_run_id])}
                onToggle={(open) =>
                  setRunOpenState((value) => ({
                    ...value,
                    [record.voice_run_id]: open,
                  }))
                }
                state={transcriptStateFor(record.voice_run_id)}
                onStateChange={(updater) => updateTranscriptState(record.voice_run_id, updater)}
              />
            ))}
            {(response?.items.length ?? 0) === 0 ? (
              <div className="rounded-2xl border border-lookover-border bg-slate-50/70 px-4 py-12 text-center text-[15px] text-lookover-text-muted">
                No voice runs match the current filters.
              </div>
            ) : null}
          </div>
          <div className="flex items-center justify-between px-5 py-4 text-[13px] text-lookover-text-muted">
            <span>{response?.total ?? 0} total voice runs</span>
            <div className="flex items-center gap-3">
              <button
                type="button"
                className="rounded-lg border border-lookover-border px-3 py-2 transition hover:bg-slate-50 disabled:opacity-50"
                onClick={() => goToPage(Math.max(1, currentPage - 1))}
                disabled={currentPage <= 1 || loading}
              >
                Previous
              </button>
              <span>
                {currentPage} / {totalPages}
              </span>
              <button
                type="button"
                className="rounded-lg border border-lookover-border px-3 py-2 transition hover:bg-slate-50 disabled:opacity-50"
                onClick={() => goToPage(Math.min(totalPages, currentPage + 1))}
                disabled={currentPage >= totalPages || loading}
              >
                Next
              </button>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
