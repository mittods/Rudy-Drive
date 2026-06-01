import { useEffect, useMemo, useState } from "react"
import {
  Badge,
  Box,
  Button,
  Center,
  Flex,
  Grid,
  GridItem,
  Heading,
  Input,
  Spinner,
  Stack,
  Text,
} from "@chakra-ui/react"
import { FiDownload, FiFolderPlus, FiLogIn, FiRefreshCw, FiServer, FiTrash2 } from "react-icons/fi"

import { UploadModal } from "../../components/ui/uploadModal"
import { toaster } from "../../components/ui/toaster"
import {
  deleteFile,
  healthCheck,
  listFiles,
  login,
  me,
  register,
  setStoredToken,
  taskStatus,
  uploadFile,
  type TaskResponse,
  getStoredToken,
  type BackendFile,
  type HealthResponse,
} from "../../services/api"

function statusColor(status: string): string {
  if (status === "ready" || status === "completed") return "green"
  if (status === "pending" || status === "queued") return "yellow"
  if (status === "deleted") return "gray"
  return "red"
}

export default function FileSys() {
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [token, setToken] = useState<string | null>(getStoredToken())
  const [userId, setUserId] = useState<string | null>(null)
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [files, setFiles] = useState<BackendFile[]>([])
  const [loading, setLoading] = useState(false)
  const [authLoading, setAuthLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const activeFiles = useMemo(
    () => files.filter((file) => file.status !== "deleted"),
    [files],
  )

  async function refreshData(currentToken = token) {
    if (!currentToken) {
      return
    }

    const [healthData, userInfo, fileData] = await Promise.all([
      healthCheck(),
      me(currentToken),
      listFiles(currentToken),
    ])

    setHealth(healthData)
    setUserId(userInfo.user_id)
    setFiles(fileData)
  }

  useEffect(() => {
    void (async () => {
      try {
        await healthCheck().then(setHealth)
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "No se pudo consultar la salud")
      }
    })()
  }, [])

  useEffect(() => {
    if (!token) {
      return
    }

    setLoading(true)
    refreshData(token)
      .catch((cause) => {
        setError(cause instanceof Error ? cause.message : "No se pudo cargar el dashboard")
      })
      .finally(() => setLoading(false))
  }, [token])

  async function handleLogin() {
    setAuthLoading(true)
    setError(null)
    try {
      const auth = await login(email, password)
      setStoredToken(auth.access_token)
      setToken(auth.access_token)
      setUserId(auth.user_id)
      toaster.create({
        title: "Sesión iniciada",
        description: `Hola ${auth.email}`,
        type: "success",
      })
      await refreshData(auth.access_token)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No se pudo iniciar sesión")
    } finally {
      setAuthLoading(false)
    }
  }

  async function handleRegister() {
    setAuthLoading(true)
    setError(null)
    try {
      await register(email, password)
      const auth = await login(email, password)
      setStoredToken(auth.access_token)
      setToken(auth.access_token)
      setUserId(auth.user_id)
      toaster.create({
        title: "Cuenta creada",
        description: `Se registró ${auth.email} y se inició sesión`,
        type: "success",
      })
      await refreshData(auth.access_token)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No se pudo registrar")
    } finally {
      setAuthLoading(false)
    }
  }

  async function handleFilesDropped(filesToUpload: File[]) {
    if (!token || !userId) {
      setError("Debes iniciar sesión primero")
      return
    }

    setIsModalOpen(false)
    setLoading(true)
    try {
      for (const file of filesToUpload) {
        const task = await uploadFile(token, userId, file)
        toaster.create({
          title: "Archivo encolado",
          description: `${file.name} -> tarea ${task.task_id}`,
          type: "info",
        })

        let currentTask: TaskResponse = task
        for (let retries = 0; retries < 30 && currentTask.status === "pending"; retries += 1) {
          await new Promise((resolve) => setTimeout(resolve, 1000))
          currentTask = await taskStatus(token, task.task_id)
        }

        toaster.create({
          title: `Archivo ${currentTask.status}`,
          description: `${file.name} terminó con estado ${currentTask.status}`,
          type: currentTask.status === "completed" ? "success" : "warning",
        })
      }

      await refreshData(token)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No se pudo subir el archivo")
    } finally {
      setLoading(false)
    }
  }

  async function handleDelete(fileId: string) {
    if (!token || !userId) {
      setError("Debes iniciar sesión primero")
      return
    }

    setLoading(true)
    try {
      const task = await deleteFile(token, userId, fileId)
      let currentTask: TaskResponse = task
      for (let retries = 0; retries < 30 && currentTask.status === "pending"; retries += 1) {
        await new Promise((resolve) => setTimeout(resolve, 1000))
        currentTask = await taskStatus(token, task.task_id)
      }

      toaster.create({
        title: "Eliminación completada",
        description: `Tarea ${currentTask.task_id} terminó con estado ${currentTask.status}`,
        type: currentTask.status === "completed" ? "success" : "warning",
      })
      await refreshData(token)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No se pudo borrar el archivo")
    } finally {
      setLoading(false)
    }
  }

  async function handleDownload(fileId: string, filename: string) {
    if (!token) {
      setError("Debes iniciar sesión primero")
      return
    }

    try {
      const response = await fetch(`/api/files/${fileId}/download`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })

      if (!response.ok) {
        const body = await response.text()
        throw new Error(body || `HTTP ${response.status}`)
      }

      const blob = await response.blob()
      const objectUrl = URL.createObjectURL(blob)
      const anchor = document.createElement("a")
      anchor.href = objectUrl
      anchor.download = filename
      anchor.click()
      URL.revokeObjectURL(objectUrl)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No se pudo descargar el archivo")
    }
  }

  function handleLogout() {
    setStoredToken(null)
    setToken(null)
    setUserId(null)
    setFiles([])
    toaster.create({
      title: "Sesión cerrada",
      type: "info",
    })
  }

  return (
    <Grid h="100vh" templateRows="auto 1fr auto" templateColumns="100%">
      <GridItem bgGradient="linear(to-r, #0b1324, #11324d 55%, #1AAE9F)" color="white" px={8} py={5}>
        <Flex justify="space-between" align="center" gap={4} wrap="wrap">
          <Box>
            <Heading size="2xl" letterSpacing="tight">
              RudyDrive
            </Heading>
            <Text opacity={0.8}>Backend, distributed y frontend conectados por Docker</Text>
          </Box>
          <Flex gap={3} align="center" wrap="wrap">
            <Badge colorPalette={health?.status === "healthy" ? "green" : "red"} px={3} py={1} rounded="full">
              {health?.status ?? "health..."}
            </Badge>
            {token ? (
              <Button variant="outline" colorPalette="whiteAlpha" onClick={handleLogout}>
                Cerrar sesión
              </Button>
            ) : null}
          </Flex>
        </Flex>
      </GridItem>

      <GridItem bg="gray.50" px={6} py={6} overflow="auto">
        <Grid templateColumns={{ base: "1fr", xl: "360px 1fr" }} gap={6}>
          <GridItem>
            <Box bg="white" p={6} borderRadius="2xl" boxShadow="lg" border="1px solid" borderColor="gray.100">
              <Heading size="md" mb={4}>
                Acceso
              </Heading>
              <Stack gap={3}>
                <Input placeholder="Email" value={email} onChange={(event) => setEmail(event.target.value)} />
                <Input placeholder="Password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
                <Flex gap={3} wrap="wrap">
                  <Button bg="#1AAE9F" color="white" onClick={handleLogin} loading={authLoading}>
                    <FiLogIn /> Entrar
                  </Button>
                  <Button variant="outline" onClick={handleRegister} loading={authLoading}>
                    Crear cuenta
                  </Button>
                </Flex>
              </Stack>
            </Box>

            <Box mt={6} bg="white" p={6} borderRadius="2xl" boxShadow="lg" border="1px solid" borderColor="gray.100">
              <Flex justify="space-between" align="center" mb={4}>
                <Heading size="md">Salud del sistema</Heading>
                <Button variant="ghost" size="sm" onClick={() => refreshData().catch((cause) => setError(cause instanceof Error ? cause.message : "No se pudo refrescar"))}>
                  <FiRefreshCw />
                </Button>
              </Flex>
              <Stack gap={2} fontSize="sm">
                <Text>Backend: {health?.status ?? "-"}</Text>
                <Text>DB: {health?.database ?? "-"}</Text>
                <Text>RabbitMQ: {health?.rabbitmq ?? "-"}</Text>
                <Text>MinIO: {health?.minio ?? "-"}</Text>
                <Text>Workers: {health?.workers ?? "-"}</Text>
              </Stack>
            </Box>
          </GridItem>

          <GridItem>
            <Box bg="white" p={6} borderRadius="2xl" boxShadow="lg" border="1px solid" borderColor="gray.100" minH="70vh">
              <Flex justify="space-between" align="center" mb={4} wrap="wrap" gap={3}>
                <Box>
                  <Heading size="lg">Archivos</Heading>
                  <Text color="gray.500">Sube, inspecciona y elimina sobre el backend conectado a distributed.</Text>
                </Box>
                <Button bg="#1AAE9F" color="white" onClick={() => setIsModalOpen(true)} disabled={!token || !userId}>
                  <FiFolderPlus /> Subir archivo
                </Button>
              </Flex>

              {error ? (
                <Box bg="red.50" color="red.700" borderRadius="lg" p={4} mb={4}>
                  {error}
                </Box>
              ) : null}

              {loading ? (
                <Center minH="240px">
                  <Stack align="center">
                    <Spinner size="xl" color="teal.500" />
                    <Text color="gray.500">Sincronizando con backend y distributed...</Text>
                  </Stack>
                </Center>
              ) : activeFiles.length === 0 ? (
                <Center minH="240px" flexDirection="column" gap={2} border="1px dashed" borderColor="gray.200" borderRadius="xl">
                  <FiServer size={28} color="#1AAE9F" />
                  <Text color="gray.500">No hay archivos activos todavía</Text>
                </Center>
              ) : (
                <Box overflowX="auto">
                  <table style={{ width: "100%", borderCollapse: "collapse" }}>
                    <thead>
                      <tr style={{ textAlign: "left", color: "#4A5568" }}>
                        <th style={{ padding: "12px" }}>Nombre</th>
                        <th style={{ padding: "12px" }}>Tamaño</th>
                        <th style={{ padding: "12px" }}>Estado</th>
                        <th style={{ padding: "12px" }}>Acciones</th>
                      </tr>
                    </thead>
                    <tbody>
                      {activeFiles.map((file) => (
                        <tr key={file.id} style={{ borderTop: "1px solid #EDF2F7" }}>
                          <td style={{ padding: "12px" }}>
                            <Text fontWeight="semibold">{file.filename}</Text>
                            <Text fontSize="sm" color="gray.500">
                              {file.content_type}
                            </Text>
                          </td>
                          <td style={{ padding: "12px" }}>{(file.size / 1024 / 1024).toFixed(2)} MiB</td>
                          <td style={{ padding: "12px" }}>
                            <Badge colorPalette={statusColor(file.status)}>{file.status}</Badge>
                          </td>
                          <td style={{ padding: "12px" }}>
                            <Flex gap={2} wrap="wrap">
                              <Button size="sm" variant="outline" disabled={file.status !== "ready"} onClick={() => void handleDownload(file.id, file.filename)}>
                                <FiDownload /> Descargar
                              </Button>
                              <Button size="sm" colorPalette="red" variant="outline" onClick={() => void handleDelete(file.id)}>
                                <FiTrash2 /> Eliminar
                              </Button>
                            </Flex>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </Box>
              )}
            </Box>
          </GridItem>
        </Grid>
      </GridItem>

      <GridItem bg="gray.900" color="gray.200" px={6} py={3}>
        <Flex justify="space-between" align="center" gap={4} wrap="wrap">
          <Text fontSize="sm">API base: /api</Text>
          <Text fontSize="sm">CORS, Docker y RabbitMQ enlazados</Text>
        </Flex>
      </GridItem>

      <UploadModal open={isModalOpen} onClose={() => setIsModalOpen(false)} onFilesDropped={handleFilesDropped} />
    </Grid>
  )
}
