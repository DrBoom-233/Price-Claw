import { JsonViewer } from "./JsonViewer";
import type { InspectionData, InspectionExtraction, InspectionSchema, InspectionTab } from "../types/app";

interface MongoInspectorModalProps {
  inspectionData: InspectionData;
  selectedInspectionTab: InspectionTab;
  selectedExtractionId: string;
  selectedInspectionSchemaId: string;
  selectedExtraction?: InspectionExtraction;
  selectedInspectionSchema?: InspectionSchema;
  isLoadingInspection: boolean;
  inspectionError: string;
  onClose: () => void;
  onTabChange: (tab: InspectionTab) => void;
  onRefresh: () => void;
  onSelectedExtractionIdChange: (id: string) => void;
  onSelectedInspectionSchemaIdChange: (id: string) => void;
  onExportSelectedPriceJson: () => void;
  onExportSelectedSchemaJson: () => void;
}

export function MongoInspectorModal({
  inspectionData,
  selectedInspectionTab,
  selectedExtractionId,
  selectedInspectionSchemaId,
  selectedExtraction,
  selectedInspectionSchema,
  isLoadingInspection,
  inspectionError,
  onClose,
  onTabChange,
  onRefresh,
  onSelectedExtractionIdChange,
  onSelectedInspectionSchemaIdChange,
  onExportSelectedPriceJson,
  onExportSelectedSchemaJson
}: MongoInspectorModalProps) {
  return (
    <div className="modal-backdrop" role="presentation">
      <section className="modal-card inspection-modal" role="dialog" aria-modal="true" aria-labelledby="inspection-title">
        <div className="modal-header">
          <div>
            <h2 id="inspection-title">MongoDB Inspector</h2>
            <p className="subtitle">Stored price extraction JSON and schema documents</p>
          </div>
          <button className="button-secondary" onClick={onClose}>
            Close
          </button>
        </div>

        <div className="tab-bar" role="tablist" aria-label="MongoDB data views">
          <button
            className={selectedInspectionTab === "prices" ? "tab-button tab-button-active" : "tab-button"}
            onClick={() => onTabChange("prices")}
            type="button"
          >
            Price JSON
          </button>
          <button
            className={selectedInspectionTab === "schemas" ? "tab-button tab-button-active" : "tab-button"}
            onClick={() => onTabChange("schemas")}
            type="button"
          >
            Schemas
          </button>
          <button className="button-secondary" onClick={onRefresh} disabled={isLoadingInspection} type="button">
            {isLoadingInspection ? "Refreshing..." : "Refresh"}
          </button>
        </div>

        {inspectionError ? <div className="status status-error">{inspectionError}</div> : null}

        {selectedInspectionTab === "prices" ? (
          <div className="inspection-grid">
            <aside className="inspection-list" aria-label="Extraction results">
              {inspectionData.extractions.length === 0 ? (
                <div className="empty-state">No extraction results in MongoDB.</div>
              ) : (
                inspectionData.extractions.map((item) => (
                  <button
                    key={item.id}
                    className={item.id === selectedExtractionId ? "list-row list-row-active" : "list-row"}
                    onClick={() => onSelectedExtractionIdChange(item.id)}
                    type="button"
                  >
                    <span>{item.fileName || "unknown file"}</span>
                    <small>{item.createdAt || item.taskId || item.id}</small>
                  </button>
                ))
              )}
            </aside>
            <div className="json-detail">
              <div className="json-detail-header">
                <div>
                  <strong>Selected Price Info</strong>
                  <span>{selectedExtraction?.fileName || selectedExtraction?.taskId || "No price info selected"}</span>
                </div>
                <button
                  className="export-button"
                  onClick={onExportSelectedPriceJson}
                  disabled={!selectedExtraction}
                  type="button"
                >
                  Export This Price JSON
                </button>
              </div>
              <JsonViewer value={selectedExtraction?.result || selectedExtraction || {}} />
            </div>
          </div>
        ) : (
          <div className="inspection-grid">
            <aside className="inspection-list" aria-label="Schemas">
              {inspectionData.schemas.length === 0 ? (
                <div className="empty-state">No saved schemas in MongoDB.</div>
              ) : (
                inspectionData.schemas.map((item) => (
                  <button
                    key={item.id}
                    className={item.id === selectedInspectionSchemaId ? "list-row list-row-active" : "list-row"}
                    onClick={() => onSelectedInspectionSchemaIdChange(item.id)}
                    type="button"
                  >
                    <span>{item.schemaName || "unnamed schema"}</span>
                    <small>{item.domain || item.id}</small>
                  </button>
                ))
              )}
            </aside>
            <div className="json-detail">
              <div className="json-detail-header">
                <div>
                  <strong>Selected Schema</strong>
                  <span>
                    {selectedInspectionSchema
                      ? `${selectedInspectionSchema.schemaName || "unnamed schema"} (${selectedInspectionSchema.domain || "unknown domain"})`
                      : "No schema selected"}
                  </span>
                </div>
                <button
                  className="export-button"
                  onClick={onExportSelectedSchemaJson}
                  disabled={!selectedInspectionSchema}
                  type="button"
                >
                  Export This Schema
                </button>
              </div>
              <JsonViewer value={selectedInspectionSchema || {}} />
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
