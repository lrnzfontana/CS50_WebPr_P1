import os
from sqlalchemy import create_engine, text
import csv

engine = create_engine("postgres://bmhozldjiiwprg:14e3555f83106f8b85089b2c18309d6901349098d823fee6cc8e69ce82b709bf@ec2-79-125-124-30.eu-west-1.compute.amazonaws.com:5432/d7k5upcl882dh2")
db = engine.connect()

# Import csv
f = open("books.csv")
reader = csv.DictReader(f)

# Write it to database
for row in reader:
    query = text("""INSERT INTO books (isbn, title, author, year) VALUES
    (:book, :title, :author, :year)""")
    query_go = query.bindparams(book = row["isbn"], title = row["title"],
        author = row["author"], year = int(row["year"]))
    db.execute(query_go)

    # This didn't work:
    # db.execute("""INSERT INTO books (isbn, title, author, year) VALUES
    #     (:book, :title, :author, :year)""", {"book": row["isbn"],
    #     "title": row["title"], "author": row["author"], "year": row["year"]
    # })
f.close()
