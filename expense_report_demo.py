import os
import json
from datetime import date, timedelta
import time
from flask import Flask, redirect, request, url_for, render_template, session, jsonify
import requests
import redis
import psycopg2
from psycopg2.extras import DictCursor
import uuid
import werkzeug

# retrieve parametes for database from enrironment value
DATABASE_URL = os.environ['DATABASE_URL']
DATABASE_SCHEMA = os.environ['DATABASE_SCHEMA']
DATABASE_CONNECTION = None
DB_ENGINE = None

# a random secret used by Flask to encrypt session data cookies
app = Flask(__name__)
app.debug = True
app.secret_key = os.environ['FLASK_SECRET_KEY']

# API Key and TrackEvent Secret Key for Pendo
PENDO_API_KEY = os.environ['PENDO_API_KEY']
PENDO_TRACK_EVENT_SECRET_KEY = os.environ['PENDO_TRACK_EVENT_SECRET_KEY']

# Redis settings
redis_url = os.environ['REDIS_URL']
pool = redis.ConnectionPool(decode_responses=True)
redis_client = redis.StrictRedis(connection_pool=pool).from_url(redis_url)

# Redis keys
REDIS_LANGUAGE = 'EMPLOYEE_LANGUAGE'
REDIS_MESSAGES = "MESSAGES" # dict for messages

# Session keys
SESSION_EMPLOYEE_ID = 'EMPLOYEE_ID'
SESSION_EMAIL = 'EMPLOYEE_EMAIL' # visitor ID
SESSION_ROLE = 'EMPLOYEE_ROLE'
SESSION_FULL_NAME = 'EMPLOYEE_FULL_NAME'
SESSION_COMPANY_ID = 'COMPANY_ID' # account ID
SESSION_COMPANY_NAME = 'COMPANY_NAME'
SESSION_COMPANY_PLAN = 'COMPANY_PLAN'

# Events
EVENT_FILE_UPLOADED = 'FileUploaded'
EVENT_FILE_DELETED = 'FileDeleted'

# supported languages
SUPPORTED_LANGUAGES = ['ja-JP', 'ja', 'en-US', 'en']

# constant values to be used in app
# employee roles
ROLE_ADMIN = 'ROLE_ADMIN'
ROLE_APPROVER = 'ROLE_APPROVER'
ROLE_USER = 'ROLE_USER'
ROLES = [ROLE_ADMIN, ROLE_APPROVER, ROLE_USER]
# currencies
CURRENCY_DOLLAR = 'CURRENCY_DOLLAR'
CURRENCY_YEN = 'CURRENCY_YEN'
CURRENCIES = [CURRENCY_DOLLAR, CURRENCY_YEN]
# account plan
ACCOUNT_PLAN = ['Advanced', 'Standard']
# root path for image files
RECEIPT_IMAGE_ROOT = 'static/images/receipt/'
# app name
APP_NAME = 'APP_NAME'
# page titles
TITLE_INDEX = 'TITLE_INDEX'
TITLE_EXPENSE_LIST = 'TITLE_EXPENSE_LIST'
TITLE_EXPENSE_NEW = 'TITLE_EXPENSE_NEW'
TITLE_EXPENSE_DETAIL = 'TITLE_EXPENSE_DETAIL'
TITLE_REPORT_LIST = 'TITLE_REPORT_LIST'
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

def sql_select(sql_string, params):
	print("execute sql:", sql_string % params)
	cursor = getDBConnection().cursor(cursor_factory=DictCursor)
	cursor.execute(sql_string, params)
	results = cursor.fetchall()
	return results

def sql_execute(sql_string, params):
	print("execute sql:", sql_string % params)
	cursor = getDBConnection().cursor()
	cursor.execute(sql_string, params)
	getDBConnection().commit()
	return

def getPendoParams():
	params = {}
	params['email'] = session[SESSION_EMAIL]
	params['role'] = session[SESSION_ROLE]
	params['full_name'] = session[SESSION_FULL_NAME]
	params['language'] = session[REDIS_LANGUAGE]
	params['company_id'] = session[SESSION_COMPANY_ID]
	params['company_name'] = session[SESSION_COMPANY_NAME]
	params['company_plan'] = session[SESSION_COMPANY_PLAN]
	return params

def set_language(language):
	# currently supported language; ja-JP, en-US
	lang = 'en-US' # set en_US as default
	if language == 'ja' or language == 'ja-JP':
		# ja_JP as Japanese
		lang = 'ja-JP'
	elif language == 'en':
		# if 'en' is specified, set en_US
		lang = 'en-US'
	session[REDIS_LANGUAGE] = lang
	redis_client.hmset(REDIS_MESSAGES, get_message_dict())

# this should be called after language is set
# return default currenct to be used in expense
def get_default_currency():
	language = session[REDIS_LANGUAGE]
	if language == 'ja-JP':
		return CURRENCY_YEN
	else:
		return CURRENCY_DOLLAR

# this should be called after language is set
# generage full name according to the language choosen
def generate_fullname(first_name, last_name):
	language = session[REDIS_LANGUAGE]
	if language == 'ja-JP':
		# in case Japanese is used, last name comes first
		return last_name + ' ' + first_name
	else:
		return first_name + ' ' + last_name

# this should be called after language is set
# generage an expression in html according to the language choosen
def generate_currency_expression(amount, currency):
	language = session[REDIS_LANGUAGE]
	if language == 'ja-JP':
		return "{:,}".format(amount) + ' ' + currency
	else:
		return currency + ' ' + "{:,.2f}".format(amount)

def get_message_dict():
	# load messages
	messages = {}
	path = 'static/json/messages_'+session[REDIS_LANGUAGE]+'.json'
	with open(path) as message_file:
		messages = json.load(message_file)
	return messages

# Save the specified file and return the name
# If the format of the file is not correct or the file doesn't exist, then return None
def save_file(file):
	if file:
		file_name = str(uuid.uuid4()) + '_' + werkzeug.utils.secure_filename(file.filename)
		file.save(RECEIPT_IMAGE_ROOT + file_name)
		print('file created at ', RECEIPT_IMAGE_ROOT + file_name)
		send_track_event(EVENT_FILE_UPLOADED)
		return file_name
	else:
		return None

# Delete the specified file
def delete_file(file_name):
	if file_name:
		file_path = RECEIPT_IMAGE_ROOT + file_name
		if os.path.exists(file_path):
			os.remove(file_path)
			send_track_event(EVENT_FILE_DELETED)
			return True
	return False

# Invoke Pendo API to send a track event
def send_track_event(event_name):
	if SESSION_EMAIL in session:
		body = {
			"type": "track",
			"event": event_name,
			"visitorId": session[SESSION_EMAIL],
			"accountId": session[SESSION_COMPANY_ID],
			"timestamp": int(time.time() * 1000),
			"properties": {
				"role": session[SESSION_ROLE],
				"full_name": session[SESSION_FULL_NAME],
				"company_name" : session[SESSION_COMPANY_NAME],
				"company_plan" : session[SESSION_COMPANY_PLAN]
			},
			"context": {
				"ip": request.remote_addr,
				"userAgent": request.user_agent.string
			}
		}
		header = {
			"Content-Type":"application/json; charset=utf-8",
			"x-pendo-integration-key":PENDO_TRACK_EVENT_SECRET_KEY
		}

		api_url = "https://app.pendo.io/data/track"

		result = requests.post(api_url, data=jsonify(body), headers=header)
		try:
			content = json.loads(result.content)
			return content
		except Exception as exception:
			print('exception:', exception)
			return None
	else:
		return redirect(url_for('login'))

@app.context_processor
def function_processor():
	def get_fullname(first_name, last_name):
		return generate_fullname(first_name, last_name)
	def get_text(msg_key):
		if redis_client.hexists(REDIS_MESSAGES, msg_key):
			return redis_client.hget(REDIS_MESSAGES, msg_key).decode('utf8')
		else:
			return 'MSG_MISMATCH'
	def get_currency_expression(amount, currency):
		return generate_currency_expression(amount, currency)
	return dict(pendo_api_key=PENDO_API_KEY,
							get_fullname=get_fullname,
							role_list=ROLES,
							currency_list=CURRENCIES,
							get_text=get_text,
							get_currency_expression=get_currency_expression)

@app.route('/')
def index():
	if redis_client.exists(REDIS_MESSAGES):
		redis_client.hmset(REDIS_MESSAGES, get_message_dict())

	if SESSION_EMAIL in session:
		email = session[SESSION_EMAIL]
		# if the employee is already logged in, show root page
		role = session[SESSION_ROLE]
		if role == ROLE_USER:
			return redirect('user_home')
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
	set_language(request.accept_languages.best_match(SUPPORTED_LANGUAGES))
	return render_template('login.html')

@app.route('/logout')
def logout():
	# flush Pendo parameters, and keep messages and language
	session.pop(SESSION_EMPLOYEE_ID, None)
	session.pop(SESSION_EMAIL, None)
	session.pop(SESSION_ROLE, None)
	session.pop(SESSION_FULL_NAME, None)
	session.pop(SESSION_COMPANY_ID, None)
	session.pop(SESSION_COMPANY_NAME, None)
	session.pop(SESSION_COMPANY_PLAN, None)
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
					" where email=%s and password=%s"
		params = (email, password)
		results = sql_select(sql_string, params)
		if len(results) == 1:
			employee_id, email, role, first_name, last_name, company_id, company_name, company_plan = results[0]
			print('login as email:', email, ', company: ', company_name)
			# set Pendo parameters
			session[SESSION_EMPLOYEE_ID] = str(employee_id)
			session[SESSION_EMAIL] = email
			session[SESSION_ROLE] = role
			session[SESSION_FULL_NAME] = generate_fullname(first_name, last_name) # this requires that language has been already set
			session[SESSION_COMPANY_ID] = str(company_id)
			session[SESSION_COMPANY_NAME] = company_name
			session[SESSION_COMPANY_PLAN] = company_plan
			session.permanent = True
			app.permanent_session_lifetime = timedelta(hours=24)
			return redirect(url_for('index'))
		else:
			# login failed
			return redirect(url_for('error', message_key=MSG_EMAIL_MISMATCH))
	else:
		# email or password was null
		return redirect(url_for('error', message_key=MSG_NO_EMAIL_PASSWORD))

@app.route('/user_home')
def user_home():
	if SESSION_EMAIL in session:
		# get number of expenses and reports that the user has
		sql_string = "select count(distinct expense.id), count(distinct report.id)"\
				" from expense join report"\
				" on expense.report_id = report.id"\
				" where expense.user_id = %s"\
							" and report.status = %s"
		params = (session[SESSION_EMPLOYEE_ID], STATUS_OPEN)

		inprogress_records = sql_select(sql_string, params)
		sql_string = "select count(distinct expense.id), count(distinct report.id)"\
				" from expense join report"\
				" on expense.report_id = report.id"\
				" where expense.user_id = %s"\
							" and report.status = %s"
		params = (session[SESSION_EMPLOYEE_ID], STATUS_SUBMITTED)
		submitted_records = sql_select(sql_string, params)
		sql_string = "select count(distinct expense.id), count(distinct report.id)"\
				" from expense join report"\
				" on expense.report_id = report.id"\
				" where expense.user_id = %s"\
							" and report.status = %s"
		params = (session[SESSION_EMPLOYEE_ID], STATUS_APRROVED)
		approved_records = sql_select(sql_string, params)
		return render_template('user_home.html', params=getPendoParams(),
																			title=TITLE_INDEX,
																			inprogress_records=inprogress_records[0],
																			submitted_records=submitted_records[0],
																			approved_records=approved_records[0])
	else:
		return redirect(url_for('login'))

@app.route('/expense_list_html')
def expense_list_html():
	if SESSION_EMAIL in session:
		expenses = []
		sql_string = "select expense.id, name, date, amount, currency, description, receipt_image"\
					" from expense join employee"\
					" on expense.user_id = employee.id"\
					" where expense.user_id = %s"\
								" and expense.report_id is null"
		params = (session[SESSION_EMPLOYEE_ID],)
		expenses = sql_select(sql_string, params)
		return render_template('expense_list.html', params=getPendoParams(), expenses=expenses, title=TITLE_EXPENSE_LIST)
	else:
		return redirect(url_for('login'))

@app.route('/expense_detail_html', methods=['POST'])
def expense_detail_html():
	if SESSION_EMAIL in session:
		sql_string = "select id, name, date, amount, currency, description, receipt_image"\
					" from expense"\
					" where id = %s"
		params = (request.form['id'],)
		results = sql_select(sql_string, params)
		if len(results) == 1:
			return render_template('expense_detail.html', params=getPendoParams(), expense=results[0], title=TITLE_EXPENSE_DETAIL)
		else:
			return redirect(url_for('error', message_key=MSG_NO_EXPENSE_ID_MATCH))

@app.route('/expense_new_html')
def expense_new_html():		
	if SESSION_EMAIL in session:
		return render_template('expense_new.html', params=getPendoParams(), title=TITLE_EXPENSE_NEW, default_currency=get_default_currency())
	else:
		return redirect(url_for('login'))

@app.route('/create_expense', methods=['POST'])
def create_expense():
	if SESSION_EMAIL in session:
		file = request.files.get('receipt_image')
		file_name = save_file(file)
		sql_string = "insert into expense(name, date, amount, currency, description, receipt_image, user_id)"\
								" values(%s, %s, %s, %s, %s, %s, %s)"
		params = (request.form['name'], request.form['date'], request.form['amount'], request.form['currency'], request.form['description'], file_name, session[SESSION_EMPLOYEE_ID])
		sql_execute(sql_string, params)
		return redirect(url_for('expense_list_html'))
	else:
		return redirect(url_for('login'))

@app.route('/update_expense', methods=['POST'])
def update_expense():
	if SESSION_EMAIL in session:
		sql_string = "update expense set"\
								" name = %s,"\
								" date = %s,"\
								" currency = %s,"\
								" amount = %s,"\
								" description = %s"\
								" where id = %s"
		params = (request.form['name'], request.form['date'], request.form['currency'], request.form['amount'], request.form['description'], request.form['id'])
		sql_execute(sql_string, params)

		return redirect(url_for('expense_detail_html'), code=307)
	else:
		return redirect(url_for('login'))

@app.route('/delete_expense', methods=['POST'])
def delete_expense():
	if SESSION_EMAIL in session:
		if (request.form['id']):
			receipt_image = request.form.get('receipt_image')
			delete_file(receipt_image)
			sql_string = "delete from expense"\
									" where id = %s"
			params = (request.form['id'],)
			sql_execute(sql_string, params)
		return redirect(url_for('expense_list_html'))
	else:
		return redirect(url_for('login'))

@app.route('/delete_receipt_image', methods=['POST'])
def delete_receipt_image():
	if SESSION_EMAIL in session:
		receipt_image = request.form.get('receipt_image')
		if delete_file(receipt_image):
			sql_string = "update expense set"\
									" receipt_image = null"\
									" where id = %s"
			params = (request.form['id'],)
			sql_execute(sql_string, params)
		return redirect(url_for('expense_detail_html'), code=307)
	else:
		return redirect(url_for('login'))

@app.route('/update_receipt_image', methods=['POST'])
def update_receipt_image():
	if SESSION_EMAIL in session:
		file = request.files.get('new_receipt_image')
		file_name = save_file(file)
		if file_name:
			sql_string = "update expense set"\
									" receipt_image = %s"\
									" where id = %s"
			params = (file_name, request.form['id'])
			sql_execute(sql_string, params)
		return redirect(url_for('expense_detail_html'), code=307)
	else:
		return redirect(url_for('login'))

@app.route('/report_list_html')
def report_list_html():
	if SESSION_EMAIL in session:
		sql_string = "select report.id, name, submit_date, approve_date, status"\
					" from report join employee"\
					" on report.user_id = employee.id"\
					" where report.user_id = %s"
		params = (session[SESSION_EMPLOYEE_ID],)
		reports = sql_select(sql_string, params)
		return render_template('report_list.html', params=getPendoParams(), reports=reports, title=TITLE_REPORT_LIST)
	else:
		return redirect(url_for('login'))

@app.route('/report_new_html')
def report_new_html():
	if SESSION_EMAIL in session:
		return render_template('report_new.html', params=getPendoParams(), title=TITLE_REPORT_NEW)
	else:
		return redirect(url_for('login'))

@app.route('/create_report', methods=['POST'])
def create_report():
	if SESSION_EMAIL in session:
		# create a report record
		sql_string = "insert into report(name, user_id, status)"\
								" values(%s, %s, %s)"
		params = (request.form['name'], session[SESSION_EMPLOYEE_ID], STATUS_OPEN)
		sql_execute(sql_string, params)
		return redirect(url_for('report_list_html'))
	else:
		return redirect(url_for('login'))

@app.route('/report_detail_html', methods=['POST'])
def report_detail_html():
	if SESSION_EMAIL in session:
		# get the specified report
		sql_string = "select id, name"\
					" from report"\
					" where id = %s"
		params = (request.form['id'],)
		reports = sql_select(sql_string, params)
		# retrieve a list of expenses which haven't been assigned to the report
		expenses = []
		sql_string = "select expense.id, name, date, amount, currency, description"\
					" from expense"\
					" join employee on expense.user_id = employee.id"\
					" where expense.user_id = %s and expense.report_id is null"
		params = (session[SESSION_EMPLOYEE_ID])
		expenses_open = sql_select(sql_string, params)
		# retrieve a list of expenses which have already been assigned in the report
		sql_string = "select expense.id, expense.name, date, amount, currency, description"\
					" from expense"\
					" join employee on expense.user_id = employee.id"\
					" join report on expense.report_id = report.id"\
					" where expense.user_id = %s"\
								" and expense.report_id = %s"\
								" and report.status = %s"
		params = (session[SESSION_EMPLOYEE_ID], request.form['id'], STATUS_OPEN)
		expenses_included = sql_select(sql_string, params)

		if len(reports) == 1:
			return render_template('report_detail.html', params=getPendoParams(), report=reports[0], expenses_open=expenses_open, expenses_included=expenses_included, title=TITLE_REPORT_DETAIL)
		else:
			return redirect(url_for('error', message_key=MSG_NO_REPORT_ID_MATCH))
	else:
		return redirect(url_for('login'))

@app.route('/update_report', methods=['POST'])
def update_report():
	if SESSION_EMAIL in session:
		# update the name of the report
		sql_string = "update report set"\
								" name = %s"\
								" where id = %s"
		params = (request.form['name'], request.form['id'])
		sql_execute(sql_string, params)
		# update the report ID in the expenses
		id_added = request.form.getlist('id_added')
		if id_added:
			# add specified expenses to this report
			sql_string = "update expense set"\
									" report_id = %s"\
									" where id in(%s)"
			params = (request.form['id'], ",".join(id_added))
			sql_execute(sql_string, params)
		# remove the report ID from the expenses
		id_removed = request.form.getlist('id_removed')
		if id_removed:
			# remove specified expenses from this report
			sql_string = "update expense set"\
									" report_id = null"\
									" where id in(%s)"
			params = (",".join(id_removed))
			sql_execute(sql_string, params)
		return redirect(url_for('report_detail_html'), code=307)
	else:
		return redirect(url_for('login'))

@app.route('/delete_report', methods=['POST'])
def delete_report():
	if SESSION_EMAIL in session:
		# remove specified expenses from this report
		sql_string = "update expense set"\
								" report_id = null"\
								" where expense.report_id = %s"
		params = (request.form['id'],)
		sql_execute(sql_string, params)
		# delete the specified report
		sql_string = "delete from report"\
								" where id = %s"
		params = (request.form['id'],)
		sql_execute(sql_string, params)
		return redirect(url_for('report_list_html'))
	else:
		return redirect(url_for('login'))

@app.route('/submit_report', methods=['POST'])
def submit_report():
	if SESSION_EMAIL in session:
		# change the status of the report to submitted
		sql_string = "update report set"\
								" submit_date = %s,"\
								" status = %s"\
								" where report.id = %s"
		params = (date.today().strftime('%Y-%m-%d'), STATUS_SUBMITTED, request.form['id'])
		sql_execute(sql_string, params)
		return redirect(url_for('expense_list_html'))
	else:
		return redirect(url_for('login'))

@app.route('/approve_list_html')
def approve_list_html():
	if SESSION_EMAIL in session:
		# get all reports submitted
		sql_string = "select report.id as id, report.name as name, report.status as status"\
								" from report join employee"\
								" on report.user_id = employee.id"\
								" where employee.company_id = %s and"\
										" (report.status = %s or report.status = %s)"
		params = (session[SESSION_COMPANY_ID], STATUS_SUBMITTED, STATUS_APRROVED)
		results = sql_select(sql_string, params)
		reports_submitted = []
		reports_approved = []
		if results:
			for result in results:
				if result['status'] == STATUS_SUBMITTED:
					reports_submitted.append(result.copy())
				elif result['status'] == STATUS_APRROVED:
					reports_approved.append(result.copy())
		return render_template('approve_list.html', params=getPendoParams(), title=TITLE_APPROVE_LIST, reports_submitted=reports_submitted, reports_approved=reports_approved)
	else:
		return redirect(url_for('login'))

@app.route('/approve_report', methods=['POST'])
def approve_report():
	if SESSION_EMAIL in session:
		sql_string = "update report set"\
								" approve_date = %s,"\
								" status = %s"\
								" where report.id = %s"
		params = (datetime.date.today().strftime('%Y-%m-%d'), STATUS_APRROVED, request.form['id'])
		sql_execute(sql_string, params)
		return redirect(url_for('approve_list_html'))
	else:
		return redirect(url_for('login'))

@app.route('/reject_report', methods=['POST'])
def reject_report():
	if SESSION_EMAIL in session:
		sql_string = "update report set"\
								" submit_date = null,"\
								" status = %s"\
								" where report.id = %s"
		params = (STATUS_OPEN, request.form['id'])
		sql_execute(sql_string, params)
		return redirect(url_for('approve_list_html'))
	else:
		return redirect(url_for('login'))

@app.route('/employee_list_html')
def employee_list_html():
	if SESSION_EMAIL in session:
		# get all employees in this company
		sql_string = "select id, email, first_name, last_name, role"\
								" from employee"\
								" where company_id = %s"
		params = (session[SESSION_COMPANY_ID],)
		employees = sql_select(sql_string, params)
		return render_template('employee_list.html', params=getPendoParams(), title=TITLE_EMPLOYEE_LIST, employees=employees)
	else:
		return redirect(url_for('login'))

@app.route('/employee_new_html')
def employee_new_html():
	if SESSION_EMAIL in session:
		return render_template('employee_new.html', params=getPendoParams(), title=TITLE_EMPLOYEE_NEW)
	else:
		return redirect(url_for('login'))

@app.route('/employee_detail_html', methods=['POST'])
def employee_detail_html():
	if SESSION_EMAIL in session:
		# get details of the employee record
		sql_string = "select id, first_name, last_name, email, password, role"\
								" from employee"\
								" where id = %s"
		params = (request.form['id'],)
		employees = sql_select(sql_string, params)
		return render_template('employee_detail.html', params=getPendoParams(), title=TITLE_EMPLOYEE_DETAIL, employee=employees[0])
	else:
		return redirect(url_for('login'))

@app.route('/create_employee', methods=['POST'])
def create_employee():
	if SESSION_EMAIL in session:
		sql_string = "insert into employee(first_name, last_name, email, password, role, company_id)"\
								" values(%s, %s, %s, %s, %s, %s)"
		params = (request.form['first_name'], 
							request.form['last_name'], 
							request.form['email'], 
							request.form['password'], 
							request.form['role'], 
							session[SESSION_COMPANY_ID])
		sql_execute(sql_string, params)
		return redirect(url_for('employee_list_html'))
	else:
		return redirect(url_for('login'))

@app.route('/update_employee', methods=['POST'])
def update_employee():
	if SESSION_EMAIL in session:
		sql_string = "update employee set"\
								" first_name = %s,"\
								" last_name = %s,"\
								" email = %s,"\
								" role = %s"\
								" where id = %s"
		params = (request.form['first_name'], 
							request.form['last_name'], 
							request.form['email'], 
							request.form['role'], 
							request.form['id'])
		sql_execute(sql_string, params)
		return redirect(url_for('employee_list_html'))
	else:
		return redirect(url_for('login'))

@app.route('/delete_employee', methods=['POST'])
def delete_employee():
	if SESSION_EMAIL in session:
		sql_string = "delete from employee"\
								" where id = %s"
		params = (request.form['id'])
		sql_execute(sql_string, params)
		return redirect(url_for('employee_list_html'))
	else:
		return redirect(url_for('login'))

if __name__ == '__main__':
  main()
