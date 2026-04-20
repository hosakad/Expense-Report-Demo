import os
from datetime import timedelta
from flask import Flask, redirect, request, url_for, session

import constants as cns
import db_operations as db
from file_operations import save_file, delete_file
from utilities import getPendoParams, get_default_currency, generate_fullname, display_page, getRedisClient, generate_currency_expression

# a random secret used by Flask to encrypt session data cookies
app = Flask(__name__)
app.debug = True
app.secret_key = os.environ.get('FLASK_SECRET_KEY')

# Pendo API Key of this app
PENDO_API_KEY = os.environ.get('PENDO_API_KEY')
PENDO_API_KEY_2 = os.environ.get('PENDO_API_KEY_2')

def main():
    return None

@app.context_processor
def function_processor():
	def get_fullname(first_name, last_name):
		return generate_fullname(first_name, last_name)
	def get_text(msg_key):
		if getRedisClient().hexists(cns.REDIS_MESSAGES + '/' + session[cns.REDIS_LANGUAGE], msg_key):
			return getRedisClient().hget(cns.REDIS_MESSAGES + '/' + session[cns.REDIS_LANGUAGE], msg_key).decode('utf8')
		else:
			return 'MSG_MISMATCH'
	def get_currency_expression(amount, currency):
		return generate_currency_expression(amount, currency)
	return dict(pendo_api_key=PENDO_API_KEY,
							pendo_api_key_2=PENDO_API_KEY_2,
							get_fullname=get_fullname,
							role_list=cns.ROLES,
							currency_list=cns.CURRENCIES,
							get_text=get_text,
							get_currency_expression=get_currency_expression)

@app.route('/')
def index():
	if cns.SESSION_EMAIL in session:
		email = session[cns.SESSION_EMAIL]
		# if the employee is already logged in, show root page
		role = session[cns.SESSION_ROLE]
		if role == cns.ROLE_USER:
			return redirect('user_home')
		elif role == cns.ROLE_ADMIN:
			return redirect('employee_list_html')
		elif role == cns.ROLE_APPROVER:
			return redirect('approve_list_html')

	return redirect(url_for('login'))

@app.route('/error/<message_key>')
def error(message_key):
	return display_page('error.html', message_key=message_key)

@app.route('/login')
def login():
	return display_page('login.html')

@app.route('/logout')
def logout():
	# flush Pendo parameters, and keep messages and language
	session.pop(cns.SESSION_EMPLOYEE_ID, None)
	session.pop(cns.SESSION_EMAIL, None)
	session.pop(cns.SESSION_ROLE, None)
	session.pop(cns.SESSION_FULL_NAME, None)
	session.pop(cns.SESSION_COMPANY_ID, None)
	session.pop(cns.SESSION_COMPANY_NAME, None)
	session.pop(cns.SESSION_COMPANY_PLAN, None)
	return display_page('logout.html')

@app.route('/authenticate', methods=['POST'])
def authenticate():

	email = request.form['email']
	password = request.form['password']

	if email and password:
		# login succeeds
		results = db.get_employee_by_email(email, password)
		if results is not None and len(results) == 1:
			employee_id, email, role, first_name, last_name, company_id, company_name, company_plan = results[0]
			print('login as email:', email, ', company: ', company_name)
			# set Pendo parameters
			session[cns.SESSION_EMPLOYEE_ID] = str(employee_id)
			session[cns.SESSION_EMAIL] = email
			session[cns.SESSION_ROLE] = role
			session[cns.SESSION_FULL_NAME] = generate_fullname(first_name, last_name) # this requires that language has been already set
			session[cns.SESSION_COMPANY_ID] = str(company_id)
			session[cns.SESSION_COMPANY_NAME] = company_name
			session[cns.SESSION_COMPANY_PLAN] = company_plan
			session.permanent = True
			app.permanent_session_lifetime = timedelta(hours=24)
			return redirect(url_for('index'))
		else:
			# login failed
			return redirect(url_for('error', message_key=cns.MSG_EMAIL_MISMATCH))
	else:
		# email or password was null
		return redirect(url_for('error', message_key=cns.MSG_NO_EMAIL_PASSWORD))

@app.route('/user_home')
def user_home():
	if cns.SESSION_EMAIL in session:
		inprogress_records = db.get_open_expenses_count(session[cns.SESSION_EMPLOYEE_ID])
		submitted_records = db.get_reports_summary(session[cns.SESSION_EMPLOYEE_ID])
		approved_records = db.get_submitted_reports(session[cns.SESSION_EMPLOYEE_ID])
		return display_page('user_home.html', params=getPendoParams(),
													title=cns.TITLE_INDEX,
													inprogress_records=inprogress_records[0],
													submitted_records=submitted_records[0],
													approved_records=approved_records[0])
	else:
		return redirect(url_for('login'))

@app.route('/expense_list_html')
def expense_list_html():
	if cns.SESSION_EMAIL in session:
		expenses = db.get_expenses_unassigned(session[cns.SESSION_EMPLOYEE_ID])
		return display_page('expense_list.html', params=getPendoParams(), expenses=expenses, title=cns.TITLE_EXPENSE_LIST)
	else:
		return redirect(url_for('login'))

@app.route('/expense_detail_html', methods=['POST'])
def expense_detail_html():
	if cns.SESSION_EMAIL in session:
		results = db.get_expense(request.form['id'])
		if len(results) == 1:
			return display_page('expense_detail.html', params=getPendoParams(), expense=results[0], title=cns.TITLE_EXPENSE_DETAIL)
		else:
			return redirect(url_for('error', message_key=cns.MSG_NO_EXPENSE_ID_MATCH))

@app.route('/expense_new_html')
def expense_new_html():
	if cns.SESSION_EMAIL in session:
		return display_page('expense_new.html', params=getPendoParams(), title=cns.TITLE_EXPENSE_NEW, default_currency=get_default_currency())
	else:
		return redirect(url_for('login'))

@app.route('/create_expense', methods=['POST'])
def create_expense():
	if cns.SESSION_EMAIL in session:
		file = request.files.get('receipt_image')
		file_name = save_file(file)
		db.create_expense(request.form['name'], request.form['date'], request.form['amount'],
						  request.form['currency'], request.form['description'], file_name,
						  session[cns.SESSION_EMPLOYEE_ID])
		return redirect(url_for('expense_list_html'))
	else:
		return redirect(url_for('login'))

@app.route('/update_expense', methods=['POST'])
def update_expense():
	if cns.SESSION_EMAIL in session:
		db.update_expense(request.form['name'], request.form['date'], request.form['currency'],
						  request.form['amount'], request.form['description'], request.form['id'])
		return redirect(url_for('expense_list_html'))
	else:
		return redirect(url_for('login'))

@app.route('/delete_expense', methods=['POST'])
def delete_expense():
	if cns.SESSION_EMAIL in session:
		if (request.form['id']):
			receipt_image = request.form.get('receipt_image')
			delete_file(receipt_image)
			db.delete_expense(request.form['id'])
		return redirect(url_for('expense_list_html'))
	else:
		return redirect(url_for('login'))

@app.route('/delete_receipt_image', methods=['POST'])
def delete_receipt_image():
	if cns.SESSION_EMAIL in session:
		receipt_image = request.form.get('receipt_image')
		if delete_file(receipt_image):
			db.delete_receipt_image(request.form['id'])
		return redirect(url_for('expense_detail_html'), code=307)
	else:
		return redirect(url_for('login'))

@app.route('/update_receipt_image', methods=['POST'])
def update_receipt_image():
	if cns.SESSION_EMAIL in session:
		file = request.files.get('new_receipt_image')
		file_name = save_file(file)
		if file_name:
			db.update_receipt_image(file_name, request.form['id'])
		return redirect(url_for('expense_detail_html'), code=307)
	else:
		return redirect(url_for('login'))

@app.route('/report_list_html')
def report_list_html():
	if cns.SESSION_EMAIL in session:
		reports = db.get_reports(session[cns.SESSION_EMPLOYEE_ID])
		return display_page('report_list.html', params=getPendoParams(), reports=reports, title=cns.TITLE_REPORT_LIST)
	else:
		return redirect(url_for('login'))

@app.route('/report_new_html')
def report_new_html():
	if cns.SESSION_EMAIL in session:
		return display_page('report_new.html', params=getPendoParams(), title=cns.TITLE_REPORT_NEW)
	else:
		return redirect(url_for('login'))

@app.route('/create_report', methods=['POST'])
def create_report():
	if cns.SESSION_EMAIL in session:
		db.create_report(request.form['name'], session[cns.SESSION_EMPLOYEE_ID])
		return redirect(url_for('report_list_html'))
	else:
		return redirect(url_for('login'))

@app.route('/report_detail_html', methods=['POST'])
def report_detail_html():
	if cns.SESSION_EMAIL in session:
		reports = db.get_report(request.form['id'])
		expenses_open = db.get_expenses_unassigned_for_report(session[cns.SESSION_EMPLOYEE_ID])
		expenses_included = db.get_expenses_in_report(session[cns.SESSION_EMPLOYEE_ID], request.form['id'])

		if len(reports) == 1:
			return display_page('report_detail.html', params=getPendoParams(), report=reports[0], expenses_open=expenses_open, expenses_included=expenses_included, title=cns.TITLE_REPORT_DETAIL)
		else:
			return redirect(url_for('error', message_key=cns.MSG_NO_REPORT_ID_MATCH))
	else:
		return redirect(url_for('login'))

@app.route('/update_report', methods=['POST'])
def update_report():
	if cns.SESSION_EMAIL in session:
		db.update_report_name(request.form['id'], request.form['name'])
		id_added = request.form.getlist('id_added')
		if id_added:
			db.assign_expenses_to_report(request.form['id'], id_added)
		id_removed = request.form.getlist('id_removed')
		if id_removed:
			db.unassign_expenses_from_report(id_removed)
		return redirect(url_for('report_detail_html'), code=307)
	else:
		return redirect(url_for('login'))

@app.route('/delete_report', methods=['POST'])
def delete_report():
	if cns.SESSION_EMAIL in session:
		db.delete_report(request.form['id'])
		return redirect(url_for('report_list_html'))
	else:
		return redirect(url_for('login'))

@app.route('/submit_report', methods=['POST'])
def submit_report():
	if cns.SESSION_EMAIL in session:
		db.submit_report(request.form['id'])
		return redirect(url_for('expense_list_html'))
	else:
		return redirect(url_for('login'))

@app.route('/approve_list_html')
def approve_list_html():
	if cns.SESSION_EMAIL in session:
		results = db.get_approve_list(session[cns.SESSION_COMPANY_ID])
		reports_submitted = []
		reports_approved = []
		if results:
			for result in results:
				if result['status'] == cns.STATUS_SUBMITTED:
					reports_submitted.append(result.copy())
				elif result['status'] == cns.STATUS_APRROVED:
					reports_approved.append(result.copy())
		return display_page('approve_list.html', params=getPendoParams(), title=cns.TITLE_APPROVE_LIST, reports_submitted=reports_submitted, reports_approved=reports_approved)
	else:
		return redirect(url_for('login'))

@app.route('/approve_report', methods=['POST'])
def approve_report():
	if cns.SESSION_EMAIL in session:
		db.approve_report(request.form['id'])
		return redirect(url_for('approve_list_html'))
	else:
		return redirect(url_for('login'))

@app.route('/reject_report', methods=['POST'])
def reject_report():
	if cns.SESSION_EMAIL in session:
		db.reject_report(request.form['id'])
		return redirect(url_for('approve_list_html'))
	else:
		return redirect(url_for('login'))

@app.route('/employee_list_html')
def employee_list_html():
	if cns.SESSION_EMAIL in session:
		employees = db.get_employees(session[cns.SESSION_COMPANY_ID])
		return display_page('employee_list.html', params=getPendoParams(), title=cns.TITLE_EMPLOYEE_LIST, employees=employees)
	else:
		return redirect(url_for('login'))

@app.route('/employee_new_html')
def employee_new_html():
	if cns.SESSION_EMAIL in session:
		return display_page('employee_new.html', params=getPendoParams(), title=cns.TITLE_EMPLOYEE_NEW)
	else:
		return redirect(url_for('login'))

@app.route('/employee_detail_html', methods=['POST'])
def employee_detail_html():
	if cns.SESSION_EMAIL in session:
		employees = db.get_employee(request.form['id'])
		return display_page('employee_detail.html', params=getPendoParams(), title=cns.TITLE_EMPLOYEE_DETAIL, employee=employees[0])
	else:
		return redirect(url_for('login'))

@app.route('/create_employee', methods=['POST'])
def create_employee():
	if cns.SESSION_EMAIL in session:
		db.create_employee(request.form['first_name'],
						   request.form['last_name'],
						   request.form['email'],
						   request.form['password'],
						   request.form['role'],
						   session[cns.SESSION_COMPANY_ID])
		return redirect(url_for('employee_list_html'))
	else:
		return redirect(url_for('login'))

@app.route('/update_employee', methods=['POST'])
def update_employee():
	if cns.SESSION_EMAIL in session:
		db.update_employee(request.form['first_name'],
						   request.form['last_name'],
						   request.form['email'],
						   request.form['role'],
						   request.form['id'])
		return redirect(url_for('employee_list_html'))
	else:
		return redirect(url_for('login'))

@app.route('/delete_employee', methods=['POST'])
def delete_employee():
	if cns.SESSION_EMAIL in session:
		result = db.delete_employee(request.form['id'])
		if isinstance(result, Exception):
			return display_page('error.html', message_key=cns.MSG_DELETE_EMPLOYEE_FAILED, error_message=str(result))
		return redirect(url_for('employee_list_html'))
	else:
		return redirect(url_for('login'))

if __name__ == '__main__':
  main()
