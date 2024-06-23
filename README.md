# Platzi descargas

## Descripción

Platzi descargas es una herramienta de línea de comandos diseñada para descargar cursos y rutas de aprendizaje de Platzi. Permite a los usuarios descargar videos, PDFs y archivos adjuntos de los cursos a los que están suscritos, facilitando el aprendizaje offline.

## Características

- Descarga cursos completos o rutas de aprendizaje enteras
- Soporta la descarga de videos, PDFs y archivos adjuntos
- Organiza el contenido descargado en una estructura de carpetas lógica
- Permite reanudar descargas interrumpidas
- Maneja la autenticación de Platzi de forma segura

## Requisitos previos

- Python 3.7 o superior
- Google Chrome instalado
- Una cuenta activa de Platzi

## Instalación

1. Clone el repositorio:
   ```
   git clone https://github.com/zubus/Platzi-descarga
   cd Platzi-descarga
   ```

2. Cree y active un entorno virtual:
   ```
   python -m venv venv
   source venv/bin/activate  # En Windows use `venv\Scripts\activate`
   ```

3. Instale las dependencias:
   ```
   pip install -r requirements.txt
   ```

## Uso

1. Asegúrese de haber iniciado sesión en Platzi en Google Chrome.

2. Ejecute el script:
   ```
   python platzi_downloader.py
   ```

3. Cuando se le solicite, ingrese la URL de la ruta de aprendizaje o del curso que desea descargar.

4. Si ingresa una sola ruta de aprendizaje, se le mostrará una lista de cursos y se le pedirá que elija desde qué curso comenzar la descarga.

5. El script comenzará a descargar el contenido en la carpeta `Platzi_Downloads` en el directorio actual.

## Estructura de archivos

El contenido descargado se organizará de la siguiente manera:

```
Platzi_Downloads/
├── Nombre de la Ruta de Aprendizaje/
│   ├── 01_Nombre del Curso/
│   │   ├── 01_Nombre de la Clase.mp4
│   │   ├── 02_Nombre de la Clase.pdf
│   │   └── archivos_adjuntos/
│   └── 02_Nombre del Curso/
│       ├── 01_Nombre de la Clase.mp4
│       └── 02_Nombre de la Clase.mp4
└── debug/
    └── debug_YYYYMMDD_HHMMSS.txt
```

## Consideraciones éticas

Por favor, respete los términos de servicio de Platzi y los derechos de autor del contenido. No distribuya el contenido descargado.
