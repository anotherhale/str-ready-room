// The single server-state boundary for the SPA.
//
// One hand-written hook owns loading/error/data for the operational views.
// Components read from here and never call the API client directly for shared
// state, so there is exactly one place that talks to the backend.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { api, ApiError } from "../services/apiClient";
import type {
  Briefing,
  CalendarAgenda,
  CalendarStatus,
  Category,
  Dashboard,
  EmailSummary,
  MailboxStatus,
  Principal,
  RecurrenceOverview,
  Settings,
  Task,
} from "../types";

export interface AppData {
  dashboard: Dashboard | null;
  briefing: Briefing | null;
  tasks: Task[];
  settings: Settings | null;
  categories: Category[];
  recurrence: RecurrenceOverview | null;
  principal: Principal | null;
  // Optional integrations.  ``null`` means "not loaded"; ``available: false``
  // means the integration is configured off or unreachable (never an error).
  calendar: CalendarAgenda | null;
  calendarStatus: CalendarStatus | null;
  mailbox: EmailSummary[] | null;
  mailboxStatus: MailboxStatus | null;
}

export interface TaskFilters {
  status: string;
  category: string;
  search: string;
}

const EMPTY: AppData = {
  dashboard: null,
  briefing: null,
  tasks: [],
  settings: null,
  categories: [],
  recurrence: null,
  principal: null,
  calendar: null,
  calendarStatus: null,
  mailbox: null,
  mailboxStatus: null,
};

export interface UseAppData {
  data: AppData;
  loading: boolean;
  error: string | null;
  filters: TaskFilters;
  setFilters: (next: Partial<TaskFilters>) => void;
  refresh: () => Promise<void>;
  refreshTasks: () => Promise<void>;
  refreshCalendar: () => Promise<void>;
  refreshMailbox: () => Promise<void>;
  mutate: <T>(action: () => Promise<T>) => Promise<T>;
}

export function useAppData(initialFilters?: Partial<TaskFilters>): UseAppData {
  const [data, setData] = useState<AppData>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFiltersState] = useState<TaskFilters>({
    status: initialFilters?.status ?? "all",
    category: initialFilters?.category ?? "all",
    search: initialFilters?.search ?? "",
  });

  const filtersRef = useRef(filters);
  filtersRef.current = filters;

  const loadTasks = useCallback(async () => {
    const f = filtersRef.current;
    const result = await api.listTasks({
      status: f.status === "all" ? "all" : f.status,
      category: f.category === "all" ? undefined : f.category,
      search: f.search || undefined,
    });
    return result.items;
  }, []);

  // Best-effort integration load.  Each call is individually guarded so one
  // failing integration cannot blank the other, and neither can fail the whole
  // dashboard refresh.
  const loadIntegrations = useCallback(async () => {
    const [calendar, calendarStatus, mailbox, mailboxStatus] = await Promise.all([
      api.getCalendarAgenda().catch(() => null),
      api.getCalendarStatus().catch(() => null),
      api.listMessages().catch(() => null),
      api.getMailboxStatus().catch(() => null),
    ]);
    return { calendar, calendarStatus, mailbox, mailboxStatus };
  }, []);

  const refreshCalendar = useCallback(async () => {
    try {
      const [calendar, calendarStatus] = await Promise.all([
        api.getCalendarAgenda(),
        api.getCalendarStatus(),
      ]);
      setData((prev) => ({ ...prev, calendar, calendarStatus }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load calendar.");
    }
  }, []);

  const refreshMailbox = useCallback(async () => {
    try {
      const [mailbox, mailboxStatus] = await Promise.all([
        api.listMessages(),
        api.getMailboxStatus(),
      ]);
      setData((prev) => ({ ...prev, mailbox, mailboxStatus }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load mailbox.");
    }
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [principal, dashboard, briefing, settings, categories, recurrence, tasks] =
        await Promise.all([
          api.me(),
          api.getDashboard(),
          api.getBriefing(),
          api.getSettings(),
          api.listCategories(),
          api.getRecurrenceOverview(),
          loadTasks(),
        ]);
      // Integrations load best-effort: a disabled or unreachable provider must
      // never block the operational views.  Their status carries the reason.
      const integrations = await loadIntegrations();
      setData({ principal, dashboard, briefing, settings, categories, recurrence, tasks, ...integrations });
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong loading data.");
    } finally {
      setLoading(false);
    }
  }, [loadTasks]);

  const refreshTasks = useCallback(async () => {
    try {
      const tasks = await loadTasks();
      setData((prev) => ({ ...prev, tasks }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load tasks.");
    }
  }, [loadTasks]);

  // Reload the task list whenever the filters change.
  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    void refreshTasks();
  }, [filters, refreshTasks]);

  const setFilters = useCallback((next: Partial<TaskFilters>) => {
    setFiltersState((prev) => ({ ...prev, ...next }));
  }, []);

  // Run a mutation then re-derive all server state so counts and sections stay
  // consistent (urgency is computed on read by the backend).
  const mutate = useCallback(
    async <T,>(action: () => Promise<T>): Promise<T> => {
      const result = await action();
      await refresh();
      return result;
    },
    [refresh],
  );

  return useMemo(
    () => ({
      data,
      loading,
      error,
      filters,
      setFilters,
      refresh,
      refreshTasks,
      refreshCalendar,
      refreshMailbox,
      mutate,
    }),
    [data, loading, error, filters, setFilters, refresh, refreshTasks, refreshCalendar, refreshMailbox, mutate],
  );
}
