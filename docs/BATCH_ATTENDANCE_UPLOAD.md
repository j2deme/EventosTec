# Subida en Batch de Asistencias

## Descripción

Funcionalidad para registrar asistencias en lote a partir de archivos TXT o XLSX que contienen números de control de estudiantes.

## Características

### Workflow de Selección

1. **Evento**: Seleccionar el evento al cual pertenece la actividad
2. **Departamento**: Filtrar actividades por departamento
3. **Actividad**: Seleccionar la actividad específica para la cual se registrarán asistencias

### Formatos de Archivo Soportados

#### Archivo TXT

- Un número de control por línea
- Ejemplo:

```
L12345678
L23456789
L34567890
```

#### Archivo XLSX/XLS

- Números de control en la primera columna
- Puede incluir o no encabezados (se procesan todas las filas)
- Ejemplo:

| Columna A |
| --------- |
| L12345678 |
| L23456789 |
| L34567890 |

### Modo Dry-Run

El modo "Dry run" permite validar el archivo sin realizar cambios en la base de datos:

- ✅ Valida que los números de control existan
- ✅ Identifica duplicados
- ✅ Muestra qué registros se crearían
- ❌ NO guarda los cambios en la base de datos

### Ejecución Real

Desmarcando "Dry run" se ejecuta la importación:

- ✅ Crea registros de asistencia
- ✅ Establece estatus "Asistió"
- ✅ Establece porcentaje de asistencia al 100%
- ✅ Actualiza registros previos si existen

## Comportamiento del Sistema

### Búsqueda de Estudiantes

1. **Base de datos local**: Se busca primero en la BD local
2. **API externa**: Si no existe localmente, se consulta la API externa
3. **Creación automática**: Si se encuentra en la API externa, se crea el registro del estudiante

### Detección de Duplicados

- ✅ El sistema verifica si ya existe una asistencia para el estudiante en la actividad
- ✅ Los duplicados se reportan como "omitidos" y NO se sobrescriben

### Actualización de Registros Previos

- Si existe un registro previo (preregistro) para el estudiante en la actividad:
  - Se marca como `attended = true`
  - Se actualiza el estatus a "Asistió"
  - Se registra la fecha de confirmación

## Reportes de Resultado

Después de procesar el archivo, se muestra un reporte con:

### Resumen

- **Creadas**: Número de asistencias creadas exitosamente
- **Omitidas**: Número de asistencias que ya existían (duplicados)
- **No encontradas**: Números de control que no se encontraron ni en BD ni en API externa

### Detalles

Tabla con información de cada número de control procesado:

- Número de control
- Nombre del estudiante
- Acción realizada (Creada/Omitida)

### Errores

Lista de errores encontrados durante el procesamiento:

- Números de control no encontrados
- Errores de lectura del archivo
- Otros errores del sistema

## API Endpoint

### `POST /api/attendances/batch`

**Autenticación**: Requiere JWT token con rol de administrador

**Parámetros (form-data)**:

- `file` (archivo): Archivo TXT o XLSX con números de control
- `activity_id` (número): ID de la actividad
- `dry_run` (string): "1" para dry-run, "0" para ejecución real (default: "1")

**Respuesta exitosa (200/201)**:

```json
{
  "message": "Batch procesado",
  "report": {
    "created": 3,
    "skipped": 1,
    "not_found": 0,
    "errors": [],
    "details": [
      {
        "control_number": "L12345678",
        "student_name": "Juan Pérez",
        "action": "created"
      },
      {
        "control_number": "L23456789",
        "student_name": "María González",
        "action": "skipped",
        "reason": "Ya existe asistencia"
      }
    ]
  }
}
```

**Códigos de estado**:

- `200`: Dry-run exitoso
- `201`: Ejecución real exitosa
- `400`: Error en parámetros o archivo
- `401`: No autenticado
- `403`: No autorizado (no es admin)
- `500`: Error del servidor

## Interfaz de Usuario

### Acceso

1. Ir a "Gestión de Asistencias" en el panel de administrador
2. Hacer clic en el botón "Subida batch" (icono de upload azul)

### Pasos para usar

1. Seleccionar Evento
2. Seleccionar Departamento
3. Seleccionar Actividad
4. Seleccionar archivo TXT o XLSX
5. (Opcional) Marcar "Dry run" para validar sin guardar
6. Hacer clic en "Procesar"
7. Revisar el reporte de resultados

### Barra de Progreso

Durante la subida se muestra una barra de progreso que indica el avance del proceso.

## Restricciones y Validaciones

### Restricciones Implementadas

- ✅ No se permiten asistencias duplicadas
- ✅ Solo se acepta un formato de archivo a la vez
- ✅ Se requiere seleccionar evento, departamento y actividad
- ✅ Los números de control deben ser válidos

### Validaciones

- Archivo no vacío
- Activity ID válido
- Números de control con formato correcto
- Estudiante existe o puede ser importado de API externa

## Casos de Uso

### Caso 1: Registro masivo después de un evento

Un administrador tiene una lista de asistentes proporcionada por el ponente y desea registrarlos rápidamente.

**Solución**: Crear un archivo TXT con los números de control y subirlo en modo real.

### Caso 2: Validación previa de lista

Un administrador desea verificar cuántos estudiantes de una lista ya están registrados.

**Solución**: Subir el archivo en modo dry-run y revisar el reporte de omitidos.

### Caso 3: Importación desde Excel

Un departamento proporciona una lista en Excel con asistentes.

**Solución**: Asegurar que los números de control estén en la primera columna y subir el archivo XLSX.

## Tests Automatizados

Se incluyen tests para:

- ✅ Subida con archivo TXT
- ✅ Subida con archivo XLSX
- ✅ Modo dry-run
- ✅ Ejecución real
- ✅ Detección de duplicados
- ✅ Manejo de archivos inválidos
- ✅ Manejo de actividad inválida

Ver: `app/tests/api/test_attendances_batch.py`

## Configuración Requerida

### Dependencias Python

- `pandas>=2.2.3`
- `openpyxl>=3.1.2`
- `requests` (para API externa)

### API Externa

La API externa de estudiantes debe estar disponible en:

```
http://apps.tecvalles.mx:8091/api/estudiantes?search={control_number}
```

## Troubleshooting

### Problema: "El archivo no contiene números de control"

**Causa**: El archivo está vacío o no tiene datos en la primera columna (XLSX)
**Solución**: Verificar que el archivo tenga datos y que estén en la primera columna

### Problema: "No encontrado en BD ni API externa"

**Causa**: El número de control no existe en ninguno de los sistemas
**Solución**: Verificar que el número de control sea correcto

### Problema: "Error de conexión con sistema externo"

**Causa**: La API externa no está disponible
**Solución**: Verificar conectividad con la API externa o esperar a que el servicio esté disponible

### Problema: Asistencias omitidas (todos)

**Causa**: Todos los estudiantes ya tienen asistencia registrada
**Solución**: Verificar en la lista de asistencias si ya están registrados

## Mantenimiento

### Actualizaciones futuras sugeridas

- [ ] Soporte para múltiples columnas en XLSX (campos adicionales)
- [ ] Importación de check-in/check-out times desde archivo
- [ ] Exportación de template XLSX vacío
- [ ] Validación previa de formato de números de control
- [ ] Logs de auditoría para importaciones masivas
- [ ] Notificaciones por email al completar importación grande

## Referencias

- Patrón de diseño basado en: `app/services/activity_service.py::create_activities_from_xlsx`
- Endpoint similar: `POST /api/activities/batch`
- Frontend similar: Modal batch en `app/templates/admin/partials/activities.html`
