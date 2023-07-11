import os
from datetime import date, timedelta
from flask import Flask, redirect, request, url_for, session

import constants as cns
from file_operations import save_file, delete_file
from db_operations import sql_execute, sql_select
from utilities import getPendoParams, get_default_currency, generate_fullname, display_page

# a random secret used by Flask to encrypt session data cookies
app = Flask(__name__)
app.debug = True
app.secret_key = os.environ['FLASK_SECRET_KEY']

def main():
    return None

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
			session[cns.SESSION_EMPLOYEE_ID] = str(employee_id)
			session[cns.SESSION_EMAIL] = email
			session[cns.SESSION_ROLE] = role
			session[cns.SESSION_FULL_NAME] = generate_fullname(first_name, last_name) # this requires that language has been already set
			session[cns.SESSION_COMPANY_ID] = str(company_id)
			session[cns.SESSION_COMPANY_NAME] = company_name
			session[cns.SESSION_COMPANY_PLAN] = company_plan
			session.permanent = True
			app.permanent_cns.SESSION_lifetime = timedelta(hours=24)
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
		# get number of expenses and reports that the user has
		sql_string = "select count(distinct expense.id), count(distinct report.id)"\
				" from expense join report"\
				" on expense.report_id = report.id"\
				" where expense.user_id = %s"\
							" and report.status = %s"
		params = (session[cns.SESSION_EMPLOYEE_ID], cns.STATUS_OPEN)

		inprogress_records = sql_select(sql_string, params)
		sql_string = "select count(distinct expense.id), count(distinct report.id)"\
				" from expense join report"\
				" on expense.report_id = report.id"\
				" where expense.user_id = %s"\
							" and report.status = %s"
		params = (session[cns.SESSION_EMPLOYEE_ID], cns.STATUS_SUBMITTED)
		submitted_records = sql_select(sql_string, params)
		sql_string = "select count(distinct expense.id), count(distinct report.id)"\
				" from expense join report"\
				" on expense.report_id = report.id"\
				" where expense.user_id = %s"\
							" and report.status = %s"
		params = (session[cns.SESSION_EMPLOYEE_ID], cns.STATUS_APRROVED)
		approved_records = sql_select(sql_string, params)
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
		expenses = []
		sql_string = "select expense.id, name, date, amount, currency, description, receipt_image"\
					" from expense join employee"\
					" on expense.user_id = employee.id"\
					" where expense.user_id = %s"\
								" and expense.report_id is null"
		params = (session[cns.SESSION_EMPLOYEE_ID],)
		expenses = sql_select(sql_string, params)
		return display_page('expense_list.html', params=getPendoParams(), expenses=expenses, title=cns.TITLE_EXPENSE_LIST)
	else:
		return redirect(url_for('login'))

@app.route('/expense_detail_html', methods=['POST'])
def expense_detail_html():
	if cns.SESSION_EMAIL in session:
		sql_string = "select id, name, date, amount, currency, description, receipt_image"\
					" from expense"\
					" where id = %s"
		params = (request.form['id'],)
		results = sql_select(sql_string, params)
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
		sql_string = "insert into expense(name, date, amount, currency, description, receipt_image, user_id)"\
								" values(%s, %s, %s, %s, %s, %s, %s)"
		params = (request.form['name'], request.form['date'], request.form['amount'], request.form['currency'], request.form['description'], file_name, session[cns.SESSION_EMPLOYEE_ID])
		sql_execute(sql_string, params)
		return redirect(url_for('expense_list_html'))
	else:
		return redirect(url_for('login'))

@app.route('/update_expense', methods=['POST'])
def update_expense():
	if cns.SESSION_EMAIL in session:
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
	if cns.SESSION_EMAIL in session:
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
	if cns.SESSION_EMAIL in session:
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
	if cns.SESSION_EMAIL in session:
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
	if cns.SESSION_EMAIL in session:
		sql_string = "select report.id, name, submit_date, approve_date, status"\
					" from report join employee"\
					" on report.user_id = employee.id"\
					" where report.user_id = %s"
		params = (session[cns.SESSION_EMPLOYEE_ID],)
		reports = sql_select(sql_string, params)
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
		# create a report record
		sql_string = "insert into report(name, user_id, status)"\
								" values(%s, %s, %s)"
		params = (request.form['name'], session[cns.SESSION_EMPLOYEE_ID], cns.STATUS_OPEN)
		sql_execute(sql_string, params)
		return redirect(url_for('report_list_html'))
	else:
		return redirect(url_for('login'))

@app.route('/report_detail_html', methods=['POST'])
def report_detail_html():
	if cns.SESSION_EMAIL in session:
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
		params = (session[cns.SESSION_EMPLOYEE_ID])
		expenses_open = sql_select(sql_string, params)
		# retrieve a list of expenses which have already been assigned in the report
		sql_string = "select expense.id, expense.name, date, amount, currency, description"\
					" from expense"\
					" join employee on expense.user_id = employee.id"\
					" join report on expense.report_id = report.id"\
					" where expense.user_id = %s"\
								" and expense.report_id = %s"\
								" and report.status = %s"
		params = (session[cns.SESSION_EMPLOYEE_ID], request.form['id'], cns.STATUS_OPEN)
		expenses_included = sql_select(sql_string, params)

		if len(reports) == 1:
			return display_page('report_detail.html', params=getPendoParams(), report=reports[0], expenses_open=expenses_open, expenses_included=expenses_included, title=cns.TITLE_REPORT_DETAIL)
		else:
			return redirect(url_for('error', message_key=cns.MSG_NO_REPORT_ID_MATCH))
	else:
		return redirect(url_for('login'))

@app.route('/update_report', methods=['POST'])
def update_report():
	if cns.SESSION_EMAIL in session:
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
	if cns.SESSION_EMAIL in session:
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
	if cns.SESSION_EMAIL in session:
		# change the status of the report to submitted
		sql_string = "update report set"\
								" submit_date = %s,"\
								" status = %s"\
								" where report.id = %s"
		params = (date.today().strftime('%Y-%m-%d'), cns.STATUS_SUBMITTED, request.form['id'])
		sql_execute(sql_string, params)
		return redirect(url_for('expense_list_html'))
	else:
		return redirect(url_for('login'))

@app.route('/approve_list_html')
def approve_list_html():
	if cns.SESSION_EMAIL in session:
		# get all reports submitted
		sql_string = "select report.id as id, report.name as name, report.status as status"\
								" from report join employee"\
								" on report.user_id = employee.id"\
								" where employee.company_id = %s and"\
										" (report.status = %s or report.status = %s)"
		params = (session[cns.SESSION_COMPANY_ID], cns.STATUS_SUBMITTED, cns.STATUS_APRROVED)
		results = sql_select(sql_string, params)
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
		sql_string = "update report set"\
								" approve_date = %s,"\
								" status = %s"\
								" where report.id = %s"
		params = (date.today().strftime('%Y-%m-%d'), cns.STATUS_APRROVED, request.form['id'])
		sql_execute(sql_string, params)
		return redirect(url_for('approve_list_html'))
	else:
		return redirect(url_for('login'))

@app.route('/reject_report', methods=['POST'])
def reject_report():
	if cns.SESSION_EMAIL in session:
		sql_string = "update report set"\
								" submit_date = null,"\
								" status = %s"\
								" where report.id = %s"
		params = (cns.STATUS_OPEN, request.form['id'])
		sql_execute(sql_string, params)
		return redirect(url_for('approve_list_html'))
	else:
		return redirect(url_for('login'))

@app.route('/employee_list_html')
def employee_list_html():
	if cns.SESSION_EMAIL in session:
		# get all employees in this company
		sql_string = "select id, email, first_name, last_name, role"\
								" from employee"\
								" where company_id = %s"
		params = (session[cns.SESSION_COMPANY_ID],)
		employees = sql_select(sql_string, params)
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
		# get details of the employee record
		sql_string = "select id, first_name, last_name, email, password, role"\
								" from employee"\
								" where id = %s"
		params = (request.form['id'],)
		employees = sql_select(sql_string, params)
		return display_page('employee_detail.html', params=getPendoParams(), title=cns.TITLE_EMPLOYEE_DETAIL, employee=employees[0])
	else:
		return redirect(url_for('login'))

@app.route('/create_employee', methods=['POST'])
def create_employee():
	if cns.SESSION_EMAIL in session:
		sql_string = "insert into employee(first_name, last_name, email, password, role, company_id)"\
								" values(%s, %s, %s, %s, %s, %s)"
		params = (request.form['first_name'], 
							request.form['last_name'], 
							request.form['email'], 
							request.form['password'], 
							request.form['role'], 
							session[cns.SESSION_COMPANY_ID])
		sql_execute(sql_string, params)
		return redirect(url_for('employee_list_html'))
	else:
		return redirect(url_for('login'))

@app.route('/update_employee', methods=['POST'])
def update_employee():
	if cns.SESSION_EMAIL in session:
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
	if cns.SESSION_EMAIL in session:
		sql_string = "delete from employee"\
								" where id = %s"
		params = (request.form['id'])
		sql_execute(sql_string, params)
		return redirect(url_for('employee_list_html'))
	else:
		return redirect(url_for('login'))

if __name__ == '__main__':
  main()
