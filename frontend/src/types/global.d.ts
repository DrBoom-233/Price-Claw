interface DesktopAPI {
  backendBaseUrl?: string;
  getBackendBaseUrl?: () => Promise<string>;
}

interface Window {
  desktopAPI?: DesktopAPI;
}

declare module "*.png" {
  const src: string;
  export default src;
}
