import { useCallback, useEffect, useMemo, useState } from "react";
import { createApiClient, resolveApiBaseUrl } from "./api/client";
import { ExtractionPanel } from "./components/ExtractionPanel";
import { HelpModal } from "./components/HelpModal";
import { MongoInspectorCard } from "./components/MongoInspectorCard";
import { MongoInspectorModal } from "./components/MongoInspectorModal";
import { SettingsCard } from "./components/SettingsCard";
import { SettingsModal } from "./components/SettingsModal";
import { TaskConsole } from "./components/TaskConsole";
import { DEFAULT_API_BASE_URL } from "./config/providers";
import { useExtractionRunner } from "./hooks/useExtractionRunner";
import { useInspection } from "./hooks/useInspection";
import { useSchemas } from "./hooks/useSchemas";
import { useSettings } from "./hooks/useSettings";
import type { LogLine, LogType } from "./types/app";

function App() {
  const [apiBaseUrl, setApiBaseUrl] = useState(DEFAULT_API_BASE_URL);
  const [logs, setLogs] = useState<LogLine[]>([{ type: "info", text: "System ready." }]);
  const [isHelpModalOpen, setIsHelpModalOpen] = useState(false);

  const api = useMemo(() => createApiClient(apiBaseUrl), [apiBaseUrl]);

  const appendLog = useCallback((text: string, type: LogType = "info") => {
    const time = new Date().toLocaleTimeString();
    setLogs((prev) => [...prev, { type, text: `[${time}] ${text}` }]);
  }, []);

  const schemas = useSchemas(api);
  const inspection = useInspection(api);
  const settings = useSettings(api, appendLog, schemas.loadSchemas);
  const extraction = useExtractionRunner({
    api,
    apiBaseUrl,
    settingsConfigured: settings.settingsConfigured,
    selectedSchemaId: schemas.selectedSchemaId,
    appendLog,
    onRunClosed: () => {
      if (inspection.isInspectionOpen) {
        void inspection.loadInspectionData();
      }
    }
  });

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      const resolvedApiBaseUrl = await resolveApiBaseUrl();
      if (cancelled) {
        return;
      }
      setApiBaseUrl(resolvedApiBaseUrl);
    }

    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="layout">
      <div className="layout-left-col">
        <section className="card">
          <h1>Price Claw Desktop</h1>
          <a
            href="#"
            onClick={(event) => {
              event.preventDefault();
              setIsHelpModalOpen(true);
            }}
            className="help-link"
          >
            Don't know how to use it? Click here.
          </a>
          <p className="subtitle">Electron + React frontend, FastAPI backend</p>
          <div className="api-base">Backend: {apiBaseUrl}</div>
        </section>

        <SettingsCard
          isRunning={extraction.isRunning}
          hasCheckedSettings={settings.hasCheckedSettings}
          settingsStatus={settings.settingsStatus}
          settingsStatusType={settings.settingsStatusType}
          onOpenSettings={settings.openSettings}
        />

        <ExtractionPanel
          selectedFiles={extraction.selectedFiles}
          uploadedFilenames={extraction.uploadedFilenames}
          isUploading={extraction.isUploading}
          isRunning={extraction.isRunning}
          requestText={extraction.requestText}
          schemas={schemas.schemas}
          selectedSchemaId={schemas.selectedSchemaId}
          isLoadingSchemas={schemas.isLoadingSchemas}
          schemaLoadError={schemas.schemaLoadError}
          useLlm={extraction.useLlm}
          taskMode={extraction.taskMode}
          filePlans={extraction.filePlans}
          canStart={extraction.canStart}
          uploadStatus={extraction.uploadStatus}
          onSelectedFilesChange={extraction.setSelectedFiles}
          onUpload={extraction.handleUpload}
          onTaskModeChange={extraction.setTaskMode}
          onSelectedSchemaIdChange={schemas.setSelectedSchemaId}
          onLoadSchemas={schemas.loadSchemas}
          onUseLlmChange={extraction.setUseLlm}
          onFilePlansChange={extraction.setFilePlans}
          onRequestTextChange={extraction.setRequestText}
          onStart={extraction.handleStart}
        />
      </div>

      <div className="layout-right-col">
        <MongoInspectorCard
          isLoadingInspection={inspection.isLoadingInspection}
          inspectionError={inspection.inspectionError}
          onOpenInspection={inspection.openInspection}
        />

        <TaskConsole logs={logs} />
      </div>

      {settings.isSettingsOpen ? (
        <SettingsModal
          configuredProvider={settings.configuredProvider}
          provider={settings.provider}
          apiKey={settings.apiKey}
          model={settings.model}
          reasoningModel={settings.reasoningModel}
          baseUrl={settings.baseUrl}
          settingsConfigured={settings.settingsConfigured}
          isRunning={extraction.isRunning}
          isSavingSettings={settings.isSavingSettings}
          isLoadingModels={settings.isLoadingModels}
          availableModels={settings.availableModels}
          modelsError={settings.modelsError}
          onProviderChange={settings.handleProviderChange}
          onApiKeyChange={settings.setApiKey}
          onModelChange={settings.setModel}
          onReasoningModelChange={settings.setReasoningModel}
          onBaseUrlChange={settings.setBaseUrl}
          onSave={settings.handleSaveSettings}
          onClose={() => settings.setIsSettingsOpen(false)}
        />
      ) : null}

      {inspection.isInspectionOpen ? (
        <MongoInspectorModal
          inspectionData={inspection.inspectionData}
          selectedInspectionTab={inspection.selectedInspectionTab}
          selectedExtractionId={inspection.selectedExtractionId}
          selectedInspectionSchemaId={inspection.selectedInspectionSchemaId}
          selectedExtraction={inspection.selectedExtraction}
          selectedInspectionSchema={inspection.selectedInspectionSchema}
          isLoadingInspection={inspection.isLoadingInspection}
          inspectionError={inspection.inspectionError}
          onClose={() => inspection.setIsInspectionOpen(false)}
          onTabChange={inspection.setSelectedInspectionTab}
          onRefresh={inspection.loadInspectionData}
          onSelectedExtractionIdChange={inspection.setSelectedExtractionId}
          onSelectedInspectionSchemaIdChange={inspection.setSelectedInspectionSchemaId}
          onExportSelectedPriceJson={inspection.exportSelectedPriceJson}
          onExportSelectedSchemaJson={inspection.exportSelectedSchemaJson}
        />
      ) : null}

      {isHelpModalOpen ? <HelpModal onClose={() => setIsHelpModalOpen(false)} /> : null}
    </div>
  );
}

export default App;
