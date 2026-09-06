from database.mongo import client, cars_collection

try:
    client.admin.command("ping")

    print("MongoDB connection successful!")
    print("Number of cars:", cars_collection.count_documents({}))

except Exception as e:
    print("MongoDB connection failed:")
    print(e)