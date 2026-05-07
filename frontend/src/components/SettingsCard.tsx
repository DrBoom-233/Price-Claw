import type { StatusType } from "../types/app";

interface SettingsCardProps {
  isRunning: boolean;
  hasCheckedSettings: boolean;
  settingsStatus: string;
  settingsStatusType: StatusType;
  onOpenSettings: () => void;
}

export function SettingsCard({
  isRunning,
  hasCheckedSettings,
  settingsStatus,
  settingsStatusType,
  onOpenSettings
}: SettingsCardProps) {
  return (
    <section className="card">
      <h2>Settings</h2>
      <p className="subtitle">API key is configured in a secure popup and is no longer shown directly on the page.</p>
      <div className="actions">
        <button onClick={onOpenSettings} disabled={isRunning || !hasCheckedSettings}>
          Open Settings
        </button>
        <span className={`status status-${settingsStatusType}`}>{settingsStatus}</span>
      </div>
    </section>
  );
}
