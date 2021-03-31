import os
import requests

from flask import Flask, redirect, request, url_for, render_template
import redis
import psycopg2

# retrieve parametes for database from enrironment value
DATABASE_URL = os.environ['DATABASE_URL']
DATABASE_SCHEMA = os.environ['DATABASE_SCHEMA']
DATABASE_CONNECTION = None
cursor = getDBConnection().cursor()
cursor.execute('SET search_path TO' + DATABASE_SCHEMA)
cursor.close()

# a random secret used by Flask to encrypt session data cookies
app = Flask(__name__)
app.debug = True
app.secret_key = os.environ['FLASK_SECRET_KEY']

# Redis settings
redis_url = os.environ['REDIS_URL']
pool= redis.ConnectionPool(decode_responses=True)
redis_client = redis.StrictRedis(connection_pool=pool).from_url(redis_url)

# Redis keys
REDIS_FULL_NAME = 'USE_FULL_NAME'
REDIS_EMAIL = 'USER_EMAIL' # visitor ID
REDIS_ROLE = 'USER_ROLE'
REDIS_COMPANY_ID = 'COMPANY_ID' # account ID
REDIS_COMPANY_NAME = 'COMPANY_NAME'
REDIS_PLAN = 'COMPANY_PLAN'

# constant values to be used in app
# user roles
CONST_ROLE_ADMIN = '管理者'
CONST_ROLE_APPROVER = '承認者'
CONST_ROLE_USER = 'ユーザー'
CONST_ROLES = [CONST_ROLE_ADMIN, CONST_ROLE_APPROVER, CONST_ROLE_USER]
# account plan
CONST_PLAN = ['Advanced', 'Standard']
# 
# error messages
MSG_EMAIL_MISMATCH = 'メールアドレスとパスワードが一致しません'
MSG_NO_EMAIL_PASSWORD = 'メールアドレスまたはパスワードが入力されませんでした'

def getDBConnection():
	if DATABASE_CONNECTION is None:
		DATABASE_CONNECTION = psycopg2.connect(DATABASE_URL, sslmode='require')

	return DATABASE_CONNECTION

def getVisitorID():
	visitor_id = redis_client.get(REDIS_EMAIL)
	print("visitor_id:", visitor_id)
	if visitor_id:
		return visitor_id.decode('UTF8')
	else:
		return 'VISITOR-UNIQUE-ID'

def getAccountID():
	account_id = redis_client.get(REDIS_ACCOUNT_ID)
	print("account_id:", account_id)
	if account_id:
		return account_id.decode('UTF8')
	else:
		return 'ACCOUNT-UNIQUE-ID'

def sql_select(sql_string):

	cursor = conn.cursor()
	cursor.execute(sql_string)
	results = cursor.fetchall()
	return results

@app.route('/')
def index():
	# initialize
	email = redis_client.get(REDIS_EMAIL).decode('UTF8')
	if email:
		# if the user is already logged in, show index.html
		return_template('index.html')

	return redirect(url_for('login'))

@app.route('/error')
def error(message):
	return render_template('error.html', message=message)

@app.route('/login')
def login():
	return render_template('login.html')

@app.route('/authenticate')
def authenticate():

	email = request.form['email']
	password = request.form['password']
	if email and password:
		sql_string = 'select * from employee where email='+email+', password='+password
		results = sql_select(sql_string)
		print('results:'+results)
		if len(results) == 1:
			redis_client.set(REDIS_EMAIL, email)
			return redirect(url_for('index'))
		else:
			# login failed
			return redirect(url_for('error', message=MSG_EMAIL_MISMATCH))
	else:
		# email or password was null
		return redirect(url_for('error', message=MSG_NO_EMAIL_PASSWORD))

if __name__ == '__main__':
  main()
  getDBConnection().close()