from functools import wraps
from flask import Flask, jsonify, make_response, request
from flask_sqlalchemy import SQLAlchemy
import uuid
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime

app = Flask(__name__)

app.config['SECRET_KEY'] = 'Th1s1ss3cr3tecret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///todo.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key= True)
    public_id = db.Column(db.String(50), unique= True)
    name = db.Column(db.String(50))
    password = db.Column(db.String(80))
    admin = db.Column(db.Boolean)

class Todo(db.Model):
    id = db.Column(db.Integer, primary_key= True)
    text = db.Column(db.String(50))
    complete = db.Column(db.Boolean)
    user_id = db.Column(db.Integer)

def token_required(func):
    @wraps(func)
    def decorated(*args, **kwargs):
        token = None

        if 'x-access-token' in request.headers:
            token = request.headers['x-access-token']

        if not token:
            return jsonify({'message': 'Token does not exist!'}), 401

        try:
            data = jwt.decode(token, key= app.config['SECRET_KEY'], algorithms="HS256")
            curr_user = User.query.filter_by(public_id = data['public_id']).first()
        except:
            return jsonify({'message': 'Token invalid!'}), 401

        return func(curr_user, *args, **kwargs)
    return decorated

@app.route('/user', methods= ['GET'])
@token_required
def get_all_users(curr_user):

    if not curr_user.admin:
        return jsonify({'message': 'Action not permitted!'})

    users = User.query.all()

    output = []

    for user in users:
        user_data = {}

        user_data['public_id'] = user.public_id
        user_data['name'] = user.name
        user_data['password'] = user.password
        user_data['admin'] = user.admin

        output.append(user_data)

    return jsonify({'users': output})

@app.route('/user/<public_id>', methods= ['GET'])
@token_required
def get_one_user(curr_user, public_id):

    if not curr_user.admin:
        return jsonify({'message': 'Action not permitted!'})

    user = User.query.filter_by(public_id= public_id).first()

    if not user:
        return jsonify({'message': 'User does not exist!'})

    user_data = {}

    user_data['public_id'] = user.public_id
    user_data['name'] = user.name
    user_data['password'] = user.password
    user_data['admin'] = user.admin

    return jsonify({'user': user_data})
    
@app.route('/user', methods= ['POST'])
@token_required
def create_user(curr_user):

    if not curr_user.admin:
        return jsonify({'message': 'Action not permitted!'})

    data = request.get_json()

    hashed_password = generate_password_hash(data['password'], method='sha256')

    new_user = User(
        public_id= str(uuid.uuid4()),
        name= data['name'],
        password= hashed_password,
        admin= False
    )

    db.session.add(new_user)
    db.session.commit()

    return jsonify({'message': 'New user created successfully!'})

@app.route('/user/<public_id>', methods= ['PUT'])
@token_required
def promote_user(curr_user, public_id):

    if not curr_user.admin:
        return jsonify({'message': 'Action not permitted!'})

    user = User.query.filter_by(public_id= public_id).first()

    if not user:
        return jsonify({'message': 'User does not exist!'})

    user.admin= True

    db.session.commit()

    return jsonify({'message': 'The user has been granted administrative priveleges.'})

@app.route('/user/<public_id>', methods= ['DELETE'])
@token_required
def delete_user(curr_user, public_id):

    if not curr_user.admin:
        return jsonify({'message': 'Action not permitted!'})

    user = User.query.filter_by(public_id= public_id).first()

    if not user:
        return jsonify({'message': 'User does not exist!'})

    db.session.delete(user)
    db.session.commit()

    return jsonify({'message': 'User deleted successfully!'})

@app.route('/login')
def login():

    auth = request.authorization

    if not auth or not auth.username or not auth.password:
        return make_response({'Could not verify'}, 401, {'WWW-Authenticate': 'Basic realm="Login Required!"'})

    user = User.query.filter_by(name= auth.username).first()

    if not user:
        return make_response({'Could not verify'}, 401, {'WWW-Authenticate': 'Basic realm="Login Required!"'})

    if check_password_hash(user.password, auth.password):
        token = jwt.encode({'public_id': user.public_id, 'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=30)}, app.config['SECRET_KEY'])

        return jsonify({'token': token})

    return make_response({'Could not verify'}, 401, {'WWW-Authenticate': 'Basic realm="Login Required!"'})

@app.route('/todo', methods= ['GET'])
@token_required
def get_all_todos(curr_user):

    todos = Todo.query.filter_by(user_id= curr_user.id).all()

    output = []

    for todo in todos:
        todo_data = {}

        todo_data['id'] = todo.id
        todo_data['text'] = todo.text
        todo_data['complete'] = todo.complete
        output.append(todo_data)

    return jsonify({'Todos': output})

@app.route('/todo/<todo_id>', methods= ['GET'])
@token_required
def get_one_todo(curr_user, todo_id):

    todo = Todo.query.filter_by(id= todo_id, user_id= curr_user.id).first()

    if not todo:
        return jsonify({'message': 'No Todo found!'})

    todo_data = {}

    todo_data['id'] = todo.id
    todo_data['text'] = todo.text
    todo_data['complete'] = todo.complete

    return jsonify({'Todo': todo_data})

@app.route('/todo', methods= ['POST'])
@token_required
def create_todo(curr_user):

    data = request.get_json()

    new_todo = Todo(
        text = data['text'],
        complete= False,
        user_id= curr_user.id
    )

    db.session.add(new_todo)
    db.session.commit()

    return jsonify({'message': 'Todo created successfully!'})

@app.route('/todo/<todo_id>', methods= ['PUT'])
@token_required
def complete_todo(curr_user, todo_id):

    todo = Todo.query.filter_by(id= todo_id, user_id= curr_user.id).first()

    if not todo:
        return jsonify({'message': 'No Todo with the specified ID found!'})

    if todo.complete:
        return jsonify({'message': 'Todo was already completed.'})

    todo.complete= True

    db.session.commit()

    return jsonify({'message': 'The todo was completed successfully.'})

@app.route('/todo/<todo_id>', methods= ['DELETE'])
@token_required
def delete_todo(curr_user, todo_id):

    todo = Todo.query.filter_by(id= todo_id, user_id= curr_user.id).first()

    if not todo:
        return jsonify({'message': 'No Todo with the specified ID found!'})

    db.session.delete(todo)
    db.session.commit()

    return jsonify({'message': 'Todo was deleted successfully!'})

if __name__=='__main__':
    app.run(debug=True)