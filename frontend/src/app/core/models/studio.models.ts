// Modelos de Datos Tipados para Podcast Multicam Studio
export interface CameraFeed {
  id: number;
  label: string;
  stream: MediaStream | null;
  isConnected: boolean;
  isProgram: boolean;
  isPreview: boolean;
  fps: number;
  resolution: string;
  bitrateKbps: number;
  batteryLevel?: number;
  isCharging?: boolean;
  thermalStatus?: string;
  currentZoom?: number;
  isTorchOn?: boolean;
  isOledActive?: boolean;
}

export interface AudioMetrics {
  rmsDb: number;
  peakDb: number;
  lufs: number;
  isClipping: boolean;
  levelL: number; // 0 - 100%
  levelR: number; // 0 - 100%
  waveformPath: string; // SVG path d="..."
}

export interface AudioDevice {
  deviceId: string;
  label: string;
}

export interface RecordingState {
  isRecording: boolean;
  seconds: number;
  timecode: string;
  project: string;
  episode: string;
  take: number;
  markerCount: number;
}

export type TransitionMode = 'cut' | 'fade' | 'dip_black';

export interface SwitcherState {
  activeCam: number;
  previewCam: number;
  transitionMode: TransitionMode;
  transitionProgress: number; // 0.0 - 1.0
  isDipToBlack: boolean;
  isEmergencyBlack: boolean;
  framingMode: number; // 0: Off, 1: Safe 80%, 2: TikTok 9:16, 3: Tercios
}

export interface SystemTelemetry {
  ramUsedGb: number;
  ramTotalGb: number;
  ramPercent: number;
  diskFreeGb: number;
  cpuPercent: number;
}

export interface MarkerFlag {
  index: number;
  timecode: string;
  note: string;
  createdAt: string;
}

export type VideoProfile = '1080p60' | '2K60' | '4K60';

export interface VideoProfileSettings {
  profile: VideoProfile;
  resolution: string;
  fps: number;
  videoBitrate: number;
  audioBitrate: number;
  label: string;
}

export const VIDEO_PROFILES: Record<VideoProfile, VideoProfileSettings> = {
  '1080p60': {
    profile: '1080p60',
    resolution: '1920x1080',
    fps: 60,
    videoBitrate: 8_000_000, // 8 Mbps
    audioBitrate: 192_000,   // 192 kbps
    label: '1080p @ 60 FPS (8 Mbps NVENC/QS)'
  },
  '2K60': {
    profile: '2K60',
    resolution: '2560x1440',
    fps: 60,
    videoBitrate: 16_000_000, // 16 Mbps
    audioBitrate: 256_000,    // 256 kbps
    label: '2K QHD @ 60 FPS (16 Mbps)'
  },
  '4K60': {
    profile: '4K60',
    resolution: '3840x2160',
    fps: 60,
    videoBitrate: 35_000_000, // 35 Mbps
    audioBitrate: 320_000,    // 320 kbps
    label: '4K UHD @ 60 FPS (35 Mbps)'
  }
};

export interface ConnectionRoute {
  id: string;
  title: string;
  badge: string;
  ip: string;
  base_url: string;
  is_active: boolean;
  latency_label: string;
  icon: string;
  description: string;
}

export interface AdbDevice {
  serial: string;
  state: string;
  model: string;
  product: string;
  reversed: boolean;
  direct_url: string;
}

export interface ConnectionMatrix {
  hotspot_5ghz: {
    active: boolean;
    ip: string | null;
    name: string;
    adapter_desc: string | null;
    suggested_band: string;
  };
  apple_usb: {
    active: boolean;
    ip: string | null;
    name: string;
    adapter_desc: string | null;
  };
  android_rndis: {
    active: boolean;
    ip: string | null;
    name: string;
    adapter_desc: string | null;
  };
  wifi_lan: {
    active: boolean;
    ip: string | null;
    name: string;
    adapter_desc: string | null;
  };
  usb_adb: {
    available: boolean;
    adb_path: string | null;
    devices: AdbDevice[];
    count?: number;
    message?: string;
  };
  port: number;
  recommended_route: string;
  available_routes: ConnectionRoute[];
  active_ips: string[];
}

