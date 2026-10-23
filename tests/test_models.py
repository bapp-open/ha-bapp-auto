"""Pure-Python tests for the API -> model mapping (no Home Assistant needed)."""

from datetime import date

from custom_components.bapp_auto.models import BappAutoData, Car, Document, absolute_url

BASE = "https://panel.bapp.ro"


def car(**over):
    raw = {
        "id": 7,
        "display_name": "Dacia Duster",
        "license_plate": "B 123 ABC",
        "make_name": "Dacia",
        "model_text": "Duster",
        "year": 2019,
        "vin": "UU1",
        "mileage": "123456",
        "mileage_updated_at": "2026-10-20T10:00:00Z",
        "photo": "/media/cars/7.jpg",
        "is_owner": True,
        "enabled": True,
        "is_active": True,
    }
    raw.update(over)
    return raw


def doc(**over):
    raw = {
        "id": 1,
        "car": 7,
        "document_type": "rca",
        "document_type_display": "RCA (Asigurare)",
        "expiration_date": "2026-12-01",
        "days_until_expiration": 39,
        "is_expired": False,
        "is_expiring_soon": False,
        "status_level": "ok",
    }
    raw.update(over)
    return raw


def test_car_photo_is_made_absolute():
    c = Car.from_api(car(), BASE)
    assert c.photo_url == "https://panel.bapp.ro/media/cars/7.jpg"
    assert c.mileage == 123456
    assert c.mileage_updated_at is not None and c.mileage_updated_at.tzinfo is not None


def test_car_photo_falls_back_to_img_tag_and_keeps_signed_urls():
    c = Car.from_api(car(photo=None, photo_img='<img src="https://s3.example/x.jpg?sig=1" />'), BASE)
    assert c.photo_url == "https://s3.example/x.jpg?sig=1"
    assert absolute_url(BASE, "https://cdn/x.png") == "https://cdn/x.png"
    assert Car.from_api(car(photo=None, photo_img=""), BASE).photo_url is None


def test_car_tolerates_missing_fields():
    c = Car.from_api({"id": "3", "license_plate": "CJ 01 XYZ"}, BASE)
    assert c.display_name == "CJ 01 XYZ"
    assert c.mileage is None and c.year is None
    assert c.is_active is True


def test_build_skips_soft_deleted_cars_and_orphan_documents():
    data = BappAutoData.build(
        BASE,
        cars=[car(), car(id=8, is_active=False)],
        car_documents=[doc(), doc(id=2, car=8), doc(id=3, car=99)],
        service_records=[],
        user_documents=[],
    )
    assert list(data.cars) == [7]
    assert list(data.car_documents(7)) == ["rca"]
    assert data.car_documents(8) == {}


def test_renewed_document_replaces_the_old_one():
    data = BappAutoData.build(
        BASE,
        cars=[car()],
        car_documents=[
            doc(id=1, expiration_date="2026-01-01", is_expired=True),
            doc(id=2, expiration_date="2027-01-01"),
        ],
        service_records=[],
        user_documents=[],
    )
    assert data.car_documents(7)["rca"].id == 2
    assert data.attention_count(7) == 0


def test_other_documents_stay_separate_and_use_their_own_label():
    data = BappAutoData.build(
        BASE,
        cars=[car()],
        car_documents=[
            doc(id=1, document_type="other", document_type_other="Tahograf", document_type_display="Altele"),
            doc(id=2, document_type="other", document_type_other="Autorizatie", document_type_display="Altele"),
        ],
        service_records=[],
        user_documents=[],
    )
    docs = data.car_documents(7)
    assert set(docs) == {"other_1", "other_2"}
    assert docs["other_1"].label == "Tahograf"


def test_next_expiring_and_attention_count():
    data = BappAutoData.build(
        BASE,
        cars=[car()],
        car_documents=[
            doc(id=1, document_type="rca", expiration_date="2026-12-01"),
            doc(id=2, document_type="itp", expiration_date="2026-10-25", is_expiring_soon=True),
            doc(id=3, document_type="vignette", expiration_date="2026-10-01", is_expired=True),
        ],
        service_records=[],
        user_documents=[],
    )
    assert data.next_expiring(7).document_type == "vignette"
    assert data.attention_count(7) == 2


def test_service_records_keep_the_latest_per_type():
    data = BappAutoData.build(
        BASE,
        cars=[car()],
        car_documents=[],
        service_records=[
            {"id": 1, "car": 7, "service_type": "oil", "service_date": "2025-01-01", "next_service_date": "2026-01-01"},
            {
                "id": 2,
                "car": 7,
                "service_type": "oil",
                "service_date": "2026-01-05",
                "next_service_date": "2027-01-05",
                "next_service_mileage": 150000,
            },
        ],
        user_documents=[],
    )
    rec = data.car_services(7)["oil"]
    assert rec.id == 2
    assert rec.next_service_date == date(2027, 1, 5)
    assert rec.next_service_mileage == 150000


def test_user_documents_are_grouped_by_type():
    data = BappAutoData.build(
        BASE,
        cars=[],
        car_documents=[],
        service_records=[],
        user_documents=[
            {"id": 1, "document_type": "driving_license", "document_type_display": "Permis", "expiration_date": "2030-01-01"},
        ],
    )
    assert data.user_documents["driving_license"].label == "Permis"
    assert Document.from_api({"id": 5}).document_type == "other"
