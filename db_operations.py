import os
import psycopg2
from psycopg2 import InterfaceError
from psycopg2.extras import DictCursor

# retrieve parametes for database from enrironment value
DATABASE_URL = os.environ['DATABASE_URL']
DATABASE_SCHEMA = os.environ['DATABASE_SCHEMA']
DATABASE_CONNECTION = None

def getDBConnection():
    global DATABASE_CONNECTION 
	# Check if the existing connection is alive
    if DATABASE_CONNECTION is None or DATABASE_CONNECTION.closed != 0:
        # SSLモード'require'を指定して新しい接続を確立
        DATABASE_CONNECTION = psycopg2.connect(DATABASE_URL, sslmode='require')
        with DATABASE_CONNECTION.cursor() as cursor:
            cursor.execute(f"SET search_path TO {DATABASE_SCHEMA};")
    return DATABASE_CONNECTION

def sql_select(sql_string, params):
    print("Preparing to execute SQL:", sql_string, "with params:", params)
    cursor = None
    try:
        cursor = getDBConnection().cursor(cursor_factory=DictCursor)
        cursor.execute(sql_string, params) 
        results = cursor.fetchall()
        return results
    except Exception as e:
        print("Error during SQL execution:", e)
    finally:
        if cursor is not None:
            cursor.close()


def sql_execute(sql_string, params):
    print("Preparing to execute SQL:", sql_string, "with params:", params)
    connection = None
    cursor = None
    try:
        connection = getDBConnection()
        cursor = connection.cursor()
        cursor.execute(sql_string, params) 
        connection.commit()
    except Exception as e:
        print("Error during SQL execution:", e)
        if connection is not None:
            connection.rollback()
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()