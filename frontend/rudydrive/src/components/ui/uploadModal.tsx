import React from "react"
import { Dialog, Button, Stack } from "@chakra-ui/react"
import { Dropzone } from "./dropzone" // Importamos el paso anterior

interface UploadModalProps {
  open: boolean // Controla si el modal es visible
  onClose: () => void // Función para cerrar el modal
  onFilesDropped: (files: File[]) => void // Qué hacer cuando caen archivos
}

export const UploadModal: React.FC<UploadModalProps> = ({ open, onClose, onFilesDropped }) => {
  
  // Captura si el usuario hace click fuera del modal o presiona la tecla Escape
  const manejarCambioOpen = (details: { open: boolean }) => {
    if (!details.open) {
      onClose()
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={manejarCambioOpen} size="md" motionPreset="slide-in-bottom">
      <Dialog.Backdrop />
      <Dialog.Positioner>
        <Dialog.Content bg="white" p="6" borderRadius="xl">
          
          <Dialog.Header>
            <Dialog.Title fontSize="lg" fontWeight="bold" color="gray.800">
              Subir nuevos archivos a RudyDrive
            </Dialog.Title>
          </Dialog.Header>

          <Dialog.Body my="4">
            {/* Metemos el Dropzone aquí adentro */}
            <Dropzone onFilesDropped={onFilesDropped} />
          </Dialog.Body>

          <Dialog.Footer>
            <Stack direction="row" gap="3" width="100%" justify="flex-end">
              <Button variant="outline" colorPalette="gray" onClick={onClose}>
                Cancelar
              </Button>
            </Stack>
          </Dialog.Footer>
          
          <Dialog.CloseTrigger />
        </Dialog.Content>
      </Dialog.Positioner>
    </Dialog.Root>
  )
}