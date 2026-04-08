import pyodbc, json, warnings
warnings.filterwarnings("ignore")

conn = pyodbc.connect(
    "DRIVER={ODBC Driver 17 for SQL Server};SERVER=(local);DATABASE=demo;"
    "Trusted_Connection=yes;TrustServerCertificate=yes;"
)
cursor = conn.cursor()

# FKs
cursor.execute("""
    SELECT
        fk.name,
        OBJECT_SCHEMA_NAME(fk.parent_object_id)      child_schema,
        OBJECT_NAME(fk.parent_object_id)              child_table,
        COL_NAME(fkc.parent_object_id, fkc.parent_column_id) child_col,
        OBJECT_SCHEMA_NAME(fk.referenced_object_id)  parent_schema,
        OBJECT_NAME(fk.referenced_object_id)          parent_table,
        COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) parent_col
    FROM sys.foreign_keys fk
    JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id = fk.object_id
    ORDER BY child_table, parent_table
""")
fks = [{"fk": r[0], "child_schema": r[1], "child_table": r[2], "child_col": r[3],
        "parent_schema": r[4], "parent_table": r[5], "parent_col": r[6]}
       for r in cursor.fetchall()]

# Columnas por tabla
cursor.execute("""
    SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, DATA_TYPE, IS_NULLABLE,
           COLUMNPROPERTY(OBJECT_ID(TABLE_SCHEMA+'.'+TABLE_NAME), COLUMN_NAME, 'IsIdentity') is_pk
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA NOT IN ('sys','INFORMATION_SCHEMA')
    ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION
""")
cols = {}
for r in cursor.fetchall():
    key = f"{r[0]}.{r[1]}"
    cols.setdefault(key, []).append({"col": r[2], "type": r[3], "nullable": r[4], "is_pk": bool(r[5])})

conn.close()

print("FK_JSON:", json.dumps(fks))
print("COL_JSON:", json.dumps(cols))
