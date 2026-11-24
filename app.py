from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from datetime import date, timedelta
from collections import Counter
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///agriplan.db"

db = SQLAlchemy(app)

app.config["SECRET_KEY"] = "Change-this-later"
login_manager = LoginManager(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    farms = db.relationship("Farm", backref="owner", lazy=True)


class Farm(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(120), nullable=False)
    size = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    crops = db.relationship("Crop", backref="farm", lazy=True)
    tasks = db.relationship("Task", backref="farm", lazy=True)

class Crop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    planting_date = db.Column(db.Integer, nullable=False)
    expected_harvest_date = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String, nullable=True, default="Planned")
    farm_id = db.Column(db.Integer, db.ForeignKey("farm.id"), nullable=True)
    tasks = db.relationship("Task", backref="crop", lazy=True)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String, nullable=False)
    due_date = db.Column(db.Integer, nullable=False)
    status = db.Column(db.Integer, nullable=False)
    farm_id = db.Column(db.Integer, db.ForeignKey("farm.id"), nullable=False)
    crop_id = db.Column(db.Integer, db.ForeignKey("crop.id"), nullable=True)

def my_farm():
    return Farm.query.filter_by(user_id=current_user.id).all()

def my_crops():
    ids= [f.id for f in my_farm()]
    return Crop.query.filter(Crop.farm_id.in_(ids)).all() if ids else []

@app.route("/")
def home():
    return "Hello from Agriplan"

@app.route("/about")
def about():
    return "AgriPlan helps smallholder farmers in Rwanda manage their farms."

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        if User.query.filter_by(email=email).first():
            flash("email is already registered")
            return redirect(url_for("register"))
        user = User(name=name, email=email, password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        flash("Account created, please log in")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for("dashboard"))
        
        flash("Wrong email or password")
        return redirect(url_for("login"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    logout_user()
    flash("You've been logged out")
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    my_farms = Farm.query.filter_by(user_id=current_user.id).all()
    farm_ids = [f.id for f in my_farms]
    Crops = Crop.query.filter(Crop.farm_id.in_(farm_ids)).all() if farm_ids else []
    return render_template("dashboard.html", farms = my_farms, Crops=Crops)

@app.route("/farms")
@login_required
def farms():
    my_farms = Farm.query.filter_by(user_id=current_user.id).all()
    return render_template("farms.html", farms=my_farms)


@app.route("/farms/new", methods=["GET", "POST"])
@login_required
def new_farm():
    if request.method == "POST":
        farm = Farm(
            name=request.form["name"],
            location=request.form["location"],
            size=float(request.form["size"]),
            user_id=current_user.id,
        )
        db.session.add(farm)
        db.session.commit()
        flash("Farm added.")
        return redirect(url_for("farms"))
    return render_template("farm_form.html", farm=None)


@app.route("/farms/<int:farm_id>/edit", methods=["GET", "POST"])
@login_required
def edit_farm(farm_id):
    farm = db.session.get(Farm, farm_id)
    if farm is None or farm.user_id != current_user.id:
        flash("Farm not found.")
        return redirect(url_for("farms"))

    if request.method == "POST":
        farm.name = request.form["name"]
        farm.location = request.form["location"]
        farm.size = float(request.form["size"])
        db.session.commit()
        flash("Farm updated.")
        return redirect(url_for("farms"))
    return render_template("farm_form.html", farm=farm)


CROP_STATUSES = ["planned", "growing", "harvested"]


@app.route("/crops")
@login_required
def crops():
    my_farm_ids = [f.id for f in Farm.query.filter_by(user_id=current_user.id)]
    my_crops = Crop.query.filter(Crop.farm_id.in_(my_farm_ids)).all() if my_farm_ids else []
    return render_template("crops.html", crops=my_crops)


@app.route("/crops/new", methods=["GET", "POST"])
@login_required
def new_crop():
    my_farms = Farm.query.filter_by(user_id=current_user.id).all()
    if not my_farms:
        flash("Add a farm first.")
        return redirect(url_for("new_farm"))

    if request.method == "POST":
        farm = db.session.get(Farm, int(request.form["farm_id"]))
        if farm is None or farm.user_id != current_user.id:
            flash("Farm not found.")
            return redirect(url_for("crops"))
        crop = Crop(
            name=request.form["name"],
            planting_date=date.fromisoformat(request.form["planting_date"]),
            expected_harvest_date=date.fromisoformat(request.form["expected_harvest_date"]),
            status=request.form["status"],
            farm_id=farm.id,
        )
        db.session.add(crop)
        db.session.commit()
        flash("Crop added.")
        return redirect(url_for("crops"))
    return render_template("crop_form.html", crop=None, farms=my_farms, statuses=CROP_STATUSES)

@app.route("/crops/<int:crop_id>/edit", methods=["GET", "POST"])
@login_required
def edit_crop(crop_id):
    crop = db.session.get(Crop, crop_id)
    if crop is None or crop.farm.user-id != current_user.id:
        flash("crop not found.")
        return redirect(url_for("crops"))

    if request.method == "POST":
        farm = db.session.get(Farm, int(request.form["farm_id"]))
        if farm is None or farm.user_id != current_user.id:
            flash("Farm not found.")
            return redirect(url_for("crops"))
        crop.name = request.form["name"]
        crop.planting_date = date.fromisoformat(request.form["planting_date"])
        crop.expected_harvest_date = date.fromisoformat(request.form["expected_harvest_date"])
        crop.status = request.form["status"]
        crop.farm_id = farm.id
        db.session.commit()
        flash("Crop updated.")
        return redirect(url_for("crops"))
    return render_template("crop_form.html", crop=crop, farms=my_farms(), statuses=CROP_STATUSES)

@app.route("/crops/<int:crop_id>/delete", methods=["POST"])
@login_required
def delete_crop(crop_id):
    crop = db.session.get(Crop, crop_id)
    if crops is None or crop.farm.user_id != current_user.id:
        flash("Crop not found.")
        return redirect(url_for("crops"))
    Task.query.filter_by(Crop.id).update({"crop_id": None})
    db.session.delete(crop)
    db.session.commit()
    flash("crop deleted.")
    return redirect(url_for("crops"))

def get_my_task(task_id):
    task = db.session.get(Task, task_id)
    if task is None or task.farm.user_id != current_user.id:
        return None
    return task


def apply_task_form(task):
    farm = db.session.get(Farm, int(request.form["farm_id"]))
    if farm is None or farm.user_id != current_user.id:
        return False
    crop_id = request.form.get("crop_id")
    crop = db.session.get(Crop, int(crop_id)) if crop_id else None
    if crop is not None and crop.farm_id != farm.id:
        return False
    task.title = request.form["title"]
    task.due_date = date.fromisoformat(request.form["due_date"])
    task.farm_id = farm.id
    task.crop_id = crop.id if crop else None
    return True


@app.route("/tasks")
@login_required
def tasks():
    ids = [f.id for f in my_farms()]
    my_tasks = Task.query.filter(Task.farm_id.in_(ids)).order_by(Task.due_date).all() if ids else []
    return render_template("tasks.html", tasks=my_tasks, today=date.today())


@app.route("/tasks/new", methods=["GET", "POST"])
@login_required
def new_task():
    if not my_farms():
        flash("Add a farm first.")
        return redirect(url_for("new_farm"))
    if request.method == "POST":
        task = Task()
        if apply_task_form(task):
            db.session.add(task)
            db.session.commit()
            flash("Task added.")
            return redirect(url_for("tasks"))
        flash("Invalid farm or crop.")
    return render_template("task_form.html", task=None, farms=my_farms(), crops=my_crops())


@app.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
@login_required
def edit_task(task_id):
    task = get_my_task(task_id)
    if task is None:
        flash("Task not found.")
        return redirect(url_for("tasks"))
    if request.method == "POST":
        if apply_task_form(task):
            db.session.commit()
            flash("Task updated.")
            return redirect(url_for("tasks"))
        flash("Invalid farm or crop.")
    return render_template("task_form.html", task=task, farms=my_farms(), crops=my_crops())


@app.route("/tasks/<int:task_id>/toggle", methods=["POST"])
@login_required
def toggle_task(task_id):
    task = get_my_task(task_id)
    if task:
        task.status = "pending" if task.status == "done" else "done"
        db.session.commit()
    return redirect(url_for("tasks"))


@app.route("/tasks/<int:task_id>/delete", methods=["POST"])
@login_required
def delete_task(task_id):
    task = get_my_task(task_id)
    if task:
        db.session.delete(task)
        db.session.commit()
        flash("Task deleted.")
    return redirect(url_for("tasks"))

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
