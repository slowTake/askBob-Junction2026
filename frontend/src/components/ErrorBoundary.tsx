import { Component, type ReactNode } from "react";

interface Props {
  fallback: (error: unknown) => ReactNode;
  children: ReactNode;
}

interface State {
  failed: boolean;
  error: unknown;
}

/** Keeps a failing viewer from blanking the whole app; the rest of the page stays usable. */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { failed: false, error: null };

  static getDerivedStateFromError(error: unknown): State {
    return { failed: true, error };
  }

  render() {
    return this.state.failed ? this.props.fallback(this.state.error) : this.props.children;
  }
}
