from app.schemas import RecordCreate, RecordResponse, ErrorResponse, ContentType


def test_record_create_schema():
    record = RecordCreate(content_type=ContentType.TEXT, content="Hello world")
    assert record.content_type == ContentType.TEXT
    assert record.content == "Hello world"


def test_error_response_schema():
    error = ErrorResponse(code="NOT_FOUND", message="Record not found")
    assert error.code == "NOT_FOUND"
    assert error.message == "Record not found"


def test_content_type_enum():
    assert ContentType.TEXT.value == "text"
    assert ContentType.VOICE.value == "voice"
    assert ContentType.PHOTO.value == "photo"