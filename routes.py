from app import app
from flask import render_template, url_for, redirect, request, g, Response
from datetime import datetime
import lib.twitter
from model import Account, Session, Post
from app import db
import tasks

@app.before_request
def load_viewer():
    g.viewer = None
    sid = request.cookies.get('forget_sid', None)
    if sid:
        g.viewer = Session.query.get(sid)

@app.after_request
def touch_viewer(resp):
    if g.viewer:
        g.viewer.touch()
        db.session.commit()
    return resp

@app.route('/')
def index():
    if g.viewer:
        posts = Post.query.filter_by(author_id = g.viewer.account_id).order_by(db.desc(Post.created_at)).limit(30)
        return render_template('index.html', posts=posts)
    else:
        return render_template('index.html')

@app.route('/login/twitter')
def twitter_login_step1():
    return redirect(lib.twitter.get_login_url(
        callback = url_for('twitter_login_step2', _external=True),
        **app.config.get_namespace("TWITTER_")
        ))

@app.route('/login/twitter/callback')
def twitter_login_step2():
    oauth_token = request.args['oauth_token']
    oauth_verifier = request.args['oauth_verifier']
    token = lib.twitter.receive_verifier(oauth_token, oauth_verifier, **app.config.get_namespace("TWITTER_"))

    session = Session(account_id = token.account_id)
    db.session.add(session)
    db.session.commit()

    tasks.fetch_acc.s(token.account_id).delay()

    resp = Response(status=301, headers={"location": url_for('index')})
    resp.set_cookie('forget_sid', session.id,
        max_age=60*60*48,
        httponly=True,
        secure=app.config.get("HTTPS"))
    return resp

@app.route('/logout')
def logout():
    if(g.viewer):
        db.session.delete(g.viewer)
        db.session.commit()
        g.viewer = None
    return redirect(url_for('index'))
