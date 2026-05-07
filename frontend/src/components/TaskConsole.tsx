import type { LogLine } from "../types/app";

interface TaskConsoleProps {
  logs: LogLine[];
}

export function TaskConsole({ logs }: TaskConsoleProps) {
  return (
    <section className="card console-card">
      <h2>Task Console</h2>
      <div className="console">
        {logs.map((line, index) => (
          <div key={`${line.text}-${index}`} className={`log-${line.type}`}>
            {line.text}
          </div>
        ))}
      </div>
    </section>
  );
}
