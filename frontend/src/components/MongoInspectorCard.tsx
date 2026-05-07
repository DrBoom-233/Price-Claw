interface MongoInspectorCardProps {
  isLoadingInspection: boolean;
  inspectionError: string;
  onOpenInspection: () => void;
}

export function MongoInspectorCard({ isLoadingInspection, inspectionError, onOpenInspection }: MongoInspectorCardProps) {
  return (
    <section className="card">
      <h2>MongoDB Data</h2>
      <p className="subtitle">Inspect stored extraction JSON and saved schemas.</p>
      <div className="actions inspection-entry-actions">
        <button onClick={onOpenInspection} disabled={isLoadingInspection}>
          {isLoadingInspection ? "Loading..." : "Inspect Data"}
        </button>
      </div>
      {inspectionError ? <div className="status status-error">{inspectionError}</div> : null}
    </section>
  );
}
