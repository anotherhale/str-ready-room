import { SectionPanel } from "../../components/SectionPanel/SectionPanel";
import { TaskCard } from "../../components/TaskCard/TaskCard";
import { formatLongDate, localGreeting } from "../../lib/dates";
import type { Dashboard as DashboardData, Task } from "../../types";

export interface DashboardViewProps {
  dashboard: DashboardData;
  onEdit: (task: Task) => void;
  onComplete: (task: Task) => void;
  onReopen: (task: Task) => void;
  onOpenBriefing: () => void;
  onOpenInventory: () => void;
  busy: boolean;
}

export function DashboardView({
  dashboard,
  onEdit,
  onComplete,
  onReopen,
  onOpenBriefing,
  onOpenInventory,
  busy,
}: DashboardViewProps) {
  const { counts } = dashboard;
  return (
    <div>
      <div className="greeting">
        <h1>
          {localGreeting()}, {dashboard.greeting_name}.
        </h1>
        <span className="date">
          {formatLongDate(dashboard.today)} · {dashboard.timezone}
        </span>
      </div>
      <p className="readiness">{dashboard.readiness_summary}</p>

      <div className="counts" role="group" aria-label="Operational counts">
        <div className="count-tile critical">
          <div className="n">{counts.overdue}</div>
          <div className="l">Overdue</div>
        </div>
        <div className="count-tile warning">
          <div className="n">{counts.due}</div>
          <div className="l">Due today</div>
        </div>
        <div className="count-tile warning">
          <div className="n">{counts.watch}</div>
          <div className="l">Watch</div>
        </div>
        <div className="count-tile">
          <div className="n">{counts.horizon}</div>
          <div className="l">Horizon</div>
        </div>
        <div className="count-tile ok">
          <div className="n">{counts.completed_this_week}</div>
          <div className="l">Done this week</div>
        </div>
      </div>

      <SectionPanel
        title="Today"
        count={dashboard.today_tasks.length}
        emptyText="Nothing due today. You are ahead of the jet."
      >
        {dashboard.today_tasks.map((task) => (
          <TaskCard
            key={task.id}
            task={task}
            onEdit={onEdit}
            onComplete={onComplete}
            onReopen={onReopen}
            busy={busy}
          />
        ))}
      </SectionPanel>

      <SectionPanel
        title={dashboard.watch_label}
        count={dashboard.watch_tasks.length}
        emptyText="No responsibilities inside the warning window."
      >
        {dashboard.watch_tasks.map((task) => (
          <TaskCard
            key={task.id}
            task={task}
            onEdit={onEdit}
            onComplete={onComplete}
            onReopen={onReopen}
            busy={busy}
          />
        ))}
      </SectionPanel>

      <SectionPanel
        title="On the Horizon"
        count={dashboard.horizon_tasks.length}
        emptyText="Nothing on the horizon."
      >
        {dashboard.horizon_tasks.map((task) => (
          <TaskCard
            key={task.id}
            task={task}
            onEdit={onEdit}
            onComplete={onComplete}
            onReopen={onReopen}
            busy={busy}
          />
        ))}
      </SectionPanel>

      <div className="panel no-print" style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        <button className="btn primary" onClick={onOpenBriefing}>
          View daily briefing
        </button>
        <button className="btn" onClick={onOpenInventory}>
          Open full inventory
        </button>
      </div>
    </div>
  );
}
