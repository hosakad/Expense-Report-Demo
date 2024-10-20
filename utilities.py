import os
import json
import time
import requests
import redis

from flask import Flask, redirect, request, url_for, render_template, session, jsonify

import constants as cns

# a random secret used by Flask to encrypt session data cookies
app = Flask(__name__)
app.debug = True
app.secret_key = os.environ['FLASK_SECRET_KEY']

# TrackEvent Secret Key for Pendo
PENDO_TRACK_EVENT_SECRET_KEY = os.environ['PENDO_TRACK_EVENT_SECRET_KEY']

# Redis settings
redis_url = os.getenv('REDIS_URL')
pool = redis.ConnectionPool.from_url(redis_url, ssl=True, ssl_cert_reqs=None)
REDIS_client = redis.StrictRedis(connection_pool=pool)

def display_page(url_name, **arg):
	set_language(request.accept_languages.best_match(cns.SUPPORTED_LANGUAGES))
	return render_template(url_name, **arg)

def getRedisClient():
    return REDIS_client
    
def getPendoParams():
	params = {}
	params['email'] = session[cns.SESSION_EMAIL]
	params['role'] = session[cns.SESSION_ROLE]
	params['full_name'] = session[cns.SESSION_FULL_NAME]
	params['language'] = session[cns.REDIS_LANGUAGE]
	params['company_id'] = session[cns.SESSION_COMPANY_ID]
	params['company_name'] = session[cns.SESSION_COMPANY_NAME]
	params['company_plan'] = session[cns.SESSION_COMPANY_PLAN]
	return params

def set_language(language):
	print('language: ', language)
	# currently supported language; ja-JP, en-US
	lang = 'en-US' # set en_US as default
	if language == 'ja' or language == 'ja-JP':
		# ja_JP as Japanese
		lang = 'ja-JP'
	elif language == 'en':
		# if 'en' is specified, set en_US
		lang = 'en-US'
	session[cns.REDIS_LANGUAGE] = lang
	if not REDIS_client.exists(cns.REDIS_MESSAGES + '/' + lang):
		# load messages
		messages = {}
		path = 'static/json/messages_'+session[cns.REDIS_LANGUAGE]+'.json'
		with open(path) as message_file:
			messages = json.load(message_file)
		REDIS_client.hmset(cns.REDIS_MESSAGES + '/' + lang, messages)

# this should be called after language is set
# return default currenct to be used in expense
def get_default_currency():
	language = session[cns.REDIS_LANGUAGE]
	if language == 'ja-JP':
		return cns.CURRENCY_YEN
	else:
		return cns.CURRENCY_DOLLAR

# this should be called after language is set
# generage full name according to the language choosen
def generate_fullname(first_name, last_name):
	language = session[cns.REDIS_LANGUAGE]
	if language == 'ja-JP':
		# in case Japanese is used, last name comes first
		return last_name + ' ' + first_name
	else:
		return first_name + ' ' + last_name

# this should be called after language is set
# generage an expression in html according to the language choosen
def generate_currency_expression(amount, currency):
	language = session[cns.REDIS_LANGUAGE]
	if language == 'ja-JP':
		return "{:,}".format(amount) + ' ' + currency
	else:
		return currency + ' ' + "{:,.2f}".format(amount)


# Invoke Pendo API to send a track event
def send_track_event(event_name):
	if cns.SESSION_EMAIL in session:
		body = {
			"type": "track",
			"event": event_name,
			"visitorId": session[cns.SESSION_EMAIL],
			"accountId": session[cns.SESSION_COMPANY_ID],
			"timestamp": int(time.time() * 1000),
			"properties": {
				"role": session[cns.SESSION_ROLE],
				"full_name": session[cns.SESSION_FULL_NAME],
				"company_name" : session[cns.SESSION_COMPANY_NAME],
				"company_plan" : session[cns.SESSION_COMPANY_PLAN]
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

		result = requests.post(api_url, json=body, headers=header)
		try:
			content = result.json()
			return content
		except Exception as exception:
			print('exception:', exception)
			return None
	else:
		return redirect(url_for('login'))
