import pytest
from botocore.exceptions import ClientError, EndpointConnectionError, NoCredentialsError
from gene2image import s3_images

URL = "https://zfin.org/imageLoadUp/2005/ZDB-PUB-1/ZDB-IMAGE-1.jpg"
KEY = "gene2fish/zfin-images/imageLoadUp/2005/ZDB-PUB-1/ZDB-IMAGE-1.jpg"


class _Body:
    def __init__(self, data: bytes):
        self._data = data
        self.closed = False

    def read(self):
        return self._data

    def close(self):
        self.closed = True


class _FakeS3:
    def __init__(self, result):
        self._result = result
        self.calls = []

    def get_object(self, Bucket, Key):
        self.calls.append((Bucket, Key))
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def _client_error(code: str, status: int) -> ClientError:
    return ClientError(
        {"Error": {"Code": code, "Message": code}, "ResponseMetadata": {"HTTPStatusCode": status}},
        "GetObject",
    )


@pytest.fixture
def mirror(monkeypatch):
    monkeypatch.setenv("GENE2IMAGE_IMAGE_S3_BUCKET", "test-bucket")
    monkeypatch.delenv("GENE2IMAGE_IMAGE_S3_PREFIX", raising=False)

    def install(result):
        fake = _FakeS3(result)
        monkeypatch.setattr(s3_images, "_get_client", lambda: fake)
        return fake

    return install


def test_fetch_image_returns_mirrored_bytes(mirror):
    body = _Body(b"jpeg-bytes")
    fake = mirror({"Body": body, "ContentType": "image/jpeg"})

    assert s3_images.fetch_image(URL) == (b"jpeg-bytes", "image/jpeg")
    assert fake.calls == [("test-bucket", KEY)]
    assert body.closed  # connection released back to the pool


def test_fetch_image_missing_object_is_a_miss(mirror):
    mirror(_client_error("NoSuchKey", 404))

    assert s3_images.fetch_image(URL) is None


@pytest.mark.parametrize(
    "error",
    [
        _client_error("AccessDenied", 403),
        _client_error("NoSuchBucket", 404),
        NoCredentialsError(),
        EndpointConnectionError(endpoint_url="https://s3.us-west-2.amazonaws.com"),
    ],
    ids=["access-denied", "no-such-bucket", "no-credentials", "network"],
)
def test_fetch_image_raises_when_the_mirror_cannot_be_read(mirror, error):
    # Permissions, credentials, a missing bucket or the network failing do not
    # mean "not mirrored": they must surface, never pass as a miss.
    mirror(error)

    with pytest.raises(s3_images.ImageMirrorError):
        s3_images.fetch_image(URL)


def test_fetch_image_refuses_non_image_objects(mirror):
    # The proxy serves mirror bytes from our own origin, so a non-image object
    # (e.g. HTML) must never be returned where it could render as a document.
    mirror({"Body": _Body(b"<script>alert(1)</script>"), "ContentType": "text/html"})

    with pytest.raises(s3_images.ImageMirrorError):
        s3_images.fetch_image(URL)


def test_fetch_image_raises_when_the_s3_client_is_unavailable(monkeypatch):
    monkeypatch.setenv("GENE2IMAGE_IMAGE_S3_BUCKET", "test-bucket")
    monkeypatch.setattr(s3_images, "_get_client", lambda: None)

    with pytest.raises(s3_images.ImageMirrorError):
        s3_images.fetch_image(URL)


def test_fetch_image_chains_the_s3_client_construction_error(monkeypatch):
    import boto3

    boom = ValueError("bad region")

    def bad_client(*args, **kwargs):
        raise boom

    monkeypatch.setenv("GENE2IMAGE_IMAGE_S3_BUCKET", "test-bucket")
    monkeypatch.setattr(s3_images, "_client", None)
    monkeypatch.setattr(s3_images, "_client_unavailable", False)
    monkeypatch.setattr(s3_images, "_client_error", None)
    monkeypatch.setattr(boto3, "client", bad_client)

    with pytest.raises(s3_images.ImageMirrorError) as excinfo:
        s3_images.fetch_image(URL)

    assert excinfo.value.__cause__ is boom


def test_fetch_image_non_zfin_url_is_a_miss_without_touching_s3(mirror):
    fake = mirror({"Body": _Body(b"x"), "ContentType": "image/jpeg"})

    assert s3_images.fetch_image("https://example.com/x.jpg") is None
    assert fake.calls == []
