from datetime import datetime

from flask_dance.consumer.storage.sqla import OAuthConsumerMixin
from flask_login import LoginManager, UserMixin
from flask_sqlalchemy import SQLAlchemy
from flask import Flask
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
db = SQLAlchemy()


class Contests(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contest_id = db.Column(db.Integer, unique=True)
    contest_name = db.Column(db.String(256))
    contest_url = db.Column(db.String(256))
    contest_type = db.Column(db.String(256))
    contest_status = db.Column(db.String(50))
    contest_pic = db.Column(db.String(50))
    start_date_time = db.Column(db.String(256))
    end_date_time = db.Column(db.String(256))
    hosted_on = db.Column(db.String(256))
    posted_by = db.Column(db.String(8))
    posted_on = db.Column(db.DateTime, default=datetime.now())
    approved = db.Column(db.Boolean(), default=False)
    cancelled = db.Column(db.Boolean(), default=False)


class UsersDashboard(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    unique_id = db.Column(db.String(8), unique=True)
    points = db.Column(db.Integer, default=200)
    contest_posted = db.Column(db.Integer, default=0)


class Register(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    unique_id = db.Column(db.String(8), unique=True)
    first_name = db.Column(db.String(256))
    last_name = db.Column(db.String(256))
    email = db.Column(db.String(256), unique=True)
    university_name = db.Column(db.String(256))
    profession = db.Column(db.String(50))
    graduation_year = db.Column(db.String(10))
    experience = db.Column(db.String(10), default=0)
    mobile_num = db.Column(db.String(20), unique=True)
    country = db.Column(db.String(50))
    profile_pic = db.Column(db.String(256))
    date_joined = db.Column(db.DateTime, default=datetime.now())


class Users(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    unique_id = db.Column(db.String(8), unique=True)
    google_email = db.Column(db.String(256), unique=True)
    google_name = db.Column(db.String(256))
    twitter_user_name = db.Column(db.String(256), unique=True)
    twitter_name = db.Column(db.String(256))
    user_name = db.Column(db.String(256), unique=True)
    email = db.Column(db.String(256), unique=True)
    password = db.Column(db.String(256))
    is_admin = db.Column(db.Boolean(), default=False)

    def __init__(self, unique_id, google_email, google_name, twitter_user_name, twitter_name, user_name, email,
                 password):
        self.unique_id = unique_id
        self.google_email = google_email
        self.google_name = google_name
        self.twitter_user_name = twitter_user_name
        self.twitter_name = twitter_name
        self.user_name = user_name
        self.email = email
        if password is not None:
            self.password = generate_password_hash(password)
        else:
            self.password = password

    def check_password(self, password):
        return check_password_hash(self.password, password)


class OAuth(OAuthConsumerMixin, db.Model):
    provider_user_id = db.Column(db.String(256), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey(Users.id), nullable=False)
    user = db.relationship(Users)


login_manager = LoginManager()
login_manager.login_view = 'signup'


@login_manager.user_loader
def load_user(user_id):
    return Users.query.get(int(user_id))
