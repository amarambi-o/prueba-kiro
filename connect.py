
"""-- BD PostgreSQL 
"""
"""--------------------------------------------------------------"""
""" import psycopg2
import boto3

password = "demonttdata123"

conn = None
try:
    conn = psycopg2.connect(
        host='demo-database.c96e62w2u2wr.us-east-2.rds.amazonaws.com',
        port=5432,
        database='postgres',
        user='userdemo',
        password=password,
        sslmode='verify-full',
    sslrootcert='./global-bundle.pem'
    )
    cur = conn.cursor()
    cur.execute('SELECT version();')
    print(cur.fetchone()[0])
    cur.close()
except Exception as e:
    print(f"Database error: {e}")
    raise
finally:
    if conn:
        conn.close()
 """


"""-- BD MySQL """
"""--------------------------------------------------------------"""

import mysql.connector
import boto3

password = "demonttdata123"

conn = None
try:
    conn = mysql.connector.connect(
        host='demo-rds-kiro.c96e62w2u2wr.us-east-2.rds.amazonaws.com',
        port=3306,
        database='mysql',
        user='admin',
        password=password,
        ssl_disabled=False,
        autocommit=True,
    ssl_ca='./global-bundle.pem'
    )
    cur = conn.cursor()
    cur.execute('SELECT VERSION();')
    print(cur.fetchone()[0])
    cur.close()
except Exception as e:
    print(f"Database error: {e}")
    raise
finally:
    if conn:
        conn.close()