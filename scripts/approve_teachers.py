import pymongo

c = pymongo.MongoClient('mongodb://admin:admin@mongodb:27017')
db = c['Satr-Edu']

# Approve all teachers
result = db['users'].update_many({'user_role': 'teacher'}, {'$set': {'is_approved': True}})
print('Approved teachers:', result.modified_count)

# Show all users
print('All users:')
for u in db['users'].find({}, {'user_email': 1, 'user_role': 1, 'is_approved': 1, '_id': 0}):
    print(' -', u.get('user_email'), '|', u.get('user_role'), '| approved=', u.get('is_approved'))
