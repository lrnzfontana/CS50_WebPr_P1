import os

from flask import Flask, session, request, render_template, redirect, jsonify
from flask_session import Session
from sqlalchemy import create_engine, text
from sqlalchemy.orm import scoped_session, sessionmaker
from helpers import login_required, get_goodreads
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine("postgres://bmhozldjiiwprg:14e3555f83106f8b85089b2c18309d6901349098d823fee6cc8e69ce82b709bf@ec2-79-125-124-30.eu-west-1.compute.amazonaws.com:5432/d7k5upcl882dh2")
db = scoped_session(sessionmaker(bind=engine))


@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    if request.method == 'POST':
        if not request.form.get("searcharg"):
            return render_template("error.html", message = "Provide something to search for!")

        sarg = request.form.get("searcharg")
        return redirect(f"/search/{sarg}")

    if request.method == 'GET':
        uname = db.execute(text("SELECT name FROM users WHERE id = :id").bindparams(id = session["user_id"])).fetchone()
        return render_template("search.html", uname = uname[0])

# Get argument from / route and display list of books
@app.route("/search/<string:sarg>")
@login_required
def result(sarg):

    # Get results from books
    sarg = str(sarg)
    query = f"SELECT isbn, title, author, year FROM books WHERE isbn LIKE '{sarg}%' OR lower(author) LIKE '%{sarg}%' OR lower(title) LIKE '%{sarg}%' ORDER BY author, title"
    query = text(query)
    results = db.execute(query).fetchall()

    if len(results) == 0:
        return render_template("error.html", message = 'No results! Please try again')

    return render_template("results.html", results = results)


# If get shows info about the book, a review form, and existing reviews, plus average rating from Goodreads
# if post, submits review
@app.route("/book/<string:isbn>", methods = ["GET", "POST"])
@login_required
def book(isbn):

    if request.method == 'GET':
        book = db.execute(text("SELECT title, author, year FROM books WHERE isbn = :id").bindparams(id = isbn)).fetchone()
        if len(book) == 0:
            return render_template("error.html", message = 'No books found! Please try again')

        # Get reviews for books
        query = text("SELECT score, description, u.name FROM reviews r INNER JOIN users u ON r.user_id = u.id WHERE r.isbn = :id").bindparams(id = isbn)
        reviews = db.execute(query).fetchall()
        avg_score_res = db.execute(text("SELECT coalesce(avg(score), 0) score, count(*) reviews FROM reviews WHERE isbn = :id").bindparams(id = isbn)).fetchone()

        avg_score = {"score": round(avg_score_res['score'], 2), "reviews": avg_score_res['reviews'], "reviews_f" : "{:,}".format(avg_score_res['reviews'])}

        # Has the user already submitted a review?
        query_rev = text("SELECT count(*) rev FROM reviews WHERE isbn = :isbn AND user_id = :uid").bindparams(isbn = isbn, uid = session['user_id'])
        check_already = db.execute(query_rev).fetchone()

        # Get goodreads info
        goodr = get_goodreads(isbn = isbn)

        return render_template("book.html", book = book, bw_score = avg_score, gr_info = goodr, reviews = reviews, check_already = check_already)

    if request.method == 'POST':
        if not request.form.get('content') or not request.form.get('rating'):
            return render_template("error.html", message = "Please enter a valid review!")

        desc = request.form.get('content')
        rating = request.form.get('rating')
        userid = session['user_id']

        query = text("INSERT INTO reviews (user_id, isbn, score, description) VALUES (:uid, :isbn, :score, :desc)")
        query = query.bindparams(uid = userid, isbn = isbn, score = rating, desc = desc)
        db.execute(query)
        db.commit()

        return render_template("message.html", message = 'Thanks for submitting your review!')


@app.route("/signup", methods = ["GET", "POST"])
def signup():
    if request.method == "POST":

        if not request.form.get("uname") or not request.form.get("pword") or not request.form.get("pword-conf"):
            return render_template("error.html", message = "Something went wrong when creating your account. Please try again!")

        if request.form.get("pword") != request.form.get("pword-conf"):
            return render_template("error.html", message = "The password does not match!")

        uname = request.form.get("uname")

        uname_check = db.execute(text("SELECT count(*) FROM users WHERE name = :uname").bindparams(uname = uname)).fetchone()
        if uname_check[0] > 0:
            return render_template("error.html", message = "The user already exists!")

        pword = generate_password_hash(request.form.get("pword"))
        query = text("INSERT INTO users (name, password) VALUES (:uname, :pword)")
        query = query.bindparams(uname = uname, pword = pword)
        db.execute(query)
        db.commit()

        id = db.execute(text("SELECT id FROM users WHERE name = :uname").bindparams(uname = uname)).fetchone()

        session["user_id"] = id[0]
        return redirect("/")


    if request.method == "GET":
        return render_template("signup.html")


@app.route("/login", methods = ["GET", "POST"])
def login():
    if request.method == 'POST':

        if not request.form.get("uname") or not request.form.get("pword"):
            return render_template("error.html", message = "Please provide username and password!")

        uname = request.form.get("uname")
        check_uname = db.execute(text("SELECT count(*) FROM users WHERE name = :uname").bindparams(uname = uname)).fetchone()
        if check_uname[0] == 0:
            return render_template("error.html", message = "The username doesn't exist!")

        pword = request.form.get("pword")
        # Get password from database:
        pword_right = db.execute(text("SELECT password, id FROM users WHERE name = :uname").bindparams(uname = uname)).fetchone()

        if check_password_hash(pword_right[0], pword):
            session["user_id"] = pword_right[1]
            return redirect("/")
        else:
            return render_template("error.html", message = "The password is not correct!")

    if request.method == 'GET':
        return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    session.clear()
    return redirect("/")

# API
@app.route("/api/<string:isbn>")
def book_api(isbn):

    # If book doesn't exist return 400:
    book = db.execute(text("SELECT title, author, year, bk.isbn, count(*) reviews, coalesce(avg(score), 0) score FROM books bk LEFT JOIN reviews r ON bk.isbn = r.isbn WHERE bk.isbn = :id GROUP BY title, author, year, bk.isbn").bindparams(id = isbn)).fetchone()

    if book is None:
      return jsonify({"error": "book not found"}), 404
    else:
      return jsonify({"title": book['title'],
                        "author": book["author"],
                        "year": book['year'],
                        "isbn": book["isbn"],
                        "review_count": book["reviews"], #Convert to float, otherwise it fails:
                        "average_score": float(round(book['score'], 1))
      })
