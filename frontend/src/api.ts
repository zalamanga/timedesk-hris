export type User = { id: number; name: string; email: string; role: 'employee' | 'manager'; manager_id: number | null };
export type Auth = { user: User; csrf_token: string; demo_mode: boolean };
export type Entry = { id: number; employee: User; start_at: string; end_at: string | null; version: number; seconds: number; duration: string | null; active_seconds: number; request_id: string };
export type Correction = { id: number; entry: Entry; employee: User; original_start: string; original_end: string; proposed_start: string; proposed_end: string; reason: string; state: 'pending'|'approved'|'rejected'|'withdrawn'; version: number; base_entry_version: number; created_at: string; decided_at: string | null; decision_note: string | null };
export type AttendanceResponse = { items: Entry[]; active: Entry | null; server_now: string; timezone: string };
export type Recap = { items: { date: string; employee: User; completed_seconds: number; duration: string; active_seconds: number }[]; duration: string; completed_seconds: number; active_seconds: number; server_now: string };

export class ApiError extends Error { constructor(public status: number, message: string) { super(message); } }

export async function api<T>(path: string, options: RequestInit = {}, csrf?: string): Promise<T> {
  const response = await fetch(`/api${path}`, { credentials: 'same-origin', ...options, headers: { ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...(csrf ? { 'X-CSRF-Token': csrf } : {}), ...options.headers } });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const message = typeof body.detail === 'string' ? body.detail : Array.isArray(body.detail) ? 'Periksa format dan kelengkapan isian Anda.' : `Permintaan gagal (${response.status}). Coba lagi.`;
    throw new ApiError(response.status, message);
  }
  return response.status === 204 ? undefined as T : response.json();
}

export function wib(value: string) { return new Intl.DateTimeFormat('id-ID', {timeZone:'Asia/Jakarta', day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(new Date(value)); }
export function dateLabel(value: string) { return new Intl.DateTimeFormat('id-ID',{timeZone:'Asia/Jakarta',weekday:'short',day:'numeric',month:'short'}).format(new Date(`${value}T12:00:00+07:00`)); }
export function localInput(value: string) { const parts = new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Jakarta',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(new Date(value)); return parts.replace(' ','T'); }
export function duration(seconds: number) { const total = Math.max(0, Math.floor(seconds)); return `${String(Math.floor(total/3600)).padStart(2,'0')}:${String(Math.floor(total/60)%60).padStart(2,'0')}:${String(total%60).padStart(2,'0')}`; }
export function initialDates() { const now = new Date(); const end = new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Jakarta',year:'numeric',month:'2-digit',day:'2-digit'}).format(now); const prior = new Date(`${end}T12:00:00+07:00`); prior.setUTCDate(prior.getUTCDate()-6); return { from: new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Jakarta',year:'numeric',month:'2-digit',day:'2-digit'}).format(prior), to: end }; }
