import { Component, type ErrorInfo, type ReactNode } from 'react'
import { AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // In a real production deployment, this is where you'd send the error
    // to a logging service. For now, at least it's visible in the console
    // instead of silently showing a blank screen.
    console.error('Uncaught error caught by ErrorBoundary:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-background px-4 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-destructive/15 text-destructive">
            <AlertTriangle className="h-7 w-7" />
          </div>
          <div>
            <h1 className="text-xl font-semibold">Something went wrong</h1>
            <p className="mt-1 max-w-sm text-sm text-muted-foreground">
              An unexpected error occurred. Reloading usually fixes it — if it keeps happening, please let us know
              what you were doing.
            </p>
          </div>
          {this.state.error && (
            <pre className="max-w-lg overflow-x-auto rounded-md bg-secondary/50 p-3 text-left text-xs text-muted-foreground">
              {this.state.error.message}
            </pre>
          )}
          <Button onClick={() => window.location.reload()}>Reload the page</Button>
        </div>
      )
    }

    return this.props.children
  }
}
