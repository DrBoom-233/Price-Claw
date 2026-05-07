import type { ReactNode } from "react";
import { formatJson } from "../utils/jsonExport";

interface JsonViewerProps {
  value: unknown;
}

interface JsonPart {
  text: string;
  className: string;
}

function renderHighlightedJson(value: unknown): ReactNode[] {
  const json = formatJson(value);
  const tokenPattern = /"(?:\\.|[^"\\])*"|true|false|null|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/g;
  const parts: JsonPart[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = tokenPattern.exec(json)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ text: json.slice(lastIndex, match.index), className: "" });
    }

    const token = match[0];
    const afterToken = json.slice(tokenPattern.lastIndex).match(/^\s*:/);
    let className = "";
    if (/^"(?:\\.|[^"\\])*"$/.test(token)) {
      className = afterToken ? "json-key" : "json-string";
    } else if (/^-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?$/.test(token)) {
      className = "json-number";
    } else if (token === "true" || token === "false") {
      className = "json-boolean";
    } else if (token === "null") {
      className = "json-null";
    }

    parts.push({ text: token, className });
    lastIndex = tokenPattern.lastIndex;
  }

  if (lastIndex < json.length) {
    parts.push({ text: json.slice(lastIndex), className: "" });
  }

  return parts.map((part, index) =>
    part.className ? (
      <span key={`${part.text}-${index}`} className={part.className}>
        {part.text}
      </span>
    ) : (
      part.text
    )
  );
}

export function JsonViewer({ value }: JsonViewerProps) {
  return (
    <div className="json-panel">
      <pre>{renderHighlightedJson(value)}</pre>
    </div>
  );
}
