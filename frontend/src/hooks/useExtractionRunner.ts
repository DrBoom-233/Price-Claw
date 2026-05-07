import { useCallback, useMemo, useState } from "react";
import type { ApiClient } from "../api/client";
import { createWsUrl } from "../api/client";
import { DEFAULT_REQUEST } from "../config/providers";
import type { FilePlans, LogType, TaskMode } from "../types/app";

type AppendLog = (text: string, type?: LogType) => void;

interface UseExtractionRunnerArgs {
  api: ApiClient;
  apiBaseUrl: string;
  settingsConfigured: boolean;
  selectedSchemaId: string;
  appendLog: AppendLog;
  onRunClosed: () => void;
}

interface PipelineMessage {
  type: string;
  level?: string;
  message?: string;
  step?: string;
  data?: unknown;
}

export function useExtractionRunner({
  api,
  apiBaseUrl,
  settingsConfigured,
  selectedSchemaId,
  appendLog,
  onRunClosed
}: UseExtractionRunnerArgs) {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploadedFilenames, setUploadedFilenames] = useState<string[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [requestText, setRequestText] = useState(DEFAULT_REQUEST);
  const [useLlm, setUseLlm] = useState(false);
  const [taskMode, setTaskMode] = useState<TaskMode>("uniform");
  const [filePlans, setFilePlans] = useState<FilePlans>({});

  const canStart = settingsConfigured && uploadedFilenames.length > 0 && !isRunning;
  const uploadStatus = uploadedFilenames.length > 0 ? `Uploaded: ${uploadedFilenames.join(", ")}` : "";

  const handleUpload = useCallback(async () => {
    if (selectedFiles.length === 0) {
      appendLog("Please select at least one MHTML file first.", "error");
      return;
    }

    setIsUploading(true);
    appendLog(`Uploading ${selectedFiles.length} file(s) ...`);
    try {
      const formData = new FormData();
      selectedFiles.forEach((file) => {
        formData.append("file", file);
      });
      const data = await api.uploadFile(formData);
      const incoming = Array.isArray(data.filenames) ? data.filenames : data.filename ? [data.filename] : [];

      setUploadedFilenames(incoming);

      setFilePlans((prevPlans) => {
        const nextPlans = { ...prevPlans };
        incoming.forEach((filename) => {
          if (!nextPlans[filename]) {
            nextPlans[filename] = { schemaId: "", useLlm: false };
          }
        });
        return nextPlans;
      });

      appendLog(`Upload successful: ${incoming.join(", ")}`, "success");
    } catch (error) {
      appendLog(`Upload failed: ${error}`, "error");
    } finally {
      setIsUploading(false);
    }
  }, [api, appendLog, selectedFiles]);

  const handleStart = useCallback(() => {
    if (!canStart) {
      return;
    }

    setIsRunning(true);
    appendLog("Connecting to backend websocket ...", "ws");
    const wsUrl = createWsUrl(apiBaseUrl, "/api/ws");
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      appendLog("WebSocket connected, starting pipeline.", "success");
      ws.send(
        JSON.stringify({
          action: "start",
          filenames: uploadedFilenames,
          extraction_request: requestText.trim() || DEFAULT_REQUEST,
          schema_id: selectedSchemaId || null,
          task_mode: taskMode,
          use_llm: useLlm,
          file_plans: Object.entries(filePlans)
            .filter(([filename]) => uploadedFilenames.includes(filename))
            .map(([filename, plan]) => ({
              filename,
              schema_id: plan.schemaId || null,
              use_llm: plan.useLlm
            }))
        })
      );
    };

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data as string) as PipelineMessage;
      switch (message.type) {
        case "log": {
          const level = message.level || "info";
          const type = level === "error" ? "error" : level === "warning" ? "ws" : "info";
          appendLog(message.message || "", type);
          break;
        }
        case "progress":
          appendLog(`[Executing] ${message.step}`, "ws");
          break;
        case "step_done":
          appendLog(`[Completed] ${message.step}`, "success");
          if (message.data) {
            appendLog(`Returned data: ${JSON.stringify(message.data)}`, "info");
          }
          break;
        case "result":
          appendLog(`[Final Result] ${JSON.stringify(message.data)}`, "success");
          break;
        case "error":
          appendLog(`[Step Error] ${message.message}`, "error");
          break;
        case "fatal":
          appendLog(`[Fatal Error] ${message.message}`, "error");
          break;
        case "complete":
          appendLog("Extraction completed.", "success");
          break;
        default:
          appendLog(`Unhandled message: ${JSON.stringify(message)}`, "ws");
      }
    };

    ws.onerror = () => {
      appendLog("WebSocket error.", "error");
    };

    ws.onclose = () => {
      appendLog("WebSocket closed.", "ws");
      setIsRunning(false);
      onRunClosed();
    };
  }, [
    apiBaseUrl,
    appendLog,
    canStart,
    filePlans,
    onRunClosed,
    requestText,
    selectedSchemaId,
    taskMode,
    uploadedFilenames,
    useLlm
  ]);

  return useMemo(
    () => ({
      selectedFiles,
      setSelectedFiles,
      uploadedFilenames,
      isUploading,
      isRunning,
      requestText,
      setRequestText,
      useLlm,
      setUseLlm,
      taskMode,
      setTaskMode,
      filePlans,
      setFilePlans,
      canStart,
      uploadStatus,
      handleUpload,
      handleStart
    }),
    [
      canStart,
      filePlans,
      handleStart,
      handleUpload,
      isRunning,
      isUploading,
      requestText,
      selectedFiles,
      taskMode,
      uploadStatus,
      uploadedFilenames,
      useLlm
    ]
  );
}
