import React, { useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { Box, Stack, Text, Center, Button } from '@chakra-ui/react'
import { FiUploadCloud, FiFolder } from 'react-icons/fi'

interface DropzoneProps {
  onFilesDropped: (files: File[]) => void
}

export const Dropzone: React.FC<DropzoneProps> = ({ onFilesDropped }) => {
  
  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      onFilesDropped(acceptedFiles)
    }
  }, [onFilesDropped])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    multiple: true
  })

  return (
    <Center 
      {...getRootProps()} // Al hacer clic en cualquier parte de este Center, se abrirá el explorador de archivos
      w="100%"
      h="240px"
      p="6"
      border="2px dashed"
      borderColor={isDragActive ? "#1AAE9F" : "gray.300"}
      borderRadius="xl"
      bg={isDragActive ? "teal.50" : "gray.50"}
      cursor="pointer"
      transition="all 0.2s ease"
      _hover={{
        borderColor: "#1AAE9F",
        bg: "gray.100"
      }}
    >
      {/* Este es el input invisible que abre el explorador de archivos nativo del sistema (Windows/Mac/Linux) */}
      <input {...getInputProps()} />

      <Stack align="center" gap="3" textAlign="center">
        <Box color={isDragActive ? "#1AAE9F" : "gray.400"} fontSize="4xl">
          <FiUploadCloud />
        </Box>
        
        {isDragActive ? (
          <Text fontWeight="medium" color="#1AAE9F">
            ¡Suelta los archivos ahora!
          </Text>
        ) : (
          <>
            <Text fontWeight="medium" color="gray.700">
              Arrastra y suelta tus archivos aquí
            </Text>
            
            <Text fontSize="xs" color="gray.400">
              o si lo prefieres
            </Text>

            {/* BOTÓN VISUAL: Hace más obvio que se puede dar clic para buscar */}
            <Button 
              size="sm" 
              bg="#1AAE9F" 
              color="white"
              pointerEvents="none" // Importante: Evita que el botón intercepte el clic, dejando que el contenedor padre lo maneje
            >
              <FiFolder /> Seleccionar del dispositivo
            </Button>
          </>
        )}
      </Stack>
    </Center>
  )
}