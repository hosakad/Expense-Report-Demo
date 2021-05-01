# Expense-Report-Demo
 
## What's this?
This is a web-based application intended to use in a demo of Pendo. It's a simple expense report app that has miniature functionalies of real one. The Pendo agent script is installed along with `header.html` in this package.

## How it works
There are 3 roles defined in this app and each role has their own UI for the following actions:
### User
* Create/modify/delete expenses
* Create/modify/delete reports
* Add expenses to a report
* Submit a report for approval  
Users can handle only expenses and reports that they created. They can't see others' expenses or reports.
### Approver
* Approve/reject reports  
Approvers can see only reports submitted by users who are in the same company. There is no functionality to add a reason of approval or rejection in the report.
### Admin
* Create/modify/delete accounts (User/Approver/Admin)  
Admins can create accounts only in their company. The first admin should be created by directly inserting a record in DB. 

## How to set up in you environment
You need to install database and redis along with this app. You also need to make sure if your environment to run this app has Python packages described in requirement.txt. The following environment variables must be referred from os.environ in `expense_report_demo.py`:
* FLASK_SECRET_KEY
* DATABASE_SCHEMA
* DATABASE_URL
* PENDO_API_KEY
* REDIS_URL

# Data model
![Data Model](data_diagram.jpg)

## Localization
### Language support
Currently it supports Japanese and English. If you would like to add another language, please modify code as follows:  
**expense_report_demo.py**
* Add code to handle the new language(s) in `set_language()`
* Update a list `SUPPORT_LANGUAGES`
**json/messages_xx-XX.json**
* Add a new file `messages_xx-XX.json` referring to files of supported languages

### Currency expression
In case you woule like to use currency other than Yen and Dolloar, please modify code as follows:
**expense_report_demo.py**
* Add a new constant variable starting "CURRENCY_" followings variables `CURRENCY_DOLLAR` and `CURRENCY_YEN`
* Update a list `CURRENCIES`
* Update `get_default_currency()` and `generate_currency_expression`

### Full name expression
In case the language requires full name displayed in Last name and First name order like Japanese, please modify code as follows:
**expense_report_demo.py**
* Update `generate_fullname()`