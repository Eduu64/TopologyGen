# TopologyGen

Generador de topologías de red orientado a la experimentación, simulación y pruebas. Esta herramienta permite visualizar de forma gráfica dispositivos, enlaces y tipos de nodos a partir de un archivo de configuración en formato YAML que describe un testbed.

---

## Requisitos

* **Python 3.x**
* Dependencias del proyecto (instalar mediante `pip install -r requirements.txt` si el archivo existe).

---

## Uso

La herramienta se ejecuta a través de la terminal mediante el script `topology.py`.

### Interfaz de Línea de Comandos (CLI)

```bash
python topology.py [-h] [--theme {dark,light}] [--output-dir OUTPUT_DIR] [--name NAME] yaml_file
```

### Ejemplos de ejecución

```bash
python topology.py testbed.yaml
python topology.py testbed.yaml --theme light
python topology.py testbed.yaml --output-dir ./diagrams --name lab1
```
```bash
================================================================================
                           ARGUMENTOS DISPONIBLES
================================================================================
Argumento        Obligatorio   Valores          Descripción
--------------------------------------------------------------------------------
yaml_file        SÍ            Archivo YAML     Testbed a visualizar
--theme          NO            dark, light      Tema de colores del diagrama
--output-dir     NO            Ruta/Carpeta     Carpeta donde se guarda el output
--name           NO            Texto            Nombre base del archivo generado
-h, --help       NO            N/A              Muestra la ayuda en consola
================================================================================
```
---

## Archivos Generados

Tras una ejecución exitosa, el script genera los siguientes archivos:

--------------------------------------------------------------------------------
Archivo        Formato         Descripción
--------------------------------------------------------------------------------
topology.png   Rasterizado     Imagen estándar para visualización rápida.
topology.svg   Vectorial       Gráfico escalable para documentación técnica.
--------------------------------------------------------------------------------

NOTA: Si se utiliza el argumento --name (ejemplo: --name lab1), los archivos 
se renombrarán automáticamente (ej: lab1.png y lab1.svg).
