import os
#test
from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd
from datetime import datetime

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    stocks = db.execute("SELECT * FROM transactions WHERE id = :id", id=session["user_id"])
    cash = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])
    total_money = cash[0]["cash"]
    for stock in stocks:
        total_money += (stock["number"] * stock["price"])

    return render_template("index.html", stocks=stocks, cash=cash, total_money=total_money)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":

        # error checking
        if not request.form.get("symbol") or not request.form.get("shares"):
            return apology("Invalid symbol or share number", 403)
        symbol = request.form.get("symbol")
        try:
            number = int(request.form.get("shares"))
        except ValueError:
            return apology("Invalid number", 400)

        try:
            number.is_integer()
            return apology("Invalid number", 400)
        except AttributeError:
            if (number < 1):
                return apology("Invalid number", 400)
        shares = lookup(request.form.get("symbol"))
        if not shares:
            return apology("Please enter a valid symbol")
        price = shares["price"]

        cost = price * number

        # gets current money from user
        result = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])
        money = float(result[0]["cash"])

        if money < cost:
            return apology("Sorry, not enough funds")

        stock_in = db.execute("SELECT symbol FROM transactions WHERE id = :id", id=session["user_id"])

        # if stock is already in the users database, update it, else add it
        c = 1
        for x in stock_in:
            if symbol == x["symbol"]:
                db.execute("UPDATE transactions SET number = number + :number WHERE id = :id AND symbol = :symbol",
                           id=session["user_id"], number=number, symbol=symbol)
                c = 0
        if c == 1:
            db.execute("INSERT INTO transactions(id,symbol,number,price) VALUES (:id, :symbol, :number, :price)",
                       id=session["user_id"], symbol=symbol, number=number, price=cost)

        # update users cash
        db.execute("UPDATE users SET cash = cash - :cost WHERE id = :id", id=session["user_id"], cost=cost)
        db.execute("INSERT INTO history(id,symbol,number,price,datetime) VALUES (:id, :symbol, :number, :price, :datetime)",
                   id=session["user_id"], symbol=symbol, number=number, price=-cost, datetime=datetime.now())
        # return to index page
        return redirect("/")
    else:
        return render_template("buy.html")


# id is unique in this table for transacitons, therefore need to make a new one where id is not unique
@app.route("/check", methods=["GET"])
def check():
    """Return true if username available, else false, in JSON format"""

    return jsonify("TODO")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    stocks = db.execute("SELECT * FROM history WHERE id = :id", id=session["user_id"])
    return render_template("history.html", stocks=stocks)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("Please enter a symbol", 400)
        quote = lookup(request.form.get("symbol"))
        if not quote:
            return apology("Symbol not valid", 400)
        return render_template("quoted.html", quote=quote)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    session.clear()
    """Register User"""
    if request.method == "POST":

        # error checking
        if not request.form.get("username"):
            return apology("No Username", 400)

        elif not request.form.get("password"):
            return apology("No password", 400)

        elif not request.form.get("confirmation"):
            return apology("Please confirm your password", 400)

        elif (request.form.get("password") != request.form.get("confirmation")):
            return apology("Passwords do not match", 400)

        username = request.form.get("name")

        # encrypt password
        hash = generate_password_hash(request.form.get("password"))

        result = db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)",
                            username=request.form.get("username"), hash=hash)
        if not result:
            return apology("Sorry, that username is already taken")
        session["user_id"] = result
        return redirect("/")
    else:
        return render_template("register.html")


@app.route("/password", methods=["GET", "POST"])
@login_required
def password():
    if request.method == "POST":
        if not (request.form.get("password")) or not request.form.get("password-conf"):
            return apology("Please enter your desired new password")
        if request.form.get("password") != request.form.get("password-conf"):
            return apology("Your passwords did not match, please try again")

        hash = generate_password_hash(request.form.get("password"))
        db.execute("UPDATE users SET hash = :hash WHERE id = :id", hash=hash, id=session["user_id"])
        return redirect("/")

    else:
        return render_template("password.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "POST":
        symbol = request.form.get("symbol")
        number = int(request.form.get("shares"))
        try:
            number = int(request.form.get("shares"))
        except ValueError:
            return apology("Invalid number", 400)

        try:
            number.is_integer()
            return apology("Invalid number", 400)
        except AttributeError:
            if (number < 1):
                return apology("Invalid number", 400)
        quote = lookup(request.form.get("symbol"))
        print(number)
        if not quote:
            return apology("Symbol not valid", 400)
        price = float(quote["price"])
        total_profit = float(price * number)

        if not symbol or not number:
            return apology("Please enter valid symbol/number")

        current_number = db.execute(
            "SELECT symbol,number FROM transactions WHERE id = :id AND symbol = :symbol", id=session["user_id"], symbol=symbol)

        if not current_number:
            return apology("No shares of that type found in your portfolio")

        if (current_number[0]["number"] < number):
            return apology("You don't have that many shares to sell")

        db.execute("UPDATE transactions SET number = number - :number WHERE id = :id AND symbol = :symbol",
                   number=number, id=session["user_id"], symbol=symbol)
        db.execute("UPDATE users SET cash = cash + :total_profit WHERE id = :id", id=session["user_id"], total_profit=total_profit)

        checkIn = db.execute("SELECT number FROM transactions WHERE id= :id AND symbol= :symbol",
                             id=session["user_id"], symbol=symbol)
        if checkIn[0]["number"] == 0:
            db.execute("DELETE FROM transactions WHERE id = :id AND symbol = :symbol", id=session["user_id"], symbol=symbol)

        db.execute("INSERT INTO history(id, symbol, number, price, datetime) VALUES (:id, :symbol, :number, :price, :datetime)",
                   id=session["user_id"], symbol=symbol, number=number, price=total_profit, datetime=datetime.now())
        return redirect("/")
    else:
        return render_template("sell.html")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
