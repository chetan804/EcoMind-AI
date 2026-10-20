import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { createTask, fetchCollectors, fetchTask, fetchTasks, taskAction, type TaskAction, type TaskFilters } from '../api/collection-api';

export const useTasks = (f: TaskFilters) => useQuery({ queryKey: ['collection', 'list', f], queryFn: ({ signal }) => fetchTasks(f, signal) });
export const useTask = (id: string) => useQuery({ queryKey: ['collection', 'task', id], queryFn: ({ signal }) => fetchTask(id, signal) });

/** Active collectors, for the assignment pick-list. Needs `users:read`, so only ask when allowed. */
export const useCollectors = (enabled: boolean) =>
  useQuery({ queryKey: ['collection', 'collectors'], queryFn: ({ signal }) => fetchCollectors(signal), enabled, select: (p) => p.items });

/** Task changes also affect analytics, notifications, the report's status and the fleet's load. */
const AFFECTED = [['collection'], ['analytics'], ['notifications'], ['waste-reports'], ['fleet'], ['rewards']];

export function useCreateTask() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: createTask,
    onSuccess: () => Promise.all(AFFECTED.map((queryKey) => client.invalidateQueries({ queryKey }))),
  });
}

export function useTaskAction(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (v: { action: TaskAction; body?: Record<string, unknown> }) => taskAction(id, v.action, v.body),
    onSuccess: () => Promise.all(AFFECTED.map((queryKey) => client.invalidateQueries({ queryKey }))),
  });
}
