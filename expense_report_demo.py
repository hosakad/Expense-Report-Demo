import os
import requests

from flask import Flask, redirect, request, Response, url_for, render_template
import redis

app = Flask(__name__)
app.debug = True

# A random secret used by Flask to encrypt session data cookies
app.secret_key = os.environ['FLASK_SECRET_KEY']

redis_url = os.environ['REDIS_URL']
pool= redis.ConnectionPool(decode_responses=True)
redis_client = redis.StrictRedis(connection_pool=pool).from_url(redis_url)

# Redis keys
REDIS_VISITOR_ID = "VISITOR_ID"
REDIS_ACCOUNT_ID = "ACCOUNT_ID"

def getVisitorID():
	visitor_id = redis_client.get(REDIS_VISITOR_ID)
	print("visitor_id:", visitor_id)
	if (visitor_id):
		return visitor_id.decode('UTF8')
	else:
		return 'VISITOR-UNIQUE-ID'

def getAccountID():
	account_id = redis_client.get(REDIS_ACCOUNT_ID)
	print("account_id:", account_id)
	if (account_id):
		return account_id.decode('UTF8')
	else:
		return 'ACCOUNT-UNIQUE-ID'
 
@app.route('/')
def start():
	# Initialize
	print("starting app...")

	return render_template('index.html')

@app.route('/step1')
def login():
	# Save visitor ID and account ID
	visitor_id = request.args.get('visitor_id')
	account_id = request.args.get('account_id')
	redis_client.set(REDIS_VISITOR_ID, visitor_id)
	redis_client.set(REDIS_ACCOUNT_ID, account_id)

	return render_template('step1.html', visitor_id=getVisitorID(), account_id=getAccountID())

@app.route('/step2')
def step2():

	return render_template('step2.html', visitor_id=getVisitorID(), account_id=getAccountID())

@app.route('/end')
def end():

	return render_template('end.html', visitor_id=getVisitorID(), account_id=getAccountID())

if __name__ == '__main__':
  main()