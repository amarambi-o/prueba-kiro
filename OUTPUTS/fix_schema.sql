-- Scripts generados por comparar_datos.py
-- Ejecutar sobre la BD 'demo' en SQL Server local

-- CLIENTES: agregar columnas faltantes
ALTER TABLE customer_behavior_profile ADD id_cliente NVARCHAR(100) NULL; -- Identificador unico del cliente
ALTER TABLE customer_behavior_profile ADD nombre NVARCHAR(100) NULL; -- Nombre del cliente
ALTER TABLE customer_behavior_profile ADD apellido NVARCHAR(100) NULL; -- Apellido del cliente
ALTER TABLE customer_behavior_profile ADD direccion NVARCHAR(255) NULL; -- Direccion fisica
ALTER TABLE customer_behavior_profile ADD comuna NVARCHAR(100) NULL; -- Comuna (para analisis geografico)
ALTER TABLE customer_behavior_profile ADD ciudad NVARCHAR(100) NULL; -- Ciudad

-- TRANSACCIONES: agregar columnas faltantes
ALTER TABLE card_transactions_raw ADD id_transaccion NVARCHAR(100) NULL; -- Identificador unico de la transaccion
ALTER TABLE card_transactions_raw ADD id_cliente NVARCHAR(100) NULL; -- FK al cliente
ALTER TABLE card_transactions_raw ADD monto NVARCHAR(100) NULL; -- Monto de la transaccion (positivo/negativo)
ALTER TABLE card_transactions_raw ADD saldo_posterior DECIMAL(18,2) NULL; -- Saldo tras la transaccion (para F02-vaciado)
ALTER TABLE card_transactions_raw ADD tipo_transaccion NVARCHAR(50)  NULL; -- Tipo: TRANSFERENCIA_ENVIADA, DEPOSITO, etc.
ALTER TABLE card_transactions_raw ADD canal NVARCHAR(20)  NULL; -- Canal: APP_MOVIL, WEB, SUCURSAL, ATM (para F06)
ALTER TABLE card_transactions_raw ADD geolocation NVARCHAR(50)  NULL; -- Coordenadas lat/lon (para analisis geografico)
ALTER TABLE card_transactions_raw ADD comercio_contraparte NVARCHAR(100) NULL; -- Destino/comercio (para F04-cuenta mula, F08)
ALTER TABLE card_transactions_raw ADD fecha_hora DATETIME      NULL; -- Fecha y hora exacta (para F01, F05, F07, F10)
