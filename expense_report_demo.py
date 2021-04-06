import os
import requests

from flask import Flask, redirect, request, url_for, render_template
import redis
import psycopg2
from psycopg2.extras import DictCursor

# retrieve parametes for database from enrironment value
DATABASE_URL = os.environ['DATABASE_URL']
DATABASE_SCHEMA = os.environ['DATABASE_SCHEMA']
DATABASE_CONNECTION = None
DB_ENGINE = None

# a random secret used by Flask to encrypt session data cookies
app = Flask(__name__)
app.debug = True
app.secret_key = os.environ['FLASK_SECRET_KEY']

# Redis settings
redis_url = os.environ['REDIS_URL']
pool= redis.ConnectionPool(decode_responses=True)
redis_client = redis.StrictRedis(connection_pool=pool).from_url(redis_url)

# Redis keys
REDIS_EMAIL = 'EMPLOYEE_EMAIL' # visitor ID
REDIS_ROLE = 'EMPLOYEE_ROLE'
REDIS_FULL_NAME = 'EMPLOYEE_FULL_NAME'
REDIS_COMPANY_ID = 'COMPANY_ID' # account ID
REDIS_COMPANY_NAME = 'COMPANY_NAME'
REDIS_COMPANY_PLAN = 'COMPANY_PLAN'

# constant values to be used in app
# employee roles
CONST_ROLE_ADMIN = '管理者'
CONST_ROLE_APPROVER = '承認者'
CONST_ROLE_USER = 'ユーザー'
CONST_ROLES = [CONST_ROLE_ADMIN, CONST_ROLE_APPROVER, CONST_ROLE_USER]
# account plan
CONST_PLAN = ['Advanced', 'Standard']
# 
# error messages
MSG_EMAIL_MISMATCH = 'msg0'
MSG_NO_EMAIL_PASSWORD = 'msg1'
ERROR_MESSAGES = {
	MSG_EMAIL_MISMATCH : 'メールアドレスとパスワードが一致しません',
	MSG_NO_EMAIL_PASSWORD : 'メールアドレスまたはパスワードが入力されませんでした'
}

def getDBConnection():
	global DATABASE_CONNECTION
	if DATABASE_CONNECTION is None:
		DATABASE_CONNECTION = psycopg2.connect(DATABASE_URL, sslmode='require')
		cursor = DATABASE_CONNECTION.cursor()
		cursor.execute('SET search_path TO ' + DATABASE_SCHEMA)
		cursor.close()

	return DATABASE_CONNECTION

def sql_select(sql_string):
	print("execute sql:", sql_string)
	cursor = getDBConnection().cursor(cursor_factory=DictCursor)
	cursor.execute(sql_string)
	results = cursor.fetchall()
	return results

def sql_create(sql_string):
	print("execute sql:", sql_string)
	cursor = getDBConnection().cursor()
	cursor.execute(sql_string)
	getDBConnection().commit()
	return

def getPendoParams():
	params = {}
	params['email'] = redis_client.get(REDIS_EMAIL).decode('utf8')
	params['role'] = redis_client.get(REDIS_ROLE).decode('utf8')
	params['full_name'] = redis_client.get(REDIS_FULL_NAME).decode('utf8')
	params['company_id'] = redis_client.get(REDIS_COMPANY_ID).decode('utf8')
	params['company_name'] = redis_client.get(REDIS_COMPANY_NAME).decode('utf8')
	params['company_plan'] = redis_client.get(REDIS_COMPANY_PLAN).decode('utf8')
	return params

@app.route('/')
def index():
	# initialize
	email = redis_client.get(REDIS_EMAIL)
	if email:
		# if the employee is already logged in, show index.html
		print('already logged in')
		print('email:', email.decode('utf8'))
		return render_template('index.html', params=getPendoParams())

	return redirect(url_for('login'))

@app.route('/error/<message_id>')
def error(message_id):
	message = ERROR_MESSAGES[message_id]
	return render_template('error.html', message=message)

@app.route('/login')
def login():
	return render_template('login.html')

@app.route('/logout')
def logout():
	redis_client.delete(REDIS_EMAIL)
	redis_client.delete(REDIS_ROLE)
	redis_client.delete(REDIS_FULL_NAME)
	redis_client.delete(REDIS_COMPANY_ID)
	redis_client.delete(REDIS_COMPANY_NAME)
	redis_client.delete(REDIS_COMPANY_PLAN)
	return render_template('logout.html')

@app.route('/authenticate', methods=['POST'])
def authenticate():

	email = request.form['email']
	password = request.form['password']
	if email and password:
		sql_string = "select email, role, first_name, last_name, company.id as company_id,"\
					" company.name as company_name, company.plan as company_plan"\
					" from employee join company"\
					" on employee.company_id = company.id"\
					" where email='"+email+"' and password='"+password+"'"
		results = sql_select(sql_string)
		print('results:', results)
		if len(results) == 1:
			email, role, first_name, last_name, company_id, company_name, company_plan = results[0]
			print('email:', email)
			print('company_id:', company_id)
			redis_client.set(REDIS_EMAIL, email)
			redis_client.set(REDIS_ROLE, role)
			redis_client.set(REDIS_FULL_NAME, last_name + ' ' + first_name)
			redis_client.set(REDIS_COMPANY_ID, company_id)
			redis_client.set(REDIS_COMPANY_NAME, company_name)
			redis_client.set(REDIS_COMPANY_PLAN, company_plan)
			return redirect(url_for('index'))
		else:
			# login failed
			return redirect(url_for('error', message_id=MSG_EMAIL_MISMATCH))
	else:
		# email or password was null
		return redirect(url_for('error', message_id=MSG_NO_EMAIL_PASSWORD))

@app.route('/html_expense')
def html_expense():
	email = redis_client.get(REDIS_EMAIL)
	if email:
		sql_string = "select expense.id, name, date, amount, currency, description"\
					" from expense join employee"\
					" on expense.user_id = employee.id"\
					" where employee.email = '"+email.decode('utf8')+"'"
		results = sql_select(sql_string)

	return render_template('expense.html', params=getPendoParams(), expenses=results)

@app.route('/html_expense_new', methods=['POST'])
def html_expense_new():
	email = redis_client.get(REDIS_EMAIL)
	if email:
		sql_string = "select expense.id, name, date, amount, currency, description"\
					" from expense join employee"\
					" on expense.user_id = employee.id"\
					" where employee.email = '"+email.decode('utf8')+"'"
		results = sql_select(sql_string)

	return render_template('expense_new.html', params=getPendoParams(), expenses=results)

@app.route('/create_expense', methods=['POST'])
def create_expense():
	sql_string = "insert into expense(name, date, amount, currency, description, user_id)"\
							" values("+request.form['name']+","\
											+request.form['date']+","\
											+request.form['amount']+","\
											+request.form['currency']+","\
											+request.form['description']+")"
	sql_create(sql_string)

	return redirect(url_for('html_expense'))

@app.route('/html_expense_edit', methods=['POST'])
def html_expense_edit():

	expense_id = request.form['id']

	sql_string = "select id, name, date, amount, currency, description"\
				" from expense"\
				" where id = "+expense_id
	results = sql_select(sql_string)

	return render_template('expense_edit.html', params=getPendoParams(), expenses=results)

if __name__ == '__main__':
  main()
