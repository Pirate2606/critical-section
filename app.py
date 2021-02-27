import base64
import csv
import json
import os
import re
import string
import uuid

import requests
from flask import render_template, request, redirect, url_for, session, g
from flask_login import login_user, login_required, current_user, logout_user
from werkzeug.routing import ValidationError
from flask_uploads import UploadSet, configure_uploads, IMAGES

from cli import create_db
from config import Config
from models import app, db, Users, login_manager, Register, UsersDashboard
from oauth import google, twitter

# Configuration
app.config.from_object(Config)
app.cli.add_command(create_db)
app.register_blueprint(google.blueprint, url_prefix="/login")
app.register_blueprint(twitter.blueprint, url_prefix="/login")
db.init_app(app)
login_manager.init_app(app)

# Upload Photos
photos = UploadSet('photos', IMAGES)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app.config['UPLOADED_PHOTOS_DEST'] = 'static/pictures'
configure_uploads(app, photos)

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


@app.route('/<unique_id>/registration', methods=["GET", "POST"])
@login_required
def registration(unique_id):
    register = Register()
    email = Users.query.filter_by(unique_id=unique_id).first().email
    static = os.path.join(os.path.curdir, "static")
    pictures = os.path.join(static, "data")
    country_location = os.path.join(pictures, "countries.csv")
    univ_location = os.path.join(pictures, "universities.csv")
    name = []
    temp = []
    univ = []
    with open(country_location) as f:
        csv_reader = csv.reader(f)
        for c in csv_reader:
            temp.append(c)
    for country in temp[1:]:
        name.append(country[0])
    temp = []
    with open(univ_location, encoding="utf8") as f:
        csv_reader = csv.reader(f)
        for c in csv_reader:
            temp.append(c)
    for u in temp[1:]:
        univ.append(u[1])
    if request.method == "POST":
        file = request.files['profile_pic']
        if 'profile_pic' in request.files and allowed_file(file.filename):
            image_filename = photos.save(file)
            static = os.path.join(os.path.curdir, "static")
            pictures = os.path.join(static, "pictures")
            image_location = os.path.join(pictures, image_filename)
            with open(image_location, "rb") as file:
                url = "https://api.imgbb.com/1/upload"
                payload = {
                    "key": '00a33d9bbaa2f24bf801c871894e91d4',
                    "image": base64.b64encode(file.read()),
                }
                res = requests.post(url, payload)
                str_name = ""
                for r in res:
                    str_name += r.decode("utf8")
                register.profile_pic = json.loads(str_name)['data']['url']
        else:
            register.profile_pic = "https://i.ibb.co/8mq8Tfh/default.jpg"
        register.unique_id = unique_id
        register.first_name = request.form["first_name"]
        register.last_name = request.form["last_name"]
        register.email = email
        register.mobile_num = request.form["phone_num"]
        register.country = request.form["country"]
        if request.form["college"]:
            register.university_name = request.form["college"]
        if request.form["employment"] == "student":
            register.profession = request.form["employment"]
            register.graduation_year = request.form["year"]
        else:
            register.profession = request.form["employment"]
            register.experience = request.form["year"]
            register.graduation_year = "2000"
        dashboard = UsersDashboard(unique_id=unique_id)
        db.session.add_all([register, dashboard])
        db.session.commit()
        return redirect(url_for("home"))
    return render_template("registration.html", email=email, name=name, univ=univ)


@app.route("/logout")
@login_required
def logout():
    session.pop('user_id', None)
    logout_user()
    return redirect(url_for("home"))


@app.errorhandler(404)
def page_not_found(error):
    return render_template('404.html'), 404


@app.errorhandler(403)
def restricted(error):
    return render_template('403.html'), 403


# Functions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


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
