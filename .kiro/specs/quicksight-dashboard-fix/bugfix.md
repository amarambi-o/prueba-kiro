# Bugfix Requirements Document

## Introduction

Al ejecutar `app/quicksight_dashboard.py`, el pipeline falla en el Paso 3 (CreateDataSet) con un `InvalidParameterValueException` porque los permisos del dataset son incompletos. Esto provoca que el dataset `ds-bank-kpi-summary` no se cree correctamente, y en consecuencia el Paso 4 (CreateAnalysis) falla con `PREPARED_SOURCE_NOT_FOUND` al no poder localizar el dataset. El script de referencia `quicksight_setup.py` ya contiene el conjunto correcto de permisos.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN `crear_dataset_kpi()` llama a `create_data_set` con el bloque `Permissions` actual THEN el sistema lanza `InvalidParameterValueException: Resultant state of ResourcePermissions on this resource is not supported` y el dataset no se crea.

1.2 WHEN el dataset `ds-bank-kpi-summary` no existe porque el Paso 3 falló THEN el sistema lanza `ResourceNotFoundException: Failed data sets: [...]:PREPARED_SOURCE_NOT_FOUND` al intentar crear el análisis en el Paso 4.

### Expected Behavior (Correct)

2.1 WHEN `crear_dataset_kpi()` llama a `create_data_set` con el conjunto completo de permisos válidos THEN el sistema SHALL crear el dataset `ds-bank-kpi-summary` sin errores y retornar su ID.

2.2 WHEN el dataset `ds-bank-kpi-summary` existe y está disponible THEN el sistema SHALL crear el análisis QuickSight referenciando el dataset correctamente sin `PREPARED_SOURCE_NOT_FOUND`.

### Unchanged Behavior (Regression Prevention)

3.1 WHEN el pipeline se ejecuta con permisos corregidos THEN el sistema SHALL CONTINUE TO crear la vista KPI en Athena (Paso 2) con el mismo comportamiento actual.

3.2 WHEN el dataset se crea correctamente THEN el sistema SHALL CONTINUE TO iniciar la ingesta SPICE con `create_ingestion` tal como lo hace hoy.

3.3 WHEN el análisis se crea correctamente THEN el sistema SHALL CONTINUE TO publicar el dashboard en el Paso 5 con las mismas opciones de publicación actuales.

3.4 WHEN `quicksight_setup.py` se ejecuta de forma independiente THEN el sistema SHALL CONTINUE TO funcionar sin cambios, ya que sus permisos (`DATASET_PERMISSIONS`) son correctos y no se modifican.
