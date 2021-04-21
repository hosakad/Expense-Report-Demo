import os
import datetime
import json

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
REDIS_EMPLOYEE_ID = 'EMPLOYEE_ID'
REDIS_EMAIL = 'EMPLOYEE_EMAIL' # visitor ID
REDIS_ROLE = 'EMPLOYEE_ROLE'
REDIS_FULL_NAME = 'EMPLOYEE_FULL_NAME'
REDIS_LANGUAGE = 'EMPLOYEE_LANGUAGE'
REDIS_COMPANY_ID = 'COMPANY_ID' # account ID
REDIS_COMPANY_NAME = 'COMPANY_NAME'
REDIS_COMPANY_PLAN = 'COMPANY_PLAN'
REDIS_MESSAGES = "MESSAGES" # dict for messages


# constant values to be used in app
# employee roles
ROLE_ADMIN = 'ROLE_ADMIN'
ROLE_APPROVER = 'ROLE_APPROVER'
ROLE_USER = 'ROLE_USER'
ROLES = [ROLE_ADMIN, ROLE_APPROVER, ROLE_USER]
# account plan
ACCOUNT_PLAN = ['Advanced', 'Standard']
# app name
APP_NAME = 'APP_NAME'
# page titles
TITLE_INDEX = 'TITLE_INDEX'
TITLE_EXPENSE = 'TITLE_EXPENSE'
TITLE_EXPENSE_NEW = 'TITLE_EXPENSE_NEW'
TITLE_EXPENSE_DETAIL = 'TITLE_EXPENSE_DETAIL'
TITLE_REPORT = 'TITLE_REPORT'
TITLE_REPORT_NEW = 'TITLE_REPORT_NEW'
TITLE_REPORT_DETAIL = 'TITLE_REPORT_DETAIL'
TITLE_APPROVE_LIST = 'TITLE_APPROVE_LIST'
TITLE_EMPLOYEE_LIST = 'TITLE_EMPLOYEE_LIST'
TITLE_EMPLOYEE_NEW = 'TITLE_EMPLOYEE_NEW'
TITLE_EMPLOYEE_DETAIL = 'TITLE_EMPLOYEE_DETAIL'
# report status
STATUS_OPEN = 'STATUS_OPEN'
STATUS_SUBMITTED = 'STATUS_SUBMITTED'
STATUS_APRROVED= 'STATUS_APRROVED'

# error messages
MSG_EMAIL_MISMATCH = 'MSG_EMAIL_MISMATCH'
MSG_NO_EMAIL_PASSWORD = 'MSG_NO_EMAIL_PASSWORD'
MSG_NO_EXPENSE_ID_MATCH = 'MSG_NO_EXPENSE_ID_MATCH'
MSG_NO_REPORT_ID_MATCH = 'MSG_NO_REPORT_ID_MATCH'

def getDBConnection():
	global DATABASE_CONNECTION
	if DATABASE_CONNECTION is None:
		DATABASE_CONNECTION = psycopg2.connect(DATABASE_URL, sslmode='require')
		cursor = DATABASE_CONNECTION.cursor()
		cursor.execute('SET search_path TO ' + DATABASE_SCHEMA)

	return DATABASE_CONNECTION

def sql_select(sql_string):
	print("execute sql:", sql_string)
	cursor = getDBConnection().cursor(cursor_factory=DictCursor)
	cursor.execute(sql_string)
	results = cursor.fetchall()
	return results

def sql_execute(sql_string):
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
	params['language'] = redis_client.get(REDIS_LANGUAGE).decode('utf8')
	params['company_id'] = redis_client.get(REDIS_COMPANY_ID).decode('utf8')
	params['company_name'] = redis_client.get(REDIS_COMPANY_NAME).decode('utf8')
	params['company_plan'] = redis_client.get(REDIS_COMPANY_PLAN).decode('utf8')
	return params

def get_language(language):

	# currently supported language
	# ja-JP
	# en-US
	print('language:',language)
	lang = 'en-US' # set en_US as default
	if (language == 'ja' or language == 'ja-JP'):
		# ja_JP as Japanese
		lang = 'ja-JP'
	elif (language == 'en'):
		# if 'en' is specified, set en_US
		lang = 'en-US'
	return lang

def get_message_dict():
	# load messages
	messages = {}
	path = 'static/json/messages_'+redis_client.get(REDIS_LANGUAGE).decode('utf8')+'.json'
	print('current path:', os.getcwd())
	with open(path) as message_file:
		messages = json.load(message_file)
		print('messages:', messages)
	return messages

@app.context_processor
def function_processor():
	def get_fullname(first_name, last_name):
		full_name = last_name+' '+first_name
		return full_name
	def get_text(msg_key):
		if redis_client.hexists(REDIS_MESSAGES, msg_key):
			return redis_client.hget(REDIS_MESSAGES, msg_key).decode('utf8')
		else:
			return 'MSG_MISMATCH'
	return dict(get_fullname=get_fullname,
							role_list=ROLES,
							get_text=get_text)

@app.route('/')
def index():
	email = redis_client.get(REDIS_EMAIL)
	if email:
		# if the employee is already logged in, show index.html
		role = redis_client.get(REDIS_ROLE).decode('utf8')
		if role == ROLE_USER:
			# get number of expenses and reports that the user has
			sql_string = "select count(distinct expense.id), count(distinct report.id)"\
					" from expense join report"\
					" on expense.report_id = report.id"\
					" where expense.user_id = '"+redis_client.get(REDIS_EMPLOYEE_ID).decode('utf8')+"'"\
								" and report.status = '"+STATUS_OPEN+"'"
			inprogress_records = sql_select(sql_string)
			sql_string = "select count(distinct expense.id), count(distinct report.id)"\
					" from expense join report"\
					" on expense.report_id = report.id"\
					" where expense.user_id = '"+redis_client.get(REDIS_EMPLOYEE_ID).decode('utf8')+"'"\
								" and report.status = '"+STATUS_SUBMITTED+"'"
			submitted_records = sql_select(sql_string)
			sql_string = "select count(distinct expense.id), count(distinct report.id)"\
					" from expense join report"\
					" on expense.report_id = report.id"\
					" where expense.user_id = '"+redis_client.get(REDIS_EMPLOYEE_ID).decode('utf8')+"'"\
								" and report.status = '"+STATUS_APRROVED+"'"
			approved_records = sql_select(sql_string)
			return render_template('index.html', params=getPendoParams(),
																				title=TITLE_INDEX,
																				inprogress_records=inprogress_records[0],
																				submitted_records=submitted_records[0],
																				approved_records=approved_records[0])
		elif role == ROLE_ADMIN:
			return redirect('employee_list_html')
		elif role == ROLE_APPROVER:
			return redirect('approve_list_html')
	
	return redirect(url_for('login'))

@app.route('/error/<message_key>')
def error(message_key):
	return render_template('error.html', message_key=message_key)

@app.route('/login')
def login():
	redis_client.hmset(REDIS_MESSAGES, get_message_dict())
	return render_template('login.html')

@app.route('/logout')
def logout():
	# flush Pendo parameters and keep messages
	redis_client.flushall()
	redis_client.hmset(REDIS_MESSAGES, get_message_dict())
	return render_template('logout.html')

@app.route('/authenticate', methods=['POST'])
def authenticate():

	email = request.form['email']
	password = request.form['password']
	if email and password:
		# login succeeds
		sql_string = "select employee.id, email, role, first_name, last_name, company.id as company_id,"\
					" company.name as company_name, company.plan as company_plan"\
					" from employee join company"\
					" on employee.company_id = company.id"\
					" where email='"+email+"' and password='"+password+"'"
		results = sql_select(sql_string)
		if len(results) == 1:
			employee_id, email, role, first_name, last_name, company_id, company_name, company_plan = results[0]
			print('login as email:', email, ', company: ', company_name)
			# set Pendo parameters
			redis_client.set(REDIS_EMPLOYEE_ID, employee_id)
			redis_client.set(REDIS_EMAIL, email)
			redis_client.set(REDIS_ROLE, role)
			redis_client.set(REDIS_FULL_NAME, last_name + ' ' + first_name)
			redis_client.set(REDIS_LANGUAGE, get_language(request.form['language']))
			redis_client.set(REDIS_COMPANY_ID, company_id)
			redis_client.set(REDIS_COMPANY_NAME, company_name)
			redis_client.set(REDIS_COMPANY_PLAN, company_plan)
			return redirect(url_for('index'))
		else:
			# login failed
			return redirect(url_for('error', message_key=MSG_EMAIL_MISMATCH))
	else:
		# email or password was null
		return redirect(url_for('error', message_key=MSG_NO_EMAIL_PASSWORD))

@app.route('/expense_list_html')
def expense_list_html():
	expenses = []
	sql_string = "select expense.id, name, date, amount, currency, description"\
				" from expense join employee"\
				" on expense.user_id = employee.id"\
				" where expense.user_id = '"+redis_client.get(REDIS_EMPLOYEE_ID).decode('utf8')+"'"
	expenses = sql_select(sql_string)

	return render_template('expense_list.html', params=getPendoParams(), expenses=expenses, title=TITLE_EXPENSE)

@app.route('/expense_detail_html', methods=['POST'])
def expense_detail_html():
	sql_string = "select id, name, date, amount, currency, description"\
				" from expense"\
				" where id = "+request.form['id']
	results = sql_select(sql_string)
	if len(results) == 1:
		return render_template('expense_detail.html', params=getPendoParams(), expense=results[0], title=TITLE_EXPENSE_DETAIL)
	else:
		return redirect(url_for('error', message_key=MSG_NO_EXPENSE_ID_MATCH))

@app.route('/expense_new_html')
def expense_new_html():

	return render_template('expense_new.html', params=getPendoParams(), title=TITLE_EXPENSE_NEW)

@app.route('/create_expense', methods=['POST'])
def create_expense():
	sql_string = "insert into expense(name, date, amount, currency, description, user_id)"\
							" values('"+request.form['name']+"','"\
											+request.form['date']+"',"\
											+request.form['amount']+",'"\
											+request.form['currency']+"','"\
											+request.form['description']+"','"\
											+redis_client.get(REDIS_EMPLOYEE_ID).decode('utf8')+"')"
	sql_execute(sql_string)

	return redirect(url_for('expense_list_html'))

@app.route('/update_expense', methods=['POST'])
def update_expense():
	sql_string = "update expense set"\
							" name = '"+request.form['name']+"',"\
							" date = '"+request.form['date']+"',"\
							" currency = '"+request.form['currency']+"',"\
							" amount = "+request.form['amount']+","\
							" description = '"+request.form['description']+"'"\
							" where id = "+request.form['id']+""
	sql_execute(sql_string)

	return redirect(url_for('expense_list_html'))

@app.route('/delete_expense', methods=['POST'])
def delete_expense():
	sql_string = "delete from expense"\
							" where id = "+request.form['id']+""
	sql_execute(sql_string)

	return redirect(url_for('expense_list_html'))

@app.route('/report_list_html')
def report_list_html():
	sql_string = "select report.id, name, submit_date, approve_date, status"\
				" from report join employee"\
				" on report.user_id = employee.id"\
				" where report.user_id = '"+redis_client.get(REDIS_EMPLOYEE_ID).decode('utf8')+"'"
	reports = sql_select(sql_string)

	return render_template('report_list.html', params=getPendoParams(), reports=reports, title=TITLE_REPORT)

@app.route('/report_new_html')
def report_new_html():

	return render_template('report_new.html', params=getPendoParams(), title=TITLE_REPORT_NEW)

@app.route('/create_report', methods=['POST'])
def create_report():
	# create a report record
	sql_string = "insert into report(name, user_id, status)"\
							" values('"+request.form['name']+"',"\
											" '"+redis_client.get(REDIS_EMPLOYEE_ID).decode('utf8')+"',"\
											"	'"+STATUS_OPEN+"')"
	sql_execute(sql_string)

	return redirect(url_for('report_list_html'))

@app.route('/report_detail_html', methods=['POST'])
def report_detail_html():
	sql_string = "select id, name"\
				" from report"\
				" where id = "+request.form['id']
	reports = sql_select(sql_string)

	expenses = []
	employee_id = redis_client.get(REDIS_EMPLOYEE_ID)
	sql_string = "select expense.id, name, date, amount, currency, description"\
				" from expense"\
				" join employee on expense.user_id = employee.id"\
				" where expense.user_id = '"+employee_id.decode('utf8')+"' and expense.report_id is null"
	expenses_open = sql_select(sql_string)

	sql_string = "select expense.id, expense.name, date, amount, currency, description"\
				" from expense"\
				" join employee on expense.user_id = employee.id"\
				" join report on expense.report_id = report.id"\
				" where expense.user_id = '"+employee_id.decode('utf8')+"'"\
							" and expense.report_id = '"+request.form['id']+"'"\
							" and report.status = '"+STATUS_OPEN+"'"
	expenses_included = sql_select(sql_string)

	if len(reports) == 1:
		return render_template('report_detail.html', params=getPendoParams(), report=reports[0], expenses_open=expenses_open, expenses_included=expenses_included, title=TITLE_REPORT_DETAIL)
	else:
		return redirect(url_for('error', message_key=MSG_NO_REPORT_ID_MATCH))

@app.route('/update_report', methods=['POST'])
def update_report():

	print("request.form in /update_report :", request.form)
	sql_string = "update report set"\
							" name = '"+request.form['name']+"'"\
							" where id = "+request.form['id']+""
	sql_execute(sql_string)

	id_added = request.form.getlist('id_added')
	if id_added:
		# add specified expenses to this report
		sql_string = "update expense set"\
								" report_id = '"+request.form['id']+"'"\
								" where id in("+",".join(id_added)+")"
		sql_execute(sql_string)

	id_removed = request.form.getlist('id_removed')
	if id_removed:
		# remove specified expenses from this report
		sql_string = "update expense set"\
								" report_id = null"\
								" where id in("+",".join(id_removed)+")"
		sql_execute(sql_string)

	return redirect(url_for('report_list_html'))

@app.route('/delete_report', methods=['POST'])
def delete_report():
	# remove specified expenses from this report
	sql_string = "update expense set"\
							" report_id = null"\
							" where expense.report_id = '"+request.form['id']+"'"
	sql_execute(sql_string)

	# delete the specified report
	sql_string = "delete from report"\
							" where id = '"+request.form['id']+"'"
	sql_execute(sql_string)

	return redirect(url_for('report_list_html'))

@app.route('/submit_report', methods=['POST'])
def submit_report():
	# change the status of the report to submitted
	sql_string = "update report set"\
							" submit_date = '"+datetime.date.today().strftime('%Y-%m-%d')+"',"\
							" status = '"+STATUS_SUBMITTED+"'"\
							" where report.id = '"+request.form['id']+"'"
	sql_execute(sql_string)

	return redirect(url_for('expense_list_html'))

@app.route('/approve_list_html')
def approve_list_html():
	# get all reports submitted
	sql_string = "select report.id as id, report.name as name, report.status as status"\
							" from report join employee"\
							" on report.user_id = employee.id"\
							" where employee.company_id = '"+redis_client.get(REDIS_COMPANY_ID).decode('utf8')+"' and"\
									" (report.status = '"+STATUS_SUBMITTED+"' or report.status = '"+STATUS_APRROVED+"')"
	results = sql_select(sql_string)
	reports_submitted = []
	reports_approved = []
	if results:
		for result in results:
			if result['status'] == STATUS_SUBMITTED:
				reports_submitted.append(result.copy())
			elif result['status'] == STATUS_APRROVED:
				reports_approved.append(result.copy())
	return render_template('approve_list.html', params=getPendoParams(), title=TITLE_APPROVE_LIST, reports_submitted=reports_submitted, reports_approved=reports_approved)

@app.route('/approve_report', methods=['POST'])
def approve_report():
	report_id = request.get('id')
	if report_id:
		sql_string = "update report set"\
								" approve_date = '"+datetime.date.today().strftime('%Y-%m-%d')+"',"\
								" status = '"+STATUS_APRROVED+"'"\
								" where report.id = '"+report_id+"'"
	sql_execute(sql_string)

	return redirect(url_for('approve_list_html'))

@app.route('/employee_list_html')
def employee_list_html():
	# get all employees in this company
	sql_string = "select id, email, first_name, last_name, role"\
							" from employee"\
							" where company_id = '"+redis_client.get(REDIS_COMPANY_ID).decode('utf8')+"'"
	employees = sql_select(sql_string)
	
	return render_template('employee_list.html', params=getPendoParams(), title=TITLE_EMPLOYEE_LIST, employees=employees)

@app.route('/employee_new_html')
def employee_new_html():

	return render_template('employee_new.html', params=getPendoParams(), title=TITLE_EMPLOYEE_NEW)

@app.route('/employee_detail_html', methods=['POST'])
def employee_detail_html():
	# get details of the employee record
	sql_string = "select id, first_name, last_name, email, password, role"\
							" from employee"\
							" where id = '"+request.form['id']+"'"
	employees = sql_select(sql_string)

	return render_template('employee_detail.html', params=getPendoParams(), title=TITLE_EMPLOYEE_DETAIL, employee=employees[0])

@app.route('/create_employee', methods=['POST'])
def create_employee():
	sql_string = "insert into employee(first_name, last_name, email, password, role, company_id)"\
							" values('"+request.form['first_name']+"','"\
											+request.form['last_name']+"','"\
											+request.form['email']+"','"\
											+request.form['password']+"','"\
											+request.form['role']+"','"\
											+redis_client.get(REDIS_COMPANY_ID).decode('utf8')+"')"
	sql_execute(sql_string)

	return redirect(url_for('employee_list_html'))

@app.route('/update_employee', methods=['POST'])
def update_employee():
	sql_string = "update employee set"\
							" email = '"+request.form['email']+"',"\
							" first_name = '"+request.form['first_name']+"',"\
							" last_name = '"+request.form['last_name']+"',"\
							" role = '"+request.form['role']+"'"\
							" where id = "+request.form['id']+""
	sql_execute(sql_string)

	return redirect(url_for('employee_list_html'))

@app.route('/delete_employee', methods=['POST'])
def delete_employee():
	sql_string = "delete from employee"\
							" where id = "+request.form['id']+""
	sql_execute(sql_string)

	return redirect(url_for('employee_list_html'))

if __name__ == '__main__':
  main()
