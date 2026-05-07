import { useCallback, useEffect, useState } from "react";
import type { ApiClient } from "../api/client";
import type { SchemaSummary } from "../types/app";

export function useSchemas(api: ApiClient) {
  const [schemas, setSchemas] = useState<SchemaSummary[]>([]);
  const [selectedSchemaId, setSelectedSchemaId] = useState("");
  const [isLoadingSchemas, setIsLoadingSchemas] = useState(false);
  const [schemaLoadError, setSchemaLoadError] = useState("");

  const loadSchemas = useCallback(async () => {
    try {
      setIsLoadingSchemas(true);
      setSchemaLoadError("");
      const data = await api.getSchemas();
      const schemaList = Array.isArray(data.schemas) ? data.schemas : [];
      setSchemas(schemaList);

      if (schemaList.length === 0) {
        setSelectedSchemaId("");
        return;
      }

      const exists = schemaList.some((item) => item.id === selectedSchemaId);
      if (!exists) {
        setSelectedSchemaId("");
      }
    } catch (error) {
      setSchemas([]);
      setSelectedSchemaId("");
      setSchemaLoadError(String(error));
    } finally {
      setIsLoadingSchemas(false);
    }
  }, [api, selectedSchemaId]);

  useEffect(() => {
    void loadSchemas();
  }, [loadSchemas]);

  return {
    schemas,
    selectedSchemaId,
    setSelectedSchemaId,
    isLoadingSchemas,
    schemaLoadError,
    loadSchemas
  };
}
