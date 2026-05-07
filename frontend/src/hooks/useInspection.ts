import { useCallback, useMemo, useState } from "react";
import type { ApiClient } from "../api/client";
import type { InspectionData, InspectionTab } from "../types/app";
import { exportJson, safeExportFilename } from "../utils/jsonExport";

export function useInspection(api: ApiClient) {
  const [isInspectionOpen, setIsInspectionOpen] = useState(false);
  const [isLoadingInspection, setIsLoadingInspection] = useState(false);
  const [inspectionError, setInspectionError] = useState("");
  const [inspectionData, setInspectionData] = useState<InspectionData>({ schemas: [], extractions: [] });
  const [selectedInspectionTab, setSelectedInspectionTab] = useState<InspectionTab>("prices");
  const [selectedExtractionId, setSelectedExtractionId] = useState("");
  const [selectedInspectionSchemaId, setSelectedInspectionSchemaId] = useState("");

  const loadInspectionData = useCallback(async () => {
    try {
      setIsLoadingInspection(true);
      setInspectionError("");
      const data = await api.getInspection();
      const nextExtractions = Array.isArray(data.extractions) ? data.extractions : [];
      const nextSchemas = Array.isArray(data.schemas) ? data.schemas : [];
      setInspectionData({ extractions: nextExtractions, schemas: nextSchemas });

      setSelectedExtractionId((current) =>
        nextExtractions.some((item) => item.id === current) ? current : nextExtractions[0]?.id || ""
      );
      setSelectedInspectionSchemaId((current) =>
        nextSchemas.some((item) => item.id === current) ? current : nextSchemas[0]?.id || ""
      );
    } catch (error) {
      setInspectionError(String(error));
    } finally {
      setIsLoadingInspection(false);
    }
  }, [api]);

  const openInspection = useCallback(() => {
    setIsInspectionOpen(true);
    void loadInspectionData();
  }, [loadInspectionData]);

  const selectedExtraction = useMemo(
    () => inspectionData.extractions.find((item) => item.id === selectedExtractionId),
    [inspectionData.extractions, selectedExtractionId]
  );

  const selectedInspectionSchema = useMemo(
    () => inspectionData.schemas.find((item) => item.id === selectedInspectionSchemaId),
    [inspectionData.schemas, selectedInspectionSchemaId]
  );

  const exportSelectedPriceJson = useCallback(() => {
    if (!selectedExtraction) {
      return;
    }

    const baseName = safeExportFilename(
      selectedExtraction.fileName || selectedExtraction.taskId || selectedExtraction.id,
      "price-info"
    );
    exportJson(selectedExtraction.result || selectedExtraction, `${baseName}-price-info.json`);
  }, [selectedExtraction]);

  const exportSelectedSchemaJson = useCallback(() => {
    if (!selectedInspectionSchema) {
      return;
    }

    const baseName = safeExportFilename(
      selectedInspectionSchema.schemaName || selectedInspectionSchema.domain || selectedInspectionSchema.id,
      "schema"
    );
    exportJson(selectedInspectionSchema, `${baseName}-schema.json`);
  }, [selectedInspectionSchema]);

  return {
    isInspectionOpen,
    setIsInspectionOpen,
    isLoadingInspection,
    inspectionError,
    inspectionData,
    selectedInspectionTab,
    setSelectedInspectionTab,
    selectedExtractionId,
    setSelectedExtractionId,
    selectedInspectionSchemaId,
    setSelectedInspectionSchemaId,
    selectedExtraction,
    selectedInspectionSchema,
    loadInspectionData,
    openInspection,
    exportSelectedPriceJson,
    exportSelectedSchemaJson
  };
}
