from flask import redirect, render_template, request, session, url_for
from functools import wraps
import requests

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect(url_for('signup', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# Return rating info from Goodreads based on isbn:
def get_goodreads(isbn):
    key = "HQO3m52jQa5ifthLlgv7SA"
    res = requests.get("https://www.goodreads.com/book/review_counts.json", params = {"key": key, "isbns": isbn})

    if res.status_code != 200:
        return {}

    resj = res.json()
    revcount = resj['books'][0]['work_reviews_count']
    revcount_f = "{:,}".format(resj['books'][0]['work_reviews_count'])
    avgrating = resj['books'][0]['average_rating']
    return {"revcount": revcount, "avgrating": avgrating, "revcount_f" : revcount_f}
