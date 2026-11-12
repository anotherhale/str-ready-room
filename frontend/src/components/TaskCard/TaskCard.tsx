import { describeDue, formatShortDate } from "../../lib/dates";
import { PRIORITY_LABELS, describeRecurrence } from "../../lib/recurrence";
import type { Task } from "../../types";
import { WEEKDAY_NAMES } from "../../lib/dates";
import { UrgencyBadge } from "../UrgencyBadge/UrgencyBadge";

export interface TaskCardProps {
  task: Task;
  onEdit?: (task: Task) => void;
  onComplete?: (task: Task) => void;
  onReopen?: (task: Task) => void;
  onDelete?: (task: Task) => void;
  busy?: boolean;
}

export function TaskCard({ task, onEdit, onComplete, onReopen, onDelete, busy }: TaskCardProps) {
  const completed = task.status === "completed";
  return (
    <article className={`task-card urgency-${task.urgency} ${completed ? "completed" : ""}`}>
      <div className="task-main">
        <p className="task-title">{task.title}</p>
        <div className="task-meta">
          <UrgencyBadge urgency={task.urgency} />
          <span className="pill">{task.category}</span>
          <span className={`pill priority-${task.priority}`}>{PRIORITY_LABELS[task.priority]}</span>
          {task.due_date && <span>{formatShortDate(task.due_date)}</span>}
          {!completed && <span>{describeDue(task.days_until_due)}</span>}
          {task.recurrence && (
            <span title={`Occurrence ${task.occurrence_number}`}>
              ↻{" "}
              {describeRecurrence(
                task.recurrence.frequency,
                task.recurrence.interval,
                task.recurrence.day_of_week,
                WEEKDAY_NAMES,
              )}
            </span>
          )}
          {task.series_id && <span>Occurrence {task.occurrence_number}</span>}
        </div>
        {task.description && <p className="task-desc">{task.description}</p>}
      </div>
      <div className="task-actions">
        {!completed && onComplete && (
          <button className="btn btn-sm complete" disabled={busy} onClick={() => onComplete(task)}>
            Complete
          </button>
        )}
        {completed && onReopen && (
          <button className="btn btn-sm" disabled={busy} onClick={() => onReopen(task)}>
            Reopen
          </button>
        )}
        {onEdit && (
          <button className="btn btn-sm ghost" disabled={busy} onClick={() => onEdit(task)}>
            Edit
          </button>
        )}
        {onDelete && (
          <button className="btn btn-sm danger ghost" disabled={busy} onClick={() => onDelete(task)}>
            Delete
          </button>
        )}
      </div>
    </article>
  );
}
