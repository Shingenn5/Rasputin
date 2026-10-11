export function useEventConnection(context) {
  const {
    eventReconnectTimerRef,
    eventFallbackTimerRef,
    eventGenerationRef,
    eventSourceRef,
    mountedRef,
    setEventConnectionStatus,
    eventRetryAttemptRef,
    loadTasks,
    queryClient,
    setTasks,
    selectedTaskIdRef,
    setTaskDetails,
    loadTaskDetails,
    setApprovals,
    setMemoryReview,
    setTelegramConfig,
    setGlobalStatus,
  } = context;

  function clearEventTimers() {
    if (eventReconnectTimerRef.current) {
      window.clearTimeout(eventReconnectTimerRef.current);
      eventReconnectTimerRef.current = null;
    }
    if (eventFallbackTimerRef.current) {
      window.clearInterval(eventFallbackTimerRef.current);
      eventFallbackTimerRef.current = null;
    }
  }

  function disconnectEvents(status = "disconnected") {
    eventGenerationRef.current += 1;
    clearEventTimers();
    eventSourceRef.current?.close();
    eventSourceRef.current = null;
    if (mountedRef.current) setEventConnectionStatus(status);
  }

  function scheduleEventReconnect(generation) {
    if (!mountedRef.current || generation !== eventGenerationRef.current || eventReconnectTimerRef.current) return;
    const attempt = eventRetryAttemptRef.current;
    const delay = Math.min(30000, 1000 * (2 ** attempt));
    eventRetryAttemptRef.current = Math.min(attempt + 1, 5);
    eventReconnectTimerRef.current = window.setTimeout(() => {
      eventReconnectTimerRef.current = null;
      if (mountedRef.current && generation === eventGenerationRef.current) connectEvents();
    }, delay);
  }

  function startEventFallbackRefresh(generation) {
    if (eventFallbackTimerRef.current) return;
    const refresh = () => {
      if (!mountedRef.current || generation !== eventGenerationRef.current) return;
      loadTasks().catch(() => {});
    };
    refresh();
    eventFallbackTimerRef.current = window.setInterval(refresh, 3000);
  }

  function connectEvents() {
    if (!mountedRef.current) return;
    disconnectEvents("connecting");
    const generation = eventGenerationRef.current;
    const source = new EventSource("/api/events");
    eventSourceRef.current = source;
    source.onopen = () => {
      if (!mountedRef.current || generation !== eventGenerationRef.current) return;
      eventRetryAttemptRef.current = 0;
      if (eventFallbackTimerRef.current) {
        window.clearInterval(eventFallbackTimerRef.current);
        eventFallbackTimerRef.current = null;
      }
      setEventConnectionStatus("connected");
    };
    source.onerror = () => {
      if (!mountedRef.current || generation !== eventGenerationRef.current) return;
      source.close();
      if (eventSourceRef.current === source) eventSourceRef.current = null;
      setEventConnectionStatus("degraded");
      startEventFallbackRefresh(generation);
      scheduleEventReconnect(generation);
    };
    source.onmessage = (message) => {
      if (!mountedRef.current || generation !== eventGenerationRef.current) return;
      try {
        const data = JSON.parse(message.data);
        if (data.tasks) {
          queryClient.setQueryData(["tasks"], data.tasks);
          setTasks(data.tasks);
        }
        if (data.task) {
          setTasks((current) => [data.task, ...current.filter((task) => task.id !== data.task.id)]);
          queryClient.setQueryData(["tasks"], (current = []) => [data.task, ...current.filter((task) => task.id !== data.task.id)]);
          if (selectedTaskIdRef.current === data.task.id) {
            // Merge the streamed snapshot straight into the open drawer so
            // tokens/steps paint live; only refetch the full detail (events,
            // approvals, children) once the task leaves the running state.
            setTaskDetails((current) =>
              current?.task?.id === data.task.id ? { ...current, task: { ...current.task, ...data.task } } : current,
            );
            if (!["running", "queued"].includes(data.task.status)) {
              loadTaskDetails(selectedTaskIdRef.current, { silent: true });
            }
          } else if (selectedTaskIdRef.current) {
            loadTaskDetails(selectedTaskIdRef.current, { silent: true });
          }
          if (["done", "error", "cancelled"].includes(data.task.status)) {
            queryClient.invalidateQueries({ queryKey: ["inbox"] });
          }
        }
        if (data.approvals) setApprovals(data.approvals);
        if (data.memoryReview) setMemoryReview(data.memoryReview);
        if (data.telegram) setTelegramConfig(data.telegram);
      } catch {
        setGlobalStatus("Live update failed.");
      }
    };
  }

  return { disconnectEvents, connectEvents };
}
