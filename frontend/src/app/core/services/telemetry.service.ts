import { Injectable, signal } from '@angular/core';
import { SystemTelemetry } from '../models/studio.models';

@Injectable({
  providedIn: 'root'
})
export class TelemetryService {
  public readonly telemetry = signal<SystemTelemetry>({
    ramUsedGb: 0,
    ramTotalGb: 0,
    ramPercent: 0,
    diskFreeGb: 0,
    cpuPercent: 0
  });

  private intervalId: number | null = null;
  private globalHandlersRegistered = false;

  constructor() {
    this.startPolling();
    this.registerGlobalErrorHandlers();
  }

  public startPolling(): void {
    if (this.intervalId) return;
    this.fetchTelemetry();
    // Sondeo de hardware de Windows cada 1 segundo en tiempo real
    this.intervalId = window.setInterval(() => this.fetchTelemetry(), 1000);
  }

  public async fetchTelemetry(): Promise<void> {
    try {
      const res = await fetch('/api/telemetry');
      if (!res.ok) return;
      const data = await res.json();
      if (data) {
        const ramUsed = data.ram_used_gb ?? data.ram?.used_gb ?? 0;
        const ramTotal = data.ram_total_gb ?? data.ram?.total_gb ?? 0;
        const ramPct = data.ram_percent ?? data.ram?.percent ?? 0;
        const diskFree = data.disk_free_gb ?? data.disk?.free_gb ?? 0;
        const cpuPct = data.cpu_percent ?? data.cpu?.percent ?? 0;

        this.telemetry.set({
          ramUsedGb: Number(ramUsed),
          ramTotalGb: Number(ramTotal),
          ramPercent: Math.round(Number(ramPct)),
          diskFreeGb: Math.round(Number(diskFree)),
          cpuPercent: Math.round(Number(cpuPct))
        });
      }
    } catch {
      // Telemetría offline no crítica
    }
  }

  /**
   * Envía un evento estructurado o error a la Matriz de Logs JSON del Backend
   * (`Documentos/TX-STUDIO/Logs/tx_studio_events.jsonl` y `error_matrix.json`).
   */
  public logEvent(
    category: string,
    component: string,
    action: string,
    message: string,
    details: Record<string, unknown> = {},
    level: 'INFO' | 'WARN' | 'ERROR' | 'CRITICAL' = 'INFO',
    source: 'FRONTEND_UI' | 'MOBILE_CAM' = 'FRONTEND_UI'
  ): void {
    const payload = {
      level,
      source,
      category,
      component,
      action,
      message,
      details: {
        ...details,
        url: window.location.pathname,
        viewport: `${window.innerWidth}x${window.innerHeight}`
      }
    };

    fetch('/api/logs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).catch(() => {});
  }

  public async openLogsFolder(): Promise<void> {
    try {
      await fetch('/api/logs/open-folder');
    } catch {
      // Ignorar si está desconectado
    }
  }

  private registerGlobalErrorHandlers(): void {
    if (this.globalHandlersRegistered || typeof window === 'undefined') return;
    this.globalHandlersRegistered = true;

    window.addEventListener('error', (event: ErrorEvent) => {
      const sourceRole = window.location.pathname.startsWith('/cam/') ? 'MOBILE_CAM' : 'FRONTEND_UI';
      this.logEvent(
        'UNHANDLED_EXCEPTION',
        'WINDOW_ONERROR',
        'JS_RUNTIME_ERROR',
        event.message || 'Error de ejecución JavaScript en navegador',
        {
          where_file: event.filename || window.location.pathname,
          where_line: event.lineno || 0,
          where_column: event.colno || 0,
          exception_reason: event.message,
          traceback: event.error?.stack || ''
        },
        'ERROR',
        sourceRole
      );
    });

    window.addEventListener('unhandledrejection', (event: PromiseRejectionEvent) => {
      const sourceRole = window.location.pathname.startsWith('/cam/') ? 'MOBILE_CAM' : 'FRONTEND_UI';
      const reasonStr = event.reason instanceof Error ? event.reason.message : String(event.reason);
      const stackStr = event.reason instanceof Error ? (event.reason.stack || '') : '';
      this.logEvent(
        'UNHANDLED_EXCEPTION',
        'PROMISE_REJECTION',
        'ASYNC_REJECTION',
        `Promesa rechazada: ${reasonStr}`,
        {
          where_file: window.location.pathname,
          exception_reason: reasonStr,
          traceback: stackStr
        },
        'ERROR',
        sourceRole
      );
    });
  }
}
