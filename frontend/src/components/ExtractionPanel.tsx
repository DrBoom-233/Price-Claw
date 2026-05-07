import type { Dispatch, SetStateAction } from "react";
import type { FilePlans, SchemaSummary, TaskMode } from "../types/app";

interface ExtractionPanelProps {
  selectedFiles: File[];
  uploadedFilenames: string[];
  isUploading: boolean;
  isRunning: boolean;
  requestText: string;
  schemas: SchemaSummary[];
  selectedSchemaId: string;
  isLoadingSchemas: boolean;
  schemaLoadError: string;
  useLlm: boolean;
  taskMode: TaskMode;
  filePlans: FilePlans;
  canStart: boolean;
  uploadStatus: string;
  onSelectedFilesChange: (files: File[]) => void;
  onUpload: () => void;
  onTaskModeChange: (mode: TaskMode) => void;
  onSelectedSchemaIdChange: (schemaId: string) => void;
  onLoadSchemas: () => void;
  onUseLlmChange: (useLlm: boolean) => void;
  onFilePlansChange: Dispatch<SetStateAction<FilePlans>>;
  onRequestTextChange: (text: string) => void;
  onStart: () => void;
}

export function ExtractionPanel({
  selectedFiles,
  uploadedFilenames,
  isUploading,
  isRunning,
  requestText,
  schemas,
  selectedSchemaId,
  isLoadingSchemas,
  schemaLoadError,
  useLlm,
  taskMode,
  filePlans,
  canStart,
  uploadStatus,
  onSelectedFilesChange,
  onUpload,
  onTaskModeChange,
  onSelectedSchemaIdChange,
  onLoadSchemas,
  onUseLlmChange,
  onFilePlansChange,
  onRequestTextChange,
  onStart
}: ExtractionPanelProps) {
  return (
    <section className="card">
      <h2>Extraction</h2>
      <div className="actions">
        <input
          type="file"
          accept=".mhtml"
          multiple
          onChange={(event) => onSelectedFilesChange(Array.from(event.target.files || []))}
          disabled={isRunning || isUploading}
        />
        <button onClick={onUpload} disabled={isRunning || isUploading || selectedFiles.length === 0}>
          {isUploading ? "Uploading..." : "1. Upload File"}
        </button>
      </div>
      <div className="form-row">
        <label htmlFor="taskMode">Task Mode</label>
        <div className="actions">
          <select
            id="taskMode"
            value={taskMode}
            onChange={(event) => onTaskModeChange(event.target.value as TaskMode)}
            disabled={isRunning || uploadedFilenames.length === 0}
          >
            <option value="uniform">Uniform (All files share configuration)</option>
            <option value="per_file">Per-File Override (Select schema/LLM for each file)</option>
          </select>
        </div>
      </div>

      {taskMode === "uniform" ? (
        <>
          <div className="form-row">
            <label htmlFor="schemaSelect">Saved Schema</label>
            <div className="actions">
              <select
                id="schemaSelect"
                value={selectedSchemaId}
                onChange={(event) => onSelectedSchemaIdChange(event.target.value)}
                disabled={isRunning || isLoadingSchemas || useLlm || schemas.length === 0}
              >
                <option value="">Auto (reuse by domain)</option>
                {schemas.map((schema) => (
                  <option key={schema.id} value={schema.id}>
                    {schema.schemaName} ({schema.domain})
                  </option>
                ))}
              </select>
              <button onClick={onLoadSchemas} disabled={isRunning || isLoadingSchemas}>
                {isLoadingSchemas ? "Refreshing..." : "Refresh Schemas"}
              </button>
            </div>
          </div>
          <div className="form-row">
            <label>
              <input
                type="checkbox"
                checked={useLlm}
                onChange={(event) => onUseLlmChange(event.target.checked)}
                disabled={isRunning}
              />
              Use LLM to generate schema for this run
            </label>
          </div>
        </>
      ) : (
        <div className="form-row table-container">
          <label>Per-File Configurations</label>
          <table className="data-table">
            <thead>
              <tr>
                <th>Filename</th>
                <th>Schema / LLM Override</th>
              </tr>
            </thead>
            <tbody>
              {uploadedFilenames.map((filename) => {
                const plan = filePlans[filename] || { schemaId: "", useLlm: false };
                return (
                  <tr key={filename}>
                    <td>{filename}</td>
                    <td>
                      <div className="actions">
                        <select
                          value={plan.schemaId}
                          onChange={(event) =>
                            onFilePlansChange((prev) => ({
                              ...prev,
                              [filename]: { ...(prev[filename] || { schemaId: "", useLlm: false }), schemaId: event.target.value }
                            }))
                          }
                          disabled={isRunning || plan.useLlm}
                        >
                          <option value="">Auto (reuse by domain)</option>
                          {schemas.map((schema) => (
                            <option key={schema.id} value={schema.id}>
                              {schema.schemaName} ({schema.domain})
                            </option>
                          ))}
                        </select>
                        <label style={{ margin: 0, display: "flex", alignItems: "center", gap: "4px" }}>
                          <input
                            type="checkbox"
                            checked={plan.useLlm}
                            onChange={(event) =>
                              onFilePlansChange((prev) => ({
                                ...prev,
                                [filename]: { ...(prev[filename] || { schemaId: "", useLlm: false }), useLlm: event.target.checked }
                              }))
                            }
                            disabled={isRunning}
                          />
                          Force LLM
                        </label>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {schemaLoadError ? <div className="status status-error">{schemaLoadError}</div> : null}
      {uploadStatus ? <div className="status status-success">{uploadStatus}</div> : null}
      <div className="form-row">
        <label htmlFor="request">Extraction Request</label>
        <textarea
          id="request"
          rows={3}
          value={requestText}
          onChange={(event) => onRequestTextChange(event.target.value)}
          disabled={isRunning}
        />
      </div>
      <button onClick={onStart} disabled={!canStart}>
        2. Start Extraction Task
      </button>
    </section>
  );
}
