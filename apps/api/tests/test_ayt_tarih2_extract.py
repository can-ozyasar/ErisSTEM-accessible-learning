from app.pipeline.ayt_tarih2_extract import _year_in_question_box


def test_year_binding_requires_question_box_containment():
    labels = [
        (2019, (224, 218, 265, 232)),
        (2022, (476, 242, 517, 255)),
    ]
    assert _year_in_question_box(labels, (0, 101, 320, 233)) == 2019
    assert _year_in_question_box(labels, (320, 65, 552, 256)) == 2022
    assert _year_in_question_box(labels, (0, 300, 320, 400)) is None
