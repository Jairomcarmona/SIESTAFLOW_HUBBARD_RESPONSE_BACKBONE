"""Keep maintained source and documentation prose in English.

Literal archived SIESTA excerpts may stay in their original language. Any such
exception must be an exact line with a named evidence source; broad file or
directory exemptions would hide new user-facing Spanish text.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEXT_SUFFIXES = {".md", ".py", ".rst", ".txt", ".json", ".yaml", ".yml", ".toml", ".csv"}
ACCENTED_SPANISH = re.compile(r"[áéíóúüñÁÉÍÓÚÜÑ]")
MARKDOWN_LINK_DESTINATION = re.compile(r"\]\([^)]*\)")
COMMON_SPANISH_WORDS = re.compile(
    r"\b(?:estado|estados|nodo|nodos|activo|activa|analisis|campana|campanas|corrida|corridas|"
    r"ejecucion|salida|archivo|archivos|carpeta|carpetas|usuario|usuarios|advertencia|advertencias|"
    r"fallo|fallos|pendiente|pendientes|completo|completa|completado|completada|aceptado|aceptada|"
    r"rechazado|rechazada|resumen|informe|figura|prueba|pruebas|comprobacion|validacion|geometria|"
    r"atomo|atomos|sitio|sitios|malla|rejilla|ajuste|matriz|tolerancia|resultado|resultados|"
    r"declarado|declarada|utilizar|calcular|medido|medida|numero|razon|bloque|campo|campos|valor|"
    r"valores|convergencia|incertidumbre|registro|registros|historico|unico|unica|sensible|fallida|"
    r"valido|configuracion|opcion|fuente|falta|metodo|carga|segun|diseno|comparacion|compara|comparar|"
    r"detiene|detener|bloqueado|ejecuta|conserva|prohibido|maximo|minimo|requerido|obligatorio|puede|"
    r"pueden|tambien|siempre|salvo|excepto|nueva|nuevo|nuevos|nuevas|parametro|parametros|linea|"
    r"lineas|comando|comandos|iniciar|lectura|escritura|edicion|cambio|cambios|numerico|numerica|"
    r"cientifico|cientifica|ruta|rutas|directorio|comportamiento|esperado|esperada|limite|limites|"
    r"calculo|diferencia|diferencias|evidencia|respuesta|identidad|incorrecto|incorrecta|correcto|"
    r"correcta|ninguna|ningun|cada|mediante|cuando|porque|aunque|mientras|incluso|despues|antes|"
    r"durante|fuera|dentro|debe|deben|tiene|tienen|sera|seran|estara|estaran|fue|fueron|ninguno|"
    r"declarar|declara|declaracion|necesario|necesaria|necesarios|necesarias|registrado|registrada|"
    r"archivado|archivada|proximo|proxima|guia|seccion|secciones|caso|casos|"
    r"documento|documentos|documentacion|obtener|usar|usado|realizar|realizado|realizada|significa|"
    r"llamado|llamada|origen|destino|distinto|distinta|igual|ambos|ambas|conjunto|siguiente|ejemplo|"
    r"ejemplos|comun|comunes|verdadero|verdadera|falso|falsa|forma|manera|mismo|misma|mismos|mismas|"
    r"otro|otra|otros|otras|aplica|aplicar|aplicado|aplicada|aplicacion|estimacion|"
    r"derivacion|unicamente|solamente|teorico|teorica|practico|practica|especificado|especificada|"
    r"contenido|contenidos|muestra|muestran|incluir|incluido|incluida|incluidos|incluidas|"
    r"disponible|disponibles|ausente|ausentes|entrada|entradas|escribe|escriba|leido|leida|corrige|"
    r"corregir|requerida|requeridas|mostrado|mostrada|resuelto|resuelta|hallazgo|hallazgos|motivo|"
    r"motivos|despues|posterior|posteriores|inferior|superior|mientras|suficiente|insuficiente|"
    r"marcado|marcada|calculado|calculada|calculados|calculadas|especifico|especifica|posible|"
    r"imposible|cumple|cumplido|aprobado|aprobada|aprobacion|detallado|detallada|explicito|"
    r"explicita|explicitos|explicitas|necesita|necesitan|genera|generado|generada|generar|registrar|"
    r"seleccionado|seleccionada|seleccionar|devuelve|devolver|devuelven|marcador|marcadores|previo|"
    r"previa|previos|previas|actualizacion|traduccion|traducir|idioma|cadena|cadenas|palabra|"
    r"palabras|frase|frases|responder|respuestas|describir|explicar|explicacion|detencion|modificar|"
    r"modificacion|posicion|posiciones|columna|columnas|fila|filas|rango|rangos|espacio|espacios|"
    r"matematico|matematica|fisico|fisica|sistema|sistemas|condicion|condiciones|razonable|origen|"
    r"destinos|garantia|garantias|secuencia|secuencias|operacion|operaciones|formato|formatos|"
    r"indicar|calidad|limpieza|profesional|interfaz|terminacion)\b",
    re.IGNORECASE,
)

# Each entry must be one exact, verbatim evidence line. The source citation is
# part of the value so reviewers can distinguish evidence from product prose.
ARCHIVED_EVIDENCE_ALLOWLIST: dict[str, dict[str, str]] = {}


def test_source_and_documentation_prose_is_english() -> None:
    violations: list[str] = []
    for directory in (ROOT / "src", ROOT / "docs"):
        for path in sorted(directory.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            relative_path = path.relative_to(ROOT).as_posix()
            allowed_lines = ARCHIVED_EVIDENCE_ALLOWLIST.get(relative_path, {})
            text = path.read_text(encoding="utf-8")
            lines = text.splitlines()
            for evidence_line, citation in allowed_lines.items():
                if not citation.strip() or evidence_line not in lines:
                    violations.append(f"{relative_path}: stale or uncited archived-evidence exception")
            for line_number, line in enumerate(lines, start=1):
                if line in allowed_lines:
                    continue
                visible_line = MARKDOWN_LINK_DESTINATION.sub("](link)", line)
                if ACCENTED_SPANISH.search(visible_line):
                    violations.append(f"{relative_path}:{line_number}: Spanish diacritic: {line.strip()}")
                word = COMMON_SPANISH_WORDS.search(visible_line)
                if word:
                    violations.append(
                        f"{relative_path}:{line_number}: Spanish word {word.group(0)!r}: {line.strip()}"
                    )

    assert not violations, "Found non-English source/documentation text:\n" + "\n".join(violations[:80])
