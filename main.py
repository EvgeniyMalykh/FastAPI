from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from extensions import db

def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///example.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)

    @app.route("/clients", methods=["GET"])
    def get_clients():
        clients = Client.query.all()
        return jsonify(
            [
                {
                    "id": c.id,
                    "name": c.name,
                    "surname": c.surname,
                    "credit_card": c.credit_card,
                    "car_number": c.car_number,
                }
                for c in clients
            ]
        )

    @app.route("/clients/<int:client_id>", methods=["GET"])
    def get_client(client_id):
        client = Client.query.get_or_404(client_id)
        return jsonify(
            {
                "id": client.id,
                "name": client.name,
                "surname": client.surname,
                "credit_card": client.credit_card,
                "car_number": client.car_number,
            }
        )

    @app.route("/clients", methods=["POST"])
    def create_client():
        data = request.get_json()
        if not data:
            return jsonify({"error": "Отсутствуют данные"}), 400

        name = data.get("name")
        surname = data.get("surname")
        credit_card = data.get("credit_card")
        car_number = data.get("car_number")

        if not name or not surname:
            return jsonify({"error": "Поля name и surname обязательны"}), 400

        client = Client(
            name=name, surname=surname, credit_card=credit_card, car_number=car_number
        )
        db.session.add(client)
        db.session.commit()
        return jsonify({"message": "Клиент создан", "id": client.id}), 201

    @app.route("/parkings", methods=["POST"])
    def create_parking():
        data = request.get_json()
        if not data:
            return jsonify({"error": "Отсутствуют данные"}), 400

        address = data.get("address")
        opened = data.get("opened", True)
        count_places = data.get("count_places")
        count_available_places = data.get("count_available_places")

        if not address or count_places is None or count_available_places is None:
            return (
                jsonify(
                    {
                        "error": "Поля address, count_places "
                        "и count_available_places обязательны"
                    }
                ),
                400,
            )

        if count_available_places > count_places:
            return (
                jsonify(
                    {
                        "error": "count_available_places "
                        "не может быть больше count_places"
                    }
                ),
                400,
            )

        parking = Parking(
            address=address,
            opened=bool(opened),
            count_places=int(count_places),
            count_available_places=int(count_available_places),
        )
        db.session.add(parking)
        db.session.commit()
        return jsonify({"message": "Парковка создана", "id": parking.id}), 201

    @app.route("/client_parkings", methods=["POST"])
    def enter_parking():
        data = request.get_json()
        if not data:
            return jsonify({"error": "Отсутствуют данные"}), 400

        client_id = data.get("client_id")
        parking_id = data.get("parking_id")

        if not client_id or not parking_id:
            return jsonify({"error": "client_id и parking_id обязательны"}), 400

        client = Client.query.get(client_id)
        if not client:
            return jsonify({"error": "Клиент не найден"}), 404
        parking = Parking.query.get(parking_id)
        if not parking:
            return jsonify({"error": "Парковка не найдена"}), 404

        if not parking.opened:
            return jsonify({"error": "Парковка закрыта"}), 400

        if parking.count_available_places <= 0:
            return jsonify({"error": "Свободных мест нет"}), 400

        active_entry = ClientParking.query.filter_by(
            client_id=client_id, parking_id=parking_id, time_out=None
        ).first()
        if active_entry:
            return jsonify({"error": "Клиент уже находится на этой парковке"}), 400

        cp = ClientParking(
            client_id=client_id,
            parking_id=parking_id,
            time_in=datetime.utcnow(),
            time_out=None,
        )
        parking.count_available_places -= 1

        db.session.add(cp)
        db.session.commit()

        return (
            jsonify({"message": "Заезд зафиксирован", "client_parking_id": cp.id}),
            201,
        )

    @app.route("/client_parkings", methods=["DELETE"])
    def exit_parking():
        data = request.get_json()
        if not data:
            return jsonify({"error": "Отсутствуют данные"}), 400

        client_id = data.get("client_id")
        parking_id = data.get("parking_id")

        if not client_id or not parking_id:
            return jsonify({"error": "client_id и parking_id обязательны"}), 400

        client = Client.query.get(client_id)
        if not client:
            return jsonify({"error": "Клиент не найден"}), 404

        if not client.credit_card:
            return (
                jsonify(
                    {
                        "error": "У клиента не привязана "
                        "кредитная карта, оплата невозможна"
                    }
                ),
                400,
            )

        parking = Parking.query.get(parking_id)
        if not parking:
            return jsonify({"error": "Парковка не найдена"}), 404

        active_entry = ClientParking.query.filter_by(
            client_id=client_id, parking_id=parking_id, time_out=None
        ).first()
        if not active_entry:
            return jsonify({"error": "Активный заезд не найден"}), 404

        active_entry.time_out = datetime.utcnow()
        parking.count_available_places += 1

        db.session.commit()

        return jsonify({"message": "Выезд зафиксирован, оплата произведена"}), 200

    return app


class Client(db.Model):
    __tablename__ = "client"

    id = db.Column(db.Integer, primary_key=True, nullable=False)
    name = db.Column(db.String(50), nullable=False)
    surname = db.Column(db.String(50), nullable=False)
    credit_card = db.Column(db.String(50))
    car_number = db.Column(db.String(10))

    parkings = db.relationship("ClientParking", back_populates="client")


class Parking(db.Model):
    __tablename__ = "parking"

    id = db.Column(db.Integer, primary_key=True, nullable=False)
    address = db.Column(db.String(100), nullable=False)
    opened = db.Column(db.Boolean)
    count_places = db.Column(db.Integer, nullable=False)
    count_available_places = db.Column(db.Integer, nullable=False)

    clients = db.relationship("ClientParking", back_populates="parking")


class ClientParking(db.Model):
    __tablename__ = "client_parking"

    id = db.Column(db.Integer, primary_key=True, nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"))
    parking_id = db.Column(db.Integer, db.ForeignKey("parking.id"))
    time_in = db.Column(db.DateTime)
    time_out = db.Column(db.DateTime)

    __table_args__ = (
        db.UniqueConstraint("client_id", "parking_id", name="unique_client_parking"),
    )

    client = db.relationship("Client", back_populates="parkings")
    parking = db.relationship("Parking", back_populates="clients")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        db.create_all()
    print("Таблицы созданы в базе данных.")
    app.run(debug=True)
