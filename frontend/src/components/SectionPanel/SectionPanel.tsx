import type { ReactNode } from "react";

export interface SectionPanelProps {
  title: string;
  count?: number;
  action?: ReactNode;
  emptyText?: string;
  children?: ReactNode;
}

export function SectionPanel({ title, count, action, emptyText, children }: SectionPanelProps) {
  const hasChildren = Array.isArray(children) ? children.length > 0 : Boolean(children);
  return (
    <section className="panel">
      <div className="panel-head">
        <span className="panel-title">
          {title}
          {count !== undefined && <span className="count">({count})</span>}
        </span>
        {action}
      </div>
      {hasChildren ? children : <p className="panel-empty">{emptyText ?? "Nothing here."}</p>}
    </section>
  );
}
