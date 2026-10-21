import { Component, type ReactNode } from 'react'
import { APP_NAME } from './appName'

interface ErrorBoundaryProps {
  children: ReactNode
}

interface ErrorBoundaryState {
  failed: boolean
}

// Shows a message instead of a blank page when anything inside throws while
// rendering, e.g. a response with a shape the api types didn't predict
// (getJson casts responses without checking them). React logs the error to
// the console itself. Failed requests aren't rendering errors: useApi already
// turns those into messages.
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { failed: false }

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { failed: true }
  }

  // Back and Forward still change the address while the message shows, so
  // they try the app again for the page they lead to
  componentDidMount() {
    window.addEventListener('popstate', this.tryAgain)
  }

  componentWillUnmount() {
    window.removeEventListener('popstate', this.tryAgain)
  }

  tryAgain = () => {
    if (this.state.failed) this.setState({ failed: false })
  }

  render() {
    if (!this.state.failed) return this.props.children

    // Plain links, not the app's own: the app is what failed
    return (
      <>
        <header className="site-header">
          <h1>
            <a href="/">{APP_NAME}</a>
          </h1>
        </header>
        <main>
          <p role="alert" className="error">
            Something went wrong showing this page.{' '}
            <button type="button" onClick={() => window.location.reload()}>
              Reload
            </button>
          </p>
          <p>
            Or start again from <a href="/">All Leagues</a>
          </p>
        </main>
      </>
    )
  }
}
