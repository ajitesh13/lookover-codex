"use client";

import { useMemo, useState } from "react";
import { ApiSpan, ApiTraceDetail, ShareMode } from "@/lib/lookover-api";
import {
  cn,
  countFindingsByCategory,
  deriveRootIntent,
  formatCompactDate,
  formatDuration,
  getRiskLabel,
  getToneFromStatus,
  safeText,
  titleCase,
} from "@/lib/lookover-format";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/ui/page-header";
import { SectionCard } from "@/components/ui/section-card";
import shared from "@/components/ui/primitives.module.css";
import styles from "./traces.module.css";

type TraceTreeNode = {
  span: ApiSpan;
  children: TraceTreeNode[];
};

function buildTree(spans: ApiSpan[]) {
  const byId = new Map<string, TraceTreeNode>();
  const roots: TraceTreeNode[] = [];

  spans.forEach((span) => byId.set(span.span_id, { span, children: [] }));

  byId.forEach((node) => {
    if (node.span.parent_span_id && byId.has(node.span.parent_span_id)) {
      byId.get(node.span.parent_span_id)?.children.push(node);
    } else {
      roots.push(node);
    }
  });

  return roots;
}

function findingCountsForSpan(detail: ApiTraceDetail, spanId: string) {
  return detail.findings
    .filter((finding) => finding.span_id === spanId)
    .reduce(
      (accumulator, finding) => {
        const tone = getToneFromStatus(finding.status);
        if (tone === "danger") accumulator.violations += 1;
        else if (tone === "warning") accumulator.gaps += 1;
        else accumulator.covered += 1;
        return accumulator;
      },
      { violations: 0, gaps: 0, covered: 0 },
    );
}

function ShareActions({ traceId }: { traceId: string }) {
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<string>("");
  const [loadingMode, setLoadingMode] = useState<ShareMode | null>(null);

  async function createShare(mode: ShareMode) {
    setLoadingMode(mode);
    setStatus("");

    try {
      const response = await fetch(`/api/traces/${traceId}/share`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode }),
      });
      const payload = (await response.json()) as { url?: string; error?: string };
      if (!response.ok || !payload.url) {
        setStatus(payload.error || "Share link could not be created.");
        return;
      }
      await navigator.clipboard.writeText(payload.url);
      setStatus(`Share link copied for ${mode === "audit_log_only" ? "trace only" : "trace + compliance"}.`);
      setOpen(false);
    } catch {
      setStatus("Share link could not be created.");
    } finally {
      setLoadingMode(null);
    }
  }

  return (
    <div className={styles.shareWrap}>
      <button
        type="button"
        className={`${shared.button} ${shared.buttonPrimary}`}
        onClick={() => setOpen((value) => !value)}
      >
        Share run
      </button>
      {open ? (
        <div className={styles.shareMenu}>
          <button
            type="button"
            className={styles.shareOption}
            onClick={() => createShare("audit_log_plus_evaluation")}
            disabled={loadingMode !== null}
          >
            <strong>With compliance</strong>
            <span className={styles.shareStatus}>Includes violations, gaps, and covered controls.</span>
          </button>
          <button
            type="button"
            className={styles.shareOption}
            onClick={() => createShare("audit_log_only")}
            disabled={loadingMode !== null}
          >
            <strong>Without compliance</strong>
            <span className={styles.shareStatus}>Only the trace tree, span detail, and raw evidence.</span>
          </button>
        </div>
      ) : null}
      {status ? <div className={styles.shareStatus}>{status}</div> : null}
    </div>
  );
}

function TreeNode({
  node,
  selectedSpanId,
  onSelect,
  detail,
  showCompliance,
}: {
  node: TraceTreeNode;
  selectedSpanId: string;
  onSelect: (spanId: string) => void;
  detail: ApiTraceDetail;
  showCompliance: boolean;
}) {
  const counts = findingCountsForSpan(detail, node.span.span_id);
  const selected = selectedSpanId === node.span.span_id;

  return (
    <div className={styles.treeRoot}>
      <div className={cn(styles.treeNode, selected && styles.treeNodeSelected)}>
        <button type="button" className={styles.treeButton} onClick={() => onSelect(node.span.span_id)}>
          <div className={styles.treeNodeLeft}>
            <span className={styles.treeIcon}>{node.span.event_type.slice(0, 2).toUpperCase()}</span>
            <span className={styles.treeText}>
              <span className={styles.treeName}>{node.span.name}</span>
              <span className={styles.treeMeta}>
                {titleCase(node.span.event_type)} · {formatDuration(node.span.start_time, node.span.end_time)}
              </span>
            </span>
          </div>
          <span className={styles.treeBadges}>
            <Badge tone={getToneFromStatus(node.span.status) === "danger" ? "danger" : getToneFromStatus(node.span.status) === "warning" ? "warning" : "neutral"}>
              {node.span.status}
            </Badge>
            {showCompliance && counts.violations > 0 ? <Badge tone="danger">{counts.violations} violations</Badge> : null}
            {showCompliance && counts.gaps > 0 ? <Badge tone="warning">{counts.gaps} gaps</Badge> : null}
            {showCompliance && counts.covered > 0 ? <Badge tone="success">{counts.covered} covered</Badge> : null}
          </span>
        </button>
      </div>
      {node.children.length > 0 ? (
        <div className={styles.treeChildren}>
          {node.children.map((child) => (
            <TreeNode
              key={child.span.span_id}
              node={child}
              selectedSpanId={selectedSpanId}
              onSelect={onSelect}
              detail={detail}
              showCompliance={showCompliance}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function TraceWorkspace({
  detail,
  readOnly = false,
  shareMode = "audit_log_plus_evaluation",
}: {
  detail: ApiTraceDetail;
  readOnly?: boolean;
  shareMode?: ShareMode;
}) {
  const tree = useMemo(() => buildTree(detail.spans), [detail.spans]);
  const [selectedSpanId, setSelectedSpanId] = useState(detail.spans[0]?.span_id ?? "");
  const [showFindings, setShowFindings] = useState(true);
  const selectedSpan = detail.spans.find((span) => span.span_id === selectedSpanId) ?? detail.spans[0];
  const rootIntent = deriveRootIntent(detail.trace, detail.spans);
  const counts = countFindingsByCategory(detail.findings);
  const showCompliance = shareMode !== "audit_log_only";

  const evidenceItems = detail.evidence.filter((item) => item.span_id === selectedSpan?.span_id);
  const spanFindings = detail.findings.filter((finding) => finding.span_id === selectedSpan?.span_id);

  return (
    <div className={shared.section}>
      <PageHeader
        eyebrow={readOnly ? "Shared run" : "Trace workspace"}
        title={rootIntent}
        subtitle="Inspect the trace tree, select any span for audit evidence, and review grouped findings with simple, non-technical language."
        actions={
          readOnly ? (
            <Badge tone="neutral">Read only</Badge>
          ) : (
            <ShareActions traceId={detail.trace.trace_id} />
          )
        }
      />

      {readOnly ? (
        <div className={styles.readonlyBanner}>
          Shared review link loaded. Interactive inspection is allowed, but edits and approvals stay disabled.
        </div>
      ) : null}

      <SectionCard className={styles.summaryCard}>
        <div className={styles.summaryTop}>
          <div className={styles.summaryTitle}>
            <h2>{detail.trace.trace_id}</h2>
            <p>{detail.trace.agent_id} · {detail.trace.framework || "runtime trace"} · {detail.trace.model_provider || "local reviewer flow"}</p>
          </div>
          <div className={styles.summaryMeta}>
            <Badge tone={getToneFromStatus(detail.trace.status) === "danger" ? "danger" : getToneFromStatus(detail.trace.status) === "warning" ? "warning" : "neutral"}>
              {detail.trace.status}
            </Badge>
            <Badge tone={detail.trace.overall_risk_score >= 80 ? "danger" : detail.trace.overall_risk_score >= 50 ? "warning" : "neutral"}>
              {getRiskLabel(detail.trace.overall_risk_score)} risk
            </Badge>
          </div>
        </div>
        <div className={styles.summaryStats}>
          <div className={styles.stat}>
            <div className={styles.statLabel}>Agent</div>
            <div className={styles.statValue}>{detail.trace.agent_id || "—"}</div>
          </div>
          <div className={styles.stat}>
            <div className={styles.statLabel}>Started</div>
            <div className={styles.statValue}>{formatCompactDate(detail.trace.created_at)}</div>
          </div>
          <div className={styles.stat}>
            <div className={styles.statLabel}>Duration</div>
            <div className={styles.statValue}>{formatDuration(detail.trace.created_at, detail.trace.updated_at)}</div>
          </div>
          <div className={styles.stat}>
            <div className={styles.statLabel}>Spans</div>
            <div className={styles.statValue}>{detail.spans.length}</div>
          </div>
        </div>
      </SectionCard>

      {showCompliance ? (
        <SectionCard className={styles.findingGroup}>
          <div className={styles.findingGroupHeader}>
            <div className={styles.panelTitle}>
              <h3>Grouped findings</h3>
              <p>Violations, gaps, and covered controls stay tied to the observed trace evidence.</p>
            </div>
            <button
              type="button"
              className={`${shared.button} ${shared.buttonSecondary}`}
              onClick={() => setShowFindings((value) => !value)}
            >
              {showFindings ? "Collapse" : "Expand"}
            </button>
          </div>
          {showFindings ? (
            <div className={styles.findingsGrid}>
              {[
                { title: "Violations", items: detail.findings.filter((item) => getToneFromStatus(item.status) === "danger"), tone: "danger" as const, count: counts.violations },
                { title: "Gaps", items: detail.findings.filter((item) => getToneFromStatus(item.status) === "warning"), tone: "warning" as const, count: counts.gaps },
                { title: "Covered", items: detail.findings.filter((item) => getToneFromStatus(item.status) === "neutral"), tone: "success" as const, count: counts.covered },
              ].map((group) => (
                <div key={group.title} className={`${shared.card} ${styles.findingGroup}`}>
                  <div className={styles.findingGroupHeader}>
                    <h3>{group.title}</h3>
                    <Badge tone={group.tone}>{group.count}</Badge>
                  </div>
                  <div className={styles.findingList}>
                    {group.items.length === 0 ? (
                      <div className={styles.findingItem}>
                        <div className={styles.findingBody}>No items in this group for the current trace.</div>
                      </div>
                    ) : (
                      group.items.map((finding) => (
                        <div key={finding.id} className={styles.findingItem}>
                          <div className={styles.findingTitle}>{finding.title}</div>
                          <div className={styles.findingMeta}>
                            {finding.framework} · {finding.control_id} · {finding.span_id || "trace level"}
                          </div>
                          <div className={styles.findingEvidence}>
                            {finding.citation ? <div><strong>Source citation:</strong> {finding.citation}</div> : null}
                            {Object.keys(finding.observed_evidence ?? {}).length ? (
                              <div><strong>Observed evidence:</strong> {safeText(finding.observed_evidence)}</div>
                            ) : null}
                            {finding.reasoning ? <div><strong>Compliance reasoning:</strong> {finding.reasoning}</div> : null}
                            {finding.residual_risk ? <div><strong>Residual risk:</strong> {finding.residual_risk}</div> : null}
                            {finding.remediation ? <div><strong>Remediation:</strong> {finding.remediation}</div> : null}
                          </div>
                          <div className={styles.findingBody}>{finding.reasoning || finding.remediation}</div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : null}
        </SectionCard>
      ) : null}

      <div className={styles.workspace}>
        <SectionCard className={styles.treePanel}>
          <div className={styles.panelHeader}>
            <div className={styles.panelTitle}>
              <h3>Trace tree</h3>
              <p>Walk each span in order and inspect its evidence one decision at a time.</p>
            </div>
          </div>
          {tree.map((node) => (
            <TreeNode
              key={node.span.span_id}
              node={node}
              selectedSpanId={selectedSpanId}
              onSelect={setSelectedSpanId}
              detail={detail}
              showCompliance={showCompliance}
            />
          ))}
        </SectionCard>

        <SectionCard className={styles.detailPanel}>
          <div className={styles.panelHeader}>
            <div className={styles.panelTitle}>
              <h3>{selectedSpan?.name || "Span detail"}</h3>
              <p>{selectedSpan ? `${titleCase(selectedSpan.event_type)} · ${formatDuration(selectedSpan.start_time, selectedSpan.end_time)}` : "Select a span to inspect evidence."}</p>
            </div>
            {selectedSpan ? <Badge tone={getToneFromStatus(selectedSpan.status) === "danger" ? "danger" : getToneFromStatus(selectedSpan.status) === "warning" ? "warning" : "neutral"}>{selectedSpan.status}</Badge> : null}
          </div>

          {selectedSpan ? (
            <div className={styles.detailBody}>
              <div className={styles.detailSection}>
                <h4>Observed payload</h4>
                <div className={styles.detailList}>
                  <code>{JSON.stringify(selectedSpan.payload, null, 2)}</code>
                </div>
              </div>

              <div className={styles.detailSection}>
                <h4>Raw evidence</h4>
                <div className={styles.detailList}>
                  {evidenceItems.length === 0 ? (
                    <div className={shared.tableMeta}>No evidence rows were attached to this span.</div>
                  ) : (
                    evidenceItems.map((item) => (
                      <code key={item.id}>
                        {item.field_name}: {safeText(item.value)}
                      </code>
                    ))
                  )}
                </div>
              </div>

              {showCompliance ? (
                <div className={styles.detailSection}>
                  <h4>Findings tied to this span</h4>
                  <div className={styles.detailList}>
                    {spanFindings.length === 0 ? (
                      <div className={shared.tableMeta}>No findings are attached to this span.</div>
                    ) : (
                      spanFindings.map((finding) => (
                        <code key={finding.id} className={cn(shared.mono)}>
                          [{titleCase(finding.framework)} / {finding.control_id}] {finding.title} ({titleCase(finding.status)})
                        </code>
                      ))
                    )}
                  </div>
                </div>
              ) : null}
            </div>
          ) : (
            <div className={shared.emptyBody}>Select a span from the tree to open the detail panel.</div>
          )}
        </SectionCard>
      </div>
    </div>
  );
}
