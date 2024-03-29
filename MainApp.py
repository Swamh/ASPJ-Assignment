from flask import Flask, render_template, redirect, flash, url_for, request, g, session, jsonify, make_response
from Forms import UserLoginForm, CreateUserForm, ForgetPasswordForm_Email, ForgetPasswordForm, ForgetPasswordForm_Security, PaymentForm
from flask_login import LoginManager, logout_user, current_user, login_user, UserMixin
from functools import wraps
from sqlalchemy.sql import text
from uuid import uuid4
from Database import *
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import JWTManager, jwt_required, create_access_token
import os
from login_logger import create_log, update_log, get_log, send_log, check_log, timeout, time_clear, multi_fail_log
from api.Cart import cart_api
from api.Reviews import review_api
from api.User_infotest import user_info_api
# from api.User_infotest import user_infotest_api
# from api.Login_first import user_login_toinfotest_api
from api.Login_first import login_api
from api.User_info_admin import admin_api
from api.update_profile import update_profile_api

# ---------Secure Broken Object level authorization imports-----
import jwt
import datetime
import uuid
import hashlib
import bcrypt

# ---------Secure Broken Object level authorization imports-----
from flask_wtf import CSRFProtect
from flask_caching import Cache

cache = Cache()
app = Flask(__name__)
crsf = CSRFProtect(app)
app.register_blueprint(cart_api, url_prefix='/api/Cart')
app.register_blueprint(review_api, url_prefix='/api/Reviews')
app.register_blueprint(update_profile_api, url_prefix='/api/update_profile')

app.register_blueprint(login_api, url_prefix='/api/api_login')
app.register_blueprint(user_info_api, url_prefix='/api/User_info')
app.register_blueprint(admin_api, url_prefix='/api/admin_functions')

basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'shop.db')
app.config['JWT_SECRET_KEY'] = 'asp-project-security-api'
app.config['WTF_CSRF_ENABLED'] = True

# app.config['CACHE_TYPE'] = 'simple'
app.config["Cache-Control"] = "no-cache, no-store"
app.config["Pragma"] = "no-cache"
app.config['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
app.config['SESSION_COOKIE_SECURE'] = True
app.config["CACHE_TYPE"] = "null"

cache.init_app(app)
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'users.db')
# SECRET_KEY = os.environ.get('SECRET_KEY') or "asp-project-security"

app.config['SECRET_KEY'] = "asp-project-security"

db.app = app
db.init_app(app)

jwtt = JWTManager(app)

login_manager = LoginManager(app)
login_manager.init_app(app)
login_manager.login_view = 'login'
# login_manager.anonymous_user = Anonymous

# login_manager.refresh_view = 'relogin'
# login_manager.needs_refresh_message = (u"Session timedout, please re-login")
# login_manager.needs_refresh_message_category = 'info'

user_schema = UserSchema()  # expect 1 record back
users_schema = UserSchema(many=True)  # expect multiple record back

SESSION_COOKIE_SECURE = True

# ---------Secure Broken Object level authorization-----
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        if 'x-access-token' in request.headers:
            token = request.headers['x-access-token']

        if not token:
            return jsonify({'message': 'Token is missing!'}), 401

        try:
            data = jwt.decode(token, app.config['SECRET_KEY'])
            current_user = User.query.filter_by(public_id=data['public_id']).first()
        except:
            return jsonify({'message': 'Token is invalid!'}), 401

        return f(current_user, *args, **kwargs)

    return decorated


# ---------Secure Broken Object level authorization-----

# -------------------ZY's API---------------------

# Admin functions
@app.route('/allusersinfo', methods=['GET'])
@token_required
def checkalluserinfo(current_user):
    if not current_user.is_admin:
        return jsonify({'Message': 'Acess Denied'})

    users_list = User.query.all()
    result = users_schema.dump(users_list)

    return jsonify(data=result)


@app.route('/checkoneuserinfo/<public_id>', methods=['GET'])
@token_required
def checkoneuserinfo(current_user, public_id):
    if not current_user.is_admin:
        return jsonify({'Message': 'Acess Denied'})

    user = User.query.filter_by(public_id=public_id).first()

    if user:
        result = user_schema.dump(user)
        return jsonify(result)
    else:
        return jsonify(message="User does not exist"), 404


@app.route('/createuser', methods=['POST'])
@token_required
def create_user(current_user):
    if not current_user.is_admin:
        return jsonify({'Message': 'Unauthorized to perform that function'})

    data = request.get_json()

    hashed_password = generate_password_hash(data['password'], method='sha512')

    new_user = User(public_id=str(uuid.uuid4()),
                    username=data['username'],
                    password=hashed_password,
                    email=data['email'],
                    security_questions=data['security_questions'],
                    security_questions_answer=data['security_questions_answer'],
                    is_active=True,
                    is_authenticated=False,
                    is_admin=False)

    db.session.add(new_user)
    db.session.commit()

    return jsonify({'message': 'New user created!'})


@app.route('/deleteuser/<public_id>', methods=['DELETE'])
@token_required
def delete_user(current_user, public_id):
    if not current_user.is_admin:
        return jsonify({'Message': 'Unauthorized to perform that function'})

    user = User.query.filter_by(public_id=public_id).first()

    if not user:
        return jsonify({'message': 'No user found!'})

    db.session.delete(user)
    db.session.commit()

    return jsonify({'message': 'The user has been deleted!'})


@app.route('/apilogin')
def api_login():
    auth = request.authorization

    if not auth or not auth.username or not auth.password:
        return make_response('Could not verify', 401, {'WWW-Authenticate': 'Basic realm="Login required!"'})

    user = User.query.filter_by(username=auth.username).first()

    if not user:
        return make_response('Could not verify', 401, {'WWW-Authenticate': 'Basic realm="Login required!"'})

    if check_password_hash(user.password, auth.password):
        token = jwt.encode(
            {'public_id': user.public_id, 'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=30)},
            app.config['SECRET_KEY'])

        return jsonify({'token': token.decode('UTF-8')})

    return make_response('Could not verify', 401, {'WWW-Authenticate': 'Basic realm="Login required!"'})


# User functions
@app.route('/enquireuserinfo', methods=['GET'])
@token_required
def get_user_info(current_user):
    user = User.query.filter_by(public_id=current_user.public_id).first()

    if user:
        result = user_schema.dump(user)
        return jsonify(result)
    else:
        return jsonify(message="User does not exist"), 404


@app.route('/testinginfo/<public_id>', methods=['GET'])
@token_required
def test_info(current_user, public_id):
    user = User.query.filter_by(public_id=public_id).first()

    if current_user.public_id != public_id:
        return jsonify({'Message': 'Acess Denied'})

    if user:
        result = user_schema.dump(user)
        return jsonify(result)
    else:
        return jsonify(message="User does not exist"), 404


# ------------------ZY's API---------------------
@app.before_request
def before_request():
    g.user = None
    if 'user' in session:
        g.user = session['user']
        # session.permant = True
        # app.permanent_session_lifetime = timedelta(minutes=1)


@app.after_request
def after_request(r):
    r.headers["Cache-Control"] = "no-cache, no-store"
    r.headers["Pragma"] = "no-cache"
    r.headers['server'] = 'www.cbshop.com'
    # r.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return r




@app.route('/dropsession')
def dropsession():
    session.pop('user', None)
    return redirect(url_for("home"))
    # return render_template('home.html')


# -----------------------------------------------------------------------
@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))


@app.route('/', methods=['GET', 'POST'])
@app.route('/home', methods=['GET', 'POST'])
def home():
    cart_no = 0
    if current_user.is_anonymous:
        user = None
    else:
        user = current_user
        statement = text('SELECT * FROM carts WHERE id = {}'.format(current_user.id))
        results = db.engine.execute(statement)
        for row in results:
            cart_no += 1
    statement = text('SELECT * FROM products')
    results = db.engine.execute(statement)
    products = []
    # products -> 0: name | 1: price | 2: image
    for row in results:
        products.append([row[1], row[3], row[6]])
    length = len(products)
    return render_template('home.html', products=products, length=length, user=user, cart_no=cart_no)


@app.route('/search', methods=['GET', 'POST'])
def search():
    cart_no = 0
    if current_user.is_anonymous:
        user = None
    else:
        user = current_user
        statement = text('SELECT * FROM carts WHERE id = {}'.format(current_user.id))
        results = db.engine.execute(statement)
        for row in results:
            cart_no += 1
    if request.args.get('q') == '':
        print('redirected')
        return redirect(url_for('home'))
    else:
        query = request.args.get('q')
        statement = text('SELECT * FROM products')
        results = db.engine.execute(statement)
        products = []
        # products -> 0: name | 1: price | 2: image
        for row in results:
            if query.lower() in row[1].lower():
                products.append([row[1], row[3], row[6]])
        length = len(products)
        return render_template('home_search.html', products=products, length=length, query=query, user=user,
                               cart_no=cart_no)


@app.route('/getallusersrecords', methods=['GET'])
def getallusersrecords():
    users_list = User.query.all()
    result = users_schema.dump(users_list)
    return jsonify(result)


# @app.route('/protected_testing/<username>')
# def protected(username):
#     print("Inside Protected")
#     if g.user:
#         print("Login good")
#         return render_template('protected_testing.html', user=session['user'])
#     print("Login Bad")
#     return redirect(url_for('home'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    # if current_user.is_authenticated:
    #     return redirect(url_for('home'))
    # if request.method == 'POST':
    #     session.pop('user', None)

    form = UserLoginForm()
    if form.validate_on_submit():
        if 'timeout' in session:
            if not time_clear(session['timeout']):
                flash("Too many unsuccessful attempts, please try again later!")
                return redirect(url_for('login'))
            else:
                session.pop('attempts')
                session.pop('timeout')
        if 'attempts' not in session:
            session['attempts'] = 1
        if session['attempts'] >= 5 and 'timeout' not in session:
            session['timeout'] = timeout()
            multi_fail_log(request.remote_addr)
            flash("Too many unsuccessful attempts, please try again later!")
            return redirect(url_for('login'))


        # input_username = form.username.data #
        # result = encrypt_username(input_username) #
        # print(result)

        # user = User.query.filter_by(username=result).first()
        # hashed_username_data = hashlib.sha256(form.username.data.encode()).hexdigest()
        user = User.query.filter_by(username=form.username.data).first()

        # if user is None or not user.check_password(form.password.data):
        if user:
            # if check_password_hash(user.password, form.password.data):
            if bcrypt.checkpw(form.password.data.encode(), user.password):
                login_user(user, remember=form.remember_me.data)
                user.activate_is_authenticated()
                print(user.is_authenticated)
                print("hey", current_user.is_authenticated)
                db.session.add(user)
                db.session.commit()
                session['user'] = request.form['username']
                # successful attempt
                session.pop('attempts')
                update_log(create_log(request.form['username'], request.remote_addr, 'pass'))
                return redirect(url_for('home'))

        # failed attempt
        update_log(create_log(request.form['username'], request.remote_addr, 'fail'))
        session['attempts'] += 1
        flash("Invalid username or password, please try again!")
        return redirect(url_for('login'))

    return render_template('login.html', form=form, title="Login in", user=None)


@app.route('/logout')
def logout():
    # if current_user == Anonymous:
    #     user = Anonymous
    #     return redirect(url_for('login'))
    # else:
    if current_user.is_anonymous:
        return redirect(url_for('login'))

    print("here 1", current_user == None)
    print("here", current_user)
    user = current_user
    print("id", user.id)
    # print("name",current_user.username)
    # print("not login out yet", current_user.is_authenticate())
    user.deactivate_is_authenticated()
    db.session.add(user)
    db.session.commit()
    # print("login out le",current_user.is_authenticate())
    logout_user()
    return redirect(url_for("home"))

    # if Anonymous:
    #     return redirect(url_for('login'))
    # else:


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    form = CreateUserForm()
    if form.validate_on_submit():

        # hashed_username_data = hashlib.sha256(form.username.data.encode()).hexdigest()

        # --Plaintext---
        # exists = db.session.query(User.id).filter_by(email=form.email.data).scalar()
        # exists2 = db.session.query(User.id).filter_by(username=form.username.data).scalar()
        # --Plaintext---

        # --sha512---
        # email
        hashed_email_data = hashlib.sha256(form.email.data.encode()).hexdigest()
        exists = False
        statement = text("SELECT * FROM users WHERE email = '{}'".format(hashed_email_data))
        results = db.engine.execute(statement)
        count = 0
        for row in results:
            count += 1
        if count >= 1:
            exists = True

        # check username
        exists2 = False
        statement = text("SELECT * FROM users WHERE username = '{}'".format(form.username.data))
        results = db.engine.execute(statement)
        count = 0
        for row in results:
            count += 1
        if count >= 1:
            exists2 = True
        # --sha512---

        # bcrypt
        # hashed_email_data = bcrypt.hashpw(form.email.data.encode(), bcrypt.gensalt())
        # exists = db.session.query(User.id).filter_by(email=hashed_email_data).scalar()
        # exists2 = db.session.query(User.id).filter_by(username=form.username.data).scalar()
        # bcrypt

        if not exists and not exists2:
            # ---sha algorithm----
            # hashed_password = generate_password_hash(form.password.data, method='sha512') #with salt
            # hashed_security_Q = generate_password_hash(form.security_questions.data, method='sha1') #with salt
            # hashed_security_ans = generate_password_hash(form.security_questions_answer.data, method='sha512') #with salt
            # ---sha algorithm----

            # bcrypt
            hashed_password = bcrypt.hashpw(form.password.data.encode(), bcrypt.gensalt(rounds=16))
            hashed_security_Q = bcrypt.hashpw(form.security_questions.data.encode(), bcrypt.gensalt())
            hashed_security_ans = bcrypt.hashpw(form.security_questions_answer.data.encode(), bcrypt.gensalt())
            # bcrypt

            # password=form.password.data
            newuser = User(public_id=str(uuid.uuid4()), username=form.username.data, email=hashed_email_data,
                           password=hashed_password,
                           security_questions=hashed_security_Q,
                           security_questions_answer=hashed_security_ans,
                           is_active=True, is_authenticated=False, is_admin=False)
            # newuser = User(public_id=str(uuid.uuid4()),username=form.username.data, email=form.email.data, password=hashed_password,
            #                security_questions=form.security_questions.data,
            #                security_questions_answer=form.security_questions_answer.data,
            #                is_active=True, is_authenticated=False, is_admin=False)

            # Role.create('customer')
            # newuser.roles.append(Role(name='customer', id=2))
            # newuser.set_password(form.password.data)
            db.session.add(newuser)
            db.session.commit()
            flash("You have successfully signed up!")
            return redirect(url_for('login'))

        if exists:
            flash("Email exists!")
        if exists2:
            flash("Username is taken!")
        return redirect(url_for('signup'))
    return render_template('sign up.html', title="Sign Up", form=form)


@app.route('/forgotpassword', methods=['GET', 'POST'])
def forgotpassword():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    form1 = ForgetPasswordForm_Email()
    # form11 = ForgetPasswordForm_Security()
    # form2 = ForgetPasswordForm()
    if form1.validate_on_submit():

        # ---sha algorithm---
        hashed_email_data = hashlib.sha256(form1.email.data.encode()).hexdigest()
        email_exist = db.session.query(User.id).filter_by(email=hashed_email_data).scalar()
        # ---sha algorithm---
        # hashed_email_data = bcrypt.hashpw(form1.email.data.encode(), bcrypt.gensalt())
        # email_exist = db.session.query(User.id).filter_by(email=hashed_email_data).scalar()

        if email_exist is not None:
            user = User.query.filter_by(email=hashed_email_data).first()
            # form11 = ForgetPasswordForm_Security()
            print("Here")

            form11 = ForgetPasswordForm_Security()
            if form11.validate_on_submit():
                print('Here 2')
                # if check_password_hash(user.security_questions, form11.security_questions.data):
                if bcrypt.checkpw(form11.security_questions.data.encode(), user.security_questions):
                    print('Here 3')
                    # if check_password_hash(user.security_questions_answer, form11.security_questions_answer.data):
                    if bcrypt.checkpw(form11.security_questions_answer.data.encode(), user.security_questions_answer):
                        form2 = ForgetPasswordForm()
                        # user = User.query.filter_by(email=hashed_email_data).first()

                        # security_questions = user.security_questions
                        print("Checkpoint ok")
                        if form2.validate_on_submit():
                            # if user.security_questions_answer == form2.security_questions_answer.data:
                            # if check_password_hash(user.security_questions_answer, form2.security_questions_answer.data):
                            print('REACHED')
                            update_user = User.query.filter_by(email=hashed_email_data).first()

                            # ---Sha algorithm---
                            # hashed_password = generate_password_hash(form2.newpassword.data, method='sha512')
                            # update_user.password = hashed_password
                            # ---Sha algorithm---

                            hashed_password = bcrypt.hashpw(form2.newpassword.data.encode(), bcrypt.gensalt(rounds=16))

                            update_user.password = hashed_password
                            db.session.commit()
                            flash("You have successfully reset your password")
                            return redirect(url_for('login'))

                        return render_template('forgot_password.html', title='Reset Password', form1=form1,
                                               form11=form11, form2=form2)
                    else:
                        print("OH NO")
                        flash("Incorrect security questions answer")
                        return redirect(url_for('forgotpassword'))
                # else:
                #     flash('Email does not exist')
                #     return redirect((url_for('forgotpassword')))
                # return render_template('forgot_password.html', title='Reset Password', form1=form1, form11=form11, form2=form2)
            # else:
            #     flash('Email does not exist')
            #     return redirect((url_for('forgotpassword')))

            return render_template('forgot_password.html', title='Reset Password', form1=form1, form11=form11)

        else:
            flash('Email does not exist')
            return redirect(url_for('forgotpassword'))
    return render_template('forgot_password.html', title='Reset Password', form1=form1)


@app.route('/profile', methods=['GET'])
def profile():
    if current_user.id is None:
        return redirect(url_for('/'))
    else:
        return render_template('profile.html', user=current_user)


@app.route('/orders', methods=['GET'])
def orders():
    user_id = request.args.get('user_id')
    order_id = request.args.get('order_id')
    if user_id is None or order_id is None:
        return redirect(url_for('/'))
    return render_template('order.html')


@app.route('/cart')
def cart():
    cart_no = 0
    cart_list = []
    total_price = 0
    if current_user is None:
        print("Yo here man")
        user = None
    else:
        print("Yo, it is here")
        user = current_user
        statement = text('SELECT * FROM carts WHERE id = {}'.format(current_user.id))
        results = db.engine.execute(statement)
        for row in results:
            cart_no += 1
            product = Product.query.filter_by(product_id=row[1]).first()
            price = row[2] * product.product_price
            # [product_name, image, price, quantity]
            cart_list.append([product.product_name, product.product_image, row[2], price, product.product_id])
        for item in cart_list:
            total_price += item[3]
    return render_template('cart.html', user=user, cart_no=cart_no, cart_list=cart_list, total=total_price)


@app.route('/payment', methods=['GET', 'POST'])
def payment():
    if current_user.is_anonymous:
        user = None
    else:
        user = current_user
    # cardlist = []
    # statement = text('SELECT * FROM cards WHERE id = {}'.format(current_user.id))
    # results = db.engine.execute(statement)
    # print(results)
    # for row in results:
    #     remember = Payment.query.filter_by(rememberinfo=True).first()
    #     print(remember)
    #     # card = Payment.query.filter_by(cardnum=row[1]).first()
    #     #print(row)
    #     cardlist.append(row)

    cardlist = []
    form = PaymentForm()
    if request.method == 'POST':
        # print(request.form.getlist('Remember_info'))
        # if form.validate_on_submit() and request.form.getlist('Remember_info') == ['Remember_info']:
        if form.validate_on_submit():
            print("PATH 1 ")  # Card exist in the database
            # exist_cardnum = db.session.query(Payment.cardnum).filter_by(cardnum=form.cardNum.data).first()
            # print(exist_cardnum)

            print('current user id', current_user.id)

            statement = text('SELECT * FROM cards WHERE id = {}'.format(current_user.id))
            results = db.engine.execute(statement)
            for row in results:
                cards_num = row.cardnum
                cardlist.append(cards_num)

            user_card_exist = db.session.query(Payment).filter_by(id=current_user.id).first()
            print(user_card_exist)

            # if exist_cardnum:
            # if bcrypt.checkpw(form.cardNum.data, user_card.cardname):
            if user_card_exist:
                result = False

                for cardnum in cardlist:
                    print('HEREERERERERERERER')
                    print(cardnum)
                    if bcrypt.checkpw(str(form.cardNum.data).encode(), cardnum):
                        result = True
                        break
                    else:
                        continue
                # if bcrypt.checkpw(str(form.cardNum.data).encode(), user_card_exist.cardnum):
                if result == True:
                    print("PATH 1.1 ")
                    print('Payment successful')
                    while True:
                        product = Cart.query.filter_by(cart_id=current_user.id).first()
                        if product is None:
                            break
                        else:
                            db.session.delete(product)
                            db.session.commit()
                    return redirect(url_for('home'))
                else:

                    hashed_email_data = hashlib.sha256(form.email.data.encode()).hexdigest()
                    hashed_cardname = bcrypt.hashpw(form.cardName.data.encode(), bcrypt.gensalt())
                    hashed_cardnum = bcrypt.hashpw(str(form.cardNum.data).encode(), bcrypt.gensalt(rounds=16))
                    hashed_expmonth = bcrypt.hashpw(form.expmonth.data.encode(), bcrypt.gensalt())
                    hashed_expyear = bcrypt.hashpw(form.expyear.data.encode(), bcrypt.gensalt())
                    hashed_cvv = bcrypt.hashpw(str(form.cvv.data).encode(), bcrypt.gensalt(rounds=16))

                    card = Payment(name=form.name.data,
                                   email=hashed_email_data,
                                   address=form.address.data,
                                   country=form.country.data,
                                   city=form.city.data,
                                   zip=form.zip.data,
                                   cardname=hashed_cardname,
                                   cardnum=hashed_cardnum,
                                   expmonth=hashed_expmonth,
                                   expyear=hashed_expyear,
                                   cvv=hashed_cvv,
                                   id=user.get_id())

                    # card = Payment(name=form.name.data,
                    #        email=form.email.data,
                    #        address=form.address.data,
                    #        country=form.country.data,
                    #        city=form.city.data,
                    #        zip=form.zip.data,
                    #        cardname=form.cardName.data,
                    #        cardnum=form.cardNum.data,
                    #        expmonth=form.expmonth.data,
                    #        expyear=form.expyear.data,
                    #        cvv=form.cvv.data,
                    #        id=user.get_id())
                    db.session.add(card)
                    db.session.commit()
                    print("Yo2")
                    print('Payment successful')
                    while True:
                        product = Cart.query.filter_by(cart_id=current_user.id).first()
                        if product is None:
                            break
                        else:
                            db.session.delete(product)
                            db.session.commit()
                    return redirect(url_for('home'))

            # print(request.form.getlist('Remember_info'))

            # print("PATH 1.2 ") #When card does not exist in the database
            # print(bcrypt.checkpw(form.cardNum.data.encode(), user.cardname))

            hashed_email_data = hashlib.sha256(form.email.data.encode()).hexdigest()
            hashed_cardname = bcrypt.hashpw(form.cardName.data.encode(), bcrypt.gensalt())
            hashed_cardnum = bcrypt.hashpw(str(form.cardNum.data).encode(), bcrypt.gensalt(rounds=16))
            hashed_expmonth = bcrypt.hashpw(form.expmonth.data.encode(), bcrypt.gensalt())
            hashed_expyear = bcrypt.hashpw(form.expyear.data.encode(), bcrypt.gensalt())
            hashed_cvv = bcrypt.hashpw(str(form.cvv.data).encode(), bcrypt.gensalt(rounds=16))

            card = Payment(name=form.name.data,
                           email=hashed_email_data,
                           address=form.address.data,
                           country=form.country.data,
                           city=form.city.data,
                           zip=form.zip.data,
                           cardname=hashed_cardname,
                           cardnum=hashed_cardnum,
                           expmonth=hashed_expmonth,
                           expyear=hashed_expyear,
                           cvv=hashed_cvv,
                           id=user.get_id())

            # card = Payment(name=form.name.data,
            #                email=form.email.data,
            #                address=form.address.data,
            #                country=form.country.data,
            #                city=form.city.data,
            #                zip=form.zip.data,
            #                cardname=form.cardName.data, #show
            #                cardnum=form.cardNum.data, #last 4
            #                expmonth=form.expmonth.data, #show
            #                expyear=form.expyear.data, #show
            #                cvv=form.cvv.data,
            #                id=user.get_id())
            db.session.add(card)
            db.session.commit()
            print("Yo")
            print('Payment successful')
            while True:
                product = Cart.query.filter_by(cart_id=current_user.id).first()
                if product is None:
                    break
                else:
                    db.session.delete(product)
                    db.session.commit()
            return redirect(url_for('home'))

        # if form.validate_on_submit() and request.form.getlist('Remember_info') == []:
        #     print("PATH 2 ")
        #     exist_cardnum = db.session.query(Payment.cardnum).filter_by(cardnum=form.cardNum.data).first()
        #     print(exist_cardnum)
        #     if exist_cardnum:
        #         print("PATH 2.1 ")
        #         print('Payment successful')
        #         while True:
        #             product = Cart.query.filter_by(cart_id=current_user.id).first()
        #             if product is None:
        #                 break
        #             else:
        #                 db.session.delete(product)
        #                 db.session.commit()
        #         return redirect(url_for('home'))
        #
        #     print("PATH 2.2 ")
        #     card = Payment(name=form.name.data,
        #                    email=form.email.data,
        #                    address=form.address.data,
        #                    country=form.country.data,
        #                    city=form.city.data,
        #                    zip=form.zip.data,
        #                    cardname=form.cardName.data,
        #                    cardnum=form.cardNum.data,
        #                    expmonth=form.expmonth.data,
        #                    expyear=form.expyear.data,
        #                    cvv=form.cvv.data,
        #                    id=user.get_id(),
        #                    rememberinfo=False)
        #     db.session.add(card)
        #     db.session.commit()
        #     print("Yo2")
        #     print('Payment successful')
        #     while True:
        #         product = Cart.query.filter_by(cart_id=current_user.id).first()
        #         if product is None:
        #             break
        #         else:
        #             db.session.delete(product)
        #             db.session.commit()
        #     return redirect(url_for('home'))
        #
        # else:
        #     return redirect(url_for('payment'))

    return render_template('payment.html', title='Payment', form=form, user=user)


@app.route('/admin_page', methods=['GET', 'POST'])
def admin_page():
    if current_user.is_admin:
        if request.method == 'POST':
            date = request.form.get('date')
            date = date.split('-')
            date = '{}-{}-{}'.format(date[2], date[1], date[0])
            # check if the date exists
            if check_log(date):
                send_log(date)
                flash('access log for {} has been sent.'.format(date))
            else:
                flash('There is no access logs for {}'.format(date))
            return redirect(url_for('admin_page'))
        else:
            log_list = get_log()
            return render_template('admin_page.html', user=current_user, logs=log_list), 200
    else:
        return redirect(url_for("home"))


@app.route('/update_profile', methods=['GET', 'POST'])
def update_profile():
    invalid = False
    if request.referrer.endswith('update_profile'):
        invalid = True
    if current_user.is_anonymous:
        return redirect(url_for("home"))
    else:
        return render_template('update_profile.html', user=current_user, error=invalid)


def reset_database():
    # run db_drop to reset the database
    db_drop(db)

    # run db_create to initialize the database
    db_create(db)

    # run db_seed to create sample data in the database
    db_seed(db)

    # update the js file
    update_js()


# Uncomment this function to reset the database
# reset_database()


if __name__ == "__main__":
    app.run(host='192.168.1.100')
