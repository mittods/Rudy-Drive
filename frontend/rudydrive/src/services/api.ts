export interface AuthResponse {
  access_token: string
  token_type: string
  user_id: string
  email: string
}

export interface MeResponse {
  user_id: string
  email: string
  message: string
}

export interface HealthResponse {
  status: string
  database: string
  rabbitmq: string
  minio: string
  workers: string
}

export interface BackendFile {
  id: string
  user_id: string
  filename: string
  size: number
  content_type: string
  status: string
  created_at: string
  updated_at?: string | null
}

export interface TaskResponse {
  task_id: string
  file_id: string
  task_type: string
  status: string
  retry_count?: number
  error_message?: string | null
  completed_at?: string | null
}

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api"
const TOKEN_KEY = "rudydrive-token"

export function getStoredToken(): string | null {
  return window.localStorage.getItem(TOKEN_KEY)
}

export function setStoredToken(token: string | null): void {
  if (token) {
    window.localStorage.setItem(TOKEN_KEY, token)
    return
  }

  window.localStorage.removeItem(TOKEN_KEY)
}

async function requestJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (!headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json")
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
  })

  const text = await response.text()
  const payload = text ? JSON.parse(text) : null

  if (!response.ok) {
    const message = payload?.detail ?? payload?.message ?? `HTTP ${response.status}`
    throw new Error(message)
  }

  return payload as T
}

function authHeaders(token: string): HeadersInit {
  return {
    Authorization: `Bearer ${token}`,
  }
}

export async function healthCheck(): Promise<HealthResponse> {
  return requestJson<HealthResponse>("/health")
}

export async function register(email: string, password: string): Promise<{ user_id: string; message: string }> {
  return requestJson("/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  })
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  return requestJson<AuthResponse>("/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  })
}

export async function me(token: string): Promise<MeResponse> {
  return requestJson<MeResponse>("/me", {
    headers: authHeaders(token),
  })
}

export async function listFiles(token: string): Promise<BackendFile[]> {
  return requestJson<BackendFile[]>("/files", {
    headers: authHeaders(token),
  })
}

function toBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = reader.result
      if (typeof result !== "string") {
        reject(new Error("No se pudo leer el archivo"))
        return
      }

      const base64 = result.split(",", 2)[1]
      resolve(base64)
    }
    reader.onerror = () => reject(new Error("No se pudo leer el archivo"))
    reader.readAsDataURL(file)
  })
}

export async function uploadFile(token: string, userId: string, file: File): Promise<TaskResponse> {
  const requestId = crypto.randomUUID()
  const fileId = crypto.randomUUID()
  const dataBase64 = await toBase64(file)

  return requestJson<TaskResponse>("/files", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({
      request_id: requestId,
      user_id: userId,
      file_id: fileId,
      filename: file.name,
      content_type: file.type || "application/octet-stream",
      size_bytes: file.size,
      data_base64: dataBase64,
    }),
  })
}

export async function deleteFile(token: string, userId: string, fileId: string): Promise<TaskResponse> {
  const requestId = crypto.randomUUID()

  return requestJson<TaskResponse>(`/files/${fileId}`, {
    method: "DELETE",
    headers: authHeaders(token),
    body: JSON.stringify({
      request_id: requestId,
      user_id: userId,
      file_id: fileId,
      upload_id: fileId,
    }),
  })
}

export async function taskStatus(token: string, taskId: string): Promise<TaskResponse> {
  return requestJson<TaskResponse>(`/tasks/${taskId}`, {
    headers: authHeaders(token),
  })
}

export { API_BASE }
