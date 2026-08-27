import React from "react";

export class SectionErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return React.createElement(
        "section",
        {
          className:
            "rounded-[1.75rem] border border-red-400/25 bg-red-500/10 p-5 text-sm text-red-100",
        },
        this.props.fallbackMessage,
      );
    }

    return this.props.children;
  }
}
