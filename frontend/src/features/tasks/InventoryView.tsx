import { TaskCard } from "../../components/TaskCard/TaskCard";
import type { Task } from "../../types";

export interface TaskFiltersState {
  status: string;
  category: string;
  search: string;
}

export interface InventoryViewProps {
  tasks: Task[];
  total: number;
  categories: string[];
  filters: TaskFiltersState;
  onFiltersChange: (next: Partial<TaskFiltersState>) => void;
  onEdit: (task: Task) => void;
  onComplete: (task: Task) => void;
  onReopen: (task: Task) => void;
  onDelete: (task: Task) => void;
  onNew: () => void;
  busy: boolean;
}

export function InventoryView({
  tasks,
  total,
  categories,
  filters,
  onFiltersChange,
  onEdit,
  onComplete,
  onReopen,
  onDelete,
  onNew,
  busy,
}: InventoryViewProps) {
  const active = tasks.filter((t) => t.status === "open");
  const completed = tasks.filter((t) => t.status === "completed");

  return (
    <div>
      <div className="panel-head">
        <span className="panel-title">
          Complete inventory<span className="count">({total})</span>
        </span>
        <button className="btn primary" onClick={onNew}>
          + New
        </button>
      </div>

      <div className="filters">
        <div className="field grow">
          <label htmlFor="inv-search">Search</label>
          <input
            id="inv-search"
            type="text"
            placeholder="Title or notes…"
            value={filters.search}
            onChange={(e) => onFiltersChange({ search: e.target.value })}
          />
        </div>
        <div className="field">
          <label htmlFor="inv-status">Status</label>
          <select
            id="inv-status"
            value={filters.status}
            onChange={(e) => onFiltersChange({ status: e.target.value })}
          >
            <option value="all">All</option>
            <option value="open">Open</option>
            <option value="completed">Completed</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="inv-category">Category</label>
          <select
            id="inv-category"
            value={filters.category}
            onChange={(e) => onFiltersChange({ category: e.target.value })}
          >
            <option value="all">All</option>
            {categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
      </div>

      <section className="panel">
        <div className="panel-head">
          <span className="panel-title">
            Active<span className="count">({active.length})</span>
          </span>
        </div>
        {active.length === 0 ? (
          <p className="panel-empty">No active responsibilities match these filters.</p>
        ) : (
          active.map((task) => (
            <TaskCard
              key={task.id}
              task={task}
              onEdit={onEdit}
              onComplete={onComplete}
              onReopen={onReopen}
              onDelete={onDelete}
              busy={busy}
            />
          ))
        )}
      </section>

      {completed.length > 0 && (
        <section className="panel">
          <div className="panel-head">
            <span className="panel-title">
              Completed<span className="count">({completed.length})</span>
            </span>
          </div>
          {completed.map((task) => (
            <TaskCard
              key={task.id}
              task={task}
              onEdit={onEdit}
              onComplete={onComplete}
              onReopen={onReopen}
              onDelete={onDelete}
              busy={busy}
            />
          ))}
        </section>
      )}
    </div>
  );
}
