-- =============================================================
-- seed_sqlserver.sql
-- Crea e inserta 10,000+ registros ficticios en SQL Server
-- Tablas: transfers_raw, fraud_alerts_raw, debt_portfolio_raw
-- Ejecutar en la base de datos: demo
-- =============================================================

USE demo;
GO

-- =============================================================
-- 1. TRANSFERS_RAW
-- =============================================================
IF OBJECT_ID('dbo.transfers_raw', 'U') IS NOT NULL DROP TABLE dbo.transfers_raw;
GO

CREATE TABLE dbo.transfers_raw (
    transfer_id       NVARCHAR(20),
    sender_account    NVARCHAR(20),
    receiver_account  NVARCHAR(20),
    sender_name       NVARCHAR(100),
    receiver_name     NVARCHAR(100),
    sender_email      NVARCHAR(100),
    amount            NVARCHAR(20),
    currency_code     NVARCHAR(10),
    status            NVARCHAR(20),
    country_origin    NVARCHAR(5),
    country_dest      NVARCHAR(5),
    channel           NVARCHAR(20),
    bank_origin       NVARCHAR(50),
    bank_dest         NVARCHAR(50),
    created_at        NVARCHAR(30),
    updated_at        NVARCHAR(30),
    source_system     NVARCHAR(30)
);
GO

-- Insertar 10,000 transferencias usando un loop con WHILE
DECLARE @i INT = 1;
DECLARE @status NVARCHAR(20);
DECLARE @currency NVARCHAR(10);
DECLARE @country NVARCHAR(5);
DECLARE @channel NVARCHAR(20);
DECLARE @bank NVARCHAR(50);
DECLARE @amount NVARCHAR(20);
DECLARE @email NVARCHAR(100);
DECLARE @created NVARCHAR(30);

WHILE @i <= 10000
BEGIN
    -- Status con ~10% problemáticos
    SET @status = CASE (@i % 10)
        WHEN 0 THEN 'UNKNOWN'
        WHEN 1 THEN ''
        ELSE (CASE (@i % 6)
            WHEN 0 THEN 'COMPLETED'
            WHEN 1 THEN 'PENDING'
            WHEN 2 THEN 'FAILED'
            WHEN 3 THEN 'REVERSED'
            WHEN 4 THEN 'PROCESSING'
            ELSE 'CANCELLED' END)
    END;

    -- Currency con ~8% problemáticos
    SET @currency = CASE (@i % 12)
        WHEN 0 THEN 'BTC'
        WHEN 1 THEN ''
        WHEN 2 THEN 'XXX'
        ELSE (CASE (@i % 5)
            WHEN 0 THEN 'EUR'
            WHEN 1 THEN 'USD'
            WHEN 2 THEN 'COP'
            WHEN 3 THEN 'GBP'
            ELSE 'MXN' END)
    END;

    -- Country
    SET @country = CASE (@i % 11)
        WHEN 0 THEN 'XX'
        WHEN 1 THEN ''
        ELSE (CASE (@i % 7)
            WHEN 0 THEN 'ES'
            WHEN 1 THEN 'CO'
            WHEN 2 THEN 'MX'
            WHEN 3 THEN 'US'
            WHEN 4 THEN 'GB'
            WHEN 5 THEN 'DE'
            ELSE 'FR' END)
    END;

    -- Channel
    SET @channel = CASE (@i % 8)
        WHEN 0 THEN ''
        WHEN 1 THEN 'UNKNOWN'
        ELSE (CASE (@i % 4)
            WHEN 0 THEN 'APP'
            WHEN 1 THEN 'WEB'
            WHEN 2 THEN 'ATM'
            ELSE 'BRANCH' END)
    END;

    -- Bank
    SET @bank = CASE (@i % 9)
        WHEN 0 THEN ''
        ELSE (CASE (@i % 5)
            WHEN 0 THEN 'BBVA'
            WHEN 1 THEN 'Santander'
            WHEN 2 THEN 'CaixaBank'
            WHEN 3 THEN 'Bancolombia'
            ELSE 'HSBC' END)
    END;

    -- Amount con ~12% problemáticos
    SET @amount = CASE (@i % 8)
        WHEN 0 THEN ''
        WHEN 1 THEN CAST(-1 * (@i % 500 + 10) AS NVARCHAR)
        WHEN 2 THEN 'abc'
        ELSE CAST(ROUND((@i % 49990) + 10.50, 2) AS NVARCHAR)
    END;

    -- Email con ~7% corruptos
    SET @email = CASE (@i % 14)
        WHEN 0 THEN ''
        WHEN 1 THEN CONCAT('user', @i, 'bank.com')   -- sin @
        WHEN 2 THEN CONCAT('user', @i, '@')           -- sin dominio
        ELSE CONCAT('user', @i, '@bank.com')
    END;

    -- Fecha con ~4% futuras
    SET @created = CASE (@i % 25)
        WHEN 0 THEN CONVERT(NVARCHAR, DATEADD(DAY, @i % 365, GETDATE()), 120)
        WHEN 1 THEN ''
        ELSE CONVERT(NVARCHAR, DATEADD(DAY, -(@i % 730), GETDATE()), 120)
    END;

    INSERT INTO dbo.transfers_raw VALUES (
        CASE WHEN @i % 30 = 0 THEN '' ELSE CONCAT('TRF', RIGHT('0000000000' + CAST(@i AS NVARCHAR), 10)) END,
        CASE WHEN @i % 20 = 0 THEN '' ELSE CONCAT('ACC', RIGHT('0000000000' + CAST(@i * 3 AS NVARCHAR), 10)) END,
        CASE WHEN @i % 20 = 0 THEN '' ELSE CONCAT('ACC', RIGHT('0000000000' + CAST(@i * 7 AS NVARCHAR), 10)) END,
        CASE WHEN @i % 14 = 0 THEN '' ELSE CONCAT('Cliente_', @i % 500) END,
        CASE WHEN @i % 14 = 0 THEN '' ELSE CONCAT('Beneficiario_', @i % 500) END,
        @email,
        @amount,
        @currency,
        @status,
        @country,
        CASE (@i % 7)
            WHEN 0 THEN 'ES' WHEN 1 THEN 'CO' WHEN 2 THEN 'MX'
            WHEN 3 THEN 'US' WHEN 4 THEN 'GB' WHEN 5 THEN 'DE' ELSE 'FR' END,
        @channel,
        @bank,
        CASE (@i % 5)
            WHEN 0 THEN 'BBVA' WHEN 1 THEN 'Santander' WHEN 2 THEN 'CaixaBank'
            WHEN 3 THEN 'Deutsche Bank' ELSE 'HSBC' END,
        @created,
        CASE WHEN @i % 10 = 0 THEN '' ELSE CONVERT(NVARCHAR, DATEADD(DAY, -(@i % 30), GETDATE()), 120) END,
        CASE (@i % 4)
            WHEN 0 THEN 'CORE_BANKING' WHEN 1 THEN 'SWIFT'
            WHEN 2 THEN 'SEPA' ELSE '' END
    );

    SET @i = @i + 1;
END;
GO

SELECT COUNT(*) AS total_transfers FROM dbo.transfers_raw;
GO

-- =============================================================
-- 2. FRAUD_ALERTS_RAW
-- =============================================================
IF OBJECT_ID('dbo.fraud_alerts_raw', 'U') IS NOT NULL DROP TABLE dbo.fraud_alerts_raw;
GO

CREATE TABLE dbo.fraud_alerts_raw (
    alert_id          NVARCHAR(20),
    transfer_id       NVARCHAR(20),
    account_id        NVARCHAR(20),
    customer_name     NVARCHAR(100),
    customer_email    NVARCHAR(100),
    fraud_type        NVARCHAR(50),
    risk_score        NVARCHAR(10),
    amount_involved   NVARCHAR(20),
    currency_code     NVARCHAR(10),
    country_code      NVARCHAR(5),
    status            NVARCHAR(20),
    detection_method  NVARCHAR(30),
    analyst_id        NVARCHAR(15),
    created_at        NVARCHAR(30),
    resolved_at       NVARCHAR(30),
    source_system     NVARCHAR(30)
);
GO

DECLARE @i INT = 1;
WHILE @i <= 10000
BEGIN
    INSERT INTO dbo.fraud_alerts_raw VALUES (
        CASE WHEN @i % 30 = 0 THEN '' ELSE CONCAT('FRD', RIGHT('0000000000' + CAST(@i AS NVARCHAR), 10)) END,
        CASE WHEN @i % 10 = 0 THEN '' ELSE CONCAT('TRF', RIGHT('0000000000' + CAST(@i % 10000 AS NVARCHAR), 10)) END,
        CASE WHEN @i % 20 = 0 THEN '' ELSE CONCAT('ACC', RIGHT('0000000000' + CAST(@i * 3 AS NVARCHAR), 10)) END,
        CASE WHEN @i % 13 = 0 THEN '' ELSE CONCAT('Cliente_', @i % 500) END,
        CASE
            WHEN @i % 14 = 0 THEN ''
            WHEN @i % 15 = 0 THEN CONCAT('user', @i, 'bank.com')
            ELSE CONCAT('user', @i % 500, '@bank.com') END,
        CASE (@i % 7)
            WHEN 0 THEN 'CARD_NOT_PRESENT' WHEN 1 THEN 'ACCOUNT_TAKEOVER'
            WHEN 2 THEN 'SYNTHETIC_IDENTITY' WHEN 3 THEN 'MONEY_MULE'
            WHEN 4 THEN 'PHISHING' WHEN 5 THEN '' ELSE 'UNKNOWN_PATTERN' END,
        CASE
            WHEN @i % 8 = 0 THEN ''
            WHEN @i % 9 = 0 THEN '-10'
            WHEN @i % 10 = 0 THEN '150'
            ELSE CAST(ROUND((@i % 100) * 1.0, 1) AS NVARCHAR) END,
        CASE
            WHEN @i % 9 = 0 THEN ''
            ELSE CAST(ROUND((@i % 99900) + 100.0, 2) AS NVARCHAR) END,
        CASE (@i % 6)
            WHEN 0 THEN 'EUR' WHEN 1 THEN 'USD' WHEN 2 THEN 'COP'
            WHEN 3 THEN '' WHEN 4 THEN 'BTC' ELSE 'GBP' END,
        CASE (@i % 9)
            WHEN 0 THEN '' WHEN 1 THEN 'XX'
            ELSE (CASE (@i % 5)
                WHEN 0 THEN 'ES' WHEN 1 THEN 'CO' WHEN 2 THEN 'MX'
                WHEN 3 THEN 'US' ELSE 'GB' END) END,
        CASE (@i % 7)
            WHEN 0 THEN 'OPEN' WHEN 1 THEN 'INVESTIGATING' WHEN 2 THEN 'CONFIRMED'
            WHEN 3 THEN 'FALSE_POSITIVE' WHEN 4 THEN 'CLOSED'
            WHEN 5 THEN '' ELSE 'UNKNOWN' END,
        CASE (@i % 5)
            WHEN 0 THEN 'ML_MODEL' WHEN 1 THEN 'RULE_ENGINE'
            WHEN 2 THEN 'MANUAL' WHEN 3 THEN 'THIRD_PARTY' ELSE '' END,
        CASE WHEN @i % 6 = 0 THEN '' ELSE CONCAT('ANL', RIGHT('000000' + CAST(@i % 50 AS NVARCHAR), 6)) END,
        CASE
            WHEN @i % 25 = 0 THEN CONVERT(NVARCHAR, DATEADD(DAY, @i % 180, GETDATE()), 120)
            WHEN @i % 20 = 0 THEN ''
            ELSE CONVERT(NVARCHAR, DATEADD(DAY, -(@i % 730), GETDATE()), 120) END,
        CASE WHEN @i % 5 = 0 THEN '' ELSE CONVERT(NVARCHAR, DATEADD(DAY, -(@i % 60), GETDATE()), 120) END,
        CASE (@i % 4)
            WHEN 0 THEN 'FRAUD_ENGINE' WHEN 1 THEN 'AML_SYSTEM'
            WHEN 2 THEN 'MANUAL' ELSE '' END
    );
    SET @i = @i + 1;
END;
GO

SELECT COUNT(*) AS total_fraud_alerts FROM dbo.fraud_alerts_raw;
GO

-- =============================================================
-- 3. DEBT_PORTFOLIO_RAW
-- =============================================================
IF OBJECT_ID('dbo.debt_portfolio_raw', 'U') IS NOT NULL DROP TABLE dbo.debt_portfolio_raw;
GO

CREATE TABLE dbo.debt_portfolio_raw (
    debt_id             NVARCHAR(20),
    customer_id         NVARCHAR(20),
    customer_name       NVARCHAR(100),
    customer_email      NVARCHAR(100),
    debt_type           NVARCHAR(30),
    principal_amount    NVARCHAR(20),
    outstanding_balance NVARCHAR(20),
    interest_rate_pct   NVARCHAR(10),
    currency_code       NVARCHAR(10),
    status              NVARCHAR(20),
    risk_level          NVARCHAR(20),
    country_code        NVARCHAR(5),
    origination_date    NVARCHAR(30),
    maturity_date       NVARCHAR(30),
    last_payment_date   NVARCHAR(30),
    days_overdue        NVARCHAR(10),
    source_system       NVARCHAR(30)
);
GO

DECLARE @i INT = 1;
WHILE @i <= 10000
BEGIN
    INSERT INTO dbo.debt_portfolio_raw VALUES (
        CASE WHEN @i % 30 = 0 THEN '' ELSE CONCAT('DBT', RIGHT('0000000000' + CAST(@i AS NVARCHAR), 10)) END,
        CASE WHEN @i % 20 = 0 THEN '' ELSE CONCAT('CUS', RIGHT('0000000000' + CAST(@i % 5000 AS NVARCHAR), 10)) END,
        CASE WHEN @i % 13 = 0 THEN '' ELSE CONCAT('Cliente_', @i % 500) END,
        CASE
            WHEN @i % 14 = 0 THEN ''
            WHEN @i % 16 = 0 THEN CONCAT('user', @i, 'bank.com')
            ELSE CONCAT('user', @i % 500, '@bank.com') END,
        CASE (@i % 6)
            WHEN 0 THEN 'MORTGAGE' WHEN 1 THEN 'PERSONAL_LOAN'
            WHEN 2 THEN 'CREDIT_CARD' WHEN 3 THEN 'AUTO_LOAN'
            WHEN 4 THEN 'STUDENT_LOAN' ELSE '' END,
        CASE
            WHEN @i % 10 = 0 THEN ''
            WHEN @i % 11 = 0 THEN CAST(-1000 AS NVARCHAR)
            WHEN @i % 12 = 0 THEN 'abc'
            ELSE CAST(ROUND((@i % 499000) + 1000.0, 2) AS NVARCHAR) END,
        CASE
            WHEN @i % 9 = 0 THEN ''
            ELSE CAST(ROUND((@i % 499000) * 0.7, 2) AS NVARCHAR) END,
        CASE
            WHEN @i % 11 = 0 THEN ''
            WHEN @i % 13 = 0 THEN '-5'
            WHEN @i % 14 = 0 THEN '200'
            ELSE CAST(ROUND(1.5 + (@i % 235) * 0.1, 2) AS NVARCHAR) END,
        CASE (@i % 7)
            WHEN 0 THEN 'EUR' WHEN 1 THEN 'USD' WHEN 2 THEN 'COP'
            WHEN 3 THEN '' WHEN 4 THEN 'GBP' WHEN 5 THEN 'MXN' ELSE 'XXX' END,
        CASE (@i % 9)
            WHEN 0 THEN 'CURRENT' WHEN 1 THEN 'OVERDUE_30' WHEN 2 THEN 'OVERDUE_60'
            WHEN 3 THEN 'OVERDUE_90' WHEN 4 THEN 'DEFAULT' WHEN 5 THEN 'WRITTEN_OFF'
            WHEN 6 THEN 'RESTRUCTURED' WHEN 7 THEN '' ELSE 'UNKNOWN' END,
        CASE (@i % 6)
            WHEN 0 THEN 'LOW' WHEN 1 THEN 'MEDIUM' WHEN 2 THEN 'HIGH'
            WHEN 3 THEN 'CRITICAL' WHEN 4 THEN '' ELSE 'UNKNOWN' END,
        CASE (@i % 9)
            WHEN 0 THEN '' WHEN 1 THEN 'XX'
            ELSE (CASE (@i % 5)
                WHEN 0 THEN 'ES' WHEN 1 THEN 'CO' WHEN 2 THEN 'MX'
                WHEN 3 THEN 'US' ELSE 'GB' END) END,
        CASE WHEN @i % 15 = 0 THEN ''
             ELSE CONVERT(NVARCHAR, DATEADD(DAY, -(@i % 1825), GETDATE()), 120) END,
        CASE WHEN @i % 12 = 0 THEN ''
             ELSE CONVERT(NVARCHAR, DATEADD(DAY, (@i % 3650), GETDATE()), 120) END,
        CASE WHEN @i % 10 = 0 THEN ''
             ELSE CONVERT(NVARCHAR, DATEADD(DAY, -(@i % 365), GETDATE()), 120) END,
        CASE
            WHEN @i % 8 = 0 THEN ''
            WHEN @i % 9 = 0 THEN '-5'
            ELSE CAST((@i % 180) AS NVARCHAR) END,
        CASE (@i % 4)
            WHEN 0 THEN 'LOAN_SYSTEM' WHEN 1 THEN 'CORE_BANKING'
            WHEN 2 THEN 'LEGACY_CRM' ELSE '' END
    );
    SET @i = @i + 1;
END;
GO

SELECT COUNT(*) AS total_debt_portfolio FROM dbo.debt_portfolio_raw;
GO

PRINT 'Seed completado: transfers_raw, fraud_alerts_raw, debt_portfolio_raw — 10,000 registros cada una.';
GO
