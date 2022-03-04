import os
import json
from datetime import date, timedelta
import time
from flask import Flask, redirect, request, url_for, render_template, session
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

def sql_select(sql_string):
	print("execute sql:", sql_string)
	cursor = getDBConnection().cursor(cursor_factory=DictCursor)
	cursor.execute(sql_string)
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

		result = requests.post(api_url, data=json.dumps(body), headers=header)
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

@app.route('/test', method='POST')
def test():
	# get number of expenses and reports that the user has
	sql_string = f'select count(distinct expense.id), count(distinct report.id)\
				from expense join report\
				on expense.report_id = report.id\
				where expense.user_id = {session[SESSION_EMPLOYEE_ID]}\
							and report.status = {STATUS_OPEN}'
	return sql_select(sql_string)

if __name__ == '__main__':
  main()
