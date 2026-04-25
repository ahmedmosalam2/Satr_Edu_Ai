import pymongo
client = pymongo.MongoClient('mongodb://admin:admin@mongodb:27017')
db = client['Satr_Edu']
users = list(db.users.find({}, {'user_email':1,'user_role':1,'is_approved':1,'_id':0}))
for u in users:
    approved = u.get('is_approved', False)
    print(u['user_role'], '|', u['user_email'], '| approved=', approved)
