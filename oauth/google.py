import uuid

from flask import flash, session, redirect, url_for
from flask_dance.consumer import oauth_authorized, oauth_error
from flask_dance.consumer.storage.sqla import SQLAlchemyStorage
from flask_dance.contrib.google import make_google_blueprint
from flask_login import current_user, login_user
from sqlalchemy.orm.exc import NoResultFound

from models import db, Users, OAuth

blueprint = make_google_blueprint(
    scope=["profile", "email"],
    storage=SQLAlchemyStorage(OAuth, db.session, user=current_user),
    redirect_to="check_login",
)


# create/login local user on successful OAuth login
@oauth_authorized.connect_via(blueprint)
def google_logged_in(blueprint, token):
    if not token:
        flash("Failed to log in.", category="error")
        return False

    resp = blueprint.session.get("/oauth2/v1/userinfo")
    if not resp.ok:
        msg = "Failed to fetch user info."
        flash(msg, category="error")
        return False

    info = resp.json()
    user_id = info["id"]

    # Find this OAuth token in the database, or create it
    query = OAuth.query.filter_by(provider=blueprint.name, provider_user_id=user_id)
    try:
        oauth = query.one()
    except NoResultFound:
        oauth = OAuth(provider=blueprint.name, provider_user_id=user_id, token=token)

    if oauth.user:
        session['user_id'] = oauth.user_id
        login_user(oauth.user)
    else:
        # Create a new local user account for this user
        unique_id = uuid.uuid4().hex[:8]
        if Users.query.filter_by(email=info["email"]).first() is not None:
            flash("This email is already registered with other account.")
            return redirect(url_for('sign_in'))
        u_name = info["email"].split("@")[0]
        user = Users(unique_id, info["email"], info["name"], None, None, u_name, info["email"], None)
        # Associate the new local user account with the OAuth token
        oauth.user = user
        # Save and commit our database models
        db.session.add_all([user, oauth])
        db.session.commit()
        # Log in the new local user account
        session['user_id'] = Users.query.filter_by(unique_id=unique_id).first().id
        login_user(user)

    # Disable Flask-Dance's default behavior for saving the OAuth token
    return False


# notify on OAuth provider error
@oauth_error.connect_via(blueprint)
def google_error(blueprint, message, response):
    msg = "OAuth error from {name}! " "message={message} response={response}".format(
        name=blueprint.name, message=message, response=response
    )
    flash(msg, category="error")
