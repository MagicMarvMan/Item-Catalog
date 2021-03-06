#!/usr/bin/env python3

from flask import Flask, render_template, request
from flask import redirect, jsonify, url_for, flash
from functools import wraps
from sqlalchemy import create_engine, asc, desc
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import NoResultFound
from database_setup import Base, User, Category, Item
from flask import session as login_session
import random
import string
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests
from flask_oauthlib.client import OAuth, OAuthException
import html

app = Flask(__name__)

oauth = OAuth(app)

app.config['GOOGLE_ID'] = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']

APPLICATION_NAME = "Restaurant Menu Application"

app.config['GOOGLE_SECRET'] = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_secret']

app.config['GITHUB_ID'] = json.loads(
    open('gh_client_secrets.json', 'r').read())['client_id']
app.config['GITHUB_SECRET'] = json.loads(
    open('gh_client_secrets.json', 'r').read())['client_secret']

app.config['FACEBOOK_ID'] = json.loads(
    open('fb_client_secrets.json', 'r').read())['web']['app_id']
app.config['FACEBOOK_SECRET'] = json.loads(
    open('fb_client_secrets.json', 'r').read())['web']['app_secret']

app.config['SECRET_KEY'] = "UaGGGuWqikQaMIZ1JCn6vJXHIK003YBKlqk8sdzn"

app.debug = True
app.secret_key = app.config.get('SECRET_KEY')

google = oauth.remote_app(
    'google',
    consumer_key=app.config.get('GOOGLE_ID'),
    consumer_secret=app.config.get('GOOGLE_SECRET'),
    request_token_params={
        'scope': 'email'
    },
    base_url='https://www.googleapis.com/oauth2/v1/',
    request_token_url=None,
    access_token_method='POST',
    access_token_url='https://accounts.google.com/o/oauth2/token',
    authorize_url='https://accounts.google.com/o/oauth2/auth',
)

github = oauth.remote_app(
    'github',
    consumer_key=app.config.get('GITHUB_ID'),
    consumer_secret=app.config.get('GITHUB_SECRET'),
    request_token_params={'scope': 'user:email'},
    base_url='https://api.github.com/',
    request_token_url=None,
    access_token_method='POST',
    access_token_url='https://github.com/login/oauth/access_token',
    authorize_url='https://github.com/login/oauth/authorize'
)

facebook = oauth.remote_app(
    'facebook',
    consumer_key=app.config.get('FACEBOOK_ID'),
    consumer_secret=app.config.get('FACEBOOK_SECRET'),
    request_token_params={'scope': 'email'},
    base_url='https://graph.facebook.com',
    request_token_url=None,
    access_token_url='/oauth/access_token',
    access_token_method='GET',
    authorize_url='https://www.facebook.com/dialog/oauth'
)


# <UTIL>
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' in login_session:
            return f(*args, **kwargs)
        else:
            flash("You are not allowed to access there")
            return redirect('/login')
    return decorated_function

# OAUTH helper functions


@google.tokengetter
def get_google_oauth_token():
    return login_session["token"]


@github.tokengetter
def get_github_oauth_token():
    return login_session["token"]


@facebook.tokengetter
def get_facebook_oauth_token():
    return login_session["token"]


# Connect to Database and create database session
engine = create_engine('sqlite:///itemcatalog.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()


@app.errorhandler(404)
def page_not_found(e):
    return(render_template("error.html",
                           error=404,
                           login_session=login_session),
           404)


@app.errorhandler(410)
def page_gone(e):
    return(render_template("error.html",
                           error=410,
                           login_session=login_session),
           410)


@app.errorhandler(403)
def page_forbidden(e):
    return(render_template("error.html",
                           error=403,
                           login_session=login_session),
           403)


@app.errorhandler(500)
def page_server_error(e):
    return(render_template("error.html",
                           error=500,
                           login_session=login_session),
           500)


@app.route("/")
@app.route("/index")
@app.route("/feed")
@app.route("/feed/index")
def index():
    latest = session.query(Item).order_by(desc(Item.id)).limit(10)
    categories = session.query(Category).order_by(Category.id)
    return render_template("feed.html",
                           latest=latest,
                           categories=categories,
                           login_session=login_session)


@app.route("/users/list")
@app.route("/users/list/index")
def userlist():
    users = session.query(User).all()
    return render_template("userlist.html",
                           users=users,
                           login_session=login_session)


@app.route("/api/categories.json")
@app.route("/api/categories")
def categoriesJson():
    categories = session.query(Category)
    return jsonify(Categories=[c.serialize for c in categories])


@app.route("/api/category/<int:category_id>.json")
@app.route("/api/category/<int:category_id>")
def getCategoryAPI(category_id):
    Catalog = session.query(Category).filter_by(id=category_id).one()
    CatalogItems = session.query(Item).filter_by(category_id=category_id)
    return jsonify(Meta=Catalog.serialize,
                   Items=[i.serialize for i in CatalogItems])


@app.route("/api/item/<int:item_id>.json")
@app.route("/api/item/<int:item_id>")
def getItemAPI(item_id):
    SItem = session.query(Item).filter_by(id=item_id).one()
    return jsonify(SItem.serialize)


@app.route("/category/<int:category_id>")
@app.route("/category/<int:category_id>/index")
def showCategory(category_id):
    try:
        Items = session.query(Item).filter_by(
            category_id=category_id).order_by(Item.id)
        CategoryMeta = session.query(Category).filter_by(id=category_id).one()
    except NoResultFound:
        flash("The requested item was not found!")
        return redirect("/", code=302)
    else:
        return render_template("category.html",
                               items=Items,
                               category=CategoryMeta,
                               login_session=login_session)


@app.route("/category/<int:category_id>/<int:item_id>")
@app.route("/category/<int:category_id>/<int:item_id>/index")
def showItem(category_id, item_id):
    try:
        SearchedItem = session.query(Item).filter_by(
            category_id=category_id, id=item_id).one()
    except NoResultFound:
        flash("The requested item was not found!")
        return redirect("/", code=302)
    else:
        return render_template("item.html",
                               item=SearchedItem,
                               login_session=login_session)


@app.route("/category/<int:category_id>/<int:item_id>/edit",
           methods=["POST", "GET"])
@app.route("/category/<int:category_id>/<int:item_id>/edit/index",
           methods=["POST", "GET"])
@app.route("/category/<int:category_id>/<int:item_id>/index/edit",
           methods=["POST", "GET"])
@app.route("/category/<int:category_id>/<int:item_id>/index/edit/index",
           methods=["POST", "GET"])
@login_required
def editItem(category_id, item_id):
    try:
        SearchedItem = session.query(Item).filter_by(
            category_id=category_id, id=item_id).one()
    except NoResultFound:
        flash("The requested item can't be found!")
        return redirect("/", code=302)
    else:
        if(login_session["user_id"] == SearchedItem.user_id):
            if(request.method == "POST"):
                if(request.form["name"]):
                    SearchedItem.name = request.form["name"]
                if(request.form["description"]):
                    SearchedItem.description = request.form["description"]
                session.add(SearchedItem)
                session.commit()
                flash("The item has been edited!")
                return redirect("/category/" +
                                str(category_id)+"/"+str(item_id),
                                code=302)
            else:
                return render_template("edit-item.html",
                                       item=SearchedItem,
                                       login_session=login_session)
        else:
            flash("This is not your item!")
            return redirect("/category/"+str(category_id)+"/"+str(item_id),
                            code=302)


@app.route("/category/<int:category_id>/<int:item_id>/delete")
@app.route("/category/<int:category_id>/<int:item_id>/delete/index")
@app.route("/category/<int:category_id>/<int:item_id>/index/delete")
@app.route("/category/<int:category_id>/<int:item_id>/index/delete/index")
@login_required
def deleteItem(category_id, item_id):
    try:
        DeletedItem = session.query(Item).filter_by(
            category_id=category_id, id=item_id).one()
    except NoResultFound:
        flash("The requested item could not be found!")
        return redirect("/feed", code=302)
    else:
        if(login_session["user_id"] == DeletedItem.user_id):
            session.delete(DeletedItem)
            session.commit()
            flash("The item has been deleted!")
            return redirect("/category/"+str(category_id),
                            code=302)
        else:
            flash("You are not authorized!")
            return redirect("/category/"+str(category_id)+"/"+str(item_id),
                            code=302)


@app.route("/category/<int:category_id>/new", methods=["POST", "GET"])
@app.route("/category/<int:category_id>/new/index", methods=["POST", "GET"])
@login_required
def newItem(category_id):
    if(request.method == "POST"):
        if request.form["name"] and request.form["description"]:
            NewItem = Item(name=request.form["name"],
                           description=request.form["description"],
                           user_id=login_session["user_id"],
                           category_id=category_id)
            session.add(NewItem)
            session.commit()
            flash("Your new item has been created!")
            return redirect("/category/" +
                            str(category_id)+"/"+str(NewItem.id),
                            code=302)
        else:
            flash("Please submit all the required data!")
            return redirect("/category/"+str(category_id)+"/new", code=302)
    else:
        try:
            Cat = session.query(Category).filter_by(id=category_id).one()
        except NoResultFound:
            flash("The requested category could not be found!")
            return redirect("/feed", code=302)
        else:
            return render_template("new-item.html",
                                   category=Cat,
                                   login_session=login_session)


@app.route("/category/new", methods=["POST", "GET"])
@app.route("/category/new/index", methods=["POST", "GET"])
@login_required
def createCategory():
    if(request.method == "POST"):
        if request.form["name"] and request.form["description"]:
            NewCat = Category(name=request.form[
                              "name"],
                              description=request.form["description"])
            session.add(NewCat)
            session.commit()
            flash("The category has been created!")
            return redirect("/category/"+str(NewCat.id), code=302)
        else:
            flash("Please submit all the required data!")
            return redirect("/category/new", code=302)
    else:
        return render_template("new-category.html",
                               login_session=login_session)


@app.route("/category/<int:category_id>/edit", methods=["POST", "GET"])
@app.route("/category/<int:category_id>/edit/index", methods=["POST", "GET"])
@login_required
def editCategory(category_id):
    try:
        Cat = session.query(Category).filter_by(id=category_id).one()
    except NoResultFound:
        flash("This category does not exist!")
        return redirect("/feed", code=302)
    else:
        if(request.method == "POST"):
            if request.form["name"] and request.form["description"]:
                Cat.name = request.form["name"]
                Cat.description = request.form["description"]
                session.add(Cat)
                session.commit()
                flash("The category has been edited!")
                return redirect("/category/"+str(category_id), code=302)
            else:
                flash("Please submit the required data!")
                return redirect("/category/"+str(category_id)+"/edit",
                                code=302)
        else:
            return render_template("edit-category.html",
                                   login_session=login_session,
                                   category=Cat)


@app.route("/category/<int:category_id>/delete")
@app.route("/category/<int:category_id>/delete/index")
@login_required
def deleteCategory(category_id):
    try:
        Cat = session.query(Category).filter_by(id=category_id).one()
    except NoResultFound:
        flash("The requested category can't be found!")
        return redirect("/feed", code=302)
    else:
        Items = session.query(Item).filter_by(category_id=category_id)
        for i in Items:
            session.delete(i)
        session.delete(Cat)
        session.commit()
        flash("The category has been deleted!")
        return redirect("/feed", code=302)


@app.route('/login')
@app.route("/login/index")
def showLogin():
    return render_template('login.html',
                           ls=login_session,
                           login_session=login_session)


@app.route("/login/loggedin")
@app.route("/login/loggedin/index")
def showLoggedIn():
    flash("You have been logged in!")
    return redirect("/feed",
                    code=302)


@app.route('/login/google')
@app.route('/login/google/index')
def showGoogleLogin():
    return google.authorize(
        callback=url_for('googleAuthorized',
                         _external=True)
    )


@app.route("/login/github")
@app.route("/login/github/index")
def showGithubLogin():
    return github.authorize(
        callback=url_for('githubAuthorized',
                         _external=True)
    )


@app.route("/login/facebook")
@app.route("/login/facebook/index")
def showFacebookLogin():
    callback = url_for(
        'facebookAuthorized',
        next=request.args.get('next') or request.referrer or None,
        _external=True
    )
    return facebook.authorize(callback=callback)


@app.route("/login/github/authorized")
@app.route("/login/github/authorized/index")
def githubAuthorized():
    try:
        resp = github.authorized_response()
    except OAuthException:
        flash("An error occured while authorizing with GitHub!")
        return redirect("/login", code=302)
    if resp is None or resp.get('access_token') is None:
        flash('Access denied: reason=%s error=%s resp=%s' % (
            request.args['error'],
            request.args['error_description'],
            resp
        ))
        return redirect("/login", code=302)
    login_session["token"] = (resp['access_token'], '')
    me = github.get('user')
    login_session["provider"] = "github"
    login_session["email"] = "github-"+me.data["login"]+"@users.item-catalog"
    if(me.data["email"] is None):
        login_session["email"] = "github-" + \
            me.data["login"]+"@users.item-catalog"
    else:
        if(len(me.data["email"]) < 1):
            login_session["email"] = "github-" + \
                me.data["login"]+"@users.item-catalog"
        else:
            login_session["email"] = me.data["email"]

    login_session["username"] = me.data["name"]
    login_session["link"] = me.data["html_url"]
    login_session["picture"] = me.data["avatar_url"]
    login_session["user_id"] = checkUser(login_session)
    return redirect("/login/loggedin", code=302)
    # return jsonify(me.data)


@app.route('/login/facebook/authorized')
@app.route('/login/facebook/authorized/index')
def facebookAuthorized():
    try:
        resp = facebook.authorized_response()
    except OAuthException:
        flash("An error occured while authorizing with Facebook!")
        return redirect("/login", code=302)
    if resp is None:
        flash('Access denied: reason=%s error=%s resp=%s' % (
            request.args['error'],
            request.args['error_description'],
            resp
        ))
        return redirect("/login", code=302)
    if isinstance(resp, OAuthException):
        return 'Access denied: %s' % resp.message

    login_session["provider"] = "facebook"
    login_session["token"] = (resp['access_token'], '')
    me = facebook.get('/me')
    login_session["email"] = ""
    login_session["picture"] = "/static/blank_user.gif"

    try:
        me.data["email"]
    except KeyError:
        login_session["email"] = "facebook-" + \
            me.data["id"]+"@users.item-catalog"
    else:
        login_session["email"] = me.data["email"]

    try:
        me.data["picture"]
    except KeyError:
        login_session["picture"] = "/static/blank_user.gif"
    else:
        login_session["picture"] = me.data["picture"]

    login_session["username"] = me.data["name"]
    login_session["link"] = "https://facebook.com/"+me.data["id"]
    login_session["user_id"] = checkUser(login_session)
    return redirect("/login/loggedin", code=302)


@app.route('/login/google/authorized')
@app.route('/login/google/authorized/index')
def googleAuthorized():
    try:
        resp = google.authorized_response()
    except OAuthException:
        flash("An error occured while authorizing with Google!")
        return redirect("/login", code=302)
    if resp is None:
        flash('Access denied: reason=%s error=%s resp=%s' % (
            request.args['error'],
            request.args['error_description'],
            resp
        ))
        return redirect("/login", code=302)
    login_session["provider"] = "google"
    login_session["token"] = (resp['access_token'], '')
    # checkUser(login_session)
    # login_session["user_id"] = getUserID(login_session["email"])
    me = google.get('userinfo')
    if(me.data["email"] is None):
        login_session["email"] = ""
    else:
        if(len(me.data["email"]) < 1):
            login_session["email"] = ""
        else:
            login_session["email"] = me.data["email"]

    login_session["username"] = me.data["name"]
    try:
        login_session["link"]
    except KeyError:
        login_session["link"] = "#"
    else:
        login_session["link"] = me.data["link"]
    login_session["picture"] = me.data["picture"]
    login_session["user_id"] = checkUser(login_session)
    return redirect("/login/loggedin", code=302)


# User Helper Functions


def createUser(login_session):
    newUser = User(name=login_session['username'], email=login_session[
                   'email'], picture="")
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user


def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None


def checkUser(ls):
    if getUserID(ls["email"]) is None:
        return createUser(ls)
    else:
        return getUserID(ls["email"])


# Disconnect based on provider
@app.route('/logout')
@app.route('/logout/index')
def logout():
    if(login_session["token"]):
        del login_session["user_id"]
        del login_session["token"]
        del login_session["username"]
        del login_session["provider"]
        del login_session["picture"]
        del login_session["link"]
        del login_session["email"]
        flash("You have been logged out!")
        return redirect(url_for("showLogin"), code=302)
    else:
        flash("You are not logged in, so you can't log out!")
        return redirect("/login", code=302)


if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.run(host='0.0.0.0', port=5000)
