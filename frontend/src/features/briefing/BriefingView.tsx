import { formatLongDate, formatShortDate } from "../../lib/dates";
import { UrgencyBadge } from "../../components/UrgencyBadge/UrgencyBadge";
import type { Briefing as BriefingData, Task } from "../../types";

function BriefingList({ tasks }: { tasks: Task[] }) {
  if (tasks.length === 0) return <p className="panel-empty">None.</p>;
  return (
    <ul>
      {tasks.map((task) => (
        <li key={task.id}>
          <strong>{task.title}</strong>{" "}
          <span className="no-print">
            <UrgencyBadge urgency={task.urgency} />
          </span>{" "}
          <span style={{ color: "var(--text-faint)", fontSize: 12 }}>
            {task.category}
            {task.due_date ? ` · ${formatShortDate(task.due_date)}` : ""}
            {task.series_id ? ` · occurrence ${task.occurrence_number}` : ""}
          </span>
        </li>
      ))}
    </ul>
  );
}

export function BriefingView({ briefing }: { briefing: BriefingData }) {
  return (
    <div className="briefing">
      <div className="briefing-head">
        <h1>READY ROOM — Daily Briefing</h1>
        <p style={{ margin: "6px 0 0", color: "var(--text-dim)" }}>
          {formatLongDate(briefing.date)} · {briefing.timezone}
        </p>
      </div>

      <p className="look-ahead">{briefing.look_ahead}</p>

      <section>
        <h2>Overdue</h2>
        <BriefingList tasks={briefing.overdue} />
      </section>

      <section>
        <h2>Today</h2>
        <BriefingList tasks={briefing.today} />
      </section>

      <section>
        <h2>Upcoming deadlines</h2>
        <BriefingList tasks={briefing.upcoming} />
      </section>

      <section>
        <h2>Recurring obligations (short horizon)</h2>
        <BriefingList tasks={briefing.recurring_obligations} />
      </section>

      <div className="no-print" style={{ marginTop: 20 }}>
        <button className="btn primary" onClick={() => window.print()}>
          Print briefing
        </button>
      </div>
    </div>
  );
}
