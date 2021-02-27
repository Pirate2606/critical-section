import os
import re
import string
import uuid

from flask import render_template, request, redirect, url_for, session, g
from flask_login import login_user, login_required, current_user
from werkzeug.routing import ValidationError

from cli import create_db
from config import Config
from models import app, db, Users, login_manager, Register
from oauth import google, twitter


app.config.from_object(Config)
app.cli.add_command(create_db)
app.register_blueprint(google.blueprint, url_prefix="/login")
app.register_blueprint(twitter.blueprint, url_prefix="/login")
db.init_app(app)
login_manager.init_app(app)

# enabling insecure login for OAuth login
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'


@app.route('/')
def home():
    return render_template('home.html')


@app.route("/check_login")
@login_required
def check_login():
    g.user = current_user.get_id()
    if g.user:
        user_id = int(g.user)
        user = Users.query.get(user_id)
        unique_id = user.unique_id
        has_registered = Register.query.filter_by(unique_id=unique_id).first()
        if has_registered is not None:
            return redirect(url_for('home'))
        return redirect(url_for('registration', unique_id=unique_id))


@app.route('/sign_up', methods=['GET', 'POST'])
def signup():
    email_flag = False
    username_flag = False
    password_flag = False

    if request.method == "POST":
        user_name = request.form['username']
        email = request.form['email']
        password = request.form['password']

        password_flag = check_password(password)
        try:
            email_flag = check_mail(email)
        except ValidationError:
            email_flag = True

        try:
            username_flag = check_username(user_name)
        except ValidationError:
            username_flag = True

        if not username_flag and not email_flag and not password_flag and password_flag != "short":
            # Entering data into Database (Register table)
            unique_id = uuid.uuid4().hex[:8]
            user = Users(unique_id, None, None, None, None, user_name, email, password)
            db.session.add(user)
            db.session.commit()
            session['user_id'] = user.id
            login_user(user)

            return redirect(url_for('check_login'))

    return render_template('sign-up.html',
                           email_flag=email_flag,
                           username_flag=username_flag,
                           password_flag=password_flag)


@app.route('/sign_in', methods=['GET', 'POST'])
def sign_in():
    flag = False
    if request.method == "POST":
        user = Users.query.filter_by(email=request.form['username']).first()
        if user is None:
            user = Users.query.filter_by(user_name=request.form['username']).first()
        if user is not None:
            if user.check_password(request.form['password']):
                user = Users.query.filter_by(email=user.email).first()
                session['user_id'] = user.id
                login_user(user)
                return redirect(url_for("home"))
            else:
                flag = True
        else:
            flag = True
    return render_template('sign-in.html', flag=flag)


@app.errorhandler(404)
def page_not_found(error):
    return render_template('404.html'), 404


@app.errorhandler(403)
def restricted(error):
    return render_template('403.html'), 403


# Functions
def check_mail(data):
    if Users.query.filter_by(email=data).first():
        raise ValidationError('Your email is already registered.')
    else:
        return False


def check_username(data):
    if Users.query.filter_by(user_name=data).first():
        raise ValidationError('This username is already registered.')
    else:
        return False


def check_password(data):
    special_char = string.punctuation
    if len(data) < 6:
        return "short"
    elif not re.search("[a-zA-Z]", data):
        return True
    elif not re.search("[0-9]", data):
        return True
    for char in data:
        if char in special_char:
            break
    else:
        return True
    return False


if __name__ == '__main__':
    app.run(debug=True)
