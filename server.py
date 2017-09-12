from flask import Flask, request, redirect, render_template, session, flash
from mysqlconnection import MySQLConnector
import re
import md5
import os, binascii

app = Flask(__name__)
mysql = MySQLConnector(app,'wall')
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9.+_-]+@[a-zA-Z0-9._-]+\.[a-zA-Z]+$')
app.secret_key='secret'

@app.route('/')
def index():
	if 'user' not in session:
		return render_template('login.html')
	else:
		return render_template('welcome.html')

@app.route('/login', methods=['POST'])
def login():
	query = "SELECT * FROM users WHERE email=:email LIMIT 1"
	data = {
			'email':request.form['email']
	}
	user=mysql.query_db(query,data)

	if len(user) > 0:
		encrypted_password=md5.new(request.form['password']+user[0]['salt']).hexdigest()
		if user[0]['password']==encrypted_password:
			session['user']={
				'id':user[0]['id'],
				'first_name': user[0]['first_name'],
				'last_name': user[0]['last_name'],
				'email': user[0]['email']
			}

			return redirect('/')
		else:
			flash('Invalid password')
			return redirect('/')
	else:
		return render_template('registration.html')

@app.route('/register')
def show_register():
	return render_template('registration.html')

@app.route('/register', methods=['POST'])
def register():
	error = False

	if len(request.form['first_name'])<=2:
		error = True
		flash('Enter your first name')
	elif request.form['first_name'].isalpha()==False:
		error=True
		flash('Enter a valid first name')

	if len(request.form['last_name'])<=2:
		error = True
		flash('Enter your last name')
	elif request.form['last_name'].isalpha()==False:
		error=True
		flash('Enter a valid last name')

	if len(request.form['email'])==0:
		error=True
		flash('Enter an email')
	elif not EMAIL_REGEX.match(request.form['email']):
		error=True
		flash('Enter a valid email')
	else:
		query="SELECT email FROM users WHERE email=:email"
		data = {
			'email':request.form['email']
		}
		check=mysql.query_db(query,data)

		if len(check) > 0:
			error=True
			flash('Email already registered')

	if len(request.form['password'])==0:
		error=True
		flash('Enter a valid password')
	elif len(request.form['password']) in range(1,9):
		error=True
		flash('Password must be more than 8 characters')

	if re.search('[0-9]',request.form['password']) is None:
		error=True
		flash('Make sure your password has a number in it')

	if re.search('[A-Z]',request.form['password']) is None:
		error=True
		flash('Make sure your password has a capital letter in it')

	if request.form['confirm']==0:
		error=True
		flash('Enter a confirmation password')

	if request.form['password'] != request.form['confirm']:
		error=True
		flash('Password and confirmation must match')

	if error == False:
		salt=binascii.b2a_hex(os.urandom(15))
		hashed_pw=md5.new(request.form['password'] + salt).hexdigest()
		query = "INSERT INTO users (first_name, last_name, email, password, salt, created_at, updated_at) VALUES (:first_name, :last_name, :email, :password, :salt, NOW(), NOW())"
		data = {
			'first_name': request.form['first_name'],
			'last_name': request.form['last_name'],
			'email': request.form['email'],
			'password':hashed_pw,
			'salt':salt
		}
		users = mysql.query_db(query,data)

		query="SELECT id, first_name, last_name, email FROM users WHERE email=:email" 
		data= {
				'email': request.form['email']
		}
		current_user=mysql.query_db(query,data)

		session['user']={
				'id':current_user[0]['id'],
				'first_name': current_user[0]['first_name'],
				'last_name': current_user[0]['last_name'],
				'email': current_user[0]['email']
		}
		return render_template('welcome.html')
	else:
		return redirect('/register')

@app.route('/friends', methods=['GET','POST'])
def show_friends():
	query="SELECT friendships.user_id, users.first_name, users.last_name, DATE_FORMAT(friendships.created_at, '%M %D') AS 'day', DATE_FORMAT(friendships.created_at, '%Y') AS 'year', users.email FROM friendships JOIN users ON friendships.friend_id=users.id WHERE friendships.user_id=:user_id"
	data={
		'user_id':session['user']['id']
	}

	friends=mysql.query_db(query,data)
	return render_template('friends.html', all_friends=friends)

@app.route('/add_friend', methods=['POST'])
def add_friend():
	if request.form['email']==session['user']['email']:
		flash('Cannot add self as friend')
		return redirect('/friends')

	query="SELECT friendships.user_id, users.email FROM friendships JOIN users ON friendships.friend_id=users.id WHERE friendships.user_id=:user_id AND users.email=:email"
	data={
		'user_id':session['user']['id'],
		'email':request.form['email']
	}
	repeat_check=mysql.query_db(query,data)

	if len(repeat_check) > 0:
		flash('Friend already added')
		return redirect('/friends')

	query="SELECT * FROM users WHERE email=:email LIMIT 1"
	data={
		'email':request.form['email']
	}
	friend_check=mysql.query_db(query,data)

	if len(friend_check)==1:
		query="INSERT INTO friendships (user_id, friend_id, created_at, updated_at) VALUES (:user_id, :friend_id, NOW(), NOW())"
		data={
				'user_id':session['user']['id'],
				'friend_id':friend_check[0]['id']
		}
		friends=mysql.query_db(query,data)
	else:
		flash("Return a valid friend's email")
	return redirect('/friends')

@app.route('/wall', methods=['GET','POST'])
def wall():
	query = "SELECT messages.id, messages.message as messages_content, DATE_FORMAT(messages.created_at, '%M %e, %Y at %h: %m %p') as 'time', DATE_FORMAT(messages.created_at, '%h: %m') as 'timer', CONCAT(users.first_name,' ',users.last_name) as 'name',comments.message_id as 'comment_id', comments.comment as 'comment', DATE_FORMAT(comments.created_at, '%M %e, %Y at %h: %m %p') as 'comment_time', CONCAT(user2.first_name,' ',user2.last_name) as commenter_name FROM messages JOIN users ON messages.user_id = users.id LEFT JOIN comments ON comments.message_id = messages.id JOIN users as user2 ON comments.user_id = user2.id ORDER BY messages.id DESC"
	posts = mysql.query_db(query)

	box = {}

	for post in posts:
		if post['id'] in box:
			box[post['id']]['comments'].append(post['comment'])
		else:
			box[post['id']] = post
			box[post['id']]['comments']=[]
			box[post['id']]['comments'].append(post['comment'])

	comments = post['id']
	comments2= box[post['id']]['comment_id']
	print "This is post['id']: "+ str(post['id'])
	print comments2

	if comments==comments2:
		print box[post['id']]['comments']

	print "HAHAHA"

	for post in posts:
		print post['id']

	for box[post['id']]['comments'] in box:
		print box[post['id']]['comments']

	print box[post['id']]['comments']
	# for x in box:
	# 	print str(x)
	# 	for y in box[x]:
	# 		print str(y)
		

	return render_template('wall.html', posts = posts, box=box)

@app.route('/message', methods=['POST'])
def message():
    query = "INSERT INTO messages (message, created_at, updated_at, user_id) VALUES (:message, NOW(), NOW(), :user_id)"
    data = {
            'message': request.form['message'],
            'user_id': session['user']['id']
            }
    message = mysql.query_db(query, data)

    return redirect('/wall')

@app.route('/comment', methods=['POST'])
def comment():
    query = "INSERT INTO comments (comment, created_at, updated_at, message_id, user_id) VALUES (:comment, NOW(), NOW(), :message_id, :user_id)"
    data = {
            'comment': request.form['comment'],
            'message_id': request.form['msgid'],
            'user_id': session['user']['id']
            }

    comment = mysql.query_db(query, data)

    return redirect('/wall')

@app.route('/logout', methods=['POST'])
def logout():
	session.pop('user')
	return redirect('/')


app.run(debug=True)