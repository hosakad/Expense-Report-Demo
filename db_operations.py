import os
import psycopg2
from psycopg2.extras import DictCursor

# retrieve parametes for database from enrironment value
DATABASE_URL = os.environ['DATABASE_URL']
DATABASE_SCHEMA = os.environ['DATABASE_SCHEMA']
DATABASE_CONNECTION = None

def getDBConnection():
	global DATABASE_CONNECTION
	# Check if the existing connection is alive
	try:
		DATABASE_CONNECTION.ping()
	except (AttributeError, InterfaceError):
		DATABASE_CONNECTION = None

	if DATABASE_CONNECTION is None:
		DATABASE_CONNECTION = psycopg2.connect(DATABASE_URL, sslmode='require')
		cursor = DATABASE_CONNECTION.cursor()
		cursor.execute('SET search_path TO ' + DATABASE_SCHEMA)
		cursor.close()

	return DATABASE_CONNECTION

def sql_select(sql_string, params):
	print("execute sql:", sql_string % params)
	cursor = None
	try:
		cursor = getDBConnection().cursor(cursor_factory=DictCursor)
		cursor.execute(sql_string, params)
		results = cursor.fetchall()
		return results
	finally:
		if cursor is not None:
			cursor.close()

def sql_execute(sql_string, params):
    print('execute sql:', sql_string % params)
    cursor = None
    try:
        cursor = getDBConnection().cursor()
        cursor.execute(sql_string, params)
        getDBConnection().commit()
    finally:
        if cursor is not None:
            cursor.close()