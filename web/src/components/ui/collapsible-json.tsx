"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { cn, safeText } from "@/lib/lookover-format";

function parseJsonLikeString(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return value;
  if (
    (trimmed.startsWith("{") && trimmed.endsWith("}")) ||
    (trimmed.startsWith("[") && trimmed.endsWith("]"))
  ) {
    try {
      return JSON.parse(trimmed) as unknown;
    } catch {
      return value;
    }
  }
  return value;
}

function normalizeValue(value: unknown) {
  if (typeof value === "string") {
    return parseJsonLikeString(value);
  }
  return value;
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function primitiveTone(value: unknown) {
  if (typeof value === "string") return "text-emerald-700";
  if (typeof value === "number") return "text-sky-700";
  if (typeof value === "boolean") return "text-violet-700";
  if (value === null) return "text-slate-400";
  return "text-slate-600";
}

function primitiveLabel(value: unknown) {
  if (typeof value === "string") return `"${value}"`;
  if (value === null) return "null";
  if (value === undefined) return "undefined";
  return safeText(value);
}

function branchSummary(value: unknown, label?: string) {
  if (Array.isArray(value)) {
    return `${label ?? "Array"} · ${value.length} item${value.length === 1 ? "" : "s"}`;
  }
  if (isPlainObject(value)) {
    const size = Object.keys(value).length;
    return `${label ?? "Object"} · ${size} key${size === 1 ? "" : "s"}`;
  }
  return label ?? "Value";
}

function JsonNode({
  label,
  value,
  depth = 0,
  defaultExpanded = false,
}: {
  label?: string;
  value: unknown;
  depth?: number;
  defaultExpanded?: boolean;
}) {
  const normalized = normalizeValue(value);
  const [open, setOpen] = useState(defaultExpanded);

  if (Array.isArray(normalized)) {
    return (
      <div className={cn(depth > 0 ? "ml-4 border-l border-slate-200 pl-3" : "")}>
        <button
          type="button"
          className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left transition hover:bg-white/70"
          onClick={() => setOpen((current) => !current)}
        >
          <ChevronDown className={cn("h-4 w-4 text-slate-400 transition", open ? "rotate-0" : "-rotate-90")} />
          <span className="font-medium text-slate-900">{branchSummary(normalized, label)}</span>
        </button>
        {open ? (
          <div className="mt-1 space-y-1">
            {normalized.length === 0 ? (
              <div className="ml-6 px-2 py-1 text-[13px] text-lookover-text-muted">[]</div>
            ) : (
              normalized.map((item, index) => (
                <JsonNode
                  key={`${label ?? "array"}-${index}`}
                  label={`[${index}]`}
                  value={item}
                  depth={depth + 1}
                />
              ))
            )}
          </div>
        ) : null}
      </div>
    );
  }

  if (isPlainObject(normalized)) {
    const entries = Object.entries(normalized);
    return (
      <div className={cn(depth > 0 ? "ml-4 border-l border-slate-200 pl-3" : "")}>
        <button
          type="button"
          className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left transition hover:bg-white/70"
          onClick={() => setOpen((current) => !current)}
        >
          <ChevronDown className={cn("h-4 w-4 text-slate-400 transition", open ? "rotate-0" : "-rotate-90")} />
          <span className="font-medium text-slate-900">{branchSummary(normalized, label)}</span>
        </button>
        {open ? (
          <div className="mt-1 space-y-1">
            {entries.length === 0 ? (
              <div className="ml-6 px-2 py-1 text-[13px] text-lookover-text-muted">{"{}"}</div>
            ) : (
              entries.map(([key, item]) => (
                <JsonNode key={key} label={key} value={item} depth={depth + 1} />
              ))
            )}
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <div className={cn("flex items-start gap-3 rounded-lg px-2 py-1.5", depth > 0 ? "ml-4" : "")}>
      {label ? <span className="min-w-[112px] text-slate-500">{label}</span> : null}
      <span className={cn("min-w-0 flex-1 whitespace-pre-wrap break-words", primitiveTone(normalized))}>
        {primitiveLabel(normalized)}
      </span>
    </div>
  );
}

export function CollapsibleJson({
  value,
  label,
  className,
  defaultExpanded = false,
}: {
  value: unknown;
  label?: string;
  className?: string;
  defaultExpanded?: boolean;
}) {
  return (
    <div
      className={cn(
        "min-w-0 rounded-[14px] border border-lookover-border bg-slate-50/80 px-3 py-3 font-mono text-[13px] leading-6 text-slate-700",
        className,
      )}
    >
      <JsonNode value={value} label={label} defaultExpanded={defaultExpanded} />
    </div>
  );
}
