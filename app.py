import base64
import csv
import json
import os
import re
import string
import uuid
from datetime import datetime

import requests
from flask import render_template, request, redirect, url_for, session, g, abort
from flask_login import login_user, login_required, current_user, logout_user
from werkzeug.routing import ValidationError
from flask_uploads import UploadSet, configure_uploads, IMAGES

from cli import create_db
from config import Config
from models import app, db, Users, login_manager, Register, UsersDashboard, Contests
from oauth import google, twitter

# Configuration
from sendMail import send_mail, send_approval_mail

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


@app.route("/")
def home():
    if not session.get('user_id'):
        return render_template("home.html")
    else:
        user_name = Users.query.filter_by(id=session['user_id']).first().user_name
        is_admin = Users.query.filter_by(id=session['user_id']).first().is_admin
        return render_template("home.html", user_name=user_name, is_admin=is_admin)


@app.route('/admin/contests')
@login_required
def admin():
    g.user = current_user.get_id()
    if g.user:
        user_id = int(g.user)
        user = Users.query.get(user_id)
        if user.is_admin:
            contest_id = request.args.get("c")
            action = request.args.get("a")
            if contest_id:
                contests = Contests.query.filter_by(contest_id=int(contest_id)).first()
                posted_by = contests.posted_by
                unique_id = Users.query.filter_by(user_name=posted_by).first().unique_id
                dashboard = UsersDashboard.query.filter_by(unique_id=unique_id).first()
                if action == "approve":
                    dashboard.points += 10
                    dashboard.contest_posted += 1
                    contests.approved = 1
                elif action == "cancel":
                    dashboard.points -= 5
                    dashboard.contest_posted += 1
                    contests.cancelled = 1
                db.session.add_all([contests, dashboard])
                db.session.commit()
            contests = Contests.query.all()
            return render_template("admin.html", contests=contests)
        else:
            abort(403)


@app.route('/contest/<category>')
def contest(category):
    contests = Contests().query.all()
    for con in contests:
        status = check_contest_status(con.start_date_time, con.end_date_time)
        if status == con.contest_status:
            continue
        else:
            con.contest_status = status
            db.session.commit()
    contest_category = Contests().query.filter_by(contest_status=category, approved=True).all()
    formatted_date = []
    for cont in contest_category:
        if cont.contest_status == "upcoming":
            dt = cont.start_date_time
        else:
            dt = cont.end_date_time
        end_date = dt.split("T")[0].split('-')
        month_name = datetime(2020, int(end_date[1]), 1).strftime("%b")
        date = str(month_name) + ', ' + str(end_date[2]) + " " + str(end_date[0])
        end_time = dt.split("T")[1]
        time = str(end_time[:2]) + ":" + str(end_time[3:])
        formatted_date.append(date + " " + time)

    total_items = len(contest_category)
    number_of_rows = (total_items // 3) + 1
    if not session.get('user_id'):
        return render_template("contests.html",
                               contests=contest_category,
                               category=category,
                               number_of_rows=number_of_rows,
                               total_items=total_items,
                               formatted_date=formatted_date)
    else:
        user_name = Users.query.filter_by(id=session['user_id']).first().user_name
        is_admin = Users.query.filter_by(id=session['user_id']).first().is_admin
        return render_template("contests.html",
                               contests=contest_category,
                               category=category,
                               number_of_rows=number_of_rows,
                               total_items=total_items,
                               user_name=user_name,
                               is_admin=is_admin,
                               formatted_date=formatted_date)


@app.route('/create_contest', methods=["GET", "POST"])
@login_required
def create_contest():
    contests = Contests()
    if contests.query.all() is not None:
        length = len(contests.query.all())
    else:
        length = 0
    if request.method == "POST":
        file = request.files['contest_pic']
        if 'contest_pic' in request.files and allowed_file(file.filename):
            contests.contest_id = length + 1
            contests.contest_name = request.form["name"]
            contests.contest_url = request.form["url"]
            contests.contest_type = request.form["type"]
            contests.start_date_time = request.form["start"]
            contests.end_date_time = request.form["end"]
            contests.contest_status = check_contest_status(request.form["start"], request.form["end"])
            contests.hosted_on = request.form["hosted"]
            contests.posted_by = Users.query.filter_by(id=session["user_id"]).first().user_name
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
                contests.contest_pic = json.loads(str_name)['data']['url']
            db.session.add(contests)
            db.session.commit()
            send_approval_mail()
        return redirect(url_for("home"))
    if not session.get('user_id'):
        return redirect(url_for("signup"))
    else:
        user_name = Users.query.filter_by(id=session['user_id']).first().user_name
        is_admin = Users.query.filter_by(id=session['user_id']).first().is_admin
        return render_template("register-contest.html", user_name=user_name, is_admin=is_admin)


@app.route('/ongoing')
def ongoing():
    return {"success": True}


@app.route('/upcoming')
def upcoming():
    return {"success": True}


@app.route('/previous')
def previous():
    return {"success": True}


@app.route('/user/<user_name>', methods=["GET", "POST"])
@login_required
def profile(user_name):
    if user_name != Users.query.filter_by(id=session['user_id']).first().user_name:
        abort(403)
    user = Users.query.filter_by(user_name=user_name).first()
    register = Register.query.filter_by(unique_id=user.unique_id).first()
    contests = Contests.query.filter_by(posted_by=user_name).all()
    points = UsersDashboard.query.filter_by(unique_id=user.unique_id).first().points
    date = []
    for con in contests:
        posted_on = con.posted_on
        post_date = posted_on.strftime("%d-%m-%Y")
        time = posted_on.strftime("%H:%M:%S")
        date_time = post_date + " | " + time
        start_date = con.start_date_time.split("T")[0]
        start_time = con.start_date_time.split("T")[1]
        start_date_time = start_date + " | " + start_time
        end_date = con.end_date_time.split("T")[0]
        end_time = con.end_date_time.split("T")[1]
        end_date_time = end_date + " | " + end_time
        date.append([date_time, start_date_time, end_date_time])
    if request.method == "POST":
        file = request.files['new_profile_pic']
        if 'new_profile_pic' in request.files and allowed_file(file.filename):
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
                db.session.commit()
    user_name = Users.query.filter_by(id=session['user_id']).first().user_name
    is_admin = Users.query.filter_by(id=session['user_id']).first().is_admin
    return render_template("profile.html",
                           register=register,
                           user_name=user_name,
                           contests=contests,
                           date=date,
                           is_admin=is_admin,
                           points=points)


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


@app.route('/contact_us', methods=["GET", "POST"])
def contact_us():
    if request.method == "POST":
        name = request.form['txtName']
        email = request.form['txtEmail']
        phone = request.form['txtPhone']
        msg = request.form['txtMsg']
        send_mail(name, email, phone, msg)
    if not session.get('user_id'):
        return render_template('contact-us.html')
    else:
        return render_template('contact-us.html',
                               user_name=Users.query.filter_by(id=session['user_id']).first().user_name,
                               unique_id=Users.query.filter_by(id=session.get('user_id')).first().unique_id,
                               is_admin=Users.query.filter_by(id=session.get('user_id')).first().is_admin)


@app.route('/about_us')
def about_us():
    if not session.get('user_id'):
        return render_template('about-us.html')
    else:
        return render_template('about-us.html',
                               user_name=Users.query.filter_by(id=session['user_id']).first().user_name,
                               unique_id=Users.query.filter_by(id=session.get('user_id')).first().unique_id,
                               is_admin=Users.query.filter_by(id=session.get('user_id')).first().is_admin)


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


def check_contest_status(start, end):
    start_date = start.split("T")[0]
    start_time = start.split("T")[1]
    end_date = end.split("T")[0]
    end_time = end.split("T")[1]
    start_datetime = datetime(int(start_date[0:4]), int(start_date[5:7]), int(start_date[8:]), int(start_time[:2]),
                              int(start_time[3:]))
    end_datetime = datetime(int(end_date[0:4]), int(end_date[5:7]), int(end_date[8:]), int(end_time[:2]),
                            int(end_time[3:]))
    if start_datetime > end_datetime:
        return False
    if datetime.now() < start_datetime:
        return "upcoming"
    elif start_datetime < datetime.now() < end_datetime:
        return "ongoing"
    elif datetime.now() > end_datetime:
        return "previous"


if __name__ == '__main__':
    app.run(debug=True)
