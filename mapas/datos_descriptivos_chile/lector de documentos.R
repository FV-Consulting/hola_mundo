install.packages("sf")

# Cargar el paquete
library(sf)

# Leer el shapefile
shp <- st_read("C:/Users/dream/Downloads/COMUNAS/COMUNAS/COMUNAS_v1.shp")

# Ver información básica
print(shp)


#::::::::::::::::::::::::: DTA

# Instalar si no lo tienes
install.packages("haven")

# Cargar el paquete
library(haven)

# Leer archivo Stata (.dta)
datos <- read_dta("C:/Users/dream/Downloads/datos_descriptivos_chile/casen_2024_provincia_comuna.dta")

# Ver las primeras filas
head(datos)

# Ver estructura
str(datos)