# TopologyGen

Generador de topologías de red orientado a experimentación, simulación y pruebas.  
Permite visualizar dispositivos, enlaces y tipos de nodos a partir de un archivo YAML que describe un testbed.

---

## Requisitos

- Python 3.x

---

## Uso

### Mostrar ayuda

```bash
python topology.py -help
```
### Ejemplos de ejecución

```bash
python topology.py testbed.yaml
python topology.py testbed.yaml --theme light
python topology.py testbed.yaml --output-dir ./diagrams --name lab1
```

Argumentos disponibles
Argumento	Obligatorio	Valores	Descripción
yaml_file	Sí	archivo YAML	Testbed a visualizar
--theme	No	dark, light	Tema de colores
--output-dir	No	ruta	Carpeta de salida
--name	No	texto	Nombre base del archivo generado

Archivos generados
El script produce los siguientes archivos en el directorio indicado:

topology.png
topology.svg
