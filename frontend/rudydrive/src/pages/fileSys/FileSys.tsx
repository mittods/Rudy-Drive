import { Grid, GridItem, Heading, Box, Field, Input, Button, Center,Stack,Text, Progress, Tooltip } from "@chakra-ui/react"
import React, { useState } from "react"
import { FiSearch, FiFolderPlus, FiServer} from "react-icons/fi"
import { UploadModal } from "../../components/ui/uploadModal" // 👈 Importamos tu ventana emergente
import { toaster } from "../../components/ui/toaster"

function FileSys() {
  // 1. Estados para controlar el Modal y guardar la lista de archivos cargados
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false)
  const [archivosCargados, setArchivosCargados] = useState<File[]>([])

  // 2. Esta función recibe los archivos cuando el usuario los suelta en el Dropzone
  const manejarNuevosArchivos = (files: File[]) => {
    setArchivosCargados((prev) => [...prev, ...files])
    
    // Cerramos la ventana emergente automáticamente
    setIsModalOpen(false)

    // Notificación de éxito usando el toaster de Chakra v3
    toaster.create({
      title: `${files.length} archivo(s) agregados`,
      description: "Los archivos se han cargado en la lista.",
      type: "success",
    })
  }


  return (
    <Grid
      h="100vh"
      templateRows="10vh 85vh 5vh"
      templateColumns="100%"
    >
      {/* Banner Superior */}
      <GridItem bg="#1AAE9F" color="white" display="flex" alignItems="center" px={6}>
        <Heading size="3xl">RudyDrive</Heading>
      </GridItem>

      {/* Espacio Usable */}
      <GridItem bg="gray.50" p={10}>
        <Box bg="white" p={10} borderRadius="xl" shadow="sm" h="100%">
          <Grid
            h="100%"
            templateRows="5vh 95vh"
            templateColumns="100%"
          >
            {/*Busqueda, Ingreso, Espacio*/}
            <GridItem>
              <Grid templateColumns="repeat(3, 1fr)" gap="6">
                {/*Busqueda*/}
                <GridItem>
                  <Grid templateColumns="90% 10%" w="100%">
                    <GridItem>
                      <Field.Root>
                        <Input placeholder="Buscar archivo..."/>
                      </Field.Root>
                    </GridItem>
                    <GridItem>
                      <Button bg="#1AAE9F"><FiSearch/></Button>
                    </GridItem>
                  </Grid>
                </GridItem>
                {/*Ingreso*/}
                <GridItem>
                  <Center>
                    <Button bg="#1AAE9F" w="50%" onClick={() => setIsModalOpen(true)}>Subir archivo<FiFolderPlus/></Button>
                  </Center>
                </GridItem>
                {/*Espacio*/}
                <GridItem>
                  <Stack>
                    <Progress.Root size="sm" value={60}>
                      <Progress.Track bg="gray.50">
                        <Progress.Range bg="#1AAE9F"/>
                      </Progress.Track>
                    </Progress.Root>
                    <Text color="gray.400">
                      Espacio ocupado
                    </Text>
                  </Stack>
                </GridItem>
              </Grid>
            </GridItem>
            {/*Tabla de archivos*/}
            <GridItem mt="4">
              <Text mb="2" fontWeight="bold">Tabla de objetos</Text>
              
              {/* Renderizamos de forma dinámica los archivos que vayas subiendo */}
              <Stack gap="2">
                {archivosCargados.length === 0 ? (
                  <Text color="gray.400" fontSize="sm">No hay archivos subidos aún.</Text>
                ) : (
                  archivosCargados.map((arc, i) => (
                    <Text key={i} fontSize="sm" color="gray.600">
                      📄 {arc.name} — {(arc.size / 1024).toFixed(1)} KB
                    </Text>
                  ))
                )}
              </Stack>
            </GridItem>
            

          </Grid>
        </Box>
      </GridItem>
      <GridItem bg="gray.50">
        <Grid templateColumns="90% 10%">
          <GridItem colStart={2}>
            <Tooltip.Root>
              <Tooltip.Trigger asChild>
                <Button variant="plain" color="gray.400" size="2xl">
                  <FiServer/>
                </Button>
              </Tooltip.Trigger>

              <Tooltip.Content color="white" p="2" borderRadius="md">
                Este tooltip no se moverá de arriba
                <Tooltip.Arrow />
              </Tooltip.Content>
            </Tooltip.Root>
          </GridItem>
        </Grid>
      </GridItem>
      <UploadModal 
        open={isModalOpen} 
        onClose={() => setIsModalOpen(false)} 
        onFilesDropped={manejarNuevosArchivos}
      />
    </Grid>
    
  )
}

export default FileSys