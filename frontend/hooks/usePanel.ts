"use client";

import { useEffect, useState } from "react";

interface PanelState<T> {
  data: T | null;
  loading: boolean;
  error: boolean;
}

// Fetch a side-panel's data once on mount. `fetcher` is one of the
// api-client getters (getAppointments / getReports / getHistory / getQueue).
export function usePanel<T>(fetcher: () => Promise<T>): PanelState<T> {
  const [state, setState] = useState<PanelState<T>>({
    data: null,
    loading: true,
    error: false,
  });

  useEffect(() => {
    let active = true;
    fetcher()
      .then((data) => {
        if (active) setState({ data, loading: false, error: false });
      })
      .catch(() => {
        if (active) setState({ data: null, loading: false, error: true });
      });
    return () => {
      active = false;
    };
    // fetcher getters are stable module-level functions.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return state;
}
