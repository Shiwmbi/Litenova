import sqlite3

connection = sqlite3.connect("litenova.db")
connection.close()

print("Database created successfully.")